"""The two insert dialogs must emit lines that COMPILE, and hide what does not apply.

Same discipline as ``test_condition_builder_roundtrip``: a dialog that writes
scene source is only correct if the source it writes survives ``parse`` +
``validate``. Asserting on the string ``_build_line`` returns would restate the
implementation; these tests feed it back through the real pipeline, against the
**shipped base allowlists** and with values taken from those allowlists rather
than hardcoded, so an allowlist change cannot quietly invalidate the sweep.

Also covers the two visibility rules, which are about what a writer can reach:
a text message carries no visuals, and the per-arm slots stay folded away until
asked for.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.editor import _CharacterInsertDialog, _DirectiveDialog
from tnh_scene_compiler.parser import parse
from tnh_scene_compiler.validator import validate

BASE_ALLOWLISTS = Path(__file__).resolve().parents[1] / "allowlists_base"

_HEAD = (
    "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
    "Scene Type: cinematic\nTrigger: manual\n\n"
)

# ``tk_root`` is the session-scoped fixture in conftest.py.


@pytest.fixture(scope="module")
def base_allow() -> Allowlists:
    """The allowlists the packaged app ships with."""
    return Allowlists.load(BASE_ALLOWLISTS)


@pytest.fixture(scope="module")
def rich_char(base_allow: Allowlists) -> str:
    """A shipped character that declares all four visual slots.

    Chosen from the data instead of named outright: the point is to exercise
    every slot, and which character carries them is the allowlists' business.
    """
    for char in sorted(base_allow.characters):
        if all((
            base_allow.char_faces.get(char),
            base_allow.char_arms.get(char),
            base_allow.char_left_arm.get(char),
            base_allow.char_right_arm.get(char),
        )):
            return char
    pytest.skip("no shipped character declares all four visual slots")


def _first(values: set[str]) -> str:
    return sorted(values)[0]


def assert_line_compiles(line: str, allow: Allowlists) -> None:
    """The dialog's output must survive the parser and the validator."""
    assert line, "the dialog produced an empty line"
    scene = parse(_HEAD + line + "\nHello.\n", path="roundtrip.scene")
    errors = validate(scene, allow)
    assert errors == [], [e.message for e in errors]


# -- Character insert dialog --------------------------------------------------

def _insert_dialog(root, allow, char):
    return _CharacterInsertDialog(root, char, allow, lambda _t: None)


def test_every_visual_slot_round_trips(tk_root, base_allow, rich_char):
    """A line carrying face + preset + both side overrides must compile.

    ``left_arm`` / ``right_arm`` are named-only keys in the parenthetical
    grammar and the dialog had never emitted them before.
    """
    dialog = _insert_dialog(tk_root, base_allow, rich_char)
    try:
        dialog._mood_var.set(_first(
            base_allow.shared_moods | base_allow.char_moods.get(rich_char, set())
        ))
        dialog._face_var.set(_first(base_allow.char_faces[rich_char]))
        dialog._arms_var.set(_first(base_allow.char_arms[rich_char]))
        dialog._per_arm_var.set(True)
        dialog._on_per_arm_change()
        dialog._left_arm_var.set(_first(base_allow.char_left_arm[rich_char]))
        dialog._right_arm_var.set(_first(base_allow.char_right_arm[rich_char]))

        line = dialog._build_line()
        assert "left_arm=" in line and "right_arm=" in line
        assert_line_compiles(line, base_allow)
    finally:
        dialog.destroy()


def test_preset_and_one_side_override_compile_together(tk_root, base_allow, rich_char):
    """``arms=<preset>, right_arm=<side>`` is legal and must stay reachable.

    ``change_arms`` takes the preset as its defaults and lets a side kwarg
    override that side (npcs.rpy:256), so this is not a contradiction — which
    is why the checkbox reveals the side rows instead of replacing the preset.
    """
    dialog = _insert_dialog(tk_root, base_allow, rich_char)
    try:
        dialog._arms_var.set(_first(base_allow.char_arms[rich_char]))
        dialog._per_arm_var.set(True)
        dialog._on_per_arm_change()
        dialog._right_arm_var.set(_first(base_allow.char_right_arm[rich_char]))

        line = dialog._build_line()
        assert "arms=" in line and "right_arm=" in line
        assert_line_compiles(line, base_allow)
    finally:
        dialog.destroy()


def _row_visible(dialog, name: str) -> bool:
    """Whether a named field row is currently gridded."""
    caption, combo, _var = dialog._fields[name]
    return bool(caption.winfo_manager()) and bool(combo.winfo_manager())


def test_per_arm_rows_are_hidden_until_asked_for(tk_root, base_allow, rich_char):
    dialog = _insert_dialog(tk_root, base_allow, rich_char)
    try:
        assert not _row_visible(dialog, "left arm")
        assert not _row_visible(dialog, "right arm")
        assert _row_visible(dialog, "arms")

        dialog._per_arm_var.set(True)
        dialog._on_per_arm_change()
        assert _row_visible(dialog, "left arm")
        assert _row_visible(dialog, "right arm")
        # The preset is not replaced by the override.
        assert _row_visible(dialog, "arms")
    finally:
        dialog.destroy()


