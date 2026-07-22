"""In-app glossary window, the canonical scene-format reference.

A separate, non-modal reference window: a searchable section list on the
left, the selected section's prose + copyable code examples on the right.
Content comes from the markdown files under ``docs/glossary/`` (one file
per top-level section, numbered for order), read and concatenated at
runtime so the reference lives in the repo, not in the code.

The parser (:func:`parse_glossary`) is pure and importable/testable without
Tkinter; the window (:class:`GlossaryDialog`) is the thin UI on top.
"""

from __future__ import annotations

import re
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk

from .config import get_data_root

# Directory of the glossary markdown files relative to the data root (bundle
# ``_MEIPASS`` when frozen, repo root in dev). Bundled via the ``.spec`` ``datas``.
_GLOSSARY_RELDIR = ("docs", "glossary")

# Inline cross-reference links inside prose/notes: ``[label](#section-slug)``.
_LINK_RE = re.compile(r"\[([^\]]+)\]\(#([a-z0-9][a-z0-9-]*)\)")


# -- Pure-logic model + parser (no Tkinter) ----------------------------------


def slugify(title: str) -> str:
    """Turn a section title into its link anchor (lowercase, hyphenated)."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def parse_inline_links(text: str) -> list[tuple[str, str | None]]:
    """Split *text* into runs of ``(text, anchor_or_None)``.

    A run whose anchor is a string came from a ``[label](#anchor)`` link (its
    text is the label); a run whose anchor is ``None`` is plain text. Text
    with no links returns a single plain run.
    """
    runs: list[tuple[str, str | None]] = []
    pos = 0
    for match in _LINK_RE.finditer(text):
        if match.start() > pos:
            runs.append((text[pos:match.start()], None))
        runs.append((match.group(1), match.group(2)))
        pos = match.end()
    if pos < len(text):
        runs.append((text[pos:], None))
    if not runs:
        runs.append((text, None))
    return runs


@dataclass
class GlossaryBlock:
    """One rendered unit of a section: prose text, a note, or a code example."""

    kind: str  # "prose" | "note" | "code"
    text: str


@dataclass
class GlossarySection:
    """A cheatsheet heading and the blocks under it, until the next heading."""

    title: str
    level: int  # 2 for ``##``, 3 for ``###``
    parent: str = ""  # the enclosing ``##`` title, for a ``###`` subsection
    blocks: list[GlossaryBlock] = field(default_factory=list)

    def search_text(self) -> str:
        """Lowercase title + all block text, for substring search."""
        joined = " ".join(block.text for block in self.blocks)
        return f"{self.title} {self.parent} {joined}".lower()


def parse_glossary(markdown: str) -> list[GlossarySection]:
    """Parse cheatsheet markdown into a flat list of sections.

    Recognises ``##`` / ``###`` headings (each starts a section), fenced
    ``` blocks (code examples), ``>`` blockquotes (notes), ``---`` rules
    (ignored), and everything else as prose. Consecutive prose / note lines
    coalesce into one block; a blank line ends the current text block.
    Content before the first ``##`` (the file's ``#`` title and intro) is
    dropped.
    """
    sections: list[GlossarySection] = []
    current: GlossarySection | None = None
    parent_h2 = ""
    in_code = False
    code_lines: list[str] = []
    text_lines: list[str] = []
    text_kind = "prose"

    def flush_text() -> None:
        nonlocal text_lines, text_kind
        if current is not None and text_lines:
            joined = "\n".join(text_lines).strip()
            if joined:
                current.blocks.append(GlossaryBlock(text_kind, joined))
        text_lines = []
        text_kind = "prose"

    def flush_code() -> None:
        nonlocal code_lines
        if current is not None and code_lines:
            current.blocks.append(
                GlossaryBlock("code", "\n".join(code_lines).strip("\n")),
            )
        code_lines = []

    for raw in markdown.splitlines():
        stripped = raw.strip()

        if in_code:
            if stripped.startswith("```"):
                in_code = False
                flush_code()
            else:
                code_lines.append(raw)
            continue

        if stripped.startswith("```"):
            flush_text()
            in_code = True
            continue
        if stripped.startswith("### "):
            flush_text()
            current = GlossarySection(
                title=stripped[4:].strip(), level=3, parent=parent_h2,
            )
            sections.append(current)
            continue
        if stripped.startswith("## "):
            flush_text()
            parent_h2 = stripped[3:].strip()
            current = GlossarySection(title=parent_h2, level=2)
            sections.append(current)
            continue
        if stripped.startswith("# "):
            flush_text()
            continue
        if stripped == "---" or not stripped:
            flush_text()
            continue
        if stripped.startswith(">"):
            if text_kind != "note":
                flush_text()
                text_kind = "note"
            text_lines.append(stripped.lstrip(">").strip())
            continue

        if text_kind != "prose":
            flush_text()
            text_kind = "prose"
        text_lines.append(stripped)

    flush_text()
    flush_code()
    return sections


