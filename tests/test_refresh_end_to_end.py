"""End-to-end smoke test of the refresh_allowlists CLI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

FIXTURES = Path(__file__).parent / "fixtures" / "refresh_allowlists"
PACKAGE_PARENT = Path(__file__).parent.parent


def _subprocess_env() -> dict[str, str]:
    """Return an env dict with PYTHONPATH pointing at the package parent."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    if existing:
        env["PYTHONPATH"] = f"{PACKAGE_PARENT}{os.pathsep}{existing}"
    else:
        env["PYTHONPATH"] = str(PACKAGE_PARENT)
    return env


def test_cli_runs_and_emits_expected_files(tmp_path):
    out_dir = tmp_path / "allowlists"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tnh_refresh_allowlists",
            "--base-game", str(FIXTURES / "mini_tnh"),
            "--mod", str(FIXTURES / "mini_mod"),
            "--out", str(out_dir),
            "--repo-root", str(FIXTURES),
        ],
        capture_output = True,
        text = True,
        check = False,
        env = _subprocess_env(),
    )

    assert completed.returncode == 0, completed.stderr

    for expected in ("characters.yaml", "stages.yaml", "sfx.yaml", "_meta.yaml"):
        assert (out_dir / expected).exists(), f"missing {expected}"

    characters = yaml.safe_load((out_dir / "characters.yaml").read_text(encoding = "utf-8"))
    names = {entry["name"] for entry in characters["values"]}
    assert {"Alpha", "Beta", "Gamma", "Player", "Narrator"}.issubset(names)

    stages_data = yaml.safe_load((out_dir / "stages.yaml").read_text(encoding = "utf-8"))
    stage_names = {entry["name"] for entry in stages_data["values"]}
    assert "stage_center" in stage_names

    sfx_data = yaml.safe_load((out_dir / "sfx.yaml").read_text(encoding = "utf-8"))
    sfx_names = {entry["name"] for entry in sfx_data["values"]}
    assert {"knock", "door_open", "phone_buzz"}.issubset(sfx_names)

    meta = yaml.safe_load((out_dir / "_meta.yaml").read_text(encoding = "utf-8"))
    assert meta["tool_version"] == "1.0.0"
    assert isinstance(meta["stats"], dict)
    assert meta["stats"]["characters"] >= 5


def test_cli_fails_when_no_characters_found(tmp_path):
    empty_tnh = tmp_path / "empty_tnh"
    (empty_tnh / "game").mkdir(parents = True)
    empty_mod = tmp_path / "empty_mod"
    (empty_mod / "game").mkdir(parents = True)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tnh_refresh_allowlists",
            "--base-game", str(empty_tnh),
            "--mod", str(empty_mod),
            "--out", str(tmp_path / "out"),
            "--repo-root", str(tmp_path),
        ],
        capture_output = True,
        text = True,
        check = False,
        env = _subprocess_env(),
    )

    assert completed.returncode == 1
    assert "no characters" in completed.stderr.lower()
