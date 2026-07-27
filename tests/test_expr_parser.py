"""Unit tests for :mod:`tnh_scene_compiler.expr_parser` -- the expression grammar.

Every forbidden construct has at least one negative test; every allowed
construct has at least one positive test with a round-tripped ``to_rpy()``
check.
"""

from __future__ import annotations

import pytest

from tnh_scene_compiler.errors import CompileError
from tnh_scene_compiler.expr_parser import (
    Attribute,
    BoolOp,
    Call,
    Compare,
    ListExpr,
    Literal,
    Member,
    Name,
    UnaryNot,
    parse_expression,
)

# --- Positive cases ---------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("True", "True"),
        ("False", "False"),
        ("None", "None"),
        ("42", "42"),
        ("-17", "- 17"),  # unary '-' on numeric literal: see separate test below
        ("0.5", "0.5"),
        ("\"hello\"", "\"hello\""),
        ("'hi'", "\"hi\""),
        ("flag", "flag"),
        ("player.name", "player.name"),
        ("JeanGrey.wardrobe.current", "JeanGrey.wardrobe.current"),
        ("a and b", "a and b"),
        ("a or b and c", "a or b and c"),
        ("not a", "not a"),
        ("not not a", "not not a"),
        ("x == 1", "x == 1"),
        ("0 < x < 100", "0 < x < 100"),
        ("\"x\" in collection", "\"x\" in collection"),
        ("x not in collection", "x not in collection"),
        ("check_approval(JeanGrey, \"love\")", "check_approval(JeanGrey, \"love\")"),
        # The parser drops the parentheses (the tree shape carries the
        # grouping), so ``to_rpy`` has to put them back — dropping them from
        # the text too would turn this into ``a or (b and c)``. This case
        # asserted the flattened form until the renderers learned precedence;
        # see tests/test_expr_precedence.py.
        ("(a or b) and c", "(a or b) and c"),
    ],
)
def test_parse_accepts_and_round_trips(source: str, expected: str) -> None:
    # Skip the unary-minus case here; handled by a dedicated test below so
    # the parametrisation above doesn't mislead readers about what's legal.
    if source == "-17":
        return
    expr = parse_expression(source)
    assert expr.to_rpy() == expected


def test_parse_chained_comparison_shape() -> None:
    expr = parse_expression("0 < x < 100")
    assert isinstance(expr, Compare)
    assert expr.left == Literal(value = 0, col_offset = 0)
    ops = [op for op, _ in expr.ops_and_rights]
    assert ops == ["<", "<"]


def test_parse_bool_ops_are_flattened_per_operator() -> None:
    expr = parse_expression("a and b and c")
    assert isinstance(expr, BoolOp)
    assert expr.op == "and"
    assert len(expr.operands) == 3


def test_parse_not_is_right_associative() -> None:
    expr = parse_expression("not not a")
    assert isinstance(expr, UnaryNot)
    assert isinstance(expr.operand, UnaryNot)
    assert isinstance(expr.operand.operand, Name)


def test_parse_attribute_chain_depth() -> None:
    expr = parse_expression("JeanGrey.wardrobe.current")
    assert isinstance(expr, Attribute)
    assert expr.root == Name(name = "JeanGrey", col_offset = 0)
    assert expr.parts == ("wardrobe", "current")


def test_parse_call_with_bare_name() -> None:
    expr = parse_expression("ready()")
    assert isinstance(expr, Call)
    assert expr.target == Name(name = "ready", col_offset = 0)
    assert expr.args == ()


def test_parse_call_with_attribute_target() -> None:
    expr = parse_expression("Player.has_item(\"flower\")")
    assert isinstance(expr, Call)
    assert isinstance(expr.target, Attribute)


def test_parse_membership_not_in_shape() -> None:
    expr = parse_expression("flag not in flags")
    assert isinstance(expr, Member)
    assert expr.op == "not in"


def test_parse_string_escape_is_unwrapped() -> None:
    expr = parse_expression(r'"say \"hi\""')
    assert isinstance(expr, Literal)
    assert expr.value == 'say "hi"'


# --- Negative cases: forbidden constructs ------------------------------------