def load_glossary_sections() -> list[GlossarySection]:
    """Load and parse the bundled glossary files, or ``[]`` if none are found.

    The glossary is one markdown file per top-level section under
    ``docs/glossary/`` (numbered for order). The files are read in
    sorted-name order and concatenated, then parsed as a single document so
    the section list keeps its authored order.
    """
    directory = get_data_root().joinpath(*_GLOSSARY_RELDIR)
    if not directory.is_dir():
        return []
    try:
        parts = [
            path.read_text(encoding="utf-8")
            for path in sorted(directory.glob("*.md"))
        ]
    except OSError:
        return []
    if not parts:
        return []
    return parse_glossary("\n".join(parts))


# -- Window ------------------------------------------------------------------


class GlossaryDialog(tk.Toplevel):
    """Non-modal glossary window: searchable sections + copyable examples."""

    def __init__(
        self, master: tk.Widget, *, search: str = "", modal: bool = False,
    ) -> None:
        super().__init__(master)
        self.title("Glossary — scene cheatsheet")
        self.geometry("860x640")
        self.minsize(560, 400)
        # From the editor toolbar it's modeless (kept open beside the editor).
        # Opened from a modal dialog (the Condition Builder's "?"), it grabs so
        # it's interactive; the grab returns to that dialog when it closes.
        if modal:
            self.grab_set()

        # Optional initial search term — a caller (e.g. the Condition Builder's
        # "?" button) can open the glossary pre-filtered to the relevant topic.
        self._initial_search = search
        self._sections = load_glossary_sections()
        # slug -> section, resolving [label](#slug) cross-reference links.
        self._anchors: dict[str, GlossarySection] = {}
        for section in self._sections:
            self._anchors.setdefault(slugify(section.title), section)
        # Parallel to the listbox rows: the section shown at each visible index.
        self._visible: list[GlossarySection] = []

        body = ttk.Frame(self, padding=8)
        body.pack(fill=tk.BOTH, expand=True)

        if not self._sections:
            ttk.Label(
                body,
                text=(
                    "The glossary could not be loaded.\n"
                    "It should live under docs/glossary/*.md."
                ),
                foreground="#E05252", justify=tk.LEFT,
            ).pack(anchor=tk.W, padx=8, pady=8)
            self._bind_close()
            return

        paned = ttk.PanedWindow(body, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        self._build_sidebar(paned)
        self._build_content_pane(paned)

        # Applying the initial search fires the filter (via the var trace),
        # narrowing the list before the first section is shown.
        if self._initial_search:
            self._search_var.set(self._initial_search)
        else:
            self._refresh_list()
        if self._visible:
            self._listbox.selection_set(0)
            self._render_section(self._visible[0])

        self._bind_close()
        self._center_on(master)

    # -- Layout ------------------------------------------------------------

    def _build_sidebar(self, paned: ttk.PanedWindow) -> None:
        side = ttk.Frame(paned, padding=(0, 0, 6, 0))
        paned.add(side, weight=0)

        self._search_var = tk.StringVar()
        search = ttk.Entry(side, textvariable=self._search_var)
        search.pack(fill=tk.X, pady=(0, 4))
        search.insert(0, "")
        self._search_var.trace_add("write", lambda *_: self._refresh_list())
        # A hint the writer sees before typing.
        search.configure(foreground="#D4D4D4")

        list_frame = ttk.Frame(side)
        list_frame.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self._listbox = tk.Listbox(
            list_frame, width=30, activestyle="none",
            bg="#1E1E1E", fg="#D4D4D4",
            selectbackground="#264F78", selectforeground="#FFFFFF",
            highlightthickness=0, borderwidth=0, exportselection=False,
            yscrollcommand=scroll.set,
        )
        scroll.configure(command=self._listbox.yview)
        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

    def _build_content_pane(self, paned: ttk.PanedWindow) -> None:
        container = ttk.Frame(paned)
        paned.add(container, weight=1)

        canvas = tk.Canvas(
            container, bg="#1E1E1E", highlightthickness=0, borderwidth=0,
        )
        scroll = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        self._content = ttk.Frame(canvas)
        self._content_window = canvas.create_window(
            (0, 0), window=self._content, anchor="nw",
        )
        self._content.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(self._content_window, width=e.width),
        )
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )
        self._content_canvas = canvas

    # -- Section list ------------------------------------------------------

    def _refresh_list(self) -> None:
        query = self._search_var.get().lower().strip()
        self._listbox.delete(0, tk.END)
        self._visible = []
        for section in self._sections:
            if query and query not in section.search_text():
                continue
            self._visible.append(section)
            indent = "    " if section.level == 3 else ""
            self._listbox.insert(tk.END, f"{indent}{section.title}")

    def _on_select(self, _event: object = None) -> None:
        selection = self._listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if 0 <= index < len(self._visible):
            self._render_section(self._visible[index])

    # -- Content rendering -------------------------------------------------

    def _render_section(self, section: GlossarySection) -> None:
        for widget in self._content.winfo_children():
            widget.destroy()
        self._content_canvas.yview_moveto(0)

        heading = section.title
        if section.parent and section.level == 3:
            heading = f"{section.parent}  ›  {section.title}"
        ttk.Label(
            self._content, text=heading, font=("Segoe UI", 13, "bold"),
        ).pack(anchor=tk.W, padx=8, pady=(6, 8))

        for block in section.blocks:
            if block.kind == "code":
                self._render_code_block(block.text)
            else:
                self._render_text_block(block.text, block.kind)

    def _render_text_block(self, text: str, kind: str) -> None:
        # Prose and notes render in a read-only Text so inline
        # ``[label](#anchor)`` links can be individually clickable. Notes keep
        # the orange warning colour; plain prose the muted grey.
        colour = "#E0A030" if kind == "note" else "#C8C8C8"
        widget = tk.Text(
            self._content, wrap=tk.WORD, font=("Segoe UI", 9),
            bg="#1E1E1E", fg=colour, relief=tk.FLAT, borderwidth=0,
            highlightthickness=0, padx=0, pady=0, height=1,
            cursor="arrow", takefocus=0,
        )
        widget.tag_configure("link", foreground="#4EA1F0", underline=True)
        for run_text, anchor in parse_inline_links(text):
            if anchor is None:
                widget.insert(tk.END, run_text)
            else:
                widget.insert(tk.END, run_text, ("link", f"anchor::{anchor}"))
        widget.tag_bind("link", "<Button-1>", self._on_link_click)
        widget.tag_bind(
            "link", "<Enter>", lambda _e: widget.configure(cursor="hand2"),
        )
        widget.tag_bind(
            "link", "<Leave>", lambda _e: widget.configure(cursor="arrow"),
        )
        widget.configure(state=tk.DISABLED)
        widget.pack(fill=tk.X, padx=8, pady=(0, 8))
        self._bind_wheel(widget)
        self._fit_text_height(widget)

    def _on_link_click(self, event: tk.Event) -> str:
        widget = event.widget
        index = widget.index(f"@{event.x},{event.y}")
        for tag in widget.tag_names(index):
            if tag.startswith("anchor::"):
                self._navigate_to(tag[len("anchor::"):])
                break
        return "break"

    def _navigate_to(self, anchor: str) -> None:
        target = self._anchors.get(anchor)
        if target is None:
            return
        # Drop any active filter so the target row is guaranteed visible.
        if self._search_var.get():
            self._search_var.set("")  # fires the trace -> _refresh_list
        else:
            self._refresh_list()
        for idx, section in enumerate(self._visible):
            if section is target:
                self._listbox.selection_clear(0, tk.END)
                self._listbox.selection_set(idx)
                self._listbox.see(idx)
                break
        self._render_section(target)

    def _fit_text_height(self, widget: tk.Text) -> None:
        # Size the Text to its wrapped content: recount display lines whenever
        # the width changes (the content pane reflows on window resize).
        def fit(_event: object = None) -> None:
            try:
                counted = widget.count("1.0", "end-1c", "displaylines")
            except tk.TclError:
                counted = None
            lines = counted[0] if counted else 1
            widget.configure(height=max(1, lines))
        widget.bind("<Configure>", fit)
        widget.after_idle(fit)

    def _bind_wheel(self, widget: tk.Widget) -> None:
        # Forward the wheel to the outer canvas so hovering a Text block still
        # scrolls the page (and stop the Text from consuming the event).
        def scroll(event: tk.Event) -> str:
            self._content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        widget.bind("<MouseWheel>", scroll)

    def _render_code_block(self, code: str) -> None:
        frame = ttk.Frame(self._content)
        frame.pack(fill=tk.X, padx=8, pady=(0, 10))

        bar = ttk.Frame(frame)
        bar.pack(fill=tk.X)
        ttk.Button(
            bar, text="Copy", width=6,
            command=lambda c=code: self._copy(c),
        ).pack(side=tk.RIGHT)

        line_count = code.count("\n") + 1
        text = tk.Text(
            frame, height=min(line_count, 20), wrap=tk.NONE,
            font=("Consolas", 10), bg="#252526", fg="#D4D4D4",
            insertbackground="#D4D4D4", relief=tk.FLAT,
            padx=6, pady=4, highlightthickness=0,
        )
        text.insert("1.0", code)
        text.configure(state=tk.DISABLED)
        text.pack(fill=tk.X)
        self._bind_wheel(text)

    def _copy(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)

    # -- Window plumbing ---------------------------------------------------

    def _bind_close(self) -> None:
        self.bind("<Escape>", lambda _e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _close(self) -> None:
        # Drop the app-wide mousewheel binding this window installed.
        try:
            self.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
        self.destroy()

    def _center_on(self, master: tk.Widget) -> None:
        self.update_idletasks()
        try:
            x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
            y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass
