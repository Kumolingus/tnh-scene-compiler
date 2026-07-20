"""Tests for the condition builder pure-logic helpers."""

import pytest

from tnh_scene_compiler.condition_builder import (
    build_condition,
    combine_conditions,
    resolve_method_path,
    wrap_condition,
)


# -- build_condition ---------------------------------------------------------

class TestBuildConditionApproval:
    def test_numeric_threshold(self):
        result = build_condition(
            "approval", character="JeanGrey", axis="love", threshold="500",
        )
        assert result == "JeanGrey.love >= 500"

    def test_trust_numeric(self):
        result = build_condition(
            "approval", character="Rogue", axis="trust", threshold="300",
        )
        assert result == "Rogue.trust >= 300"

    def test_tier_name_still_works(self):
        result = build_condition(
            "approval", character="JeanGrey", axis="love", threshold="medium",
        )
        assert result == "JeanGrey.love >= medium"


class TestBuildConditionTrait:
    def test_basic(self):
        result = build_condition("trait", character="JeanGrey", trait="shy")
        assert result == 'JeanGrey.has("shy")'

    def test_empty_trait(self):
        result = build_condition("trait", character="JeanGrey", trait="")
        assert result == 'JeanGrey.has("")'


class TestBuildConditionHistory:
    def test_basic(self):
        result = build_condition(
            "history", character="JeanGrey", event="kissed_player",
        )
        assert result == 'JeanGrey.did("kissed_player")'


class TestBuildConditionMood:
    def test_basic(self):
        result = build_condition("mood", character="KurtWagner", mood="normal")
        assert result == 'KurtWagner.mood == "normal"'

    def test_custom_mood(self):
        result = build_condition("mood", character="JeanGrey", mood="flirty")
        assert result == 'JeanGrey.mood == "flirty"'


class TestBuildConditionFriendship:
    def test_basic(self):
        result = build_condition(
            "friendship", character="JeanGrey", other_character="Rogue",
        )
        assert result == "JeanGrey.friends_with(Rogue)"


class TestBuildConditionNearby:
    def test_basic(self):
        result = build_condition("nearby", character="LauraKinney")
        assert result == "LauraKinney.nearby"


class TestBuildConditionPersonality:
    def test_without_threshold(self):
        result = build_condition(
            "personality", character="JeanGrey", trait="bold",
        )
        assert result == 'JeanGrey.personality("bold")'

    def test_with_threshold(self):
        result = build_condition(
            "personality", character="JeanGrey", trait="bold", threshold="3",
        )
        assert result == 'JeanGrey.personality("bold", 3)'

    def test_empty_threshold_ignored(self):
        result = build_condition(
            "personality", character="JeanGrey", trait="bold", threshold="",
        )
        assert result == 'JeanGrey.personality("bold")'


class TestBuildConditionFunction:
    def test_no_args(self):
        result = build_condition("function", func_name="get_Location")
        assert result == "get_Location()"

    def test_with_args(self):
        result = build_condition(
            "function", func_name="seen_Player_recently",
            func_args="JeanGrey",
        )
        assert result == "seen_Player_recently(JeanGrey)"

    def test_empty_args(self):
        result = build_condition(
            "function", func_name="get_Location", func_args="",
        )
        assert result == "get_Location()"

    def test_with_comparison(self):
        result = build_condition(
            "function", func_name="get_effective_friendship",
            func_args="JeanGrey, Rogue", compare_op=">=", compare_value="2",
        )
        assert result == "get_effective_friendship(JeanGrey, Rogue) >= 2"

    def test_comparison_operator_without_value_stays_bare(self):
        # Operator chosen but value not yet typed -> no trailing comparison.
        result = build_condition(
            "function", func_name="get_effective_friendship",
            func_args="JeanGrey, Rogue", compare_op=">=", compare_value="",
        )
        assert result == "get_effective_friendship(JeanGrey, Rogue)"

    def test_empty_operator_stays_bare(self):
        result = build_condition(
            "function", func_name="are_Characters_friends",
            func_args="[JeanGrey, Rogue]", compare_op="", compare_value="9",
        )
        assert result == "are_Characters_friends([JeanGrey, Rogue])"


