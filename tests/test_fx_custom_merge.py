"""Allowlists.load merges fx.yaml (auto) with fx_custom.yaml (manual).

fx.yaml is regenerated on every refresh and holds base-game effects;
fx_custom.yaml is hand-maintained and never regenerated, so project/mod
effects survive a refresh. The loader must union both, with fx_custom
winning on name collisions.
"""

from __future__ import annotations

from pathlib import Path

from tnh_scene_compiler.allowlists import Allowlists


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_fx_custom_is_merged_into_loaded_fx(tmp_path: Path) -> None:
    _write(tmp_path / "fx.yaml", (
        "effects:\n"
        "- name: bamf\n"
        "  signature: bamf(x = 0.5) -> None\n"
        "  call_mode: label\n"
    ))
    _write(tmp_path / "fx_custom.yaml", (
        "effects:\n"
        "- name: mymod_do_thing\n"
        "  signature: 'mymod_do_thing(Character) -> None'\n"
    ))

    allowlists = Allowlists.load(tmp_path)

    # Both the auto base effect and the manual mod effect are present.
    assert "bamf" in allowlists.fx
    assert "mymod_do_thing" in allowlists.fx
    assert allowlists.fx_signatures["mymod_do_thing"] == "mymod_do_thing(Character) -> None"
    assert allowlists.fx_call_modes.get("bamf") == "label"


def test_fx_custom_wins_on_name_collision(tmp_path: Path) -> None:
    _write(tmp_path / "fx.yaml", (
        "effects:\n"
        "- name: shared_effect\n"
        "  signature: shared_effect() -> None\n"
        "  call_mode: label\n"
    ))
    _write(tmp_path / "fx_custom.yaml", (
        "effects:\n"
        "- name: shared_effect\n"
        "  signature: 'shared_effect(override) -> None'\n"
        "  call_mode: function\n"
    ))

    allowlists = Allowlists.load(tmp_path)

    assert allowlists.fx_signatures["shared_effect"] == "shared_effect(override) -> None"
    assert allowlists.fx_call_modes["shared_effect"] == "function"


def test_missing_fx_custom_is_tolerated(tmp_path: Path) -> None:
    _write(tmp_path / "fx.yaml", (
        "effects:\n"
        "- name: bamf\n"
        "  signature: bamf() -> None\n"
    ))

    allowlists = Allowlists.load(tmp_path)

    assert allowlists.fx == {"bamf"}
