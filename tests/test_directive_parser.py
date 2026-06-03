"""Unit tests for :mod:`tnh_scene_compiler.directive_parser`."""

from __future__ import annotations

import pytest

from tnh_scene_compiler.ast_nodes import Goto, Label, Pause, SetDirective, Sfx
from tnh_scene_compiler.directive_parser import parse_directive
from tnh_scene_compiler.errors import CompileError


def _dir(raw: str):
    return parse_directive(raw, path = "inline.scene", line = 1, col = 1)


def test_pause_integer() -> None:
    node = _dir("[[pause 2]]")

    assert isinstance(node, Pause)
    assert node.seconds == 2.0


def test_pause_float() -> None:
    node = _dir("[[pause 0.5]]")

    assert isinstance(node, Pause)
    assert node.seconds == 0.5


def test_pause_negative_is_rejected() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[pause -1]]")

    assert "non-negative" in excinfo.value.message


def test_pause_non_numeric_is_rejected() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[pause soon]]")

    assert "not a number" in excinfo.value.message


def test_sfx_without_duration() -> None:
    node = _dir("[[sfx phone_buzz]]")

    assert isinstance(node, Sfx)
    assert node.name == "phone_buzz"
    assert node.duration is None


def test_sfx_with_duration() -> None:
    node = _dir("[[sfx phone_buzz 0.3]]")

    assert isinstance(node, Sfx)
    assert node.name == "phone_buzz"
    assert node.duration == 0.3


def test_sfx_rejects_extra_args() -> None:
    with pytest.raises(CompileError):
        _dir("[[sfx phone_buzz 0.3 extra]]")


def test_set_bare_key_maps_to_true() -> None:
    node = _dir("[[set lied_about_sleep]]")

    assert isinstance(node, SetDirective)
    assert node.key == "lied_about_sleep"
    assert node.value is True


def test_set_with_integer_value() -> None:
    node = _dir("[[set attempts = 3]]")

    assert isinstance(node, SetDirective)
    assert node.value == 3


def test_set_with_string_value() -> None:
    node = _dir('[[set note = "hello"]]')

    assert isinstance(node, SetDirective)
    assert node.value == "hello"


def test_set_with_bool_value() -> None:
    node = _dir("[[set keep = true]]")

    assert isinstance(node, SetDirective)
    assert node.value is True


def test_set_rejects_expression_rhs() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[set attempts = foo(1)]]")

    assert "literal" in excinfo.value.message


def test_set_rejects_dotted_key() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[set JeanGrey.mood = true]]")

    assert "run" in excinfo.value.message


def test_label_parses() -> None:
    node = _dir("[[label after_phone_check]]")

    assert isinstance(node, Label)
    assert node.name == "after_phone_check"


def test_label_rejects_non_identifier() -> None:
    with pytest.raises(CompileError):
        _dir("[[label 123bad]]")


def test_goto_parses() -> None:
    node = _dir("[[goto after_phone_check]]")

    assert isinstance(node, Goto)
    assert node.name == "after_phone_check"


def test_run_parses_method_call() -> None:
    from tnh_scene_compiler.ast_nodes import Run
    node = _dir("[[run JeanGrey.give_trait(\"x\")]]")

    assert isinstance(node, Run)
    assert node.target_name == "give_trait"


def test_run_parses_bare_function_call() -> None:
    from tnh_scene_compiler.ast_nodes import Run
    node = _dir("[[run mymod_set_stage(JeanGrey, 2)]]")

    assert isinstance(node, Run)
    assert node.target_name == "mymod_set_stage"


def test_run_rejects_non_call_body() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[run JeanGrey.love]]")

    assert "call" in excinfo.value.message.lower()


def test_run_inherits_expression_grammar_rejections() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[run fn(a + b)]]")

    assert "Arithmetic" in excinfo.value.message


# -- give_trait ---------------------------------------------------------------


