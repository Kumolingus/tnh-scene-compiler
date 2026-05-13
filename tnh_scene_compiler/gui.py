"""Tkinter GUI for the TNH Scene Compiler.

Screen flow:
  Welcome  — quick compile, open project, or create new project.
  Quick    — compile individual .scene files against the base game only.
  Project  — full project workspace with auto-discovered scenes and allowlists.
  Init     — set up a new project (name + folder).
"""

from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk

import yaml
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import Any

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _HAS_DND = True
except ImportError:
    TkinterDnD = None  # type: ignore[assignment,misc]
    DND_FILES = None
    _HAS_DND = False

from . import __version__
from .__main__ import (
    _INIT_CONFIG_TEMPLATE,
    build_allowlists,
    compile_one,
    iter_scene_files,
    resolve_config,
)
from .allowlists import Allowlists
from .ast_nodes import Scene
from .codegen import CodegenContext, generate_events_rpy
from .config import Config, ConfigError, config_filename, find_config, get_data_root, load_config
from .errors import CompileError
from . import output as out
from .parser import parse
from .validator import validate


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_POLL_MS = 50
_WINDOW_TITLE = "TNH Scene Compiler"
_MIN_WIDTH = 1100
_MIN_HEIGHT = 700

_TAG_COLORS: dict[str, dict[str, Any]] = {
    "header":        {"foreground": "#FFFFFF", "font": ("Consolas", 10, "bold")},
    "success":       {"foreground": "#4EC94E"},
    "error":         {"foreground": "#E05252"},
    "warning":       {"foreground": "#E0A030"},
    "info":          {"foreground": "#888888"},
    "compile_error": {"foreground": "#E05252"},
}

_MAX_RECENT = 10


# ---------------------------------------------------------------------------
# Recent projects persistence
# ---------------------------------------------------------------------------

def _recent_file() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home()))
    return base / "tnh-scene-compiler" / "recent_projects.json"


