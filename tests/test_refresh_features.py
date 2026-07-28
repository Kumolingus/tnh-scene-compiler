"""Tests for the per-character features extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import features


def test_extracts_each_characters_own_set(mini_context):
    result = features.extract(mini_context)

    assert {entry.name for entry in result.per_character["Alpha"]} == {
        "chatting", "date", "flirt",
    }
    assert {entry.name for entry in result.per_character["Beta"]} == {"chatting"}


def test_sets_are_not_flattened_across_characters(mini_context):
    # The whole point of extracting per character: Beta must not inherit
    # Alpha's features just because they share a source file.
    result = features.extract(mini_context)
    beta = {entry.name for entry in result.per_character["Beta"]}
    assert "date" not in beta


def test_deduplicates_within_a_character(mini_context):
    result = features.extract(mini_context)
    names = [entry.name for entry in result.per_character["Alpha"]]
    assert names.count("date") == 1


def test_captures_line_numbers(mini_context):
    result = features.extract(mini_context)
    entry = next(e for e in result.per_character["Alpha"] if e.name == "flirt")
    assert entry.source_line > 0
    assert entry.source_file.endswith("features.rpy")


def test_no_subgroup(mini_context):
    result = features.extract(mini_context)
    for entries in result.per_character.values():
        for entry in entries:
            assert entry.subgroup is None
