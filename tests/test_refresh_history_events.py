"""Tests for the history_events extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import history_events


def test_extracts_history_events(mini_context):
    result = history_events.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert {"kissed_player", "fought_villain", "visited_library"}.issubset(names)


def test_ignores_commented_and_docstring(mini_context):
    result = history_events.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert "commented_event" not in names
    assert "docstring_event" not in names


def test_deduplicates(mini_context):
    result = history_events.extract(mini_context)
    names = [entry.name for entry in result.entries]
    assert len(names) == len(set(names))


def test_category(mini_context):
    result = history_events.extract(mini_context)
    assert result.category == "history_events"


def test_tnh_excluded_when_flag_off(mini_mod_only_context):
    result = history_events.extract(mini_mod_only_context)
    assert result.entries == []
