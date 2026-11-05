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


def test_an_effect_kept_in_a_named_store_loads_its_call_path(tmp_path: Path) -> None:
    # TNH 0.9c.beta.28 keeps a character's animations in a named store; the
    # writer types the flat name, the scene calls the function's home.
    _write(tmp_path / "fx.yaml", (
        "effects:\n"
        "- name: LauraKinney_animations_sheathe_claws\n"
        "  signature: LauraKinney_animations_sheathe_claws(x = 0.675) -> None\n"
        "  call: CHARACTERS.LauraKinney.animations.sheathe_claws\n"
        "- name: phone_buzz\n"
        "  signature: phone_buzz() -> None\n"
    ))

    allowlists = Allowlists.load(tmp_path)

    assert allowlists.fx_calls["LauraKinney_animations_sheathe_claws"] == "CHARACTERS.LauraKinney.animations.sheathe_claws"
    assert allowlists.fx_calls["phone_buzz"] == ""


def test_a_project_effect_of_the_same_name_drops_the_base_call_path(tmp_path: Path) -> None:
    # A project redefining a base effect calls its own function, by its name.
    base, project = tmp_path / "base", tmp_path / "project"
    base.mkdir()
    project.mkdir()
    _write(base / "fx.yaml", (
        "effects:\n"
        "- name: bamf\n"
        "  signature: bamf() -> None\n"
        "  call: displayables.effects.bamf\n"
    ))
    _write(project / "fx_custom.yaml", (
        "effects:\n"
        "- name: bamf\n"
        "  signature: bamf(override) -> None\n"
    ))

    assert Allowlists.load(base).merge(Allowlists.load(project)).fx_calls["bamf"] == ""

    _write(base / "fx_custom.yaml", (
        "effects:\n"
        "- name: bamf\n"
        "  signature: bamf(override) -> None\n"
    ))
    assert Allowlists.load(base).fx_calls["bamf"] == ""


def test_missing_fx_custom_is_tolerated(tmp_path: Path) -> None:
    _write(tmp_path / "fx.yaml", (
        "effects:\n"
        "- name: bamf\n"
        "  signature: bamf() -> None\n"
    ))

    allowlists = Allowlists.load(tmp_path)

    assert allowlists.fx == {"bamf"}