def test_hiding_the_per_arm_rows_clears_them(tk_root, base_allow, rich_char):
    """A slot the writer can no longer see must stop feeding the line."""
    dialog = _insert_dialog(tk_root, base_allow, rich_char)
    try:
        dialog._per_arm_var.set(True)
        dialog._on_per_arm_change()
        dialog._left_arm_var.set(_first(base_allow.char_left_arm[rich_char]))
        assert "left_arm=" in dialog._build_line()

        dialog._per_arm_var.set(False)
        dialog._on_per_arm_change()
        assert dialog._left_arm_var.get() == ""
        assert "left_arm=" not in dialog._build_line()
    finally:
        dialog.destroy()


def test_text_medium_hides_every_visual_row(tk_root, base_allow, rich_char):
    """Text messages carry no visuals; the rows go away rather than grey out."""
    dialog = _insert_dialog(tk_root, base_allow, rich_char)
    try:
        dialog._face_var.set(_first(base_allow.char_faces[rich_char]))

        dialog._medium_var.set("text")
        dialog._on_medium_change()
        for name in ("mood", "face", "arms", "outfit", "look"):
            assert not _row_visible(dialog, name), name
        assert not dialog._per_arm_check.winfo_manager()
        assert dialog._face_var.get() == ""
        assert dialog._build_line().endswith("(text)")
    finally:
        dialog.destroy()


def test_switching_back_to_spoken_restores_the_rows(tk_root, base_allow, rich_char):
    """...but the per-arm rows come back only if the checkbox still says so."""
    dialog = _insert_dialog(tk_root, base_allow, rich_char)
    try:
        dialog._medium_var.set("text")
        dialog._on_medium_change()
        dialog._medium_var.set("spoken")
        dialog._on_medium_change()

        for name in ("mood", "face", "arms", "outfit", "look"):
            assert _row_visible(dialog, name), name
        assert not _row_visible(dialog, "left arm")

        dialog._per_arm_var.set(True)
        dialog._on_per_arm_change()
        dialog._medium_var.set("text")
        dialog._on_medium_change()
        dialog._medium_var.set("spoken")
        dialog._on_medium_change()
        assert _row_visible(dialog, "left arm")
    finally:
        dialog.destroy()


def test_a_text_line_round_trips(tk_root, base_allow, rich_char):
    dialog = _insert_dialog(tk_root, base_allow, rich_char)
    try:
        dialog._medium_var.set("text")
        dialog._on_medium_change()
        assert_line_compiles(dialog._build_line(), base_allow)
    finally:
        dialog.destroy()


# -- [[show]] directive dialog ------------------------------------------------

def test_show_directive_round_trips_every_slot(tk_root, base_allow, rich_char):
    dialog = _DirectiveDialog(tk_root, "show", base_allow, lambda _t: None)
    try:
        dialog._vars["char"].set(rich_char)
        dialog._vars["face"].set(_first(base_allow.char_faces[rich_char]))
        dialog._vars["arms"].set(_first(base_allow.char_arms[rich_char]))
        dialog._per_arm_var.set(True)
        dialog._on_per_arm_change()
        dialog._vars["left_arm"].set(_first(base_allow.char_left_arm[rich_char]))
        dialog._vars["right_arm"].set(_first(base_allow.char_right_arm[rich_char]))

        line = dialog._build_line()
        assert "left_arm=" in line and "right_arm=" in line
        assert_line_compiles(line, base_allow)
    finally:
        dialog.destroy()


def test_show_per_arm_rows_are_hidden_until_asked_for(tk_root, base_allow):
    dialog = _DirectiveDialog(tk_root, "show", base_allow, lambda _t: None)
    try:
        for key in ("left_arm", "right_arm"):
            caption, combo = dialog._widgets[key]
            assert not caption.winfo_manager()
            assert not combo.winfo_manager()

        dialog._per_arm_var.set(True)
        dialog._on_per_arm_change()
        for key in ("left_arm", "right_arm"):
            caption, combo = dialog._widgets[key]
            assert caption.winfo_manager()
            assert combo.winfo_manager()
    finally:
        dialog.destroy()


def test_show_character_change_refills_every_slot(tk_root, base_allow):
    """The per-character refill is keyed by slot, not by row position.

    It used to recover each combo from ``grid_slaves`` at the slot's index in
    ``_vars`` plus one — arithmetic that the checkbox row would have broken
    silently, leaving the writer with another character's poses.
    """
    chars = [
        c for c in sorted(base_allow.characters)
        if base_allow.char_faces.get(c)
    ]
    if len(chars) < 2:
        pytest.skip("need two shipped characters with faces")
    dialog = _DirectiveDialog(tk_root, "show", base_allow, lambda _t: None)
    try:
        for char in chars[:2]:
            dialog._vars["char"].set(char)
            offered = set(dialog._widgets["face"][1].cget("values")) - {""}
            assert offered == base_allow.char_faces[char], char
    finally:
        dialog.destroy()