def _load_recent() -> list[dict[str, str]]:
    path = _recent_file()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [e for e in data if isinstance(e, dict) and "path" in e]
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_recent(entries: list[dict[str, str]]) -> None:
    path = _recent_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(entries[:_MAX_RECENT], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _add_recent(project_path: str, project_prefix: str) -> None:
    entries = _load_recent()
    normalized = str(Path(project_path).resolve())
    entries = [e for e in entries if str(Path(e["path"]).resolve()) != normalized]
    entries.insert(0, {"path": normalized, "project_prefix": project_prefix})
    _save_recent(entries)


def _remove_recent(project_path: str) -> None:
    entries = _load_recent()
    normalized = str(Path(project_path).resolve())
    entries = [e for e in entries if str(Path(e["path"]).resolve()) != normalized]
    _save_recent(entries)


# ---------------------------------------------------------------------------
# Shared workspace base (output pane + threading)
# ---------------------------------------------------------------------------

class _WorkspaceBase(ttk.Frame):
    """Base class for screens that run compiler tasks in a worker thread.

    Queue message protocol:
      ``(level, text)``            — append to the output pane.
      ``("_file", iid, status)``   — update per-file status in a treeview.
      ``None``                     — worker finished.
    """

    def __init__(self, master: tk.Widget, app: CompilerApp) -> None:
        super().__init__(master, padding=8)
        self._app = app
        self._queue: queue.Queue[tuple[str, ...] | None] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._action_buttons: list[ttk.Button] = []

    def _build_output_pane(self) -> None:
        frm = ttk.LabelFrame(self, text="Output", padding=4)
        frm.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        self._output = tk.Text(
            frm, wrap=tk.WORD, state=tk.DISABLED, height=10,
            font=("Consolas", 10), bg="#1E1E1E", fg="#D4D4D4",
            insertbackground="#D4D4D4",
        )
        scrollbar = ttk.Scrollbar(frm, command=self._output.yview)
        self._output.configure(yscrollcommand=scrollbar.set)

        self._output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for tag, opts in _TAG_COLORS.items():
            self._output.tag_configure(tag, **opts)

    def _build_status_bar(self) -> None:
        frm = ttk.Frame(self)
        frm.pack(fill=tk.X)
        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(frm, textvariable=self._status_var).pack(side=tk.RIGHT)

    # -- Output helpers -----------------------------------------------------

    def _append(self, level: str, text: str) -> None:
        self._output.configure(state=tk.NORMAL)
        self._output.insert(tk.END, text + "\n", level)
        self._output.see(tk.END)
        self._output.configure(state=tk.DISABLED)

    def _clear_output(self) -> None:
        self._output.configure(state=tk.NORMAL)
        self._output.delete("1.0", tk.END)
        self._output.configure(state=tk.DISABLED)

    def _output_callback(self, level: str, text: str) -> None:
        self._queue.put((level, text))

    def _poll_queue(self) -> None:
        while True:
            try:
                msg = self._queue.get_nowait()
            except queue.Empty:
                break
            if msg is None:
                self._status_var.set("Ready")
                for btn in self._action_buttons:
                    btn.configure(state=tk.NORMAL)
                self._worker = None
                break
            if len(msg) == 3 and msg[0] == "_file":
                _, iid, status = msg
                self._on_file_status(iid, status)
            else:
                level, text = msg
                self._append(level, text)

        self.after(_POLL_MS, self._poll_queue)

    def _on_file_status(self, iid: str, status: str) -> None:
        """Override in subclasses that have a per-file status treeview."""

    # -- Thread management --------------------------------------------------

    def _start_worker(self, target: Any) -> None:
        if self._worker is not None and self._worker.is_alive():
            self._append("warning", "A task is already running.")
            return

        self._clear_output()
        self._status_var.set("Running…")
        for btn in self._action_buttons:
            btn.configure(state=tk.DISABLED)
        out.set_callback(self._output_callback)

        self._worker = threading.Thread(target=target, daemon=True)
        self._worker.start()

    def _finish_worker(self) -> None:
        out.set_callback(None)
        self._queue.put(None)

    def _signal_file_status(self, iid: str, status: str) -> None:
        """Call from a worker thread to update a file's visual status."""
        self._queue.put(("_file", iid, status))

    # -- Shared compile/validate logic --------------------------------------

    def _do_compile_scenes(
        self,
        sources: list[Path],
        allow: Allowlists,
        ctx: CodegenContext,
        repo_root: Path,
        output_dir: Path,
    ) -> None:
        if not sources:
            out.warning("No .scene files found.")
            return

        out.header(f"Compiling {len(sources)} scene(s)…")

        total = 0
        written = 0
        had_errors = False
        compiled_scenes: list[Scene] = []

        for source in sources:
            total += 1
            scene, rpy, errors = compile_one(
                source, allow, ctx, repo_root=repo_root,
            )
            if errors:
                had_errors = True
                for err in errors:
                    out.compile_error_detail(err.format_for_user())
                continue

            assert scene is not None
            target_dir = output_dir / scene.title_page.character
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / (source.stem + ".rpy")
            target_path.write_text(rpy, encoding="utf-8", newline="\n")
            written += 1
            compiled_scenes.append(scene)
            out.success(target_path.name)

        if not had_errors:
            output_dir.mkdir(parents=True, exist_ok=True)
            events_path = output_dir / "_events.rpy"
            events_path.write_text(
                generate_events_rpy(compiled_scenes, ctx),
                encoding="utf-8",
                newline="\n",
            )
            cinematic_count = sum(
                1 for s in compiled_scenes
                if s.title_page.scene_type == "cinematic"
            )
            out.info(
                f"Events registry: {cinematic_count} cinematic "
                f"entries -> {events_path.name}"
            )

        out.summary(written, total, had_errors)

    def _do_validate_scenes(
        self,
        sources: list[Path],
        allow: Allowlists,
        repo_root: Path,
    ) -> None:
        if not sources:
            out.warning("No .scene files found.")
            return

        out.header(f"Validating {len(sources)} scene(s)…")

        total = 0
        valid = 0
        had_errors = False

        for source in sources:
            total += 1
            try:
                display_path = (
                    source.resolve()
                    .relative_to(repo_root.resolve())
                    .as_posix()
                )
            except ValueError:
                display_path = source.as_posix()

            text = source.read_text(encoding="utf-8")
            try:
                scene = parse(text, path=display_path)
            except CompileError as exc:
                had_errors = True
                out.compile_error_detail(exc.format_for_user())
                continue

            errors = validate(scene, allow)
            if errors:
                had_errors = True
                for err in errors:
                    out.compile_error_detail(err.format_for_user())
            else:
                valid += 1
                out.success(source.name)

        out.summary(valid, total, had_errors)


# ---------------------------------------------------------------------------
# Welcome screen
# ---------------------------------------------------------------------------

class WelcomeScreen(ttk.Frame):

    def __init__(self, master: tk.Widget, app: CompilerApp) -> None:
        super().__init__(master, padding=16)
        self._app = app

        # -- Title ----------------------------------------------------------
        ttk.Label(
            self, text=_WINDOW_TITLE,
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(24, 4))

        ttk.Label(
            self, text=f"v{__version__}",
            font=("Segoe UI", 10),
        ).pack(pady=(0, 8))

        ttk.Label(
            self,
            text="Compile your .scene scripts into Ren'Py code.",
            font=("Segoe UI", 10),
        ).pack(pady=(0, 24))

        # -- Mode selection -------------------------------------------------
        mode_frame = ttk.Frame(self)
        mode_frame.pack(pady=(0, 8))

        # New scene
        scene_frame = ttk.LabelFrame(
            mode_frame, text="New scene", padding=8,
        )
        scene_frame.pack(side=tk.LEFT, padx=8, fill=tk.Y)
        ttk.Label(
            scene_frame,
            text="Create a new scene\nfile and open it in\nthe editor.",
            justify=tk.CENTER,
        ).pack(pady=(0, 8))
        ttk.Button(
            scene_frame, text="New scene",
            command=self._new_scene,
        ).pack()

        # Quick compile
        quick_frame = ttk.LabelFrame(
            mode_frame, text="Quick compile", padding=8,
        )
        quick_frame.pack(side=tk.LEFT, padx=8, fill=tk.Y)
        ttk.Label(
            quick_frame,
            text="Compile scenes using\nthe base game only.\nNo project setup needed.",
            justify=tk.CENTER,
        ).pack(pady=(0, 8))
        ttk.Button(
            quick_frame, text="Quick compile",
            command=self._quick_compile,
        ).pack()

        # Open project
        open_frame = ttk.LabelFrame(
            mode_frame, text="Open project", padding=8,
        )
        open_frame.pack(side=tk.LEFT, padx=8, fill=tk.Y)
        ttk.Label(
            open_frame,
            text="Open an existing project\nwith custom allowlists\nand scene structure.",
            justify=tk.CENTER,
        ).pack(pady=(0, 8))
        ttk.Button(
            open_frame, text="Open project",
            command=self._open_project,
        ).pack()

        # Create project
        create_frame = ttk.LabelFrame(
            mode_frame, text="New project", padding=8,
        )
        create_frame.pack(side=tk.LEFT, padx=8, fill=tk.Y)
        ttk.Label(
            create_frame,
            text="Set up a new project\nfrom scratch with its\nown allowlists.",
            justify=tk.CENTER,
        ).pack(pady=(0, 8))
        ttk.Button(
            create_frame, text="Create project",
            command=self._create_project,
        ).pack()

        # -- Recent projects ------------------------------------------------
        self._recent_entries = _load_recent()

        if self._recent_entries:
            ttk.Separator(self, orient=tk.HORIZONTAL).pack(
                fill=tk.X, pady=(12, 12),
            )

            ttk.Label(
                self, text="Recent projects",
                font=("Segoe UI", 11, "bold"),
            ).pack(anchor=tk.W)

            list_frame = ttk.Frame(self)
            list_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

            self._recent_list = tk.Listbox(
                list_frame, font=("Consolas", 10),
                bg="#1E1E1E", fg="#D4D4D4",
                selectbackground="#264F78", selectforeground="#FFFFFF",
                activestyle="none",
            )
            scrollbar = ttk.Scrollbar(
                list_frame, command=self._recent_list.yview,
            )
            self._recent_list.configure(yscrollcommand=scrollbar.set)

            self._recent_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            for entry in self._recent_entries:
                label = f"{entry.get('project_prefix', '?')}  —  {entry['path']}"
                self._recent_list.insert(tk.END, label)

            self._recent_list.bind("<Double-1>", self._open_recent)

            recent_btn_frame = ttk.Frame(self)
            recent_btn_frame.pack(fill=tk.X, pady=(4, 0))

            ttk.Button(
                recent_btn_frame, text="Open selected",
                command=self._open_recent,
            ).pack(side=tk.LEFT)

            ttk.Button(
                recent_btn_frame, text="Remove from list", style="Danger.TButton",
                command=self._remove_recent,
            ).pack(side=tk.LEFT, padx=4)

    # -- Actions ------------------------------------------------------------

    def _quick_compile(self) -> None:
        self._app.show_quick()

    def _new_scene(self) -> None:
        from .editor import EditorContext
        from .allowlists import Allowlists
        from .config import get_data_root

        base_dir = get_data_root() / "allowlists_base"
        if base_dir.is_dir():
            allow = Allowlists.load_layered([base_dir])
        else:
            allow = Allowlists()

        ctx = EditorContext(
            file_path=None,
            allowlists=allow,
            project_prefix="my_project",
            scenes_source=None,
            origin="welcome",
        )
        self._app.show_editor(ctx)

    def _open_project(self) -> None:
        path = filedialog.askopenfilename(
            title="Select project config file",
            filetypes=[
                ("TNH config", "tnh_scene_compiler.*.yaml"),
                ("YAML files", "*.yaml *.yml"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self._try_open_config(Path(path))

    def _open_recent(self, _event: Any = None) -> None:
        sel = self._recent_list.curselection()
        if not sel:
            return
        entry = self._recent_entries[sel[0]]
        config_path = Path(entry["path"])
        if config_path.is_file():
            self._try_open_config(config_path)
        else:
            found = find_config(config_path)
            if found:
                self._try_open_config(found)
            else:
                messagebox.showerror(
                    "Project not found",
                    f"Config file no longer exists:\n{entry['path']}",
                )

    def _remove_recent(self) -> None:
        sel = self._recent_list.curselection()
        if not sel:
            return
        entry = self._recent_entries[sel[0]]
        _remove_recent(entry["path"])
        self._recent_entries.pop(sel[0])
        self._recent_list.delete(sel[0])

    def _create_project(self) -> None:
        self._app.show_init()

    def _try_open_config(self, config_path: Path) -> None:
        try:
            cfg = load_config(config_path)
        except ConfigError as exc:
            messagebox.showerror("Configuration error", str(exc))
            return

        _add_recent(str(config_path.resolve()), cfg.project_prefix)
        self._app.show_project(cfg)


# ---------------------------------------------------------------------------
# Init screen
# ---------------------------------------------------------------------------

class InitScreen(ttk.Frame):

    def __init__(self, master: tk.Widget, app: CompilerApp) -> None:
        super().__init__(master, padding=16)
        self._app = app

        ttk.Label(
            self, text="Create a new project",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor=tk.W, pady=(0, 16))

        ttk.Label(
            self,
            text=(
                "Choose a short identifier for your project (lowercase, "
                "no spaces — e.g. my_romance_project)."
            ),
            wraplength=600,
        ).pack(anchor=tk.W, pady=(0, 8))

        row_prefix = ttk.Frame(self)
        row_prefix.pack(fill=tk.X, pady=4)
        ttk.Label(row_prefix, text="Project name:", width=12).pack(side=tk.LEFT)
        self._prefix_var = tk.StringVar()
        ttk.Entry(row_prefix, textvariable=self._prefix_var, width=30).pack(
            side=tk.LEFT, padx=4,
        )

        ttk.Label(
            self,
            text="Select the folder where your project files will live.",
            wraplength=600,
        ).pack(anchor=tk.W, pady=(16, 8))

        row_dir = ttk.Frame(self)
        row_dir.pack(fill=tk.X, pady=4)
        ttk.Label(row_dir, text="Project folder:", width=12).pack(side=tk.LEFT)
        self._dir_var = tk.StringVar()
        ttk.Entry(row_dir, textvariable=self._dir_var, width=50).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4,
        )
        ttk.Button(row_dir, text="Browse…", command=self._browse).pack(
            side=tk.LEFT,
        )

        self._error_var = tk.StringVar()
        ttk.Label(
            self, textvariable=self._error_var, foreground="red",
        ).pack(anchor=tk.W, pady=(8, 0))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(anchor=tk.W, pady=(20, 0))

        ttk.Button(
            btn_frame, text="Back", style="Danger.TButton", command=self._back,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            btn_frame, text="Create", command=self._create,
        ).pack(side=tk.LEFT)

    def _browse(self) -> None:
        path = filedialog.askdirectory(title="Select project folder")
        if path:
            self._dir_var.set(path)

    def _back(self) -> None:
        self._app.show_welcome()

    def _create(self) -> None:
        project_prefix = self._prefix_var.get().strip()
        if not project_prefix:
            self._error_var.set("Project name is required.")
            return

        folder = self._dir_var.get().strip()
        if not folder:
            self._error_var.set("Project folder is required.")
            return

        output_dir = Path(folder).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        config_path = output_dir / config_filename(project_prefix)
        if config_path.exists():
            self._error_var.set(
                "A project already exists in this folder. Use 'Open' instead."
            )
            return

        self._error_var.set("")

        config_path.write_text(
            _INIT_CONFIG_TEMPLATE.format(project_prefix=project_prefix),
            encoding="utf-8",
            newline="\n",
        )

        templates_dir = get_data_root() / "templates"
        if templates_dir.is_dir():
            for tmpl_file in sorted(templates_dir.glob("*.tmpl")):
                content = tmpl_file.read_text(encoding="utf-8")
                content = content.replace("{{project_prefix}}", project_prefix)
                out_name = tmpl_file.stem
                out_path = output_dir / out_name
                if not out_path.exists():
                    out_path.write_text(
                        content, encoding="utf-8", newline="\n",
                    )

        scenes_dir = output_dir / "scenes_source"
        scenes_dir.mkdir(exist_ok=True)

        try:
            cfg = load_config(config_path)
        except ConfigError as exc:
            self._error_var.set(str(exc))
            return

        _add_recent(str(config_path.resolve()), cfg.project_prefix)
        self._app.show_project(cfg)


# ---------------------------------------------------------------------------
# Quick compile screen (base game only, no project needed)
# ---------------------------------------------------------------------------

class QuickScreen(_WorkspaceBase):
    """Compile/validate individual .scene files against the base game."""

    # Per-file status symbols and their treeview tag names.
    _S_PENDING  = "—"   # —
    _S_RUNNING  = "▶"   # ▶
    _S_OK       = "✓"   # ✓
    _S_ERROR    = "✗"   # ✗

    def __init__(self, master: tk.Widget, app: CompilerApp) -> None:
        super().__init__(master, app)
        self._file_paths: dict[str, Path] = {}  # treeview iid -> Path

        self._build_header()
        self._build_settings()
        self._build_file_list()
        self._build_actions()
        self._build_output_pane()
        self._build_status_bar()
        self._poll_queue()

    # -- Layout -------------------------------------------------------------

    def _build_header(self) -> None:
        frm = ttk.Frame(self)
        frm.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(
            frm, text="Quick compile",
            font=("Segoe UI", 11, "bold"),
        ).pack(side=tk.LEFT)

        ttk.Label(
            frm, text="  (base game allowlists only)",
            foreground="gray",
        ).pack(side=tk.LEFT)

        ttk.Button(
            frm, text="Back to home", style="Danger.TButton", command=lambda: self._app.show_welcome(),
        ).pack(side=tk.RIGHT)

    def _build_settings(self) -> None:
        frm = ttk.Frame(self)
        frm.pack(fill=tk.X, pady=(0, 4))

        # Mod name
        row_name = ttk.Frame(frm)
        row_name.pack(fill=tk.X, pady=2)
        ttk.Label(row_name, text="Project name:", width=14).pack(side=tk.LEFT)
        self._prefix_var = tk.StringVar(value="my_project")
        ttk.Entry(row_name, textvariable=self._prefix_var, width=25).pack(
            side=tk.LEFT, padx=4,
        )
        ttk.Label(
            row_name, text="(identifier used in generated Ren'Py code)",
            foreground="gray",
        ).pack(side=tk.LEFT, padx=4)

        # Output directory
        row_out = ttk.Frame(frm)
        row_out.pack(fill=tk.X, pady=2)
        ttk.Label(row_out, text="Output folder:", width=14).pack(side=tk.LEFT)
        self._out_dir_var = tk.StringVar()
        ttk.Entry(row_out, textvariable=self._out_dir_var, width=50).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4,
        )
        ttk.Button(
            row_out, text="Browse…", command=self._browse_out_dir,
        ).pack(side=tk.LEFT)

    def _build_file_list(self) -> None:
        frm = ttk.LabelFrame(self, text="Scene files", padding=4)
        frm.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        # Treeview with status + filename columns
        tree_frame = ttk.Frame(frm)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self._tree = ttk.Treeview(
            tree_frame,
            columns=("status", "file"),
            show="headings",
            selectmode="extended",
        )
        self._tree.heading("status", text="")
        self._tree.heading("file", text="File", anchor=tk.W)
        self._tree.column("status", width=36, minwidth=36, stretch=False, anchor=tk.CENTER)
        self._tree.column("file", stretch=True, anchor=tk.W)

        self._tree.tag_configure("pending",  foreground="#888888")
        self._tree.tag_configure("running",  foreground="#4EAEE0")
        self._tree.tag_configure("ok",       foreground="#4EC94E")
        self._tree.tag_configure("error",    foreground="#E05252")

        scrollbar = ttk.Scrollbar(tree_frame, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Register drag-and-drop if available
        if _HAS_DND:
            self._tree.drop_target_register(DND_FILES)
            self._tree.dnd_bind("<<Drop>>", self._on_drop)

        self._tree.bind("<Double-1>", self._on_double_click_edit)

        # Buttons + hint
        btn_frame = ttk.Frame(frm)
        btn_frame.pack(fill=tk.X, pady=(4, 0))

        ttk.Button(
            btn_frame, text="Add files…", command=self._browse_files,
        ).pack(side=tk.LEFT)
        ttk.Button(
            btn_frame, text="Remove selected", style="Danger.TButton", command=self._remove_selected,
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(
            btn_frame, text="Clear all", style="Danger.TButton", command=self._clear_files,
        ).pack(side=tk.LEFT, padx=4)

        ttk.Button(
            btn_frame, text="Edit scene", style="Edit.TButton", command=self._edit_selected,
        ).pack(side=tk.LEFT, padx=4)

        hint = "Drop .scene files here or use Add files…"
        if not _HAS_DND:
            hint = "Use Add files… to load .scene files."
        self._file_count_var = tk.StringVar(value=hint)
        ttk.Label(
            btn_frame, textvariable=self._file_count_var, foreground="gray",
        ).pack(side=tk.RIGHT)

    def _build_actions(self) -> None:
        frm = ttk.Frame(self)
        frm.pack(fill=tk.X, pady=(0, 4))

        compile_btn = ttk.Button(
            frm, text="Compile", style="Compile.TButton", command=self._run_compile,
        )
        compile_btn.pack(side=tk.LEFT, padx=(0, 4))
        self._action_buttons.append(compile_btn)

        validate_btn = ttk.Button(
            frm, text="Validate", style="Validate.TButton", command=self._run_validate,
        )
        validate_btn.pack(side=tk.LEFT)
        self._action_buttons.append(validate_btn)

    # -- File management ----------------------------------------------------

    def _add_files(self, paths: list[str | Path]) -> None:
        """Add scene files to the list (deduplicates)."""
        existing = set(self._file_paths.values())
        for p in paths:
            path = Path(p).resolve()
            if path.suffix != ".scene":
                continue
            if path in existing:
                continue
            iid = self._tree.insert(
                "", tk.END,
                values=(self._S_PENDING, path.name),
                tags=("pending",),
            )
            self._file_paths[iid] = path
            existing.add(path)

        self._update_count()

        if not self._out_dir_var.get().strip() and self._file_paths:
            first = next(iter(self._file_paths.values()))
            self._out_dir_var.set(str(first.parent / "compiled"))

    def _remove_selected(self) -> None:
        for iid in self._tree.selection():
            self._file_paths.pop(iid, None)
            self._tree.delete(iid)
        self._update_count()

    def _clear_files(self) -> None:
        self._tree.delete(*self._tree.get_children())
        self._file_paths.clear()
        self._update_count()

    def _update_count(self) -> None:
        n = len(self._file_paths)
        if n == 0:
            hint = "Drop .scene files here or use Add files…" if _HAS_DND \
                else "Use Add files… to load .scene files."
            self._file_count_var.set(hint)
        else:
            self._file_count_var.set(
                f"{n} file{'s' if n != 1 else ''}"
            )

    def _reset_all_statuses(self) -> None:
        for iid in self._tree.get_children():
            self._tree.item(iid, values=(self._S_PENDING, self._tree.set(iid, "file")))
            self._tree.item(iid, tags=("pending",))

    # -- Editor integration -------------------------------------------------

    def _edit_selected(self) -> None:
        sel = self._tree.selection()
        if len(sel) != 1:
            messagebox.showinfo(
                "Edit scene",
                "Select a single scene to edit.",
            )
            return
        path = self._file_paths.get(sel[0])
        if path:
            self._open_editor(path)

    def _on_double_click_edit(self, _event: Any = None) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        path = self._file_paths.get(sel[0])
        if path:
            self._open_editor(path)

    def _open_editor(self, file_path: Path) -> None:
        from .editor import EditorContext

        allow = self._load_base_allowlists()
        if allow is None:
            return

        ctx = EditorContext(
            file_path=file_path,
            allowlists=allow,
            project_prefix=self._prefix_var.get().strip() or "my_project",
            scenes_source=None,
            origin="quick",
        )
        self._app.show_editor(ctx)

    # -- File dialogs / DnD -------------------------------------------------

    def _browse_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select .scene files",
            filetypes=[("Scene files", "*.scene"), ("All files", "*.*")],
        )
        if paths:
            self._add_files(paths)

    def _browse_out_dir(self) -> None:
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self._out_dir_var.set(path)

    def _on_drop(self, event: Any) -> None:
        """Handle files dropped onto the treeview."""
        raw = event.data
        # tkinterdnd2 wraps paths with spaces in braces: {C:/path with spaces}
        paths: list[str] = []
        if "{" in raw:
            import re
            paths = re.findall(r"\{([^}]+)\}", raw)
            rest = re.sub(r"\{[^}]+\}", "", raw).strip()
            if rest:
                paths.extend(rest.split())
        else:
            paths = raw.split()
        self._add_files(paths)

    # -- Per-file status hook -----------------------------------------------

    def _on_file_status(self, iid: str, status: str) -> None:
        symbols = {
            "pending": self._S_PENDING,
            "running": self._S_RUNNING,
            "ok":      self._S_OK,
            "error":   self._S_ERROR,
        }
        sym = symbols.get(status, self._S_PENDING)
        if self._tree.exists(iid):
            self._tree.set(iid, "status", sym)
            self._tree.item(iid, tags=(status,))

    # -- Helpers ------------------------------------------------------------

    def _get_file_items(self) -> list[tuple[str, Path]]:
        """Return ``(iid, path)`` pairs for all files in the list."""
        return [(iid, self._file_paths[iid]) for iid in self._tree.get_children()]

    def _load_base_allowlists(self) -> Allowlists | None:
        base_dir = get_data_root() / "allowlists_base"
        if not base_dir.is_dir():
            out.error(
                "Base allowlists not found. The installation may be incomplete."
            )
            return None
        return Allowlists.load_layered([base_dir])

    # -- Compile / Validate -------------------------------------------------

    def _run_compile(self) -> None:
        self._reset_all_statuses()
        self._start_worker(self._do_compile)

    def _do_compile(self) -> None:
        try:
            items = self._get_file_items()
            if not items:
                out.error("No scene files loaded.")
                return

            allow = self._load_base_allowlists()
            if allow is None:
                return

            prefix = self._prefix_var.get().strip() or "my_project"
            ctx = CodegenContext(project_prefix=prefix)

            out_dir_str = self._out_dir_var.get().strip()
            if not out_dir_str:
                out.error("Output folder is required.")
                return
            output_dir = Path(out_dir_str).resolve()
            repo_root = items[0][1].resolve().parent

            out.header(f"Compiling {len(items)} scene(s)…")

            total = 0
            written = 0
            had_errors = False
            compiled_scenes: list[Scene] = []

            for iid, source in items:
                total += 1
                self._signal_file_status(iid, "running")

                scene, rpy, errors = compile_one(
                    source, allow, ctx, repo_root=repo_root,
                )
                if errors:
                    had_errors = True
                    self._signal_file_status(iid, "error")
                    for err in errors:
                        out.compile_error_detail(err.format_for_user())
                    continue

                assert scene is not None
                target_dir = output_dir / scene.title_page.character
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = target_dir / (source.stem + ".rpy")
                target_path.write_text(rpy, encoding="utf-8", newline="\n")
                written += 1
                compiled_scenes.append(scene)
                self._signal_file_status(iid, "ok")
                out.success(target_path.name)

            if not had_errors:
                output_dir.mkdir(parents=True, exist_ok=True)
                events_path = output_dir / "_events.rpy"
                events_path.write_text(
                    generate_events_rpy(compiled_scenes, ctx),
                    encoding="utf-8",
                    newline="\n",
                )
                cinematic_count = sum(
                    1 for s in compiled_scenes
                    if s.title_page.scene_type == "cinematic"
                )
                out.info(
                    f"Events registry: {cinematic_count} cinematic "
                    f"entries -> {events_path.name}"
                )

            out.summary(written, total, had_errors)

        except Exception as exc:
            out.error(f"Unexpected error: {exc}")
        finally:
            self._finish_worker()

    def _run_validate(self) -> None:
        self._reset_all_statuses()
        self._start_worker(self._do_validate)

    def _do_validate(self) -> None:
        try:
            items = self._get_file_items()
            if not items:
                out.error("No scene files loaded.")
                return

            allow = self._load_base_allowlists()
            if allow is None:
                return

            repo_root = items[0][1].resolve().parent
            out.header(f"Validating {len(items)} scene(s)…")

            total = 0
            valid = 0
            had_errors = False

            for iid, source in items:
                total += 1
                self._signal_file_status(iid, "running")

                try:
                    display_path = source.name
                    text = source.read_text(encoding="utf-8")
                    scene = parse(text, path=display_path)
                except CompileError as exc:
                    had_errors = True
                    self._signal_file_status(iid, "error")
                    out.compile_error_detail(exc.format_for_user())
                    continue

                errors = validate(scene, allow)
                if errors:
                    had_errors = True
                    self._signal_file_status(iid, "error")
                    for err in errors:
                        out.compile_error_detail(err.format_for_user())
                else:
                    valid += 1
                    self._signal_file_status(iid, "ok")
                    out.success(source.name)

            out.summary(valid, total, had_errors)

        except Exception as exc:
            out.error(f"Unexpected error: {exc}")
        finally:
            self._finish_worker()


# ---------------------------------------------------------------------------
# Project settings dialog
# ---------------------------------------------------------------------------

class SettingsDialog(tk.Toplevel):
    """Modal dialog to edit the project config YAML."""

    def __init__(self, master: tk.Widget, cfg: Config, on_save) -> None:
        super().__init__(master)
        self.title(f"Settings — {cfg.project_prefix}")
        self.resizable(False, False)
        self.grab_set()

        self._cfg = cfg
        self._on_save = on_save
        self._config_path = self._find_config_path()

        body = ttk.Frame(self, padding=16)
        body.pack(fill=tk.BOTH, expand=True)

        # -- Fields ---------------------------------------------------------
        row = 0

        ttk.Label(body, text="Project name:").grid(
            row=row, column=0, sticky=tk.W, pady=2,
        )
        self._prefix_var = tk.StringVar(value=cfg.project_prefix)
        ttk.Entry(body, textvariable=self._prefix_var, width=30).grid(
            row=row, column=1, sticky=tk.EW, padx=4, pady=2,
        )
        row += 1

        self._scenes_var = tk.StringVar(value=str(cfg.scenes_source))
        row = self._add_path_row(body, row, "Scenes source:", self._scenes_var)

        self._allowlists_var = tk.StringVar(value=str(cfg.project_allowlists))
        row = self._add_path_row(body, row, "Project allowlists:", self._allowlists_var)

        self._output_var = tk.StringVar(value=str(cfg.output))
        row = self._add_path_row(body, row, "Output:", self._output_var)

        self._base_allow_var = tk.BooleanVar(value=cfg.include_base_allowlists)
        ttk.Checkbutton(
            body, text="Include base game allowlists",
            variable=self._base_allow_var,
        ).grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=4)
        row += 1

        # -- Refresh section (optional) ------------------------------------
        ttk.Separator(body, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=3, sticky=tk.EW, pady=8,
        )
        row += 1

        ttk.Label(
            body, text="Allowlist refresh (optional)",
            font=("Segoe UI", 9, "bold"),
        ).grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(0, 4))
        row += 1

        base_game_val = str(cfg.refresh.base_game) if cfg.refresh else ""
        self._base_game_var = tk.StringVar(value=base_game_val)
        row = self._add_path_row(body, row, "Base game path:", self._base_game_var)

        project_root_val = str(cfg.refresh.project_root) if cfg.refresh else ""
        self._project_root_var = tk.StringVar(value=project_root_val)
        row = self._add_path_row(body, row, "Project root:", self._project_root_var)

        body.columnconfigure(1, weight=1)

        # -- Error + buttons ------------------------------------------------
        self._error_var = tk.StringVar()
        ttk.Label(
            body, textvariable=self._error_var, foreground="red",
        ).grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(4, 0))
        row += 1

        btn_frame = ttk.Frame(body)
        btn_frame.grid(row=row, column=0, columnspan=3, sticky=tk.E, pady=(8, 0))

        ttk.Button(btn_frame, text="Cancel", style="Danger.TButton", command=self.destroy).pack(
            side=tk.LEFT, padx=(0, 4),
        )
        ttk.Button(btn_frame, text="Save", style="Compile.TButton", command=self._save).pack(
            side=tk.LEFT,
        )

    def _add_path_row(
        self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar,
    ) -> int:
        ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky=tk.W, pady=2,
        )
        ttk.Entry(parent, textvariable=var, width=50).grid(
            row=row, column=1, sticky=tk.EW, padx=4, pady=2,
        )
        ttk.Button(
            parent, text="…",
            command=lambda: self._browse_dir(var),
        ).grid(row=row, column=2, pady=2)
        return row + 1

    def _browse_dir(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(
            title="Select directory",
            initialdir=var.get() or str(self._cfg.config_dir),
        )
        if path:
            var.set(path)

    def _find_config_path(self) -> Path:
        """Locate the config file on disk."""
        candidate = self._cfg.config_dir / config_filename(self._cfg.project_prefix)
        if candidate.is_file():
            return candidate
        from .config import _CONFIG_LEGACY
        legacy = self._cfg.config_dir / _CONFIG_LEGACY
        if legacy.is_file():
            return legacy
        return candidate

    def _save(self) -> None:
        prefix = self._prefix_var.get().strip()
        if not prefix:
            self._error_var.set("Project name is required.")
            return

        config_dir = self._cfg.config_dir

        def _rel(val: str) -> str:
            """Convert absolute paths to relative (to config_dir) for the YAML."""
            try:
                return str(Path(val).relative_to(config_dir))
            except ValueError:
                return val

        data: dict[str, Any] = {
            "project_prefix": prefix,
            "scenes_source": _rel(self._scenes_var.get().strip()),
            "project_allowlists": _rel(self._allowlists_var.get().strip()),
            "output": _rel(self._output_var.get().strip()),
            "include_base_allowlists": self._base_allow_var.get(),
        }

        base_game = self._base_game_var.get().strip()
        project_root = self._project_root_var.get().strip()
        if base_game or project_root:
            data["refresh"] = {}
            if base_game:
                data["refresh"]["base_game"] = _rel(base_game)
            if project_root:
                data["refresh"]["project_root"] = _rel(project_root)

        new_path = config_dir / config_filename(prefix)
        old_path = self._config_path

        try:
            new_path.write_text(
                yaml.dump(data, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
                newline="\n",
            )
        except OSError as exc:
            self._error_var.set(f"Write failed: {exc}")
            return

        if old_path != new_path and old_path.is_file():
            old_path.unlink()

        try:
            new_cfg = load_config(new_path)
        except ConfigError as exc:
            self._error_var.set(str(exc))
            return

        _add_recent(str(new_path.resolve()), new_cfg.project_prefix)
        self.destroy()
        self._on_save(new_cfg)


# ---------------------------------------------------------------------------
# Project workspace screen
# ---------------------------------------------------------------------------

class ProjectScreen(_WorkspaceBase):

    _S_PENDING = "—"
    _S_RUNNING = "▶"
    _S_OK      = "✓"
    _S_ERROR   = "✗"

    def __init__(
        self, master: tk.Widget, app: CompilerApp, cfg: Config,
    ) -> None:
        super().__init__(master, app)
        self._cfg = cfg
        self._file_paths: dict[str, Path] = {}

        self._build_header()
        self._build_scene_list()
        self._build_actions()
        self._build_output_pane()
        self._build_status_bar()

        self._refresh_scenes()
        self._poll_queue()

    def _build_header(self) -> None:
        frm = ttk.Frame(self)
        frm.pack(fill=tk.X, pady=(0, 8))

        self._header_title = ttk.Label(
            frm,
            text=f"Project: {self._cfg.project_prefix}",
            font=("Segoe UI", 11, "bold"),
        )
        self._header_title.pack(side=tk.LEFT)

        self._header_path = ttk.Label(
            frm,
            text=f"  ({self._cfg.config_dir})",
            foreground="gray",
        )
        self._header_path.pack(side=tk.LEFT, padx=(4, 0))

        ttk.Button(
            frm, text="Back to home", style="Danger.TButton",
            command=lambda: self._app.show_welcome(),
        ).pack(side=tk.RIGHT)

        ttk.Button(
            frm, text="Settings",
            command=self._open_settings,
        ).pack(side=tk.RIGHT, padx=(0, 4))

    def _build_scene_list(self) -> None:
        frm = ttk.LabelFrame(self, text="Scene files", padding=4)
        frm.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        tree_frame = ttk.Frame(frm)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self._tree = ttk.Treeview(
            tree_frame,
            columns=("status", "file"),
            show="headings",
            selectmode="extended",
        )
        self._tree.heading("status", text="")
        self._tree.heading("file", text="File", anchor=tk.W)
        self._tree.column(
            "status", width=36, minwidth=36, stretch=False, anchor=tk.CENTER,
        )
        self._tree.column("file", stretch=True, anchor=tk.W)

        self._tree.tag_configure("pending", foreground="#888888")
        self._tree.tag_configure("running", foreground="#4EAEE0")
        self._tree.tag_configure("ok",      foreground="#4EC94E")
        self._tree.tag_configure("error",   foreground="#E05252")

        scrollbar = ttk.Scrollbar(tree_frame, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        btn_frame = ttk.Frame(frm)
        btn_frame.pack(fill=tk.X, pady=(4, 0))

        ttk.Button(
            btn_frame, text="Refresh", command=self._refresh_scenes,
        ).pack(side=tk.LEFT)

        ttk.Button(
            btn_frame, text="Select all", command=self._select_all,
        ).pack(side=tk.LEFT, padx=4)

        ttk.Button(
            btn_frame, text="New Scene", style="New.TButton", command=self._new_scene,
        ).pack(side=tk.LEFT, padx=4)

        ttk.Button(
            btn_frame, text="Edit scene", style="Edit.TButton", command=self._edit_selected,
        ).pack(side=tk.LEFT, padx=4)

        self._scene_count_var = tk.StringVar()
        ttk.Label(
            btn_frame, textvariable=self._scene_count_var, foreground="gray",
        ).pack(side=tk.RIGHT)

        self._tree.bind("<Double-1>", self._on_double_click)

    def _build_actions(self) -> None:
        frm = ttk.Frame(self)
        frm.pack(fill=tk.X, pady=(0, 4))

        compile_btn = ttk.Button(
            frm, text="Compile", style="Compile.TButton", command=self._run_compile,
        )
        compile_btn.pack(side=tk.LEFT, padx=(0, 4))
        self._action_buttons.append(compile_btn)

        validate_btn = ttk.Button(
            frm, text="Validate", style="Validate.TButton", command=self._run_validate,
        )
        validate_btn.pack(side=tk.LEFT, padx=(0, 8))
        self._action_buttons.append(validate_btn)

        ttk.Label(
            frm,
            text="Select scenes above, or leave empty to process all.",
            foreground="gray",
        ).pack(side=tk.LEFT)

    # -- Editor integration -------------------------------------------------

    def _on_double_click(self, _event: Any = None) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        path = self._file_paths.get(sel[0])
        if path:
            self._open_editor(path)

    def _edit_selected(self) -> None:
        sel = self._tree.selection()
        if len(sel) != 1:
            messagebox.showinfo(
                "Edit scene",
                "Select a single scene to edit.",
            )
            return
        path = self._file_paths.get(sel[0])
        if path:
            self._open_editor(path)

    def _new_scene(self) -> None:
        self._open_editor(None)

    def _open_editor(self, file_path: Path | None) -> None:
        from .editor import EditorContext

        try:
            allow = build_allowlists(self._cfg)
        except ConfigError as exc:
            messagebox.showerror("Configuration error", str(exc))
            return

        ctx = EditorContext(
            file_path=file_path,
            allowlists=allow,
            project_prefix=self._cfg.project_prefix,
            scenes_source=self._cfg.scenes_source,
            origin="project",
            cfg=self._cfg,
        )
        self._app.show_editor(ctx)

    # -- Settings -----------------------------------------------------------

    def _open_settings(self) -> None:
        SettingsDialog(self, self._cfg, self._on_settings_saved)

    def _on_settings_saved(self, new_cfg: Config) -> None:
        self._cfg = new_cfg
        self._refresh_header()
        self._refresh_scenes()

    def _refresh_header(self) -> None:
        self._header_title.configure(text=f"Project: {self._cfg.project_prefix}")
        self._header_path.configure(text=f"  ({self._cfg.config_dir})")

    # -- Scene discovery ----------------------------------------------------

    def _refresh_scenes(self) -> None:
        self._tree.delete(*self._tree.get_children())
        self._file_paths.clear()

        if not self._cfg.scenes_source.is_dir():
            self._scene_count_var.set("scenes_source/ not found")
            return

        for path in iter_scene_files(self._cfg.scenes_source):
            try:
                display = path.relative_to(self._cfg.config_dir).as_posix()
            except ValueError:
                display = path.name
            iid = self._tree.insert(
                "", tk.END,
                values=(self._S_PENDING, display),
                tags=("pending",),
            )
            self._file_paths[iid] = path

        count = len(self._file_paths)
        self._scene_count_var.set(
            f"{count} scene{'s' if count != 1 else ''} found"
        )

    def _select_all(self) -> None:
        self._tree.selection_set(self._tree.get_children())

    def _get_selected_items(self) -> list[tuple[str, Path]]:
        """Return ``(iid, path)`` for selected files, or all if none selected."""
        sel = self._tree.selection()
        if sel:
            return [(iid, self._file_paths[iid]) for iid in sel]
        return [(iid, self._file_paths[iid]) for iid in self._tree.get_children()]

    def _reset_all_statuses(self) -> None:
        for iid in self._tree.get_children():
            self._tree.item(
                iid, values=(self._S_PENDING, self._tree.set(iid, "file")),
            )
            self._tree.item(iid, tags=("pending",))

    # -- Per-file status hook -----------------------------------------------

    def _on_file_status(self, iid: str, status: str) -> None:
        symbols = {
            "pending": self._S_PENDING,
            "running": self._S_RUNNING,
            "ok":      self._S_OK,
            "error":   self._S_ERROR,
        }
        sym = symbols.get(status, self._S_PENDING)
        if self._tree.exists(iid):
            self._tree.set(iid, "status", sym)
            self._tree.item(iid, tags=(status,))

    # -- Compile / Validate -------------------------------------------------

    def _run_compile(self) -> None:
        self._reset_all_statuses()
        self._start_worker(self._do_compile)

    def _do_compile(self) -> None:
        try:
            cfg = self._cfg
            allow = build_allowlists(cfg)
            ctx = CodegenContext(project_prefix=cfg.project_prefix)
            items = self._get_selected_items()

            if not items:
                out.warning("No .scene files found.")
                return

            out.header(f"Compiling {len(items)} scene(s)…")

            total = 0
            written = 0
            had_errors = False
            compiled_scenes: list[Scene] = []

            for iid, source in items:
                total += 1
                self._signal_file_status(iid, "running")

                scene, rpy, errors = compile_one(
                    source, allow, ctx, repo_root=cfg.config_dir,
                )
                if errors:
                    had_errors = True
                    self._signal_file_status(iid, "error")
                    for err in errors:
                        out.compile_error_detail(err.format_for_user())
                    continue

                assert scene is not None
                target_dir = cfg.output / scene.title_page.character
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = target_dir / (source.stem + ".rpy")
                target_path.write_text(rpy, encoding="utf-8", newline="\n")
                written += 1
                compiled_scenes.append(scene)
                self._signal_file_status(iid, "ok")
                out.success(target_path.name)

            if not had_errors:
                cfg.output.mkdir(parents=True, exist_ok=True)
                events_path = cfg.output / "_events.rpy"
                events_path.write_text(
                    generate_events_rpy(compiled_scenes, ctx),
                    encoding="utf-8",
                    newline="\n",
                )
                cinematic_count = sum(
                    1 for s in compiled_scenes
                    if s.title_page.scene_type == "cinematic"
                )
                out.info(
                    f"Events registry: {cinematic_count} cinematic "
                    f"entries -> {events_path.name}"
                )

            out.summary(written, total, had_errors)

        except ConfigError as exc:
            out.error(str(exc))
        except Exception as exc:
            out.error(f"Unexpected error: {exc}")
        finally:
            self._finish_worker()

    def _run_validate(self) -> None:
        self._reset_all_statuses()
        self._start_worker(self._do_validate)

    def _do_validate(self) -> None:
        try:
            cfg = self._cfg
            allow = build_allowlists(cfg)
            items = self._get_selected_items()

            if not items:
                out.warning("No .scene files found.")
                return

            out.header(f"Validating {len(items)} scene(s)…")

            total = 0
            valid = 0
            had_errors = False

            for iid, source in items:
                total += 1
                self._signal_file_status(iid, "running")

                try:
                    display_path = (
                        source.resolve()
                        .relative_to(cfg.config_dir.resolve())
                        .as_posix()
                    )
                except ValueError:
                    display_path = source.as_posix()

                text = source.read_text(encoding="utf-8")
                try:
                    scene = parse(text, path=display_path)
                except CompileError as exc:
                    had_errors = True
                    self._signal_file_status(iid, "error")
                    out.compile_error_detail(exc.format_for_user())
                    continue

                errors = validate(scene, allow)
                if errors:
                    had_errors = True
                    self._signal_file_status(iid, "error")
                    for err in errors:
                        out.compile_error_detail(err.format_for_user())
                else:
                    valid += 1
                    self._signal_file_status(iid, "ok")
                    out.success(source.name)

            out.summary(valid, total, had_errors)

        except ConfigError as exc:
            out.error(str(exc))
        except Exception as exc:
            out.error(f"Unexpected error: {exc}")
        finally:
            self._finish_worker()


# ---------------------------------------------------------------------------
# Application controller
# ---------------------------------------------------------------------------

class CompilerApp(ttk.Frame):

    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master)
        self.pack(fill=tk.BOTH, expand=True)
        self._current: ttk.Frame | None = None
        self._stashed: ttk.Frame | None = None
        self.show_welcome()

    def _switch_to(self, screen: ttk.Frame) -> None:
        if self._stashed is not None:
            self._stashed.destroy()
            self._stashed = None
        if self._current is not None:
            self._current.destroy()
        self._current = screen
        screen.pack(fill=tk.BOTH, expand=True)

    def show_welcome(self) -> None:
        self._switch_to(WelcomeScreen(self, self))

    def show_init(self) -> None:
        self._switch_to(InitScreen(self, self))

    def show_quick(self) -> None:
        self._switch_to(QuickScreen(self, self))

    def show_project(self, cfg: Config) -> None:
        self._switch_to(ProjectScreen(self, self, cfg))

    def show_editor(self, ctx) -> None:
        from .editor import EditorScreen
        if self._current is not None:
            self._current.pack_forget()
            self._stashed = self._current
        editor = EditorScreen(self, self, ctx)
        self._current = editor
        editor.pack(fill=tk.BOTH, expand=True)

    def restore_previous(self) -> None:
        if self._current is not None:
            self._current.destroy()
        if self._stashed is not None:
            self._current = self._stashed
            self._stashed = None
            self._current.pack(fill=tk.BOTH, expand=True)
        else:
            self.show_welcome()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _apply_dark_theme(root: tk.Tk) -> None:
    root.configure(bg="#1E1E1E")

    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background="#1E1E1E", foreground="#D4D4D4",
                     fieldbackground="#141414", borderwidth=1,
                     troughcolor="#141414", arrowcolor="#D4D4D4")
    style.configure("TFrame", background="#1E1E1E")
    style.configure("TLabel", background="#1E1E1E", foreground="#D4D4D4")
    style.configure("TButton", background="#2D2D2D", foreground="#D4D4D4")
    style.map("TButton",
              background=[("active", "#3C3C3C"), ("pressed", "#505050")])
    style.configure("TEntry", fieldbackground="#141414", foreground="#D4D4D4")
    style.configure("TCombobox", fieldbackground="#141414", foreground="#D4D4D4",
                     selectbackground="#264F78", selectforeground="#FFFFFF",
                     background="#141414")
    style.map("TCombobox",
              fieldbackground=[("readonly", "#141414")],
              foreground=[("readonly", "#D4D4D4")],
              selectbackground=[("readonly", "#264F78")],
              selectforeground=[("readonly", "#FFFFFF")])
    style.configure("TCheckbutton", background="#1E1E1E", foreground="#D4D4D4")
    style.configure("TRadiobutton", background="#1E1E1E", foreground="#D4D4D4")
    style.configure("TLabelframe", background="#1E1E1E", foreground="#D4D4D4")
    style.configure("TLabelframe.Label", background="#1E1E1E", foreground="#D4D4D4")
    style.configure("TNotebook", background="#1E1E1E")
    style.configure("TNotebook.Tab", background="#2D2D2D", foreground="#D4D4D4",
                     padding=[12, 5])
    style.map("TNotebook.Tab",
              background=[("selected", "#141414")],
              foreground=[("selected", "#FFFFFF")])
    style.configure("TSeparator", background="#3C3C3C")
    style.configure("TPanedwindow", background="#1E1E1E")
    style.configure("Treeview", background="#141414", foreground="#D4D4D4",
                     fieldbackground="#141414", borderwidth=0)
    style.configure("Treeview.Heading", background="#2D2D2D",
                     foreground="#D4D4D4")
    style.map("Treeview",
              background=[("selected", "#264F78")],
              foreground=[("selected", "#FFFFFF")])
    style.configure("Vertical.TScrollbar", background="#2D2D2D",
                     troughcolor="#141414", arrowcolor="#D4D4D4")
    style.configure("Horizontal.TScrollbar", background="#2D2D2D",
                     troughcolor="#141414", arrowcolor="#D4D4D4")

    # Colored button styles
    style.configure("Danger.TButton", background="#5C1E1E", foreground="#E8A0A0")
    style.map("Danger.TButton",
              background=[("active", "#7A2A2A"), ("pressed", "#8B3232")])

    style.configure("Compile.TButton", background="#1E3A1E", foreground="#A0E8A0")
    style.map("Compile.TButton",
              background=[("active", "#2A5A2A"), ("pressed", "#327032")])

    style.configure("Validate.TButton", background="#1E2E5C", foreground="#A0C0E8")
    style.map("Validate.TButton",
              background=[("active", "#2A3E7A"), ("pressed", "#324A8B")])

    style.configure("Edit.TButton", background="#3A2E1E", foreground="#E8D0A0")
    style.map("Edit.TButton",
              background=[("active", "#5A4A2A"), ("pressed", "#705832")])

    style.configure("New.TButton", background="#1E3A3A", foreground="#A0E8E0")
    style.map("New.TButton",
              background=[("active", "#2A5A5A"), ("pressed", "#327070")])

    root.option_add("*TCombobox*Listbox.background", "#1E1E1E")
    root.option_add("*TCombobox*Listbox.foreground", "#D4D4D4")
    root.option_add("*TCombobox*Listbox.selectBackground", "#264F78")
    root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")


def main() -> None:
    if _HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    root.title(f"{_WINDOW_TITLE} v{__version__}")
    root.minsize(_MIN_WIDTH, _MIN_HEIGHT)
    root.geometry(f"{_MIN_WIDTH}x{_MIN_HEIGHT}")

    _apply_dark_theme(root)
    CompilerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
