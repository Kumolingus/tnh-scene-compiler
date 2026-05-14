"""Parse ``[[...]]`` directive lines into concrete AST nodes.

Phases 6B-3 and 6C cover most single-line directives: ``pause``, ``sfx``,
``set``, ``label``, ``goto``, ``call``, ``phone``, ``show``, ``hide``.
``if`` / ``elif`` / ``else`` / ``/if`` and ``choice`` / ``/choice`` stay
in the main parser because they nest or carry option lines.

Every function raises :class:`CompileError` on malformed input with an
anchored ``line:col`` so the writer sees exactly where the problem is.
"""

from __future__ import annotations

import re

from .ast_nodes import (
    Approval,
    CallScene,
    FxCall,
    GiveTrait,
    Goto,
    Hide,
    Label,
    RecordEvent,
    RemoveTrait,
    Run,
    Pause,
    PhoneClose,
    PhoneOpen,
    SetDirective,
    SetPersonality,
    Sfx,
    Show,
)
from .errors import CompileError
from .expr_parser import Attribute, Call, Name, parse_expression

# Identifier shape reused across several directives (label/goto/set key).
_RE_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# [[approval]] grammar pieces — kept module-level so the parser, validator,
# and tests share a single source of truth for the closed enums.
_RE_APPROVAL_SIGNED = re.compile(r"^([+\-])(.+)$")
_APPROVAL_AXES: tuple[str, ...] = ("love", "trust")
_APPROVAL_STAT_TIERS: tuple[str, ...] = (
    "tiny_stat", "small_stat", "medium_stat", "large_stat", "massive_stat",
)


def _strip_directive(raw: str) -> str:
    """Return the inner body of a ``[[...]]`` line (stripped)."""
    stripped = raw.strip()
    if not (stripped.startswith("[[") and stripped.endswith("]]")):
        raise ValueError(f"not a directive: {raw!r}")
    return stripped[2:-2].strip()


def parse_pause(raw: str, *, path: str, line: int, col: int) -> Pause:
    body = _strip_directive(raw)
    parts = body.split(None, 1)
    if len(parts) != 2 or parts[0] != "pause":
        raise CompileError(
            path = path, line = line, col = col,
            message = "Malformed [[pause]] directive. Expected '[[pause N]]'.",
        )
    arg = parts[1].strip()
    try:
        seconds = float(arg)
    except ValueError as exc:
        raise CompileError(
            path = path, line = line, col = col,
            message = f"Pause duration {arg!r} is not a number.",
        ) from exc
    if seconds < 0:
        raise CompileError(
            path = path, line = line, col = col,
            message = "Pause duration must be non-negative.",
        )
    return Pause(seconds = seconds, line = line, col = col)


def parse_sfx(raw: str, *, path: str, line: int, col: int) -> Sfx:
    body = _strip_directive(raw)
    parts = body.split()
    if len(parts) < 2 or parts[0] != "sfx":
        raise CompileError(
            path = path, line = line, col = col,
            message = "Malformed [[sfx]] directive. Expected '[[sfx name]]' or '[[sfx name N]]'.",
        )
    name = parts[1]
    if not _RE_IDENT.match(name):
        raise CompileError(
            path = path, line = line, col = col,
            message = f"SFX name {name!r} is not a plain identifier.",
        )
    duration: float | None = None
    if len(parts) == 3:
        try:
            duration = float(parts[2])
        except ValueError as exc:
            raise CompileError(
                path = path, line = line, col = col,
                message = f"SFX duration {parts[2]!r} is not a number.",
            ) from exc
    elif len(parts) > 3:
        raise CompileError(
            path = path, line = line, col = col,
            message = "[[sfx]] accepts at most two arguments: name and optional duration.",
        )
    return Sfx(name = name, duration = duration, line = line, col = col)


