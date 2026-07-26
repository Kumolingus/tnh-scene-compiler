"""Tests for the per-character clothing extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import clothing_items


def test_emits_the_inventory_key_not_the_bare_id(mini_context):
    # InventoryClass.add files a garment under Item.tag, which is
    # f"{Owner.tag}_{string}" — the bare id would never match a lookup.
    result = clothing_items.extract(mini_context)

    assert {entry.name for entry in result.per_character["Alpha"]} == {
        "Alpha_blue_jeans", "Alpha_white_tshirt",
    }


def test_sets_are_not_flattened_across_characters(mini_context):
    result = clothing_items.extract(mini_context)
    beta = {entry.name for entry in result.per_character["Beta"]}

    assert beta == {"Beta_red_dress"}
    assert "Alpha_blue_jeans" not in beta


def test_deduplicates_within_a_character(mini_context):
    result = clothing_items.extract(mini_context)
    names = [entry.name for entry in result.per_character["Alpha"]]

    assert names.count("Alpha_blue_jeans") == 1


def test_captures_line_numbers(mini_context):
    result = clothing_items.extract(mini_context)
    entry = next(
        e for e in result.per_character["Alpha"] if e.name == "Alpha_white_tshirt"
    )

    assert entry.source_line > 0
    assert entry.source_file.endswith("items.rpy")


def test_no_subgroup(mini_context):
    result = clothing_items.extract(mini_context)

    for entries in result.per_character.values():
        for entry in entries:
            assert entry.subgroup is None
