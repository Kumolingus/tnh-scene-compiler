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
        operand = parenthesize(self.operand.to_rpy(), self.operand, PRECEDENCE_NOT)
        return f"not {operand}"


@dataclass(frozen=True, slots=True)
class BoolOp:
    """Short-circuit boolean ``and``/``or`` chain."""

    op: str  # "and" or "or"
    operands: tuple[Expr, ...]
    col_offset: int = 0

    def to_rpy(self) -> str:
        own = PRECEDENCE_OR if self.op == "or" else PRECEDENCE_AND
        sep = f" {self.op} "
        return sep.join(
            parenthesize(a.to_rpy(), a, own) for a in self.operands
        )


@dataclass(frozen=True, slots=True)
class Compare:
    """Chained comparison. ``ops_and_rights`` is ``[(op, right), ...]``."""

    left: Expr
    ops_and_rights: tuple[tuple[str, Expr], ...]
    col_offset: int = 0

    def to_rpy(self) -> str:
        out = [parenthesize(self.left.to_rpy(), self.left, PRECEDENCE_ATOM)]
        for op, right in self.ops_and_rights:
            out.append(f" {op} {parenthesize(right.to_rpy(), right, PRECEDENCE_ATOM)}")
        return "".join(out)


@dataclass(frozen=True, slots=True)
class Member:
    """``x in y`` or ``x not in y``. ``op`` is ``"in"`` or ``"not in"``."""

    left: Expr
    op: str
    right: Expr
    col_offset: int = 0

    def to_rpy(self) -> str:
        left = parenthesize(self.left.to_rpy(), self.left, PRECEDENCE_ATOM)
        right = parenthesize(self.right.to_rpy(), self.right, PRECEDENCE_ATOM)
        return f"{left} {self.op} {right}"


@dataclass(frozen=True, slots=True)
class ListExpr:
    """A sequence literal — ``[a, b]``, or ``(a, b)`` when ``is_tuple``.

    Produced by the DSL transformation layer (:mod:`dsl`), which builds one
    when a writer-friendly rewrite targets a base-game function expecting an
    iterable of characters (``Character.friends_with(Y)`` ->
    ``are_Characters_friends([Character, Y])``), and by the parser, since a
    writer needs to name a group of characters (``are_Characters_friends(
    [JeanGrey, Rogue], 2)``) or a ``(day, time_index)`` moment.

    Tuples reuse this node rather than adding a kind: every consumer that
    walks the expression tree (codegen, the validator's call and attribute
    collectors) already descends into ``elements``, and the two differ only
    in how they render.
    """

    elements: tuple[Expr, ...]
    col_offset: int = 0
    is_tuple: bool = False

    def to_rpy(self) -> str:
        inner = ", ".join(e.to_rpy() for e in self.elements)
        if self.is_tuple:
            # A 1-tuple needs its trailing comma to stay a tuple.
            return f"({inner},)" if len(self.elements) == 1 else f"({inner})"
        return f"[{inner}]"


Expr = Literal | Name | Attribute | Call | UnaryNot | BoolOp | Compare | Member | ListExpr


# --- Operator precedence ------------------------------------------------------

# Binding strength of each operator in the ``[[if]]`` subset, low to high,
# matching Python's own. The parser does not keep the writer's parentheses —
# the tree shape is what carries the grouping — so a renderer has to put them
# back from precedence alone. Without that, ``not (a and b)`` renders as
# ``not a and b``, which Python reads as ``(not a) and b``: valid Ren'Py, the
# other branch, and nothing raises anywhere along the way.
PRECEDENCE_OR: int = 1
PRECEDENCE_AND: int = 2
PRECEDENCE_NOT: int = 3
PRECEDENCE_COMPARISON: int = 4
PRECEDENCE_ATOM: int = 5