def _parse_set_value(raw: str) -> bool | int | float | str:
    """Parse the right-hand side of ``[[set key = value]]``.

    Only literals are accepted (bool, int, float, string). Any other
    construct is rejected by the caller via :class:`CompileError`.
    """
    text = raw.strip()
    low = text.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    # String literal.
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("\"", "'"):
        return text[1:-1]
    # Numeric.
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    raise ValueError(text)


def parse_set(raw: str, *, path: str, line: int, col: int) -> SetDirective:
    body = _strip_directive(raw)
    if not body.startswith("set"):
        raise CompileError(
            path = path, line = line, col = col,
            message = "Malformed [[set]] directive.",
        )
    remainder = body[3:].strip()
    if not remainder:
        raise CompileError(
            path = path, line = line, col = col,
            message = "[[set]] requires a key name.",
        )

    if "=" in remainder:
        key_raw, _, value_raw = remainder.partition("=")
        key = key_raw.strip()
        # Dotted keys first — writers who tried to target a character attribute
        # get pointed at [[run]] rather than a generic "not an identifier"
        # error they'd struggle to act on.
        if "." in key:
            raise CompileError(
                path = path, line = line, col = col,
                message = (
                    "[[set]] targets scene-local state only. "
                    "To write to a character attribute, use [[run]]."
                ),
            )
        if not _RE_IDENT.match(key):
            raise CompileError(
                path = path, line = line, col = col,
                message = (
                    f"Set key {key!r} is not a plain identifier. "
                    "Use a snake_case name."
                ),
            )
        try:
            value = _parse_set_value(value_raw)
        except ValueError as exc:
            raise CompileError(
                path = path, line = line, col = col,
                message = (
                    f"Value {value_raw.strip()!r} is not a literal. [[set]] only "
                    "accepts true, false, integers, floats, and quoted strings."
                ),
            ) from exc
        return SetDirective(key = key, value = value, line = line, col = col)

    # Bare form: [[set key]] sets the key to True.
    if not _RE_IDENT.match(remainder):
        raise CompileError(
            path = path, line = line, col = col,
            message = (
                f"Set key {remainder!r} is not a plain identifier. "
                "Use a snake_case name."
            ),
        )
    if "." in remainder:
        raise CompileError(
            path = path, line = line, col = col,
            message = (
                "[[set]] targets scene-local state only. "
                "To write to a character attribute, use [[run]]."
            ),
        )
    return SetDirective(key = remainder, value = True, line = line, col = col)


def parse_label(raw: str, *, path: str, line: int, col: int) -> Label:
    body = _strip_directive(raw)
    parts = body.split()
    if len(parts) != 2 or parts[0] != "label":
        raise CompileError(
            path = path, line = line, col = col,
            message = "Malformed [[label]] directive. Expected '[[label name]]'.",
        )
    name = parts[1]
    if not _RE_IDENT.match(name):
        raise CompileError(
            path = path, line = line, col = col,
            message = f"Label name {name!r} is not a plain identifier.",
        )
    return Label(name = name, line = line, col = col)


def parse_goto(raw: str, *, path: str, line: int, col: int) -> Goto:
    body = _strip_directive(raw)
    parts = body.split()
    if len(parts) != 2 or parts[0] != "goto":
        raise CompileError(
            path = path, line = line, col = col,
            message = "Malformed [[goto]] directive. Expected '[[goto name]]'.",
        )
    name = parts[1]
    if not _RE_IDENT.match(name):
        raise CompileError(
            path = path, line = line, col = col,
            message = f"Goto target {name!r} is not a plain identifier.",
        )
    return Goto(name = name, line = line, col = col)


def parse_call(raw: str, *, path: str, line: int, col: int) -> CallScene:
    body = _strip_directive(raw)
    parts = body.split()
    if len(parts) != 2 or parts[0] != "call":
        raise CompileError(
            path = path, line = line, col = col,
            message = "Malformed [[call]] directive. Expected '[[call scene_id]]'.",
        )
    scene_id = parts[1]
    if not _RE_IDENT.match(scene_id):
        raise CompileError(
            path = path, line = line, col = col,
            message = (
                f"Call target {scene_id!r} is not a plain identifier. "
                "Scene IDs are snake_case."
            ),
        )
    return CallScene(scene_id = scene_id, line = line, col = col)


