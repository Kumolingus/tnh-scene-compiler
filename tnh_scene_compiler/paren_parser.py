"""Parenthetical-line sub-parser for §11.6 visual attribute grammar.

Isolated from the main body parser so its rules stay easy to read against
the spec. Takes the raw ``(...)`` text produced by the lexer, returns a
:class:`Parenthetical` AST node, or raises :class:`CompileError`.

Phase 6B-2 handles the structural grammar only — positional assignment,
named keys, ``_`` skip token, ``text`` medium — without validating the
value against per-character allowlists. That cross-lookup happens in the
validator so multiple semantic errors can be collected in one compile
pass.
"""

from __future__ import annotations

from .ast_nodes import Parenthetical
from .errors import CompileError

# Positional slots in §11.6 order. ``None`` at index 6+ is a hard cap — any
# positional token past the last slot is an error.
_POSITIONAL_SLOTS: tuple[str, ...] = ("mood", "face", "arms", "look", "outfit", "stage")

# Every legal key, including the named-only ones (``left_arm``, ``right_arm``,
# ``pose``) §11.6 "Valid keys". ``medium`` is not in the key-set — it is
# triggered by the reserved value ``text``/``spoken``.
_NAMED_KEYS: frozenset[str] = frozenset({
    "mood", "face", "arms", "look", "outfit", "stage",
    "left_arm", "right_arm", "pose",
})

# Reserved values that select the dialogue medium §11.7. ``spoken`` is the
# default and redundant; ``text`` switches to phone-text medium.
_MEDIUM_VALUES: frozenset[str] = frozenset({"text", "spoken"})

# Skip token for positional slots §11.6 "Skipping a positional slot".
_SKIP_TOKEN = "_"


def _split_tokens(body: str) -> list[str]:
    """Split a parenthetical body on commas, respecting quoted strings.

    The grammar does not actually use quoted strings — every value is a
    bare identifier — but string support is free given we already handle
    quotes in the expression parser, and it lets writers spell awkward
    values like ``face="worried 1"`` (rare, but it avoids future grief).
    """
    out: list[str] = []
    depth = 0
    quote: str | None = None
    buf: list[str] = []
    for ch in body:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("\"", "'"):
            quote = ch
            buf.append(ch)
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            continue
        if ch == ")":
            depth -= 1
            buf.append(ch)
            continue
        if ch == "," and depth == 0:
            out.append("".join(buf).strip())
            buf.clear()
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def _assign_slot(
    acc: dict[str, str],
    key: str,
    value: str,
    *,
    path: str,
    line: int,
    col: int,
    positional: bool,
    positional_locked: bool,
) -> None:
    """Assign one slot with the §11.6 error contract.

    Parameters:
        acc: Mutable mapping accumulating ``{slot_name: value}`` so far.
        key: Slot name for this assignment.
        value: Raw value string.
        path/line/col: Source position for error reporting.
        positional: Whether this token came from a positional slot. When
            ``True`` and ``positional_locked`` is also ``True``, the token
            is illegal ("positional after named").
        positional_locked: Set to ``True`` after the parser sees its first
            named ``key=value`` token, so any subsequent positional triggers
            the §11.6 "named after positional" error.
    """
    if positional and positional_locked:
        raise CompileError(
            path = path,
            line = line,
            col = col,
            message = "Positional values must come before named ones.",
        )
    if key in acc:
        raise CompileError(
            path = path,
            line = line,
            col = col,
            message = f"Slot {key!r} is already set to {acc[key]!r}.",
        )
    acc[key] = value


def parse_parenthetical(
    raw: str,
    *,
    path: str,
    line: int,
    col: int,
) -> Parenthetical:
    """Parse a parenthetical line (e.g. ``(mood=sad, face=crying)``).

    ``raw`` is the whole ``(...)`` including the parentheses. ``line`` /
    ``col`` point at the ``(`` so error messages can show the exact
    source position.
    """
    stripped = raw.strip()
    if not (stripped.startswith("(") and stripped.endswith(")")):
        raise CompileError(
            path = path,
            line = line,
            col = col,
            message = "Expected a parenthesised attribute list like '(mood=sad)'.",
        )
    body = stripped[1:-1].strip()
    if not body:
        # Empty parenthetical ``()`` is legal but useless — treat it as no-op.
        return Parenthetical(line = line, col = col)

    tokens = _split_tokens(body)

    assignments: dict[str, str] = {}
    medium: str | None = None
    positional_locked = False
    positional_index = 0

    for tok in tokens:
        # Named form.
        if "=" in tok:
            positional_locked = True
            key_raw, _, value_raw = tok.partition("=")
            key = key_raw.strip()
            value = value_raw.strip().strip("\"").strip("'")
            if key not in _NAMED_KEYS:
                raise CompileError(
                    path = path,
                    line = line,
                    col = col,
                    message = (
                        f"Unknown attribute {key!r}. Valid keys: "
                        f"{', '.join(sorted(_NAMED_KEYS))}."
                    ),
                )
            if not value:
                raise CompileError(
                    path = path,
                    line = line,
                    col = col,
                    message = f"Slot {key!r} has no value.",
                )
            _assign_slot(
                assignments, key, value,
                path = path, line = line, col = col,
                positional = False, positional_locked = positional_locked,
            )
            continue

        # Positional form.
        value = tok.strip().strip("\"").strip("'")
        if not value:
            raise CompileError(
                path = path,
                line = line,
                col = col,
                message = "Empty positional token.",
            )

        # Reserved medium values. ``text`` or ``spoken`` alone selects the
        # dialogue medium and has no positional slot index.
        if value in _MEDIUM_VALUES:
            if medium is not None:
                raise CompileError(
                    path = path,
                    line = line,
                    col = col,
                    message = f"Medium already set to {medium!r}.",
                )
            medium = value
            continue

        if value == _SKIP_TOKEN:
            positional_index += 1
            if positional_index > len(_POSITIONAL_SLOTS):
                raise CompileError(
                    path = path,
                    line = line,
                    col = col,
                    message = (
                        "Too many positional skips. "
                        f"There are only {len(_POSITIONAL_SLOTS)} positional slots."
                    ),
                )
            continue

        if positional_index >= len(_POSITIONAL_SLOTS):
            raise CompileError(
                path = path,
                line = line,
                col = col,
                message = (
                    f"Too many positional values (max {len(_POSITIONAL_SLOTS)}). "
                    f"Use named keys: {', '.join(_POSITIONAL_SLOTS)}."
                ),
            )

        slot_name = _POSITIONAL_SLOTS[positional_index]
        _assign_slot(
            assignments, slot_name, value,
            path = path, line = line, col = col,
            positional = True, positional_locked = positional_locked,
        )
        positional_index += 1

    # Medium/visual mutual exclusion §11.7.
    if medium == "text":
        visual_set = [k for k in assignments if k in _NAMED_KEYS]
        if visual_set:
            raise CompileError(
                path = path,
                line = line,
                col = col,
                message = (
                    "Medium 'text' cannot be combined with visual attributes "
                    f"({', '.join(sorted(visual_set))})."
                ),
            )

    return Parenthetical(
        mood = assignments.get("mood"),
        face = assignments.get("face"),
        arms = assignments.get("arms"),
        look = assignments.get("look"),
        outfit = assignments.get("outfit"),
        stage = assignments.get("stage"),
        left_arm = assignments.get("left_arm"),
        right_arm = assignments.get("right_arm"),
        pose = assignments.get("pose"),
        medium = medium,
        line = line,
        col = col,
    )
