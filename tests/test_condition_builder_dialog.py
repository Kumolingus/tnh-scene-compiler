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
from tkinter import ttk

import pytest

from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.condition_builder import (
    COLLECTION_MODE_PICK,
    COLLECTION_MODE_VISIBLE,
    ConditionBuilderDialog,
)


# ``tk_root`` is the session-scoped fixture in conftest.py. It used to live
# here, module-scoped; the second Tkinter-level module added to the suite then
# got a second ``tk.Tk()`` and started skipping at random. One root per session
# is the only shape that holds.


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
    # category; Advanced keeps only the character-method escape hatch, since
    # methods are the ones never promoted individually.
    rel = [e.label for e in clause._catalog["Relationships"]]
    assert "Love / Trust check" in rel
    assert "get_effective_friendship" in rel
    adv = [e.label for e in clause._catalog["Advanced"]]
    assert adv == ["Character method (any)"]


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
    clause._func_params[0].var.set("JeanGrey")
    clause._func_params[1].var.set("Rogue")

    # Operator set but no value -> not valid (would insert `... >= `).
    assert clause.is_valid() is False
    clause._compare_value_var.set("2")
    assert clause.is_valid() is True
    assert clause.get_condition() == "get_effective_friendship(JeanGrey, Rogue) >= 2"

    # Switch to the bool function -> no comparison widgets, bare call is valid.
    _select(clause, "Is ready")
    assert clause._compare_op_var is None
    assert clause._compare_value_var is None
    clause._func_params[0].var.set("JeanGrey")
    assert clause.get_condition() == "is_ready(JeanGrey)"
    assert clause.is_valid() is True


@pytest.fixture()
def allow_collection_and_choices() -> Allowlists:
    """A function with a Character-collection param, a bool, and a declared choice."""
    return Allowlists(
        characters=["JeanGrey", "Rogue", "LauraKinney"],
        characters_upper={"JEANGREY", "ROGUE", "LAURAKINNEY"},
        condition_functions={"get_best_Friend", "are_Characters_in_Partners"},
        condition_function_signatures={
            "get_best_Friend": (
                "get_best_Friend(Character, Characters) -> Character | None"
            ),
            "are_Characters_in_Partners": (
                "are_Characters_in_Partners(A: Character, B: Character, "
                "knows_about: bool = True) -> bool"
            ),
        },
        condition_function_categories={
            "get_best_Friend": "Relationships",
            "are_Characters_in_Partners": "Relationships",
        },
        condition_function_labels={
            "get_best_Friend": "Best friend (of a group)",
            "are_Characters_in_Partners": "In a relationship",
        },
        condition_function_param_choices={
            "are_Characters_in_Partners": {"knows_about": ["True", "False"]},
        },
    )


def test_character_collection_param_defaults_to_everyone_present(
    tk_root, allow_collection_and_choices,
) -> None:
    from tnh_scene_compiler.condition_builder import (
        PARAM_WIDGET_CHARACTER,
        PARAM_WIDGET_CHARACTER_SET,
    )

    dlg = _make_dialog(tk_root, allow_collection_and_choices)
    clause = _panel(dlg, 0)
    _select(clause, "Best friend (of a group)")

    # First param is a single Character; second is a Characters collection.
    assert clause._func_params[0].kind == PARAM_WIDGET_CHARACTER
    assert clause._func_params[1].kind == PARAM_WIDGET_CHARACTER_SET

    clause._func_params[0].var.set("JeanGrey")
    # A required collection leads with the form the game itself uses.
    assert clause.get_condition() == (
        "get_best_Friend(JeanGrey, get_present_Characters(get_Location()))"
    )

    clause._func_params[1].mode_var.set(COLLECTION_MODE_VISIBLE)
    clause._func_params[1].current_var.set(False)
    clause._func_params[1].var.set('"Jean\'s Room"')
    assert clause.get_condition() == (
        "get_best_Friend(JeanGrey, get_visible_Characters(\"Jean's Room\"))"
    )


