"""AST -> Ren'Py ``.rpy`` text.

Covers every node produced by phases 6A and 6B: cinematic scenes with
sluglines, dialogue (with parenthetical-driven ``$ change_mood/face/...``
preludes), narration, the simple directives (``[[pause]]``, ``[[sfx]]``,
``[[set]]``, ``[[label]]``, ``[[goto]]``), and conditional blocks
(``[[if]]`` / ``[[elif]]`` / ``[[else]]``).

Output skeleton::

    # Auto-generated from <path>. Do not edit by hand.

    define all_Events["<scene_id>"] = {
        "conditions": ConditionClass("<conditions>"),
        "flags": {"<trigger>"},
        "priority": <int>,
        "repeatable": <bool>,
    }

    label <scene_id>:
        $ ongoing_Event = True
        $ _scene_state = {}

        $ set_the_scene(location = "<loc_id>", greetings = False)

        "Narration paragraph."
        CHARACTER "Dialogue line."
        if <cond>:
            ...

        $ ongoing_Event = False
        return

Scene-local state (``[[set]]`` / bare identifiers in ``[[if]]``
expressions) is materialised as a single ``_scene_state`` dict reset at
scene entry. Expression codegen rewrites bare :class:`Name` nodes whose
key appears in the scene-local set into ``_scene_state.get("key")`` so
Ren'Py can evaluate the condition without the writer having to qualify
the reference.

Later phases will extend this with a centralised ``_events.rpy``
registry (6D) and the remaining directives (6C: ``[[choice]]``,
``[[call]]``, ``[[phone]]``, ``[[show]]``, ``[[run]]``).
"""

from __future__ import annotations

from dataclasses import dataclass

from .allowlists import Allowlists
from .dsl import transform as dsl_transform
from .ast_nodes import (
    Approval,
    CallScene,
    Choice,
    DialogueBlock,
    Fade,
    FxCall,
    GiveTrait,
    Goto,
    Hide,
    IfChain,
    Label,
    RecordEvent,
    RemoveTrait,
    Run,
    NarrationBlock,
    Parenthetical,
    Pause,
    PhoneClose,
    PhoneOpen,
    Scene,
    SetDirective,
    SetPersonality,
    Sfx,
    Show,
    Slugline,
)
from .expr_parser import (
    Attribute,
    BoolOp,
    Call,
    Compare,
    Literal,
    Member,
    Name,
    UnaryNot,
)


@dataclass(frozen=True, slots=True)
class CodegenContext:
    """Per-mod configuration injected by the CLI."""
    project_prefix: str


# Body indent unit inside a Ren'Py ``label`` block. Matches the rest of the mod.
_INDENT = "    "

# Default event priority when the title page omits it. Source: §11.3.
_DEFAULT_PRIORITY = 50

# §11.9.1 "Allowed identifier roots". These bare names resolve to Ren'Py
# globals (and must not be rewritten as scene-local state).
_TIME_WORLD_KEYS: frozenset[str] = frozenset({
    "day", "time_index", "weekday", "season", "chapter", "chapter_day", "season_day",
})


def _format_seconds(value: float) -> str:
    """Render a pause/sfx duration as a compact int when possible."""
    if value == int(value):
        return str(int(value))
    return repr(value)


def _format_set_value(value: bool | int | float | str) -> str:
    """Render a :class:`SetDirective` value as Ren'Py source."""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
        return f"\"{escaped}\""
    return repr(value)


def _escape_rpy_string(text: str) -> str:
    """Escape backslashes and double-quotes for embedding in a ``"..."`` literal.

    Ren'Py interpolates ``[path]`` at runtime, so we deliberately do **not**
    touch brackets — the validator has already confirmed every ``[...]`` is
    a known path.
    """
    return text.replace("\\", "\\\\").replace("\"", "\\\"")


# --- Time-of-day suffix helpers (shared with the validator) -----------------

_TIME_SUFFIXES: tuple[str, ...] = (" - MORNING", " - DAY", " - EVENING", " - NIGHT")

# Map the slugline suffix to TNH's ``store.time_index`` value. Mirrors the
# mod runner's ``{project_prefix}_scene_time_value_aliases`` table:
# morning=0, day=1, evening=2, night=3. Sluglines without a suffix leave
# ``time_index`` untouched.
_TIME_SUFFIX_TO_INDEX: dict[str, int] = {
    " - MORNING": 0,
    " - DAY": 1,
    " - EVENING": 2,
    " - NIGHT": 3,
}


def _strip_time_suffix(text: str) -> str:
    for suffix in _TIME_SUFFIXES:
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def _resolve_location_id(looked_up: str, allow: Allowlists) -> str:
    """Return the location_id for *looked_up*, using fuzzy interpolation match as fallback."""
    if looked_up in allow.locations:
        return allow.locations[looked_up]
    matched_key = allow.match_location(looked_up)
    if matched_key is not None:
        return allow.locations[matched_key]
    return looked_up


def _time_index_for_suffix(text: str) -> int | None:
    """Return the time_index for ``text``'s suffix, or ``None`` when absent."""
    for suffix, index in _TIME_SUFFIX_TO_INDEX.items():
        if text.endswith(suffix):
            return index
    return None


# --- Scene-local state discovery --------------------------------------------


def _collect_scene_local_keys(body) -> set[str]:
    """Walk the scene body and return every key touched by a ``[[set]]``."""
    keys: set[str] = set()
    _walk_for_set_keys(body, keys)
    return keys


def _walk_for_set_keys(nodes, keys: set[str]) -> None:
    for node in nodes:
        if isinstance(node, SetDirective):
            keys.add(node.key)
        elif isinstance(node, IfChain):
            for branch in node.branches:
                _walk_for_set_keys(branch.body, keys)
        elif isinstance(node, Choice):
            for option in node.options:
                _walk_for_set_keys(option.body, keys)


# --- Scene-local state spec collection (for the testing hub metadata) -------


