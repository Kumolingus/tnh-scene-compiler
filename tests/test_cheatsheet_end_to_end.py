"""Snapshot end-to-end test: load fixtures + render = pinned expected file.

The ``expected_cheatsheet.md`` fixture is refreshed on purpose when the
template or the rendering changes.
"""

from __future__ import annotations

from pathlib import Path

from tnh_generate_cheatsheet.loader import load
from tnh_generate_cheatsheet.renderer import render


def test_snapshot_matches_pinned_expected(
    allowlists_dir: Path,
    expected_cheatsheet_path: Path,
) -> None:
    data = load(allowlists_dir)

    actual = render(data)
    expected = expected_cheatsheet_path.read_text(encoding = "utf-8")

    assert actual == expected, (
        "Generated cheatsheet drifted from the pinned snapshot. "
        "Regenerate the fixture if the change is intentional."
    )


def test_render_is_deterministic_across_runs(allowlists_dir: Path) -> None:
    """Running the pipeline twice on the same input must yield identical output."""
    first = render(load(allowlists_dir))
    second = render(load(allowlists_dir))

    assert first == second
