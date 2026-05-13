"""Safe-subset expression parser for ``[[if]]`` bodies (§11.9.1).

Design constraints:

* **No ``eval``, no ``ast.literal_eval``.** The compiler must never execute
  writer-supplied code. The grammar is implemented as a hand-written
  recursive-descent parser so every syntactic construct is explicitly
  allowed or explicitly rejected.
* **One error per mistake.** The parser raises :class:`CompileError` on
  the first violation and returns a parsed AST when the expression is
  valid. Callers that want to accumulate multiple errors must run the
  parser per condition string.
* **Render-back for codegen.** Every AST node implements :meth:`to_rpy`
  returning a Ren'Py-compatible string representation. Ren'Py accepts the
  same Python-subset we allow here, so ``to_rpy`` is essentially a
  pretty-print — but going through the AST guarantees that forbidden
  constructs never reach the ``.rpy`` output even if the parser is later
  relaxed.

Grammar (precedence low-to-high, matching Python's own operator
precedence for the allowed subset):

.. code-block:: none

    expr        := or_expr
    or_expr     := and_expr ( "or" and_expr )*
    and_expr    := not_expr ( "and" not_expr )*
    not_expr    := "not" not_expr | compare
    compare     := member ( ( "==" | "!=" | "<" | "<=" | ">" | ">=" ) member )*
    member      := primary ( ( "in" | "not" "in" ) primary )?
    primary     := literal
                 | "(" expr ")"
                 | name_or_call_or_attr
    name_or_call_or_attr :=
                   NAME ( "." NAME )* ( "(" arglist? ")" )?
    arglist     := expr ( "," expr )*
    literal     := INT | FLOAT | STRING | "True" | "False" | "None"

Chained comparisons (``0 < x < 100``) share Python's semantics; the AST
node :class:`Compare` holds a left operand plus a list of
``(op, right)`` pairs so codegen can render them as-is.

Any token the lexer produces but the grammar does not accept produces a
:class:`CompileError` with the offending text and column offset. This is
deliberately strict: the writer-facing spec rules out arithmetic,
subscripting, slicing, f-strings, lambdas, comprehensions, ternary,
walrus, and bitwise operators (§11.9.1 "Forbidden constructs").
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import CompileError

# --- Expression AST -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Literal:
    """Numeric, string, boolean or None literal."""

    value: int | float | str | bool | None
    col_offset: int = 0

    def to_rpy(self) -> str:
        if isinstance(self.value, bool):
            return "True" if self.value else "False"
        if self.value is None:
            return "None"
        if isinstance(self.value, str):
            # Ren'Py accepts single or double quotes; we always emit double
            # and escape embedded quotes/backslashes the same way codegen
            # does for dialogue lines.
            escaped = self.value.replace("\\", "\\\\").replace("\"", "\\\"")
            return f"\"{escaped}\""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class Name:
    """A bare identifier (scene-local state key, time/world key, or function)."""

    name: str
    col_offset: int = 0

    def to_rpy(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class Attribute:
    """Dotted attribute access chain.

    The ``root`` is a :class:`Name` and ``parts`` the dot-separated suffix.
    Example: ``JeanGrey.pregnancy_stage`` → ``root=Name("JeanGrey")``,
    ``parts=("pregnancy_stage",)``.
    """

    root: Name
    parts: tuple[str, ...]
    col_offset: int = 0

    def to_rpy(self) -> str:
        return ".".join((self.root.name, *self.parts))


@dataclass(frozen=True, slots=True)
class Call:
    """A function call. ``target`` is a :class:`Name` or :class:`Attribute`."""

    target: Name | Attribute
    args: tuple[Expr, ...] = ()
    col_offset: int = 0

    def to_rpy(self) -> str:
        rendered_args = ", ".join(a.to_rpy() for a in self.args)
        return f"{self.target.to_rpy()}({rendered_args})"


@dataclass(frozen=True, slots=True)
class UnaryNot:
    """Boolean ``not x``."""

    operand: Expr
    col_offset: int = 0

    def to_rpy(self) -> str:
        return f"not {self.operand.to_rpy()}"


@dataclass(frozen=True, slots=True)
class BoolOp:
    """Short-circuit boolean ``and``/``or`` chain."""

    op: str  # "and" or "or"
    operands: tuple[Expr, ...]
    col_offset: int = 0

    def to_rpy(self) -> str:
        sep = f" {self.op} "
        return sep.join(a.to_rpy() for a in self.operands)


@dataclass(frozen=True, slots=True)
class Compare:
    """Chained comparison. ``ops_and_rights`` is ``[(op, right), ...]``."""

    left: Expr
    ops_and_rights: tuple[tuple[str, Expr], ...]
    col_offset: int = 0

    def to_rpy(self) -> str:
        out = [self.left.to_rpy()]
        for op, right in self.ops_and_rights:
            out.append(f" {op} {right.to_rpy()}")
        return "".join(out)


@dataclass(frozen=True, slots=True)
class Member:
    """``x in y`` or ``x not in y``. ``op`` is ``"in"`` or ``"not in"``."""

    left: Expr
    op: str
    right: Expr
    col_offset: int = 0

    def to_rpy(self) -> str:
        return f"{self.left.to_rpy()} {self.op} {self.right.to_rpy()}"


Expr = Literal | Name | Attribute | Call | UnaryNot | BoolOp | Compare | Member


# --- Tokeniser ----------------------------------------------------------------
#
# The parser consumes a typed token stream rather than chewing on raw chars.
# Token kinds are deliberately minimal; forbidden constructs are flagged as
# ``ILLEGAL`` at scan time so the parser can report a precise message.


class _TK:
    NAME = "NAME"
    INT = "INT"
    FLOAT = "FLOAT"
    STRING = "STRING"
    TRUE = "TRUE"
    FALSE = "FALSE"
    NONE = "NONE"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    IN = "IN"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    COMMA = "COMMA"
    DOT = "DOT"
    EQ = "EQ"       # ==
    NEQ = "NEQ"     # !=
    LT = "LT"
    LE = "LE"
    GT = "GT"
    GE = "GE"
    EOF = "EOF"
    ILLEGAL = "ILLEGAL"


@dataclass(frozen=True, slots=True)
class _Tok:
    kind: str
    value: str
    col: int  # 0-based offset within the expression source


_KEYWORDS = {
    "True": (_TK.TRUE, True),
    "False": (_TK.FALSE, False),
    "None": (_TK.NONE, None),
    "and": (_TK.AND, "and"),
    "or": (_TK.OR, "or"),
    "not": (_TK.NOT, "not"),
    "in": (_TK.IN, "in"),
}

# Reserved Python words the writer is not allowed to use inside [[if]]
# expressions. Mapped to the precise §11.9.1 error text so the scanner
# can surface the right message via an ILLEGAL token.
_RESERVED_WORDS: dict[str, str] = {
    "lambda": "Lambdas are not allowed.",
    "if": "Ternary expressions are not allowed. Use [[if]]/[[else]] in the scene body.",
    "else": "Ternary expressions are not allowed. Use [[if]]/[[else]] in the scene body.",
    "elif": "Ternary expressions are not allowed. Use [[if]]/[[else]] in the scene body.",
    "for": "Comprehensions are not allowed.",
    "while": "Loops are not allowed.",
    "yield": "Generator expressions are not allowed.",
    "is": "'is' / 'is not' are not allowed. Use '==' / '!='.",
    "def": "Function definitions are not allowed.",
    "class": "Class definitions are not allowed.",
    "import": "Imports are not allowed.",
    "from": "Imports are not allowed.",
    "as": "'as' aliases are not allowed.",
    "pass": "'pass' is not allowed.",
    "return": "'return' is not allowed.",
    "raise": "'raise' is not allowed.",
    "try": "Exception handling is not allowed.",
    "with": "'with' statements are not allowed.",
    "global": "'global' is not allowed.",
    "nonlocal": "'nonlocal' is not allowed.",
    "async": "Async constructs are not allowed.",
    "await": "Async constructs are not allowed.",
}


def _scan(text: str) -> list[_Tok]:
    """Scan ``text`` into a list of tokens. Whitespace is skipped.

    Forbidden characters (``+``, ``-``, ``*``, ``/``, ``%``, ``[``, ``]``,
    ``{``, ``}``, ``&``, ``|``, ``^``, ``~``, ``:``, ``@``, ``#``, ``?``,
    ``\\``, ``;``, ``!`` outside ``!=``, ``<<``, ``>>``) are emitted as
    ``ILLEGAL`` tokens so the parser can raise with an accurate column.
    """
    tokens: list[_Tok] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]

        # Whitespace.
        if ch in " \t":
            i += 1
            continue

        # Identifiers / keywords.
        if ch.isalpha() or ch == "_":
            start = i
            while i < n and (text[i].isalnum() or text[i] == "_"):
                i += 1
            ident = text[start:i]
            if ident in _KEYWORDS:
                kind, _ = _KEYWORDS[ident]
                tokens.append(_Tok(kind, ident, start))
            elif ident in _RESERVED_WORDS:
                tokens.append(_Tok(_TK.ILLEGAL, ident, start))
            else:
                # Reject f-string / r-string / b-string prefixes specifically,
                # since the scanner would otherwise tokenise them as NAME +
                # STRING and surface a generic "trailing content" error.
                if (
                    i < n
                    and text[i] in ("\"", "'")
                    and ident.lower() in ("f", "r", "b", "u", "rb", "br", "rf", "fr")
                ):
                    tokens.append(_Tok(_TK.ILLEGAL, ident + text[i], start))
                    # Consume the opening quote so the scanner resumes cleanly.
                    i += 1
                    while i < n and text[i] not in ("\"", "'"):
                        i += 1
                    if i < n:
                        i += 1
                    continue
                tokens.append(_Tok(_TK.NAME, ident, start))
            continue

        # Numbers.
        if ch.isdigit():
            start = i
            while i < n and text[i].isdigit():
                i += 1
            if i < n and text[i] == ".":
                i += 1
                while i < n and text[i].isdigit():
                    i += 1
                tokens.append(_Tok(_TK.FLOAT, text[start:i], start))
            else:
                tokens.append(_Tok(_TK.INT, text[start:i], start))
            continue

        # Strings.
        if ch in ("\"", "'"):
            quote = ch
            start = i
            i += 1
            buf: list[str] = []
            while i < n and text[i] != quote:
                if text[i] == "\\" and i + 1 < n:
                    buf.append(text[i + 1])
                    i += 2
                    continue
                buf.append(text[i])
                i += 1
            if i >= n:
                tokens.append(_Tok(_TK.ILLEGAL, text[start:], start))
                return tokens
            i += 1  # closing quote
            tokens.append(_Tok(_TK.STRING, "".join(buf), start))
            continue

        # Two-char operators.
        if ch == "=" and i + 1 < n and text[i + 1] == "=":
            tokens.append(_Tok(_TK.EQ, "==", i))
            i += 2
            continue
        if ch == "!" and i + 1 < n and text[i + 1] == "=":
            tokens.append(_Tok(_TK.NEQ, "!=", i))
            i += 2
            continue
        if ch == "<" and i + 1 < n and text[i + 1] == "=":
            tokens.append(_Tok(_TK.LE, "<=", i))
            i += 2
            continue
        if ch == ">" and i + 1 < n and text[i + 1] == "=":
            tokens.append(_Tok(_TK.GE, ">=", i))
            i += 2
            continue

        # Single-char punctuation.
        single: dict[str, str] = {
            "(": _TK.LPAREN,
            ")": _TK.RPAREN,
            ",": _TK.COMMA,
            ".": _TK.DOT,
            "<": _TK.LT,
            ">": _TK.GT,
        }
        if ch in single:
            tokens.append(_Tok(single[ch], ch, i))
            i += 1
            continue

        # Anything else — including forbidden operators — is illegal. The
        # caller inspects the first ILLEGAL token it meets and translates
        # it into the §11.9.1 error message.
        tokens.append(_Tok(_TK.ILLEGAL, ch, i))
        i += 1

    tokens.append(_Tok(_TK.EOF, "", n))
    return tokens


# --- Parser -------------------------------------------------------------------


@dataclass(slots=True)
class _ParseState:
    tokens: list[_Tok]
    pos: int = 0
    path: str = "<inline>"
    base_line: int = 1
    base_col: int = 1
    source: str = ""
    _illegal_messages: dict[str, str] = field(default_factory=dict)

    def peek(self, offset: int = 0) -> _Tok:
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def advance(self) -> _Tok:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def error(self, tok: _Tok, message: str, hint: str | None = None) -> CompileError:
        """Build a :class:`CompileError` anchored at ``tok``'s column."""
        return CompileError(
            path = self.path,
            line = self.base_line,
            col = self.base_col + tok.col,
            message = message,
            hint = hint,
        )


