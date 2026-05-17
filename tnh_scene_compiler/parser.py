"""Token stream -> :class:`Scene` AST.

The parser is structured as a single-pass recursive-descent over the token
list. It produces ONE :class:`CompileError` per mistake rather than a
cascade — a badly formed title page does not cause a shower of follow-on
body errors. When parsing cannot continue, the parser raises immediately.

Phase 6A rejects parentheticals and directives with a blocking error that
tells the writer the feature is coming. The classification lives in the
lexer; the parser only carries the refusal policy.
"""

from __future__ import annotations

from .ast_nodes import (
    Choice,
    ChoiceOption,
    DialogueBlock,
    IfBranch,
    IfChain,
    NarrationBlock,
    Scene,
    Slugline,
    TitlePage,
)
from .directive_parser import parse_directive
from .errors import CompileError
from .expr_parser import parse_expression
from .lexer import Token, TokenKind, tokenize
from .paren_parser import parse_parenthetical

# Every key the title page may carry. Unknown keys raise per §11.3.
_TITLE_KEYS: frozenset[str] = frozenset({
    "Title",
    "Scene Id",
    "Character",
    "Scene Type",
    "Trigger",
    "Description",
    "Conditions",
    "Priority",
    "Repeatable",
    "Tags",
    "Location",
    "Format",
    # Phone-specific keys from §11.13 — accepted here so phone scenes fail at
    # the Scene Type check (which is informative) rather than at the unknown-
    # key check (which would be misleading).
    "Openness",
    "Stage",
})

_REQUIRED_KEYS: frozenset[str] = frozenset({"Title", "Scene Id", "Character", "Scene Type"})

_SCENE_TYPES: frozenset[str] = frozenset({"cinematic", "phone", "texting", "hub_option", "visual_test"})

# Triggers allowed by §11.3. ``custom`` mod-prefixed flags are also legal
# but we cannot know the mod prefix at parse time — the validator is the
# one that cross-checks against mod conventions. Here we only require that
# the value is a non-empty identifier-ish token.
_KNOWN_TRIGGERS: frozenset[str] = frozenset({
    "manual", "sleeping", "waking", "traveling", "getting_ready_for_bed",
})


def _parse_bool(raw: str, path: str, line: int, col: int) -> bool:
    """Convert ``"true"``/``"false"`` (case-insensitive) to a bool."""
    value = raw.strip().lower()
    if value in ("true", "yes"):
        return True
    if value in ("false", "no"):
        return False
    raise CompileError(
        path = path,
        line = line,
        col = col,
        message = f"Expected a boolean (true/false), got {raw!r}.",
    )


def _parse_int(raw: str, path: str, line: int, col: int, *, field: str) -> int:
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise CompileError(
            path = path,
            line = line,
            col = col,
            message = f"Title page field {field!r} must be an integer, got {raw!r}.",
        ) from exc


def _split_title_line(token: Token, path: str) -> tuple[str, str]:
    """Split a TITLE_KEY line into ``(key, value)``.

    Raises :class:`CompileError` when the line is missing the ``:``
    separator — a common paste-from-Word failure mode worth a clear
    message.
    """
    raw = token.value.rstrip()
    if ":" not in raw:
        raise CompileError(
            path = path,
            line = token.line,
            col = token.col,
            message = (
                "Title page line is missing a ':' separator. "
                "Expected 'Key: value'."
            ),
        )
    key, _, value = raw.partition(":")
    return key.strip(), value.strip()


