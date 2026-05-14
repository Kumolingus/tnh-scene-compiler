"""Condition builder dialog for the scene editor.

Guided UI that helps writers discover and construct condition
expressions for ``[[if]]``, ``[[elif]]``, and choice guards.

The pure-logic helpers (``build_condition``, ``wrap_condition``) are
importable and testable without Tkinter.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from .allowlists import Allowlists

# -- Constants ---------------------------------------------------------------

CONDITION_TYPES: list[tuple[str, str]] = [
    ("Love / Trust check", "approval"),
    ("Trait check", "trait"),
    ("History check", "history"),
    ("Mood check", "mood"),
    ("Friendship check", "friendship"),
    ("Nearby check", "nearby"),
    ("Personality check", "personality"),
    ("Standalone function", "function"),
]

AXES: list[str] = ["love", "trust"]

WRAP_MODES: list[tuple[str, str]] = [
    ("⟦if …⟧ / ⟦/if⟧", "if_block"),
    ("⟦elif …⟧", "elif"),
    ("⟦if …⟧ (no closing)", "if_open"),
    ("Expression only", "bare"),
]

_REQUIRED_VARS: dict[str, list[str]] = {
    "approval": ["character", "threshold"],
    "trait": ["character", "trait"],
    "history": ["character", "event"],
    "mood": ["character", "mood"],
    "friendship": ["character", "other_character"],
    "nearby": ["character"],
    "personality": ["character", "trait"],
    "function": ["func_name"],
}

_DESCRIPTIONS: dict[str, str] = {
    "approval": (
        "Checks if the character’s love or trust\n"
        "for the player meets the threshold.\n\n"
        "Enter a numeric value (e.g. 500) or a tier\n"
        "name (tiny, small, medium, large, massive)."
    ),
    "trait": (
        "Checks if the character has a specific trait\n"
        "(e.g. shy, bold, romantic)."
    ),
    "history": (
        "Checks if the character has done this event\n"
        "at least once (e.g. kissed_player, fought_villain)."
    ),
    "mood": (
        "Checks the character’s current mood.\n"
        "Mood list depends on the selected character."
    ),
    "friendship": "Checks if two characters are friends.",
    "nearby": (
        "Checks if the character is in close\n"
        "proximity to the player."
    ),
    "personality": (
        "Checks a character’s personality trait.\n"
        "Optional numeric threshold for comparison."
    ),
    "function": (
        "Standalone functions from the\n"
        "condition_functions allowlist.\n"
        "Arguments are free-text (e.g. JeanGrey)."
    ),
}


# -- Pure-logic helpers (no Tkinter) -----------------------------------------

def build_condition(
    kind: str,
    *,
    character: str = "",
    axis: str = "love",
    threshold: str = "",
    trait: str = "",
    event: str = "",
    mood: str = "",
    other_character: str = "",
    func_name: str = "",
    func_args: str = "",
) -> str:
    """Return the DSL condition expression for the given parameters.

    Parameters
    ----------
    kind
        One of the ``CONDITION_TYPES`` keys.
    threshold
        For ``approval``: a numeric value (e.g. ``"500"``) or a tier
        name (``"medium"``).  For ``personality``: optional numeric
        threshold.

    Returns
    -------
    str
        The condition expression, e.g. ``JeanGrey.love >= 500``.
    """
    if kind == "approval":
        return f"{character}.{axis} >= {threshold}"
    if kind == "trait":
        return f'{character}.has("{trait}")'
    if kind == "history":
        return f'{character}.did("{event}")'
    if kind == "mood":
        return f'{character}.mood == "{mood}"'
    if kind == "friendship":
        return f"{character}.friends_with({other_character})"
    if kind == "nearby":
        return f"{character}.nearby"
    if kind == "personality":
        if threshold:
            return f'{character}.personality("{trait}", {threshold})'
        return f'{character}.personality("{trait}")'
    if kind == "function":
        if func_args:
            return f"{func_name}({func_args})"
        return f"{func_name}()"
    return ""


def wrap_condition(condition: str, mode: str) -> str:
    """Wrap a condition expression for insertion into the editor.

    Parameters
    ----------
    condition
        The bare condition expression.
    mode
        One of ``"if_block"``, ``"elif"``, ``"if_open"``, ``"bare"``.
    """
    if mode == "if_block":
        return f"[[if {condition}]]\n\n[[/if]]\n"
    if mode == "elif":
        return f"[[elif {condition}]]\n"
    if mode == "if_open":
        return f"[[if {condition}]]\n"
    return condition


# -- Dialog ------------------------------------------------------------------

class ConditionBuilderDialog(tk.Toplevel):
    """Modal dialog that guides writers through building a condition."""

    def __init__(
        self,
        master: tk.Widget,
        allow: Allowlists,
        insert_cb: Callable[[str], None],
        *,
        characters: list[str] | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Condition Builder")
        self.resizable(False, False)
        self.grab_set()

        self._insert = insert_cb
        self._allow = allow
        self._characters = sorted(characters) if characters else (
            sorted(allow.characters) if allow.characters else []
        )
        self._vars: dict[str, tk.StringVar] = {}
        self._mood_combo_widget: ttk.Combobox | None = None
        self._current_kind: str | None = None

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        # -- Condition type selector -----------------------------------------
        ttk.Label(
            body, text="Condition type:", font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W)

        type_labels = [label for label, _ in CONDITION_TYPES]
        self._type_label_to_key = {label: key for label, key in CONDITION_TYPES}
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

        # -- Wrap mode -------------------------------------------------------
        ttk.Separator(body, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        wrap_frame = ttk.Frame(body)
        wrap_frame.pack(fill=tk.X)
        ttk.Label(wrap_frame, text="Insert as:").pack(side=tk.LEFT, padx=(0, 4))

        wrap_labels = [label for label, _ in WRAP_MODES]
        self._wrap_label_to_key = {label: key for label, key in WRAP_MODES}
        self._wrap_var = tk.StringVar(value=wrap_labels[0])
        wrap_combo = ttk.Combobox(
            wrap_frame, textvariable=self._wrap_var,
            values=wrap_labels, state="readonly", width=28,
        )
        wrap_combo.pack(side=tk.LEFT)
        wrap_combo.bind("<<ComboboxSelected>>", lambda _: self._update_preview())

        # -- Preview ---------------------------------------------------------
        preview_frame = ttk.Frame(body)
        preview_frame.pack(fill=tk.X, pady=(8, 0))
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

        # Build initial params for the first type
        self._on_type_select()

        # Center on parent
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
        """Destroy old parameter widgets and build new ones for *kind*."""
        if self._param_frame is not None:
            self._param_frame.destroy()

        self._param_frame = ttk.Frame(self._param_container)
        self._param_frame.pack(fill=tk.BOTH, expand=True)
        self._vars.clear()
        self._mood_combo_widget = None

        builder = getattr(self, f"_params_{kind}", None)
        if builder:
            builder(self._param_frame)

        self._update_preview()

    # -- Field helpers -------------------------------------------------------

    def _add_character_field(
        self,
        parent: ttk.Frame,
        label: str,
        row: int,
        var_key: str = "character",
    ) -> int:
        """Add a character-selection row. Returns the next row index."""
        ttk.Label(parent, text=f"{label}:").grid(
            row=row, column=0, sticky=tk.W, pady=2, padx=(0, 8),
        )
        default = self._characters[0] if self._characters else ""
        var = tk.StringVar(value=default)

        if self._characters:
            widget = ttk.Combobox(
                parent, textvariable=var,
                values=self._characters, state="readonly", width=20,
            )
            widget.bind(
                "<<ComboboxSelected>>",
                lambda _: self._on_character_changed(),
            )
        else:
            widget = ttk.Entry(parent, textvariable=var, width=22)

        widget.grid(row=row, column=1, sticky=tk.W, pady=2)
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
        """Add a free-text entry row. Returns the next row index."""
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

    def _add_combo_field(
        self,
        parent: ttk.Frame,
        label: str,
        row: int,
        var_key: str,
        values: list[str],
        default: str = "",
    ) -> int:
        """Add a dropdown row. Returns the next row index."""
        ttk.Label(parent, text=f"{label}:").grid(
            row=row, column=0, sticky=tk.W, pady=2, padx=(0, 8),
        )
        var = tk.StringVar(value=default or (values[0] if values else ""))
        ttk.Combobox(
            parent, textvariable=var, values=values,
            state="readonly", width=20,
        ).grid(row=row, column=1, sticky=tk.W, pady=2)
        self._vars[var_key] = var
        var.trace_add("write", lambda *_: self._update_preview())
        return row + 1

    def _add_description(self, parent: ttk.Frame, row: int, kind: str) -> int:
        """Add the help text for the current condition type."""
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

    # -- Character-change callback -------------------------------------------

    def _on_character_changed(self) -> None:
        """Refresh mood values when the character changes in mood mode."""
        if self._current_kind == "mood":
            self._refresh_mood_values()

    def _refresh_mood_values(self) -> None:
        """Update the mood combo with values for the selected character."""
        char_name = self._get_var("character")
        moods = sorted(
            self._allow.shared_moods
            | self._allow.char_moods.get(char_name, set()),
        )
        if self._mood_combo_widget is not None:
            self._mood_combo_widget.configure(values=moods)
            if self._get_var("mood") not in moods and moods:
                self._vars["mood"].set(moods[0])

    # -- Per-type parameter builders -----------------------------------------

    def _params_approval(self, parent: ttk.Frame) -> None:
        row = self._add_character_field(parent, "Character", 0)
        row = self._add_combo_field(parent, "Axis", row, "axis", AXES)
        row = self._add_text_field(
            parent, "Threshold", row, "threshold", default="500",
        )
        self._add_description(parent, row, "approval")

    def _params_trait(self, parent: ttk.Frame) -> None:
        row = self._add_character_field(parent, "Character", 0)
        known_traits = sorted(self._allow.traits) if self._allow.traits else []
        if known_traits:
            row = self._add_combo_field(
                parent, "Trait", row, "trait", known_traits,
            )
        else:
            row = self._add_text_field(
                parent, "Trait", row, "trait", default="shy",
            )
        self._add_description(parent, row, "trait")

    def _params_history(self, parent: ttk.Frame) -> None:
        row = self._add_character_field(parent, "Character", 0)
        known_events = sorted(self._allow.history_events) if self._allow.history_events else []
        if known_events:
            row = self._add_combo_field(
                parent, "Event", row, "event", known_events,
            )
        else:
            row = self._add_text_field(
                parent, "Event", row, "event", default="kissed_player",
            )
        self._add_description(parent, row, "history")

    def _params_mood(self, parent: ttk.Frame) -> None:
        row = self._add_character_field(parent, "Character", 0)

        char = self._characters[0] if self._characters else ""
        moods = sorted(
            self._allow.shared_moods
            | self._allow.char_moods.get(char, set()),
        )
        default_mood = "normal" if "normal" in moods else (moods[0] if moods else "")

        ttk.Label(parent, text="Mood:").grid(
            row=row, column=0, sticky=tk.W, pady=2, padx=(0, 8),
        )
        var = tk.StringVar(value=default_mood)
        self._mood_combo_widget = ttk.Combobox(
            parent, textvariable=var, values=moods,
            state="readonly", width=20,
        )
        self._mood_combo_widget.grid(row=row, column=1, sticky=tk.W, pady=2)
        self._vars["mood"] = var
        var.trace_add("write", lambda *_: self._update_preview())
        row += 1

        self._add_description(parent, row, "mood")

    def _params_friendship(self, parent: ttk.Frame) -> None:
        row = self._add_character_field(parent, "Character", 0)
        default_other = self._characters[1] if len(self._characters) > 1 else ""
        ttk.Label(parent, text="With:").grid(
            row=row, column=0, sticky=tk.W, pady=2, padx=(0, 8),
        )
        var = tk.StringVar(value=default_other)
        if self._characters:
            ttk.Combobox(
                parent, textvariable=var,
                values=self._characters, state="readonly", width=20,
            ).grid(row=row, column=1, sticky=tk.W, pady=2)
        else:
            ttk.Entry(parent, textvariable=var, width=22).grid(
                row=row, column=1, sticky=tk.W, pady=2,
            )
        self._vars["other_character"] = var
        var.trace_add("write", lambda *_: self._update_preview())
        row += 1

        self._add_description(parent, row, "friendship")

    def _params_nearby(self, parent: ttk.Frame) -> None:
        row = self._add_character_field(parent, "Character", 0)
        self._add_description(parent, row, "nearby")

    def _params_personality(self, parent: ttk.Frame) -> None:
        row = self._add_character_field(parent, "Character", 0)
        known_personalities = sorted(self._allow.personalities) if self._allow.personalities else []
        if known_personalities:
            row = self._add_combo_field(
                parent, "Trait", row, "trait", known_personalities,
            )
        else:
            row = self._add_text_field(
                parent, "Trait", row, "trait", default="bold",
            )
        row = self._add_text_field(
            parent, "Threshold (optional)", row, "threshold",
        )
        self._add_description(parent, row, "personality")

    def _params_function(self, parent: ttk.Frame) -> None:
        funcs = sorted(self._allow.condition_functions) if self._allow.condition_functions else []
        if funcs:
            row = self._add_combo_field(
                parent, "Function", 0, "func_name", funcs,
            )
        else:
            row = self._add_text_field(parent, "Function", 0, "func_name")
        row = self._add_text_field(parent, "Arguments", row, "func_args")
        self._add_description(parent, row, "function")

    # -- Preview and insertion -----------------------------------------------

    def _get_var(self, key: str) -> str:
        """Return the current value of a parameter variable, or ``""``."""
        var = self._vars.get(key)
        return var.get() if var else ""

    def _build_current_condition(self) -> str:
        """Build the condition string from the current parameter values."""
        if not self._current_kind:
            return ""
        return build_condition(
            self._current_kind,
            character=self._get_var("character"),
            axis=self._get_var("axis") or "love",
            threshold=self._get_var("threshold"),
            trait=self._get_var("trait"),
            event=self._get_var("event"),
            mood=self._get_var("mood"),
            other_character=self._get_var("other_character"),
            func_name=self._get_var("func_name"),
            func_args=self._get_var("func_args"),
        )

    def _get_wrap_mode(self) -> str:
        """Return the selected wrap mode key."""
        return self._wrap_label_to_key.get(self._wrap_var.get(), "if_block")

    def _update_preview(self, *_args: Any) -> None:
        """Refresh the preview label and the Insert button state."""
        condition = self._build_current_condition()
        wrapped = wrap_condition(condition, self._get_wrap_mode())
        display = wrapped.replace("\n\n", " … ").replace("\n", " ")
        self._preview_var.set(display)

        required = _REQUIRED_VARS.get(self._current_kind or "", [])
        valid = all(self._get_var(k) for k in required)
        self._insert_btn.configure(state=tk.NORMAL if valid else tk.DISABLED)

    def _do_insert(self) -> None:
        """Build the final condition, wrap it, and insert into the editor."""
        if str(self._insert_btn.cget("state")) == "disabled":
            return
        condition = self._build_current_condition()
        wrapped = wrap_condition(condition, self._get_wrap_mode())
        self._insert(wrapped)
        self.destroy()
