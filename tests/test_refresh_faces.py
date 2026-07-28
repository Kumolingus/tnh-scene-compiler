"""Tests for the faces extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import faces
from tnh_refresh_allowlists.models import ScanContext


def test_extracts_per_character(mini_context):
    result = faces.extract(mini_context)
    assert set(result.per_character.keys()) == {"Alpha", "Gamma"}


def test_alpha_has_expected_faces(mini_context):
    result = faces.extract(mini_context)
    alpha = {entry.name for entry in result.per_character["Alpha"]}
    assert alpha == {"neutral", "happy", "angry"}


def test_gamma_mod_faces(mini_context):
    result = faces.extract(mini_context)
    gamma = {entry.name for entry in result.per_character["Gamma"]}
    assert {"neutral", "mod_specific"}.issubset(gamma)


def test_ignores_commented_and_docstring_faces(mini_context):
    result = faces.extract(mini_context)
    alpha = {entry.name for entry in result.per_character["Alpha"]}
    assert "commented_out" not in alpha
    assert "inside_docstring" not in alpha


def test_no_subgroup_on_entries(mini_context):
    """Faces live in the default bucket; they are not subgrouped."""
    result = faces.extract(mini_context)
    for entries in result.per_character.values():
        for entry in entries:
            assert entry.subgroup is None


def test_tnh_excluded_when_flag_off(mini_mod_only_context):
    result = faces.extract(mini_mod_only_context)
    assert "Alpha" not in result.per_character
    assert "Gamma" in result.per_character


def test_dedupes_repeated_face_name(tmp_path):
    # The base game can declare the same face for one character at two lines
    # (e.g. LauraKinney "squint"). The extractor must emit the name once.
    tnh = tmp_path / "tnh"
    tnh.mkdir()
    (tnh / "expressions.rpy").write_text(
        'define Delta_faces["neutral"] = 1\n'
        'define Delta_faces["squint"] = 2\n'
        'define Delta_faces["squint"] = 3\n',
        encoding = "utf-8",
    )
    mod = tmp_path / "mod"
    mod.mkdir()
    context = ScanContext(
        base_game_root = tnh,
        project_root = mod,
        repo_root = tmp_path,
        include_tnh = True,
    )

    result = faces.extract(context)
    names = [entry.name for entry in result.per_character["Delta"]]

    # "squint" appears once; the first occurrence (line 2) is kept.
    assert names == ["neutral", "squint"]
    squint = next(e for e in result.per_character["Delta"] if e.name == "squint")
    assert squint.source_line == 2
