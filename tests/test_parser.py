"""Unit tests for :mod:`tnh_scene_compiler.parser`."""

from __future__ import annotations

from pathlib import Path

import pytest

from tnh_scene_compiler.ast_nodes import DialogueBlock, NarrationBlock, Slugline
from tnh_scene_compiler.errors import CompileError
from tnh_scene_compiler.parser import parse

# Common title-page prefix used by inline-built test inputs. Saves the same
# ``Title:`` / ``Scene Id:`` / ... lines being repeated in every test.
_TITLE_PREFIX = (
    "Title: T\n"
    "Scene Id: s\n"
    "Character: X\n"
    "Scene Type: cinematic\n"
    "Trigger: manual\n"
    "\n"
)


def _read(fixtures_dir: Path, name: str) -> tuple[str, str]:
    """Return ``(text, display_path)`` for fixture ``name``."""
    path = fixtures_dir / name
    return path.read_text(encoding = "utf-8"), path.as_posix()


def test_parse_minimal_scene_title_page_fields(fixtures_dir: Path) -> None:
    text, path = _read(fixtures_dir, "minimal_cinematic.scene")

    scene = parse(text, path = path)

    tp = scene.title_page
    assert tp.title == "Minimal Test Scene"
    assert tp.scene_id == "mymod_scene_minimal"
    assert tp.character == "JeanGrey"
    assert tp.scene_type == "cinematic"
    assert tp.trigger == "manual"
    assert tp.priority == 100
    assert tp.repeatable is False


def test_parse_body_order_is_preserved(fixtures_dir: Path) -> None:
    text, path = _read(fixtures_dir, "minimal_cinematic.scene")

    scene = parse(text, path = path)

    kinds = [type(node).__name__ for node in scene.body]
    assert kinds == [
        "Slugline",
        "NarrationBlock",
        "DialogueBlock",
        "NarrationBlock",
        "DialogueBlock",
    ]


def test_parse_collects_dialogue_text_across_lines() -> None:
    text = _TITLE_PREFIX + "JEANGREY\nLine one.\nLine two.\n"

    scene = parse(text, path = "inline.scene")

    dialogue = [n for n in scene.body if isinstance(n, DialogueBlock)]
    assert len(dialogue) == 1
    assert dialogue[0].text == "Line one. Line two."


def test_parse_rejects_unknown_title_key() -> None:
    text = (
        "Title: T\nBogus: whatever\nScene Id: s\n"
        "Character: X\nScene Type: cinematic\n\n"
    )

    with pytest.raises(CompileError) as excinfo:
        parse(text, path = "inline.scene")

    assert "Bogus" in excinfo.value.message


def test_parse_rejects_missing_required_field() -> None:
    text = "Title: T\nCharacter: X\nScene Type: cinematic\n\n"

    with pytest.raises(CompileError) as excinfo:
        parse(text, path = "inline.scene")

    assert "Scene Id" in excinfo.value.message


def test_parse_rejects_duplicate_title_key() -> None:
    text = (
        "Title: T\nTitle: Other\nScene Id: s\n"
        "Character: X\nScene Type: cinematic\nTrigger: manual\n\n"
    )

    with pytest.raises(CompileError) as excinfo:
        parse(text, path = "inline.scene")

    assert "Title" in excinfo.value.message
    assert "twice" in excinfo.value.message


def test_parse_cinematic_requires_trigger() -> None:
    text = "Title: T\nScene Id: s\nCharacter: X\nScene Type: cinematic\n\n"

    with pytest.raises(CompileError) as excinfo:
        parse(text, path = "inline.scene")

    assert "Trigger" in excinfo.value.message


def test_parse_phone_scene_defaults_trigger_to_manual() -> None:
    text = "Title: T\nScene Id: s\nCharacter: X\nScene Type: phone\n\n"

    scene = parse(text, path = "inline.scene")

    assert scene.title_page.trigger == "manual"


def test_parse_accepts_multiline_parenthetical() -> None:
    text = _TITLE_PREFIX + "JEANGREY\n(mood=sad)\nHello.\n"

    scene = parse(text, path = "inline.scene")

    dialogues = [n for n in scene.body if isinstance(n, DialogueBlock)]
    assert len(dialogues) == 1
    assert dialogues[0].parenthetical is not None
    assert dialogues[0].parenthetical.mood == "sad"


