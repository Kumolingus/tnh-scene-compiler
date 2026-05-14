"""Action builder dialog for the scene editor.

Guided UI that helps writers discover and construct state-mutation
directives: ``[[give_trait]]``, ``[[remove_trait]]``, ``[[record]]``,
``[[set_personality]]``, and the generic ``[[run]]``.

The pure-logic helper (``build_action``) is importable and testable
without Tkinter.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from .allowlists import Allowlists

# -- Constants ---------------------------------------------------------------

ACTION_TYPES: list[tuple[str, str]] = [
    ("Give trait", "give_trait"),
    ("Remove trait", "remove_trait"),
    ("Record event", "record"),
    ("Set personality", "set_personality"),
    ("Custom function", "run"),
]

_REQUIRED_VARS: dict[str, list[str]] = {
    "give_trait": ["character", "trait"],
    "remove_trait": ["character", "trait"],
    "record": ["character", "event"],
    "set_personality": ["character", "trait", "value"],
    "run": ["func_call"],
}

_DESCRIPTIONS: dict[str, str] = {
    "give_trait": (
        "Grants a trait to a character.\n"
        "Emits: Character.give_trait(\"trait\")"
    ),
    "remove_trait": (
        "Revokes a trait from a character.\n"
        "Emits: Character.remove_trait(\"trait\")"
    ),
    "record": (
        "Records a history event for a character.\n"
        "Emits: Character.History.add(\"event\")"
    ),
    "set_personality": (
        "Sets a personality score for a character.\n"
        "Provide an integer value.\n"
        "Emits: Character.set_personality(\"trait\", value)"
    ),
    "run": (
        "Call any allowlisted function.\n"
        "Type the full call expression."
    ),
}


# -- Pure-logic helper (no Tkinter) ------------------------------------------

def build_action(
    kind: str,
    *,
    character: str = "",
    trait: str = "",
    event: str = "",
    value: str = "",
    func_call: str = "",
) -> str:
    """Return the complete directive line for the given parameters.

    Parameters
    ----------
    kind
        One of the ``ACTION_TYPES`` keys.

    Returns
    -------
    str
        The directive line, e.g. ``[[give_trait JeanGrey shy]]``.
    """
    if kind == "give_trait":
        return f"[[give_trait {character} {trait}]]"
    if kind == "remove_trait":
        return f"[[remove_trait {character} {trait}]]"
    if kind == "record":
        return f"[[record {character} {event}]]"
    if kind == "set_personality":
        return f"[[set_personality {character} {trait} {value}]]"
    if kind == "run":
        call = func_call
        if call and "(" not in call:
            call += "()"
        return f"[[run {call}]]"
    return ""


# -- Dialog ------------------------------------------------------------------

class ActionBuilderDialog(tk.Toplevel):
    """Modal dialog that guides writers through building a state-mutation action."""

    def __init__(
        self,
        master: tk.Widget,
        allow: Allowlists,
        insert_cb: Callable[[str], None],
    ) -> None:
        super().__init__(master)
        self.title("Action Builder")
        self.resizable(False, False)
        self.grab_set()

        self._insert = insert_cb
        self._allow = allow
        self._characters = sorted(allow.characters) if allow.characters else []
        self._vars: dict[str, tk.StringVar] = {}
        self._current_kind: str | None = None

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        # -- Action type selector --------------------------------------------
        ttk.Label(
            body, text="Action type:", font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W)

        type_labels = [label for label, _ in ACTION_TYPES]
        self._type_label_to_key = {label: key for label, key in ACTION_TYPES}
        self._type_var = tk.StringVar(value=type_labels[0])
        type_combo = ttk.Combobox(
            body, textvariable=self._type_var,
            values=type_labels, state="readonly", width=28,
        )
        type_combo.pack(fill=tk.X, pady=(2, 8))
        type_combo.bind("<<ComboboxSelected>>", self._on_type_select)

        ttk.Separator(body, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 8))

        # -- Dynamic parameter area ------------------------------------------
        self._param_container = ttk.Frame(body)
        self._param_container.pack(fill=tk.BOTH, expand=True)
        self._param_frame: ttk.Frame | None = None

        # -- Preview ---------------------------------------------------------
        ttk.Separator(body, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        preview_frame = ttk.Frame(body)
        preview_frame.pack(fill=tk.X, pady=(0, 0))
        ttk.Label(
            preview_frame, text="Preview:", font=("Segoe UI", 9, "bold"),
        ).pack(anchor=tk.W)
        self._preview_var = tk.StringVar()
        ttk.Label(
            preview_frame, textvariable=self._preview_var,
            font=("Consolas", 10), foreground="#A0E8C0",
            wraplength=450, justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(2, 0))

        # -- Buttons ---------------------------------------------------------
        btn_frame = ttk.Frame(body)
        btn_frame.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(
            btn_frame, text="Cancel", style="Danger.TButton",
            command=self.destroy,
        ).pack(side=tk.RIGHT, padx=(4, 0))
        self._insert_btn = ttk.Button(
            btn_frame, text="Insert", style="Compile.TButton",
            command=self._do_insert, state=tk.DISABLED,
        )
        self._insert_btn.pack(side=tk.RIGHT)

        self.bind("<Return>", lambda e: self._do_insert())
        self.bind("<Escape>", lambda e: self.destroy())

        self._on_type_select()

        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    # -- Type selection ------------------------------------------------------

    def _on_type_select(self, _event: Any = None) -> None:
        kind = self._type_label_to_key.get(self._type_var.get())
        if kind is None or kind == self._current_kind:
            return
        self._current_kind = kind
        self._build_params(kind)

    def _build_params(self, kind: str) -> None:
        if self._param_frame is not None:
            self._param_frame.destroy()

        self._param_frame = ttk.Frame(self._param_container)
        self._param_frame.pack(fill=tk.BOTH, expand=True)
        self._vars.clear()

        builder = getattr(self, f"_params_{kind}", None)
        if builder:
            builder(self._param_frame)

        self._update_preview()

    # -- Field helpers -------------------------------------------------------

    def _add_character_field(self, parent: ttk.Frame, row: int) -> int:
        ttk.Label(parent, text="Character:").grid(
            row=row, column=0, sticky=tk.W, pady=2, padx=(0, 8),
        )
        default = self._characters[0] if self._characters else ""
        var = tk.StringVar(value=default)
        if self._characters:
            ttk.Combobox(
                parent, textvariable=var,
                values=self._characters, state="readonly", width=20,
            ).grid(row=row, column=1, sticky=tk.W, pady=2)
        else:
            ttk.Entry(parent, textvariable=var, width=22).grid(
                row=row, column=1, sticky=tk.W, pady=2,
            )
        self._vars["character"] = var
        var.trace_add("write", lambda *_: self._update_preview())
        return row + 1

    def _add_combo_field(
        self,
        parent: ttk.Frame,
        label: str,
        row: int,
        var_key: str,
        values: list[str],
    ) -> int:
        ttk.Label(parent, text=f"{label}:").grid(
            row=row, column=0, sticky=tk.W, pady=2, padx=(0, 8),
        )
        var = tk.StringVar(value=values[0] if values else "")
        ttk.Combobox(
            parent, textvariable=var, values=values,
            state="readonly", width=20,
        ).grid(row=row, column=1, sticky=tk.W, pady=2)
        self._vars[var_key] = var
        var.trace_add("write", lambda *_: self._update_preview())
        return row + 1

    def _add_text_field(
        self,
        parent: ttk.Frame,
        label: str,
        row: int,
        var_key: str,
        default: str = "",
    ) -> int:
        ttk.Label(parent, text=f"{label}:").grid(
            row=row, column=0, sticky=tk.W, pady=2, padx=(0, 8),
        )
        var = tk.StringVar(value=default)
        ttk.Entry(parent, textvariable=var, width=22).grid(
            row=row, column=1, sticky=tk.W, pady=2,
        )
        self._vars[var_key] = var
        var.trace_add("write", lambda *_: self._update_preview())
        return row + 1

    def _add_description(self, parent: ttk.Frame, row: int, kind: str) -> int:
        text = _DESCRIPTIONS.get(kind, "")
        if text:
            ttk.Label(
                parent, text=text,
                foreground="#808080", font=("Segoe UI", 8),
            ).grid(
                row=row, column=0, columnspan=2,
                sticky=tk.W, pady=(12, 0),
            )
            return row + 1
        return row

    # -- Per-type parameter builders -----------------------------------------

    def _params_give_trait(self, parent: ttk.Frame) -> None:
        row = self._add_character_field(parent, 0)
        known_traits = sorted(self._allow.traits) if self._allow.traits else []
        if known_traits:
            row = self._add_combo_field(parent, "Trait", row, "trait", known_traits)
        else:
            row = self._add_text_field(parent, "Trait", row, "trait")
        self._add_description(parent, row, "give_trait")

    def _params_remove_trait(self, parent: ttk.Frame) -> None:
        row = self._add_character_field(parent, 0)
        known_traits = sorted(self._allow.traits) if self._allow.traits else []
        if known_traits:
            row = self._add_combo_field(parent, "Trait", row, "trait", known_traits)
        else:
            row = self._add_text_field(parent, "Trait", row, "trait")
        self._add_description(parent, row, "remove_trait")

    def _params_record(self, parent: ttk.Frame) -> None:
        row = self._add_character_field(parent, 0)
        known_events = sorted(self._allow.history_events) if self._allow.history_events else []
        if known_events:
            row = self._add_combo_field(parent, "Event", row, "event", known_events)
        else:
            row = self._add_text_field(parent, "Event", row, "event")
        self._add_description(parent, row, "record")

    def _params_set_personality(self, parent: ttk.Frame) -> None:
        row = self._add_character_field(parent, 0)
        known = sorted(self._allow.personalities) if self._allow.personalities else []
        if known:
            row = self._add_combo_field(parent, "Trait", row, "trait", known)
        else:
            row = self._add_text_field(parent, "Trait", row, "trait")
        row = self._add_text_field(parent, "Value", row, "value", default="1")
        self._add_description(parent, row, "set_personality")

    def _params_run(self, parent: ttk.Frame) -> None:
        ops = sorted(self._allow.run_operations) if self._allow.run_operations else []
        if ops:
            row = self._add_combo_field(parent, "Function", 0, "func_call", ops)
        else:
            row = self._add_text_field(parent, "Function call", 0, "func_call")
        self._add_description(parent, row, "run")

    # -- Preview and insertion -----------------------------------------------

    def _get_var(self, key: str) -> str:
        var = self._vars.get(key)
        return var.get() if var else ""

    def _update_preview(self, *_args: Any) -> None:
        if not self._current_kind:
            return
        line = build_action(
            self._current_kind,
            character=self._get_var("character"),
            trait=self._get_var("trait"),
            event=self._get_var("event"),
            value=self._get_var("value"),
            func_call=self._get_var("func_call"),
        )
        self._preview_var.set(line)

        required = _REQUIRED_VARS.get(self._current_kind, [])
        valid = all(self._get_var(k) for k in required)
        self._insert_btn.configure(state=tk.NORMAL if valid else tk.DISABLED)

    def _do_insert(self) -> None:
        if str(self._insert_btn.cget("state")) == "disabled":
            return
        line = build_action(
            self._current_kind or "",
            character=self._get_var("character"),
            trait=self._get_var("trait"),
            event=self._get_var("event"),
            value=self._get_var("value"),
            func_call=self._get_var("func_call"),
        )
        self._insert(line + "\n")
        self.destroy()
