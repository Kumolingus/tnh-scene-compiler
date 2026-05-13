"""End-to-end snapshot test: parse + validate + codegen on real fixtures."""

from __future__ import annotations

from pathlib import Path

from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.codegen import CodegenContext, generate
from tnh_scene_compiler.parser import parse
from tnh_scene_compiler.validator import validate

_CTX = CodegenContext(mod_prefix = "testmod")


def _compile(text: str, path: str, allowlists: Allowlists) -> str:
    scene = parse(text, path = path)
    errors = validate(scene, allowlists)
    assert errors == []
    return generate(scene, allowlists, _CTX)


def test_minimal_scene_matches_snapshot(
    fixtures_dir: Path,
    allowlists: Allowlists,
) -> None:
    src = (fixtures_dir / "minimal_cinematic.scene").read_text(encoding = "utf-8")
    expected_path = fixtures_dir / "minimal_cinematic.expected.rpy"
    expected = expected_path.read_text(encoding = "utf-8")

    actual = _compile(src, "minimal.scene", allowlists)

    assert actual == expected, (
        "Generated .rpy drifted from snapshot. If the change is intentional, "
        "regenerate the fixture."
    )


def test_codegen_is_deterministic(fixtures_dir: Path, allowlists: Allowlists) -> None:
    src = (fixtures_dir / "minimal_cinematic.scene").read_text(encoding = "utf-8")
    first = _compile(src, "minimal.scene", allowlists)
    second = _compile(src, "minimal.scene", allowlists)

    assert first == second
