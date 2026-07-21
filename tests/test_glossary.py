"""Tests for the in-app glossary: the pure markdown parser, plus a guarded
Tkinter smoke of the window (search filter + copy)."""

from __future__ import annotations

import tkinter as tk

import pytest

from tnh_scene_compiler.glossary import (
    GlossaryBlock,
    GlossaryDialog,
    load_glossary_sections,
    parse_glossary,
)

_SAMPLE = """\
# Scene cheatsheet

Intro line that should be dropped.

---

## Title page

Every scene starts with a title block:

```
Title: A short description
Scene Id: my_id
```

**Scene types:** cinematic, phone

---

## Dialogue

```
JEANGREY
Hello.
```

> Note: arm poses are standing only.

### Text messages

```
JEANGREY (text)
Hi by text.
```
"""


# -- parse_glossary -----------------------------------------------------------


class TestParseGlossary:
    def test_sections_and_levels(self) -> None:
        sections = parse_glossary(_SAMPLE)
        titles = [(s.title, s.level, s.parent) for s in sections]
        assert titles == [
            ("Title page", 2, ""),
            ("Dialogue", 2, ""),
            ("Text messages", 3, "Dialogue"),
        ]

    def test_content_before_first_heading_is_dropped(self) -> None:
        sections = parse_glossary(_SAMPLE)
        # The "# Scene cheatsheet" title and intro line produce no section.
        assert all(s.title != "Scene cheatsheet" for s in sections)
        assert all(
            "Intro line" not in b.text for s in sections for b in s.blocks
        )

    def test_block_kinds_and_code_content(self) -> None:
        title_page = parse_glossary(_SAMPLE)[0]
        kinds = [b.kind for b in title_page.blocks]
        assert kinds == ["prose", "code", "prose"]
        code = next(b for b in title_page.blocks if b.kind == "code")
        assert code.text == "Title: A short description\nScene Id: my_id"

    def test_note_block_strips_marker(self) -> None:
        dialogue = parse_glossary(_SAMPLE)[1]
        notes = [b for b in dialogue.blocks if b.kind == "note"]
        assert notes and notes[0].text == "Note: arm poses are standing only."

    def test_search_text_covers_title_and_body(self) -> None:
        title_page = parse_glossary(_SAMPLE)[0]
        text = title_page.search_text()
        assert "title page" in text
        assert "scene id" in text  # from a code block

    def test_empty_input(self) -> None:
        assert parse_glossary("") == []

    def test_unterminated_code_block_is_still_emitted(self) -> None:
        sections = parse_glossary("## S\n\n```\ncode line\n")
        assert sections[0].blocks == [GlossaryBlock("code", "code line")]


# -- load_glossary_sections (real bundled cheatsheet) -------------------------


def test_load_real_cheatsheet_has_expected_sections() -> None:
    sections = load_glossary_sections()
    assert sections, "the bundled scene_cheatsheet.md should load in dev"
    titles = {s.title for s in sections}
    assert {"Title page", "Dialogue", "Conditions", "Directives"} <= titles


def test_real_cheatsheet_show_examples_use_spaces_not_commas() -> None:
    # Regression: the Show/Hide example used to show a comma between attributes,
    # which does not compile (the directive grammar is space-separated).
    sections = load_glossary_sections()
    show = next(s for s in sections if s.title == "Show / Hide characters")
    code = "\n".join(b.text for b in show.blocks if b.kind == "code")
    assert "[[show" in code
    assert "mood=happy, face=smile" not in code
    assert "mood=happy face=smile" in code


# -- GlossaryDialog (guarded Tkinter) -----------------------------------------


@pytest.fixture(scope="module")
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no Tk display available: {exc}")
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


def test_dialog_lists_sections_and_search_filters(tk_root) -> None:
    dlg = GlossaryDialog(tk_root)
    try:
        total = dlg._listbox.size()
        assert total > 10

        dlg._search_var.set("choice")
        filtered = dlg._listbox.size()
        assert 0 < filtered < total
        titles = [dlg._listbox.get(i).strip() for i in range(filtered)]
        assert any("Choices" in t for t in titles)
    finally:
        dlg.destroy()


def test_dialog_copy_puts_code_on_clipboard(tk_root) -> None:
    dlg = GlossaryDialog(tk_root)
    try:
        dlg._copy("[[pause 1.5]]")
        assert tk_root.clipboard_get() == "[[pause 1.5]]"
    finally:
        dlg.destroy()


def test_dialog_opens_pre_filtered_by_search(tk_root) -> None:
    dlg = GlossaryDialog(tk_root, search="relationship conditions")
    try:
        titles = [dlg._listbox.get(i).strip() for i in range(dlg._listbox.size())]
        assert "Relationship conditions" in titles
        # The list is narrowed (not the full ~29 sections) and a section renders.
        assert len(titles) < 10
        assert dlg._content.winfo_children()
    finally:
        dlg.destroy()
