"""Tests for the traits extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import traits


def test_extracts_trait_names(mini_context):
    result = traits.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert {"shy", "romantic", "brave", "cowardly"}.issubset(names)


def test_ignores_commented_and_docstring_traits(mini_context):
    result = traits.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert "commented_out_trait" not in names
    assert "inside_docstring_trait" not in names


def test_deduplicates(mini_context):
    result = traits.extract(mini_context)
    names = [entry.name for entry in result.entries]
    assert len(names) == len(set(names))


def test_category(mini_context):
    result = traits.extract(mini_context)
    assert result.category == "traits"


def test_tnh_excluded_when_flag_off(mini_mod_only_context):
    result = traits.extract(mini_mod_only_context)
    assert result.entries == []
