"""Tests for allowlists.py helpers not covered by test_fx_custom_merge.py:
the shared ``parse_signature_params`` used by every GUI param-form builder,
and the ``character_methods.yaml`` signature loading it was added to feed.
"""

from __future__ import annotations

from pathlib import Path

from tnh_scene_compiler.allowlists import Allowlists, parse_signature_params


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
