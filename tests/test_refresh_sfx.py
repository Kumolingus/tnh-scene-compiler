"""Tests for the SFX extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import sfx


def test_extracts_tnh_and_mod_sfx(mini_context):
    result = sfx.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert {"knock", "door_open", "phone_buzz"}.issubset(names)


def test_excludes_tnh_when_flag_off(mini_mod_only_context):
    result = sfx.extract(mini_mod_only_context)
    names = {entry.name for entry in result.entries}
    assert "knock" not in names
    assert "door_open" not in names
    assert "phone_buzz" in names


def test_names_are_filename_stems(mini_context):
    result = sfx.extract(mini_context)
    assert all("." not in entry.name for entry in result.entries)


def test_deduplicates_by_name(tmp_path):
    """Two audio files with the same stem keep only the first discovered."""
    from tnh_refresh_allowlists.models import ScanContext

    sfx_dir = tmp_path / "TheNullHypothesis" / "game" / "sounds" / "effects"
    sfx_dir.mkdir(parents = True)
    (sfx_dir / "clang.ogg").write_bytes(b"")
    (sfx_dir / "clang.wav").write_bytes(b"")

    mod_sfx = tmp_path / "mod" / "game" / "mymod" / "sounds" / "sfx"
    mod_sfx.mkdir(parents = True)

    context = ScanContext(
        base_game_root = tmp_path / "TheNullHypothesis",
        mod_root = tmp_path / "mod",
        repo_root = tmp_path,
        include_tnh = True,
    )

    result = sfx.extract(context)
    clangs = [entry for entry in result.entries if entry.name == "clang"]
    assert len(clangs) == 1