def test_character_collection_param_builds_a_list_literal(
    tk_root, allow_collection_and_choices,
) -> None:
    dlg = _make_dialog(tk_root, allow_collection_and_choices)
    clause = _panel(dlg, 0)
    _select(clause, "Best friend (of a group)")

    clause._func_params[0].var.set("JeanGrey")
    clause._func_params[1].mode_var.set(COLLECTION_MODE_PICK)
    # Tick two of the three characters (checkbuttons follow the sorted order
    # the dialog imposes: JeanGrey, LauraKinney, Rogue).
    picks = dict(clause._func_params[1].char_vars)
    picks["Rogue"].set(True)
    picks["LauraKinney"].set(True)
    # A list, not a set: the [[if]] grammar has no set literal.
    assert clause.get_condition() == "get_best_Friend(JeanGrey, [LauraKinney, Rogue])"

    # No picks -> an explicit empty list, never a dangling comma.
    picks["Rogue"].set(False)
    picks["LauraKinney"].set(False)
    assert clause.get_condition() == "get_best_Friend(JeanGrey, [])"


def test_character_set_picker_opens_a_window_and_drives_the_list(
    tk_root, allow_collection_and_choices,
) -> None:
    dlg = _make_dialog(tk_root, allow_collection_and_choices)
    clause = _panel(dlg, 0)
    _select(clause, "Best friend (of a group)")
    field = clause._func_params[1]
    field.mode_var.set(COLLECTION_MODE_PICK)

    # The "Choose…" button opens a dedicated picker window.
    clause._open_character_set_picker(field.name, field.char_vars)
    pickers = [w for w in dlg.winfo_children() if isinstance(w, tk.Toplevel)]
    assert pickers, "the Choose… button should open a picker window"

    # Ticking there drives the very vars the field reads.
    clause._func_params[0].var.set("JeanGrey")
    dict(field.char_vars)["Rogue"].set(True)
    assert clause.get_condition() == "get_best_Friend(JeanGrey, [Rogue])"
    pickers[0].destroy()


def test_bool_and_declared_choice_params_build_the_call(
    tk_root, allow_collection_and_choices,
) -> None:
    from tnh_scene_compiler.condition_builder import PARAM_WIDGET_CHOICES

    dlg = _make_dialog(tk_root, allow_collection_and_choices)
    clause = _panel(dlg, 0)
    _select(clause, "In a relationship")

    # knows_about carries declared param_choices -> a (still editable) combo.
    knows = clause._func_params[2]
    assert knows.name == "knows_about"
    assert knows.kind == PARAM_WIDGET_CHOICES

    clause._func_params[0].var.set("JeanGrey")
    clause._func_params[1].var.set("Rogue")
    knows.var.set("False")
    assert clause.get_condition() == (
        "are_Characters_in_Partners(JeanGrey, Rogue, False)"
    )


@pytest.fixture()
def allow_location() -> Allowlists:
    """A function taking a Location param, with sluglines to suggest."""
    return Allowlists(
        characters=["JeanGrey", "Rogue"],
        characters_upper={"JEANGREY", "ROGUE"},
        locations={"Jean's Room": "loc_JeanRoom", "Danger Room": "loc_Danger"},
        condition_functions={"get_present_Characters"},
        condition_function_signatures={
            "get_present_Characters": "get_present_Characters(Location) -> set[Character]",
        },
        condition_function_categories={"get_present_Characters": "Location"},
        condition_function_labels={"get_present_Characters": "Characters present"},
    )


def test_location_param_defaults_to_current_then_takes_a_slugline(
    tk_root, allow_location,
) -> None:
    from tnh_scene_compiler.condition_builder import PARAM_WIDGET_LOCATION

    dlg = _make_dialog(tk_root, allow_location)
    clause = _panel(dlg, 0)
    _select(clause, "Characters present")

    field = clause._func_params[0]
    assert field.kind == PARAM_WIDGET_LOCATION
    # "Current location?" is on by default -> the current room, no typing needed.
    assert field.current_var.get() is True
    assert clause.get_condition() == "get_present_Characters(get_Location())"

    # Untick it and pick a slugline; it inserts quoted so it is a valid str arg.
    field.current_var.set(False)
    field.var.set('"Jean\'s Room"')
    assert clause.get_condition() == 'get_present_Characters("Jean\'s Room")'


@pytest.fixture()
def allow_optional_location() -> Allowlists:
    """get_Location itself: an *optional* location parameter."""
    return Allowlists(
        characters=["JeanGrey"],
        characters_upper={"JEANGREY"},
        locations={"Jean's Room": "loc_JeanRoom"},
        condition_functions={"get_Location"},
        condition_function_signatures={
            "get_Location": "get_Location(location: str | None = None) -> Location | None",
        },
        condition_function_categories={"get_Location": "Location"},
        condition_function_labels={"get_Location": "Get a location"},
    )


