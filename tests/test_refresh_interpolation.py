"""Tests for the interpolation extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import interpolation


def test_emits_player_baseline(mini_context):
    result = interpolation.extract(mini_context)
    names = {entry.name for entry in result.entries}
    # PascalCase required -- matches the TNH store variable ``Player``.
    assert {"Player.name", "Player.first_name", "Player.petname"}.issubset(names)


def test_emits_world_paths(mini_context):
    result = interpolation.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert {"day", "time_index", "season", "chapter"}.issubset(names)


def test_emits_per_character_paths(mini_context):
    result = interpolation.extract(mini_context)
    names = {entry.name for entry in result.entries}
    # Discovered characters in fixtures: Alpha, Beta (TNH), Gamma (mod).
    # PascalCase root is required.
    for character in ("Alpha", "Beta", "Gamma"):
        for suffix in ("name", "petname", "Player_petname"):
            assert f"{character}.{suffix}" in names


def test_all_entries_have_builtin_source(mini_context):
    result = interpolation.extract(mini_context)
    for entry in result.entries:
        assert entry.source_file == "<builtin>"


def test_excludes_tnh_characters_when_flag_off(mini_mod_only_context):
    result = interpolation.extract(mini_mod_only_context)
    names = {entry.name for entry in result.entries}
    # Alpha and Beta are TNH-only; Gamma is the mod character.
    assert "Alpha.name" not in names
    assert "Beta.name" not in names
    assert "Gamma.name" in names
