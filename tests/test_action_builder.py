"""Tests for the pure-logic helper ``build_action``."""

from tnh_scene_compiler.action_builder import build_action


class TestBuildActionGiveTrait:
    def test_basic(self) -> None:
        result = build_action("give_trait", character="JeanGrey", trait="shy")
        assert result == "[[give_trait JeanGrey shy]]"

    def test_empty_trait(self) -> None:
        result = build_action("give_trait", character="JeanGrey", trait="")
        assert result == "[[give_trait JeanGrey ]]"


class TestBuildActionRemoveTrait:
    def test_basic(self) -> None:
        result = build_action("remove_trait", character="Rogue", trait="bold")
        assert result == "[[remove_trait Rogue bold]]"


class TestBuildActionRecord:
    def test_basic(self) -> None:
        result = build_action("record", character="JeanGrey", event="kissed_player")
        assert result == "[[record JeanGrey kissed_player]]"

    def test_empty_event(self) -> None:
        result = build_action("record", character="JeanGrey", event="")
        assert result == "[[record JeanGrey ]]"


class TestBuildActionSetPersonality:
    def test_basic(self) -> None:
        result = build_action(
            "set_personality", character="JeanGrey", trait="dominant", value="3",
        )
        assert result == "[[set_personality JeanGrey dominant 3]]"


class TestBuildActionRun:
    def test_basic(self) -> None:
        result = build_action("run", func_call="give_trait(\"x\")")
        assert result == '[[run give_trait("x")]]'

    def test_auto_parens(self) -> None:
        result = build_action("run", func_call="my_func")
        assert result == "[[run my_func()]]"

    def test_empty(self) -> None:
        result = build_action("run", func_call="")
        assert result == "[[run ]]"


class TestBuildActionUnknownKind:
    def test_returns_empty(self) -> None:
        result = build_action("nonexistent")
        assert result == ""