def _python_kind_for_value(value: object) -> str:
    """Return the metadata ``kind`` tag for a literal value."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    return "str"


def _is_scene_local_name(expr, allow: Allowlists) -> bool:
    """``True`` when ``expr`` is a bare :class:`Name` resolved as scene-local.

    Mirrors the precedence in :func:`_resolve_name`: characters, ``player``
    and time/world keys are excluded so we don't classify them as scene
    state.
    """
    if not isinstance(expr, Name):
        return False
    if allow.characters and expr.name in allow.characters:
        return False
    if expr.name == "player":
        return False
    if expr.name in _TIME_WORLD_KEYS:
        return False
    return True


class _StateSpecCollector:
    """Aggregate the testing-hub state spec dict for one scene.

    The collector is intentionally tolerant: condition functions (calls)
    are ignored, ``Attribute`` accesses are ignored, only bare
    :class:`Name` identifiers feed the spec. This matches the hub
    contract — scene-local toggles and string/int values that the writer
    flips with ``[[set]]`` or branches on with ``[[if]]``.
    """

    def __init__(self, allow: Allowlists) -> None:
        self._allow = allow
        # path -> {"kind": str, "choices": list, "default": object}
        self._specs: dict[str, dict[str, object]] = {}
        # Names that appeared as a truthy/falsy bare check (``[[if K]]``,
        # ``[[if not K]]``). Used to backfill ``[True, False]`` so the hub
        # can offer both states even when the writer only wrote one branch.
        self._bool_uses: set[str] = set()

    def _ensure(self, path: str, kind: str | None = None) -> dict[str, object]:
        spec = self._specs.get(path)
        if spec is None:
            spec = {"kind": kind or "bool", "choices": [], "default": None}
            self._specs[path] = spec
        elif kind and spec["kind"] == "bool" and kind != "bool":
            # Promote bool -> typed when a typed assignment is observed.
            spec["kind"] = kind
        return spec

    def _add_choice(self, path: str, value: object, kind: str | None = None) -> None:
        spec = self._ensure(path, kind = kind)
        choices = spec["choices"]
        assert isinstance(choices, list)
        if value not in choices:
            choices.append(value)
        if spec["default"] is None:
            spec["default"] = value

    def visit_body(self, nodes) -> None:
        for node in nodes:
            if isinstance(node, SetDirective):
                kind = _python_kind_for_value(node.value)
                self._add_choice(node.key, node.value, kind = kind)
            elif isinstance(node, IfChain):
                for branch in node.branches:
                    if branch.condition is not None:
                        self.visit_expr(branch.condition)
                    self.visit_body(branch.body)
            elif isinstance(node, Choice):
                for option in node.options:
                    if option.condition is not None:
                        self.visit_expr(option.condition)
                    self.visit_body(option.body)

    def visit_expr(self, expr) -> None:
        # Bare ``[[if K]]`` — record K as a bool toggle.
        if _is_scene_local_name(expr, self._allow):
            self._bool_uses.add(expr.name)
            self._ensure(expr.name, kind = "bool")
            return
        if isinstance(expr, UnaryNot):
            self.visit_expr(expr.operand)
            return
        if isinstance(expr, BoolOp):
            for operand in expr.operands:
                self.visit_expr(operand)
            return
        if isinstance(expr, Compare):
            self._visit_compare(expr)
            return
        # Calls / Attribute / Literal: nothing to harvest. Calls' arguments
        # may contain scene-local names but those are condition-function
        # arguments (e.g. character refs); skip them to avoid noise.

    def _visit_compare(self, expr) -> None:
        # Walk every (left, op, right) pair. Pattern matched: bare Name on
        # one side and Literal on the other, op == ``==`` or ``!=``.
        operands = [expr.left]
        for _op, right in expr.ops_and_rights:
            operands.append(right)
        for idx in range(len(operands) - 1):
            left = operands[idx]
            right = operands[idx + 1]
            op = expr.ops_and_rights[idx][0]
            if op not in {"==", "!="}:
                continue
            if _is_scene_local_name(left, self._allow) and isinstance(right, Literal):
                self._add_choice(
                    left.name, right.value,
                    kind = _python_kind_for_value(right.value),
                )
            elif _is_scene_local_name(right, self._allow) and isinstance(left, Literal):
                self._add_choice(
                    right.name, left.value,
                    kind = _python_kind_for_value(left.value),
                )

    def finalize(self) -> list[dict[str, object]]:
        """Return the ordered ``state_specs`` list for emission."""
        # Backfill False/True for bool toggles so the hub offers both.
        # Force ``default=False`` for bools regardless of observation
        # order: scene-local toggles start un-set, and a writer who only
        # writes ``[[set X]]`` (the most common pattern) would otherwise
        # have ``X`` default to ``True`` in the hub — preventing the
        # tester from previewing the "user did not pick that branch" case.
        for path, spec in self._specs.items():
            if spec["kind"] != "bool":
                continue
            choices = spec["choices"]
            assert isinstance(choices, list)
            for value in (False, True):
                if value not in choices:
                    choices.append(value)
            # Sort bool choices deterministically: False, True.
            choices.sort(key = lambda value: 0 if value is False else 1)
            spec["default"] = False
        # Stable order: preserve insertion order of paths but make the
        # output deterministic across runs by sorting alphabetically.
        ordered_paths = sorted(self._specs.keys())
        return [
            {
                "path": path,
                "kind": self._specs[path]["kind"],
                "choices": list(self._specs[path]["choices"]),
                "default": self._specs[path]["default"],
            }
            for path in ordered_paths
        ]


def _collect_state_specs(body, allow: Allowlists) -> list[dict[str, object]]:
    """Return the scene-local ``state_specs`` list for the testing hub."""
    collector = _StateSpecCollector(allow)
    collector.visit_body(body)
    return collector.finalize()


# --- Condition-spec collection (testing-hub override metadata) --------------


def _is_overridable_condition_call(expr, allow: Allowlists) -> bool:
    """``True`` when ``expr`` is a ``Call`` the testing hub can override.

    The MVP is intentionally narrow: the target must be a bare
    :class:`Name` whose value is in
    :attr:`Allowlists.condition_functions`, and every argument must be
    a bare :class:`Name` whose value is a registered character or the
    ``player`` literal. Calls with literal/attribute/non-allowlisted
    args fall through to the default rendering and are not exposed in
    the hub.
    """
    expr = dsl_transform(expr, allow.character_aliases, allow.function_aliases)
    if not isinstance(expr, Call):
        return False
    target = expr.target
    if not isinstance(target, Name):
        return False
    if target.name not in allow.condition_functions:
        return False
    for arg in expr.args:
        if not isinstance(arg, Name):
            return False
        if arg.name == "player":
            continue
        if allow.characters and arg.name in allow.characters:
            continue
        return False
    return True


class _ConditionSpecCollector:
    """Collect overridable condition calls per (name, args) pair.

    Each unique ``(helper_name, (arg_name, ...))`` becomes one entry in
    the metadata's ``condition_specs`` list. Duplicate calls in the
    same scene collapse — the hub shows one toggle for both.
    """

    def __init__(self, allow: Allowlists) -> None:
        self._allow = allow
        # ``ordered_keys`` keeps insertion order; ``seen`` deduplicates.
        self._ordered_keys: list[tuple[str, tuple[str, ...]]] = []
        self._seen: set[tuple[str, tuple[str, ...]]] = set()

    def visit_body(self, nodes) -> None:
        for node in nodes:
            if isinstance(node, IfChain):
                for branch in node.branches:
                    if branch.condition is not None:
                        self.visit_expr(branch.condition)
                    self.visit_body(branch.body)
            elif isinstance(node, Choice):
                for option in node.options:
                    if option.condition is not None:
                        self.visit_expr(option.condition)
                    self.visit_body(option.body)

    def visit_expr(self, expr) -> None:
        transformed = dsl_transform(
            expr, self._allow.character_aliases, self._allow.function_aliases,
        )
        if _is_overridable_condition_call(transformed, self._allow):
            assert isinstance(transformed, Call)
            assert isinstance(transformed.target, Name)
            arg_names = tuple(arg.name for arg in transformed.args if isinstance(arg, Name))
            key = (transformed.target.name, arg_names)
            if key not in self._seen:
                self._seen.add(key)
                self._ordered_keys.append(key)
            return
        if isinstance(expr, UnaryNot):
            self.visit_expr(expr.operand)
            return
        if isinstance(expr, BoolOp):
            for operand in expr.operands:
                self.visit_expr(operand)
            return
        if isinstance(expr, Compare):
            self.visit_expr(expr.left)
            for _op, right in expr.ops_and_rights:
                self.visit_expr(right)
            return
        if isinstance(expr, Call):
            for arg in expr.args:
                self.visit_expr(arg)

    def finalize(self) -> list[dict[str, object]]:
        return [
            {"name": name, "args": list(args), "kind": "bool"}
            for name, args in self._ordered_keys
        ]


def _collect_condition_specs(body, allow: Allowlists) -> list[dict[str, object]]:
    """Return the overridable ``condition_specs`` list for the testing hub."""
    collector = _ConditionSpecCollector(allow)
    collector.visit_body(body)
    return collector.finalize()


# --- Called-scenes collection (testing-hub chain enumeration) ---------------


def _collect_called_scenes(body) -> list[str]:
    """Return every ``[[call <id>]]`` scene id reachable from ``body``.

    The list is order-preserving and deduplicated. The testing hub
    uses it to walk a scene's chain at preview time so the
    ``Override condition results`` menu can offer the conditions of
    sub-scenes called from the selected one (e.g. announcement
    chaining into discussion).
    """
    collected: list[str] = []
    seen: set[str] = set()

    def visit(nodes) -> None:
        for node in nodes:
            if isinstance(node, CallScene):
                scene_id = str(node.scene_id or "").strip()
                if scene_id and scene_id not in seen:
                    seen.add(scene_id)
                    collected.append(scene_id)
            elif isinstance(node, IfChain):
                for branch in node.branches:
                    visit(branch.body)
            elif isinstance(node, Choice):
                for option in node.options:
                    visit(option.body)

    visit(body)
    return collected


# --- Expression rendering ----------------------------------------------------


def _render_expr(
    expr,
    scene_local: set[str],
    allow: Allowlists,
    ctx: CodegenContext,
) -> str:
    """Render an :class:`Expr` into Ren'Py source.

    The expression is first run through the DSL transformation layer so
    writer-friendly sugar is rewritten before emission.

    Bare :class:`Name` nodes are resolved in precedence order:

    1. Registered character -> leave as-is (``JeanGrey``).
    2. ``player`` -> leave as-is.
    3. Time/world key (``day``, ``season``, …) -> leave as-is.
    4. Scene-local key -> rewrite to ``_scene_state.get("key")``.
    5. Condition-function name is left as-is (the call emission adds parens).
    6. Anything else -> default to ``_scene_state.get("key")``; the validator
       is expected to have rejected unknown roots before this runs.
    """
    expr = dsl_transform(expr, allow.character_aliases, allow.function_aliases)
    if isinstance(expr, Literal):
        return expr.to_rpy()
    if isinstance(expr, Name):
        return _resolve_name(expr.name, scene_local, allow)
    if isinstance(expr, Attribute):
        # Attribute roots may only be characters, player, or time/world
        # keys — never scene-local (scene-local is a flat dict).
        return ".".join((expr.root.name, *expr.parts))
    if isinstance(expr, Call):
        # Calls into condition-functions where every arg is a bare
        # character / player Name route through
        # ``{project_prefix}_testing_eval_condition`` so the testing hub
        # can substitute a preview value at runtime. In normal
        # gameplay the override store-var is ``None`` and the wrapper
        # falls back to the original ``fn(*args)`` call.
        if _is_overridable_condition_call(expr, allow):
            assert isinstance(expr.target, Name)
            name = expr.target.name
            arg_runtime = [arg.name for arg in expr.args if isinstance(arg, Name)]
            arg_runtime_literal = _format_tuple_literal(arg_runtime)
            arg_name_literal = _format_tuple_literal(
                [repr(arg) for arg in arg_runtime],
            )
            return (
                f"{ctx.project_prefix}_testing_eval_condition("
                f"{name!r}, {name}, {arg_runtime_literal}, {arg_name_literal})"
            )
        target_str = _render_call_target(expr.target, scene_local, allow)
        arg_str = ", ".join(
            _render_expr(a, scene_local, allow, ctx) for a in expr.args
        )
        return f"{target_str}({arg_str})"
    if isinstance(expr, UnaryNot):
        return f"not {_render_expr(expr.operand, scene_local, allow, ctx)}"
    if isinstance(expr, BoolOp):
        sep = f" {expr.op} "
        return sep.join(
            _render_expr(o, scene_local, allow, ctx) for o in expr.operands
        )
    if isinstance(expr, Compare):
        parts = [_render_expr(expr.left, scene_local, allow, ctx)]
        for op, right in expr.ops_and_rights:
            parts.append(f" {op} {_render_expr(right, scene_local, allow, ctx)}")
        return "".join(parts)
    if isinstance(expr, Member):
        left = _render_expr(expr.left, scene_local, allow, ctx)
        right = _render_expr(expr.right, scene_local, allow, ctx)
        return f"{left} {expr.op} {right}"
    # Defensive: an unknown node means the expression parser grew a kind
    # without teaching codegen about it.
    raise TypeError(f"Unsupported expression node {type(expr).__name__}")


def _resolve_name(name: str, scene_local: set[str], allow: Allowlists) -> str:
    if allow.characters and name in allow.characters:
        return name
    if name == "player":
        return name
    if name in _TIME_WORLD_KEYS:
        return name
    if name in scene_local:
        return f"_scene_state.get({name!r})"
    # Fall-through: treat as scene-local. The validator is responsible for
    # catching truly unknown roots before this point.
    return f"_scene_state.get({name!r})"


def _render_call_target(target, scene_local: set[str], allow: Allowlists) -> str:
    """Render a :class:`Call` target (``Name`` or ``Attribute``).

    Names that aren't characters/player/time-world fall back to bare
    identifiers — condition-function calls resolve to Ren'Py-side helpers,
    not scene-local state, so we don't wrap them with ``_scene_state``.
    """
    if isinstance(target, Name):
        if allow.characters and target.name in allow.characters:
            return target.name
        if target.name == "player":
            return target.name
        if target.name in _TIME_WORLD_KEYS:
            return target.name
        return target.name  # condition-function name
    if isinstance(target, Attribute):
        return ".".join((target.root.name, *target.parts))
    raise TypeError(f"Unsupported call target {type(target).__name__}")


# --- Per-section emitters ----------------------------------------------------


def _emit_event_block(scene: Scene) -> list[str]:
    """Return the ``define all_Events[...]`` block lines for a cinematic scene.

    Public via :func:`generate_event_entry` — the per-scene ``.rpy`` no
    longer inlines this block; the CLI collects every scene's event entry
    into a single ``_events.rpy`` via :func:`generate_events_rpy`.
    """
    tp = scene.title_page
    lines = [f"define all_Events[{tp.scene_id!r}] = {{"]

    if tp.conditions:
        escaped = _escape_rpy_string(tp.conditions)
        lines.append(f"{_INDENT}\"conditions\": ConditionClass(\"{escaped}\"),")

    flag = tp.trigger or "manual"
    lines.append(f"{_INDENT}\"flags\": {{\"{flag}\"}},")

    priority = tp.priority if tp.priority is not None else _DEFAULT_PRIORITY
    lines.append(f"{_INDENT}\"priority\": {priority},")

    repeatable = tp.repeatable if tp.repeatable is not None else False
    lines.append(f"{_INDENT}\"repeatable\": {repeatable},")

    if tp.tags:
        tag_literal = ", ".join(f"\"{tag}\"" for tag in tp.tags)
        lines.append(f"{_INDENT}\"tags\": {{{tag_literal}}},")

    lines.append("}")
    return lines


def generate_event_entry(scene: Scene) -> str:
    """Return the ``define all_Events[...] = {...}`` block for ``scene``.

    Emitted for cinematic scenes; phone/texting/hub_option scenes omit
    event registration per §11.13 and this function returns an empty
    string for them.
    """
    if scene.title_page.scene_type != "cinematic":
        return ""
    return "\n".join(_emit_event_block(scene))


def generate_events_rpy(scenes, ctx: CodegenContext) -> str:
    """Return a consolidated ``_events.rpy`` for ``scenes``.

    Picks up every cinematic scene's event entry in the order supplied
    and concatenates them with one blank line between entries. An empty
    ``scenes`` list produces only the header comment — the CLI emits
    the file even on empty input so a stale on-disk ``_events.rpy``
    doesn't linger past a "deleted every scene" regression.
    """
    lines = [
        "# Auto-generated by tnh-scene-compiler from scenes_source/**/*.scene.",
        "# Do not edit by hand.",
        "",
    ]
    entries: list[str] = []
    for scene in scenes:
        entry = generate_event_entry(scene)
        if entry:
            entries.append(entry)
    if entries:
        lines.append("\n\n".join(entries))
        lines.append("")  # trailing newline
    return "\n".join(lines)


def _emit_set_scene(
    location_id: str,
    indent: str,
    time_index: int | None = None,
    *,
    clean_present: bool = False,
) -> list[str]:
    """Emit the set-scene block: optional time_index, then ``set_the_scene``.

    TNH's ``set_the_scene`` does not take a time argument (see
    ``core/mechanics/characters.rpy:143``). When the slugline carries a
    time-of-day suffix the codegen emits a ``$ time_index = N``
    assignment first so the background renders with the correct
    lighting / tint.

    When ``clean_present`` is set (cinematic scenes), the codegen passes
    ``show_Characters = False`` to ``set_the_scene`` AND follows it with
    ``remove_everyone_but([], send_Offscreen = True)``. Both are needed:

    - ``show_Characters = False`` only suppresses *rendering*; it does
      not empty ``Location.Present``. ``set_the_scene`` (and the
      ``rebalance_Location_Characters`` it runs while travelling) leaves
      stray NPCs in ``Present``, so a later ``add_Characters`` re-renders
      them — e.g. Jean popping into Rogue's announcement.
    - ``remove_everyone_but([], send_Offscreen = True)`` empties
      ``Present`` (``get_visible_Characters`` reads ``Location.Present``,
      not the rendered set, so it still finds the suppressed NPCs). The
      ``send_Offscreen`` path goes through ``hide_Character`` rather than
      ``remove_Characters``, so no ``set_Outfits(instant=False)`` re-dress
      animation runs. ``show_Characters = False`` means nobody was drawn,
      so the clear is also flash-free.

    The cinematic then opts characters back in via ``[[show]]`` /
    ``[[say]]`` (``add_Characters``) — the documented "cinematic starts
    empty" contract in 11_dialogue_authoring.md §11.8.
    """
    lines: list[str] = []
    if time_index is not None:
        lines.append(f"{indent}$ time_index = {time_index}")
    extra_args = ", show_Characters = False" if clean_present else ""
    lines.append(
        f"{indent}$ set_the_scene(location = \"{location_id}\", "
        f"greetings = False{extra_args})",
    )
    if clean_present:
        lines.append(
            f"{indent}$ remove_everyone_but([], send_Offscreen = True)",
        )
    return lines


def _emit_parenthetical_prelude(
    paren: Parenthetical,
    speaker_pascal: str,
    indent: str,
    *,
    use_fade: bool = False,
) -> list[str]:
    """Emit state-change calls for the parenthetical's populated slots.

    Emission order matches the TNH base-game idiom (see e.g.
    ``characters/JeanGrey/events/optional/chapter_one/season_four/blockbusters.rpy:89-95``):
    every visual state change is applied **before** ``add_Characters``
    brings the sprite on screen. Applying outfit/face/arms first — with
    ``change_Outfit(..., instant = True)`` so the wardrobe swap is not
    animated — means the character appears already in the target state
    instead of being added in a default pose and visibly "dressing".
    """
    lines: list[str] = []
    if paren.outfit:
        # ``change_Outfit`` is a module-level function in
        # ``core/mechanics/clothing.rpy:1136``:
        # ``def change_Outfit(Character, Outfit, instant=False)``. It is
        # NOT a method on CompanionClass — calling
        # ``Char.change_Outfit(...)`` raises AttributeError. Resolve the
        # outfit name through the character's Wardrobe and call the
        # free function with the character as first arg.
        #
        # ``instant = True`` skips the try_on/take_off animations so the
        # swap is not visible at runtime. Required when outfit is set
        # before the character enters the stage (no animated dressing).
        lines.append(
            f"{indent}$ change_Outfit({speaker_pascal}, "
            f"{speaker_pascal}.Wardrobe.Outfits[\"{paren.outfit}\"], "
            "instant = True)",
        )
    if paren.mood:
        lines.append(f"{indent}$ {speaker_pascal}.change_mood(\"{paren.mood}\")")
    if paren.face:
        lines.append(f"{indent}$ {speaker_pascal}.change_face(\"{paren.face}\")")
    if paren.arms or paren.left_arm or paren.right_arm:
        preset = f"\"{paren.arms}\"" if paren.arms else "None"
        kwargs: list[str] = []
        if paren.left_arm:
            kwargs.append(f"left_arm = \"{paren.left_arm}\"")
        if paren.right_arm:
            kwargs.append(f"right_arm = \"{paren.right_arm}\"")
        args = ", ".join([preset, *kwargs])
        lines.append(f"{indent}$ {speaker_pascal}.change_arms({args})")
    if paren.look:
        # CompanionClass has no ``change_look`` method, and no ``face``
        # attribute either — ``FACE_PARTS = ("brows", "eyes", "mouth")``
        # so the current face is not stored as ``Char.face``. The
        # runner's equivalent sets ``<Char>.eyes`` then re-renders via
        # ``change_face(<current face or None>, eyes=X)`` using
        # ``getattr(Char, "face", None)`` as a defensive read. Mirror
        # that here: the ``getattr`` tolerates the missing attribute
        # and ``change_face(None, eyes=...)`` still refreshes the
        # sprite without touching mood-driven defaults.
        lines.append(f"{indent}$ {speaker_pascal}.eyes = \"{paren.look}\"")
        lines.append(
            f"{indent}$ {speaker_pascal}.change_face("
            f"getattr({speaker_pascal}, \"face\", None), "
            f"eyes = \"{paren.look}\")",
        )
    if paren.pose:
        # TODO(compile_scenes): ``change_pose`` does not exist on
        # CompanionClass. The slot is accepted by the grammar but the
        # codegen emission is a no-op with a trailing comment so the dev
        # notices on review. Wait for the mod to decide on the API.
        lines.append(
            f"{indent}# TODO(pose): {speaker_pascal} pose \"{paren.pose}\" "
            "- no change_pose API yet; set a mod-side helper.",
        )
    if paren.stage:
        direction = _stage_to_direction(paren.stage)
        if direction is None:
            lines.append(
                f"{indent}# TODO(stage): {paren.stage!r} has no "
                "add_Characters direction equivalent — adjust by hand.",
            )
        else:
            fade_value = "True" if use_fade else "False"
            lines.append(
                f"{indent}$ add_Characters({speaker_pascal}, "
                f"direction = \"{direction}\", fade = {fade_value})",
            )
    return lines


def _emit_dialogue(
    block: DialogueBlock,
    allow: Allowlists,
    indent: str,
    *,
    force_text_medium: bool = False,
) -> list[str]:
    """Render a dialogue block, honouring medium and the narrator tag.

    ``force_text_medium`` is set when the enclosing scene has
    ``Scene Type: texting`` (§11.13). In that mode every dialogue line
    is rewritten into a phone-text helper call regardless of whether the
    parenthetical carried ``(text)``.

    Speaker mapping: spoken dialogue emits ``ch_<PascalCase>`` (the TNH
    convention for the Ren'Py Character sayer, e.g.
    ``ch_JeanGrey = Character("[JeanGrey.tag]")`` in
    ``TheNullHypothesis/game/characters/JeanGrey/character.rpy:12``).
    The PascalCase form (``JeanGrey``) is the ``CompanionClass`` instance
    that owns the attributes (mood/face/outfit) and is the right target
    for ``receive_text`` / ``$ JeanGrey.change_mood(...)`` but is not a
    valid Ren'Py Sayer.
    """
    if block.speaker == "NARRATOR":
        return [f"{indent}\"{_escape_rpy_string(block.text)}\""]

    upper_to_pascal = {name.upper(): name for name in allow.characters}
    pascal = upper_to_pascal.get(block.speaker, block.speaker)
    speaker_token = f"ch_{pascal}"
    companion = pascal  # receive_text / change_* calls target the Companion.
    text = _escape_rpy_string(block.text)

    output: list[str] = []
    if block.parenthetical is not None:
        # Parenthetical prelude targets the Companion (state object), not
        # the Ren'Py Character sayer — mood/face/arms/etc. live on the
        # Companion.
        output.extend(
            _emit_parenthetical_prelude(block.parenthetical, companion, indent),
        )

    emit_as_text = force_text_medium or (
        block.parenthetical is not None and block.parenthetical.medium == "text"
    )
    if emit_as_text:
        # Phone-text medium compiles to the TNH core primitives
        # (``send_text`` when the Player is the speaker, ``receive_text``
        # otherwise).
        if companion == "Player":
            output.append(
                f"{indent}$ send_text(current_phone_Chat, \"{text}\")",
            )
        else:
            output.append(
                f"{indent}$ receive_text({companion}, \"{text}\")",
            )
        return output
    output.append(f"{indent}{speaker_token} \"{text}\"")
    return output


# Map the stages allowlist values (``stage_center`` etc.) to the plain
# direction strings ``add_Characters`` accepts (``middle``/``left``/``right``).
# add_Characters only knows about the 3 on-screen slots — writers pointing at
# stage_far_left / stage_far_right need a different helper (send_Characters to
# a location, or a specific slot reassignment); surface a TODO for those.
_STAGE_DIRECTION_MAP: dict[str, str] = {
    "stage_left": "left",
    "stage_center": "middle",
    "stage_right": "right",
}


def _stage_to_direction(stage: str) -> str | None:
    """Return the ``add_Characters`` direction matching a stage allowlist value."""
    return _STAGE_DIRECTION_MAP.get(stage)


def _emit_show(node: Show, indent: str) -> list[str]:
    """Emit ``$ add_Characters(Char, direction=...)`` + change_* calls.

    Delegates to ``_emit_parenthetical_prelude`` so the emission order
    matches the dialogue case: every state change first (outfit instant,
    then mood/face/arms/look), ``add_Characters`` last. This keeps the
    character from being visibly "dressing" after entering the stage.
    """
    attrs = node.attrs
    fade_raw = attrs.get("fade", "").lower()
    use_fade = fade_raw in ("true", "yes", "1")
    paren_like = Parenthetical(
        mood = attrs.get("mood"),
        face = attrs.get("face"),
        arms = attrs.get("arms"),
        look = attrs.get("look"),
        outfit = attrs.get("outfit"),
        left_arm = attrs.get("left_arm"),
        right_arm = attrs.get("right_arm"),
        pose = attrs.get("pose"),
        stage = attrs.get("stage"),
    )
    return _emit_parenthetical_prelude(paren_like, node.character, indent, use_fade = use_fade)


def _emit_hide(node: Hide, indent: str) -> str:
    # hide_Character is the sprite-level hide — no outfit-change
    # animation, unlike remove_Characters which calls set_Outfits.
    fade_value = "0.5" if node.fade else "False"
    return f"{indent}$ hide_Character({node.character}, fade = {fade_value})"


def _emit_fade(node: Fade, indent: str) -> str:
    # Full-screen cinematic fade via the base-game helpers: the black
    # overlay renders on the "cinematic" layer at zorder 99 (above sprites
    # and Live2D) and the global black_screen state is managed for us. This
    # is the screen-level fade, distinct from the sprite-level [[hide C fade]].
    fn = "fade_to_black" if node.to_black else "fade_in_from_black"
    return f"{indent}$ {fn}({_format_seconds(node.duration)})"


def _emit_phone_open(node: PhoneOpen, indent: str) -> str:
    """Open the phone overlay via the TNH core primitives.

    Text mode is the only form the spec §11.9 "Phone UI switch" block
    covers today. When a character is supplied, route to ``open_texts``
    (TNH ``core/mechanics/phone.rpy:41``); without a character, fall
    back to a bare ``renpy.show_screen("phone_screen")``.
    """
    if node.character is None:
        return f"{indent}$ renpy.show_screen(\"phone_screen\")"
    return f"{indent}$ open_texts({node.character})"


def _emit_phone_close(indent: str) -> str:
    return f"{indent}$ renpy.hide_screen(\"phone_screen\")"


def _emit_call_scene(node: CallScene, indent: str) -> str:
    return f"{indent}call {node.scene_id}"


def _emit_approval(node: Approval, indent: str) -> str:
    """Emit ``$ update_approval(Char, "axis", [-]magnitude)``.

    The magnitude keeps its source form (named tier or integer literal).
    A negative sign is rendered as a ``-`` prefix; positive is rendered
    bare so the line reads like the rest of the TNH codebase.
    """
    sign_prefix = "" if node.sign == "+" else "-"
    return (
        f"{indent}$ update_approval("
        f"{node.character}, "
        f'"{node.axis}", '
        f"{sign_prefix}{node.magnitude_text})"
    )


def _emit_choice(
    node: Choice,
    allow: Allowlists,
    scene_local: set[str],
    indent: str,
    ctx: CodegenContext,
    *,
    force_text_medium: bool = False,
    clean_present_on_set_scene: bool = False,
    use_cinematic_fx: bool = False,
) -> list[str]:
    """Emit a Ren'Py ``menu:`` for a ``[[choice]]`` block.

    Per-option conditions use Ren'Py's ``"text" if <cond>:`` syntax.
    Option bodies are indented one level deeper. An empty body becomes
    a ``pass`` so the lint stays clean.
    """
    lines: list[str] = [f"{indent}menu:"]
    option_indent = indent + _INDENT
    body_indent = option_indent + _INDENT
    for option in node.options:
        text = _escape_rpy_string(option.text)
        if option.condition is not None:
            cond_src = _render_expr(option.condition, scene_local, allow, ctx)
            lines.append(f"{option_indent}\"{text}\" if {cond_src}:")
        else:
            lines.append(f"{option_indent}\"{text}\":")
        option_body = _emit_body(
            option.body, allow, scene_local, body_indent, ctx,
            force_text_medium = force_text_medium,
            clean_present_on_set_scene = clean_present_on_set_scene,
            use_cinematic_fx = use_cinematic_fx,
        )
        if option_body:
            lines.extend(option_body)
        else:
            lines.append(f"{body_indent}pass")
    return lines


_CINEMATIC_FX_OVERRIDES: dict[str, str] = {
    # Base-game labels whose cinematic_ variant has a compatible
    # parameter signature (straight name prefix, same args).
    # knock_on_door is deliberately absent: cinematic_knock has
    # incompatible parameters (no times, 3rd arg is intensity).
    "bamf": "cinematic_bamf",
    "boom": "cinematic_boom",
    "bone_crack": "cinematic_bone_crack",
    "bzilll": "cinematic_bzilll",
    "clash": "cinematic_clash",
    "clang": "cinematic_clang",
    "click": "cinematic_click",
    "crack": "cinematic_crack",
    "crash": "cinematic_crash",
    "green_smack": "cinematic_green_smack",
    "kaboom": "cinematic_kaboom",
    "phone_buzz": "cinematic_phone_buzz",
    "pow": "cinematic_pow",
    "roar": "cinematic_roar",
    "shirk": "cinematic_shirk",
    "smack": "cinematic_smack",
    "snakt": "cinematic_snakt",
    "snikt": "cinematic_snikt",
    "zing": "cinematic_zing",
    "zirk": "cinematic_zirk",
}


def _emit_body(
    body,
    allow: Allowlists,
    scene_local: set[str],
    indent: str,
    ctx: CodegenContext,
    *,
    force_text_medium: bool = False,
    clean_present_on_set_scene: bool = False,
    use_cinematic_fx: bool = False,
) -> list[str]:
    """Emit every node in ``body`` at ``indent``; recurses into :class:`IfChain`.

    ``force_text_medium`` is threaded through nested bodies (choice
    branches, if branches) so a texting scene emits phone-text inside
    every branch, not just at the top level.

    ``clean_present_on_set_scene`` is threaded the same way: cinematic
    scenes set it so every ``set_the_scene`` (slugline mid-scene) is
    followed by a ``remove_everyone_but([], send_Offscreen = True)`` call
    that empties ``Location.Present`` (see :func:`_emit_set_scene`).

    ``use_cinematic_fx`` causes ``[[fx name()]]`` to emit the
    ``cinematic_`` prefixed label variant when one exists.
    """
    lines: list[str] = []
    for node in body:
        if isinstance(node, Slugline):
            looked_up = _strip_time_suffix(node.text)
            loc_id = _resolve_location_id(looked_up, allow)
            time_index = _time_index_for_suffix(node.text)
            lines.extend(_emit_set_scene(
                loc_id, indent,
                time_index = time_index,
                clean_present = clean_present_on_set_scene,
            ))
        elif isinstance(node, DialogueBlock):
            lines.extend(_emit_dialogue(
                node, allow, indent, force_text_medium = force_text_medium,
            ))
        elif isinstance(node, NarrationBlock):
            lines.append(f"{indent}\"{_escape_rpy_string(node.text)}\"")
        elif isinstance(node, Pause):
            lines.append(f"{indent}$ renpy.pause({_format_seconds(node.seconds)})")
        elif isinstance(node, Sfx):
            lines.append(f"{indent}$ renpy.sound.play(\"{node.name}.ogg\")")
            if node.duration is not None:
                lines.append(f"{indent}$ renpy.pause({_format_seconds(node.duration)})")
        elif isinstance(node, SetDirective):
            lines.append(
                f"{indent}$ _scene_state[{node.key!r}] = {_format_set_value(node.value)}",
            )
        elif isinstance(node, Label):
            # Local dot-label stays at the same indent as surrounding body
            # statements so Ren'Py scopes it to the enclosing scene label.
            lines.append(f"{indent}label .{node.name}:")
            # An empty block after ``label :`` is a syntax error in Ren'Py;
            # emit a ``pass`` so flow-through works when no statements follow.
            # Subsequent nodes (at same indent) will sit under the label, and
            # Ren'Py treats them as label body naturally.
            lines.append(f"{indent}{_INDENT}pass")
        elif isinstance(node, Goto):
            lines.append(f"{indent}jump .{node.name}")
        elif isinstance(node, IfChain):
            lines.extend(_emit_if_chain(
                node, allow, scene_local, indent, ctx,
                force_text_medium = force_text_medium,
                clean_present_on_set_scene = clean_present_on_set_scene,
                use_cinematic_fx = use_cinematic_fx,
            ))
        elif isinstance(node, Show):
            lines.extend(_emit_show(node, indent))
        elif isinstance(node, Hide):
            lines.append(_emit_hide(node, indent))
        elif isinstance(node, Fade):
            lines.append(_emit_fade(node, indent))
        elif isinstance(node, PhoneOpen):
            lines.append(_emit_phone_open(node, indent))
        elif isinstance(node, PhoneClose):
            lines.append(_emit_phone_close(indent))
        elif isinstance(node, CallScene):
            lines.append(_emit_call_scene(node, indent))
        elif isinstance(node, Choice):
            lines.extend(_emit_choice(
                node, allow, scene_local, indent, ctx,
                force_text_medium = force_text_medium,
                clean_present_on_set_scene = clean_present_on_set_scene,
                use_cinematic_fx = use_cinematic_fx,
            ))
        elif isinstance(node, Run):
            # The call text came straight from the writer's source and has
            # already passed the safe-subset expression parser; it's safe
            # to splice into a ``$`` Python line verbatim.
            lines.append(f"{indent}$ {node.call_text}")
        elif isinstance(node, FxCall):
            call_text = node.call_text
            is_label = allow.fx_call_modes.get(node.target_name) == "label"
            cinematic_name = _CINEMATIC_FX_OVERRIDES.get(node.target_name)
            if use_cinematic_fx and cinematic_name is not None:
                call_text = cinematic_name + call_text[len(node.target_name):]
                lines.append(f"{indent}call {call_text}")
            elif is_label:
                lines.append(f"{indent}call {call_text}")
            else:
                lines.append(f"{indent}$ {call_text}")
        elif isinstance(node, Approval):
            lines.append(_emit_approval(node, indent))
        elif isinstance(node, GiveTrait):
            lines.append(f'{indent}$ {node.character}.give_trait("{node.trait}")')
        elif isinstance(node, RemoveTrait):
            lines.append(f'{indent}$ {node.character}.remove_trait("{node.trait}")')
        elif isinstance(node, RecordEvent):
            lines.append(f'{indent}$ {node.character}.History.add("{node.event}")')
        elif isinstance(node, SetPersonality):
            lines.append(
                f'{indent}$ {node.character}.set_personality("{node.trait}", {node.value})'
            )
    return lines


def _emit_if_chain(
    chain: IfChain,
    allow: Allowlists,
    scene_local: set[str],
    indent: str,
    ctx: CodegenContext,
    *,
    force_text_medium: bool = False,
    clean_present_on_set_scene: bool = False,
    use_cinematic_fx: bool = False,
) -> list[str]:
    """Emit a nested ``if/elif/else`` block rooted at ``indent``."""
    lines: list[str] = []
    nested_indent = indent + _INDENT
    for idx, branch in enumerate(chain.branches):
        if branch.condition is None:
            lines.append(f"{indent}else:")
        else:
            keyword = "if" if idx == 0 else "elif"
            condition_src = _render_expr(branch.condition, scene_local, allow, ctx)
            lines.append(f"{indent}{keyword} {condition_src}:")
        branch_body = _emit_body(
            branch.body, allow, scene_local, nested_indent, ctx,
            force_text_medium = force_text_medium,
            clean_present_on_set_scene = clean_present_on_set_scene,
            use_cinematic_fx = use_cinematic_fx,
        )
        if branch_body:
            lines.extend(branch_body)
        else:
            # Ren'Py rejects empty suites; emit a no-op so the lint stays clean.
            lines.append(f"{nested_indent}pass")
    return lines


# --- Metadata block emission -------------------------------------------------


def _format_tuple_literal(items: list[str]) -> str:
    """Render an iterable of pre-formatted Python expressions as a tuple literal.

    Single-item tuples need the trailing comma to disambiguate from
    parenthesised expressions; the empty tuple is ``()``.
    """
    if not items:
        return "()"
    if len(items) == 1:
        return f"({items[0]},)"
    return "(" + ", ".join(items) + ")"


def _format_metadata_value(value: object) -> str:
    """Render a metadata literal as Ren'Py-compatible Python source.

    Booleans must come before ints because ``isinstance(True, int)`` is
    ``True`` in Python. Strings are double-quoted with backslash/quote
    escaping; lists are rendered recursively.
    """
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
        return f"\"{escaped}\""
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_format_metadata_value(item) for item in value) + "]"
    if isinstance(value, dict):
        items = ", ".join(
            f"\"{k}\": {_format_metadata_value(v)}" for k, v in value.items()
        )
        return "{" + items + "}"
    raise TypeError(f"Cannot serialize metadata value of type {type(value).__name__}")


def _emit_metadata_block(
    scene: Scene,
    state_specs: list[dict[str, object]],
    condition_specs: list[dict[str, object]],
    called_scenes: list[str],
    ctx: CodegenContext,
) -> list[str]:
    """Return the ``init python: {project_prefix}_scene_metadata[...] = {...}`` lines.

    The block declares one entry per compiled scene; entries from every
    compiled ``.rpy`` aggregate into the dict at boot. Removing a
    ``.scene`` removes its ``.rpy`` on the next compile, and the entry
    disappears with it — no central registry to resynchronize.

    All string literals are emitted with double quotes via
    :func:`_format_metadata_value` for visual homogeneity with the dict
    keys.
    """
    tp = scene.title_page
    lines: list[str] = ["init python:"]
    scene_id_literal = _format_metadata_value(tp.scene_id)
    lines.append(
        f"{_INDENT}{ctx.project_prefix}_scene_metadata[{scene_id_literal}] = {{",
    )
    lines.append(f"{_INDENT}{_INDENT}\"character\": {_format_metadata_value(tp.character)},")
    lines.append(f"{_INDENT}{_INDENT}\"scene_type\": {_format_metadata_value(tp.scene_type)},")
    lines.append(f"{_INDENT}{_INDENT}\"openness\": {_format_metadata_value(tp.openness or '')},")
    lines.append(f"{_INDENT}{_INDENT}\"stage_key\": {_format_metadata_value(tp.stage or '')},")
    lines.append(f"{_INDENT}{_INDENT}\"description\": {_format_metadata_value(tp.description or '')},")
    if state_specs:
        lines.append(f"{_INDENT}{_INDENT}\"state_specs\": [")
        for spec in state_specs:
            lines.append(
                f"{_INDENT}{_INDENT}{_INDENT}{_format_metadata_value(spec)},",
            )
        lines.append(f"{_INDENT}{_INDENT}],")
    else:
        lines.append(f"{_INDENT}{_INDENT}\"state_specs\": [],")
    if condition_specs:
        lines.append(f"{_INDENT}{_INDENT}\"condition_specs\": [")
        for spec in condition_specs:
            lines.append(
                f"{_INDENT}{_INDENT}{_INDENT}{_format_metadata_value(spec)},",
            )
        lines.append(f"{_INDENT}{_INDENT}],")
    else:
        lines.append(f"{_INDENT}{_INDENT}\"condition_specs\": [],")
    if called_scenes:
        lines.append(
            f"{_INDENT}{_INDENT}\"called_scenes\": "
            f"{_format_metadata_value(called_scenes)},",
        )
    else:
        lines.append(f"{_INDENT}{_INDENT}\"called_scenes\": [],")
    lines.append(f"{_INDENT}{_INDENT}\"uses_target\": False,")
    lines.append(f"{_INDENT}}}")
    return lines


# --- Public entry point ------------------------------------------------------


def generate(scene: Scene, allow: Allowlists, ctx: CodegenContext) -> str:
    """Return the ``.rpy`` text for one scene (label block only).

    Only ``cinematic`` scenes wrap the body with ``$ ongoing_Event =
    True`` / ``= False`` (§11.13) — ``phone``, ``texting``, and
    ``hub_option`` scenes are called by mod code rather than the event
    scheduler, so they skip the wrapping. Every scene type resets
    ``_scene_state`` at entry so ``[[if]]`` on bare identifiers works
    regardless of scene type.

    For ``texting`` scenes every dialogue line is forced to phone-text
    medium (§11.13) regardless of the parenthetical's explicit medium.

    The ``all_Events[...]`` entry lives in the centralised
    ``_events.rpy`` produced by :func:`generate_events_rpy`.
    """
    lines: list[str] = []

    rel_source = scene.source_path.replace("\\", "/")
    lines.append(f"# Auto-generated from {rel_source}. Do not edit by hand.")
    lines.append("")

    tp = scene.title_page

    # Testing-hub metadata — declared at module scope so the per-scene
    # entries aggregate into ``{project_prefix}_scene_metadata`` at boot.
    state_specs = _collect_state_specs(scene.body, allow)
    condition_specs = _collect_condition_specs(scene.body, allow)
    called_scenes = _collect_called_scenes(scene.body)
    lines.extend(_emit_metadata_block(
        scene, state_specs, condition_specs, called_scenes, ctx,
    ))
    lines.append("")

    # Header metadata as comments for phone scenes — the dev uses
    # Openness/Stage to wire the compiled label into the phone pool
    # registry (see {project_prefix}_register_character_dialogue).
    if tp.scene_type == "phone":
        if tp.openness:
            lines.append(f"# Openness: {tp.openness}")
        if tp.stage:
            lines.append(f"# Stage: {tp.stage}")
        if tp.openness or tp.stage:
            lines.append("")

    lines.append(f"label {tp.scene_id}:")
    if tp.scene_type == "cinematic":
        lines.append(f"{_INDENT}$ ongoing_Event = True")
    # Seed scene-local state from the testing-hub override channel.
    # ``{project_prefix}_runtime`` is a standalone Python module
    # imported by the dispatch shim; module globals live outside the
    # Ren'Py store, so the value survives the
    # ``invoke_in_new_context`` boundary the hub uses to play preview
    # scenes (store-vars and ``config`` attributes both proved
    # insufficient). In normal gameplay the override is ``None`` so the
    # dict comes out empty and behaviour matches the old
    # ``_scene_state = {}``.
    lines.append(
        f"{_INDENT}$ _scene_state = "
        f"dict(getattr({ctx.project_prefix}_runtime, 'scene_state', None) or {{}})",
    )

    is_cinematic = tp.scene_type in ("cinematic", "visual_test")
    first_slugline = next(
        (node for node in scene.body if isinstance(node, Slugline)),
        None,
    )
    if first_slugline is None and tp.location:
        looked_up = _strip_time_suffix(tp.location)
        loc_id = _resolve_location_id(looked_up, allow)
        time_index = _time_index_for_suffix(tp.location)
        lines.append("")
        lines.extend(_emit_set_scene(
            loc_id, _INDENT,
            time_index = time_index,
            clean_present = is_cinematic,
        ))

    lines.append("")
    scene_local = _collect_scene_local_keys(scene.body)
    force_text_medium = tp.scene_type == "texting"
    lines.extend(_emit_body(
        scene.body, allow, scene_local, _INDENT, ctx,
        force_text_medium = force_text_medium,
        clean_present_on_set_scene = is_cinematic,
        use_cinematic_fx = tp.scene_type == "cinematic",
    ))

    lines.append("")
    if is_cinematic:
        # Drop every non-Party character before ``ongoing_Event = False``
        # so gameplay resumes on a clean location. ``set_the_scene``
        # with ``show_Characters = False`` and ``silent = True`` calls
        # ``hide_Character`` for every off-Party char without the
        # outfit-change animation that ``remove_Characters`` triggers
        # via ``set_Outfits(instant=False)`` — that animation looked
        # like the character "re-dressing before disappearing".
        lines.append(
            f"{_INDENT}$ set_the_scene(show_Characters = False, silent = True)",
        )
        lines.append(f"{_INDENT}$ ongoing_Event = False")
    lines.append(f"{_INDENT}return")
    lines.append("")

    return "\n".join(lines)
