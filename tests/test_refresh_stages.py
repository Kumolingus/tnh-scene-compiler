"""Tests for the stages extractor."""

from __future__ import annotations

from pathlib import Path

from tnh_refresh_allowlists.extractors import stages
from tnh_refresh_allowlists.models import ScanContext


def test_extracts_stage_constants(mini_context):
    result = stages.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert {"stage_far_left", "stage_left", "stage_center", "stage_middle", "stage_right", "stage_far_right"}.issubset(
        names,
    )


def test_ignores_non_stage_defines(mini_context):
    result = stages.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert "not_a_stage" not in names


def test_ignores_commented_out_definitions(mini_context):
    result = stages.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert "stage_commented_out" not in names


def test_ignores_docstring_contents(mini_context):
    result = stages.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert "stage_inside_docstring" not in names


def test_captures_line_numbers(mini_context):
    result = stages.extract(mini_context)
    far_left = next(entry for entry in result.entries if entry.name == "stage_far_left")
    assert far_left.source_line == 3


def test_no_extraction_when_include_tnh_is_false(mini_mod_only_context):
    result = stages.extract(mini_mod_only_context)
    assert result.entries == []


def test_warns_when_expected_file_missing(tmp_path):
    context = ScanContext(
        base_game_root = tmp_path,
        mod_root = tmp_path,
        repo_root = tmp_path,
        include_tnh = True,
    )
    result = stages.extract(context)
    assert result.entries == []
    assert len(result.warnings) == 1
    assert "definitions.rpy" in result.warnings[0].message