def _build_title_page(
    fields: dict[str, tuple[str, int, int]],
    path: str,
) -> TitlePage:
    """Assemble a :class:`TitlePage` from the parsed fields dict.

    Checks required keys, unknown keys, and per-field types. Trigger is
    mandatory when ``Scene Type`` is ``cinematic`` per §11.3. For every
    other scene type a missing ``Trigger`` defaults to ``manual``.
    """
    # Required-key check.
    missing = sorted(_REQUIRED_KEYS - fields.keys())
    if missing:
        first = missing[0]
        raise CompileError(
            path = path,
            line = 1,
            col = 1,
            message = f"Title page is missing required field {first!r}.",
        )

    # Scene type validation.
    scene_type_raw, st_line, st_col = fields["Scene Type"]
    scene_type = scene_type_raw.strip()
    if scene_type not in _SCENE_TYPES:
        raise CompileError(
            path = path,
            line = st_line,
            col = st_col,
            message = (
                f"Unknown scene type {scene_type!r}. "
                f"Expected one of: {', '.join(sorted(_SCENE_TYPES))}."
            ),
        )

    # Trigger handling.
    trigger: str | None = None
    if "Trigger" in fields:
        trig_raw, trig_line, trig_col = fields["Trigger"]
        trig = trig_raw.strip()
        if not trig:
            raise CompileError(
                path = path,
                line = trig_line,
                col = trig_col,
                message = "Trigger value is empty.",
            )
        trigger = trig
    elif scene_type == "cinematic":
        raise CompileError(
            path = path,
            line = st_line,
            col = st_col,
            message = (
                "Cinematic scenes require a 'Trigger' title-page field. "
                "Examples: manual, sleeping, waking."
            ),
        )
    else:
        trigger = "manual"

    # Optional fields.
    def field_or_none(name: str) -> str | None:
        return fields[name][0].strip() if name in fields else None

    description = field_or_none("Description")
    conditions = field_or_none("Conditions")
    location = field_or_none("Location")

    priority: int | None = None
    if "Priority" in fields:
        raw, line, col = fields["Priority"]
        priority = _parse_int(raw, path, line, col, field = "Priority")

    repeatable: bool | None = None
    if "Repeatable" in fields:
        raw, line, col = fields["Repeatable"]
        repeatable = _parse_bool(raw, path, line, col)

    format_version: int | None = None
    if "Format" in fields:
        raw, line, col = fields["Format"]
        format_version = _parse_int(raw, path, line, col, field = "Format")

    tags: tuple[str, ...] = ()
    if "Tags" in fields:
        raw, _, _ = fields["Tags"]
        tags = tuple(tag.strip() for tag in raw.split(",") if tag.strip())

    # Phone/texting-specific title-page keys. Shape validation happens here
    # (non-empty string); the scene-type-specific "required" check lives in
    # the validator since a missing ``Openness`` is only a problem when the
    # scene type is ``phone``.
    openness = fields["Openness"][0].strip() if "Openness" in fields else None
    stage = fields["Stage"][0].strip() if "Stage" in fields else None

    # Extract title/scene_id/character early so we can store them as plain str.
    title_val = fields["Title"][0].strip()
    scene_id_val = fields["Scene Id"][0].strip()
    character_val = fields["Character"][0].strip()

    if trigger is not None and scene_type == "cinematic" and trigger not in _KNOWN_TRIGGERS:
        # Custom mod-prefixed triggers are allowed, but bare identifiers look
        # like typos. We stay permissive here; the validator may tighten this
        # against per-mod conventions.
        pass

    return TitlePage(
        title = title_val,
        scene_id = scene_id_val,
        character = character_val,
        scene_type = scene_type,
        trigger = trigger,
        description = description,
        conditions = conditions,
        priority = priority,
        repeatable = repeatable,
        tags = tags,
        location = location,
        format_version = format_version,
        openness = openness,
        stage = stage,
    )


def _parse_title_page(
    tokens: list[Token],
    cursor: int,
    path: str,
) -> tuple[TitlePage, int]:
    """Consume every TITLE_KEY token until TITLE_END.

    Returns ``(title_page, new_cursor)`` where ``new_cursor`` points at the
    token AFTER ``TITLE_END``.
    """
    fields: dict[str, tuple[str, int, int]] = {}

    while tokens[cursor].kind == TokenKind.TITLE_KEY:
        token = tokens[cursor]
        key, value = _split_title_line(token, path)
        if key not in _TITLE_KEYS:
            raise CompileError(
                path = path,
                line = token.line,
                col = token.col,
                message = (
                    f"Unknown title-page key {key!r}. "
                    f"Valid keys: {', '.join(sorted(_TITLE_KEYS))}."
                ),
            )
        if key in fields:
            raise CompileError(
                path = path,
                line = token.line,
                col = token.col,
                message = f"Title-page key {key!r} is set twice.",
            )
        fields[key] = (value, token.line, token.col)
        cursor += 1

    # The stream is guaranteed to contain a TITLE_END (possibly synthesised
    # by the lexer at EOF if the file ends without a blank line). Tolerate
    # a TITLE_KEY-free title page as a degenerate error worth its own message.
    if not fields:
        token = tokens[cursor]
        raise CompileError(
            path = path,
            line = token.line,
            col = token.col,
            message = (
                "Title page is empty. Expected "
                "'Title', 'Scene Id', 'Character', 'Scene Type'."
            ),
        )

    if tokens[cursor].kind == TokenKind.TITLE_END:
        cursor += 1
    return _build_title_page(fields, path), cursor