# Reject every forbidden Python operator §11.9.1 lists. Mapping the raw
# character to the writer-facing message keeps the error text stable.
_FORBIDDEN_CHAR_MESSAGES: dict[str, str] = {
    "+": "Arithmetic is not allowed in [[if]] expressions.",
    "-": "Arithmetic is not allowed in [[if]] expressions.",
    "*": "Arithmetic is not allowed in [[if]] expressions.",
    "/": "Arithmetic is not allowed in [[if]] expressions.",
    "%": "Arithmetic is not allowed in [[if]] expressions.",
    "[": "Indexing is not allowed. Use an attribute access or register a helper function.",
    "]": "Indexing is not allowed. Use an attribute access or register a helper function.",
    "{": "Set/dict literals are not allowed in [[if]] expressions.",
    "}": "Set/dict literals are not allowed in [[if]] expressions.",
    "&": "Bitwise operators are not allowed.",
    "|": "Bitwise operators are not allowed.",
    "^": "Bitwise operators are not allowed.",
    "~": "Bitwise operators are not allowed.",
    "@": "Decorators are not allowed in [[if]] expressions.",
    "#": "Comments are not allowed inside [[if]] expressions.",
    "?": "The '?' character is not allowed. Use [[if]]/[[else]] in the scene body.",
    ":": "Slicing or ternary expressions are not allowed.",
    ";": "Multiple statements per [[if]] line are not allowed.",
    "\\": "Backslash escapes outside strings are not allowed.",
    "!": "'!' is only valid as part of '!='.",
}