def precedence(expr: Expr) -> int:
    """Return the binding strength of *expr*'s top-level operator.

    Atoms — names, literals, calls, sequence literals — are self-delimiting
    and never need protecting, so they rank above every operator.
    """
    if isinstance(expr, BoolOp):
        return PRECEDENCE_OR if expr.op == "or" else PRECEDENCE_AND
    if isinstance(expr, UnaryNot):
        return PRECEDENCE_NOT
    if isinstance(expr, (Compare, Member)):
        return PRECEDENCE_COMPARISON
    return PRECEDENCE_ATOM


def parenthesize(rendered: str, expr: Expr, parent_precedence: int) -> str:
    """Wrap *rendered* in parentheses when *expr* binds looser than its parent.

    ``rendered`` is *expr* already turned into text by the caller: the two
    renderers (this module's ``to_rpy`` and :mod:`codegen`, which resolves
    scene-local names) emit different text for the same node, so the
    decision is shared but the rendering is not.

    Operands of a comparison or membership test pass
    :data:`PRECEDENCE_ATOM` rather than :data:`PRECEDENCE_COMPARISON`, so
    anything that is not an atom gets wrapped. Two reasons: ``(not a) == b``
    must not flatten to ``not a == b`` (Python reads that as
    ``not (a == b)``), and ``a == (b in c)`` must not flatten to
    ``a == b in c``, which Python reads as a *chained* comparison. Neither
    over-parenthesises real conditions — the grammar only allows an operator
    there when the writer wrote the parentheses in the first place.
    """
    if precedence(expr) < parent_precedence:
        return f"({rendered})"
    return rendered


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
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
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


# Value literals, spelled exactly as Python spells them. ``TRUE`` is a name,
# not a boolean: these are values a condition compares *against*, so they
# belong to the condition, not to the glue between conditions.
_LITERAL_KEYWORDS: dict[str, tuple[str, bool | None]] = {
    "True": (_TK.TRUE, True),
    "False": (_TK.FALSE, False),
    "None": (_TK.NONE, None),
}