def _parse_dialogue_block(
    tokens: list[Token],
    cursor: int,
    path: str,
) -> tuple[DialogueBlock, int]:
    """Consume SPEAKER [+ optional PARENTHETICAL] + PROSE lines until BLANK/EOF.

    Phase 6B supports both the inline ``SPEAKER (mood)`` form (the lexer
    emits SPEAKER + PARENTHETICAL on the same source line) and the
    multiline form where the parenthetical sits on the line after the
    speaker. COMMENT lines between the speaker and the dialogue body are
    silently skipped §11.3.
    """
    speaker_token = tokens[cursor]
    cursor += 1

    parenthetical = None
    # Accept an immediate PARENTHETICAL (same line or the line below).
    # Skip COMMENT tokens that may sit between speaker and parenthetical.
    while tokens[cursor].kind == TokenKind.COMMENT:
        cursor += 1
    if tokens[cursor].kind == TokenKind.PARENTHETICAL:
        paren_token = tokens[cursor]
        parenthetical = parse_parenthetical(
            paren_token.value,
            path = path,
            line = paren_token.line,
            col = paren_token.col,
        )
        cursor += 1
        while tokens[cursor].kind == TokenKind.COMMENT:
            cursor += 1

    # Gather PROSE lines until BLANK or EOF. Comments inside the body are
    # stripped per §11.3.
    prose_parts: list[str] = []
    while tokens[cursor].kind in (TokenKind.PROSE, TokenKind.COMMENT):
        if tokens[cursor].kind == TokenKind.PROSE:
            prose_parts.append(tokens[cursor].value.strip())
        cursor += 1

    if not prose_parts:
        raise CompileError(
            path = path,
            line = speaker_token.line,
            col = speaker_token.col,
            message = (
                f"Speaker {speaker_token.value!r} has no dialogue text on the "
                "following line(s)."
            ),
        )

    text = " ".join(prose_parts)
    return (
        DialogueBlock(
            speaker = speaker_token.value,
            text = text,
            line = speaker_token.line,
            col = speaker_token.col,
            parenthetical = parenthetical,
        ),
        cursor,
    )


def _parse_narration_block(
    tokens: list[Token],
    cursor: int,
    path: str,
) -> tuple[NarrationBlock, int]:
    """Consume consecutive PROSE lines as a narration paragraph.

    Entry assumes the first PROSE token is at ``cursor``.
    """
    _ = path  # Unused in 6A — kept to align signature with dialogue parser.
    first = tokens[cursor]
    prose_parts: list[str] = [first.value.strip()]
    cursor += 1
    while tokens[cursor].kind == TokenKind.PROSE:
        prose_parts.append(tokens[cursor].value.strip())
        cursor += 1

    text = " ".join(prose_parts)
    return NarrationBlock(text = text, line = first.line, col = first.col), cursor


def _first_word(directive_raw: str) -> str:
    """Return the head keyword of a ``[[...]]`` directive line."""
    stripped = directive_raw.strip()
    if not (stripped.startswith("[[") and stripped.endswith("]]")):
        return ""
    body = stripped[2:-2].strip()
    if not body:
        return ""
    # Treat ``/if`` and ``/choice`` as single tokens even with trailing text.
    if body.startswith("/"):
        return body.split(None, 1)[0]
    return body.split(None, 1)[0]