def _raise_illegal(state: _ParseState, tok: _Tok) -> None:
    """Translate an ``ILLEGAL`` token into the writer-facing §11.9.1 message.

    ``ILLEGAL`` tokens carry either a single forbidden character
    (``+``, ``[``, ``&``, …), a reserved Python keyword
    (``lambda``, ``if``, ``for``, …), or a string-prefix like ``f"``.
    The message is picked from whichever lookup matches.
    """
    value = tok.value
    if value in _RESERVED_WORDS:
        raise state.error(tok, _RESERVED_WORDS[value])
    if len(value) >= 2 and value[0].isalpha() and value[-1] in ("\"", "'"):
        raise state.error(
            tok,
            "f-strings / raw-strings / byte-strings are not allowed in [[if]] expressions.",
        )
    message = _FORBIDDEN_CHAR_MESSAGES.get(value, f"Unexpected character {value!r}.")
    raise state.error(tok, message)


def _parse_expr(state: _ParseState) -> Expr:
    return _parse_or(state)


def _parse_or(state: _ParseState) -> Expr:
    left = _parse_and(state)
    operands: list[Expr] = [left]
    col = getattr(left, "col_offset", 0)
    while state.peek().kind == _TK.OR:
        state.advance()
        operands.append(_parse_and(state))
    if len(operands) == 1:
        return left
    return BoolOp(op = "or", operands = tuple(operands), col_offset = col)


