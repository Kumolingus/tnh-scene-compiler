"""Tests for the in-app glossary: the pure markdown parser, plus a guarded
Tkinter smoke of the window (search filter + copy)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pytest

from tnh_scene_compiler.glossary import (
    GlossaryBlock,
    GlossaryDialog,
    load_glossary_sections,
    parse_glossary,
    parse_inline_links,
    slugify,
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


# -- load_glossary_sections (real bundled glossary files) ---------------------


def test_load_real_glossary_has_expected_sections() -> None:
    sections = load_glossary_sections()
    assert sections, "the bundled docs/glossary/*.md files should load in dev"
    titles = {s.title for s in sections}
    assert {"Title page", "Dialogue", "Conditions", "Directives"} <= titles


def test_glossary_files_load_in_declared_order() -> None:
    # The loader concatenates docs/glossary/*.md in sorted-name order (the
    # files are numbered), so the top-level sections keep their authored order.
    sections = load_glossary_sections()
    top = [s.title for s in sections if s.level == 2]
    assert top.index("Key terms") < top.index("Title page")
    assert top.index("Title page") < top.index("Conditions")
    assert top.index("Conditions") < top.index("Complete example")


def test_real_glossary_documents_calling_a_compiled_scene() -> None:
    # The integration section is the developer half of the reference: a
    # compiled scene is a label and does nothing until something calls it.
    sections = load_glossary_sections()
    titles = {s.title for s in sections}
    assert "Using compiled scenes" in titles

    calling = next(s for s in sections if s.title == "Calling a scene")
    assert calling.parent == "Using compiled scenes"
    code = "\n".join(b.text for b in calling.blocks if b.kind == "code")
    assert "renpy.call" in code

    bootstrap = next(s for s in sections if s.title == "The runtime bootstrap")
    code = "\n".join(b.text for b in bootstrap.blocks if b.kind == "code")
    assert "_scene_metadata" in code and "_runtime" in code


def test_real_glossary_cross_links_all_resolve() -> None:
    # A [label](#anchor) pointing at a renamed or deleted section is dead in
    # the window — clicking it goes nowhere — and nothing else would catch it.
    sections = load_glossary_sections()
    anchors = {slugify(s.title) for s in sections}
    broken = [
        (s.title, label, anchor)
        for s in sections
        for b in s.blocks
        if b.kind != "code"
        for label, anchor in parse_inline_links(b.text)
        if anchor and anchor not in anchors
    ]
    assert broken == [], broken


def test_real_glossary_has_no_markdown_tables() -> None:
    # parse_glossary knows prose, notes and code — a table would land in a
    # prose block as raw pipes and render as noise.
    sections = load_glossary_sections()
    tables = [
        s.title
        for s in sections
        for b in s.blocks
        if b.kind != "code" and "|---" in b.text.replace(" ", "")
    ]
    assert tables == [], tables


def test_real_glossary_show_examples_use_spaces_not_commas() -> None:
    # Regression: the Show/Hide example used to show a comma between attributes,
    # which does not compile (the directive grammar is space-separated).
    sections = load_glossary_sections()
    show = next(s for s in sections if s.title == "Show / Hide characters")
    code = "\n".join(b.text for b in show.blocks if b.kind == "code")
    assert "[[show" in code
    assert "mood=happy, face=smile" not in code
    assert "mood=happy face=smile" in code


# -- Inline cross-reference links ---------------------------------------------


class TestInlineLinks:
    def test_slugify(self) -> None:
        assert slugify("Directives") == "directives"
        assert slugify("Key terms") == "key-terms"
        assert slugify("Character-state conditions") == "character-state-conditions"
        assert slugify("Show / Hide characters") == "show-hide-characters"

    def test_plain_text_is_a_single_run(self) -> None:
        assert parse_inline_links("just text") == [("just text", None)]

    def test_extracts_label_and_anchor(self) -> None:
        assert parse_inline_links("see the [Directives](#directives) section") == [
            ("see the ", None),
            ("Directives", "directives"),
            (" section", None),
        ]

    def test_multiple_links(self) -> None:
        assert parse_inline_links("[A](#a) and [B](#b)") == [
            ("A", "a"),
            (" and ", None),
            ("B", "b"),
        ]

    def test_empty_text(self) -> None:
        assert parse_inline_links("") == [("", None)]


def test_real_glossary_links_resolve_to_existing_sections() -> None:
    # Every [label](#anchor) in the shipped glossary must point at a real
    # section slug, or the click would go nowhere.
    sections = load_glossary_sections()
    slugs = {slugify(s.title) for s in sections}
    anchors = [
        anchor
        for section in sections
        for block in section.blocks
        for _text, anchor in parse_inline_links(block.text)
        if anchor is not None
    ]
    assert anchors, "the glossary should ship at least one cross-reference link"
    dangling = [a for a in anchors if a not in slugs]
    assert not dangling, f"links point at missing sections: {dangling}"


# -- GlossaryDialog (guarded Tkinter) -----------------------------------------

# ``tk_root`` comes from conftest.py and is session-scoped on purpose. This
# module used to shadow it with a module-scoped copy — a second ``tk.Tk()``
# in the same process, which is what broke Tcl for whatever ran next. See
# the fixture's own docstring, and test_tk_fixture_discipline.py.


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


def _content_headings(dlg: GlossaryDialog) -> list[str]:
    return [
        w.cget("text")
        for w in dlg._content.winfo_children()
        if isinstance(w, ttk.Label)
    ]


def test_dialog_link_navigates_to_target_section(tk_root) -> None:
    dlg = GlossaryDialog(tk_root, search="key terms")
    try:
        # A link click resolves an anchor slug to its section and renders it,
        # even when the current search would otherwise hide the target.
        dlg._navigate_to("directives")
        assert any("Directives" in h for h in _content_headings(dlg))
        # The filter was cleared so the row is selectable again.
        assert not dlg._search_var.get()
    finally:
        dlg.destroy()


def test_dialog_text_blocks_are_tall_enough_for_their_content(tk_root) -> None:
    # Regression: the height fit used ``count -displaylines`` raw, but Tk returns
    # the number of display-line *breaks* (one less than the number of lines), so
    # the last line of every multi-line paragraph was clipped off.
    dlg = GlossaryDialog(tk_root, search="key terms")
    try:
        dlg._navigate_to("cinematic-scene")
        dlg.update()
        blocks = [w for w in dlg._content.winfo_children() if isinstance(w, tk.Text)]
        assert blocks, "the section should render at least one prose block"
        multiline = False
        for widget in blocks:
            counted = widget.count("1.0", "end-1c", "displaylines")
            display_lines = (counted[0] if counted else 0) + 1
            multiline = multiline or display_lines > 1
            assert int(widget.cget("height")) >= display_lines
        assert multiline, "the section should exercise a multi-line block"
    finally:
        dlg.destroy()


def test_dialog_navigate_ignores_unknown_anchor(tk_root) -> None:
    dlg = GlossaryDialog(tk_root)
    try:
        before = _content_headings(dlg)
        dlg._navigate_to("no-such-section")
        assert _content_headings(dlg) == before
    finally:
        dlg.destroy()
