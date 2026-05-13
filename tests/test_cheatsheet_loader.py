"""Unit tests for :mod:`tnh_generate_cheatsheet.loader`."""

from __future__ import annotations

from pathlib import Path

from tnh_generate_cheatsheet.loader import load


def test_load_reports_meta_and_source_label(allowlists_dir: Path) -> None:
    data = load(allowlists_dir)

    assert data.generated_at == "2026-04-23"
    assert data.source_label == "TNH + Mod"
    assert data.warnings == []


def test_load_characters_returns_every_speaker(allowlists_dir: Path) -> None:
    data = load(allowlists_dir)

    names = [entry.name for entry in data.characters]
    assert names == ["JeanGrey", "Narrator", "Rogue"]


def test_load_locations_merges_overrides(allowlists_dir: Path) -> None:
    """``locations_overrides.yaml`` must win on matching names and be tagged."""
    data = load(allowlists_dir)

    by_name = {entry.name: entry for entry in data.locations}
    assert by_name["CLASSROOM"].provenance == "auto"
    assert by_name["KITCHEN"].provenance == "override"
    assert dict(by_name["KITCHEN"].metadata)["display_name"] == "Kitchen (manual override)"


def test_load_interpolation_concatenates_custom_paths(allowlists_dir: Path) -> None:
    data = load(allowlists_dir)

    names = [entry.name for entry in data.interpolation]
    provenances = {entry.name: entry.provenance for entry in data.interpolation}

    assert "day" in names
    assert "player.name" in names
    assert "mod.pregnancy_stage" in names
    assert provenances["mod.pregnancy_stage"] == "custom"
    assert provenances["day"] == "auto"


def test_load_condition_functions_keeps_signature(allowlists_dir: Path) -> None:
    data = load(allowlists_dir)

    assert len(data.condition_functions) == 1
    entry = data.condition_functions[0]
    meta = dict(entry.metadata)

    assert entry.name == "check_approval"
    assert "Character" in meta["signature"]
    assert meta["source_file"].endswith("approval.rpy")


def test_load_shared_moods_distinct_from_character_moods(allowlists_dir: Path) -> None:
    data = load(allowlists_dir)

    shared_names = [entry.name for entry in data.shared_moods]
    jean_mood_names = [entry.name for entry in data.per_character["JeanGrey"].moods]

    # Shared moods must stay at the top level, not duplicated on each character.
    assert set(shared_names).isdisjoint(jean_mood_names)
    assert "happy" in shared_names
    assert "focused" in jean_mood_names


def test_load_skips_characters_with_no_authoring_surface(allowlists_dir: Path) -> None:
    """Narrator is in characters.yaml but has no moods/faces/etc. -> excluded."""
    data = load(allowlists_dir)

    assert "Narrator" not in data.per_character
    assert "JeanGrey" in data.per_character
    assert "Rogue" in data.per_character


def test_load_arms_split_into_three_subgroups(allowlists_dir: Path) -> None:
    data = load(allowlists_dir)

    jean = data.per_character["JeanGrey"]
    assert [e.name for e in jean.arms] == ["crossed"]
    assert [e.name for e in jean.arms_left] == ["extended", "hip"]
    assert [e.name for e in jean.arms_right] == ["extended"]
