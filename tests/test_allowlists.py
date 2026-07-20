"""Tests for allowlists.py helpers not covered by test_fx_custom_merge.py:
the shared ``parse_signature_params`` used by every GUI param-form builder,
and the ``character_methods.yaml`` signature loading it was added to feed.
"""

from __future__ import annotations

from pathlib import Path

from tnh_scene_compiler.allowlists import (
    Allowlists,
    group_by_category,
    is_character_param,
    parse_signature_params,
    return_is_comparable,
    signature_return_type,
)


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


# -- parse_signature_params ---------------------------------------------------


class TestParseSignatureParams:
    def test_empty_signature(self) -> None:
        assert parse_signature_params("") == []

    def test_no_parentheses(self) -> None:
        assert parse_signature_params("not a signature") == []

    def test_no_params(self) -> None:
        assert parse_signature_params("f() -> None") == []

    def test_single_untyped_param(self) -> None:
        assert parse_signature_params("f(preference)") == [("preference", "", "")]

    def test_typed_param_with_default(self) -> None:
        result = parse_signature_params("phone_buzz(x: float = 0.5) -> None")
        assert result == [("x", "float", "0.5")]

    def test_multiple_mixed_params(self) -> None:
        result = parse_signature_params(
            "f(Character, preference: str, retries = 3) -> None",
        )
        assert result == [
            ("Character", "", ""),
            ("preference", "str", ""),
            ("retries", "", "3"),
        ]

    def test_ignores_call_path_before_first_paren(self) -> None:
        # ``Character.History.check(...)`` — only the parenthesized part is
        # parsed; the dotted call path in front of it is not a parameter.
        result = parse_signature_params(
            "Character.History.check(Item: str, tracker: str = 'persistent', "
            "after = 0) -> int",
        )
        assert result == [
            ("Item", "str", ""),
            ("tracker", "str", "'persistent'"),
            ("after", "", "0"),
        ]

    def test_comma_inside_nested_call_does_not_split_param(self) -> None:
        result = parse_signature_params("f(x = foo(1, 2), y = 3)")
        assert result == [("x", "", "foo(1, 2)"), ("y", "", "3")]


# -- character_methods.yaml signature loading ---------------------------------


class TestCharacterMethodSignatures:
    def test_signature_is_captured(self, tmp_path: Path) -> None:
        _write(tmp_path / "character_methods.yaml", (
            "methods:\n"
            "- name: check_trait\n"
            "  signature: \"Character.check_trait(trait: str) -> bool\"\n"
        ))

        allowlists = Allowlists.load(tmp_path)

        assert "check_trait" in allowlists.character_methods
        assert (
            allowlists.character_method_signatures["check_trait"]
            == "Character.check_trait(trait: str) -> bool"
        )

    def test_missing_signature_key_is_tolerated(self, tmp_path: Path) -> None:
        _write(tmp_path / "character_methods.yaml", (
            "methods:\n"
            "- name: get_status\n"
        ))

        allowlists = Allowlists.load(tmp_path)

        assert "get_status" in allowlists.character_methods
        assert "get_status" not in allowlists.character_method_signatures

    def test_merge_unions_signatures(self) -> None:
        base = Allowlists(
            character_methods={"check_trait"},
            character_method_signatures={
                "check_trait": "Character.check_trait(trait: str) -> bool",
            },
        )
        mod = Allowlists(
            character_methods={"pregnancy_mod_is_pregnant"},
            character_method_signatures={
                "pregnancy_mod_is_pregnant": "Character.pregnancy_mod_is_pregnant() -> bool",
            },
        )

        merged = base.merge(mod)

        assert merged.character_methods == {"check_trait", "pregnancy_mod_is_pregnant"}
        assert merged.character_method_signatures == {
            "check_trait": "Character.check_trait(trait: str) -> bool",
            "pregnancy_mod_is_pregnant": "Character.pregnancy_mod_is_pregnant() -> bool",
        }