class TestBuildConditionMethod:
    def test_no_args(self):
        result = build_condition(
            "method", character="JeanGrey", method_path="get_status",
        )
        assert result == "JeanGrey.get_status()"

    def test_with_args(self):
        result = build_condition(
            "method", character="JeanGrey", method_path="check_trait",
            method_args='"shy"',
        )
        assert result == 'JeanGrey.check_trait("shy")'

    def test_nested_path(self):
        # e.g. History.check, resolved by resolve_method_path from the
        # method's "Character.History.check(...)" signature.
        result = build_condition(
            "method", character="Rogue", method_path="History.check",
            method_args='"kissed_player"',
        )
        assert result == 'Rogue.History.check("kissed_player")'

    def test_with_comparison(self):
        result = build_condition(
            "method", character="JeanGrey", method_path="get_friendship",
            method_args="Rogue", compare_op="<", compare_value="0",
        )
        assert result == "JeanGrey.get_friendship(Rogue) < 0"


class TestBuildConditionUnknownKind:
    def test_returns_empty(self):
        assert build_condition("nonexistent") == ""


# -- resolve_method_path ------------------------------------------------------


class TestResolveMethodPath:
    def test_simple_method(self):
        result = resolve_method_path(
            "Character.check_trait(trait: str) -> bool", "check_trait",
        )
        assert result == "check_trait"

    def test_nested_attribute_chain(self):
        result = resolve_method_path(
            "Character.History.check(Item: str) -> int", "check",
        )
        assert result == "History.check"

    def test_empty_signature_falls_back_to_method_name(self):
        assert resolve_method_path("", "custom_method") == "custom_method"

    def test_unexpected_prefix_falls_back_to_method_name(self):
        # Signature does not start with "Character." — keep the bare name
        # rather than guessing.
        result = resolve_method_path("some_other_shape(x)", "custom_method")
        assert result == "custom_method"


# -- wrap_condition ----------------------------------------------------------

class TestWrapCondition:
    COND = "JeanGrey.love >= medium"

    def test_if_block(self):
        result = wrap_condition(self.COND, "if_block")
        assert result == "[[if JeanGrey.love >= medium]]\n\n[[/if]]\n"

    def test_elif(self):
        result = wrap_condition(self.COND, "elif")
        assert result == "[[elif JeanGrey.love >= medium]]\n"

    def test_if_open(self):
        result = wrap_condition(self.COND, "if_open")
        assert result == "[[if JeanGrey.love >= medium]]\n"

    def test_bare(self):
        result = wrap_condition(self.COND, "bare")
        assert result == self.COND

    def test_unknown_mode_returns_bare(self):
        result = wrap_condition(self.COND, "unknown")
        assert result == self.COND


# -- combine_conditions --------------------------------------------------------


class TestCombineConditions:
    def test_and(self):
        result = combine_conditions("JeanGrey.love >= 500", "and", 'Rogue.has("shy")')
        assert result == 'JeanGrey.love >= 500 and Rogue.has("shy")'

    def test_or(self):
        result = combine_conditions("JeanGrey.nearby", "or", "Rogue.nearby")
        assert result == "JeanGrey.nearby or Rogue.nearby"

    def test_none_mode_returns_first_only(self):
        result = combine_conditions("JeanGrey.love >= 500", "none", "Rogue.nearby")
        assert result == "JeanGrey.love >= 500"

    def test_empty_second_clause_returns_first_only(self):
        # A combine mode is selected but clause B isn't valid/filled yet.
        result = combine_conditions("JeanGrey.love >= 500", "and", "")
        assert result == "JeanGrey.love >= 500"