def parse_phone(raw: str, *, path: str, line: int, col: int) -> PhoneOpen | PhoneClose:
    body = _strip_directive(raw)
    parts = body.split()
    if not parts or parts[0] != "phone":
        raise CompileError(
            path = path, line = line, col = col,
            message = "Malformed [[phone]] directive.",
        )
    if len(parts) < 2:
        raise CompileError(
            path = path, line = line, col = col,
            message = "[[phone]] requires an action: 'open', 'open <Character>', or 'close'.",
        )
    action = parts[1]
    if action == "close":
        if len(parts) != 2:
            raise CompileError(
                path = path, line = line, col = col,
                message = "[[phone close]] takes no arguments.",
            )
        return PhoneClose(line = line, col = col)
    if action == "open":
        if len(parts) == 2:
            return PhoneOpen(character = None, line = line, col = col)
        if len(parts) == 3:
            character = parts[2]
            if not _RE_IDENT.match(character):
                raise CompileError(
                    path = path, line = line, col = col,
                    message = (
                        f"Character {character!r} is not a plain identifier."
                    ),
                )
            return PhoneOpen(character = character, line = line, col = col)
        raise CompileError(
            path = path, line = line, col = col,
            message = (
                "[[phone open]] accepts at most one argument (the character)."
            ),
        )
    raise CompileError(
        path = path, line = line, col = col,
        message = (
            f"Unknown [[phone]] action {action!r}. Expected 'open' or 'close'."
        ),
    )


# Named slots §11.6 excluding ``text`` medium — used by [[show]] for argument
# validation since the directive does not carry a medium.
_SHOW_KEYS: frozenset[str] = frozenset({
    "mood", "face", "arms", "look", "outfit", "stage",
    "left_arm", "right_arm", "pose",
})


def parse_show(raw: str, *, path: str, line: int, col: int) -> Show:
    """Parse ``[[show <Character> attr=val attr=val ...]]``.

    Named-only: every argument after the character must be a ``key=value``
    pair using the §11.6 vocabulary. No positional tokens, no medium,
    no text. The validator performs per-slot allowlist checks downstream.
    """
    body = _strip_directive(raw)
    parts = body.split()
    if not parts or parts[0] != "show":
        raise CompileError(
            path = path, line = line, col = col,
            message = "Malformed [[show]] directive.",
        )
    if len(parts) < 2:
        raise CompileError(
            path = path, line = line, col = col,
            message = "[[show]] requires a character.",
        )
    character = parts[1]
    if not _RE_IDENT.match(character):
        raise CompileError(
            path = path, line = line, col = col,
            message = f"Character {character!r} is not a plain identifier.",
        )

    attrs: dict[str, str] = {}
    for tok in parts[2:]:
        if "=" not in tok:
            raise CompileError(
                path = path, line = line, col = col,
                message = (
                    f"[[show]] argument {tok!r} is not a key=value pair. "
                    "All attributes must be named."
                ),
            )
        key, _, value = tok.partition("=")
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key not in _SHOW_KEYS:
            raise CompileError(
                path = path, line = line, col = col,
                message = (
                    f"[[show]] attribute {key!r} is not valid. "
                    f"Expected one of: {', '.join(sorted(_SHOW_KEYS))}."
                ),
            )
        if not value:
            raise CompileError(
                path = path, line = line, col = col,
                message = f"[[show]] attribute {key!r} has no value.",
            )
        if key in attrs:
            raise CompileError(
                path = path, line = line, col = col,
                message = f"[[show]] attribute {key!r} is set twice.",
            )
        attrs[key] = value

    return Show(character = character, attrs = attrs, line = line, col = col)


# -- High-level state-mutation directives ------------------------------------