def _parse_if_chain(
    tokens: list[Token],
    cursor: int,
    path: str,
) -> tuple[IfChain, int]:
    """Parse ``[[if expr]] ... [[elif expr]] ... [[else]] ... [[/if]]``.

    Branches are consumed sequentially. Nested ``[[if]]`` blocks are
    handled by the recursive call in :func:`_parse_body`.
    """
    branches: list[IfBranch] = []

    if_token = tokens[cursor]
    if_head = if_token.value.strip()[2:-2].strip()
    # Strip the leading ``if`` keyword; everything after is the expression.
    expr_source = if_head[2:].lstrip() if if_head.startswith("if") else if_head
    if not expr_source:
        raise CompileError(
            path = path,
            line = if_token.line,
            col = if_token.col,
            message = "[[if]] requires a condition expression.",
        )
    # ``base_col`` is the column of the first expression character inside
    # the directive. The directive starts at ``if_token.col`` with ``[[if`` —
    # 5 characters (``[[``, ``i``, ``f``, space) before the expression.
    condition = parse_expression(
        expr_source,
        path = path,
        line = if_token.line,
        base_col = if_token.col + 5,
    )
    cursor += 1
    body, cursor = _parse_body(
        tokens, cursor, path, terminators = {"elif", "else", "/if"},
    )
    branches.append(IfBranch(
        condition = condition, body = tuple(body),
        line = if_token.line, col = if_token.col,
    ))

    # Zero or more ``elif`` branches.
    while (
        tokens[cursor].kind == TokenKind.DIRECTIVE
        and _first_word(tokens[cursor].value) == "elif"
    ):
        elif_token = tokens[cursor]
        elif_head = elif_token.value.strip()[2:-2].strip()
        elif_expr_source = elif_head[4:].lstrip() if elif_head.startswith("elif") else elif_head
        if not elif_expr_source:
            raise CompileError(
                path = path,
                line = elif_token.line,
                col = elif_token.col,
                message = "[[elif]] requires a condition expression.",
            )
        elif_condition = parse_expression(
            elif_expr_source,
            path = path,
            line = elif_token.line,
            base_col = elif_token.col + 7,
        )
        cursor += 1
        elif_body, cursor = _parse_body(
            tokens, cursor, path, terminators = {"elif", "else", "/if"},
        )
        branches.append(IfBranch(
            condition = elif_condition, body = tuple(elif_body),
            line = elif_token.line, col = elif_token.col,
        ))

    # Optional ``else`` branch.
    if (
        tokens[cursor].kind == TokenKind.DIRECTIVE
        and _first_word(tokens[cursor].value) == "else"
    ):
        else_token = tokens[cursor]
        cursor += 1
        else_body, cursor = _parse_body(
            tokens, cursor, path, terminators = {"/if"},
        )
        branches.append(IfBranch(
            condition = None, body = tuple(else_body),
            line = else_token.line, col = else_token.col,
        ))

    # Closing [[/if]].
    if not (
        tokens[cursor].kind == TokenKind.DIRECTIVE
        and _first_word(tokens[cursor].value) == "/if"
    ):
        here = tokens[cursor]
        raise CompileError(
            path = path,
            line = here.line,
            col = here.col,
            message = "Expected [[/if]] to close the conditional block.",
        )
    cursor += 1

    return IfChain(
        branches = tuple(branches),
        line = if_token.line,
        col = if_token.col,
    ), cursor


def _parse_choice_option(
    tokens: list[Token],
    cursor: int,
    path: str,
) -> tuple[ChoiceOption, int]:
    """Consume one ``= Option text [[if cond]]?`` option and its body.

    Cursor entry: on the OPTION token. Cursor exit: on the next OPTION,
    the ``[[/choice]]`` directive, or EOF.
    """
    option_token = tokens[cursor]
    raw = option_token.value
    # Strip the leading ``=`` and any whitespace.
    without_eq = raw.lstrip()[1:].lstrip()
    # Trailing [[if <cond>]] carved off if present.
    text_part = without_eq
    condition = None
    marker = "[[if "
    idx = text_part.rfind(marker)
    if idx != -1 and text_part.rstrip().endswith("]]"):
        head = text_part[:idx].rstrip()
        cond_src = text_part[idx + len(marker):].rstrip()
        # Strip the trailing ``]]``.
        if cond_src.endswith("]]"):
            cond_src = cond_src[:-2].rstrip()
        if not cond_src:
            raise CompileError(
                path = path,
                line = option_token.line,
                col = option_token.col,
                message = "Option '[[if ...]]' clause has no expression.",
            )
        condition = parse_expression(
            cond_src,
            path = path,
            line = option_token.line,
            base_col = option_token.col + idx + len(marker),
        )
        text_part = head

    option_text = text_part.strip()
    if not option_text:
        raise CompileError(
            path = path,
            line = option_token.line,
            col = option_token.col,
            message = "Option text is empty.",
        )
    cursor += 1

    body, cursor = _parse_body(
        tokens, cursor, path,
        terminators = {"/choice"},
        stop_on_option = True,
    )
    return (
        ChoiceOption(
            text = option_text,
            condition = condition,
            body = tuple(body),
            line = option_token.line,
            col = option_token.col,
        ),
        cursor,
    )


def _parse_choice(
    tokens: list[Token],
    cursor: int,
    path: str,
) -> tuple[Choice, int]:
    """Parse ``[[choice]]`` ... ``[[/choice]]`` with one or more options."""
    choice_token = tokens[cursor]
    cursor += 1
    options: list[ChoiceOption] = []

    # Skip blanks/comments between [[choice]] and the first OPTION.
    while tokens[cursor].kind in (TokenKind.BLANK, TokenKind.COMMENT):
        cursor += 1

    while tokens[cursor].kind == TokenKind.OPTION:
        option, cursor = _parse_choice_option(tokens, cursor, path)
        options.append(option)

    if not (
        tokens[cursor].kind == TokenKind.DIRECTIVE
        and _first_word(tokens[cursor].value) == "/choice"
    ):
        here = tokens[cursor]
        raise CompileError(
            path = path,
            line = here.line,
            col = here.col,
            message = "Expected [[/choice]] to close the choice block.",
        )
    cursor += 1

    if not options:
        raise CompileError(
            path = path,
            line = choice_token.line,
            col = choice_token.col,
            message = "[[choice]] block has no '=' options.",
        )

    return Choice(
        options = tuple(options),
        line = choice_token.line,
        col = choice_token.col,
    ), cursor