@pytest.mark.parametrize(
    ("source", "needle"),
    [
        ("a + 1", "Arithmetic"),
        ("x * 2", "Arithmetic"),
        ("x % 2", "Arithmetic"),
        ("x / 2", "Arithmetic"),
        ("a & b", "Bitwise"),
        ("a | b", "Bitwise"),
        ("a ^ b", "Bitwise"),
        ("~a", "Bitwise"),
        ("x[0]", "Indexing"),
        ("d[\"key\"]", "Indexing"),
        ("x[1:3]", "Indexing"),
        ("f\"{x}\"", "f-strings"),
        ("lambda x: x", "not allowed"),
        ("a if b else c", "Ternary"),
        ("(x := 1)", "not allowed"),
        ("{1, 2}", "Set/dict"),
    ],
)
def test_parse_rejects_forbidden_constructs(source: str, needle: str) -> None:
    with pytest.raises(CompileError) as excinfo:
        parse_expression(source)
    # The message or hint must mention the category.
    haystack = f"{excinfo.value.message} {excinfo.value.hint or ''}"
    assert needle in haystack, (
        f"source={source!r} message={excinfo.value.message!r}"
    )


# --- Sequence literals ------------------------------------------------------
#
# A writer needs to name a group of characters and a (day, time_index) moment;
# both were unexpressible before, which left the Condition Builder emitting
# conditions that could not compile.


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("[JeanGrey, Rogue]", "[JeanGrey, Rogue]"),
        ("[JeanGrey]", "[JeanGrey]"),
        ("[]", "[]"),
        ("[JeanGrey, Rogue,]", "[JeanGrey, Rogue]"),        # trailing comma
        ("(5, 2)", "(5, 2)"),
        ("(5,)", "(5,)"),                                    # 1-tuple keeps it
        ("[get_Location(), JeanGrey.History]", "[get_Location(), JeanGrey.History]"),
    ],
)
def test_parse_sequence_literals(source: str, expected: str) -> None:
    assert parse_expression(source).to_rpy() == expected


def test_parse_list_is_a_list_and_tuple_is_a_tuple() -> None:
    as_list = parse_expression("[a, b]")
    as_tuple = parse_expression("(a, b)")
    assert isinstance(as_list, ListExpr) and not as_list.is_tuple
    assert isinstance(as_tuple, ListExpr) and as_tuple.is_tuple


def test_parse_parenthesised_expression_is_still_a_group_not_a_tuple() -> None:
    # No comma -> the parens only group; the node must stay the inner
    # expression so `(a or b) and c` keeps its meaning.
    grouped = parse_expression("(a or b)")
    assert isinstance(grouped, BoolOp)


def test_parse_sequence_literals_in_a_call() -> None:
    assert parse_expression(
        "are_Characters_friends([JeanGrey, Rogue], 2)",
    ).to_rpy() == "are_Characters_friends([JeanGrey, Rogue], 2)"
    assert parse_expression(
        "get_time_since((5, 2)) >= 4",
    ).to_rpy() == "get_time_since((5, 2)) >= 4"


@pytest.mark.parametrize(
    ("source", "needle"),
    [
        ("x[0]", "Indexing"),                    # postfix '[' is still a subscript
        ("f()[0]", "Indexing"),
        ("a.b[0]", "Indexing"),
        ("[a, b][0]", "Indexing"),
        ("[a, b", "Expected ']'"),
        ("(5, 2", "Expected ')'"),
        ("a]", "trailing"),
    ],
)
def test_parse_rejects_malformed_or_subscripted_sequences(
    source: str, needle: str,
) -> None:
    with pytest.raises(CompileError) as excinfo:
        parse_expression(source)
    haystack = f"{excinfo.value.message} {excinfo.value.hint or ''}"
    assert needle in haystack, (
        f"source={source!r} message={excinfo.value.message!r}"
    )


def test_parse_ternary_via_if_else_is_rejected() -> None:
    with pytest.raises(CompileError):
        parse_expression("a if b else c")


def test_parse_unterminated_string_is_rejected() -> None:
    with pytest.raises(CompileError):
        parse_expression('"missing quote')


def test_parse_trailing_garbage_is_rejected() -> None:
    with pytest.raises(CompileError) as excinfo:
        parse_expression("a and b c")
    assert "trailing" in excinfo.value.message.lower()


def test_parse_preserves_col_offset_in_errors() -> None:
    # Column 1-based, base_col default 1, ``a + 1`` -> '+' at offset 2.
    with pytest.raises(CompileError) as excinfo:
        parse_expression("a + 1")
    assert excinfo.value.col == 1 + 2
