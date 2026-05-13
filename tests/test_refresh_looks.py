"""Tests for the looks extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import looks


def test_baseline_is_present(mini_context):
    result = looks.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert {"at_player", "away", "down", "up", "left", "right", "neutral"}.issubset(names)


def test_entries_are_builtin_sourced(mini_context):
    result = looks.extract(mini_context)
    for entry in result.entries:
        assert entry.source_file == "<builtin>"


def test_no_per_character_output(mini_context):
    """V1 looks is flat; no per-character partitioning yet."""
    result = looks.extract(mini_context)
    assert result.per_character == {}


def test_deterministic_order(mini_context):
    """Baseline order is deterministic (used for snapshot stability)."""
    result1 = looks.extract(mini_context)
    result2 = looks.extract(mini_context)
    assert [entry.name for entry in result1.entries] == [entry.name for entry in result2.entries]
