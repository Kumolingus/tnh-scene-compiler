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


def _panel(dlg, index=0):
    """The _ConditionClausePanel of the *index*-th clause row."""
    return dlg._clauses[index]["panel"]


def test_starts_with_one_clause_and_no_operator(tk_root, allow) -> None:
    dlg = _make_dialog(tk_root, allow)
    assert len(dlg._clauses) == 1
    assert dlg._clauses[0]["op_var"] is None  # first clause has no operator


def test_add_and_remove_clauses(tk_root, allow) -> None:
    dlg = _make_dialog(tk_root, allow)
    dlg._add_clause()
    dlg._add_clause()
    assert len(dlg._clauses) == 3
    # Every clause after the first carries an operator, defaulting to AND.
    assert dlg._clauses[1]["op_var"].get() == "AND"
    assert dlg._clauses[2]["op_var"].get() == "AND"

    third = dlg._clauses[2]
    dlg._remove_clause(third)
    assert len(dlg._clauses) == 2
    assert third not in dlg._clauses


def test_many_clauses_join_with_their_operators(tk_root, allow) -> None:
    dlg = _make_dialog(tk_root, allow)
    # Clause 1 defaults to the approval type (love/trust) — valid out of the box.
    dlg._add_clause()
    dlg._add_clause()
    dlg._clauses[2]["op_var"].set("OR")
    combined = dlg._build_current_condition()
    # Three approval clauses: "X.love >= 500 and X.love >= 500 or X.love >= 500".
    assert combined.count(" and ") == 1
    assert combined.count(" or ") == 1


def test_note_label_populates_for_tier_function(tk_root, allow) -> None:
    dlg = _make_dialog(tk_root, allow)
    clause = _panel(dlg, 0)
    # Switch to the standalone-function type; its only function is the tier one
    # carrying a note, which should surface in a note label.
    clause._type_var.set("Standalone function")
    clause._on_type_select()

    note_labels = [
        w for w in clause._param_frame.winfo_children()
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
    clause = _panel(dlg, 0)
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


@pytest.fixture()
def allow_properties() -> Allowlists:
    return Allowlists(
        characters=["JeanGrey", "Rogue"],
        characters_upper={"JEANGREY", "ROGUE"},
        character_properties={"desire", "breast_size"},
        character_property_types={"desire": "float", "breast_size": "int"},
        character_property_categories={"desire": "Arousal", "breast_size": "Body"},
    )


def test_property_type_builds_bare_attribute_comparison(
    tk_root, allow_properties,
) -> None:
    dlg = _make_dialog(tk_root, allow_properties)
    clause = _panel(dlg, 0)
    clause._type_var.set("Character property")
    clause._on_type_select()

    clause._vars["character"].set("JeanGrey")
    clause._vars["property_category"].set("Arousal")
    clause._vars["property_name"].set("desire")

    # A numeric property always offers a comparison row.
    assert clause._compare_op_var is not None
    assert clause.is_valid() is False  # operator, no value yet
    clause._compare_value_var.set("0.5")
    assert clause.is_valid() is True
    assert clause.get_condition() == "JeanGrey.desire >= 0.5"

    # "(no comparison)" -> bare property access.
    clause._compare_op_var.set("(no comparison)")
    assert clause.get_condition() == "JeanGrey.desire"
