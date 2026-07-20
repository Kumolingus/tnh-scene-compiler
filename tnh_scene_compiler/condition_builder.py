"""Condition builder dialog for the scene editor.

Guided UI that helps writers discover and construct condition
expressions for ``[[if]]``, ``[[elif]]``, and choice guards. Supports an
optional second clause joined with ``and``/``or`` so two guided checks can
be combined without hand-typing the boolean expression.

The pure-logic helpers (``build_condition``, ``combine_conditions``,
``wrap_condition``) are importable and testable without Tkinter.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from .allowlists import (
    Allowlists,
    group_by_category,
    is_character_param,
    parse_signature_params,
)

# -- Constants ---------------------------------------------------------------

CONDITION_TYPES: list[tuple[str, str]] = [
    ("Love / Trust check", "approval"),
    ("Trait check", "trait"),
    ("History check", "history"),
    ("Mood check", "mood"),
    ("Friendship check", "friendship"),
    ("Nearby check", "nearby"),
    ("Personality check", "personality"),
    ("Character method", "method"),
    ("Standalone function", "function"),
]

AXES: list[str] = ["love", "trust"]

WRAP_MODES: list[tuple[str, str]] = [
    ("⟦if …⟧ / ⟦/if⟧", "if_block"),
    ("⟦elif …⟧", "elif"),
    ("⟦if …⟧ (no closing)", "if_open"),
    ("Expression only", "bare"),
]

COMBINE_MODES: list[tuple[str, str]] = [
    ("Single condition", "none"),
    ("AND", "and"),
    ("OR", "or"),
]

_REQUIRED_VARS: dict[str, list[str]] = {
    "approval": ["character", "threshold"],
    "trait": ["character", "trait"],
    "history": ["character", "event"],
    "mood": ["character", "mood"],
    "friendship": ["character", "other_character"],
    "nearby": ["character"],
    "personality": ["character", "trait"],
    "method": ["character", "method_name"],
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
    "method": (
        "Checks a low-level, read-only character method\n"
        "(e.g. check_trait, get_status, History.check).\n"
        "Arguments are pre-filled from the method's signature\n"
        "once you pick one."
    ),
    "function": (
        "Standalone functions from the\n"
        "condition_functions allowlist.\n"
        "Arguments are pre-filled from the function's signature\n"
        "once you pick one."
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
    method_path: str = "",
    method_args: str = "",
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
    method_path
        For ``method``: the attribute chain to call on ``character``,
        e.g. ``"check_trait"`` or ``"History.check"`` — resolved by the
        caller from the method's ``Character.<path>(...)`` signature
        (see :func:`resolve_method_path`), since most methods hang
        directly off the character but a few (``History.check``) need an
        extra hop.

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
    if kind == "method":
        if method_args:
            return f"{character}.{method_path}({method_args})"
        return f"{character}.{method_path}()"
    if kind == "function":
        if func_args:
            return f"{func_name}({func_args})"
        return f"{func_name}()"
    return ""


def resolve_method_path(signature: str, method_name: str) -> str:
    """Return the attribute chain after ``Character.`` from a method signature.

    ``"Character.History.check(...)"`` -> ``"History.check"``.
    ``"Character.check_trait(...)"`` -> ``"check_trait"``.
    Falls back to the bare *method_name* when *signature* is empty or does
    not start with the expected ``Character.`` call path — this happens for
    the free-text fallback used when no ``character_methods.yaml`` is
    loaded.
    """
    if not signature:
        return method_name
    paren = signature.find("(")
    head = (signature[:paren] if paren >= 0 else signature).strip()
    prefix = "Character."
    if head.startswith(prefix):
        return head[len(prefix):]
    return method_name


def combine_conditions(cond_a: str, op: str, cond_b: str) -> str:
    """Join two condition expressions with a boolean operator.

    *op* is one of the ``COMBINE_MODES`` keys (``"none"``, ``"and"``,
    ``"or"``). ``"none"`` — or a blank *cond_b* — returns *cond_a* alone,
    so a dialog can call this unconditionally regardless of whether a
    second clause is currently active.
    """
    if op == "none" or not cond_b:
        return cond_a
    return f"{cond_a} {op} {cond_b}"


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


# -- Single-clause panel ------------------------------------------------------

class _ConditionClausePanel(ttk.Frame):
    """One condition's worth of guided UI: type selector + dynamic params.

    Embedded once (always) or twice (when the dialog's Combine mode is
    AND/OR) inside :class:`ConditionBuilderDialog`. Owns none of the
    wrap-mode / insert-button / combine-mode state — that stays in the
    dialog, which reads this panel back via :meth:`get_condition` and
    :meth:`is_valid`.

    The change callback is wired via :meth:`set_on_change` *after*
    construction rather than passed into ``__init__`` — the panel builds
    its own initial parameter fields as part of construction (so it opens
    pre-populated), and at that point the dialog's own preview/insert-button
    widgets do not exist yet to be safely notified.
    """

    def __init__(
        self,
        master: tk.Widget,
        allow: Allowlists,
        characters: list[str],
    ) -> None:
        super().__init__(master)
        self._allow = allow
        self._characters = characters
        self._on_change: Callable[[], None] | None = None
        self._vars: dict[str, tk.StringVar] = {}
        self._mood_combo_widget: ttk.Combobox | None = None
        self._func_param_vars: list[tuple[str, str, tk.StringVar]] = []
        self._method_param_vars: list[tuple[str, str, tk.StringVar]] = []
        self._current_kind: str | None = None

        # -- Condition type selector ------------------------------------
        ttk.Label(
            self, text="Condition type:", font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W)

        type_labels = [label for label, _ in CONDITION_TYPES]
        self._type_label_to_key = {label: key for label, key in CONDITION_TYPES}
        self._type_var = tk.StringVar(value=type_labels[0])
        type_combo = ttk.Combobox(
            self, textvariable=self._type_var,
            values=type_labels, state="readonly", width=28,
        )
        type_combo.pack(fill=tk.X, pady=(2, 8))
        type_combo.bind("<<ComboboxSelected>>", self._on_type_select)

        # -- Dynamic parameter area ---------------------------------------
        self._param_container = ttk.Frame(self)
        self._param_container.pack(fill=tk.BOTH, expand=True)
        self._param_frame: ttk.Frame | None = None

        # Build initial params for the first type (silent — no on_change
        # wired yet; see set_on_change).
        self._on_type_select()

    def set_on_change(self, callback: Callable[[], None]) -> None:
        """Wire the change notification. Call after construction."""
        self._on_change = callback

    def _notify_change(self) -> None:
        if self._on_change is not None:
            self._on_change()

    # -- Type selection --------------------------------------------------

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
        self._func_param_vars = []
        self._method_param_vars = []

        builder = getattr(self, f"_params_{kind}", None)
        if builder:
            builder(self._param_frame)

        self._notify_change()

    # -- Field helpers -----------------------------------------------------

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
        var.trace_add("write", lambda *_: self._notify_change())
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
        var.trace_add("write", lambda *_: self._notify_change())
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
        var.trace_add("write", lambda *_: self._notify_change())
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

    def _make_note_label(self, parent: ttk.Frame, row: int) -> ttk.Label:
        """Create an empty, per-selection note label and return it.

        Distinct from ``_add_description`` (static per condition-type text):
        the returned label is updated with the currently-selected
        function/method's ``notes:`` each time the selection changes, so a
        writer sees e.g. the "this returns a tier, compare it" warning on
        the tier-returning friendship functions. Warmer colour than the
        grey description so it reads as a heads-up, not boilerplate.
        """
        label = ttk.Label(
            parent, text="", foreground="#E0A030", font=("Segoe UI", 8),
            wraplength=360, justify=tk.LEFT,
        )
        label.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(6, 0))
        return label

    # -- Character-change callback -----------------------------------------

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
        var.trace_add("write", lambda *_: self._notify_change())
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
        var.trace_add("write", lambda *_: self._notify_change())
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

    def _params_method(self, parent: ttk.Frame) -> None:
        row = self._add_character_field(parent, "Character", 0)
        known_methods = sorted(self._allow.character_methods) if self._allow.character_methods else []
        if not known_methods:
            row = self._add_text_field(
                parent, "Method", row, "method_name", default="check_trait",
            )
            self._add_description(parent, row, "method")
            return

        grouped = group_by_category(
            self._allow.character_methods, self._allow.character_method_categories,
        )
        cat_names = list(grouped.keys())

        row = self._add_combo_field(parent, "Category", row, "method_category", cat_names)
        method_row = row
        row = self._add_combo_field(
            parent, "Method", row, "method_name", grouped[cat_names[0]],
        )
        params_frame = ttk.Frame(parent)
        params_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))
        row += 1
        note_label = self._make_note_label(parent, row)
        row += 1

        def _on_category_change(*_a: Any) -> None:
            names = grouped.get(self._get_var("method_category"), [])
            widget = parent.grid_slaves(row=method_row, column=1)
            if widget:
                widget[0].configure(values=names)
            if names:
                self._vars["method_name"].set(names[0])

        def _on_method_change(*_a: Any) -> None:
            for widget in params_frame.winfo_children():
                widget.destroy()
            self._method_param_vars.clear()

            name = self._get_var("method_name")
            note_label.configure(text=self._allow.character_method_notes.get(name, ""))
            sig = self._allow.character_method_signatures.get(name, "")
            params = parse_signature_params(sig)
            for i, (pname, ptype, pdefault) in enumerate(params):
                hint = pname
                if ptype:
                    hint += f"  ({ptype})"
                ttk.Label(params_frame, text=f"{hint}:").grid(
                    row=i, column=0, sticky=tk.W, pady=1, padx=(0, 8),
                )
                var = tk.StringVar(value=pdefault)
                self._method_param_vars.append((pname, pdefault, var))
                if is_character_param(pname, ptype):
                    ttk.Combobox(
                        params_frame, textvariable=var, values=self._characters,
                        state="readonly", width=18,
                    ).grid(row=i, column=1, sticky=tk.W, pady=1)
                else:
                    ttk.Entry(params_frame, textvariable=var, width=20).grid(
                        row=i, column=1, sticky=tk.W, pady=1,
                    )
                var.trace_add("write", lambda *_: self._notify_change())

            self._notify_change()

        self._vars["method_category"].trace_add("write", _on_category_change)
        self._vars["method_name"].trace_add("write", _on_method_change)
        _on_method_change()

        self._add_description(parent, row, "method")

    def _params_function(self, parent: ttk.Frame) -> None:
        funcs = sorted(self._allow.condition_functions) if self._allow.condition_functions else []
        if not funcs:
            row = self._add_text_field(parent, "Function", 0, "func_name")
            row = self._add_text_field(parent, "Arguments", row, "func_args")
            self._add_description(parent, row, "function")
            return

        grouped = group_by_category(
            self._allow.condition_functions, self._allow.condition_function_categories,
        )
        cat_names = list(grouped.keys())

        row = self._add_combo_field(parent, "Category", 0, "func_category", cat_names)
        func_row = row
        row = self._add_combo_field(
            parent, "Function", row, "func_name", grouped[cat_names[0]],
        )
        params_frame = ttk.Frame(parent)
        params_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(4, 0))
        row += 1
        note_label = self._make_note_label(parent, row)
        row += 1

        def _on_category_change(*_a: Any) -> None:
            names = grouped.get(self._get_var("func_category"), [])
            widget = parent.grid_slaves(row=func_row, column=1)
            if widget:
                widget[0].configure(values=names)
            if names:
                self._vars["func_name"].set(names[0])

        def _on_func_change(*_a: Any) -> None:
            for widget in params_frame.winfo_children():
                widget.destroy()
            self._func_param_vars.clear()

            name = self._get_var("func_name")
            note_label.configure(text=self._allow.condition_function_notes.get(name, ""))
            sig = self._allow.condition_function_signatures.get(name, "")
            params = parse_signature_params(sig)
            for i, (pname, ptype, pdefault) in enumerate(params):
                hint = pname
                if ptype:
                    hint += f"  ({ptype})"
                ttk.Label(params_frame, text=f"{hint}:").grid(
                    row=i, column=0, sticky=tk.W, pady=1, padx=(0, 8),
                )
                var = tk.StringVar(value=pdefault)
                self._func_param_vars.append((pname, pdefault, var))
                if is_character_param(pname, ptype):
                    ttk.Combobox(
                        params_frame, textvariable=var, values=self._characters,
                        state="readonly", width=18,
                    ).grid(row=i, column=1, sticky=tk.W, pady=1)
                else:
                    ttk.Entry(params_frame, textvariable=var, width=20).grid(
                        row=i, column=1, sticky=tk.W, pady=1,
                    )
                var.trace_add("write", lambda *_: self._notify_change())

            self._notify_change()

        self._vars["func_category"].trace_add("write", _on_category_change)
        self._vars["func_name"].trace_add("write", _on_func_change)
        _on_func_change()

        self._add_description(parent, row, "function")

    # -- Signature-derived argument assembly ----------------------------------

    def _assemble_func_args(self) -> str:
        """Return the comma-joined argument list for the "function" kind.

        Falls back to the free-text ``func_args`` field when no
        ``condition_functions`` allowlist was loaded (no per-parameter
        fields were built).
        """
        if self._func_param_vars:
            parts = []
            for _pname, default, var in self._func_param_vars:
                val = var.get().strip()
                parts.append(val if val else default)
            return ", ".join(parts)
        return self._get_var("func_args")

    def _assemble_method_args(self) -> str:
        """Return the comma-joined argument list for the "method" kind."""
        if not self._method_param_vars:
            return ""
        parts = []
        for _pname, default, var in self._method_param_vars:
            val = var.get().strip()
            parts.append(val if val else default)
        return ", ".join(parts)

    def _resolve_method_path(self) -> str:
        """Return the attribute chain to call for the current "method" kind."""
        name = self._get_var("method_name")
        sig = self._allow.character_method_signatures.get(name, "")
        return resolve_method_path(sig, name)

    # -- Public accessors ------------------------------------------------

    def _get_var(self, key: str) -> str:
        """Return the current value of a parameter variable, or ``""``."""
        var = self._vars.get(key)
        return var.get() if var else ""

    def get_condition(self) -> str:
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
            func_args=self._assemble_func_args(),
            method_path=self._resolve_method_path(),
            method_args=self._assemble_method_args(),
        )

    def is_valid(self) -> bool:
        """``True`` once every field required by the current type is filled."""
        required = _REQUIRED_VARS.get(self._current_kind or "", [])
        return all(self._get_var(k) for k in required)


# -- Dialog ------------------------------------------------------------------

class ConditionBuilderDialog(tk.Toplevel):
    """Modal dialog that guides writers through building a condition.

    Always shows one :class:`_ConditionClausePanel`. Setting "Combine
    with" to AND/OR reveals a second panel; the two clauses are then
    joined with that operator (see :func:`combine_conditions`).
    """

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
        self._clause_b: _ConditionClausePanel | None = None

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        # -- Clause A (always present) ---------------------------------------
        self._clause_a = _ConditionClausePanel(body, allow, self._characters)
        self._clause_a.pack(fill=tk.BOTH, expand=True)

        # -- Combine mode ------------------------------------------------------
        ttk.Separator(body, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        combine_frame = ttk.Frame(body)
        combine_frame.pack(fill=tk.X)
        ttk.Label(combine_frame, text="Combine with:").pack(side=tk.LEFT, padx=(0, 4))

        combine_labels = [label for label, _ in COMBINE_MODES]
        self._combine_label_to_key = {label: key for label, key in COMBINE_MODES}
        self._combine_var = tk.StringVar(value=combine_labels[0])
        combine_combo = ttk.Combobox(
            combine_frame, textvariable=self._combine_var,
            values=combine_labels, state="readonly", width=20,
        )
        combine_combo.pack(side=tk.LEFT)
        combine_combo.bind("<<ComboboxSelected>>", self._on_combine_change)

        # -- Clause B (created lazily) -----------------------------------------
        self._clause_b_container = ttk.Frame(body)

        # -- Wrap mode -------------------------------------------------------
        # Handle kept so clause B's container can be packed just above this
        # separator (via before=) when the combine mode is turned on, instead
        # of appending after the buttons.
        self._pre_wrap_separator = ttk.Separator(body, orient=tk.HORIZONTAL)
        self._pre_wrap_separator.pack(fill=tk.X, pady=8)

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

        # Wire the change callback now that preview/insert-button exist,
        # then run one initial preview pass.
        self._clause_a.set_on_change(self._update_preview)
        self._update_preview()

        # Center on parent
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    # -- Combine mode ------------------------------------------------------

    def _on_combine_change(self, _event: Any = None) -> None:
        mode = self._combine_label_to_key.get(self._combine_var.get(), "none")
        if mode == "none":
            if self._clause_b is not None:
                # Clear the whole container, not just the panel — the
                # separator is a separate child, so destroying only the
                # panel would leave it behind and stack a fresh one on the
                # next none->AND toggle.
                for child in self._clause_b_container.winfo_children():
                    child.destroy()
                self._clause_b = None
            self._clause_b_container.pack_forget()
        else:
            if self._clause_b is None:
                ttk.Separator(
                    self._clause_b_container, orient=tk.HORIZONTAL,
                ).pack(fill=tk.X, pady=(0, 8))
                self._clause_b = _ConditionClausePanel(
                    self._clause_b_container, self._allow, self._characters,
                )
                self._clause_b.pack(fill=tk.BOTH, expand=True)
                self._clause_b.set_on_change(self._update_preview)
            self._clause_b_container.pack(
                fill=tk.BOTH, expand=True, pady=(8, 0), before=self._pre_wrap_separator,
            )
        self._update_preview()

    # -- Preview and insertion -----------------------------------------------

    def _get_wrap_mode(self) -> str:
        """Return the selected wrap mode key."""
        return self._wrap_label_to_key.get(self._wrap_var.get(), "if_block")

    def _get_combine_mode(self) -> str:
        return self._combine_label_to_key.get(self._combine_var.get(), "none")

    def _build_current_condition(self) -> str:
        """Build the (possibly combined) condition string."""
        cond_a = self._clause_a.get_condition()
        mode = self._get_combine_mode()
        if mode == "none" or self._clause_b is None:
            return cond_a
        return combine_conditions(cond_a, mode, self._clause_b.get_condition())

    def _is_valid(self) -> bool:
        if not self._clause_a.is_valid():
            return False
        if self._get_combine_mode() == "none":
            return True
        return self._clause_b is not None and self._clause_b.is_valid()

    def _update_preview(self, *_args: Any) -> None:
        """Refresh the preview label and the Insert button state."""
        condition = self._build_current_condition()
        wrapped = wrap_condition(condition, self._get_wrap_mode())
        display = wrapped.replace("\n\n", " … ").replace("\n", " ")
        self._preview_var.set(display)
        self._insert_btn.configure(state=tk.NORMAL if self._is_valid() else tk.DISABLED)

    def _do_insert(self) -> None:
        """Build the final condition, wrap it, and insert into the editor."""
        if str(self._insert_btn.cget("state")) == "disabled":
            return
        condition = self._build_current_condition()
        wrapped = wrap_condition(condition, self._get_wrap_mode())
        self._insert(wrapped)
        self.destroy()
