"""New Scene dialog — guided form for creating a scene with setup and examples.

The pure-logic helper (``build_scene_text``) is importable and testable
without Tkinter.
"""

from __future__ import annotations

import re
import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from .allowlists import Allowlists

# -- Constants ---------------------------------------------------------------

SCENE_TYPES: list[str] = ["cinematic", "phone", "texting", "hub_option"]

TRIGGERS: list[str] = [
    "manual", "sleeping", "waking", "traveling", "getting_ready_for_bed",
]


EXAMPLES: list[tuple[str, str]] = [
    ("Empty scene", "empty"),
    ("Simple dialogue", "dialogue"),
    ("Dialogue with choices", "choices"),
    ("Conditional scene", "conditional"),
]


# -- Pure-logic helper -------------------------------------------------------

def _slugify(title: str) -> str:
    """Convert a human title to a snake_case Scene Id fragment."""
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug


def build_scene_text(
    *,
    title: str = "",
    scene_id: str = "",
    character: str = "",
    scene_type: str = "cinematic",
    trigger: str = "manual",
    location: str = "",
    description: str = "",
    example: str = "empty",
    featured: bool = True,
) -> str:
    """Return the full scene text from form parameters.

    Parameters
    ----------
    example
        One of ``"empty"``, ``"dialogue"``, ``"choices"``, ``"conditional"``.
    featured
        Whether the character has visuals (faces/moods). When ``False``,
        ``[[show]]`` is not inserted in the body examples.
    """
    lines: list[str] = []

    # -- Title page --
    lines.append(f"Title: {title}")
    lines.append(f"Scene Id: {scene_id}")
    lines.append(f"Character: {character}")
    lines.append(f"Scene Type: {scene_type}")

    if scene_type == "cinematic":
        lines.append(f"Trigger: {trigger}")

    if description:
        lines.append(f"Description: {description}")
    if location:
        lines.append(f"Location: {location}")

    lines.append("")

    # -- Body --
    speaker = character.upper() if character else "CHARACTER"
    char = character or "Character"
    loc = location if location else "LOCATION"
    is_phone = scene_type in ("phone", "texting")

    def _opening() -> list[str]:
        if is_phone:
            return [f"[[phone open {char}]]", ""]
        opening = [f"INT. {loc}", ""]
        if featured:
            opening.extend([f"[[show {char}]]", ""])
        return opening

    def _closing() -> list[str]:
        if is_phone:
            return ["[[phone close]]", ""]
        return []

    if example == "empty":
        pass

    elif example == "dialogue":
        lines.extend(_opening())
        if is_phone:
            lines.extend([
                f"{speaker}",
                "Hello!",
                "",
                "PLAYER",
                "Hi there.",
                "",
            ])
        else:
            lines.extend([
                f"{speaker} (happy)",
                "Hello!",
                "",
                "PLAYER",
                "Hi there.",
                "",
            ])
        lines.extend(_closing())

    elif example == "choices":
        lines.extend(_opening())
        lines.extend([
            f"{speaker}",
            "What do you want to do?",
            "",
            "[[choice]]",
            "= Option A",
            "",
            f"{speaker}",
            "Good choice!",
            "",
            "= Option B",
            "",
            f"{speaker}",
            "Interesting...",
            "",
            "[[/choice]]",
            "",
        ])
        lines.extend(_closing())

    elif example == "conditional":
        lines.extend(_opening())
        lines.extend([
            f"[[if {char}.love >= 500]]",
            "",
            f"{speaker}",
            "I'm glad we're close.",
            "",
            "[[else]]",
            "",
            f"{speaker}",
            "We should talk more.",
            "",
            "[[/if]]",
            "",
        ])
        lines.extend(_closing())

    return "\n".join(lines)


# -- Dialog ------------------------------------------------------------------

