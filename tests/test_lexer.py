"""Unit tests for :mod:`tnh_scene_compiler.lexer`."""

from __future__ import annotations

from tnh_scene_compiler.lexer import TokenKind, tokenize


def test_title_page_is_bounded_by_blank_line() -> None:
    text = "Title: X\nScene Id: y\n\nBody paragraph."
    tokens = tokenize(text)

    kinds = [t.kind for t in tokens]
    assert TokenKind.TITLE_KEY in kinds
    assert TokenKind.TITLE_END in kinds
    assert TokenKind.PROSE in kinds
    # TITLE_END must come before the first body token.
    title_end_idx = kinds.index(TokenKind.TITLE_END)
    prose_idx = kinds.index(TokenKind.PROSE)
    assert title_end_idx < prose_idx


def test_slugline_prefixes_are_recognised() -> None:
    for prefix in ("INT.", "EXT.", "INT./EXT.", "I/E."):
        tokens = tokenize(f"Title: X\n\n{prefix} SOMEWHERE")
        kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]
        assert TokenKind.SLUGLINE in kinds, f"{prefix} should be a slugline"


def test_speaker_line_only_uppercase_letters() -> None:
    tokens = tokenize("Title: X\n\nJEANGREY\nHello.")
    kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]

    assert TokenKind.SPEAKER in kinds
    # The following line is PROSE (the dialogue text).
    assert kinds[kinds.index(TokenKind.SPEAKER) + 1] == TokenKind.PROSE


def test_directive_line_is_tagged() -> None:
    tokens = tokenize("Title: X\n\n[[pause 1]]")

    kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]
    assert TokenKind.DIRECTIVE in kinds


def test_parenthetical_line_is_tagged() -> None:
    tokens = tokenize("Title: X\n\nJEANGREY\n(mood=sad, face=smirk)\nHello.")

    kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]
    assert TokenKind.PARENTHETICAL in kinds


def test_comment_line_is_tagged() -> None:
    tokens = tokenize("Title: X\n\n# This is a comment.")

    kinds = [t.kind for t in tokens if t.kind != TokenKind.EOF]
    assert TokenKind.COMMENT in kinds


def test_crlf_is_normalised() -> None:
    tokens = tokenize("Title: X\r\n\r\nSome narration.\r\n")

    # No blank-line artifact from stray \r; the first body line is PROSE.
    prose = [t for t in tokens if t.kind == TokenKind.PROSE]
    assert prose
    assert prose[0].value == "Some narration."
