"""Tests for the FX side of ``scripts/import_thumbnails.py``.

The importer files each FX thumbnail under the name ``_fx_mapping.yaml``
gives it, and the editor looks thumbnails up by allowlisted name. When the
game renamed two effects, the mapping kept the old names: every source file
was still found, the importer printed a full match, and the editor showed no
thumbnail for either effect. These tests pin the report that makes that
visible.

The script is loaded by path (``scripts/`` is not a package) and its resize
step is replaced, so the tests need no Pillow.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "import_thumbnails.py"


@pytest.fixture
def importer(tmp_path, monkeypatch):
    """Load the script with its allowlist and output folders under tmp_path."""
    spec = importlib.util.spec_from_file_location("import_thumbnails_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setattr(module, "ALLOWLISTS_DIR", tmp_path / "allowlists")
    monkeypatch.setattr(module, "OUTPUT_DIR", tmp_path / "thumbnails")
    monkeypatch.setattr(module, "_resize_and_save", lambda src, dst, width: None)

    return module


def _write_allowlist(tmp_path: Path, names: list[str]) -> None:
    folder = tmp_path / "allowlists"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "fx.yaml").write_text(
        yaml.safe_dump({"effects": [{"name": name} for name in names]}),
        encoding="utf-8",
    )


def _write_effects(tmp_path: Path, mapping: dict[str, str]) -> Path:
    effects = tmp_path / "effects"
    effects.mkdir()
    for filename in mapping:
        (effects / filename).write_bytes(b"")
    (effects / "_fx_mapping.yaml").write_text(
        yaml.safe_dump({"effects": mapping}),
        encoding="utf-8",
    )
    return effects


def test_a_mapped_name_missing_from_the_allowlist_is_reported(importer, tmp_path, capsys):
    _write_allowlist(tmp_path, ["spark_burst", "unsheathe_blades"])
    effects = _write_effects(tmp_path, {
        "spark.png": "spark_burst",
        "blades.png": "unsheathes_blades",
    })

    result = importer._process_fx(effects, 200)
    out = capsys.readouterr().out

    # both source files exist, so the file count alone still reads as complete
    assert "FX: 2/2 matched" in out
    assert "WARNING: 1 mapped FX name(s) not in fx.yaml" in out
    assert "unsheathes_blades (closest allowlisted name: unsheathe_blades)" in out
    assert "spark_burst (" not in out
    assert set(result) == {"spark_burst", "unsheathes_blades"}


def test_a_mapping_the_allowlist_covers_prints_no_warning(importer, tmp_path, capsys):
    _write_allowlist(tmp_path, ["spark_burst"])
    effects = _write_effects(tmp_path, {"spark.png": "spark_burst"})

    importer._process_fx(effects, 200)
    out = capsys.readouterr().out

    assert "FX: 1/1 matched" in out
    assert "WARNING" not in out


def test_an_unknown_name_with_no_close_match_gets_no_hint(importer, tmp_path, capsys):
    _write_allowlist(tmp_path, ["spark_burst"])

    unknown = importer._report_unknown_fx_names(["zzz"])
    out = capsys.readouterr().out

    assert unknown == ["zzz"]
    assert "    zzz\n" in out


def test_without_an_fx_allowlist_the_names_are_said_to_be_unchecked(importer, tmp_path, capsys):
    effects = _write_effects(tmp_path, {"spark.png": "spark_burst"})

    result = importer._process_fx(effects, 200)
    out = capsys.readouterr().out

    assert "FX names not checked: no effects in" in out
    assert "WARNING" not in out
    assert set(result) == {"spark_burst"}