def parse_give_trait(raw: str, *, path: str, line: int, col: int) -> GiveTrait:
    """Parse ``[[give_trait Character trait]]``."""
    body = _strip_directive(raw)
    parts = body.split()
    if len(parts) != 3 or parts[0] != "give_trait":
        raise CompileError(
            path = path, line = line, col = col,
            message = (
                "Malformed [[give_trait]] directive. Expected "
                "'[[give_trait Character trait]]'."
            ),
        )
    _, character, trait = parts
    if not _RE_IDENT.match(character):
        raise CompileError(
            path = path, line = line, col = col,
            message = f"Character {character!r} is not a plain identifier.",
        )
    if not _RE_IDENT.match(trait):
        raise CompileError(
            path = path, line = line, col = col,
            message = f"Trait {trait!r} is not a plain identifier.",
        )
    return GiveTrait(character = character, trait = trait, line = line, col = col)


def parse_remove_trait(raw: str, *, path: str, line: int, col: int) -> RemoveTrait:
    """Parse ``[[remove_trait Character trait]]``."""
    body = _strip_directive(raw)
    parts = body.split()
    if len(parts) != 3 or parts[0] != "remove_trait":
        raise CompileError(
            path = path, line = line, col = col,
            message = (
                "Malformed [[remove_trait]] directive. Expected "
                "'[[remove_trait Character trait]]'."
            ),
        )
    _, character, trait = parts
    if not _RE_IDENT.match(character):
        raise CompileError(
            path = path, line = line, col = col,
            message = f"Character {character!r} is not a plain identifier.",
        )
    if not _RE_IDENT.match(trait):
        raise CompileError(
            path = path, line = line, col = col,
            message = f"Trait {trait!r} is not a plain identifier.",
        )
    return RemoveTrait(character = character, trait = trait, line = line, col = col)


def parse_record(raw: str, *, path: str, line: int, col: int) -> RecordEvent:
    """Parse ``[[record Character event]]``."""
    body = _strip_directive(raw)
    parts = body.split()
    if len(parts) != 3 or parts[0] != "record":
        raise CompileError(
            path = path, line = line, col = col,
            message = (
                "Malformed [[record]] directive. Expected "
                "'[[record Character event]]'."
            ),
        )
    _, character, event = parts
    if not _RE_IDENT.match(character):
        raise CompileError(
            path = path, line = line, col = col,
            message = f"Character {character!r} is not a plain identifier.",
        )
    if not _RE_IDENT.match(event):
        raise CompileError(
            path = path, line = line, col = col,
            message = f"Event {event!r} is not a plain identifier.",
        )
    return RecordEvent(character = character, event = event, line = line, col = col)


def parse_set_personality(
    raw: str, *, path: str, line: int, col: int,
) -> SetPersonality:
    """Parse ``[[set_personality Character trait value]]``."""
    body = _strip_directive(raw)
    parts = body.split()
    if len(parts) != 4 or parts[0] != "set_personality":
        raise CompileError(
            path = path, line = line, col = col,
            message = (
                "Malformed [[set_personality]] directive. Expected "
                "'[[set_personality Character trait value]]'."
            ),
        )
    _, character, trait, value_str = parts
    if not _RE_IDENT.match(character):
        raise CompileError(
            path = path, line = line, col = col,
            message = f"Character {character!r} is not a plain identifier.",
        )
    if not _RE_IDENT.match(trait):
        raise CompileError(
            path = path, line = line, col = col,
            message = f"Personality trait {trait!r} is not a plain identifier.",
        )
    try:
        value = int(value_str)
    except ValueError as exc:
        raise CompileError(
            path = path, line = line, col = col,
            message = f"Value {value_str!r} must be an integer.",
        ) from exc
    return SetPersonality(
        character = character, trait = trait, value = value,
        line = line, col = col,
    )