# Boolean and membership operators, matched **case-insensitively**:
# ``JeanGrey.nearby AND NOT lied`` and ``JeanGrey.nearby and not lied`` are
# the same expression. Uppercase is the house style — it reads as glue
# rather than as part of a condition, and it is what the Condition Builder
# inserts — but lowercase stays valid, so no existing scene has to change.
#
# The AST is unaffected either way: ``_parse_and`` / ``_parse_or`` / the
# membership branch hardcode the lowercase spelling into the node, so
# codegen always emits Python regardless of how the writer typed it.
#
# The cost, accepted: a scene-local state key can no longer be named `AND`,
# `Or`, `NOT` or `In` in any casing.
_OPERATOR_KEYWORDS: dict[str, tuple[str, str]] = {
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
            # Literals match exactly; operators match in any casing. The
            # token keeps the source spelling so an error message quotes
            # the writer's own text back at them.
            if ident in _LITERAL_KEYWORDS:
                kind, _ = _LITERAL_KEYWORDS[ident]
                tokens.append(_Tok(kind, ident, start))
            elif ident.lower() in _OPERATOR_KEYWORDS:
                kind, _ = _OPERATOR_KEYWORDS[ident.lower()]
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
            # A leading '[' opens a list literal; a '[' following a value is
            # indexing, which the parser rejects with the §11.9.1 message.
            "[": _TK.LBRACKET,
            "]": _TK.RBRACKET,
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


# Subscripting stays forbidden even though '[' now opens a list literal, so
# the message lives here for the parser to raise on a postfix '['.
_INDEXING_MESSAGE = (
    "Indexing is not allowed. Use an attribute access or register a helper function."
)

# Reject every forbidden Python operator §11.9.1 lists. Mapping the raw
# character to the writer-facing message keeps the error text stable.
_FORBIDDEN_CHAR_MESSAGES: dict[str, str] = {
    "+": "Arithmetic is not allowed in [[if]] expressions.",
    "-": "Arithmetic is not allowed in [[if]] expressions.",
    "*": "Arithmetic is not allowed in [[if]] expressions.",
    "/": "Arithmetic is not allowed in [[if]] expressions.",
    "%": "Arithmetic is not allowed in [[if]] expressions.",
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
    # A '[' that follows a value is a subscript, not a list literal — still
    # forbidden. Only a '[' in value position (handled by _parse_primary)
    # opens a list.
    if state.peek().kind == _TK.LBRACKET:
        raise state.error(state.peek(), _INDEXING_MESSAGE)
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


def _parse_sequence_elements(
    state: _ParseState,
    closer: str,
    *,
    first: Expr | None = None,
) -> list[Expr]:
    """Parse the comma-separated elements of a list or tuple literal.

    *first* is the element already consumed by the caller (the tuple case,
    where the opening expression was parsed before the comma disambiguated
    it). A trailing comma before *closer* is accepted and ignored, which is
    also what makes the one-element tuple ``(x,)`` parse.
    """
    elements: list[Expr] = [] if first is None else [first]
    if first is None:
        elements.append(_parse_expr(state))
    while state.peek().kind == _TK.COMMA:
        state.advance()
        if state.peek().kind == closer:
            break
        elements.append(_parse_expr(state))
    return elements


def _expect_close(state: _ParseState, kind: str, message: str) -> None:
    """Consume the closing bracket of a literal, or raise *message*."""
    close = state.peek()
    if close.kind == _TK.ILLEGAL:
        _raise_illegal(state, close)
    if close.kind != kind:
        raise state.error(close, message)
    state.advance()


def _parse_primary(state: _ParseState) -> Expr:
    tok = state.peek()

    # A '-' in *value* position, directly before a number, belongs to the
    # literal rather than being arithmetic — the same value-position versus
    # postfix split that lets '[' open a list without allowing subscripting.
    # It has to be expressible: the friendship tiers run down to -2 (enemies)
    # and -1 (rivals), and every doc that names that scale tells writers to
    # compare against it, so `get_effective_friendship(A, B) >= -1` is a
    # question the format promises. Arithmetic stays refused — a '-' that
    # *follows* a value never reaches here, and one before a name or a '('
    # falls through to _raise_illegal below.
    if tok.kind == _TK.ILLEGAL and tok.value == "-":
        number = state.peek(1)
        if number.kind in (_TK.INT, _TK.FLOAT):
            state.advance()
            state.advance()
            magnitude = (
                int(number.value) if number.kind == _TK.INT else float(number.value)
            )
            return Literal(value = -magnitude, col_offset = tok.col)

    if tok.kind == _TK.ILLEGAL:
        _raise_illegal(state, tok)

    if tok.kind == _TK.LPAREN:
        state.advance()
        inner = _parse_expr(state)
        # A comma turns the group into a tuple — the `(day, time_index)`
        # moment the time functions take.
        if state.peek().kind == _TK.COMMA:
            elements = _parse_sequence_elements(state, _TK.RPAREN, first = inner)
            _expect_close(state, _TK.RPAREN, "Expected ')' to close the tuple.")
            return ListExpr(
                elements = tuple(elements), col_offset = tok.col, is_tuple = True,
            )
        close = state.peek()
        if close.kind == _TK.ILLEGAL:
            _raise_illegal(state, close)
        if close.kind != _TK.RPAREN:
            raise state.error(close, "Expected ')' to close the parenthesised expression.")
        state.advance()
        return inner

    if tok.kind == _TK.LBRACKET:
        state.advance()
        elements = (
            []
            if state.peek().kind == _TK.RBRACKET
            else _parse_sequence_elements(state, _TK.RBRACKET)
        )
        _expect_close(state, _TK.RBRACKET, "Expected ']' to close the list.")
        return ListExpr(elements = tuple(elements), col_offset = tok.col)

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
    if tok.kind == _TK.RBRACKET:
        raise state.error(tok, "Unexpected ']'.")
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