def _parse_and(state: _ParseState) -> Expr:
    left = _parse_not(state)
    operands: list[Expr] = [left]
    col = getattr(left, "col_offset", 0)
    while state.peek().kind == _TK.AND:
        state.advance()
        operands.append(_parse_not(state))
    if len(operands) == 1:
        return left
    return BoolOp(op = "and", operands = tuple(operands), col_offset = col)


def _parse_not(state: _ParseState) -> Expr:
    if state.peek().kind == _TK.NOT:
        tok = state.advance()
        # ``not in`` only makes sense as a postfix operator — a leading
        # ``not in`` is a syntax error.
        if state.peek().kind == _TK.IN:
            raise state.error(tok, "'not in' must follow a value.")
        return UnaryNot(operand = _parse_not(state), col_offset = tok.col)
    return _parse_compare(state)


_COMP_OPS = {_TK.EQ, _TK.NEQ, _TK.LT, _TK.LE, _TK.GT, _TK.GE}


def _parse_compare(state: _ParseState) -> Expr:
    left = _parse_member(state)
    rights: list[tuple[str, Expr]] = []
    col = getattr(left, "col_offset", 0)
    while state.peek().kind in _COMP_OPS:
        op_tok = state.advance()
        rights.append((op_tok.value, _parse_member(state)))
    if not rights:
        return left
    return Compare(left = left, ops_and_rights = tuple(rights), col_offset = col)


def _parse_member(state: _ParseState) -> Expr:
    left = _parse_primary(state)
    # Either ``<expr> in <expr>`` or ``<expr> not in <expr>``.
    if state.peek().kind == _TK.IN:
        state.advance()
        return Member(
            left = left, op = "in", right = _parse_primary(state),
            col_offset = getattr(left, "col_offset", 0),
        )
    if state.peek().kind == _TK.NOT and state.peek(1).kind == _TK.IN:
        state.advance()
        state.advance()
        return Member(
            left = left, op = "not in", right = _parse_primary(state),
            col_offset = getattr(left, "col_offset", 0),
        )
    return left


