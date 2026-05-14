"""Tests for the personalities extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import personalities


def test_extracts_personality_names(mini_context):
    result = personalities.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert {"bold", "sarcastic"}.issubset(names)


def test_ignores_commented_and_docstring(mini_context):
    result = personalities.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert "commented_personality" not in names
    assert "docstring_personality" not in names


def test_deduplicates(mini_context):
    result = personalities.extract(mini_context)
    names = [entry.name for entry in result.entries]
    assert len(names) == len(set(names))


def test_category(mini_context):
    result = personalities.extract(mini_context)
    assert result.category == "personalities"


def test_tnh_excluded_when_flag_off(mini_mod_only_context):
    result = personalities.extract(mini_mod_only_context)
    assert result.entries == []
