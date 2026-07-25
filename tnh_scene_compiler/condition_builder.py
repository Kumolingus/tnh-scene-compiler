"""Condition builder dialog for the scene editor.

Guided UI that helps writers discover and construct condition
expressions for ``[[if]]``, ``[[elif]]``, and choice guards. Any number of
clauses can be added, each (after the first) joined with ``and``/``or``, so
a compound condition is built without hand-typing the boolean expression.

The pure-logic helpers (``build_condition``, ``join_conditions``,
``wrap_condition``) are importable and testable without Tkinter.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk
from typing import Any

from .allowlists import (
    Allowlists,
    group_by_category,
    is_character_collection_param,
    is_character_param,
    is_location_param,
    parse_signature_params,
    return_is_comparable,
    type_is_comparable,
)

# -- Constants ---------------------------------------------------------------

# Top-level condition categories, in display order. The "Condition type"
# selector is two-level (Category -> Condition); these group the built-in
# checks and route allowlist functions in by their own category.
CONDITION_CATEGORIES: list[str] = [
    "Relationships",
    "Character state",
    "Story & history",
    "Location & time",
    "Advanced",
]

# Built-in condition types: (kind, top-level category, label). These are the
# DSL-sugar checks (universal to TNH), hardcoded here; allowlist functions are
# layered in on top by :func:`build_condition_catalog`.
_BUILTIN_TYPES: list[tuple[str, str, str]] = [
    ("approval",    "Relationships",   "Love / Trust check"),
    ("friendship",  "Relationships",   "Friendship check"),
    ("trait",       "Character state", "Trait check"),
    ("mood",        "Character state", "Mood check"),
    ("personality", "Character state", "Personality check"),
    ("nearby",      "Character state", "Nearby check"),
    ("property",    "Character state", "Character property"),
    ("history",     "Story & history", "History check"),
    ("method",      "Advanced",        "Character method (any)"),
]
# There is deliberately no generic "Standalone function (any)" entry here.
# :func:`build_condition_catalog` promotes *every* allowlist function to its own
# entry (an uncategorised one falls to "Advanced"), so a generic picker reached
# nothing that was not already one click away — under raw names, and grouped by
# the raw allowlist ``category`` field, which put the same function under a
# second, conflicting taxonomy ("Approval" vs "Relationships", …). Character
# methods still need their generic picker: they are never promoted individually.

# Allowlist function category -> top-level condition category.
_FUNC_CATEGORY_TO_TOP: dict[str, str] = {
    "Approval": "Relationships",
    "Relationships": "Relationships",
    "Character status": "Character state",
    "Clothing": "Character state",
    "History": "Story & history",
    "Mod state": "Story & history",
    "Location": "Location & time",
    "Time": "Location & time",
}

# Functions already covered by a friendlier built-in type — not surfaced
# individually (they'd duplicate the sugar checks).
_SUGAR_DUPLICATE_FUNCTIONS: frozenset[str] = frozenset({
    "check_approval",                    # Love / Trust check
    "are_Characters_friends",            # Friendship check
    "Character_is_in_close_proximity",   # Nearby check
})

# Top-level category -> glossary search term for the "?" quick-access button.
# The terms hit the enriched cheatsheet's per-family Conditions subsections.
_GLOSSARY_SEARCH_BY_CATEGORY: dict[str, str] = {
    "Relationships": "relationship conditions",
    "Character state": "character-state conditions",
    "Story & history": "story, location",
    "Location & time": "story, location",
    "Advanced": "conditions",
}

# Kept for backward reference; the flat type list is now derived from the
# catalog. Order matches _BUILTIN_TYPES.
CONDITION_TYPES: list[tuple[str, str]] = [
    (label, kind) for kind, _cat, label in _BUILTIN_TYPES
]

AXES: list[str] = ["love", "trust"]

WRAP_MODES: list[tuple[str, str]] = [
    ("⟦if …⟧ / ⟦/if⟧", "if_block"),
    ("⟦elif …⟧", "elif"),
    ("⟦if …⟧ (no closing)", "if_open"),
    ("Expression only", "bare"),
]

# Boolean operators offered before each clause after the first, when
# combining several conditions into one expression.
COMBINE_OPERATORS: list[str] = ["AND", "OR"]


@dataclass(frozen=True)
class ConditionEntry:
    """One pick in the two-level "Condition type" selector.

    ``kind`` is the underlying condition kind (``approval``, ``function``…).
    ``target`` is empty for a built-in check or the generic function/method
    pickers; for a *promoted* standalone function it holds that function's
    name, so the panel jumps straight to its parameter form.
    """

    label: str
    kind: str
    target: str = ""


def build_condition_catalog(allow: Allowlists) -> dict[str, list[ConditionEntry]]:
    """Group condition entries by top-level category for the selector.

    Built-in checks land in their assigned category; each allowlist function
    (minus the sugar duplicates) is surfaced individually under the top-level
    category its own ``category`` maps to, labelled by its ``label`` (or its
    name). Categories are returned in :data:`CONDITION_CATEGORIES` order,
    empty ones dropped; within a category the built-ins keep their order and
    the promoted functions follow, sorted by label.
    """
    builtins: dict[str, list[ConditionEntry]] = {c: [] for c in CONDITION_CATEGORIES}
    for kind, category, label in _BUILTIN_TYPES:
        builtins[category].append(ConditionEntry(label, kind, ""))

    functions: dict[str, list[ConditionEntry]] = {c: [] for c in CONDITION_CATEGORIES}
    for name in allow.condition_functions:
        if name in _SUGAR_DUPLICATE_FUNCTIONS:
            continue
        top = _FUNC_CATEGORY_TO_TOP.get(
            allow.condition_function_categories.get(name, ""), "Advanced",
        )
        label = allow.condition_function_labels.get(name, name)
        functions[top].append(ConditionEntry(label, "function", name))

    catalog: dict[str, list[ConditionEntry]] = {}
    for category in CONDITION_CATEGORIES:
        entries = builtins[category] + sorted(
            functions[category], key=lambda e: e.label.lower(),
        )
        if entries:
            catalog[category] = entries
    return catalog

# Operator choices shown for a comparable (tier/int/float) function or method
# return. The first entry inserts a bare call (empty operator); the rest
# append `<op> <value>`. Default selection is ">=" so the common case nudges
# the writer toward a comparison rather than the truthy-when-nonzero footgun.
COMPARE_OPS: list[str] = ["(no comparison)", ">=", ">", "<=", "<", "==", "!="]
_BARE_COMPARE_LABEL = "(no comparison)"

_REQUIRED_VARS: dict[str, list[str]] = {
    "approval": ["character", "threshold"],
    "trait": ["character", "trait"],
    "history": ["character", "event"],
    "mood": ["character", "mood"],
    "friendship": ["character", "other_character"],
    "nearby": ["character"],
    "personality": ["character", "trait"],
    "property": ["character", "property_name"],
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
        "at least once (e.g. kissed_player, fought_villain).\n"
        "Uses the permanent history — once recorded it\n"
        "stays true for the rest of the save, unless the\n"
        "mod explicitly clears the event."
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
        "Checks a character’s personality score for a\n"
        "trait (e.g. dominant, submissive, protective).\n"
        "Scores are small integers (commonly -1, 0, 1;\n"
        "higher = stronger). With a threshold it checks\n"
        "score >= threshold; give one (e.g. 1) for a\n"
        "clear yes/no — an empty threshold returns the\n"
        "raw score, which reads as true for -1 too."
    ),
    "property": (
        "Checks a read-only character property\n"
        "(e.g. desire, breast_size, sex_experience).\n"
        "These return a number — pick an operator and\n"
        "value in the Compare row."
    ),
    "method": (
        "Checks a low-level, read-only character method\n"
        "(e.g. check_trait, get_status, History.check).\n"
        "Arguments are pre-filled from the method's signature\n"
        "once you pick one."
    ),
    "function": (
        "A ready-made check the game provides as a\n"
        "standalone function. Its arguments are pre-filled\n"
        "from the signature the allowlist declares for it."
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
    property_name: str = "",
    compare_op: str = "",
    compare_value: str = "",
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
    compare_op / compare_value
        For ``function`` / ``method`` whose return value is a number worth
        comparing (a tier/int/float — see :func:`return_is_comparable`): the
        operator and right-hand value appended to the call, e.g.
        ``get_effective_friendship(A, B) >= 2``. An empty ``compare_op`` (or
        empty ``compare_value``) leaves the call bare.

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
    if kind == "property":
        return _append_comparison(
            f"{character}.{property_name}", compare_op, compare_value,
        )
    if kind == "method":
        call = (
            f"{character}.{method_path}({method_args})"
            if method_args else f"{character}.{method_path}()"
        )
        return _append_comparison(call, compare_op, compare_value)
    if kind == "function":
        call = f"{func_name}({func_args})" if func_args else f"{func_name}()"
        return _append_comparison(call, compare_op, compare_value)
    return ""


def _append_comparison(expr: str, op: str, value: str) -> str:
    """Return ``"<expr> <op> <value>"`` when both op and value are set, else ``expr``.

    The bare fallback covers a boolean-returning call (no comparison
    needed) and the in-progress state where the writer picked an operator
    but hasn't typed a value yet.
    """
    op = op.strip()
    value = value.strip()
    if op and value:
        return f"{expr} {op} {value}"
    return expr


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


def join_conditions(clauses: list[tuple[str, str]]) -> str:
    """Join clauses into one expression: ``[(op, cond), ...]``.

    Each clause is an ``(operator, condition)`` pair; the first clause's
    operator is ignored (there's nothing before it). Empty conditions are
    skipped, so an in-progress clause the writer hasn't filled yet doesn't
    break the preview, and the operator that follows a skipped clause still
    joins the next one. Operators (``"and"`` / ``"or"``) are inserted
    verbatim; note ``and`` binds tighter than ``or`` in Python, so a mixed
    chain follows that precedence.
    """
    parts: list[str] = []
    for op, cond in clauses:
        if not cond:
            continue
        if parts:
            parts.append(op or "and")
        parts.append(cond)
    return " ".join(parts)


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


# -- Parameter widget selection (pure) ---------------------------------------

# Widget kinds a signature parameter can map to in the guided form. Picking one
# per parameter decides whether the writer types freely or picks from a
# constrained control.
PARAM_WIDGET_CHOICES = "choices"              # declared param_choices -> editable combo
PARAM_WIDGET_CHARACTER = "character"          # single Character -> readonly combo
PARAM_WIDGET_CHARACTER_SET = "character_set"  # several Characters -> multi-select
PARAM_WIDGET_LOCATION = "location"            # single location -> editable slugline combo
PARAM_WIDGET_BOOL = "bool"                    # bool -> True/False combo
PARAM_WIDGET_DATE = "date"                    # (day, period) tuple -> Day + period fields
PARAM_WIDGET_TEXT = "text"                    # anything else -> free text

# TNH time-of-day periods, in ``time_index`` order (see the base game's
# ``time_options``). A "date" is a ``(day, time_index)`` pair; the date widget
# shows these names and emits the index.
_TIME_PERIODS: list[str] = ["Morning", "Midday", "Evening", "Night", "Late Night"]


def is_bool_param(type_hint: str, default: str) -> bool:
    """Return ``True`` for a boolean parameter (typed ``bool`` or defaulting to one)."""
    if type_hint.strip() == "bool":
        return True
    return default.strip() in ("True", "False")


def is_date_tuple_param(type_hint: str) -> bool:
    """Return ``True`` for a ``(day, time_index)`` date parameter (``tuple[int, int]``).

    The Condition Builder gives these a plain-language Day + time-of-day form
    instead of a raw ``(int, int)`` text field, so a non-developer knows what to
    enter.
    """
    return type_hint.replace(" ", "") == "tuple[int,int]"


def param_widget_kind(
    name: str,
    type_hint: str,
    default: str,
    *,
    has_choices: bool,
) -> str:
    """Pick the input widget kind for one signature parameter.

    Precedence, most specific first:

    1. ``has_choices`` — the entry declared ``param_choices`` for this
       parameter; the writer picks from that curated list (still editable).
    2. a single ``Character`` (:func:`is_character_param`).
    3. a collection of ``Character`` (:func:`is_character_collection_param`) —
       a multi-select producing a set literal.
    4. a single location (:func:`is_location_param`) — an editable combo of the
       known sluglines, inserted **quoted** (the base-game functions accept a
       slugline ``str``).
    5. a ``bool`` (:func:`is_bool_param`) — a ``True`` / ``False`` picker.
    6. otherwise free text.

    Event / other free-string parameters are not inferred (their value set is
    project-specific and needs quoting) — declare ``param_choices`` for them.
    """
    if has_choices:
        return PARAM_WIDGET_CHOICES
    if is_character_param(name, type_hint):
        return PARAM_WIDGET_CHARACTER
    if is_character_collection_param(name, type_hint):
        return PARAM_WIDGET_CHARACTER_SET
    if is_location_param(name, type_hint):
        return PARAM_WIDGET_LOCATION
    if is_bool_param(type_hint, default):
        return PARAM_WIDGET_BOOL
    if is_date_tuple_param(type_hint):
        return PARAM_WIDGET_DATE
    return PARAM_WIDGET_TEXT


def format_character_set(characters: list[str]) -> str:
    """Return a Python set literal for the picked characters.

    ``["JeanGrey", "Rogue"]`` -> ``"{JeanGrey, Rogue}"``. No picks -> ``"set()"``
    (an empty ``{}`` is a dict, not a set). Bare names are emitted, matching how
    single-``Character`` params insert — they resolve to the game's defined
    character store variables.
    """
    picked = [c for c in characters if c]
    if not picked:
        return "set()"
    return "{" + ", ".join(picked) + "}"


def flow_text(text: str) -> str:
    """Collapse a help string's soft line breaks so a wrapping label can reflow it.

    Whitespace within each paragraph is squeezed to single spaces (dropping the
    hand-inserted ``\\n`` that would otherwise fight the label's own
    ``wraplength`` and leave ragged breaks); blank-line paragraph separations
    are kept. Idempotent on already-flowed text.
    """
    paragraphs = text.split("\n\n")
    return "\n\n".join(" ".join(p.split()) for p in paragraphs)


# Named allowlist sets a dynamic ``param_choices`` source can pull from.
_CHOICE_SOURCES: dict[str, Callable[[Allowlists], list[str]]] = {
    "history_events": lambda a: sorted(a.history_events),
    "traits": lambda a: sorted(a.traits),
    "personalities": lambda a: sorted(a.personalities),
    "characters": lambda a: list(a.characters),
    "locations": lambda a: sorted(a.locations),
    "looks": lambda a: sorted(a.looks),
    "stages": lambda a: sorted(a.stages),
    "sfx": lambda a: sorted(a.sfx),
}


def resolve_param_choices(
    spec: list[str] | dict[str, Any], allow: Allowlists,
) -> list[str]:
    """Resolve a declared ``param_choices`` value into the dropdown options.

    A plain list is returned as-is. A dynamic-source mapping
    (``{source: "history_events", quote: true, suffix: ".History"}``) pulls the
    named allowlist set from *allow*, appends the optional ``suffix``, and wraps
    each value in double quotes when ``quote`` is set — so e.g. a history-event
    parameter suggests every known event as a valid quoted string literal, kept
    in sync with the data instead of copied into the allowlist entry. An
    unknown source resolves to no options (the combo stays free text).
    """
    if isinstance(spec, list):
        return list(spec)
    if not isinstance(spec, dict):
        return []
    values = _CHOICE_SOURCES.get(str(spec.get("source", "")), lambda _a: [])(allow)
    suffix = str(spec.get("suffix", ""))
    quote = bool(spec.get("quote", False))
    return [f'"{v}{suffix}"' if quote else f"{v}{suffix}" for v in values]


@dataclass
class _ParamField:
    """One signature parameter's live input state in the guided form.

    ``kind`` is a ``PARAM_WIDGET_*`` constant. Single-value widgets keep their
    ``tk.StringVar`` in ``var``; the multi-select keeps ``(character,
    BooleanVar)`` pairs in ``char_vars``; a location field also keeps a
    "current location?" toggle in ``current_var``. :meth:`value` returns the
    argument string to splice into the call, in signature order.
    """

    name: str
    default: str
    kind: str
    var: tk.StringVar | None = None
    char_vars: list[tuple[str, tk.BooleanVar]] | None = None
    current_var: tk.BooleanVar | None = None
    # Location only: this param takes an *optional* location, so "current" means
    # "no argument" (drop it) rather than passing get_Location() explicitly.
    omit_when_current: bool = False
    # Date only: the time-of-day period name (``var`` holds the day number).
    period_var: tk.StringVar | None = None

    def value(self) -> str:
        """Return the current argument string (``""`` -> caller falls back to default)."""
        if self.kind == PARAM_WIDGET_CHARACTER_SET:
            picked = [c for c, v in (self.char_vars or []) if v.get()]
            return format_character_set(picked)
        if self.kind == PARAM_WIDGET_LOCATION and self.current_var is not None:
            if self.current_var.get():
                # Optional param -> "" so it drops out (the assembler omits a
                # trailing current-location arg); required -> the current room.
                return "" if self.omit_when_current else "get_Location()"
            return self.var.get() if self.var is not None else ""
        if self.kind == PARAM_WIDGET_DATE:
            day = (self.var.get().strip() if self.var is not None else "") or "0"
            period = self.period_var.get() if self.period_var is not None else ""
            index = _TIME_PERIODS.index(period) if period in _TIME_PERIODS else 0
            return f"({day}, {index})"
        return self.var.get() if self.var is not None else ""


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
        self._func_params: list[_ParamField] = []
        self._method_params: list[_ParamField] = []
        # Comparison affordance for a comparable function/method return
        # (tier/int/float). Non-None only while such an entry is selected.
        self._compare_op_var: tk.StringVar | None = None
        self._compare_value_var: tk.StringVar | None = None
        self._current_kind: str | None = None
        # The selected standalone function's name. Every allowlist function is
        # promoted to its own selector entry, so this is always set while the
        # kind is "function" — _params_function has no generic picker to fall
        # back on.
        self._preset_func: str = ""

        # -- Two-level condition-type selector (Category -> Condition) -------
        self._catalog = build_condition_catalog(allow)
        self._categories = list(self._catalog.keys())

        ttk.Label(
            self, text="Condition type:", font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.W)

        selector = ttk.Frame(self)
        selector.pack(fill=tk.X, pady=(2, 8))
        selector.columnconfigure(1, weight=1)

        ttk.Label(selector, text="Category:").grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
        self._category_var = tk.StringVar(value=self._categories[0])
        ttk.Combobox(
            selector, textvariable=self._category_var, values=self._categories,
            state="readonly",
        ).grid(row=0, column=1, sticky=tk.EW, pady=(0, 2))
        self._category_var.trace_add("write", self._on_category_select)
        # Quick access to the glossary, opened on the current category's
        # conditions section.
        ttk.Button(
            selector, text="?", width=2, command=self._open_glossary,
        ).grid(row=0, column=2, rowspan=2, sticky=tk.NS, padx=(6, 0))

        ttk.Label(selector, text="Condition:").grid(row=1, column=0, sticky=tk.W, padx=(0, 6))
        self._condition_var = tk.StringVar()
        self._condition_combo = ttk.Combobox(
            selector, textvariable=self._condition_var, state="readonly",
        )
        self._condition_combo.grid(row=1, column=1, sticky=tk.EW)
        self._condition_var.trace_add("write", self._on_condition_select)

        # -- Dynamic parameter area ---------------------------------------
        self._param_container = ttk.Frame(self)
        self._param_container.pack(fill=tk.BOTH, expand=True)
        self._param_frame: ttk.Frame | None = None

        # Populate the first category's conditions and build the first one
        # (silent — no on_change wired yet; see set_on_change).
        self._refresh_condition_choices()

    def set_on_change(self, callback: Callable[[], None]) -> None:
        """Wire the change notification. Call after construction."""
        self._on_change = callback

    def _notify_change(self) -> None:
        if self._on_change is not None:
            self._on_change()

    # -- Type selection --------------------------------------------------

    def _current_entry(self) -> ConditionEntry | None:
        """Return the catalog entry for the current Category + Condition pick."""
        entries = self._catalog.get(self._category_var.get(), [])
        label = self._condition_var.get()
        for entry in entries:
            if entry.label == label:
                return entry
        return None

    def _refresh_condition_choices(self) -> None:
        """Fill the Condition combo for the selected category and pick the first."""
        entries = self._catalog.get(self._category_var.get(), [])
        labels = [e.label for e in entries]
        self._condition_combo.configure(values=labels)
        # Setting the var fires _on_condition_select (which builds the params).
        self._condition_var.set(labels[0] if labels else "")

    def _on_category_select(self, *_a: Any) -> None:
        self._refresh_condition_choices()

    def _open_glossary(self) -> None:
        """Open the glossary pre-filtered to the current category's section.

        Modal because the Condition Builder itself holds a grab; the grab
        returns to the builder when the glossary closes.
        """
        from .glossary import GlossaryDialog
        search = _GLOSSARY_SEARCH_BY_CATEGORY.get(
            self._category_var.get(), "conditions",
        )
        GlossaryDialog(self.winfo_toplevel(), search=search, modal=True)

    def _on_condition_select(self, *_a: Any) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        self._current_kind = entry.kind
        self._preset_func = entry.target if entry.kind == "function" else ""
        self._build_params(entry.kind)

    def _build_params(self, kind: str) -> None:
        """Destroy old parameter widgets and build new ones for *kind*."""
        if self._param_frame is not None:
            self._param_frame.destroy()

        self._param_frame = ttk.Frame(self._param_container)
        self._param_frame.pack(fill=tk.BOTH, expand=True)
        self._vars.clear()
        self._mood_combo_widget = None
        self._func_params = []
        self._method_params = []
        self._compare_op_var = None
        self._compare_value_var = None

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
                parent, text=flow_text(text),
                foreground="#808080", font=("Segoe UI", 8),
                wraplength=360, justify=tk.LEFT,
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

    def _build_comparison(self, compare_frame: ttk.Frame, is_comparable: bool) -> None:
        """(Re)build the operator + value widgets when *is_comparable*.

        Clears *compare_frame* and, when *is_comparable*, lays out an operator
        combo (default ``>=``) and a value entry, stored on
        ``self._compare_op_var`` / ``self._compare_value_var``. Otherwise it
        leaves both ``None`` so the call/property inserts bare. Callers decide
        comparability: ``return_is_comparable(signature)`` for a function/
        method return, ``type_is_comparable(type)`` for a property. Called
        from the selection callbacks (comparability changes with the pick).
        """
        for widget in compare_frame.winfo_children():
            widget.destroy()
        self._compare_op_var = None
        self._compare_value_var = None
        if not is_comparable:
            return

        ttk.Label(compare_frame, text="Compare:").grid(
            row=0, column=0, sticky=tk.W, pady=(4, 0), padx=(0, 8),
        )
        op_var = tk.StringVar(value=">=")
        self._compare_op_var = op_var
        ttk.Combobox(
            compare_frame, textvariable=op_var, values=COMPARE_OPS,
            state="readonly", width=15,
        ).grid(row=0, column=1, sticky=tk.W, pady=(4, 0))
        value_var = tk.StringVar(value="")
        self._compare_value_var = value_var
        ttk.Entry(compare_frame, textvariable=value_var, width=10).grid(
            row=0, column=2, sticky=tk.W, pady=(4, 0), padx=(4, 0),
        )
        op_var.trace_add("write", lambda *_: self._notify_change())
        value_var.trace_add("write", lambda *_: self._notify_change())

    def _current_comparison(self) -> tuple[str, str]:
        """Return the (operator, value) for the current comparison, or ("", "").

        Maps the bare "(no comparison)" choice to an empty operator so the
        call is inserted without a trailing comparison.
        """
        if self._compare_op_var is None or self._compare_value_var is None:
            return ("", "")
        op = self._compare_op_var.get()
        if op == _BARE_COMPARE_LABEL:
            op = ""
        return (op, self._compare_value_var.get())

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

    def _params_property(self, parent: ttk.Frame) -> None:
        row = self._add_character_field(parent, "Character", 0)
        props = self._allow.character_properties
        if not props:
            row = self._add_text_field(
                parent, "Property", row, "property_name", default="desire",
            )
            self._add_description(parent, row, "property")
            return

        grouped = group_by_category(props, self._allow.character_property_categories)
        cat_names = list(grouped.keys())

        row = self._add_combo_field(parent, "Category", row, "property_category", cat_names)
        prop_row = row
        row = self._add_combo_field(
            parent, "Property", row, "property_name", grouped[cat_names[0]],
        )
        compare_frame = ttk.Frame(parent)
        compare_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W)
        row += 1
        note_label = self._make_note_label(parent, row)
        row += 1

        def _on_category_change(*_a: Any) -> None:
            names = grouped.get(self._get_var("property_category"), [])
            widget = parent.grid_slaves(row=prop_row, column=1)
            if widget:
                widget[0].configure(values=names)
            if names:
                self._vars["property_name"].set(names[0])

        def _on_property_change(*_a: Any) -> None:
            name = self._get_var("property_name")
            note_label.configure(text=flow_text(self._allow.character_property_notes.get(name, "")))
            ptype = self._allow.character_property_types.get(name, "")
            self._build_comparison(compare_frame, type_is_comparable(ptype))
            self._notify_change()

        self._vars["property_category"].trace_add("write", _on_category_change)
        self._vars["property_name"].trace_add("write", _on_property_change)
        _on_property_change()

        self._add_description(parent, row, "property")

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
        compare_frame = ttk.Frame(parent)
        compare_frame.grid(row=row, column=0, columnspan=3, sticky=tk.W)
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
            self._method_params.clear()

            name = self._get_var("method_name")
            note_label.configure(text=flow_text(self._allow.character_method_notes.get(name, "")))
            sig = self._allow.character_method_signatures.get(name, "")
            self._build_comparison(compare_frame, return_is_comparable(sig))
            choices_map = self._allow.character_method_param_choices.get(name, {})
            for i, (pname, ptype, pdefault) in enumerate(parse_signature_params(sig)):
                self._method_params.append(
                    self._build_param_field(
                        params_frame, i, pname, ptype, pdefault, choices_map.get(pname),
                    ),
                )
            self._notify_change()

        self._vars["method_category"].trace_add("write", _on_category_change)
        self._vars["method_name"].trace_add("write", _on_method_change)
        _on_method_change()

        self._add_description(parent, row, "method")

    def _build_param_field(
        self,
        parent: ttk.Frame,
        row: int,
        pname: str,
        ptype: str,
        pdefault: str,
        choices: list[str] | dict[str, Any] | None,
    ) -> _ParamField:
        """Build the label + input widget for one signature parameter.

        The widget kind follows :func:`param_widget_kind`: a declared-choice or
        boolean parameter gets an editable combobox (a suggestion list, not a
        whitelist — another creator may need an off-list value), a single
        ``Character`` a readonly picker, a ``Character`` collection a row of
        checkbuttons that assemble a set literal, everything else a free-text
        entry. Every value change notifies the dialog so the preview and
        Insert-button state stay live. Returns the field capturing its value.
        """
        hint = pname + (f"  ({ptype})" if ptype else "")
        ttk.Label(parent, text=f"{hint}:").grid(
            row=row, column=0, sticky=tk.W, pady=1, padx=(0, 8),
        )
        kind = param_widget_kind(pname, ptype, pdefault, has_choices=bool(choices))
        # No character list to pick from (no allowlist) -> fall back to free text
        # so the writer can still type a set literal by hand.
        if kind == PARAM_WIDGET_CHARACTER_SET and not self._characters:
            kind = PARAM_WIDGET_TEXT

        if kind == PARAM_WIDGET_CHARACTER_SET:
            return self._build_character_set_widget(parent, row, pname, pdefault)
        if kind == PARAM_WIDGET_LOCATION:
            return self._build_location_widget(parent, row, pname, pdefault)
        if kind == PARAM_WIDGET_DATE:
            return self._build_date_widget(parent, row, pname, pdefault)

        var = tk.StringVar(value=pdefault)
        if kind == PARAM_WIDGET_CHOICES:
            ttk.Combobox(
                parent, textvariable=var,
                values=resolve_param_choices(choices or [], self._allow),
                state="normal", width=20,
            ).grid(row=row, column=1, sticky=tk.W, pady=1)
        elif kind == PARAM_WIDGET_CHARACTER:
            ttk.Combobox(
                parent, textvariable=var, values=self._characters,
                state="readonly", width=18,
            ).grid(row=row, column=1, sticky=tk.W, pady=1)
        elif kind == PARAM_WIDGET_BOOL:
            ttk.Combobox(
                parent, textvariable=var, values=["True", "False"],
                state="normal", width=18,
            ).grid(row=row, column=1, sticky=tk.W, pady=1)
        else:
            ttk.Entry(parent, textvariable=var, width=20).grid(
                row=row, column=1, sticky=tk.W, pady=1,
            )
        var.trace_add("write", lambda *_: self._notify_change())
        return _ParamField(pname, pdefault, kind, var=var)

    def _build_character_set_widget(
        self,
        parent: ttk.Frame,
        row: int,
        pname: str,
        pdefault: str,
    ) -> _ParamField:
        """Build a "Choose…" button that opens a dedicated character-picker window.

        A wide row of checkbuttons for a large cast would fight the clause
        list's fixed width, so the picking happens in its own window instead.
        The button just shows how many are chosen; the ticked state lives in the
        shared ``char_vars`` (so it survives reopening the picker), which
        :meth:`_ParamField.value` turns into a set literal. Returns the field.
        """
        char_vars: list[tuple[str, tk.BooleanVar]] = [
            (char, tk.BooleanVar(value=False)) for char in self._characters
        ]
        button = ttk.Button(parent, width=22)
        button.grid(row=row, column=1, sticky=tk.W, pady=1)

        def _refresh_label() -> None:
            chosen = sum(1 for _c, var in char_vars if var.get())
            button.configure(text=f"Choose…  ({chosen})" if chosen else "Choose…")

        button.configure(
            command=lambda: self._open_character_set_picker(pname, char_vars),
        )
        for _char, var in char_vars:
            var.trace_add(
                "write", lambda *_: (_refresh_label(), self._notify_change()),
            )
        _refresh_label()
        return _ParamField(
            pname, pdefault, PARAM_WIDGET_CHARACTER_SET, char_vars=char_vars,
        )

    def _open_character_set_picker(
        self,
        pname: str,
        char_vars: list[tuple[str, tk.BooleanVar]],
    ) -> None:
        """Open a small modal window of checkbuttons bound to *char_vars*.

        The checkbuttons drive the very same ``BooleanVar``s the field reads, so
        edits apply live (button label and preview update through their traces)
        and persist when the window is reopened. Grab returns to the builder on
        close, like the glossary window.
        """
        top = tk.Toplevel(self.winfo_toplevel())
        top.title(f"Choose characters — {pname}")
        top.transient(self.winfo_toplevel())
        top.grab_set()
        body = ttk.Frame(top, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        for i, (char, var) in enumerate(char_vars):
            ttk.Checkbutton(body, text=char, variable=var).grid(
                row=i, column=0, sticky=tk.W, pady=1,
            )
        ttk.Button(body, text="OK", command=top.destroy).grid(
            row=len(char_vars), column=0, sticky=tk.E, pady=(10, 0),
        )
        top.bind("<Return>", lambda _e: top.destroy())
        top.bind("<Escape>", lambda _e: top.destroy())

    def _build_location_widget(
        self,
        parent: ttk.Frame,
        row: int,
        pname: str,
        pdefault: str,
    ) -> _ParamField:
        """Build a location field: a "Current location?" toggle + slugline picker.

        Ticked (the default) inserts ``get_Location()`` — the current room —
        without the writer having to know that call. Unticked reveals an
        editable dropdown of the known sluglines (inserted quoted, since the
        base-game functions accept a slugline ``str``) and pre-selects the
        first so the argument is never left empty.
        """
        holder = ttk.Frame(parent)
        holder.grid(row=row, column=1, sticky=tk.W, pady=1)
        current_var = tk.BooleanVar(value=True)
        var = tk.StringVar(value=pdefault)
        sluglines = [f'"{slugline}"' for slugline in sorted(self._allow.locations)]
        combo = ttk.Combobox(
            holder, textvariable=var, values=sluglines, state="normal", width=20,
        )

        def _toggle() -> None:
            if current_var.get():
                combo.grid_remove()
            else:
                combo.grid()
                if not var.get() and sluglines:
                    var.set(sluglines[0])
            self._notify_change()

        ttk.Checkbutton(
            holder, text="Current location", variable=current_var, command=_toggle,
        ).grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        combo.grid(row=0, column=1, sticky=tk.W)
        combo.grid_remove()  # hidden while "Current location" is on (the default)
        var.trace_add("write", lambda *_: self._notify_change())
        # An optional location param (has a default, e.g. `location=None`) treats
        # "current" as "no argument"; a required one passes get_Location().
        return _ParamField(
            pname, pdefault, PARAM_WIDGET_LOCATION, var=var,
            current_var=current_var, omit_when_current=bool(pdefault.strip()),
        )

    def _build_date_widget(
        self,
        parent: ttk.Frame,
        row: int,
        pname: str,
        pdefault: str,
    ) -> _ParamField:
        """Build a plain-language ``(day, time_index)`` date field.

        A raw ``tuple[int, int]`` means nothing to a writer, so this offers a
        "Day" number and a named time-of-day dropdown (Morning … Late Night),
        and :meth:`_ParamField.value` assembles them into the ``(day, index)``
        tuple the function expects.
        """
        holder = ttk.Frame(parent)
        holder.grid(row=row, column=1, sticky=tk.W, pady=1)
        day_var = tk.StringVar(value="0")
        period_var = tk.StringVar(value=_TIME_PERIODS[0])

        ttk.Label(holder, text="Day").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(holder, textvariable=day_var, width=6).grid(
            row=0, column=1, sticky=tk.W, padx=(4, 10),
        )
        ttk.Label(holder, text="Time of day").grid(row=0, column=2, sticky=tk.W)
        ttk.Combobox(
            holder, textvariable=period_var, values=_TIME_PERIODS,
            state="readonly", width=12,
        ).grid(row=0, column=3, sticky=tk.W, padx=(4, 0))

        day_var.trace_add("write", lambda *_: self._notify_change())
        period_var.trace_add("write", lambda *_: self._notify_change())
        return _ParamField(
            pname, pdefault, PARAM_WIDGET_DATE, var=day_var, period_var=period_var,
        )

    def _render_function_fields(
        self,
        name: str,
        params_frame: ttk.Frame,
        compare_frame: ttk.Frame,
        note_label: ttk.Label,
    ) -> None:
        """(Re)build the per-parameter fields + comparison + note for *name*.

        Shared by the generic function picker and the preset path (a function
        promoted to a top-level condition entry), so both render identically.
        The selected function's name is read back from ``_vars["func_name"]``
        by :meth:`get_condition`; callers set it before calling this.
        """
        for widget in params_frame.winfo_children():
            widget.destroy()
        self._func_params.clear()

        note_label.configure(text=flow_text(self._allow.condition_function_notes.get(name, "")))
        sig = self._allow.condition_function_signatures.get(name, "")
        self._build_comparison(compare_frame, return_is_comparable(sig))
        choices_map = self._allow.condition_function_param_choices.get(name, {})
        for i, (pname, ptype, pdefault) in enumerate(parse_signature_params(sig)):
            self._func_params.append(
                self._build_param_field(
                    params_frame, i, pname, ptype, pdefault, choices_map.get(pname),
                ),
            )
        self._notify_change()

    def _params_function(self, parent: ttk.Frame) -> None:
        """Build the parameter form for the selected standalone function.

        The function is always already known: the selector promotes each
        allowlist function to its own entry, which carries the name in
        ``_preset_func``. So this jumps straight to the per-parameter form —
        there is no "now pick a function" step (see :data:`_BUILTIN_TYPES`).
        """
        self._vars["func_name"] = tk.StringVar(value=self._preset_func)
        params_frame = ttk.Frame(parent)
        params_frame.grid(row=0, column=0, columnspan=2, sticky=tk.W)
        compare_frame = ttk.Frame(parent)
        compare_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W)
        note_label = self._make_note_label(parent, 2)
        self._render_function_fields(
            self._preset_func, params_frame, compare_frame, note_label,
        )
        self._add_description(parent, 3, "function")

    # -- Signature-derived argument assembly ----------------------------------

    @staticmethod
    def _arg_from_field(field: _ParamField) -> str:
        """Return one parameter's argument text, falling back to its default.

        A multi-select (``PARAM_WIDGET_CHARACTER_SET``) never yields an empty
        string — it returns ``set()`` for no picks — so the default fallback
        only ever applies to an untouched single-value field.
        """
        val = field.value().strip()
        return val if val else field.default

    @staticmethod
    def _is_omitted_location(field: _ParamField) -> bool:
        """True for an optional location arg left on "current" — dropped if trailing.

        Keeps ``get_Location()`` from becoming ``get_Location(get_Location())``:
        when an optional ``location`` param is on "Current location", the call
        should simply omit it rather than pass the current room explicitly.
        """
        return (
            field.kind == PARAM_WIDGET_LOCATION
            and field.omit_when_current
            and field.current_var is not None
            and field.current_var.get()
        )

    def _join_args(self, fields: list[_ParamField]) -> str:
        """Join the fields' arguments, dropping trailing omitted-location args."""
        rendered = [(f, self._arg_from_field(f)) for f in fields]
        while rendered and self._is_omitted_location(rendered[-1][0]):
            rendered.pop()
        return ", ".join(val for _f, val in rendered)

    def _assemble_func_args(self) -> str:
        """Return the comma-joined argument list for the "function" kind.

        Falls back to the free-text ``func_args`` field when no
        ``condition_functions`` allowlist was loaded (no per-parameter
        fields were built).
        """
        if self._func_params:
            return self._join_args(self._func_params)
        return self._get_var("func_args")

    def _assemble_method_args(self) -> str:
        """Return the comma-joined argument list for the "method" kind."""
        if not self._method_params:
            return ""
        return self._join_args(self._method_params)

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
        compare_op, compare_value = self._current_comparison()
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
            property_name=self._get_var("property_name"),
            compare_op=compare_op,
            compare_value=compare_value,
        )

    def is_valid(self) -> bool:
        """``True`` once every field required by the current type is filled."""
        required = _REQUIRED_VARS.get(self._current_kind or "", [])
        if not all(self._get_var(k) for k in required):
            return False
        # If a comparison operator is offered and chosen (not the bare
        # "(no comparison)" option), require the right-hand value too — an
        # operator with no value would insert an incomplete `f(...) >= `.
        op, value = self._current_comparison()
        if op and not value:
            return False
        return True