def _parse_body(
    tokens: list[Token],
    cursor: int,
    path: str,
    *,
    terminators: set[str] = frozenset(),
    stop_on_option: bool = False,
) -> tuple[list, int]:
    """Consume body tokens until EOF or a terminator directive is reached.

    ``terminators`` is a set of directive head keywords that stop the
    loop without being consumed — e.g. ``{"elif", "else", "/if"}`` for the
    body of an ``if`` branch. The outermost :func:`parse` call uses an
    empty set so only EOF terminates.
    """
    body: list = []
    while tokens[cursor].kind != TokenKind.EOF:
        kind = tokens[cursor].kind

        if kind in (TokenKind.BLANK, TokenKind.COMMENT):
            cursor += 1
            continue

        if kind == TokenKind.OPTION:
            if stop_on_option:
                return body, cursor
            here = tokens[cursor]
            raise CompileError(
                path = path,
                line = here.line,
                col = here.col,
                message = (
                    "Option line (starting with '=') is only valid inside a "
                    "[[choice]] block."
                ),
            )

        if kind == TokenKind.DIRECTIVE:
            head = _first_word(tokens[cursor].value)
            if head in terminators:
                return body, cursor
            if head == "if":
                chain, cursor = _parse_if_chain(tokens, cursor, path)
                body.append(chain)
                continue
            if head == "choice":
                choice, cursor = _parse_choice(tokens, cursor, path)
                body.append(choice)
                continue
            if head in ("elif", "else", "/if"):
                # These must have been caught by the surrounding
                # ``_parse_if_chain``; seeing them at top level is an error.
                here = tokens[cursor]
                raise CompileError(
                    path = path,
                    line = here.line,
                    col = here.col,
                    message = (
                        f"Unexpected [[{head}]] — not inside an open "
                        "[[if]] block."
                    ),
                )
            if head == "/choice":
                here = tokens[cursor]
                raise CompileError(
                    path = path,
                    line = here.line,
                    col = here.col,
                    message = (
                        "Unexpected [[/choice]] — not inside an open "
                        "[[choice]] block."
                    ),
                )
            directive_token = tokens[cursor]
            node = parse_directive(
                directive_token.value,
                path = path,
                line = directive_token.line,
                col = directive_token.col,
            )
            body.append(node)
            cursor += 1
            continue

        if kind == TokenKind.SLUGLINE:
            slug_token = tokens[cursor]
            raw = slug_token.value
            prefix, _, text_rest = raw.partition(" ")
            body.append(Slugline(
                prefix = prefix.rstrip(),
                text = text_rest.strip(),
                line = slug_token.line,
                col = slug_token.col,
            ))
            cursor += 1
            continue

        if kind == TokenKind.SPEAKER:
            block, cursor = _parse_dialogue_block(tokens, cursor, path)
            body.append(block)
            continue

        if kind == TokenKind.PROSE:
            block, cursor = _parse_narration_block(tokens, cursor, path)
            body.append(block)
            continue

        if kind == TokenKind.PARENTHETICAL:
            paren = tokens[cursor]
            raise CompileError(
                path = path,
                line = paren.line,
                col = paren.col,
                message = (
                    "Stray parenthetical on its own — parentheticals only "
                    "follow a speaker line."
                ),
            )

        unexpected = tokens[cursor]
        raise CompileError(
            path = path,
            line = unexpected.line,
            col = unexpected.col,
            message = f"Unexpected token {unexpected.kind.value!r} in scene body.",
        )

    if terminators:
        here = tokens[cursor]
        expected = ", ".join(sorted(f"[[{t}]]" for t in terminators))
        raise CompileError(
            path = path,
            line = here.line,
            col = here.col,
            message = f"Unexpected end of file; expected one of {expected}.",
        )

    return body, cursor


def parse(text: str, *, path: str) -> Scene:
    """Parse ``.scene`` source text into a :class:`Scene`.

    ``path`` is preserved on every error so the CLI can emit
    ``path:line:col: message`` output.
    """
    tokens = tokenize(text)
    cursor = 0
    title_page, cursor = _parse_title_page(tokens, cursor, path)
    body, _ = _parse_body(tokens, cursor, path)
    return Scene(source_path = path, title_page = title_page, body = tuple(body))
