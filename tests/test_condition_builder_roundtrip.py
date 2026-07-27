"""Every Condition Builder entry must produce a condition that COMPILES.

The rest of the builder suite asserts on the string ``get_condition()``
returns. That is not the same as the string being usable: three separate
defects shipped behind green tests because nothing fed the dialog's output
back through the parser and validator.

  * the character multi-select emitted a set literal ``{A, B}`` — rejected
    outright by the ``[[if]]`` grammar;
  * an empty multi-select emitted ``set()`` — not a registered condition
    function;
  * the date field's day form emitted ``(5, 2)`` — no tuple in the grammar.

So this module round-trips: build a clause through the real dialog against
the **shipped base allowlists** (what a writer actually gets), read the
condition back, and run it through ``parse`` + ``validate``. Every entry in
the catalog is swept, so a new allowlist entry with an unusable widget fails
here instead of in a writer's scene.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest

from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.condition_builder import (
    ConditionBuilderDialog,
    build_condition_catalog,
)
from tnh_scene_compiler.parser import parse
from tnh_scene_compiler.validator import validate

BASE_ALLOWLISTS = Path(__file__).resolve().parents[1] / "allowlists_base"

_HEAD = (
    "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
    "Scene Type: cinematic\nTrigger: manual\n\n"
)


@pytest.fixture(scope="module")
def base_allow() -> Allowlists:
    """The allowlists the packaged app ships with."""
    return Allowlists.load(BASE_ALLOWLISTS)


# ``tk_root`` is the session-scoped fixture in conftest.py — one root for the
# whole suite. A module-scoped one here would be a second tk.Tk() in the same
# process, which intermittently fails to re-init Tcl and skips this sweep.


def _labels() -> list[str]:
    """Every entry label in the catalog, for parametrisation."""
    allow = Allowlists.load(BASE_ALLOWLISTS)
    return [
        entry.label
        for entries in build_condition_catalog(allow).values()
        for entry in entries
    ]


def _select(clause, label: str) -> None:
    for category, entries in clause._catalog.items():
        if any(e.label == label for e in entries):
            clause._category_var.set(category)
            clause._condition_var.set(label)
            return
    raise AssertionError(f"no condition entry labelled {label!r}")


def assert_compiles(condition: str, allow: Allowlists) -> None:
    """The condition must survive both the [[if]] grammar and the validator."""
    assert condition, "an entry reported valid but produced an empty condition"
    scene = parse(_HEAD + f"[[if {condition}]]\nOk.\n[[/if]]\n", path="roundtrip.scene")
    errors = validate(scene, allow)
    assert errors == [], [e.message for e in errors]


@pytest.mark.parametrize("label", _labels())
def test_every_catalog_entry_compiles(tk_root, base_allow, label) -> None:
    dlg = ConditionBuilderDialog(
        tk_root, base_allow, lambda _t: None, characters=list(base_allow.characters),
    )
    clause = dlg._clauses[0]["panel"]
    _select(clause, label)

    # A comparable return offers an operator with no right-hand value; fill it
    # so the clause can reach validity on defaults alone.
    if clause._compare_op_var is not None and clause._compare_op_var.get():
        clause._compare_value_var.set("1")

    if not clause.is_valid():
        # The entry needs a free-text value the writer must type (a threshold,
        # an id with no declared choices). It cannot reach a scene unfilled, so
        # there is nothing to round-trip — but list it under `-rs` rather than
        # passing silently.
        pytest.skip(f"{label!r} needs a hand-typed value to become valid")

    assert_compiles(clause.get_condition(), base_allow)


def test_the_sweep_actually_covers_the_catalog() -> None:
    # Guards the parametrisation itself: an import-time failure that returned
    # an empty list would make every assertion above vacuous.
    assert len(_labels()) > 20


# -- Player / Narrator ---------------------------------------------------------

_ARGUMENT_ENTRIES = [
    "Love / Trust check",
    "Friendship check",
    "Nearby check",
    "In a relationship",
    "In a relationship, and the others know",
    "Friends (a group, at a tier)",
    "Effective friendship (tier)",
    "Best friend (of a group)",
]

# Entries whose character names the SUBJECT of an attribute or method rather
# than an argument. `Player.History` has 316 uses in the base game and
# `Player.check_trait` 109, so filtering the player here would remove more
# than it fixes.
_SUBJECT_ENTRIES = ["Trait check", "History check", "Chance of a repeat event"]


def _offered_names(clause) -> set[str]:
    """Every character name any picker in the form offers.

    A suffixed source yields ``Player.History``, so the leading name is what
    is compared — the question is whether the character is reachable, not
    how the value is spelled.
    """
    from tkinter import ttk

    names: set[str] = set()

    def walk(widget) -> None:
        for child in widget.winfo_children():
            if isinstance(child, ttk.Combobox):
                for item in child.cget("values"):
                    names.add(str(item).split(".")[0])
            walk(child)

    walk(clause._param_frame)
    for field in clause._func_params:
        for char, _var in field.char_vars or []:
            names.add(char)
    return names


def _build(tk_root, base_allow, label):
    dlg = ConditionBuilderDialog(
        tk_root, base_allow, lambda _t: None, characters=list(base_allow.characters),
    )
    clause = dlg._clauses[0]["panel"]
    _select(clause, label)
    return clause


@pytest.mark.parametrize("label", _ARGUMENT_ENTRIES)
def test_argument_pickers_offer_neither_player_nor_narrator(
    tk_root, base_allow, label: str,
) -> None:
    """Naming the player here is a category error, not a value that fails.

    `Player` is not in `all_Characters`, so no friendship record can involve
    it and `check_approval` returns 0 on sight; `Partners` is already the
    player's own set. The base game never passes it to one of these.
    """
    offered = _offered_names(_build(tk_root, base_allow, label))
    assert "Player" not in offered
    assert "Narrator" not in offered


@pytest.mark.parametrize("label", _SUBJECT_ENTRIES)
def test_subject_pickers_keep_the_player(tk_root, base_allow, label: str) -> None:
    offered = _offered_names(_build(tk_root, base_allow, label))
    assert "Player" in offered
    assert "Narrator" not in offered
