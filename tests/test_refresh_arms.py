"""Tests for the arms extractor (partitioned by subgroup)."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import arms


def _by_subgroup(entries):
    grouped: dict[str | None, set[str]] = {}
    for entry in entries:
        grouped.setdefault(entry.subgroup, set()).add(entry.name)
    return grouped


def test_alpha_has_three_subgroups(mini_context):
    result = arms.extract(mini_context)
    grouped = _by_subgroup(result.per_character["Alpha"])
    assert set(grouped.keys()) == {"arms", "left_arm", "right_arm"}


def test_alpha_arms_union_across_poses(mini_context):
    """Arms from both 'standing' and 'sitting' poses merge into one set."""
    result = arms.extract(mini_context)
    grouped = _by_subgroup(result.per_character["Alpha"])
    assert grouped["arms"] == {"crossed", "neutral", "lap"}
    assert grouped["left_arm"] == {"bra", "crossed", "hip", "neutral", "lap", "resting"}
    assert grouped["right_arm"] == {"crossed", "hip", "neutral", "lap", "resting", "phone"}


def test_no_duplicate_entries_per_slot(mini_context):
    result = arms.extract(mini_context)
    for entries in result.per_character.values():
        seen: set[tuple[str | None, str]] = set()
        for entry in entries:
            key = (entry.subgroup, entry.name)
            assert key not in seen
            seen.add(key)


def test_empty_when_no_poses(tmp_path):
    """An empty TNH + mod produces no arms entries."""
    from tnh_refresh_allowlists.models import ScanContext

    context = ScanContext(
        base_game_root = tmp_path / "tnh",
        project_root = tmp_path / "mod",
        repo_root = tmp_path,
        include_tnh = True,
    )
    result = arms.extract(context)
    assert result.per_character == {}
