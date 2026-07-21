"""In-app glossary window, rendered from the bundled scene cheatsheet.

A separate, non-modal reference window: a searchable section list on the
left, the selected section's prose + copyable code examples on the right.
Content comes from ``docs/scene_cheatsheet.md`` (single source of truth,
already maintained), parsed at runtime so the two never drift.

The parser (:func:`parse_glossary`) is pure and importable/testable without
Tkinter; the window (:class:`GlossaryDialog`) is the thin UI on top.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk

from .config import get_data_root

# Path of the cheatsheet relative to the data root (bundle ``_MEIPASS`` when
# frozen, repo root in dev). Bundled via the ``.spec`` ``datas``.
_CHEATSHEET_RELPATH = ("docs", "scene_cheatsheet.md")


# -- Pure-logic model + parser (no Tkinter) ----------------------------------


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
    """Load and parse the bundled cheatsheet, or ``[]`` if it is missing."""
    path = get_data_root().joinpath(*_CHEATSHEET_RELPATH)
    if not path.is_file():
        return []
    try:
        return parse_glossary(path.read_text(encoding="utf-8"))
    except OSError:
        return []


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
        # Parallel to the listbox rows: the section shown at each visible index.
        self._visible: list[GlossarySection] = []

        body = ttk.Frame(self, padding=8)
        body.pack(fill=tk.BOTH, expand=True)

        if not self._sections:
            ttk.Label(
                body,
                text=(
                    "The scene cheatsheet could not be loaded.\n"
                    "It should live at docs/scene_cheatsheet.md."
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
            elif block.kind == "note":
                ttk.Label(
                    self._content, text=block.text, foreground="#E0A030",
                    font=("Segoe UI", 9), wraplength=560, justify=tk.LEFT,
                ).pack(anchor=tk.W, padx=8, pady=(0, 8))
            else:
                ttk.Label(
                    self._content, text=block.text, foreground="#C8C8C8",
                    font=("Segoe UI", 9), wraplength=560, justify=tk.LEFT,
                ).pack(anchor=tk.W, padx=8, pady=(0, 8))

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