def test_parse_accepts_inline_parenthetical() -> None:
    text = _TITLE_PREFIX + "JEANGREY (happy)\nHello.\n"

    scene = parse(text, path = "inline.scene")

    dialogues = [n for n in scene.body if isinstance(n, DialogueBlock)]
    assert dialogues[0].parenthetical is not None
    assert dialogues[0].parenthetical.mood == "happy"
    assert dialogues[0].text == "Hello."


def test_parse_parenthetical_positional_order() -> None:
    text = _TITLE_PREFIX + "JEANGREY (sad, smirk, crossed)\nHello.\n"

    scene = parse(text, path = "inline.scene")

    paren = next(n for n in scene.body if isinstance(n, DialogueBlock)).parenthetical
    assert paren is not None
    assert paren.mood == "sad"
    assert paren.face == "smirk"
    assert paren.arms == "crossed"


def test_parse_parenthetical_underscore_skip() -> None:
    text = _TITLE_PREFIX + "JEANGREY (_, smirk)\nHello.\n"

    scene = parse(text, path = "inline.scene")

    paren = next(n for n in scene.body if isinstance(n, DialogueBlock)).parenthetical
    assert paren is not None
    assert paren.mood is None
    assert paren.face == "smirk"


def test_parse_parenthetical_named_after_positional_is_rejected() -> None:
    text = _TITLE_PREFIX + "JEANGREY (face=smirk, happy)\nHello.\n"

    with pytest.raises(CompileError) as excinfo:
        parse(text, path = "inline.scene")

    assert "Positional" in excinfo.value.message


def test_parse_parenthetical_text_medium_is_captured() -> None:
    text = _TITLE_PREFIX + "JEANGREY (text)\nHi.\n"

    scene = parse(text, path = "inline.scene")

    paren = next(n for n in scene.body if isinstance(n, DialogueBlock)).parenthetical
    assert paren is not None
    assert paren.medium == "text"


def test_parse_parenthetical_text_plus_visual_is_rejected() -> None:
    text = _TITLE_PREFIX + "JEANGREY (text, face=smirk)\nHi.\n"

    with pytest.raises(CompileError) as excinfo:
        parse(text, path = "inline.scene")

    assert "text" in excinfo.value.message


def test_parse_accepts_pause_directive() -> None:
    text = _TITLE_PREFIX + "[[pause 1]]\n"

    scene = parse(text, path = "inline.scene")

    from tnh_scene_compiler.ast_nodes import Pause
    pauses = [n for n in scene.body if isinstance(n, Pause)]
    assert len(pauses) == 1
    assert pauses[0].seconds == 1.0


def test_parse_rejects_unknown_directive() -> None:
    text = _TITLE_PREFIX + "[[totally_made_up arg]]\n"

    with pytest.raises(CompileError) as excinfo:
        parse(text, path = "inline.scene")

    assert "Unknown directive" in excinfo.value.message


def test_parse_slugline_parts_are_split() -> None:
    text = _TITLE_PREFIX + "INT. JEANGREY'S ROOM\n"

    scene = parse(text, path = "inline.scene")

    sluglines = [n for n in scene.body if isinstance(n, Slugline)]
    assert sluglines
    assert sluglines[0].prefix == "INT."
    assert sluglines[0].text == "JEANGREY'S ROOM"


def test_parse_narration_collects_consecutive_prose() -> None:
    text = _TITLE_PREFIX + "First line.\nSecond line.\n"

    scene = parse(text, path = "inline.scene")

    narrations = [n for n in scene.body if isinstance(n, NarrationBlock)]
    assert len(narrations) == 1
    assert narrations[0].text == "First line. Second line."


def test_parse_title_page_missing_colon_errors() -> None:
    text = "Title: T\nJust a line no colon\n\n"

    with pytest.raises(CompileError) as excinfo:
        parse(text, path = "inline.scene")

    assert "':' separator" in excinfo.value.message


def test_parse_tags_are_split_on_comma() -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: X\n"
        "Scene Type: cinematic\nTrigger: manual\n"
        "Tags: mymod_a, mymod_b\n\n"
    )

    scene = parse(text, path = "inline.scene")

    assert scene.title_page.tags == ("mymod_a", "mymod_b")
