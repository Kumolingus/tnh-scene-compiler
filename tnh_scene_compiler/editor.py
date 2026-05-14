"""Integrated scene editor with syntax highlighting and insertion palette."""

from __future__ import annotations

import re
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from .action_builder import ActionBuilderDialog
from .allowlists import Allowlists
from .condition_builder import ConditionBuilderDialog
from .config import Config
from .errors import CompileError
from .new_scene_dialog import NewSceneDialog
from . import output as out
from .parser import parse
from .validator import validate


# ---------------------------------------------------------------------------
# Editor context
# ---------------------------------------------------------------------------

@dataclass
class EditorContext:
    """Everything the editor needs from the calling screen."""

    file_path: Path | None
    allowlists: Allowlists
    project_prefix: str
    scenes_source: Path | None
    origin: str  # "project" or "quick"
    cfg: Config | None = None


# ---------------------------------------------------------------------------
# Syntax highlighting
# ---------------------------------------------------------------------------

_HL_TAGS: dict[str, dict[str, Any]] = {
    "hl_titlekey":      {"foreground": "#569CD6", "font": ("Consolas", 10, "bold")},
    "hl_slugline":      {"foreground": "#4EC9B0", "font": ("Consolas", 10, "bold")},
    "hl_speaker":       {"foreground": "#DCDCAA"},
    "hl_directive":     {"foreground": "#C586C0"},
    "hl_comment":       {"foreground": "#6A9955"},
    "hl_parenthetical": {"foreground": "#CE9178"},
    "hl_option":        {"foreground": "#D7BA7D"},
    "hl_interpolation": {"foreground": "#9CDCFE"},
    "hl_error":         {"underline": True, "foreground": "#E05252"},
}

_RE_SLUGLINE = re.compile(r"^(INT\.|EXT\.|INT\./EXT\.|EST\.)\s+", re.IGNORECASE)
_RE_SPEAKER = re.compile(r"^[A-Z][A-Z0-9_]+\s*$")
_RE_DIRECTIVE = re.compile(r"^\s*\[\[.+\]\]\s*$")
_RE_COMMENT = re.compile(r"^\s*#")
_RE_PAREN = re.compile(r"^\s*\(.*\)\s*$")
_RE_OPTION = re.compile(r"^\s*=\s+")
_RE_TITLE_KV = re.compile(r"^([A-Za-z ]+):\s*(.*)")
_RE_INTERP = re.compile(r"\[([^\]]+)\]")

_REHIGHLIGHT_DELAY = 150


class _SyntaxHighlighter:
    """Debounced, viewport-only syntax highlighter for a tk.Text widget."""

    def __init__(self, text: tk.Text) -> None:
        self._text = text
        self._timer_id: str | None = None
        self._in_title_page = True
        self._tracking = False

        for tag, opts in _HL_TAGS.items():
            text.tag_configure(tag, **opts)

        text.bind("<KeyRelease>", self._on_key)
        text.bind("<<Paste>>", self._on_key)

    def _on_key(self, _event: Any = None) -> None:
        self.schedule()

    def schedule(self) -> None:
        if self._timer_id is not None:
            self._text.after_cancel(self._timer_id)
        self._timer_id = self._text.after(_REHIGHLIGHT_DELAY, self.rehighlight)

    def rehighlight(self) -> None:
        self._timer_id = None
        text = self._text

        first_vis = text.index("@0,0")
        last_vis = text.index(f"@0,{text.winfo_height()}")
        first_line = int(first_vis.split(".")[0])
        last_line = int(last_vis.split(".")[0])

        all_tags = [t for t in _HL_TAGS if t != "hl_error"]
        for tag in all_tags:
            text.tag_remove(tag, f"{first_line}.0", f"{last_line + 1}.0")

        self._in_title_page = True
        blank_seen = False
        for i in range(1, first_line):
            line = text.get(f"{i}.0", f"{i}.end")
            if not line.strip():
                blank_seen = True
                break
        if blank_seen:
            self._in_title_page = False

        for i in range(first_line, last_line + 1):
            line = text.get(f"{i}.0", f"{i}.end")
            self._highlight_line(i, line)

    def _highlight_line(self, lineno: int, line: str) -> None:
        text = self._text
        start = f"{lineno}.0"
        end = f"{lineno}.end"

        if not line.strip():
            self._in_title_page = False
            return

        if self._in_title_page:
            m = _RE_TITLE_KV.match(line)
            if m:
                key_end = f"{lineno}.{m.end(1)}"
                text.tag_add("hl_titlekey", start, key_end)
            return

        if _RE_COMMENT.match(line):
            text.tag_add("hl_comment", start, end)
            return

        if _RE_DIRECTIVE.match(line):
            text.tag_add("hl_directive", start, end)
            return

        if _RE_SLUGLINE.match(line):
            text.tag_add("hl_slugline", start, end)
            return

        if _RE_SPEAKER.match(line):
            text.tag_add("hl_speaker", start, end)
            return

        if _RE_PAREN.match(line):
            text.tag_add("hl_parenthetical", start, end)
            return

        if _RE_OPTION.match(line):
            text.tag_add("hl_option", start, end)
            return

        for m in _RE_INTERP.finditer(line):
            text.tag_add(
                "hl_interpolation",
                f"{lineno}.{m.start()}",
                f"{lineno}.{m.end()}",
            )

    def clear_errors(self) -> None:
        self._text.tag_remove("hl_error", "1.0", tk.END)

    def mark_error(self, line: int) -> None:
        self._text.tag_add("hl_error", f"{line}.0", f"{line}.end")


# ---------------------------------------------------------------------------
# Line numbers
# ---------------------------------------------------------------------------

class _LineNumbers(tk.Canvas):
    """Line number gutter synchronized with a tk.Text widget."""

    def __init__(self, master: tk.Widget, text: tk.Text, **kw: Any) -> None:
        super().__init__(
            master, width=45, bg="#1E1E1E", highlightthickness=0, **kw,
        )
        self._text = text

    def redraw(self) -> None:
        self.delete("all")
        i = self._text.index("@0,0")
        while True:
            dline = self._text.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            linenum = int(i.split(".")[0])
            self.create_text(
                40, y, anchor="ne", text=str(linenum),
                fill="#858585", font=("Consolas", 10),
            )
            i = self._text.index(f"{i}+1line")
            if int(i.split(".")[0]) <= linenum:
                break


# ---------------------------------------------------------------------------
# Palette sidebar
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Character insertion dialog
# ---------------------------------------------------------------------------