# -- Dialog ------------------------------------------------------------------

class ConditionBuilderDialog(tk.Toplevel):
    """Modal dialog: one or more condition clauses joined with and/or.

    The first clause stands alone; each further clause (added via
    "+ Add condition") carries its own AND/OR operator and a Remove button.
    The clauses join in order (see :func:`join_conditions`). The clause list
    scrolls, so an arbitrary number of conditions fits.
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
        self.resizable(True, True)
        self.minsize(440, 500)
        self.grab_set()

        self._insert = insert_cb
        self._allow = allow
        self._characters = sorted(characters) if characters else (
            sorted(allow.characters) if allow.characters else []
        )
        # Each entry: {"row": Frame, "panel": _ConditionClausePanel,
        #              "op_var": StringVar | None}. op_var is None on the first.
        self._clauses: list[dict[str, Any]] = []

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        # -- Scrollable clause list ------------------------------------------
        scroll_holder = ttk.Frame(body)
        scroll_holder.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(
            scroll_holder, bg="#1E1E1E", highlightthickness=0, borderwidth=0,
        )
        vbar = ttk.Scrollbar(scroll_holder, orient=tk.VERTICAL, command=canvas.yview)
        self._clauses_container = ttk.Frame(canvas)
        window = canvas.create_window(
            (0, 0), window=self._clauses_container, anchor="nw",
        )
        self._clauses_container.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(window, width=e.width),
        )
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )
        self._clauses_canvas = canvas

        # -- Add-condition button --------------------------------------------
        add_bar = ttk.Frame(body)
        add_bar.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(
            add_bar, text="+ Add condition", command=self._add_clause,
        ).pack(side=tk.LEFT)

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
            command=self._close,
        ).pack(side=tk.RIGHT, padx=(4, 0))
        self._insert_btn = ttk.Button(
            btn_frame, text="Insert", style="Compile.TButton",
            command=self._do_insert, state=tk.DISABLED,
        )
        self._insert_btn.pack(side=tk.RIGHT)

        self.bind("<Return>", lambda e: self._do_insert())
        self.bind("<Escape>", lambda e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)

        # The preview/insert widgets now exist, so clause panels can notify.
        self._add_clause()  # first clause, no operator
        self._update_preview()

        # Center on parent
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    # -- Clause management -------------------------------------------------

    def _add_clause(self) -> None:
        is_first = not self._clauses
        row = ttk.Frame(self._clauses_container, padding=(0, 4))
        row.pack(fill=tk.X, expand=True)

        op_var: tk.StringVar | None = None
        remove_btn: ttk.Button | None = None
        if not is_first:
            ttk.Separator(row, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 6))
            header = ttk.Frame(row)
            header.pack(fill=tk.X)
            op_var = tk.StringVar(value=COMBINE_OPERATORS[0])
            ttk.Combobox(
                header, textvariable=op_var, values=COMBINE_OPERATORS,
                state="readonly", width=6,
            ).pack(side=tk.LEFT)
            op_var.trace_add("write", lambda *_: self._update_preview())
            remove_btn = ttk.Button(
                header, text="Remove", style="Danger.TButton", width=8,
            )
            remove_btn.pack(side=tk.RIGHT)

        panel = _ConditionClausePanel(row, self._allow, self._characters)
        panel.pack(fill=tk.BOTH, expand=True)
        panel.set_on_change(self._update_preview)

        entry: dict[str, Any] = {"row": row, "panel": panel, "op_var": op_var}
        if remove_btn is not None:
            remove_btn.configure(command=lambda e=entry: self._remove_clause(e))
        self._clauses.append(entry)

        self._update_preview()
        # Reveal the freshly added clause at the bottom of the scroll region.
        self._clauses_canvas.update_idletasks()
        self._clauses_canvas.yview_moveto(1.0)

    def _remove_clause(self, entry: dict[str, Any]) -> None:
        entry["row"].destroy()
        if entry in self._clauses:
            self._clauses.remove(entry)
        self._update_preview()

    # -- Preview and insertion -----------------------------------------------

    def _get_wrap_mode(self) -> str:
        """Return the selected wrap mode key."""
        return self._wrap_label_to_key.get(self._wrap_var.get(), "if_block")

    def _build_current_condition(self) -> str:
        """Build the combined condition string from every clause, in order."""
        clauses: list[tuple[str, str]] = []
        for entry in self._clauses:
            op_var = entry["op_var"]
            op = "" if op_var is None else op_var.get().lower()
            clauses.append((op, entry["panel"].get_condition()))
        return join_conditions(clauses)

    def _is_valid(self) -> bool:
        return bool(self._clauses) and all(
            entry["panel"].is_valid() for entry in self._clauses
        )

    def _update_preview(self, *_args: Any) -> None:
        """Refresh the preview label and the Insert button state."""
        if not hasattr(self, "_insert_btn"):
            return
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
        self._close()

    def _close(self) -> None:
        # Drop the app-wide mousewheel binding this window installed.
        try:
            self.unbind_all("<MouseWheel>")
        except tk.TclError:
            pass
        self.destroy()
