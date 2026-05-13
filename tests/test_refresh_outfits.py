"""Tests for the outfits extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import outfits


def test_extracts_alpha_outfits(mini_context):
    result = outfits.extract(mini_context)
    alpha = {entry.name for entry in result.per_character["Alpha"]}
    assert alpha == {"Casual 1", "Hero"}


def test_deduplicates_same_name(mini_context):
    """The fixture declares 'Casual 1' twice; it should appear once."""
    result = outfits.extract(mini_context)
    alpha_entries = result.per_character["Alpha"]
    names = [entry.name for entry in alpha_entries]
    assert names.count("Casual 1") == 1


def test_captures_line_numbers(mini_context):
    result = outfits.extract(mini_context)
    casual = next(entry for entry in result.per_character["Alpha"] if entry.name == "Casual 1")
    assert casual.source_line > 0


def test_no_subgroup(mini_context):
    result = outfits.extract(mini_context)
    for entries in result.per_character.values():
        for entry in entries:
            assert entry.subgroup is None
