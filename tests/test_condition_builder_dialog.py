"""Tkinter-level regression tests for ConditionBuilderDialog.

The rest of the condition-builder suite is deliberately Tkinter-free (pure
helpers), so these live in their own module and skip cleanly when no display
is available (headless CI, no X server). They cover the stateful dialog
wiring that pure-logic tests can't reach: the second-clause (AND/OR)
lifecycle and the per-selection note label.
"""

from __future__ import annotations

import tkinter as tk

import pytest

from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.condition_builder import ConditionBuilderDialog


@pytest.fixture(scope="module")
def tk_root():
    """A single withdrawn Tk root shared by the module, or skip if no display.

    Module-scoped on purpose: creating and destroying a fresh ``tk.Tk()``
    per test in one process intermittently fails to re-init Tcl ("Can't find
    a usable init.tcl"), which would make these tests flaky-skip. One root
    for the module sidesteps that; each test still builds its own dialog
    (a Toplevel) on it.
    """
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no Tk display available: {exc}")
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


@pytest.fixture()
def allow() -> Allowlists:
    """Minimal allowlists with a tier function carrying a note."""
    return Allowlists(
        characters=["JeanGrey", "Rogue", "LauraKinney"],
        characters_upper={"JEANGREY", "ROGUE", "LAURAKINNEY"},
        traits={"shy", "bold"},
        condition_functions={"get_effective_friendship"},
        condition_function_signatures={
            "get_effective_friendship": (
                "get_effective_friendship(A: Character, B: Character) -> FriendshipTier"
            ),
        },
        condition_function_categories={"get_effective_friendship": "Relationships"},
        condition_function_notes={
            "get_effective_friendship": "Returns a tier NUMBER, compare it.",
        },
    )


def _make_dialog(root, allow):
    return ConditionBuilderDialog(
        root, allow, lambda _t: None, characters=list(allow.characters),
    )


def _combine_container_children(dlg):
    return dlg._clause_b_container.winfo_children()


def _count_separators(dlg):
    return sum(
        1 for w in _combine_container_children(dlg)
        if isinstance(w, tk.ttk.Separator)
    )


def test_second_clause_created_and_destroyed_on_toggle(tk_root, allow) -> None:
    dlg = _make_dialog(tk_root, allow)
    assert dlg._clause_b is None

    dlg._combine_var.set("AND")
    dlg._on_combine_change()
    assert dlg._clause_b is not None
    # winfo_manager() == "pack" once packed, "" after pack_forget — reliable
    # without a display, unlike winfo_ismapped() on a withdrawn root.
    assert dlg._clause_b_container.winfo_manager() == "pack"

    dlg._combine_var.set("Single condition")
    dlg._on_combine_change()
    assert dlg._clause_b is None
    assert dlg._clause_b_container.winfo_manager() == ""


def test_toggling_combine_does_not_accumulate_separators(tk_root, allow) -> None:
    # Regression: destroying only the panel (not the whole container) on the
    # "none" path used to leave the separator behind, so each none->AND cycle
    # stacked a fresh one.
    dlg = _make_dialog(tk_root, allow)

    for _ in range(4):
        dlg._combine_var.set("AND")
        dlg._on_combine_change()
        dlg._combine_var.set("Single condition")
        dlg._on_combine_change()

    dlg._combine_var.set("AND")
    dlg._on_combine_change()

    assert _count_separators(dlg) == 1


def test_and_or_switch_reuses_the_same_clause_b(tk_root, allow) -> None:
    dlg = _make_dialog(tk_root, allow)
    dlg._combine_var.set("AND")
    dlg._on_combine_change()
    clause_b = dlg._clause_b

    dlg._combine_var.set("OR")
    dlg._on_combine_change()
    # Switching operator between two non-none modes must not rebuild clause B.
    assert dlg._clause_b is clause_b
    assert _count_separators(dlg) == 1


def test_combined_condition_uses_the_operator(tk_root, allow) -> None:
    dlg = _make_dialog(tk_root, allow)
    # Clause A defaults to the approval type (love/trust) — valid out of the box.
    dlg._combine_var.set("AND")
    dlg._on_combine_change()
    combined = dlg._build_current_condition()
    assert " and " in combined


def test_note_label_populates_for_tier_function(tk_root, allow) -> None:
    dlg = _make_dialog(tk_root, allow)
    # Switch clause A to the standalone-function type; its only function is the
    # tier one carrying a note, which should surface in a note label.
    dlg._clause_a._type_var.set("Standalone function")
    dlg._clause_a._on_type_select()

    note_labels = [
        w for w in dlg._clause_a._param_frame.winfo_children()
        if isinstance(w, tk.ttk.Label)
        and w.cget("text") == "Returns a tier NUMBER, compare it."
    ]
    assert note_labels, "expected the tier function's note to be shown"


@pytest.fixture()
def allow_tier_and_bool() -> Allowlists:
    """One tier-returning function and one bool-returning function, same category."""
    return Allowlists(
        characters=["JeanGrey", "Rogue"],
        characters_upper={"JEANGREY", "ROGUE"},
        condition_functions={"get_effective_friendship", "are_Characters_friends"},
        condition_function_signatures={
            "get_effective_friendship": (
                "get_effective_friendship(A: Character, B: Character) -> FriendshipTier"
            ),
            "are_Characters_friends": "are_Characters_friends(Characters) -> bool",
        },
        condition_function_categories={
            "get_effective_friendship": "Relationships",
            "are_Characters_friends": "Relationships",
        },
    )


def test_comparison_widgets_appear_for_tier_and_vanish_for_bool(
    tk_root, allow_tier_and_bool,
) -> None:
    dlg = _make_dialog(tk_root, allow_tier_and_bool)
    clause = dlg._clause_a
    clause._type_var.set("Standalone function")
    clause._on_type_select()

    # Pick the tier function -> comparison widgets exist, default operator ">=".
    clause._vars["func_name"].set("get_effective_friendship")
    assert clause._compare_op_var is not None
    assert clause._compare_op_var.get() == ">="
    assert clause._compare_value_var is not None

    # Fill the two character arguments (A, B).
    clause._func_param_vars[0][2].set("JeanGrey")
    clause._func_param_vars[1][2].set("Rogue")

    # Operator set but no value -> not valid (would insert `... >= `).
    assert clause.is_valid() is False
    clause._compare_value_var.set("2")
    assert clause.is_valid() is True
    assert clause.get_condition() == "get_effective_friendship(JeanGrey, Rogue) >= 2"

    # Switch to the bool function -> no comparison widgets, bare call is valid.
    clause._vars["func_name"].set("are_Characters_friends")
    assert clause._compare_op_var is None
    assert clause._compare_value_var is None
    assert clause.is_valid() is True
