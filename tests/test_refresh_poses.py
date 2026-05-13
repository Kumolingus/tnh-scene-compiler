"""Tests for the poses extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import poses


def test_extracts_alpha_poses(mini_context):
    result = poses.extract(mini_context)
    alpha = {entry.name for entry in result.per_character["Alpha"]}
    assert alpha == {"standing", "sitting"}


def test_captures_line_numbers(mini_context):
    result = poses.extract(mini_context)
    standing = next(entry for entry in result.per_character["Alpha"] if entry.name == "standing")
    assert standing.source_line > 0


def test_no_subgroup(mini_context):
    result = poses.extract(mini_context)
    for entries in result.per_character.values():
        for entry in entries:
            assert entry.subgroup is None