def test_give_trait_parses() -> None:
    from tnh_scene_compiler.ast_nodes import GiveTrait
    node = _dir("[[give_trait JeanGrey shy]]")

    assert isinstance(node, GiveTrait)
    assert node.character == "JeanGrey"
    assert node.trait == "shy"


def test_give_trait_rejects_missing_args() -> None:
    with pytest.raises(CompileError):
        _dir("[[give_trait JeanGrey]]")


def test_give_trait_rejects_extra_args() -> None:
    with pytest.raises(CompileError):
        _dir("[[give_trait JeanGrey shy extra]]")


def test_give_trait_rejects_non_identifier_character() -> None:
    with pytest.raises(CompileError):
        _dir("[[give_trait 123 shy]]")


# -- remove_trait -------------------------------------------------------------


def test_remove_trait_parses() -> None:
    from tnh_scene_compiler.ast_nodes import RemoveTrait
    node = _dir("[[remove_trait JeanGrey shy]]")

    assert isinstance(node, RemoveTrait)
    assert node.character == "JeanGrey"
    assert node.trait == "shy"


def test_remove_trait_rejects_missing_args() -> None:
    with pytest.raises(CompileError):
        _dir("[[remove_trait JeanGrey]]")


# -- record -------------------------------------------------------------------


def test_record_parses() -> None:
    from tnh_scene_compiler.ast_nodes import RecordEvent
    node = _dir("[[record JeanGrey kissed_player]]")

    assert isinstance(node, RecordEvent)
    assert node.character == "JeanGrey"
    assert node.event == "kissed_player"


def test_record_rejects_missing_args() -> None:
    with pytest.raises(CompileError):
        _dir("[[record JeanGrey]]")


# -- set_personality ----------------------------------------------------------


def test_set_personality_parses() -> None:
    from tnh_scene_compiler.ast_nodes import SetPersonality
    node = _dir("[[set_personality JeanGrey dominant 3]]")

    assert isinstance(node, SetPersonality)
    assert node.character == "JeanGrey"
    assert node.trait == "dominant"
    assert node.value == 3


def test_set_personality_rejects_non_integer_value() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[set_personality JeanGrey bold abc]]")

    assert "integer" in excinfo.value.message.lower()


def test_set_personality_rejects_missing_args() -> None:
    with pytest.raises(CompileError):
        _dir("[[set_personality JeanGrey dominant]]")


# -- fx -----------------------------------------------------------------------


def test_fx_parses_function_call() -> None:
    from tnh_scene_compiler.ast_nodes import FxCall
    node = _dir("[[fx phone_buzz()]]")

    assert isinstance(node, FxCall)
    assert node.target_name == "phone_buzz"
    assert node.call_text == "phone_buzz()"


def test_fx_rejects_non_call_body() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[fx phone_buzz]]")

    assert "call" in excinfo.value.message.lower()


def test_fx_accepts_call_with_positional_args() -> None:
    from tnh_scene_compiler.ast_nodes import FxCall
    node = _dir("[[fx phone_buzz(0.5, 0.5)]]")

    assert isinstance(node, FxCall)
    assert node.target_name == "phone_buzz"


def test_approval_parses_named_stat_tier_positive() -> None:
    from tnh_scene_compiler.ast_nodes import Approval
    node = _dir("[[approval JeanGrey love +large_stat]]")

    assert isinstance(node, Approval)
    assert node.character == "JeanGrey"
    assert node.axis == "love"
    assert node.magnitude_text == "large_stat"
    assert node.sign == "+"


def test_approval_parses_named_stat_tier_negative() -> None:
    from tnh_scene_compiler.ast_nodes import Approval
    node = _dir("[[approval Rogue trust -medium_stat]]")

    assert isinstance(node, Approval)
    assert node.axis == "trust"
    assert node.magnitude_text == "medium_stat"
    assert node.sign == "-"


def test_approval_parses_integer_literal() -> None:
    from tnh_scene_compiler.ast_nodes import Approval
    node = _dir("[[approval LauraKinney love +25]]")

    assert isinstance(node, Approval)
    assert node.magnitude_text == "25"
    assert node.sign == "+"