class TestCategoryLoading:
    """The category field on condition_functions / run_operations / character_methods."""

    def test_condition_function_category_is_captured(self, tmp_path: Path) -> None:
        _write(tmp_path / "condition_functions.yaml", (
            "functions:\n"
            "- name: are_Characters_friends\n"
            "  category: Relationships\n"
            "  signature: \"are_Characters_friends(Characters) -> bool\"\n"
        ))

        allowlists = Allowlists.load(tmp_path)

        assert allowlists.condition_function_categories["are_Characters_friends"] == "Relationships"

    def test_run_operation_category_is_captured(self, tmp_path: Path) -> None:
        _write(tmp_path / "run_operations.yaml", (
            "operations:\n"
            "- name: mymod_record_choice\n"
            "  category: Player choice recording\n"
            "  signature: mymod_record_choice(value)\n"
        ))

        allowlists = Allowlists.load(tmp_path)

        assert allowlists.run_operation_categories["mymod_record_choice"] == "Player choice recording"

    def test_missing_category_is_tolerated(self, tmp_path: Path) -> None:
        _write(tmp_path / "condition_functions.yaml", (
            "functions:\n"
            "- name: get_Location\n"
            "  signature: \"get_Location() -> Location\"\n"
        ))

        allowlists = Allowlists.load(tmp_path)

        assert "get_Location" in allowlists.condition_functions
        assert "get_Location" not in allowlists.condition_function_categories

    def test_merge_unions_categories(self) -> None:
        base = Allowlists(
            condition_functions={"check_approval"},
            condition_function_categories={"check_approval": "Approval"},
        )
        mod = Allowlists(
            condition_functions={"pregnancy_mod_is_pregnant"},
            condition_function_categories={"pregnancy_mod_is_pregnant": "Mod state"},
        )

        merged = base.merge(mod)

        assert merged.condition_function_categories == {
            "check_approval": "Approval",
            "pregnancy_mod_is_pregnant": "Mod state",
        }


class TestNotesLoading:
    """The optional writer-facing `notes` field on condition functions / methods."""

    def test_condition_function_note_is_captured_and_stripped(self, tmp_path: Path) -> None:
        _write(tmp_path / "condition_functions.yaml", (
            "functions:\n"
            "- name: get_effective_friendship\n"
            "  signature: \"get_effective_friendship(A, B) -> FriendshipTier\"\n"
            "  notes: |\n"
            "    Returns a tier NUMBER, not a yes/no. Compare it.\n"
        ))

        allowlists = Allowlists.load(tmp_path)

        # Block-scalar trailing newline is stripped on load.
        assert (
            allowlists.condition_function_notes["get_effective_friendship"]
            == "Returns a tier NUMBER, not a yes/no. Compare it."
        )

    def test_character_method_note_is_captured(self, tmp_path: Path) -> None:
        _write(tmp_path / "character_methods.yaml", (
            "methods:\n"
            "- name: get_friendship\n"
            "  signature: \"Character.get_friendship(other: Character) -> int\"\n"
            "  notes: Returns a raw score, compare it.\n"
        ))

        allowlists = Allowlists.load(tmp_path)

        assert allowlists.character_method_notes["get_friendship"] == "Returns a raw score, compare it."

    def test_missing_note_is_tolerated(self, tmp_path: Path) -> None:
        _write(tmp_path / "condition_functions.yaml", (
            "functions:\n"
            "- name: get_Location\n"
            "  signature: \"get_Location() -> Location\"\n"
        ))

        allowlists = Allowlists.load(tmp_path)

        assert "get_Location" in allowlists.condition_functions
        assert "get_Location" not in allowlists.condition_function_notes

    def test_merge_unions_notes(self) -> None:
        base = Allowlists(
            condition_function_notes={"f": "note A"},
            character_method_notes={"m": "note B"},
        )
        mod = Allowlists(
            condition_function_notes={"g": "note C"},
        )

        merged = base.merge(mod)

        assert merged.condition_function_notes == {"f": "note A", "g": "note C"}
        assert merged.character_method_notes == {"m": "note B"}