class NewSceneDialog(tk.Toplevel):
    """Modal dialog that guides writers through creating a new scene."""

    def __init__(
        self,
        master: tk.Widget,
        allow: Allowlists,
        project_prefix: str,
        on_create: Callable[[str], None],
    ) -> None:
        super().__init__(master)
        self.title("New Scene")
        self.resizable(False, False)
        self.grab_set()

        self._allow = allow
        self._prefix = project_prefix
        self._on_create = on_create
        self._characters = sorted(allow.characters) if allow.characters else []
        self._locations = sorted(allow.locations.keys()) if allow.locations else []

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        # -- Scene setup fields ----------------------------------------------
        ttk.Label(
            body, text="Scene setup", font=("Segoe UI", 11, "bold"),
        ).pack(anchor=tk.W, pady=(0, 6))

        form = ttk.Frame(body)
        form.pack(fill=tk.X)

        row = 0

        # Title
        row = self._add_entry(form, "Title:", row, "title")

        # Scene Id (auto-generated, editable)
        ttk.Label(form, text="Scene Id:").grid(
            row=row, column=0, sticky=tk.W, pady=2, padx=(0, 8),
        )
        self._scene_id_var = tk.StringVar(value=f"{project_prefix}_")
        self._scene_id_auto = True
        id_entry = ttk.Entry(form, textvariable=self._scene_id_var, width=30)
        id_entry.grid(row=row, column=1, sticky=tk.W, pady=2)
        self._scene_id_var.trace_add("write", self._on_id_manual_edit)
        row += 1

        # Character
        row = self._add_character_or_entry(form, "Character:", row, "character")

        # Scene Type
        self._scene_type_var = tk.StringVar(value="cinematic")
        ttk.Label(form, text="Scene Type:").grid(
            row=row, column=0, sticky=tk.W, pady=2, padx=(0, 8),
        )
        type_combo = ttk.Combobox(
            form, textvariable=self._scene_type_var,
            values=SCENE_TYPES, state="readonly", width=28,
        )
        type_combo.grid(row=row, column=1, sticky=tk.W, pady=2)
        type_combo.bind("<<ComboboxSelected>>", self._on_type_change)
        row += 1

        # Dynamic fields container (Trigger / Openness+Stage)
        self._dynamic_frame = ttk.Frame(form)
        self._dynamic_frame.grid(
            row=row, column=0, columnspan=2, sticky=tk.EW,
        )
        self._dynamic_row = row
        row += 1

        # Location (optional)
        row = self._add_location_or_entry(form, "Location (optional):", row, "location")

        # Description (optional)
        row = self._add_entry(form, "Description (optional):", row, "description")

        # -- Build dynamic fields for initial type --
        self._trigger_var = tk.StringVar(value="manual")
        self._build_dynamic_fields()

        # -- Example selector ------------------------------------------------
        ttk.Separator(body, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        ttk.Label(
            body, text="Start from", font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W, pady=(0, 4))

        self._example_var = tk.StringVar(value="empty")
        example_frame = ttk.Frame(body)
        example_frame.pack(fill=tk.X)
        for label, key in EXAMPLES:
            ttk.Radiobutton(
                example_frame, text=label,
                variable=self._example_var, value=key,
                command=self._update_preview,
            ).pack(anchor=tk.W, padx=(8, 0))

        # -- Preview ---------------------------------------------------------
        ttk.Separator(body, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        ttk.Label(
            body, text="Preview", font=("Segoe UI", 9, "bold"),
        ).pack(anchor=tk.W)

        preview_frame = ttk.Frame(body, height=120)
        preview_frame.pack(fill=tk.X, pady=(2, 0))
        preview_frame.pack_propagate(False)

        self._preview_text = tk.Text(
            preview_frame, height=6, width=50,
            font=("Consolas", 9), bg="#1E1E1E", fg="#A0E8C0",
            relief=tk.FLAT, wrap=tk.NONE, state=tk.DISABLED,
        )
        self._preview_text.pack(fill=tk.BOTH, expand=True)

        # -- Buttons ---------------------------------------------------------
        btn_frame = ttk.Frame(body)
        btn_frame.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(
            btn_frame, text="Cancel", style="Danger.TButton",
            command=self.destroy,
        ).pack(side=tk.RIGHT, padx=(4, 0))
        self._create_btn = ttk.Button(
            btn_frame, text="Create", style="Compile.TButton",
            command=self._do_create,
        )
        self._create_btn.pack(side=tk.RIGHT)

        self.bind("<Return>", lambda e: self._do_create())
        self.bind("<Escape>", lambda e: self.destroy())

        # Auto-gen Scene Id from title
        self._vars["title"].trace_add("write", self._auto_scene_id)

        self._update_preview()

        # Center on parent
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    # -- Field helpers -------------------------------------------------------

    _vars: dict[str, tk.StringVar]

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)

    def _add_entry(
        self, parent: ttk.Frame, label: str, row: int, var_key: str,
        default: str = "",
    ) -> int:
        if not hasattr(self, "_vars"):
            self._vars = {}
        ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky=tk.W, pady=2, padx=(0, 8),
        )
        var = tk.StringVar(value=default)
        ttk.Entry(parent, textvariable=var, width=30).grid(
            row=row, column=1, sticky=tk.W, pady=2,
        )
        self._vars[var_key] = var
        var.trace_add("write", lambda *_: self._update_preview())
        return row + 1

    def _add_character_or_entry(
        self, parent: ttk.Frame, label: str, row: int, var_key: str,
    ) -> int:
        if not hasattr(self, "_vars"):
            self._vars = {}
        ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky=tk.W, pady=2, padx=(0, 8),
        )
        default = self._characters[0] if self._characters else ""
        var = tk.StringVar(value=default)
        if self._characters:
            ttk.Combobox(
                parent, textvariable=var,
                values=self._characters, state="readonly", width=28,
            ).grid(row=row, column=1, sticky=tk.W, pady=2)
        else:
            ttk.Entry(parent, textvariable=var, width=30).grid(
                row=row, column=1, sticky=tk.W, pady=2,
            )
        self._vars[var_key] = var
        var.trace_add("write", lambda *_: self._update_preview())
        return row + 1

    def _add_location_or_entry(
        self, parent: ttk.Frame, label: str, row: int, var_key: str,
    ) -> int:
        if not hasattr(self, "_vars"):
            self._vars = {}
        ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky=tk.W, pady=2, padx=(0, 8),
        )
        var = tk.StringVar(value="")
        if self._locations:
            locs = [""] + self._locations
            ttk.Combobox(
                parent, textvariable=var,
                values=locs, state="readonly", width=28,
            ).grid(row=row, column=1, sticky=tk.W, pady=2)
        else:
            ttk.Entry(parent, textvariable=var, width=30).grid(
                row=row, column=1, sticky=tk.W, pady=2,
            )
        self._vars[var_key] = var
        var.trace_add("write", lambda *_: self._update_preview())
        return row + 1

    # -- Scene Id auto-generation --------------------------------------------

    def _auto_scene_id(self, *_args: Any) -> None:
        """Update Scene Id from Title when the user hasn't manually edited it."""
        if not self._scene_id_auto:
            return
        title = self._vars["title"].get()
        slug = _slugify(title)
        new_id = f"{self._prefix}_{slug}" if slug else f"{self._prefix}_"
        self._scene_id_auto = True
        self._scene_id_var.set(new_id)
        self._scene_id_auto = True

    def _on_id_manual_edit(self, *_args: Any) -> None:
        """Detect manual edits to Scene Id to stop auto-generation."""
        title = self._vars["title"].get()
        slug = _slugify(title)
        expected = f"{self._prefix}_{slug}" if slug else f"{self._prefix}_"
        if self._scene_id_var.get() != expected:
            self._scene_id_auto = False
        self._update_preview()

    # -- Dynamic fields (Trigger / Openness+Stage) ---------------------------

    def _on_type_change(self, _event: Any = None) -> None:
        self._build_dynamic_fields()
        self._update_preview()

    def _build_dynamic_fields(self) -> None:
        for widget in self._dynamic_frame.winfo_children():
            widget.destroy()

        scene_type = self._scene_type_var.get()

        if scene_type == "cinematic":
            ttk.Label(self._dynamic_frame, text="Trigger:").grid(
                row=0, column=0, sticky=tk.W, pady=2, padx=(0, 8),
            )
            ttk.Combobox(
                self._dynamic_frame, textvariable=self._trigger_var,
                values=TRIGGERS, state="readonly", width=28,
            ).grid(row=0, column=1, sticky=tk.W, pady=2)


    # -- Preview and creation ------------------------------------------------

    def _get_var(self, key: str) -> str:
        var = self._vars.get(key)
        return var.get() if var else ""

    def _is_featured(self) -> bool:
        """Return whether the selected character has visuals."""
        char = self._get_var("character")
        if not char:
            return False
        return bool(
            self._allow.char_faces.get(char)
            or self._allow.char_moods.get(char)
        )

    def _build_text(self) -> str:
        return build_scene_text(
            title=self._get_var("title"),
            scene_id=self._scene_id_var.get(),
            character=self._get_var("character"),
            scene_type=self._scene_type_var.get(),
            trigger=self._trigger_var.get(),
            location=self._get_var("location"),
            description=self._get_var("description"),
            example=self._example_var.get(),
            featured=self._is_featured(),
        )

    def _update_preview(self, *_args: Any) -> None:
        text = self._build_text()
        self._preview_text.configure(state=tk.NORMAL)
        self._preview_text.delete("1.0", tk.END)
        self._preview_text.insert("1.0", text)
        self._preview_text.configure(state=tk.DISABLED)

    def _do_create(self) -> None:
        text = self._build_text()
        self._on_create(text)
        self.destroy()
