"""DSL transformation layer for writer-friendly condition syntax.

Transforms intuitive expressions into the canonical function calls that
the Ren'Py engine expects.  Applied after parsing and before both
validation and code generation so the rest of the pipeline only sees
canonical forms.

Supported rewrites:

    Character.love >= tier   → check_approval(Character, "love", "tier_stat")
    Character.trust >= tier  → check_approval(Character, "trust", "tier_stat")
    Character.has("x")       → Character.check_trait("x")
    Character.mood == "normal" → Character.is_in_normal_mood()
    Character.mood == "x"    → Character.get_status() == "x"
    Character.friends_with(Y) → are_Characters_friends(Character, Y)
    Character.did("event")   → Character.History.check("event") > 0
    Character.nearby         → Character_is_in_close_proximity(Character)
    Character.personality("t") → Character.check_personality("t")
    Character.personality("t", n) → Character.check_personality("t", n)
"""

from __future__ import annotations

from .expr_parser import (
    Attribute,
    BoolOp,
    Call,
    Compare,
    Expr,
    Literal,
    Member,
    Name,
    UnaryNot,
)

_APPROVAL_AXES = frozenset({"love", "trust"})
_TIER_MAP: dict[str, str] = {
    "tiny": "tiny_stat",
    "small": "small_stat",
    "medium": "medium_stat",
    "large": "large_stat",
    "massive": "massive_stat",
}


def transform(
    expr: Expr,
    character_aliases: dict[str, str] | None = None,
    function_aliases: dict[str, str] | None = None,
) -> Expr:
    """Recursively rewrite DSL sugar into canonical expressions.

    Project-level aliases (loaded from ``aliases.yaml``) are applied
    first, then the built-in rewrites run on the result.
    """
    ca = character_aliases or {}
    fa = function_aliases or {}

    # --- Project-level aliases first ---
    expr = _apply_aliases(expr, ca, fa)

    # --- Built-in rewrites ---
    if isinstance(expr, Compare):
        return _transform_compare(expr, ca, fa)
    if isinstance(expr, Call):
        return _transform_call(expr, ca, fa)
    if isinstance(expr, Attribute):
        return _transform_attribute(expr, ca)
    if isinstance(expr, BoolOp):
        return BoolOp(
            op=expr.op,
            operands=tuple(transform(o, ca, fa) for o in expr.operands),
            col_offset=expr.col_offset,
        )
    if isinstance(expr, UnaryNot):
        return UnaryNot(
            operand=transform(expr.operand, ca, fa),
            col_offset=expr.col_offset,
        )
    if isinstance(expr, Member):
        return Member(
            left=transform(expr.left, ca, fa),
            op=expr.op,
            right=transform(expr.right, ca, fa),
            col_offset=expr.col_offset,
        )
    return expr


# ---------------------------------------------------------------------------
# Project-level alias resolution
# ---------------------------------------------------------------------------

def _apply_aliases(
    expr: Expr,
    ca: dict[str, str],
    fa: dict[str, str],
) -> Expr:
    """Resolve project-level aliases before built-in transforms."""
    # Character.alias(args) → target_function(Character, args)
    if isinstance(expr, Call) and isinstance(expr.target, Attribute):
        if len(expr.target.parts) == 1:
            method = expr.target.parts[0]
            if method in ca:
                root = expr.target.root
                return Call(
                    target=Name(ca[method], col_offset=expr.col_offset),
                    args=(Name(root.name, col_offset=root.col_offset), *expr.args),
                    col_offset=expr.col_offset,
                )

    # alias(args) → target_function(args)
    if isinstance(expr, Call) and isinstance(expr.target, Name):
        if expr.target.name in fa:
            return Call(
                target=Name(fa[expr.target.name], col_offset=expr.target.col_offset),
                args=expr.args,
                col_offset=expr.col_offset,
            )

    # Character.alias (bare property) → target_function(Character)
    if isinstance(expr, Attribute) and len(expr.parts) == 1:
        prop = expr.parts[0]
        if prop in ca:
            return Call(
                target=Name(ca[prop], col_offset=expr.col_offset),
                args=(Name(expr.root.name, col_offset=expr.root.col_offset),),
                col_offset=expr.col_offset,
            )

    return expr


# ---------------------------------------------------------------------------
# Compare rewrites
# ---------------------------------------------------------------------------