def parse_run(raw: str, *, path: str, line: int, col: int) -> Run:
    """Parse ``[[run <call>]]`` — a function or method invocation.

    The body is parsed with the safe-subset expression parser; the
    top-level node must be a :class:`Call`. Every construct §11.9.1
    forbids (arithmetic, subscript, ternary, …) is rejected automatically
    by the expression scanner. Validation of the target against the
    run-operations allowlist happens in the validator.
    """
    body = _strip_directive(raw)
    if not body.startswith("run"):
        raise CompileError(
            path = path, line = line, col = col,
            message = "Malformed [[run]] directive.",
        )
    remainder = body[len("run"):].strip()
    if not remainder:
        raise CompileError(
            path = path, line = line, col = col,
            message = "[[run]] requires a call expression.",
        )

    expr = parse_expression(
        remainder,
        path = path,
        line = line,
        base_col = col + len("[[run ") + 1 - 1,
    )
    if not isinstance(expr, Call):
        raise CompileError(
            path = path, line = line, col = col,
            message = (
                "[[run]] must be a function or method call. "
                "Plain values and assignments are not allowed."
            ),
        )

    target = expr.target
    if isinstance(target, Name):
        target_name = target.name
    elif isinstance(target, Attribute):
        target_name = target.parts[-1]
    else:
        raise CompileError(
            path = path, line = line, col = col,
            message = "[[run]] call target is not a plain function or method.",
        )

    return Run(
        call_text = remainder,
        target_name = target_name,
        line = line,
        col = col,
    )


def parse_fx(raw: str, *, path: str, line: int, col: int) -> FxCall:
    """Parse ``[[fx <call>]]`` — an engine-effect invocation.

    Structurally identical to ``[[run]]`` (call expression, target
    name extracted for allowlist lookup) but routed through a separate
    allowlist (``fx.yaml``) because ``fx`` is side-effect only (plays a
    visual / transient animation like ``phone_buzz()`` or
    ``knock_on_door()``) while ``run`` writes persistent state.
    Keeping the two directives apart makes a scene line's intent
    obvious.
    """
    body = _strip_directive(raw)
    if not body.startswith("fx"):
        raise CompileError(
            path = path, line = line, col = col,
            message = "Malformed [[fx]] directive.",
        )
    remainder = body[len("fx"):].strip()
    if not remainder:
        raise CompileError(
            path = path, line = line, col = col,
            message = "[[fx]] requires a call expression.",
        )

    expr = parse_expression(
        remainder,
        path = path,
        line = line,
        base_col = col + len("[[fx ") + 1 - 1,
    )
    if not isinstance(expr, Call):
        raise CompileError(
            path = path, line = line, col = col,
            message = (
                "[[fx]] must be a function or method call. "
                "Plain values and assignments are not allowed."
            ),
        )

    target = expr.target
    if isinstance(target, Name):
        target_name = target.name
    elif isinstance(target, Attribute):
        target_name = target.parts[-1]
    else:
        raise CompileError(
            path = path, line = line, col = col,
            message = "[[fx]] call target is not a plain function or method.",
        )

    return FxCall(
        call_text = remainder,
        target_name = target_name,
        line = line,
        col = col,
    )


def parse_hide(raw: str, *, path: str, line: int, col: int) -> Hide:
    body = _strip_directive(raw)
    parts = body.split()
    if len(parts) != 2 or parts[0] != "hide":
        raise CompileError(
            path = path, line = line, col = col,
            message = "Malformed [[hide]] directive. Expected '[[hide Character]]'.",
        )
    character = parts[1]
    if not _RE_IDENT.match(character):
        raise CompileError(
            path = path, line = line, col = col,
            message = f"Character {character!r} is not a plain identifier.",
        )
    return Hide(character = character, line = line, col = col)


