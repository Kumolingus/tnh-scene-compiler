"""Tkinter-level regression tests for ConditionBuilderDialog.

The rest of the condition-builder suite is deliberately Tkinter-free (pure
helpers), so these live in their own module and skip cleanly when no display
is available (headless CI, no X server). They cover the stateful dialog
wiring that pure-logic tests can't reach: the multi-clause add/remove/join,
the two-level Category -> Condition selector, per-selection comparison/note
widgets, and the "?" glossary quick-access.
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


def _select(clause, label):
    """Pick a condition entry by its label via the two-level selector."""
    for category, entries in clause._catalog.items():
        if any(e.label == label for e in entries):
            clause._category_var.set(category)
            clause._condition_var.set(label)
            return
    raise AssertionError(f"no condition entry labelled {label!r}")


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
    # The tier function is promoted into the Relationships category (no label
    # in the fixture, so it shows under its name); selecting it should surface
    # its note.
    _select(clause, "get_effective_friendship")

    note_labels = [
        w for w in clause._param_frame.winfo_children()
        if isinstance(w, tk.ttk.Label)
        and w.cget("text") == "Returns a tier NUMBER, compare it."
    ]
    assert note_labels, "expected the tier function's note to be shown"


def test_catalog_groups_functions_by_category(tk_root, allow) -> None:
    dlg = _make_dialog(tk_root, allow)
    clause = _panel(dlg, 0)
    # The built-in checks and the promoted function share the Relationships
    # category; the generic escape hatches live under Advanced.
    rel = [e.label for e in clause._catalog["Relationships"]]
    assert "Love / Trust check" in rel
    assert "get_effective_friendship" in rel
    adv = [e.label for e in clause._catalog["Advanced"]]
    assert "Standalone function (any)" in adv
    assert "Character method (any)" in adv


@pytest.fixture()
def allow_tier_and_bool() -> Allowlists:
    """A tier-returning and a bool-returning function, both promotable.

    (Not ``are_Characters_friends`` for the bool one — that's a sugar
    duplicate excluded from the catalog.)
    """
    return Allowlists(
        characters=["JeanGrey", "Rogue"],
        characters_upper={"JEANGREY", "ROGUE"},
        condition_functions={"get_effective_friendship", "is_ready"},
        condition_function_signatures={
            "get_effective_friendship": (
                "get_effective_friendship(A: Character, B: Character) -> FriendshipTier"
            ),
            "is_ready": "is_ready(Character) -> bool",
        },
        condition_function_categories={
            "get_effective_friendship": "Relationships",
            "is_ready": "Relationships",
        },
        condition_function_labels={
            "get_effective_friendship": "Effective friendship (tier)",
            "is_ready": "Is ready",
        },
    )


def test_comparison_widgets_appear_for_tier_and_vanish_for_bool(
    tk_root, allow_tier_and_bool,
) -> None:
    dlg = _make_dialog(tk_root, allow_tier_and_bool)
    clause = _panel(dlg, 0)

    # Pick the tier function -> comparison widgets exist, default operator ">=".
    _select(clause, "Effective friendship (tier)")
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
    _select(clause, "Is ready")
    assert clause._compare_op_var is None
    assert clause._compare_value_var is None
    clause._func_param_vars[0][2].set("JeanGrey")
    assert clause.get_condition() == "is_ready(JeanGrey)"
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
    _select(clause, "Character property")

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


def test_glossary_button_opens_filtered_glossary(tk_root, allow) -> None:
    from tnh_scene_compiler.glossary import GlossaryDialog

    dlg = _make_dialog(tk_root, allow)
    clause = _panel(dlg, 0)
    clause._category_var.set("Relationships")
    clause._open_glossary()

    # The glossary opens as a child of the (modal) builder, pre-filtered.
    glossaries = [w for w in dlg.winfo_children() if isinstance(w, GlossaryDialog)]
    assert glossaries, "the ? button should open a glossary window"
    g = glossaries[0]
    titles = [g._listbox.get(i).strip() for i in range(g._listbox.size())]
    assert "Relationship conditions" in titles
    g.destroy()
