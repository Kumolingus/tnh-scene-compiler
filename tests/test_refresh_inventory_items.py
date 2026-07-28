"""Tests for the inventory-items extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import inventory_items


def test_extracts_every_all_items_key(mini_context):
    result = inventory_items.extract(mini_context)
    assert {entry.name for entry in result.entries} == {"flowers", "camera"}


def test_entries_are_flat_not_per_character(mini_context):
    # Items belong to the world, not to a character — unlike features.
    result = inventory_items.extract(mini_context)
    assert result.per_character == {}


def test_sorted_by_name(mini_context):
    result = inventory_items.extract(mini_context)
    names = [entry.name for entry in result.entries]
    assert names == sorted(names)


def test_captures_provenance(mini_context):
    result = inventory_items.extract(mini_context)
    entry = next(e for e in result.entries if e.name == "flowers")
    assert entry.source_line > 0
    assert entry.source_file.endswith("flowers.rpy")