def parse_approval(raw: str, *, path: str, line: int, col: int) -> Approval:
    """Parse ``[[approval Character axis +magnitude]]``.

    Grammar: four whitespace-separated tokens — the directive name, a
    PascalCase character identifier, the axis (``love`` / ``trust``), and
    a signed magnitude. The sign is mandatory; the magnitude is either a
    stat-tier name (``tiny_stat`` ... ``massive_stat``) or a positive
    integer literal. Allowlist validation of the character is deferred
    to the validator module.
    """
    body = _strip_directive(raw)
    parts = body.split()
    if len(parts) != 4 or parts[0] != "approval":
        raise CompileError(
            path = path, line = line, col = col,
            message = (
                "Malformed [[approval]] directive. Expected "
                "'[[approval Character axis +magnitude]]'."
            ),
        )

    _, character, axis, signed_magnitude = parts

    if not _RE_IDENT.match(character):
        raise CompileError(
            path = path, line = line, col = col,
            message = f"Character {character!r} is not a plain identifier.",
        )

    if axis not in _APPROVAL_AXES:
        raise CompileError(
            path = path, line = line, col = col,
            message = (
                f"Approval axis {axis!r} is invalid. Must be one of: "
                f"{', '.join(_APPROVAL_AXES)}."
            ),
        )

    match = _RE_APPROVAL_SIGNED.match(signed_magnitude)
    if not match:
        raise CompileError(
            path = path, line = line, col = col,
            message = (
                f"Approval magnitude {signed_magnitude!r} must start with "
                "an explicit '+' or '-' sign."
            ),
        )

    sign, magnitude_text = match.group(1), match.group(2)

    if magnitude_text not in _APPROVAL_STAT_TIERS:
        try:
            value = int(magnitude_text)
        except ValueError as exc:
            raise CompileError(
                path = path, line = line, col = col,
                message = (
                    f"Approval magnitude {magnitude_text!r} must be a stat "
                    f"tier ({', '.join(_APPROVAL_STAT_TIERS)}) or a "
                    "positive integer literal."
                ),
            ) from exc
        if value < 1:
            raise CompileError(
                path = path, line = line, col = col,
                message = (
                    "Approval magnitude integer must be >= 1; use the "
                    "leading sign to indicate direction."
                ),
            )

    return Approval(
        character = character,
        axis = axis,
        magnitude_text = magnitude_text,
        sign = sign,
        line = line,
        col = col,
    )


def parse_directive(raw: str, *, path: str, line: int, col: int):
    """Dispatch on the first word of a ``[[...]]`` body.

    Returns the matching AST node, or raises :class:`CompileError` when
    the directive name is unknown or reserved for a later phase.
    """
    body = _strip_directive(raw)
    first = body.split(None, 1)[0] if body else ""
    if first == "pause":
        return parse_pause(raw, path = path, line = line, col = col)
    if first == "sfx":
        return parse_sfx(raw, path = path, line = line, col = col)
    if first == "set":
        return parse_set(raw, path = path, line = line, col = col)
    if first == "label":
        return parse_label(raw, path = path, line = line, col = col)
    if first == "goto":
        return parse_goto(raw, path = path, line = line, col = col)
    if first == "call":
        return parse_call(raw, path = path, line = line, col = col)
    if first == "phone":
        return parse_phone(raw, path = path, line = line, col = col)
    if first == "show":
        return parse_show(raw, path = path, line = line, col = col)
    if first == "hide":
        return parse_hide(raw, path = path, line = line, col = col)
    if first == "run":
        return parse_run(raw, path = path, line = line, col = col)
    if first == "give_trait":
        return parse_give_trait(raw, path = path, line = line, col = col)
    if first == "remove_trait":
        return parse_remove_trait(raw, path = path, line = line, col = col)
    if first == "record":
        return parse_record(raw, path = path, line = line, col = col)
    if first == "set_personality":
        return parse_set_personality(raw, path = path, line = line, col = col)
    if first == "fx":
        return parse_fx(raw, path = path, line = line, col = col)
    if first == "approval":
        return parse_approval(raw, path = path, line = line, col = col)
    # [[if]] / [[elif]] / [[else]] / [[/if]] / [[choice]] / [[/choice]] are
    # handled by the main parser.
    raise CompileError(
        path = path, line = line, col = col,
        message = f"Unknown directive [[{first}]].",
    )
