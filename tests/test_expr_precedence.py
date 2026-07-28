"""A grouped condition must keep its meaning all the way to the ``.rpy``.

The parser deliberately drops the writer's parentheses — the shape of the
tree is what carries the grouping — so every renderer has to put them back
from precedence alone. Before this was fixed, ``not (a and b)`` came out as
``not a and b``, which Python reads as ``(not a) and b``: valid Ren'Py, the
other branch taken, and nothing raised anywhere along the way.

These tests compare **meaning**, not text. The emitted line is re-parsed
with Python's own ``ast`` and matched against the condition the writer
typed, which is the only comparison that would have caught the original
bug — asserting on the rendered string is exactly what let it through.
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

# Leaves are registered as characters so ``_resolve_name`` passes them
# through untouched: a scene-local key would render as
# ``_scene_state.get('a')`` and the two sides could not be compared as
# Python source.
_ALLOW = Allowlists(characters = {"a", "b", "c", "d"})

# Conditions whose grouping contradicts Python's natural precedence — the
# ones that were silently miscompiled — plus the forms that were already
# right, to catch a fix that over-parenthesises.
_GROUPED_CONDITIONS = [
    "not (a and b)",
    "not (a or b)",
    "(a or b) and c",
    "a and (b or c)",
    "not (a and b) or c",
    "(a or b) and (c or d)",
    "not ((a or b) and c)",
    "not (a)",
    "not not a",
    "not a and b",
    "a and b or c",
    "a or b and c",
    "a and b and c",
    "not a",
    "(not a) == b",
    "a == (b in c)",
]


def _emitted_condition(condition: str) -> str:
    """Compile a one-branch scene and return the ``if`` line's expression."""
    src = _PREFIX + f"[[if {condition}]]\nLine.\n[[/if]]\n"
    out = generate(parse(src, path = "inline.scene"), _ALLOW, _CTX)
    line = next(
        stripped
        for stripped in (raw.strip() for raw in out.splitlines())
        if stripped.startswith("if ")
    )
    return line[len("if "):].rstrip(":")


def _meaning(expression: str) -> str:
    """Normalised Python AST dump — parentheses collapse, structure does not."""
    return ast.dump(ast.parse(expression, mode = "eval"))


@pytest.mark.parametrize("condition", _GROUPED_CONDITIONS)
def test_codegen_preserves_grouping(condition: str) -> None:
    assert _meaning(_emitted_condition(condition)) == _meaning(condition)


@pytest.mark.parametrize("condition", _GROUPED_CONDITIONS)
def test_ast_to_rpy_preserves_grouping(condition: str) -> None:
    """The AST's own ``to_rpy`` carries the same duty as codegen's renderer.

    It is a second renderer of the same trees; it had the same defect and
    must not drift back.
    """
    assert _meaning(parse_expression(condition).to_rpy()) == _meaning(condition)


def test_grouped_negation_is_parenthesised_verbatim() -> None:
    """One text assertion, to name the regression this file exists for."""
    assert _emitted_condition("not (a and b)") == "not (a and b)"
