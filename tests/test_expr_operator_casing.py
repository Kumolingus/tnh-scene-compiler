"""``AND`` / ``OR`` / ``NOT`` / ``IN`` are readable in any casing.

Uppercase is the house style — it reads as glue between conditions rather
than as part of one, and it is what the Condition Builder inserts — but
lowercase stays valid forever: 163 authored scenes were written that way.

The AST stores the lowercase spelling whichever the writer used, so the
emitted Ren'Py is Python either way. That is the property worth locking:
an uppercase source must not reach the ``.rpy``.
"""

from __future__ import annotations

import ast

import pytest

from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.codegen import CodegenContext, generate
from tnh_scene_compiler.expr_parser import parse_expression
from tnh_scene_compiler.parser import parse

_PREFIX = (
    "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
    "Scene Type: cinematic\nTrigger: manual\n\n"
)

_CTX = CodegenContext(project_prefix = "testmod")
_ALLOW = Allowlists(characters = {"a", "b", "c"})

# (source spelling, the lowercase expression it must mean)
_CASINGS = [
    ("a AND b", "a and b"),
    ("a OR b", "a or b"),
    ("NOT a", "not a"),
    ("NOT (a AND b)", "not (a and b)"),
    ("(a OR b) AND c", "(a or b) and c"),
    ("a And b Or c", "a and b or c"),
    ("NOT a AND b", "not a and b"),
    # Mixed casing in one expression is legal — no style is enforced.
    ("a AND not b", "a and not b"),
    ('"x" IN c', '"x" in c'),
    ('"x" NOT IN c', '"x" not in c'),
]


def _emitted_condition(condition: str) -> str:
    src = _PREFIX + f"[[if {condition}]]\nLine.\n[[/if]]\n"
    out = generate(parse(src, path = "inline.scene"), _ALLOW, _CTX)
    line = next(
        stripped
        for stripped in (raw.strip() for raw in out.splitlines())
        if stripped.startswith("if ")
    )
    return line[len("if "):].rstrip(":")


@pytest.mark.parametrize(("source", "equivalent"), _CASINGS)
def test_uppercase_operators_parse_to_the_same_tree(
    source: str, equivalent: str,
) -> None:
    assert parse_expression(source) == parse_expression(equivalent)


@pytest.mark.parametrize(("source", "equivalent"), _CASINGS)
def test_uppercase_operators_emit_python(source: str, equivalent: str) -> None:
    """Whatever the writer typed, the ``.rpy`` gets lowercase Python."""
    emitted = _emitted_condition(source)
    assert ast.dump(ast.parse(emitted, mode = "eval")) == ast.dump(
        ast.parse(equivalent, mode = "eval"),
    )


def test_literals_stay_case_sensitive() -> None:
    """``TRUE`` is a name, not a boolean — only the operators are relaxed.

    Values a condition compares against belong to the condition; relaxing
    them would silently turn a misspelled state key into a constant.
    """
    from tnh_scene_compiler.expr_parser import Literal, Name

    assert parse_expression("True") == Literal(value = True, col_offset = 0)
    assert parse_expression("TRUE") == Name(name = "TRUE", col_offset = 0)
    assert parse_expression("none") == Name(name = "none", col_offset = 0)