def test_approval_rejects_invalid_axis() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[approval JeanGrey lust +large_stat]]")

    assert "axis" in excinfo.value.message.lower()


def test_approval_rejects_unsigned_magnitude() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[approval JeanGrey love large_stat]]")

    assert "sign" in excinfo.value.message.lower()


def test_approval_rejects_unknown_stat_tier() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[approval JeanGrey love +huge_stat]]")

    assert "stat tier" in excinfo.value.message.lower()


def test_approval_rejects_zero_magnitude() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[approval JeanGrey love +0]]")

    assert ">= 1" in excinfo.value.message


def test_approval_rejects_extra_args() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[approval JeanGrey love +large_stat extra]]")

    assert "Malformed" in excinfo.value.message


def test_unknown_bare_directive_is_rejected() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[made_up_thing]]")

    assert "Unknown" in excinfo.value.message


def test_call_parses() -> None:
    from tnh_scene_compiler.ast_nodes import CallScene
    node = _dir("[[call mymod_scene_next]]")

    assert isinstance(node, CallScene)
    assert node.scene_id == "mymod_scene_next"


def test_phone_close_parses() -> None:
    from tnh_scene_compiler.ast_nodes import PhoneClose
    node = _dir("[[phone close]]")

    assert isinstance(node, PhoneClose)


def test_phone_open_without_character() -> None:
    from tnh_scene_compiler.ast_nodes import PhoneOpen
    node = _dir("[[phone open]]")

    assert isinstance(node, PhoneOpen)
    assert node.character is None


def test_phone_open_with_character() -> None:
    from tnh_scene_compiler.ast_nodes import PhoneOpen
    node = _dir("[[phone open JeanGrey]]")

    assert isinstance(node, PhoneOpen)
    assert node.character == "JeanGrey"


def test_phone_unknown_action_is_rejected() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[phone wiggle]]")

    assert "action" in excinfo.value.message


def test_show_requires_named_attrs_only() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[show JeanGrey happy]]")

    assert "key=value" in excinfo.value.message


def test_show_rejects_unknown_attribute() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[show JeanGrey bogus=x]]")

    assert "bogus" in excinfo.value.message


def test_show_parses_multiple_attrs() -> None:
    from tnh_scene_compiler.ast_nodes import Show
    node = _dir("[[show JeanGrey mood=happy face=smirk stage=stage_left]]")

    assert isinstance(node, Show)
    assert node.character == "JeanGrey"
    assert node.attrs == {"mood": "happy", "face": "smirk", "stage": "stage_left"}


def test_hide_parses() -> None:
    from tnh_scene_compiler.ast_nodes import Hide
    node = _dir("[[hide JeanGrey]]")

    assert isinstance(node, Hide)
    assert node.character == "JeanGrey"


def test_fade_to_black_parses() -> None:
    from tnh_scene_compiler.ast_nodes import Fade
    node = _dir("[[fade to black]]")

    assert isinstance(node, Fade)
    assert node.to_black is True
    assert node.duration == 0.4


def test_fade_from_black_parses() -> None:
    from tnh_scene_compiler.ast_nodes import Fade
    node = _dir("[[fade from black]]")

    assert isinstance(node, Fade)
    assert node.to_black is False
    assert node.duration == 0.4


def test_fade_with_explicit_duration() -> None:
    from tnh_scene_compiler.ast_nodes import Fade
    node = _dir("[[fade to black 0.6]]")

    assert isinstance(node, Fade)
    assert node.to_black is True
    assert node.duration == 0.6


def test_fade_malformed_is_rejected() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[fade sideways]]")

    assert "Malformed [[fade]]" in excinfo.value.message


def test_fade_non_numeric_duration_is_rejected() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[fade to black soon]]")

    assert "not a number" in excinfo.value.message


def test_fade_negative_duration_is_rejected() -> None:
    with pytest.raises(CompileError) as excinfo:
        _dir("[[fade to black -1]]")

    assert "non-negative" in excinfo.value.message
