"""One function, several named questions — the ``variants`` mechanism.

A parameter that *replaces* the question instead of refining it must not be
offered as a bare field: the writer would have to know the base game to
guess which question the default asks. `are_Characters_in_Partners`'s
``knows_about`` is the case that drove this — left at the game's default it
turns "is she the player's partner" into "…and every other partner knows
about her", which answers False for a real partner as soon as an
undisclosed second one exists.

Also covers ``param_collection_mode``, the sibling declaration: nothing in a
signature says whether a required character collection means "everyone in
the room" (how the game fills them) or a named cast, and guessing wrong
turns this entry into "is everyone present my partner".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tnh_scene_compiler.allowlists import (
    Allowlists,
    ConditionVariant,
    _read_collection_modes,
    _read_condition_variants,
)
from tnh_scene_compiler.condition_builder import (
    COLLECTION_MODE_PICK,
    COLLECTION_MODE_PRESENT,
    COLLECTION_MODE_VISIBLE,
    build_condition_catalog,
    default_collection_mode,
)

BASE_ALLOWLISTS = Path(__file__).resolve().parents[1] / "allowlists_base"


# -- Parsing ------------------------------------------------------------------


def test_reads_a_variant() -> None:
    variants = _read_condition_variants({
        "variants": [
            {"label": " Plain ", "fixed": {"flag": "False"}, "notes": " hi "},
        ],
    })
    assert variants == [ConditionVariant("Plain", {"flag": "False"}, "hi")]


def test_pinned_values_are_coerced_to_source_text() -> None:
    """YAML ``false`` would reach the scene as Python's ``False``."""
    variants = _read_condition_variants({
        "variants": [{"label": "L", "fixed": {"level": 2}}],
    })
    assert variants[0].fixed == {"level": "2"}


@pytest.mark.parametrize("payload", [
    {},                                                    # no variants key
    {"variants": "nope"},                                  # not a list
    {"variants": [{"label": "L"}]},                        # no pins
    {"variants": [{"label": "L", "fixed": {}}]},           # empty pins
    {"variants": [{"label": "  ", "fixed": {"a": "1"}}]},  # blank label
    {"variants": [{"fixed": {"a": "1"}}]},                 # no label
])
def test_malformed_variants_degrade_to_none(payload: dict) -> None:
    """A broken declaration leaves the function its ordinary single entry.

    Raising would take the whole allowlist down for one bad entry, and the
    fallback is a working catalog rather than a missing one.
    """
    assert _read_condition_variants(payload) == []


def test_reads_collection_modes() -> None:
    assert _read_collection_modes(
        {"param_collection_mode": {"Characters": " Pick "}},
    ) == {"Characters": "pick"}


@pytest.mark.parametrize("payload", [
    {}, {"param_collection_mode": "nope"}, {"param_collection_mode": {"a": 2}},
])
def test_malformed_collection_modes_degrade(payload: dict) -> None:
    assert _read_collection_modes(payload) == {}


# -- Collection mode ----------------------------------------------------------


@pytest.mark.parametrize(("pdefault", "declared", "expected"), [
    # Derived: required collection -> the game fills these from a location.
    ("", "", COLLECTION_MODE_PRESENT),
    # Derived: optional -> presuming everyone present changes the question.
    ("None", "", COLLECTION_MODE_PICK),
    # Declared wins over both derivations.
    ("", "pick", COLLECTION_MODE_PICK),
    ("None", "present", COLLECTION_MODE_PRESENT),
    ("", "visible", COLLECTION_MODE_VISIBLE),
    # A typo falls back to the derivation rather than emptying the field.
    ("", "picc", COLLECTION_MODE_PRESENT),
])
def test_default_collection_mode(
    pdefault: str, declared: str, expected: str,
) -> None:
    assert default_collection_mode(pdefault, declared) == expected


# -- Catalog ------------------------------------------------------------------


@pytest.fixture(scope="module")
def base_allow() -> Allowlists:
    return Allowlists.load(BASE_ALLOWLISTS)


def _relationship_entries(allow: Allowlists) -> list:
    return build_condition_catalog(allow)["Relationships"]


def test_partners_is_listed_once_per_variant(base_allow: Allowlists) -> None:
    entries = [
        e for e in _relationship_entries(base_allow)
        if e.target == "are_Characters_in_Partners"
    ]
    assert [e.label for e in entries] == [
        "In a relationship",
        "In a relationship, and the others know",
    ]
    assert [e.variant for e in entries] == [0, 1]


def test_a_variant_function_contributes_no_unpinned_entry(
    base_allow: Allowlists,
) -> None:
    """Listing the bare form beside the variants would be a third question.

    Its meaning would rest on a default the writer cannot see — the exact
    thing the split exists to remove.
    """
    entries = [
        e for e in _relationship_entries(base_allow)
        if e.target == "are_Characters_in_Partners"
    ]
    assert all(e.variant >= 0 for e in entries)


def test_functions_without_variants_are_unaffected(
    base_allow: Allowlists,
) -> None:
    friends = [
        e for e in _relationship_entries(base_allow)
        if e.target == "are_Characters_friends"
    ]
    assert len(friends) == 1
    assert friends[0].variant == -1


# -- Merge --------------------------------------------------------------------


def test_project_layer_replaces_a_functions_variants() -> None:
    """Whole-list replacement, not entry-by-entry.

    Merging variant by variant would let a project half-override a split and
    end up with two entries asking the same question.
    """
    base = Allowlists(
        condition_functions = {"f"},
        condition_function_variants = {
            "f": [ConditionVariant("A", {"x": "1"}), ConditionVariant("B", {"x": "2"})],
        },
    )
    project = Allowlists(
        condition_functions = {"f"},
        condition_function_variants = {"f": [ConditionVariant("C", {"x": "3"})]},
    )
    merged = base.merge(project)
    assert [v.label for v in merged.condition_function_variants["f"]] == ["C"]


def test_merge_carries_collection_modes() -> None:
    base = Allowlists(condition_function_collection_modes = {"f": {"Characters": "pick"}})
    merged = base.merge(Allowlists())
    assert merged.condition_function_collection_modes == {"f": {"Characters": "pick"}}
