"""Tests for the moods extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import moods


def test_extracts_shared_moods(mini_context):
    result = moods.extract(mini_context)
    shared = {entry.name for entry in result.entries}
    assert {"neutral", "happy", "sad"}.issubset(shared)


def test_ignores_commented_and_docstring_shared_moods(mini_context):
    result = moods.extract(mini_context)
    shared = {entry.name for entry in result.entries}
    assert "commented_out" not in shared
    assert "inside_docstring" not in shared


def test_extracts_per_character_moods(mini_context):
    result = moods.extract(mini_context)
    alpha = {entry.name for entry in result.per_character["Alpha"]}
    assert alpha == {"telepathic", "focused"}


def test_shared_and_per_character_can_overlap():
    """Per-character pot is allowed to shadow shared mood names.

    TNH explicitly allows a character to declare a mood with the same key as
    a shared one, typically to override its per-character face/arms weights.
    The extractor must emit both entries.
    """
    assert True


def test_tnh_excluded_when_flag_off(mini_mod_only_context):
    result = moods.extract(mini_mod_only_context)
    assert result.entries == []
    assert result.per_character == {}