def test_optional_location_current_omits_the_argument(
    tk_root, allow_optional_location,
) -> None:
    dlg = _make_dialog(tk_root, allow_optional_location)
    clause = _panel(dlg, 0)
    _select(clause, "Get a location")
    field = clause._func_params[0]

    # Optional param + "Current location" on -> the arg is dropped, not nested:
    # get_Location(), never get_Location(get_Location()).
    assert field.omit_when_current is True
    assert clause.get_condition() == "get_Location()"

    field.current_var.set(False)
    field.var.set('"Jean\'s Room"')
    assert clause.get_condition() == 'get_Location("Jean\'s Room")'


@pytest.fixture()
def allow_dynamic_item() -> Allowlists:
    """chance_of_repeat_Event: Item pulls its suggestions from history_events."""
    return Allowlists(
        characters=["JeanGrey"],
        characters_upper={"JEANGREY"},
        history_events={"kissed_player", "anal"},
        condition_functions={"chance_of_repeat_Event"},
        condition_function_signatures={
            "chance_of_repeat_Event": (
                "chance_of_repeat_Event(History, Item: str, chance: float = 0) -> float"
            ),
        },
        condition_function_categories={"chance_of_repeat_Event": "History"},
        condition_function_labels={"chance_of_repeat_Event": "Chance of a repeat event"},
        condition_function_param_choices={
            "chance_of_repeat_Event": {
                "Item": {"source": "history_events", "quote": True},
            },
        },
    )


def test_dynamic_source_param_renders_as_choices(tk_root, allow_dynamic_item) -> None:
    from tnh_scene_compiler.condition_builder import PARAM_WIDGET_CHOICES

    dlg = _make_dialog(tk_root, allow_dynamic_item)
    clause = _panel(dlg, 0)
    _select(clause, "Chance of a repeat event")

    item_field = clause._func_params[1]
    assert item_field.name == "Item"
    assert item_field.kind == PARAM_WIDGET_CHOICES

    clause._func_params[0].var.set("JeanGrey.History")
    item_field.var.set('"kissed_player"')
    assert clause.get_condition().startswith(
        'chance_of_repeat_Event(JeanGrey.History, "kissed_player"',
    )


def test_arriving_characters_is_also_a_multi_select(tk_root) -> None:
    from tnh_scene_compiler.condition_builder import (
        PARAM_WIDGET_BOOL,
        PARAM_WIDGET_CHARACTER_SET,
    )

    allow = Allowlists(
        characters=["JeanGrey", "Rogue"],
        characters_upper={"JEANGREY", "ROGUE"},
        condition_functions={"check_if_need_to_change"},
        condition_function_signatures={
            "check_if_need_to_change": (
                "check_if_need_to_change(Characters, arriving_Characters = None, "
                "check: bool = False) -> bool"
            ),
        },
        condition_function_categories={"check_if_need_to_change": "Clothing"},
        condition_function_labels={"check_if_need_to_change": "Needs to change clothes"},
    )
    dlg = _make_dialog(tk_root, allow)
    clause = _panel(dlg, 0)
    _select(clause, "Needs to change clothes")

    assert clause._func_params[0].kind == PARAM_WIDGET_CHARACTER_SET  # Characters
    assert clause._func_params[1].kind == PARAM_WIDGET_CHARACTER_SET  # arriving_Characters
    assert clause._func_params[2].kind == PARAM_WIDGET_BOOL  # clothing


@pytest.fixture()
def allow_date() -> Allowlists:
    return Allowlists(
        characters=["JeanGrey", "Rogue"],
        characters_upper={"JEANGREY", "ROGUE"},
        history_events={"kissed_player", "anal_sex"},
        condition_functions={"get_time_since"},
        condition_function_signatures={
            "get_time_since": "get_time_since(date: tuple[int, int]) -> int",
        },
        condition_function_categories={"get_time_since": "Time"},
        condition_function_labels={"get_time_since": "Periods since a date"},
    )


def test_date_tuple_param_defaults_to_the_event_form(tk_root, allow_date) -> None:
    from tnh_scene_compiler.condition_builder import PARAM_WIDGET_DATE

    dlg = _make_dialog(tk_root, allow_date)
    clause = _panel(dlg, 0)
    _select(clause, "Periods since a date")

    field = clause._func_params[0]
    assert field.kind == PARAM_WIDGET_DATE
    # Pre-picked first character + first event -> valid out of the box, no
    # writer typing `JeanGrey.History.check_when(...)` by hand.
    assert clause.get_condition() == (
        'get_time_since(JeanGrey.History.check_when("anal_sex"))'
    )

    field.date_char_var.set("Rogue")
    field.date_event_var.set("kissed_player")
    assert clause.get_condition() == (
        'get_time_since(Rogue.History.check_when("kissed_player"))'
    )


