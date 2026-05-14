"""Tests for the condition builder pure-logic helpers."""

import pytest

from tnh_scene_compiler.condition_builder import build_condition, wrap_condition


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


class TestBuildConditionUnknownKind:
    def test_returns_empty(self):
        assert build_condition("nonexistent") == ""


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
