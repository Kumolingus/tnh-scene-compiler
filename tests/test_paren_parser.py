"""Unit tests for :mod:`tnh_scene_compiler.paren_parser` -- parenthetical grammar."""

from __future__ import annotations

import pytest

from tnh_scene_compiler.errors import CompileError
from tnh_scene_compiler.paren_parser import parse_parenthetical


def _p(raw: str):
    return parse_parenthetical(raw, path = "inline.scene", line = 1, col = 1)


def test_empty_parenthetical_is_legal() -> None:
    result = _p("()")

    assert result.mood is None
    assert result.face is None


def test_single_positional_is_mood() -> None:
    result = _p("(happy)")

    assert result.mood == "happy"


def test_full_positional_order() -> None:
    # (mood, face, arms, look, outfit, stage)
    result = _p("(sad, crying, covering_face, down, Pajamas, left)")

    assert result.mood == "sad"
    assert result.face == "crying"
    assert result.arms == "covering_face"
    assert result.look == "down"
    assert result.outfit == "Pajamas"
    assert result.stage == "left"


def test_named_only() -> None:
    result = _p("(mood=sad, face=smirk)")

    assert result.mood == "sad"
    assert result.face == "smirk"


def test_mixed_positional_then_named() -> None:
    result = _p("(happy, face=worried1, look=at_player)")

    assert result.mood == "happy"
    assert result.face == "worried1"
    assert result.look == "at_player"


def test_underscore_skips_positional_slot() -> None:
    result = _p("(_, smirk)")

    assert result.mood is None
    assert result.face == "smirk"


def test_underscore_skips_two_slots() -> None:
    result = _p("(_, _, crossed)")

    assert result.arms == "crossed"
    assert result.mood is None
    assert result.face is None


def test_named_only_left_arm_and_right_arm() -> None:
    result = _p("(left_arm=bra, right_arm=hip)")

    assert result.left_arm == "bra"
    assert result.right_arm == "hip"


def test_text_medium_is_captured() -> None:
    result = _p("(text)")

    assert result.medium == "text"
    assert not result.has_visuals()


def test_spoken_medium_is_captured() -> None:
    result = _p("(spoken)")

    assert result.medium == "spoken"


def test_text_medium_plus_visual_is_rejected() -> None:
    with pytest.raises(CompileError) as excinfo:
        _p("(text, face=smirk)")

    assert "text" in excinfo.value.message
    assert "visual" in excinfo.value.message.lower()


def test_named_after_positional_is_rejected() -> None:
    with pytest.raises(CompileError) as excinfo:
        _p("(face=smirk, happy)")

    assert "Positional" in excinfo.value.message


def test_slot_filled_twice_is_rejected() -> None:
    with pytest.raises(CompileError) as excinfo:
        _p("(happy, mood=sad)")

    assert "mood" in excinfo.value.message
    assert "already" in excinfo.value.message


def test_unknown_key_is_rejected_with_list() -> None:
    with pytest.raises(CompileError) as excinfo:
        _p("(bogus=x)")

    assert "bogus" in excinfo.value.message


def test_too_many_positional_values_are_rejected() -> None:
    with pytest.raises(CompileError) as excinfo:
        _p("(a, b, c, d, e, f, g)")

    assert "positional" in excinfo.value.message.lower()


def test_empty_positional_token_is_rejected() -> None:
    with pytest.raises(CompileError) as excinfo:
        _p("(,)")

    # Empty body after comma-split. The message mentions 'Empty'.
    assert "Empty" in excinfo.value.message
