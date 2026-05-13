"""Tests for the characters extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import characters


def test_extracts_tnh_characters(mini_context):
    result = characters.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert {"Alpha", "Beta", "Gamma"}.issubset(names)


def test_adds_builtin_speakers(mini_context):
    result = characters.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert "Player" in names
    assert "Narrator" in names


def test_excludes_tnh_when_flag_off(mini_mod_only_context):
    result = characters.extract(mini_mod_only_context)
    names = {entry.name for entry in result.entries}
    assert "Alpha" not in names
    assert "Beta" not in names
    # Mod character still included.
    assert "Gamma" in names


def test_source_paths_are_relative_with_forward_slashes(mini_context):
    result = characters.extract(mini_context)
    alpha = next(entry for entry in result.entries if entry.name == "Alpha")
    assert "\\" not in alpha.source_file
    assert alpha.source_file.endswith("Alpha")


def test_builtin_speaker_marks_its_source_as_builtin(mini_context):
    result = characters.extract(mini_context)
    player = next(entry for entry in result.entries if entry.name == "Player")
    assert player.source_file == "<builtin>"
    assert player.source_line == 0


def test_mod_character_not_duplicated_when_same_name_exists_in_tnh(tmp_path, mini_context):
    # Build a fake mod that also declares Alpha.
    fake_mod = tmp_path / "fake_mod"
    (fake_mod / "game" / "mymod" / "characters" / "Alpha").mkdir(parents = True)
    (fake_mod / "game" / "mymod" / "characters" / "Alpha" / "character.rpy").write_text(
        "default Alpha = CompanionClass('Alpha')\n",
        encoding = "utf-8",
    )

    from tnh_refresh_allowlists.models import ScanContext

    context = ScanContext(
        base_game_root = mini_context.base_game_root,
        project_root = fake_mod,
        repo_root = tmp_path,
        include_tnh = True,
    )

    result = characters.extract(context)
    alpha_entries = [entry for entry in result.entries if entry.name == "Alpha"]
    assert len(alpha_entries) == 1
