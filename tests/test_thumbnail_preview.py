"""Tests for the character-visual thumbnail preview.

Two layers, on purpose:

* the pure selection rule (``selected_visual_slots``) and the store's slot
  dispatch (``get_slot``), which need no display at all;
* a Tkinter-level regression driving the two real dialogs, because the bug
  this covers was a *rendering* one — the selection rule was never wrong,
  the dialogs simply stopped after the first image they found. Asserting on
  a helper's return value would not have caught it; only counting what the
  preview frame actually holds does.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pytest

from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.editor import (
    _CharacterInsertDialog,
    _DirectiveDialog,
    _render_thumbnail_row,
)
from tnh_scene_compiler.thumbnails import (
    VISUAL_SLOTS,
    ThumbnailStore,
    selected_visual_slots,
)


# -- Pure: which slots get previewed -----------------------------------------

def test_every_filled_slot_is_returned():
    """The regression in one line: a face must not hide the arms."""
    assert selected_visual_slots({"face": "smile1", "arms": "crossed"}) == [
        ("face", "smile1"),
        ("arms", "crossed"),
    ]


def test_slots_come_back_in_display_order():
    values = {"right_arm": "hip", "face": "angry1", "left_arm": "up", "arms": "x"}
    assert [slot for slot, _ in selected_visual_slots(values)] == list(VISUAL_SLOTS)


def test_blank_none_and_whitespace_count_as_unset():
    values = {"face": "", "arms": None, "left_arm": "   ", "right_arm": "hip"}
    assert selected_visual_slots(values) == [("right_arm", "hip")]


def test_non_visual_keys_are_ignored():
    """The directive dialog hands over its whole variable map."""
    values = {"char": "JeanGrey", "mood": "happy", "outfit": "casual",
              "look": "wet", "stage": "3", "fade": "true", "face": "smile1"}
    assert selected_visual_slots(values) == [("face", "smile1")]


def test_empty_selection():
    assert selected_visual_slots({}) == []


# -- Pure: slot -> getter dispatch -------------------------------------------

def _store_with(mapping) -> ThumbnailStore:
    """A store whose ``_load_image`` returns the relative path it was given.

    Lets the dispatch be checked without Tk: the "image" is the mapping key
    that was resolved.
    """
    store = ThumbnailStore(thumbnails_dir=None, mapping=mapping)
    store._load_image = lambda rel: rel  # type: ignore[assignment]
    return store


def test_get_slot_routes_each_kind_to_its_mapping_key():
    store = _store_with({
        "faces": {"JeanGrey": {"smile1": "f.png"}},
        "arms": {"JeanGrey": {
            "both_crossed": "b.png",
            "left_up": "l.png",
            "right_hip": "r.png",
        }},
    })
    assert store.get_slot("JeanGrey", "face", "smile1") == "f.png"
    assert store.get_slot("JeanGrey", "arms", "crossed") == "b.png"
    assert store.get_slot("JeanGrey", "left_arm", "up") == "l.png"
    assert store.get_slot("JeanGrey", "right_arm", "hip") == "r.png"


def test_get_slot_on_an_unknown_slot_returns_none():
    store = _store_with({"faces": {"JeanGrey": {"smile1": "f.png"}}})
    assert store.get_slot("JeanGrey", "outfit", "casual") is None
    assert store.get_slot("JeanGrey", "face", "nope") is None


# -- Tkinter: what the preview frame actually holds ---------------------------
#
# ``tk_root`` is the session-scoped fixture in conftest.py — see its docstring
# for why it must not be re-created per module.

class _FakeStore:
    """Serves a distinct 4x4 image per ``(slot, value)`` asked for.

    ``known`` lists the pairs that have artwork; anything else returns
    ``None``, which is how a real store reports a value with no capture.
    """

    def __init__(self, known: set[tuple[str, str]]) -> None:
        self._known = known
        self.images: dict[tuple[str, str], tk.PhotoImage] = {}

    def get_slot(self, character: str, slot: str, name: str):
        if (slot, name) not in self._known:
            return None
        key = (slot, name)
        if key not in self.images:
            self.images[key] = tk.PhotoImage(width=4, height=4)
        return self.images[key]


def _cells(frame: ttk.Frame) -> list[ttk.Frame]:
    """The per-slot cells currently rendered in a preview frame."""
    return list(frame.winfo_children())


def test_row_renders_one_cell_per_filled_slot(tk_root):
    frame = ttk.Frame(tk_root)
    store = _FakeStore({("face", "smile1"), ("arms", "crossed")})
    images = _render_thumbnail_row(
        frame, store, "JeanGrey", {"face": "smile1", "arms": "crossed"},
    )
    assert len(images) == 2
    assert len(_cells(frame)) == 2
    frame.destroy()


def test_row_skips_a_slot_with_no_artwork(tk_root):
    """A picked value with no capture is dropped, not drawn as an empty box."""
    frame = ttk.Frame(tk_root)
    store = _FakeStore({("arms", "crossed")})
    images = _render_thumbnail_row(
        frame, store, "JeanGrey", {"face": "smile1", "arms": "crossed"},
    )
    assert len(images) == 1
    assert len(_cells(frame)) == 1
    frame.destroy()


def test_row_is_rebuilt_not_appended(tk_root):
    frame = ttk.Frame(tk_root)
    store = _FakeStore({("face", "smile1"), ("arms", "crossed")})
    _render_thumbnail_row(frame, store, "JeanGrey", {"face": "smile1"})
    _render_thumbnail_row(frame, store, "JeanGrey", {"arms": "crossed"})
    assert len(_cells(frame)) == 1
    frame.destroy()


def test_row_without_a_store_or_character_renders_nothing(tk_root):
    frame = ttk.Frame(tk_root)
    assert _render_thumbnail_row(frame, None, "JeanGrey", {"face": "smile1"}) == []
    assert _cells(frame) == []
    store = _FakeStore({("face", "smile1")})
    assert _render_thumbnail_row(frame, store, "", {"face": "smile1"}) == []
    assert _cells(frame) == []
    frame.destroy()


# -- Tkinter: the real dialog -------------------------------------------------

@pytest.fixture()
def allow() -> Allowlists:
    return Allowlists(
        characters=["JeanGrey"],
        characters_upper={"JEANGREY"},
        char_faces={"JeanGrey": {"smile1"}},
        char_arms={"JeanGrey": {"crossed"}},
        char_left_arm={"JeanGrey": {"up"}},
        char_right_arm={"JeanGrey": {"hip"}},
        char_outfits={"JeanGrey": {"casual"}},
        looks={"wet"},
    )


def test_insert_dialog_previews_face_and_arms_together(tk_root, allow, monkeypatch):
    """Picking a face then arms must leave both previews on screen.

    This is the reported bug: ``_update_thumbnail`` returned after the face
    lookup succeeded, so the arms combo changed the inserted line but never
    the picture.
    """
    store = _FakeStore({("face", "smile1"), ("arms", "crossed")})
    monkeypatch.setattr(
        "tnh_scene_compiler.editor._get_thumb_store", lambda: store,
    )
    dialog = _CharacterInsertDialog(
        tk_root, "JeanGrey", allow, lambda _t: None, show_thumbnails=True,
    )
    try:
        dialog._face_var.set("smile1")
        assert len(_cells(dialog._thumb_frame)) == 1

        dialog._arms_var.set("crossed")
        assert len(_cells(dialog._thumb_frame)) == 2
        assert len(dialog._thumb_images) == 2

        # Clearing the face leaves the arms behind, not a blank frame.
        dialog._face_var.set("")
        assert len(_cells(dialog._thumb_frame)) == 1
    finally:
        dialog.destroy()


def test_show_directive_previews_all_four_slots(tk_root, allow, monkeypatch):
    """The ``[[show]]`` form has four visual slots and must preview them all.

    Same defect as the insert dialog, second site: the lookup chain stopped
    at the first image it found, so ``left_arm`` and ``right_arm`` were only
    ever visible when every slot above them was empty.
    """
    store = _FakeStore({
        ("face", "smile1"), ("arms", "crossed"),
        ("left_arm", "up"), ("right_arm", "hip"),
    })
    monkeypatch.setattr(
        "tnh_scene_compiler.editor._get_thumb_store", lambda: store,
    )
    dialog = _DirectiveDialog(
        tk_root, "show", allow, lambda _t: None, show_thumbnails=True,
    )
    try:
        dialog._vars["char"].set("JeanGrey")
        for key, value in [
            ("face", "smile1"), ("arms", "crossed"),
            ("left_arm", "up"), ("right_arm", "hip"),
        ]:
            dialog._vars[key].set(value)
        assert len(_cells(dialog._thumb_frame)) == 4

        # Non-visual fields do not add cells.
        dialog._vars["look"].set("wet")
        assert len(_cells(dialog._thumb_frame)) == 4
    finally:
        dialog.destroy()


def test_directive_without_a_show_form_has_no_preview(tk_root, allow, monkeypatch):
    """``_update_show_thumbnail`` runs for every directive; only show builds a frame."""
    monkeypatch.setattr(
        "tnh_scene_compiler.editor._get_thumb_store",
        lambda: _FakeStore(set()),
    )
    dialog = _DirectiveDialog(
        tk_root, "pause", allow, lambda _t: None, show_thumbnails=True,
    )
    try:
        assert not hasattr(dialog, "_thumb_frame")
    finally:
        dialog.destroy()
