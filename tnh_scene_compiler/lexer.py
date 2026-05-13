"""Line-based lexer for ``.scene`` files.

The Fountain-TNH grammar is almost entirely line-oriented: every token kind
can be classified from a single line plus its predecessor/blank context. A
scanner that re-parses the raw text character by character would be
overkill. Instead we iterate lines once and emit one or more tokens per
line.

Tokens carry a 1-based ``line`` and 1-based ``col`` so error messages can
point at the exact offending position per §11.16.

Phase 6A recognises every token kind but delegates rejection of
parentheticals, directives and other unsupported-in-6A constructs to the
parser — the lexer's job is classification, not policy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class TokenKind(StrEnum):
    """Every line-level token kind the parser may encounter."""

    TITLE_KEY = "TITLE_KEY"           # ``Key: value`` line in the title page
    TITLE_END = "TITLE_END"           # Blank line closing the title page
    COMMENT = "COMMENT"               # Body line starting with ``#``
    BLANK = "BLANK"                   # Body blank line (block separator)
    SLUGLINE = "SLUGLINE"             # ``INT. …`` / ``EXT. …`` / ``INT./EXT. …``
    SPEAKER = "SPEAKER"               # UPPERCASE speaker tag on its own line
    PARENTHETICAL = "PARENTHETICAL"   # Standalone ``(...)`` line after a speaker
    DIRECTIVE = "DIRECTIVE"           # ``[[...]]`` line
    OPTION = "OPTION"                 # ``= Option text`` line inside a [[choice]] block
    PROSE = "PROSE"                   # Any other non-empty line (dialogue body or narration)
    EOF = "EOF"                       # Synthetic end-of-stream token


@dataclass(frozen=True, slots=True)
class Token:
    """One lexer token.

    Attributes:
        kind: Token kind.
        value: Raw source text of the line, trailing ``\\n`` stripped. For
            ``TITLE_KEY`` the value is the full line including the key — the
            parser splits key/value itself so errors can point back at the
            exact column.
        line: 1-based line number.
        col: 1-based column where the meaningful content starts (after any
            leading whitespace). For blank lines, ``col`` is 1.
    """

    kind: TokenKind
    value: str
    line: int
    col: int


# Matchers. All are compiled once at import time.
_RE_BLANK = re.compile(r"^\s*$")
_RE_COMMENT = re.compile(r"^\s*#.*$")
_RE_DIRECTIVE = re.compile(r"^\s*\[\[.*\]\]\s*$")
# Sluglines: `INT.`, `EXT.`, `INT./EXT.`, `I/E.` then a space and something.
_RE_SLUGLINE = re.compile(r"^\s*(INT\.\s|EXT\.\s|INT\./EXT\.\s|I/E\.\s)")
# Title-page key: leading identifier-ish text, a colon, then value. The key
# cannot contain whitespace in the middle (``Scene Id`` is allowed because
# the colon anchors the split). We use a lenient match and validate the key
# shape in the parser.
_RE_TITLE_KEY = re.compile(r"^([A-Za-z][A-Za-z0-9 _-]*?):\s*(.*)$")
# Speaker line: only uppercase letters, digits, underscore; must start with a
# letter. Captures an optional trailing ``(...)`` inline parenthetical so the
# lexer can emit two tokens (SPEAKER then PARENTHETICAL) on the same source
# line per §11.4 "Parenthetical ... follows the speaker on the same line".
_RE_SPEAKER = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*(\(.*\))?\s*$")
_RE_PARENTHETICAL = re.compile(r"^\s*\(.*\)\s*$")
# Option line inside a [[choice]] block: starts with '=' (not '==') followed by
# at least one space and option text. The parser enforces that OPTION tokens
# only appear between [[choice]] and [[/choice]] — here we just classify.
_RE_OPTION = re.compile(r"^\s*=\s+(.+)$")


def _leading_col(line: str) -> int:
    """Return the 1-based column of the first non-space character on ``line``."""
    stripped = line.lstrip()
    if not stripped:
        return 1
    return len(line) - len(stripped) + 1


def tokenize(text: str) -> list[Token]:
    """Convert raw ``.scene`` source text into a list of :class:`Token`.

    The lexer splits the file into two regions:

    * Title page — every non-blank line until the first fully blank line.
      Lines in this region are emitted as ``TITLE_KEY`` tokens.
    * Body — everything after. Lines are classified as ``SLUGLINE``,
      ``DIRECTIVE``, ``PARENTHETICAL``, ``SPEAKER``, ``COMMENT``,
      ``BLANK``, or ``PROSE``.

    A single ``TITLE_END`` token marks the transition. The stream always
    ends with an ``EOF`` token to simplify the parser's look-ahead.

    Line endings are normalised to ``\\n`` before splitting so ``CRLF`` files
    don't introduce spurious whitespace at column 0.
    """
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalised.split("\n")
    tokens: list[Token] = []

    in_title_page = True
    # Lexer never inspects more than the current line, so a single-pass loop
    # with an index suffices. ``line_no`` is 1-based for user-facing errors.
    for idx, raw in enumerate(lines):
        line_no = idx + 1
        col = _leading_col(raw)

        if in_title_page:
            if _RE_BLANK.match(raw):
                tokens.append(Token(TokenKind.TITLE_END, "", line_no, 1))
                in_title_page = False
                continue
            # Any non-blank line in the title page is a TITLE_KEY candidate.
            # The parser validates the shape and raises if the ``:`` is missing.
            tokens.append(Token(TokenKind.TITLE_KEY, raw, line_no, col))
            continue

        # Body region from here.
        if _RE_BLANK.match(raw):
            tokens.append(Token(TokenKind.BLANK, "", line_no, 1))
            continue
        if _RE_COMMENT.match(raw):
            tokens.append(Token(TokenKind.COMMENT, raw.lstrip(), line_no, col))
            continue
        if _RE_DIRECTIVE.match(raw):
            tokens.append(Token(TokenKind.DIRECTIVE, raw.strip(), line_no, col))
            continue
        if _RE_SLUGLINE.match(raw):
            tokens.append(Token(TokenKind.SLUGLINE, raw.strip(), line_no, col))
            continue
        if _RE_PARENTHETICAL.match(raw):
            tokens.append(Token(TokenKind.PARENTHETICAL, raw.strip(), line_no, col))
            continue
        # OPTION must be checked before SPEAKER so ``= TEXT`` doesn't
        # accidentally classify as prose just because the rest of the line
        # is mixed case.
        option_match = _RE_OPTION.match(raw)
        if option_match:
            tokens.append(Token(TokenKind.OPTION, raw.strip(), line_no, col))
            continue
        speaker_match = _RE_SPEAKER.match(raw)
        if speaker_match:
            # Emit SPEAKER, and optionally an immediately-following
            # PARENTHETICAL on the same source line when the inline form
            # ``SPEAKER (...)`` was used.
            speaker_name = speaker_match.group(1)
            tokens.append(Token(TokenKind.SPEAKER, speaker_name, line_no, col))
            inline_paren = speaker_match.group(2)
            if inline_paren:
                # The column where ``(`` begins.
                paren_col = raw.find("(") + 1
                tokens.append(Token(
                    TokenKind.PARENTHETICAL, inline_paren.strip(), line_no, paren_col,
                ))
            continue
        tokens.append(Token(TokenKind.PROSE, raw.rstrip(), line_no, col))

    # ``EOF`` on a synthetic trailing line so look-ahead at end-of-stream
    # always finds a token rather than IndexError.
    tokens.append(Token(TokenKind.EOF, "", len(lines) + 1, 1))
    return tokens