class _CharacterInsertDialog(tk.Toplevel):
    """Mini-form to build a character line with optional parenthetical."""

    def __init__(
        self,
        master: tk.Widget,
        char: str,
        allow: Allowlists,
        insert_cb,
    ) -> None:
        super().__init__(master)
        self.title(f"Insert — {char}")
        self.resizable(False, False)
        self.grab_set()

        self._char = char
        self._insert = insert_cb

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            body, text=char, font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))

        # Medium: spoken vs text
        row = 1
        ttk.Label(body, text="Medium:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self._medium_var = tk.StringVar(value="spoken")
        medium_frame = ttk.Frame(body)
        medium_frame.grid(row=row, column=1, sticky=tk.W, pady=2)
        ttk.Radiobutton(
            medium_frame, text="Spoken", variable=self._medium_var,
            value="spoken", command=self._on_medium_change,
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(
            medium_frame, text="Text message", variable=self._medium_var,
            value="text", command=self._on_medium_change,
        ).pack(side=tk.LEFT)

        # Mood
        row += 1
        moods = [""] + sorted(
            allow.shared_moods | allow.char_moods.get(char, set())
        )
        ttk.Label(body, text="Mood:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self._mood_var = tk.StringVar()
        self._mood_combo = ttk.Combobox(
            body, textvariable=self._mood_var, values=moods,
            state="readonly", width=20,
        )
        self._mood_combo.grid(row=row, column=1, sticky=tk.W, pady=2)

        # Face
        row += 1
        faces = [""] + sorted(allow.char_faces.get(char, set()))
        ttk.Label(body, text="Face:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self._face_var = tk.StringVar()
        self._face_combo = ttk.Combobox(
            body, textvariable=self._face_var, values=faces,
            state="readonly", width=20,
        )
        self._face_combo.grid(row=row, column=1, sticky=tk.W, pady=2)

        # Pose
        row += 1
        poses = [""] + sorted(allow.char_poses.get(char, set()))
        ttk.Label(body, text="Pose:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self._pose_var = tk.StringVar()
        self._pose_combo = ttk.Combobox(
            body, textvariable=self._pose_var, values=poses,
            state="readonly", width=20,
        )
        self._pose_combo.grid(row=row, column=1, sticky=tk.W, pady=2)

        # Arms
        row += 1
        arms = [""] + sorted(allow.char_arms.get(char, set()))
        ttk.Label(body, text="Arms:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self._arms_var = tk.StringVar()
        self._arms_combo = ttk.Combobox(
            body, textvariable=self._arms_var, values=arms,
            state="readonly", width=20,
        )
        self._arms_combo.grid(row=row, column=1, sticky=tk.W, pady=2)

        # Outfit
        row += 1
        outfits = [""] + sorted(allow.char_outfits.get(char, set()))
        ttk.Label(body, text="Outfit:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self._outfit_var = tk.StringVar()
        self._outfit_combo = ttk.Combobox(
            body, textvariable=self._outfit_var, values=outfits,
            state="readonly", width=20,
        )
        self._outfit_combo.grid(row=row, column=1, sticky=tk.W, pady=2)

        # Look
        row += 1
        looks = [""] + sorted(allow.looks)
        ttk.Label(body, text="Look:").grid(row=row, column=0, sticky=tk.W, pady=2)
        self._look_var = tk.StringVar()
        self._look_combo = ttk.Combobox(
            body, textvariable=self._look_var, values=looks,
            state="readonly", width=20,
        )
        self._look_combo.grid(row=row, column=1, sticky=tk.W, pady=2)

        # Preview
        row += 1
        ttk.Separator(body, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky=tk.EW, pady=8,
        )
        row += 1
        ttk.Label(body, text="Preview:").grid(
            row=row, column=0, sticky=tk.W, pady=2,
        )
        self._preview_var = tk.StringVar()
        ttk.Label(
            body, textvariable=self._preview_var,
            font=("Consolas", 10), foreground="#DCDCAA",
        ).grid(row=row, column=1, sticky=tk.W, pady=2)

        # Trace changes to update preview
        for var in (
            self._medium_var, self._mood_var, self._face_var,
            self._pose_var, self._arms_var, self._outfit_var,
            self._look_var,
        ):
            var.trace_add("write", self._update_preview)
        self._update_preview()

        # Buttons
        row += 1
        btn_frame = ttk.Frame(body)
        btn_frame.grid(row=row, column=0, columnspan=2, sticky=tk.E, pady=(8, 0))
        ttk.Button(btn_frame, text="Cancel", style="Danger.TButton", command=self.destroy).pack(
            side=tk.LEFT, padx=(0, 4),
        )
        ttk.Button(btn_frame, text="Insert", style="Compile.TButton", command=self._do_insert).pack(
            side=tk.LEFT,
        )

        self.bind("<Return>", lambda e: self._do_insert())
        self.bind("<Escape>", lambda e: self.destroy())

    def _on_medium_change(self) -> None:
        is_text = self._medium_var.get() == "text"
        state = "disabled" if is_text else "readonly"
        self._mood_combo.configure(state=state)
        self._face_combo.configure(state=state)
        self._pose_combo.configure(state=state)
        self._arms_combo.configure(state=state)
        self._outfit_combo.configure(state=state)
        self._look_combo.configure(state=state)
        if is_text:
            self._mood_var.set("")
            self._face_var.set("")
            self._pose_var.set("")
            self._arms_var.set("")
            self._look_var.set("")
            self._outfit_var.set("")

    def _update_preview(self, *_args: Any) -> None:
        self._preview_var.set(self._build_line())

    def _build_line(self) -> str:
        upper = self._char.upper()

        if self._medium_var.get() == "text":
            return f"{upper} (text)"

        parts: list[str] = []
        mood = self._mood_var.get()
        if mood:
            parts.append(mood)

        for slot, var in [
            ("face", self._face_var),
            ("pose", self._pose_var),
            ("arms", self._arms_var),
            ("outfit", self._outfit_var),
            ("look", self._look_var),
        ]:
            val = var.get()
            if val:
                parts.append(f"{slot}={val}")

        if parts:
            return f"{upper} ({', '.join(parts)})"
        return upper

    def _do_insert(self) -> None:
        self._insert(self._build_line() + "\n")
        self.destroy()


# ---------------------------------------------------------------------------
# Directive insertion dialog
# ---------------------------------------------------------------------------

class _DirectiveDialog(tk.Toplevel):
    """Mini-form for each directive type."""

    def __init__(
        self,
        master: tk.Widget,
        directive: str,
        allow: Allowlists,
        insert_cb,
        scenes_source: Path | None = None,
    ) -> None:
        super().__init__(master)
        self.title(f"Insert — [[{directive}]]")
        self.resizable(False, False)
        self.grab_set()

        self._insert = insert_cb
        self._allow = allow
        self._directive = directive
        self._scenes_source = scenes_source

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            body, text=f"[[{directive}]]",
            font=("Consolas", 12, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        fields = ttk.Frame(body)
        fields.pack(fill=tk.X)

        self._vars: dict[str, tk.StringVar] = {}
        builder = getattr(self, f"_build_{directive.replace(' ', '_')}", None)
        if builder:
            builder(fields, allow)

        # Preview
        ttk.Separator(body, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=8,
        )
        self._preview_var = tk.StringVar()
        ttk.Label(
            body, textvariable=self._preview_var,
            font=("Consolas", 10), foreground="#C586C0",
        ).pack(anchor=tk.W)

        for var in self._vars.values():
            var.trace_add("write", self._update_preview)
        self._update_preview()

        # Buttons
        btn_frame = ttk.Frame(body)
        btn_frame.pack(anchor=tk.E, pady=(8, 0))
        ttk.Button(btn_frame, text="Cancel", style="Danger.TButton", command=self.destroy).pack(
            side=tk.LEFT, padx=(0, 4),
        )
        ttk.Button(btn_frame, text="Insert", style="Compile.TButton", command=self._do_insert).pack(
            side=tk.LEFT,
        )
        self.bind("<Return>", lambda e: self._do_insert())
        self.bind("<Escape>", lambda e: self.destroy())

    # -- Per-directive field builders ----------------------------------------

    def _add_combo(
        self, parent: ttk.Frame, row: int, label: str, key: str,
        values: list[str], default: str = "",
    ) -> int:
        ttk.Label(parent, text=f"{label}:").grid(
            row=row, column=0, sticky=tk.W, pady=2,
        )
        var = tk.StringVar(value=default)
        self._vars[key] = var
        ttk.Combobox(
            parent, textvariable=var, values=values,
            state="readonly", width=22,
        ).grid(row=row, column=1, sticky=tk.W, padx=4, pady=2)
        return row + 1

    def _add_entry(
        self, parent: ttk.Frame, row: int, label: str, key: str,
        default: str = "",
    ) -> int:
        ttk.Label(parent, text=f"{label}:").grid(
            row=row, column=0, sticky=tk.W, pady=2,
        )
        var = tk.StringVar(value=default)
        self._vars[key] = var
        ttk.Entry(parent, textvariable=var, width=24).grid(
            row=row, column=1, sticky=tk.W, padx=4, pady=2,
        )
        return row + 1

    def _build_show(self, parent: ttk.Frame, allow: Allowlists) -> None:
        chars = sorted(
            c for c in allow.characters
            if allow.char_faces.get(c) or allow.char_moods.get(c)
        )
        row = self._add_combo(parent, 0, "Character", "char", chars)
        moods = [""] + sorted(allow.shared_moods)
        row = self._add_combo(parent, row, "Mood", "mood", moods)
        row = self._add_combo(parent, row, "Face", "face", [""])
        row = self._add_combo(parent, row, "Pose", "pose", [""])
        row = self._add_combo(parent, row, "Arms", "arms", [""])
        row = self._add_combo(parent, row, "Outfit", "outfit", [""])
        row = self._add_combo(parent, row, "Look", "look", [""] + sorted(allow.looks))

        def _on_char_change(*_a: Any) -> None:
            c = self._vars["char"].get()
            for key, getter in [
                ("face", lambda: [""] + sorted(allow.char_faces.get(c, set()))),
                ("pose", lambda: [""] + sorted(allow.char_poses.get(c, set()))),
                ("arms", lambda: [""] + sorted(allow.char_arms.get(c, set()))),
                ("outfit", lambda: [""] + sorted(allow.char_outfits.get(c, set()))),
                ("mood", lambda: [""] + sorted(
                    allow.shared_moods | allow.char_moods.get(c, set())
                )),
            ]:
                vals = getter()
                widget = parent.grid_slaves(
                    row=list(self._vars.keys()).index(key) + 1, column=1,
                )
                if widget:
                    widget[0].configure(values=vals)
                self._vars[key].set("")

        self._vars["char"].trace_add("write", _on_char_change)

    def _build_hide(self, parent: ttk.Frame, allow: Allowlists) -> None:
        chars = sorted(allow.characters)
        self._add_combo(parent, 0, "Character", "char", chars)

    def _build_approval(self, parent: ttk.Frame, allow: Allowlists) -> None:
        chars = sorted(allow.characters)
        row = self._add_combo(parent, 0, "Character", "char", chars)
        row = self._add_combo(parent, row, "Axis", "axis", ["love", "trust"])
        row = self._add_combo(
            parent, row, "Sign", "sign", ["+", "-"], default="+",
        )
        tiers = ["tiny_stat", "small_stat", "medium_stat", "large_stat", "massive_stat"]
        self._add_combo(parent, row, "Amount", "tier", tiers, default="small_stat")

    def _build_pause(self, parent: ttk.Frame, allow: Allowlists) -> None:
        self._add_entry(parent, 0, "Duration (seconds)", "duration", "1.0")

    def _build_set(self, parent: ttk.Frame, allow: Allowlists) -> None:
        row = self._add_entry(parent, 0, "Key", "key")
        self._add_entry(parent, row, "Value (optional)", "value")

    def _build_label(self, parent: ttk.Frame, allow: Allowlists) -> None:
        self._add_entry(parent, 0, "Label name", "name")

    def _build_goto(self, parent: ttk.Frame, allow: Allowlists) -> None:
        self._add_entry(parent, 0, "Target label", "name")

    def _build_call(self, parent: ttk.Frame, allow: Allowlists) -> None:
        existing_ids = self._scan_scene_ids()
        if existing_ids:
            ttk.Label(parent, text="Scene ID:").grid(
                row=0, column=0, sticky=tk.W, pady=2,
            )
            var = tk.StringVar()
            self._vars["scene_id"] = var
            ttk.Combobox(
                parent, textvariable=var, values=existing_ids, width=30,
            ).grid(row=0, column=1, sticky=tk.W, padx=4, pady=2)
        else:
            self._add_entry(parent, 0, "Scene ID", "scene_id")

    def _scan_scene_ids(self) -> list[str]:
        """Extract Scene Id values from .scene files in the project."""
        if self._scenes_source is None or not self._scenes_source.is_dir():
            return []
        ids: list[str] = []
        for scene_file in sorted(self._scenes_source.rglob("*.scene")):
            try:
                for line in scene_file.read_text(encoding="utf-8").splitlines():
                    if line.startswith("Scene Id:"):
                        sid = line.split(":", 1)[1].strip()
                        if sid:
                            ids.append(sid)
                        break
                    if not line.strip():
                        break
            except OSError:
                continue
        return ids

    def _build_phone_open(self, parent: ttk.Frame, allow: Allowlists) -> None:
        chars = [""] + sorted(allow.characters)
        self._add_combo(parent, 0, "Character", "char", chars)

    def _build_phone_close(self, parent: ttk.Frame, allow: Allowlists) -> None:
        pass

    def _build_give_trait(self, parent: ttk.Frame, allow: Allowlists) -> None:
        chars = sorted(allow.characters)
        self._add_combo(parent, 0, "Character", "char", chars)
        traits = sorted(allow.traits) if allow.traits else []
        if traits:
            self._add_combo(parent, 1, "Trait", "trait", traits)
        else:
            self._add_entry(parent, 1, "Trait", "trait")

    def _build_remove_trait(self, parent: ttk.Frame, allow: Allowlists) -> None:
        chars = sorted(allow.characters)
        self._add_combo(parent, 0, "Character", "char", chars)
        traits = sorted(allow.traits) if allow.traits else []
        if traits:
            self._add_combo(parent, 1, "Trait", "trait", traits)
        else:
            self._add_entry(parent, 1, "Trait", "trait")

    def _build_record(self, parent: ttk.Frame, allow: Allowlists) -> None:
        chars = sorted(allow.characters)
        self._add_combo(parent, 0, "Character", "char", chars)
        events = sorted(allow.history_events) if allow.history_events else []
        if events:
            self._add_combo(parent, 1, "Event", "event", events)
        else:
            self._add_entry(parent, 1, "Event", "event")

    def _build_set_personality(self, parent: ttk.Frame, allow: Allowlists) -> None:
        chars = sorted(allow.characters)
        self._add_combo(parent, 0, "Character", "char", chars)
        personalities = sorted(allow.personalities) if allow.personalities else []
        if personalities:
            self._add_combo(parent, 1, "Trait", "trait", personalities)
        else:
            self._add_entry(parent, 1, "Trait", "trait")
        self._add_entry(parent, 2, "Value", "value")

    def _build_run(self, parent: ttk.Frame, allow: Allowlists) -> None:
        ops = sorted(allow.run_operations) if allow.run_operations else []
        if ops:
            self._add_combo(parent, 0, "Operation", "op", ops)
        else:
            self._add_entry(parent, 0, "Function call", "op")

    # -- Preview + insert ---------------------------------------------------

    def _update_preview(self, *_args: Any) -> None:
        self._preview_var.set(self._build_line())

    def _build_line(self) -> str:
        d = self._directive
        v = {k: var.get() for k, var in self._vars.items()}

        if d == "show":
            char = v.get("char", "Character")
            attrs = []
            for slot in ("mood", "face", "pose", "arms", "outfit", "look"):
                val = v.get(slot, "")
                if val:
                    attrs.append(f"{slot}={val}")
            attr_str = ", ".join(attrs)
            if attr_str:
                return f"[[show {char} {attr_str}]]"
            return f"[[show {char}]]"

        if d == "hide":
            return f"[[hide {v.get('char', 'Character')}]]"

        if d == "approval":
            char = v.get("char", "Character")
            axis = v.get("axis", "love")
            sign = v.get("sign", "+")
            tier = v.get("tier", "small_stat")
            return f"[[approval {char} {axis} {sign}{tier}]]"

        if d == "pause":
            return f"[[pause {v.get('duration', '1.0')}]]"

        if d == "set":
            key = v.get("key", "key")
            val = v.get("value", "")
            if val:
                return f"[[set {key} = {val}]]"
            return f"[[set {key}]]"

        if d == "label":
            return f"[[label {v.get('name', 'name')}]]"

        if d == "goto":
            return f"[[goto {v.get('name', 'name')}]]"

        if d == "call":
            return f"[[call {v.get('scene_id', 'scene_id')}]]"

        if d == "phone open":
            char = v.get("char", "")
            if char:
                return f"[[phone open {char}]]"
            return "[[phone open]]"

        if d == "phone close":
            return "[[phone close]]"

        if d == "run":
            op = v.get("op", "function()")
            if "(" not in op:
                op += "()"
            return f"[[run {op}]]"

        if d == "give_trait":
            return f"[[give_trait {v.get('char', 'Character')} {v.get('trait', 'trait')}]]"

        if d == "remove_trait":
            return f"[[remove_trait {v.get('char', 'Character')} {v.get('trait', 'trait')}]]"

        if d == "record":
            return f"[[record {v.get('char', 'Character')} {v.get('event', 'event')}]]"

        if d == "set_personality":
            return (
                f"[[set_personality {v.get('char', 'Character')} "
                f"{v.get('trait', 'trait')} {v.get('value', '1')}]]"
            )

        return f"[[{d}]]"

    def _do_insert(self) -> None:
        self._insert(self._build_line() + "\n")
        self.destroy()


# ---------------------------------------------------------------------------
# Palette sidebar
# ---------------------------------------------------------------------------

class _PaletteSidebar(ttk.Frame):
    """Sidebar with categorized insertable elements."""

    def __init__(
        self,
        master: tk.Widget,
        allow: Allowlists,
        insert_cb,
        scenes_source: Path | None = None,
    ) -> None:
        super().__init__(master, width=340)
        self.pack_propagate(False)
        self._insert = insert_cb
        self._allow = allow
        self._scenes_source = scenes_source
        self._all_items: list[tuple[ttk.Frame, str, str]] = []

        self._search_var = tk.StringVar()
        ttk.Entry(self, textvariable=self._search_var).pack(
            fill=tk.X, padx=4, pady=(4, 2),
        )
        self._search_var.trace_add("write", self._on_filter)

        self._tab_colors: dict[str, tuple[str, str]] = {
            "Chars":   ("#2A1E3A", "#C0A0E8"),
            "Locs":    ("#1E2E3A", "#A0D0E8"),
            "Direct.": ("#3A2E1E", "#E8D0A0"),
            "FX/SFX":  ("#3A1E2E", "#E8A0C0"),
            "Struct.": ("#1E3A2E", "#A0E8C0"),
            "Visuals": ("#1E3A3A", "#A0E8E0"),
        }

        # Custom tab bar + stacked frames
        self._tab_bar = tk.Frame(self, bg="#1E1E1E")
        self._tab_bar.pack(fill=tk.X, padx=4, pady=(4, 0))
        self._tab_accent = tk.Frame(self, bg="#2D2D2D", height=3)
        self._tab_accent.pack(fill=tk.X, padx=4)
        self._tab_accent.pack_propagate(False)
        self._tab_container = ttk.Frame(self)
        self._tab_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self._tabs: dict[str, ttk.Frame] = {}
        self._tab_buttons: dict[str, tk.Button] = {}
        self._active_tab: str | None = None

        self._build_characters(allow)
        self._build_locations(allow)
        self._build_directives()
        self._build_fx_sfx(allow)
        self._build_structures()
        self._build_visuals(allow)

        if self._tabs:
            self._switch_tab(next(iter(self._tabs)))

    def _register_tab(self, name: str) -> ttk.Frame:
        """Create a tab frame and its colored button in the tab bar."""
        bg, fg = self._tab_colors.get(name, ("#2D2D2D", "#D4D4D4"))

        btn = tk.Button(
            self._tab_bar, text=name, bg=bg, fg=fg,
            activebackground=bg, activeforeground="#FFFFFF",
            relief=tk.FLAT, bd=0, padx=8, pady=4,
            font=("Segoe UI", 8, "bold"),
            command=lambda n=name: self._switch_tab(n),
        )
        btn.pack(side=tk.LEFT, padx=1)
        self._tab_buttons[name] = btn

        tab = ttk.Frame(self._tab_container)
        self._tabs[name] = tab
        return tab

    def _switch_tab(self, name: str) -> None:
        if self._active_tab == name:
            return
        for tab in self._tabs.values():
            tab.pack_forget()
        self._tabs[name].pack(fill=tk.BOTH, expand=True)

        _bg, accent_fg = self._tab_colors.get(name, ("#2D2D2D", "#D4D4D4"))
        self._tab_accent.configure(bg=accent_fg)

        for btn_name, btn in self._tab_buttons.items():
            bg, fg = self._tab_colors.get(btn_name, ("#2D2D2D", "#D4D4D4"))
            if btn_name == name:
                btn.configure(relief=tk.SUNKEN, bg=fg, fg="#000000")
            else:
                btn.configure(relief=tk.FLAT, bg=bg, fg=fg)

        self._active_tab = name

    # -- Tab builders -------------------------------------------------------

    def _make_scrollable(self, parent: ttk.Frame) -> ttk.Frame:
        canvas = tk.Canvas(
            parent, bg="#1E1E1E", highlightthickness=0, borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _bind_wheel(widget: tk.Widget) -> None:
            widget.bind(
                "<MouseWheel>",
                lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
            )
            widget.bind("<Enter>", lambda e: _bind_wheel_to_canvas(canvas))
            widget.bind("<Leave>", lambda e: _unbind_wheel_from_canvas(canvas))

        def _bind_wheel_to_canvas(c: tk.Canvas) -> None:
            c.bind_all(
                "<MouseWheel>",
                lambda e: c.yview_scroll(int(-1 * (e.delta / 120)), "units"),
            )

        def _unbind_wheel_from_canvas(c: tk.Canvas) -> None:
            c.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", lambda e: _bind_wheel_to_canvas(canvas))
        canvas.bind("<Leave>", lambda e: _unbind_wheel_from_canvas(canvas))

        return inner

    def _add_item(
        self, parent: ttk.Frame, label: str, text_to_insert: str, tab: str,
    ) -> ttk.Frame:
        btn = ttk.Button(
            parent, text=label,
            command=lambda t=text_to_insert: self._insert(t),
        )
        btn.pack(fill=tk.X, pady=1)
        self._all_items.append((btn, label.lower(), tab))
        return btn

    # -- Generic categorized tab builder ------------------------------------

    def _build_categorized_tab(
        self,
        tab_label: str,
        categories: dict[str, list[tuple[str, str | None]]],
        on_click: str = "insert",
    ) -> None:
        """Build a tab with a category dropdown and a scrollable item list.

        *categories* maps category names to lists of ``(display, insert_text)``
        tuples.  When *insert_text* is ``None``, the item triggers a
        callback named ``_on_{on_click}_click(display)`` instead of a
        direct insertion.

        Empty categories are excluded from the dropdown automatically.
        """
        live_cats = {k: v for k, v in categories.items() if v}
        if not live_cats:
            return

        tab = self._register_tab(tab_label)

        cat_names = list(live_cats.keys())

        cat_var = tk.StringVar(value=cat_names[0])
        ttk.Label(tab, text="Category:").pack(anchor=tk.W, padx=4, pady=(2, 0))
        cat_combo = ttk.Combobox(
            tab, textvariable=cat_var, values=cat_names, state="readonly",
        )
        cat_combo.pack(fill=tk.X, padx=4, pady=2)

        list_parent = tab
        list_frame: list[ttk.Frame | None] = [None]

        def _refresh(*_a: Any) -> None:
            if list_frame[0] is not None:
                list_frame[0].destroy()

            container = ttk.Frame(list_parent)
            container.pack(fill=tk.BOTH, expand=True)
            list_frame[0] = container

            inner = self._make_scrollable(container)

            items = live_cats.get(cat_var.get(), [])
            for display, insert_text in items:
                if insert_text is not None:
                    btn = ttk.Button(
                        inner, text=display,
                        command=lambda t=insert_text: self._insert(t),
                    )
                else:
                    cb = getattr(self, f"_on_{on_click}_click")
                    btn = ttk.Button(
                        inner, text=display,
                        command=lambda d=display: cb(d),
                    )
                btn.pack(fill=tk.X, pady=1)
                self._all_items.append((btn, display.lower(), tab_label))

        def _on_cat_select(*_a: Any) -> None:
            _refresh()
            self.focus_set()

        cat_combo.bind("<<ComboboxSelected>>", _on_cat_select)
        _refresh()

    # -- Characters ---------------------------------------------------------

    def _build_characters(self, allow: Allowlists) -> None:
        special = {"Player", "Narrator"}
        has_visuals = sorted(
            c for c in allow.characters
            if (allow.char_faces.get(c) or allow.char_moods.get(c))
            and c not in special
        )
        npcs = sorted(
            c for c in allow.characters
            if c not in has_visuals and c not in special
        )

        cats: dict[str, list[tuple[str, str | None]]] = {}
        cats["Player / Narrator"] = [(c, None) for c in sorted(special & set(allow.characters))]
        if has_visuals:
            cats["Featured characters"] = [(c, None) for c in has_visuals]
        if npcs:
            cats["NPCs"] = [(c, None) for c in npcs]

        self._build_categorized_tab("Chars", cats, on_click="character")

    def _on_character_click(self, char: str) -> None:
        if char == "Narrator":
            self._insert("NARRATOR\n")
            return
        if char == "Player":
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(
                label="Spoken",
                command=lambda: self._insert("PLAYER\n"),
            )
            menu.add_command(
                label="Text message",
                command=lambda: self._insert("PLAYER (text)\n"),
            )
            try:
                menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
            finally:
                menu.grab_release()
            return
        _CharacterInsertDialog(self, char, self._allow, self._insert)

    # -- Locations ----------------------------------------------------------

    def _build_locations(self, allow: Allowlists) -> None:
        _FLOOR_MAP: dict[str, list[str]] = {
            "School - Basement": [
                "loc_XavierSchool_BasementHallway",
                "loc_XavierSchool_Cerebro",
                "loc_XavierSchool_DangerRoom",
                "loc_XavierSchool_Lockers",
            ],
            "School - Ground floor": [
                "loc_XavierSchool_Entrance",
                "loc_XavierSchool_Kitchen",
                "loc_XavierSchool_RecRoom",
                "loc_XavierSchool_Classroom",
                "loc_XavierSchool_Infirmary",
                "loc_XavierSchool_Office",
            ],
            "School - Girls' floor": [
                "loc_XavierSchool_GirlsHallway",
                "loc_JeanGreyRoom", "loc_JeanGreyShower",
                "loc_LauraKinneyRoom", "loc_LauraKinneyShower",
                "loc_RogueRoom", "loc_RogueShower",
            ],
            "School - Boys' floor": [
                "loc_XavierSchool_BoysHallway",
                "loc_PlayerShower",
                "loc_KurtWagnerRoom",
                "loc_CharlesXavierRoom",
            ],
            "School - Attic": [
                "loc_XavierSchool_AtticHallway",
            ],
            "School - Outdoors": [
                "loc_XavierSchool_Grounds",
                "loc_XavierSchool_Pool",
            ],
        }

        # Build reverse map and classify every location
        _FLOOR_KEYWORDS: dict[str, list[str]] = {
            "School - Basement": ["Basement", "Cerebro", "DangerRoom", "Lockers"],
            "School - Ground floor": [
                "Entrance", "Kitchen", "RecRoom", "Classroom",
                "Infirmary", "Office",
            ],
            "School - Girls' floor": [
                "GirlsHallway", "JeanGrey", "LauraKinney",
                "Rogue", "OroroMunroe", "KittyPryde",
            ],
            "School - Boys' floor": [
                "BoysHallway", "Player", "KurtWagner",
                "CharlesXavier", "Dek", "Angelo",
            ],
            "School - Attic": ["Attic"],
            "School - Outdoors": ["Grounds", "Pool"],
        }

        def _classify(loc_id: str) -> str | None:
            for floor, keywords in _FLOOR_KEYWORDS.items():
                for kw in keywords:
                    if kw.lower() in loc_id.lower():
                        return floor
            if "XavierSchool" in loc_id:
                return "School - Other"
            return None

        def _make_item(loc: str) -> tuple[str, str | None]:
            display = re.sub(r"\[([A-Z_]+)\.[A-Za-z_.]+\]", r"\1", loc)
            return (display, f"INT. {loc}\n")

        cats: dict[str, list[tuple[str, str | None]]] = {}
        for loc, loc_id in sorted(allow.locations.items()):
            floor = _classify(loc_id)
            cat_name = floor if floor else "Outside school"
            cats.setdefault(cat_name, []).append(_make_item(loc))

        self._build_categorized_tab("Locs", cats)

    # -- Directives ---------------------------------------------------------

    def _build_directives(self) -> None:
        directive_defs = [
            ("show", "show"),
            ("hide", "hide"),
            ("approval", "approval"),
            ("pause", "pause"),
            ("set variable", "set"),
            ("mark label", "label"),
            ("goto label", "goto"),
            ("call scene", "call"),
            ("phone open", "phone open"),
            ("phone close", "phone close"),
            ("run function", "run"),
            ("give trait", "give_trait"),
            ("remove trait", "remove_trait"),
            ("record event", "record"),
            ("set personality", "set_personality"),
        ]

        tab = self._register_tab("Direct.")
        inner = self._make_scrollable(tab)

        for display, key in directive_defs:
            btn = ttk.Button(
                inner, text=display,
                command=lambda k=key: self._on_directive_click(k),
            )
            btn.pack(fill=tk.X, pady=1)
            self._all_items.append((btn, display.lower(), "direct"))

    def _on_directive_click(self, name: str) -> None:
        _DirectiveDialog(
            self, name, self._allow, self._insert, self._scenes_source,
        )

    # -- FX / SFX -----------------------------------------------------------

    def _build_fx_sfx(self, allow: Allowlists) -> None:
        char_names_lower = {c.lower() for c in allow.characters}

        char_fx: list[tuple[str, str | None]] = []
        generic_fx: list[tuple[str, str | None]] = []
        for name in sorted(allow.fx):
            prefix = name.split("_")[0].lower() if "_" in name else ""
            if prefix in char_names_lower:
                char_fx.append((name, f"[[fx {name}()]]\n"))
            else:
                generic_fx.append((name, f"[[fx {name}()]]\n"))

        sfx_items = [(n, f"[[sfx {n}]]\n") for n in sorted(allow.sfx)]

        cats: dict[str, list[tuple[str, str | None]]] = {}
        if generic_fx:
            cats["Effects (generic)"] = generic_fx
        if char_fx:
            cats["Effects (character)"] = char_fx
        if sfx_items:
            cats["Sounds (SFX)"] = sfx_items

        self._build_categorized_tab("FX/SFX", cats)

    # -- Structures ---------------------------------------------------------

    def _build_structures(self) -> None:
        structures = [
            ("if / endif", "[[if condition]]\n\n[[/if]]\n"),
            ("if / else / endif", "[[if condition]]\n\n[[else]]\n\n[[/if]]\n"),
            (
                "if / elif / else",
                "[[if condition]]\n\n[[elif condition]]\n\n[[else]]\n\n[[/if]]\n",
            ),
            (
                "choice",
                "[[choice]]\n= Option 1\n\n= Option 2\n\n[[/choice]]\n",
            ),
        ]

        tab = self._register_tab("Struct.")
        inner = self._make_scrollable(tab)
        for label, text in structures:
            self._add_item(inner, label, text, "struct")

        ttk.Separator(inner, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)
        builder_btn = ttk.Button(
            inner, text="Build condition…",
            style="Compile.TButton",
            command=self._open_condition_builder,
        )
        builder_btn.pack(fill=tk.X, pady=1)
        action_btn = ttk.Button(
            inner, text="Build action…",
            style="Compile.TButton",
            command=self._open_action_builder,
        )
        action_btn.pack(fill=tk.X, pady=1)

    def _open_condition_builder(self) -> None:
        ConditionBuilderDialog(self, self._allow, self._insert)

    def _open_action_builder(self) -> None:
        ActionBuilderDialog(self, self._allow, self._insert)

    # -- Visuals ------------------------------------------------------------

    def _build_visuals(self, allow: Allowlists) -> None:
        tab = self._register_tab("Visuals")

        chars = sorted(
            c for c in allow.characters
            if allow.char_faces.get(c) or allow.char_moods.get(c)
        )

        if not chars:
            ttk.Label(
                tab, text="No characters with visual data.",
                foreground="gray",
            ).pack(padx=4, pady=4)
            return

        # Character selector
        ttk.Label(tab, text="Character:").pack(anchor=tk.W, padx=4, pady=(4, 0))
        self._visual_char_var = tk.StringVar(value=chars[0])
        self._visual_char_combo = ttk.Combobox(
            tab, textvariable=self._visual_char_var,
            values=chars, state="readonly",
        )
        self._visual_char_combo.pack(fill=tk.X, padx=4, pady=2)
        def _on_vis_char(*_a: Any) -> None:
            self._refresh_visual_categories()
            self._refresh_visuals()
            self.focus_set()

        self._visual_char_combo.bind("<<ComboboxSelected>>", _on_vis_char)

        # Visual category selector
        ttk.Label(tab, text="Category:").pack(anchor=tk.W, padx=4, pady=(4, 0))
        self._visual_cat_var = tk.StringVar()
        self._visual_cat_combo = ttk.Combobox(
            tab, textvariable=self._visual_cat_var, state="readonly",
        )
        self._visual_cat_combo.pack(fill=tk.X, padx=4, pady=2)
        def _on_vis_cat(*_a: Any) -> None:
            self._refresh_visuals()
            self.focus_set()

        self._visual_cat_combo.bind("<<ComboboxSelected>>", _on_vis_cat)

        self._visual_inner_parent = tab
        self._visual_frame: ttk.Frame | None = None
        self._refresh_visual_categories()
        self._refresh_visuals()

    def _get_visual_categories(self, char: str) -> dict[str, set[str]]:
        allow = self._allow
        all_cats: dict[str, set[str]] = {
            "Moods": allow.shared_moods | allow.char_moods.get(char, set()),
            "Faces": allow.char_faces.get(char, set()),
            "Poses": allow.char_poses.get(char, set()),
            "Outfits": allow.char_outfits.get(char, set()),
            "Arms": allow.char_arms.get(char, set()),
            "Looks": allow.looks,
            "Stages": allow.stages,
        }
        return {k: v for k, v in all_cats.items() if v}

    def _refresh_visual_categories(self) -> None:
        char = self._visual_char_var.get()
        live = list(self._get_visual_categories(char).keys())
        self._visual_cat_combo.configure(values=live)
        if live:
            current = self._visual_cat_var.get()
            if current not in live:
                self._visual_cat_var.set(live[0])
        else:
            self._visual_cat_var.set("")

    def _on_visual_change(self, _event: Any = None) -> None:
        self._refresh_visual_categories()
        self._refresh_visuals()

    def _refresh_visuals(self) -> None:
        if self._visual_frame is not None:
            self._visual_frame.destroy()

        char = self._visual_char_var.get()
        category = self._visual_cat_var.get()

        container = ttk.Frame(self._visual_inner_parent)
        container.pack(fill=tk.BOTH, expand=True)
        self._visual_frame = container

        if not category:
            ttk.Label(
                container, text="No visual data for this character.",
                foreground="gray",
            ).pack(anchor=tk.W, padx=4, pady=4)
            return

        inner = self._make_scrollable(container)
        cats = self._get_visual_categories(char)
        values = cats.get(category, set())

        for v in sorted(values):
            slot = category.lower().rstrip("s")
            if category == "Moods":
                attr = f"mood={v}"
            elif category == "Stages":
                attr = f"stage={v}"
            else:
                attr = f"{slot}={v}"
            insert_text = f"[[show {char} {attr}]]\n"
            ttk.Button(
                inner, text=v,
                command=lambda t=insert_text: self._insert(t),
            ).pack(fill=tk.X, pady=1)

    # -- Search filter ------------------------------------------------------

    def _on_filter(self, *_args: Any) -> None:
        query = self._search_var.get().lower().strip()
        for btn, label, _tab in self._all_items:
            if not query or query in label:
                btn.pack(fill=tk.X, pady=1)
            else:
                btn.pack_forget()


# ---------------------------------------------------------------------------
# Output tag colors (reused from gui.py)
# ---------------------------------------------------------------------------

_OUTPUT_TAGS: dict[str, dict[str, Any]] = {
    "header":        {"foreground": "#FFFFFF", "font": ("Consolas", 10, "bold")},
    "success":       {"foreground": "#4EC94E"},
    "error":         {"foreground": "#E05252"},
    "warning":       {"foreground": "#E0A030"},
    "info":          {"foreground": "#888888"},
    "compile_error": {"foreground": "#E05252"},
}


# ---------------------------------------------------------------------------
# Editor screen
# ---------------------------------------------------------------------------

class EditorScreen(ttk.Frame):
    """Full-screen scene editor with text editing, highlighting, and palette."""

    def __init__(
        self,
        master: tk.Widget,
        app,
        ctx: EditorContext,
    ) -> None:
        super().__init__(master, padding=4)
        self._app = app
        self._ctx = ctx
        self._modified = False
        self._file_path = ctx.file_path

        self._build_toolbar()
        self._build_main_area()
        self._build_output()
        self._build_status_bar()

        if ctx.file_path and ctx.file_path.is_file():
            self._load_file(ctx.file_path)
        elif ctx.file_path is None:
            self.after(100, self._show_new_scene_dialog)

        self._editor.edit_reset()
        self._editor.edit_modified(False)
        self._modified = False
        self._update_title()

        self._editor.bind("<KeyRelease>", self._on_cursor_move)
        self._editor.bind("<ButtonRelease-1>", self._on_cursor_move)
        self._on_cursor_move()

    # -- Layout builders ----------------------------------------------------

    def _build_toolbar(self) -> None:
        frm = ttk.Frame(self)
        frm.pack(fill=tk.X, pady=(0, 4))

        ttk.Button(frm, text="Back", style="Danger.TButton", command=self._go_back).pack(side=tk.LEFT)

        self._title_label = ttk.Label(
            frm, text="", font=("Segoe UI", 10, "bold"),
        )
        self._title_label.pack(side=tk.LEFT, padx=8)

        ttk.Button(frm, text="Validate", style="Validate.TButton", command=self._validate).pack(
            side=tk.RIGHT, padx=(4, 0),
        )
        ttk.Button(frm, text="Save", style="Compile.TButton", command=self._save).pack(side=tk.RIGHT)

    def _build_main_area(self) -> None:
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        # Left: line numbers + editor
        editor_frame = ttk.Frame(paned)
        paned.add(editor_frame, weight=3)

        self._editor = tk.Text(
            editor_frame,
            wrap=tk.NONE,
            font=("Consolas", 10),
            bg="#1E1E1E",
            fg="#D4D4D4",
            insertbackground="#D4D4D4",
            selectbackground="#264F78",
            selectforeground="#FFFFFF",
            undo=True,
            maxundo=-1,
            padx=4,
            pady=4,
            tabs="2c",
        )

        self._line_numbers = _LineNumbers(editor_frame, self._editor)
        self._line_numbers.pack(side=tk.LEFT, fill=tk.Y)

        y_scroll = ttk.Scrollbar(editor_frame, command=self._editor.yview)
        x_scroll = ttk.Scrollbar(
            editor_frame, orient=tk.HORIZONTAL, command=self._editor.xview,
        )
        self._editor.configure(
            yscrollcommand=self._on_yscroll, xscrollcommand=x_scroll.set,
        )

        self._editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Syntax highlighter
        self._highlighter = _SyntaxHighlighter(self._editor)

        # Key bindings
        self._editor.bind("<Control-s>", lambda e: self._save())
        self._editor.bind("<Control-S>", lambda e: self._save())
        self._editor.bind(
            "<Control-Shift-v>", lambda e: self._validate(),
        )
        self._editor.bind(
            "<Control-Shift-V>", lambda e: self._validate(),
        )
        self._editor.bind("<Tab>", self._on_tab)
        self._editor.bind("<Control-slash>", self._toggle_comment)

        # Track modifications
        self._editor.bind("<<Modified>>", self._on_text_modified)

        # Right: palette
        self._palette = _PaletteSidebar(
            paned, self._ctx.allowlists, self._insert_at_cursor,
            scenes_source=self._ctx.scenes_source,
        )
        paned.add(self._palette, weight=0)

    def _build_output(self) -> None:
        frm = ttk.LabelFrame(self, text="Validation", padding=4)
        frm.pack(fill=tk.X, pady=(0, 4))

        self._output = tk.Text(
            frm, wrap=tk.WORD, state=tk.DISABLED, height=6,
            font=("Consolas", 10), bg="#1E1E1E", fg="#D4D4D4",
            insertbackground="#D4D4D4", cursor="arrow",
        )
        scrollbar = ttk.Scrollbar(frm, command=self._output.yview)
        self._output.configure(yscrollcommand=scrollbar.set)
        self._output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for tag, opts in _OUTPUT_TAGS.items():
            self._output.tag_configure(tag, **opts)

        self._output.tag_configure("clickable", underline=True)
        self._output.tag_bind("clickable", "<Button-1>", self._on_error_click)
        self._output.tag_bind(
            "clickable", "<Enter>",
            lambda e: self._output.configure(cursor="hand2"),
        )
        self._output.tag_bind(
            "clickable", "<Leave>",
            lambda e: self._output.configure(cursor="arrow"),
        )

        self._error_lines: list[int] = []

    def _build_status_bar(self) -> None:
        frm = ttk.Frame(self)
        frm.pack(fill=tk.X)

        self._pos_var = tk.StringVar(value="Ln 1, Col 1")
        ttk.Label(frm, textvariable=self._pos_var).pack(side=tk.LEFT)

        self._mod_var = tk.StringVar()
        ttk.Label(frm, textvariable=self._mod_var, foreground="gray").pack(
            side=tk.LEFT, padx=8,
        )

        path_text = str(self._file_path) if self._file_path else "New scene"
        self._path_var = tk.StringVar(value=path_text)
        ttk.Label(
            frm, textvariable=self._path_var, foreground="gray",
        ).pack(side=tk.RIGHT)

    # -- File operations ----------------------------------------------------

    def _load_file(self, path: Path) -> None:
        text = path.read_text(encoding="utf-8")
        self._editor.delete("1.0", tk.END)
        self._editor.insert("1.0", text)
        self._editor.mark_set(tk.INSERT, "1.0")
        self._file_path = path

    def _show_new_scene_dialog(self) -> None:
        NewSceneDialog(
            self, self._ctx.allowlists, self._ctx.project_prefix,
            on_create=self._apply_new_scene_text,
        )

    def _apply_new_scene_text(self, text: str) -> None:
        self._editor.delete("1.0", tk.END)
        self._editor.insert("1.0", text)
        self._editor.mark_set(tk.INSERT, tk.END)
        self._editor.edit_reset()
        self._editor.edit_modified(False)
        self._modified = False
        self._update_title()
        if hasattr(self, "_highlighter"):
            self._highlighter.schedule()

    def _save(self) -> None:
        if self._file_path is None:
            init_dir = str(self._ctx.scenes_source) if self._ctx.scenes_source else "."
            path = filedialog.asksaveasfilename(
                title="Save scene as",
                initialdir=init_dir,
                defaultextension=".scene",
                filetypes=[("Scene files", "*.scene"), ("All files", "*.*")],
            )
            if not path:
                return
            self._file_path = Path(path)
            self._path_var.set(str(self._file_path))

        text = self._editor.get("1.0", f"{tk.END}-1c")
        self._file_path.write_text(text, encoding="utf-8", newline="\n")
        self._modified = False
        self._editor.edit_modified(False)
        self._update_title()

    # -- Validation ---------------------------------------------------------

    def _validate(self) -> None:
        self._clear_output()
        self._highlighter.clear_errors()
        self._error_lines.clear()

        text = self._editor.get("1.0", f"{tk.END}-1c")
        display_path = str(self._file_path) if self._file_path else "scene"

        try:
            scene = parse(text, path=display_path)
        except CompileError as exc:
            self._append_output("compile_error", exc.format_for_user(), exc.line)
            if exc.line > 0:
                self._highlighter.mark_error(exc.line)
                self._error_lines.append(exc.line)
            return

        errors = validate(scene, self._ctx.allowlists)
        if not errors:
            self._append_output("success", "No errors found.")
            return

        for err in errors:
            self._append_output("compile_error", err.format_for_user(), err.line)
            if err.line > 0:
                self._highlighter.mark_error(err.line)
                self._error_lines.append(err.line)

    def _append_output(
        self, tag: str, text: str, line: int | None = None,
    ) -> None:
        self._output.configure(state=tk.NORMAL)
        start = self._output.index(tk.END)
        self._output.insert(tk.END, text + "\n", tag)
        if line is not None and line > 0:
            end = self._output.index(tk.END)
            self._output.tag_add("clickable", start, end)
        self._output.see(tk.END)
        self._output.configure(state=tk.DISABLED)

    def _clear_output(self) -> None:
        self._output.configure(state=tk.NORMAL)
        self._output.delete("1.0", tk.END)
        self._output.configure(state=tk.DISABLED)

    def _on_error_click(self, event: Any) -> None:
        idx = self._output.index(f"@{event.x},{event.y}")
        output_line = int(idx.split(".")[0]) - 1
        if 0 <= output_line < len(self._error_lines):
            target = self._error_lines[output_line]
            self._editor.see(f"{target}.0")
            self._editor.mark_set(tk.INSERT, f"{target}.0")
            self._editor.focus_set()

    # -- Insertion ----------------------------------------------------------

    def _insert_at_cursor(self, text: str) -> None:
        self._editor.edit_separator()
        self._editor.insert(tk.INSERT, text)
        self._editor.edit_separator()
        self._editor.see(tk.INSERT)
        self._editor.focus_set()

    # -- Key bindings -------------------------------------------------------

    def _on_tab(self, _event: Any) -> str:
        self._editor.edit_separator()
        self._editor.insert(tk.INSERT, "  ")
        self._editor.edit_separator()
        return "break"

    def _toggle_comment(self, _event: Any) -> str:
        self._editor.edit_separator()
        try:
            sel_start = self._editor.index(tk.SEL_FIRST)
            sel_end = self._editor.index(tk.SEL_LAST)
            first_line = int(sel_start.split(".")[0])
            last_line = int(sel_end.split(".")[0])
        except tk.TclError:
            pos = self._editor.index(tk.INSERT)
            first_line = last_line = int(pos.split(".")[0])

        for i in range(first_line, last_line + 1):
            line = self._editor.get(f"{i}.0", f"{i}.end")
            if line.startswith("# "):
                self._editor.delete(f"{i}.0", f"{i}.2")
            elif line.startswith("#"):
                self._editor.delete(f"{i}.0", f"{i}.1")
            else:
                self._editor.insert(f"{i}.0", "# ")

        self._editor.edit_separator()
        return "break"

    # -- Scroll / cursor tracking -------------------------------------------

    def _on_yscroll(self, *args: Any) -> None:
        self._editor.yview_moveto(args[0]) if len(args) == 2 else None
        self._line_numbers.redraw()
        self._highlighter.schedule()

    def _on_cursor_move(self, _event: Any = None) -> None:
        pos = self._editor.index(tk.INSERT)
        line, col = pos.split(".")
        self._pos_var.set(f"Ln {line}, Col {int(col) + 1}")

    def _on_text_modified(self, _event: Any = None) -> None:
        if self._editor.edit_modified():
            self._editor.edit_modified(False)
            self._modified = True
            self._update_title()
            self._line_numbers.redraw()
            self._highlighter.schedule()

    def _update_title(self) -> None:
        name = self._file_path.name if self._file_path else "New scene"
        suffix = " *" if self._modified else ""
        self._title_label.configure(text=f"{name}{suffix}")
        self._mod_var.set("Modified" if self._modified else "")

    # -- Navigation ---------------------------------------------------------

    def _go_back(self) -> None:
        if self._modified:
            answer = messagebox.askyesnocancel(
                "Unsaved changes",
                "Save changes before leaving?",
            )
            if answer is None:
                return
            if answer:
                self._save()
                if self._modified:
                    return

        self._app.restore_previous()
