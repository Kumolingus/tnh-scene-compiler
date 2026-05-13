"""Tests for the manual-file scaffolding behaviour in __main__."""

from __future__ import annotations

from tnh_refresh_allowlists.__main__ import _MANUAL_SCAFFOLDS, _ensure_manual_scaffolds


_SCAFFOLD_NAMES = tuple(name for name, _ in _MANUAL_SCAFFOLDS)


def test_creates_all_scaffolds_on_empty_dir(tmp_path):
    out = tmp_path / "allowlists"
    written = _ensure_manual_scaffolds(out)
    assert written == len(_SCAFFOLD_NAMES)
    for name in _SCAFFOLD_NAMES:
        assert (out / name).exists()


def test_does_not_overwrite_existing_file(tmp_path):
    out = tmp_path / "allowlists"
    out.mkdir()

    custom_text = "overrides:\n  - slugline: TEST\n    location_id: loc_test\n"
    (out / "locations_overrides.yaml").write_text(custom_text, encoding = "utf-8")

    written = _ensure_manual_scaffolds(out)
    assert written == len(_SCAFFOLD_NAMES) - 1  # The other scaffolds still get created.
    assert (out / "locations_overrides.yaml").read_text(encoding = "utf-8") == custom_text


def test_all_scaffolds_are_valid_yaml(tmp_path):
    import yaml

    out = tmp_path / "allowlists"
    _ensure_manual_scaffolds(out)

    for name in _SCAFFOLD_NAMES:
        data = yaml.safe_load((out / name).read_text(encoding = "utf-8"))
        assert isinstance(data, dict)