def test_date_tuple_param_keeps_the_day_and_period_form(tk_root, allow_date) -> None:
    from tnh_scene_compiler.condition_builder import DATE_MODE_DAY

    dlg = _make_dialog(tk_root, allow_date)
    clause = _panel(dlg, 0)
    _select(clause, "Periods since a date")

    field = clause._func_params[0]
    field.mode_var.set(DATE_MODE_DAY)
    # Defaults to day 0, Morning (index 0) -> a valid tuple out of the box.
    assert clause.get_condition() == "get_time_since((0, 0))"

    field.var.set("5")           # Day
    field.period_var.set("Evening")  # index 2
    assert clause.get_condition() == "get_time_since((5, 2))"


def test_date_event_form_blocks_insert_while_incomplete(tk_root, allow_date) -> None:
    dlg = _make_dialog(tk_root, allow_date)
    clause = _panel(dlg, 0)
    _select(clause, "Periods since a date")

    clause._compare_op_var.set(">=")
    clause._compare_value_var.set("4")
    assert clause.is_valid() is True

    # An empty half must not splice `get_time_since()` into the scene.
    clause._func_params[0].date_event_var.set("")
    assert clause.is_valid() is False


@pytest.fixture()
def allow_properties() -> Allowlists:
    # ``History`` is validator-only (``usable_bare: false`` in the YAML), so it
    # is in ``character_properties`` but not in ``character_properties_bare``.
    return Allowlists(
        characters=["JeanGrey", "Rogue"],
        characters_upper={"JEANGREY", "ROGUE"},
        character_properties={"desire", "breast_size", "History"},
        character_properties_bare={"desire", "breast_size"},
        character_property_types={
            "desire": "float", "breast_size": "int", "History": "object",
        },
        character_property_categories={
            "desire": "Arousal", "breast_size": "Body", "History": "History",
        },
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


def test_validator_only_property_is_not_offered_as_a_standalone_check(
    tk_root, allow_properties,
) -> None:
    # ``History`` is an object, so `[[if JeanGrey.History]]` is always true.
    # The validator accepts it (it is an argument of the repeat-event check),
    # but the picker must not present it as a check the writer can pick.
    dlg = _make_dialog(tk_root, allow_properties)
    clause = _panel(dlg, 0)
    _select(clause, "Character property")

    def _all_combo_values(widget: tk.Misc) -> set[str]:
        values: set[str] = set()
        if isinstance(widget, ttk.Combobox):
            values.update(widget.cget("values"))
        for child in widget.winfo_children():
            values.update(_all_combo_values(child))
        return values

    offered = _all_combo_values(clause)
    assert "desire" in offered          # the pick-list is populated at all
    assert "History" not in offered     # neither as a property nor a category


def test_character_param_prefills_instead_of_opening_blank(tk_root, allow) -> None:
    # A Character parameter rarely declares a default; left blank, its readonly
    # picker would splice an empty argument into the call.
    dlg = _make_dialog(tk_root, allow)
    clause = _panel(dlg, 0)
    _select(clause, "get_effective_friendship")

    assert [f.value() for f in clause._func_params] == ["JeanGrey", "JeanGrey"]
    assert clause.get_condition().startswith("get_effective_friendship(JeanGrey, JeanGrey)")


@pytest.fixture()
def allow_untyped_param() -> Allowlists:
    """A function whose second parameter has neither a type nor a default."""
    return Allowlists(
        characters=["JeanGrey", "Rogue"],
        characters_upper={"JEANGREY", "ROGUE"},
        condition_functions={"needs_a_tag"},
        condition_function_signatures={
            "needs_a_tag": "needs_a_tag(Character, tag) -> bool",
        },
        condition_function_categories={"needs_a_tag": "Relationships"},
    )


def test_empty_signature_field_blocks_insertion(tk_root, allow_untyped_param) -> None:
    # Without this guard the writer inserts `needs_a_tag(JeanGrey, )`, a syntax
    # error that only surfaces when the scene is compiled.
    dlg = _make_dialog(tk_root, allow_untyped_param)
    clause = _panel(dlg, 0)
    _select(clause, "needs_a_tag")

    assert clause.get_condition() == "needs_a_tag(JeanGrey, )"
    assert clause.is_valid() is False

    tag_field = next(f for f in clause._func_params if f.name == "tag")
    tag_field.var.set('"greeting"')
    assert clause.get_condition() == 'needs_a_tag(JeanGrey, "greeting")'
    assert clause.is_valid() is True


@pytest.fixture()
def allow_features() -> Allowlists:
    """Two methods, one of them fed by a per-character source."""
    return Allowlists(
        characters=["JeanGrey", "CharlesXavier"],
        characters_upper={"JEANGREY", "CHARLESXAVIER"},
        traits={"shy"},
        char_features={
            "JeanGrey": {"date", "flirt"},
            "CharlesXavier": {"chatting"},
        },
        character_methods={"feature_enabled", "check_trait"},
        character_method_signatures={
            "feature_enabled": "Character.feature_enabled(feature_name: str) -> bool",
            "check_trait": "Character.check_trait(trait: str) -> bool",
        },
        character_method_categories={
            "feature_enabled": "Features", "check_trait": "Traits",
        },
        character_method_param_choices={
            "feature_enabled": {"feature_name": {"source": "features", "quote": True}},
            "check_trait": {"trait": {"source": "traits", "quote": True}},
        },
    )


def _feature_options(clause):
    combo, _spec = clause._per_char_choice_widgets[0]
    return list(combo.cget("values"))


def test_per_character_choices_follow_the_character(tk_root, allow_features) -> None:
    dlg = _make_dialog(tk_root, allow_features)
    clause = _panel(dlg, 0)
    _select(clause, "Character method (any)")
    clause._vars["method_category"].set("Features")
    clause._vars["method_name"].set("feature_enabled")

    clause._vars["character"].set("JeanGrey")
    clause._on_character_changed()
    assert _feature_options(clause) == ['"date"', '"flirt"']

    clause._vars["character"].set("CharlesXavier")
    clause._on_character_changed()
    assert _feature_options(clause) == ['"chatting"']


def test_inventory_string_offers_items_and_that_characters_clothing(tk_root) -> None:
    # One inventory mapping holds both: plain items keyed by Item.string and
    # clothing keyed by Item.tag ("<Owner>_<id>"). One dropdown, both sets,
    # and the clothing half follows the character.
    allow = Allowlists(
        characters=["JeanGrey", "Rogue"],
        characters_upper={"JEANGREY", "ROGUE"},
        inventory_items={"flowers"},
        char_clothing_items={
            "JeanGrey": {"JeanGrey_white_tshirt"},
            "Rogue": {"Rogue_leather_jacket"},
        },
        character_methods={"get_active"},
        character_method_signatures={
            "get_active": "Character.Inventory.get_active(string: str) -> bool",
        },
        character_method_categories={"get_active": "Inventory"},
        character_method_param_choices={
            "get_active": {"string": {"source": "inventory_strings", "quote": True}},
        },
    )
    dlg = _make_dialog(tk_root, allow)
    clause = _panel(dlg, 0)
    _select(clause, "Character method (any)")
    clause._vars["method_category"].set("Inventory")
    clause._vars["method_name"].set("get_active")

    clause._vars["character"].set("JeanGrey")
    clause._on_character_changed()
    combo, _spec = clause._per_char_choice_widgets[0]
    assert list(combo.cget("values")) == ['"JeanGrey_white_tshirt"', '"flowers"']

    clause._vars["character"].set("Rogue")
    clause._on_character_changed()
    assert list(combo.cget("values")) == ['"Rogue_leather_jacket"', '"flowers"']


def test_switching_method_drops_the_destroyed_combo(tk_root, allow_features) -> None:
    # The per-character combos are rebuilt on every method change; a stale one
    # left registered would be reconfigured after Tk destroyed it (TclError).
    dlg = _make_dialog(tk_root, allow_features)
    clause = _panel(dlg, 0)
    _select(clause, "Character method (any)")
    clause._vars["method_category"].set("Features")
    clause._vars["method_name"].set("feature_enabled")
    assert len(clause._per_char_choice_widgets) == 1

    clause._vars["method_category"].set("Traits")
    clause._vars["method_name"].set("check_trait")
    assert clause._per_char_choice_widgets == []

    clause._vars["character"].set("CharlesXavier")
    clause._on_character_changed()  # must not raise


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
