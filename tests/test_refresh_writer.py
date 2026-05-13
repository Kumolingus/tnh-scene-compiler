"""Tests for the YAML writer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from tnh_refresh_allowlists.models import AllowlistEntry, ExtractionResult
from tnh_refresh_allowlists.writer import write_flat


def test_writes_sorted_entries(tmp_path):
    result = ExtractionResult(
        category = "demo",
        entries = [
            AllowlistEntry(name = "zebra", source_file = "a.rpy", source_line = 1),
            AllowlistEntry(name = "ant", source_file = "b.rpy", source_line = 2),
            AllowlistEntry(name = "monkey", source_file = "c.rpy", source_line = 3),
        ],
    )

    out_path = write_flat(
        result,
        tmp_path,
        source_label = "TNH",
        generated_at = datetime(2026, 4, 23, tzinfo = timezone.utc),
    )

    assert out_path == tmp_path / "demo.yaml"
    data = yaml.safe_load(out_path.read_text(encoding = "utf-8"))
    assert [entry["name"] for entry in data["values"]] == ["ant", "monkey", "zebra"]


def test_writes_stable_metadata(tmp_path):
    result = ExtractionResult(category = "empty", entries = [])
    out_path = write_flat(
        result,
        tmp_path,
        source_label = "TNH + Mod",
        generated_at = datetime(2026, 4, 23, 12, 0, tzinfo = timezone.utc),
    )
    data = yaml.safe_load(out_path.read_text(encoding = "utf-8"))
    assert data["source"] == "TNH + Mod"
    # Date-only -- hour and minute are intentionally discarded so
    # same-day refreshes don't produce spurious diffs.
    assert data["generated_at"] == "2026-04-23"
    assert data["values"] == []


def test_utf8_lf_no_bom(tmp_path):
    result = ExtractionResult(
        category = "utf",
        entries = [AllowlistEntry(name = "cafe", source_file = "x.rpy", source_line = 1)],
    )
    out_path = write_flat(
        result,
        tmp_path,
        source_label = "TNH",
        generated_at = datetime(2026, 4, 23, tzinfo = timezone.utc),
    )
    raw = out_path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")          # no BOM
    assert b"\r\n" not in raw                            # LF only
    assert "cafe".encode("utf-8") in raw                 # UTF-8 payload
