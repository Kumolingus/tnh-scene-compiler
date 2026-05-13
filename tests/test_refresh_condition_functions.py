"""Tests for the condition_functions extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import condition_functions


def test_extractor_returns_empty(mini_context):
    """The extractor itself never populates entries; the scaffold is main's job."""
    result = condition_functions.extract(mini_context)
    assert result.category == "condition_functions"
    assert result.entries == []
    assert result.per_character == {}
    assert result.warnings == []