class TestGroupByCategory:
    def test_groups_and_sorts_within_category(self) -> None:
        result = group_by_category(
            {"get_worst_Enemy", "are_Characters_friends", "check_approval"},
            {
                "get_worst_Enemy": "Relationships",
                "are_Characters_friends": "Relationships",
                "check_approval": "Approval",
            },
        )
        assert result == {
            "Approval": ["check_approval"],
            "Relationships": ["are_Characters_friends", "get_worst_Enemy"],
        }

    def test_categories_sorted_alphabetically(self) -> None:
        result = group_by_category(
            {"z_func", "a_func"},
            {"z_func": "Zebra", "a_func": "Alpha"},
        )
        assert list(result.keys()) == ["Alpha", "Zebra"]

    def test_uncategorized_falls_back_to_other_and_sorts_last(self) -> None:
        result = group_by_category(
            {"known_func", "mystery_func"},
            {"known_func": "Location"},
        )
        assert list(result.keys()) == ["Location", "Other"]
        assert result["Other"] == ["mystery_func"]

    def test_all_uncategorized_still_produces_one_group(self) -> None:
        result = group_by_category({"b_func", "a_func"}, {})
        assert result == {"Other": ["a_func", "b_func"]}

    def test_custom_other_label(self) -> None:
        result = group_by_category(
            {"mystery_func"}, {}, other_label="Uncategorized",
        )
        assert result == {"Uncategorized": ["mystery_func"]}

    def test_empty_names_returns_empty_dict(self) -> None:
        assert group_by_category(set(), {}) == {}


class TestIsCharacterParam:
    def test_bare_character_name_no_annotation(self) -> None:
        # run_operations.yaml convention: pregnancy_mod_foo(Character, x)
        assert is_character_param("Character", "") is True

    def test_typed_character_annotation(self) -> None:
        # character_methods.yaml: Character.get_friendship(other: Character)
        assert is_character_param("other", "Character") is True

    def test_character_class_union_none(self) -> None:
        assert is_character_param("Character", "CharacterClass | None") is True

    def test_plain_character_class(self) -> None:
        assert is_character_param("target", "CharacterClass") is True

    def test_unrelated_typed_param_rejected(self) -> None:
        assert is_character_param("trait", "str") is False

    def test_untyped_non_character_name_rejected(self) -> None:
        assert is_character_param("preference", "") is False

    def test_iterable_of_characters_rejected(self) -> None:
        # Needs a multi-character picker, not this single-value combobox.
        assert is_character_param("Characters", "Iterable[CharacterClass]") is False

    def test_list_of_characters_rejected(self) -> None:
        assert is_character_param("Characters", "list[Character]") is False


class TestReturnType:
    def test_signature_return_type_extracted(self) -> None:
        assert signature_return_type("f(x) -> FriendshipTier") == "FriendshipTier"

    def test_signature_return_type_union(self) -> None:
        assert signature_return_type("f(x) -> bool | int") == "bool | int"

    def test_signature_return_type_missing(self) -> None:
        assert signature_return_type("f(x)") == ""


class TestReturnIsComparable:
    def test_tier_return_is_comparable(self) -> None:
        assert return_is_comparable("get_effective_friendship(A, B) -> FriendshipTier") is True

    def test_int_return_is_comparable(self) -> None:
        assert return_is_comparable("get_friendship(other) -> int") is True

    def test_float_return_is_comparable(self) -> None:
        assert return_is_comparable("chance(x) -> float") is True

    def test_bool_return_is_not_comparable(self) -> None:
        assert return_is_comparable("are_Characters_friends(cs) -> bool") is False

    def test_bool_int_union_is_comparable(self) -> None:
        # check_approval -> bool | int: the int branch is worth comparing.
        assert return_is_comparable("check_approval(c, f, t) -> bool | int") is True

    def test_optional_object_return_is_not_comparable(self) -> None:
        assert return_is_comparable("get_best_Friend(c, cs) -> Character | None") is False

    def test_no_return_type_is_not_comparable(self) -> None:
        assert return_is_comparable("f(x)") is False
