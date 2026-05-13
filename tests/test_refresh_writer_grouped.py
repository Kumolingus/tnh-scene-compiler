"""Tests for the per-character YAML writer with subgroup partitioning."""

from __future__ import annotations

from datetime import datetime, timezone

import yaml

from tnh_refresh_allowlists.models import AllowlistEntry, ExtractionResult
from tnh_refresh_allowlists.writer import write_per_character


def test_flat_entries_emit_values_key(tmp_path):
    result = ExtractionResult(
        category = "faces",
        per_character = {
            "Alpha": [
                AllowlistEntry(name = "happy", source_file = "a.rpy", source_line = 1),
                AllowlistEntry(name = "sad", source_file = "a.rpy", source_line = 2),
            ],
        },
    )
    paths = write_per_character(
        result,
        tmp_path,
        source_label = "TNH",
        generated_at = datetime(2026, 4, 23, tzinfo = timezone.utc),
    )
    assert len(paths) == 1
    data = yaml.safe_load(paths[0].read_text(encoding = "utf-8"))
    assert data["character"] == "Alpha"
    assert "values" in data
    assert [entry["name"] for entry in data["values"]] == ["happy", "sad"]


def test_subgrouped_entries_emit_partitioned_keys(tmp_path):
    result = ExtractionResult(
        category = "arms",
        per_character = {
            "Alpha": [
                AllowlistEntry(name = "crossed", source_file = "a.rpy", source_line = 1, subgroup = "arms"),
                AllowlistEntry(name = "bra", source_file = "a.rpy", source_line = 2, subgroup = "left_arm"),
                AllowlistEntry(name = "hip", source_file = "a.rpy", source_line = 3, subgroup = "left_arm"),
                AllowlistEntry(name = "phone", source_file = "a.rpy", source_line = 4, subgroup = "right_arm"),
            ],
        },
    )
    paths = write_per_character(
        result,
        tmp_path,
        source_label = "TNH",
        generated_at = datetime(2026, 4, 23, tzinfo = timezone.utc),
    )
    data = yaml.safe_load(paths[0].read_text(encoding = "utf-8"))
    assert {key for key in data if key.endswith("_arm") or key == "arms"} == {"arms", "left_arm", "right_arm"}
    assert "values" not in data
    assert [entry["name"] for entry in data["arms"]] == ["crossed"]
    assert [entry["name"] for entry in data["left_arm"]] == ["bra", "hip"]
    assert [entry["name"] for entry in data["right_arm"]] == ["phone"]