def _transform_compare(
    node: Compare,
    ca: dict[str, str],
    fa: dict[str, str],
) -> Expr:
    """Handle ``Character.love >= tier`` and ``Character.mood == value``."""
    left = transform(node.left, ca, fa)

    if (
        isinstance(left, Attribute)
        and len(left.parts) == 1
        and len(node.ops_and_rights) == 1
    ):
        prop = left.parts[0]
        op, right_raw = node.ops_and_rights[0]
        right = transform(right_raw, ca, fa)

        # Character.love/trust >= tier
        if prop in _APPROVAL_AXES:
            tier_name = _extract_tier(right)
            if tier_name is not None:
                return Call(
                    target=Name("check_approval", col_offset=node.col_offset),
                    args=(
                        Name(left.root.name, col_offset=left.col_offset),
                        Literal(prop),
                        Literal(tier_name),
                    ),
                    col_offset=node.col_offset,
                )

        # Character.mood == "normal" / "mad" / ...
        if prop == "mood" and op == "==":
            if isinstance(right, Literal) and right.value == "normal":
                return Call(
                    target=Attribute(
                        root=left.root,
                        parts=("is_in_normal_mood",),
                        col_offset=left.col_offset,
                    ),
                    args=(),
                    col_offset=node.col_offset,
                )
            if isinstance(right, (Literal, Name)):
                status_val = right.value if isinstance(right, Literal) else right.name
                return Compare(
                    left=Call(
                        target=Attribute(
                            root=left.root,
                            parts=("get_status",),
                            col_offset=left.col_offset,
                        ),
                        args=(),
                        col_offset=left.col_offset,
                    ),
                    ops_and_rights=(("==", Literal(status_val)),),
                    col_offset=node.col_offset,
                )

    transformed_ops = tuple(
        (op, transform(r, ca, fa)) for op, r in node.ops_and_rights
    )
    return Compare(
        left=left,
        ops_and_rights=transformed_ops,
        col_offset=node.col_offset,
    )


def _extract_tier(expr: Expr) -> str | None:
    """Return the stat tier string if *expr* is a known tier name."""
    if isinstance(expr, Name) and expr.name in _TIER_MAP:
        return _TIER_MAP[expr.name]
    if isinstance(expr, Literal) and isinstance(expr.value, str) and expr.value in _TIER_MAP:
        return _TIER_MAP[expr.value]
    return None


# ---------------------------------------------------------------------------
# Call rewrites
# ---------------------------------------------------------------------------

def _transform_call(
    node: Call,
    ca: dict[str, str],
    fa: dict[str, str],
) -> Expr:
    """Handle method-style DSL calls on characters."""
    target = node.target
    args = tuple(transform(a, ca, fa) for a in node.args)

    if isinstance(target, Attribute) and len(target.parts) == 1:
        method = target.parts[0]
        root = target.root

        # Character.has("trait") → Character.check_trait("trait")
        if method == "has" and len(args) == 1:
            return Call(
                target=Attribute(root=root, parts=("check_trait",), col_offset=target.col_offset),
                args=args,
                col_offset=node.col_offset,
            )

        # Character.friends_with(Y) → are_Characters_friends(Character, Y)
        if method == "friends_with" and len(args) == 1:
            return Call(
                target=Name("are_Characters_friends", col_offset=node.col_offset),
                args=(Name(root.name, col_offset=root.col_offset), args[0]),
                col_offset=node.col_offset,
            )

        # Character.did("event") → Character.History.check("event") > 0
        if method == "did" and len(args) == 1:
            return Compare(
                left=Call(
                    target=Attribute(
                        root=root,
                        parts=("History", "check"),
                        col_offset=target.col_offset,
                    ),
                    args=args,
                    col_offset=node.col_offset,
                ),
                ops_and_rights=(
                    (">", Literal(0)),
                ),
                col_offset=node.col_offset,
            )

        # Character.personality("trait") → Character.check_personality("trait")
        if method == "personality" and len(args) in (1, 2):
            return Call(
                target=Attribute(root=root, parts=("check_personality",), col_offset=target.col_offset),
                args=args,
                col_offset=node.col_offset,
            )

    return Call(target=target, args=args, col_offset=node.col_offset)


# ---------------------------------------------------------------------------
# Attribute rewrites (bare property access in boolean context)
# ---------------------------------------------------------------------------

def _transform_attribute(node: Attribute, ca: dict[str, str]) -> Expr:
    """Handle ``Character.nearby`` → ``Character_is_in_close_proximity(Character)``."""
    if len(node.parts) == 1 and node.parts[0] == "nearby":
        return Call(
            target=Name("Character_is_in_close_proximity", col_offset=node.col_offset),
            args=(Name(node.root.name, col_offset=node.root.col_offset),),
            col_offset=node.col_offset,
        )
    return node