def _parse_primary(state: _ParseState) -> Expr:
    tok = state.peek()

    if tok.kind == _TK.ILLEGAL:
        _raise_illegal(state, tok)

    if tok.kind == _TK.LPAREN:
        state.advance()
        inner = _parse_expr(state)
        close = state.peek()
        if close.kind == _TK.ILLEGAL:
            _raise_illegal(state, close)
        if close.kind != _TK.RPAREN:
            raise state.error(close, "Expected ')' to close the parenthesised expression.")
        state.advance()
        return inner

    if tok.kind == _TK.INT:
        state.advance()
        return Literal(value = int(tok.value), col_offset = tok.col)
    if tok.kind == _TK.FLOAT:
        state.advance()
        return Literal(value = float(tok.value), col_offset = tok.col)
    if tok.kind == _TK.STRING:
        state.advance()
        return Literal(value = tok.value, col_offset = tok.col)
    if tok.kind == _TK.TRUE:
        state.advance()
        return Literal(value = True, col_offset = tok.col)
    if tok.kind == _TK.FALSE:
        state.advance()
        return Literal(value = False, col_offset = tok.col)
    if tok.kind == _TK.NONE:
        state.advance()
        return Literal(value = None, col_offset = tok.col)

    if tok.kind == _TK.NAME:
        return _parse_name_or_call_or_attr(state)

    # Reject the remaining token kinds explicitly so the writer gets a
    # targeted message rather than "unexpected token".
    if tok.kind == _TK.RPAREN:
        raise state.error(tok, "Unexpected ')'.")
    if tok.kind in (_TK.AND, _TK.OR, _TK.NOT, _TK.IN):
        raise state.error(tok, f"'{tok.value}' cannot appear here — expected a value.")
    if tok.kind in _COMP_OPS:
        raise state.error(tok, f"Comparison '{tok.value}' must follow a value.")
    if tok.kind == _TK.COMMA:
        raise state.error(tok, "Unexpected ','.")
    if tok.kind == _TK.EOF:
        raise state.error(tok, "Unexpected end of expression.")

    raise state.error(tok, f"Unexpected token {tok.value!r}.")


def _parse_name_or_call_or_attr(state: _ParseState) -> Expr:
    first = state.advance()
    col = first.col

    # Collect dotted attribute parts.
    parts: list[str] = []
    while state.peek().kind == _TK.DOT:
        state.advance()
        next_tok = state.peek()
        if next_tok.kind != _TK.NAME:
            raise state.error(next_tok, "Expected an attribute name after '.'.")
        state.advance()
        parts.append(next_tok.value)

    target: Name | Attribute = Name(name = first.value, col_offset = col)
    if parts:
        target = Attribute(
            root = Name(name = first.value, col_offset = col),
            parts = tuple(parts),
            col_offset = col,
        )

    # Optional call.
    if state.peek().kind == _TK.LPAREN:
        state.advance()
        args: list[Expr] = []
        if state.peek().kind != _TK.RPAREN:
            args.append(_parse_expr(state))
            while state.peek().kind == _TK.COMMA:
                state.advance()
                args.append(_parse_expr(state))
        close = state.peek()
        if close.kind == _TK.ILLEGAL:
            _raise_illegal(state, close)
        if close.kind != _TK.RPAREN:
            raise state.error(close, "Expected ')' to close the argument list.")
        state.advance()
        return Call(target = target, args = tuple(args), col_offset = col)

    return target


def parse_expression(
    text: str,
    *,
    path: str = "<inline>",
    line: int = 1,
    base_col: int = 1,
) -> Expr:
    """Parse ``text`` as a safe-subset expression. Raises :class:`CompileError`.

    Parameters:
        text: Expression source — the bit between ``[[if`` and ``]]``,
            trimmed of its enclosing whitespace by the caller.
        path: Path of the containing ``.scene`` file. Passed through to
            the error for the ``file:line:col`` format.
        line: 1-based line in the scene file where the expression starts.
        base_col: 1-based column in that line where ``text`` starts.
            Columns inside ``text`` are added to this base when an error
            is raised.

    Returns the top-level :class:`Expr` AST node.
    """
    state = _ParseState(
        tokens = _scan(text),
        path = path,
        base_line = line,
        base_col = base_col,
        source = text,
    )
    expr = _parse_expr(state)
    trailing = state.peek()
    if trailing.kind == _TK.ILLEGAL:
        _raise_illegal(state, trailing)
    if trailing.kind != _TK.EOF:
        raise state.error(
            trailing,
            f"Unexpected trailing content {trailing.value!r} after the expression.",
        )
    return expr
