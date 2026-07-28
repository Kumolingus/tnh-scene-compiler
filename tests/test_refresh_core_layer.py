"""Tests for the core-duplicate filter applied to a mod-only refresh."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

from tnh_refresh_allowlists.core_layer import (
    filter_core_duplicates,
    load_core_layer,
)
from tnh_refresh_allowlists.models import AllowlistEntry, ExtractionResult

FIXTURES = Path(__file__).parent / "fixtures" / "refresh_allowlists"
PACKAGE_PARENT = Path(__file__).parent.parent


# --- helpers ------------------------------------------------------------------


def _entry(name: str, *, subgroup: str | None = None, **metadata: str) -> AllowlistEntry:
    """Build an entry the way an extractor would."""
    return AllowlistEntry(
        name = name,
        source_file = "PregnancyMod/game/mod/file.rpy",
        source_line = 1,
        subgroup = subgroup,
        metadata = tuple(metadata.items()),
    )


def _write_flat(core_dir: Path, filename: str, items: list, *, key: str = "values") -> None:
    """Write one flat core allowlist file."""
    core_dir.mkdir(parents = True, exist_ok = True)
    payload = {"source": "TNH", "generated_at": "2026-01-01", key: items}
    (core_dir / filename).write_text(
        yaml.safe_dump(payload, sort_keys = False), encoding = "utf-8",
    )


def _write_character(core_dir: Path, category: str, stem: str, groups: dict) -> None:
    """Write one per-character core allowlist file (``groups`` keyed by subgroup)."""
    target = core_dir / category
    target.mkdir(parents = True, exist_ok = True)
    payload: dict = {"character": stem, "source": "TNH", "generated_at": "2026-01-01"}
    payload.update(groups)
    (target / f"{stem}.yaml").write_text(
        yaml.safe_dump(payload, sort_keys = False), encoding = "utf-8",
    )


def _core_entry(name: str, **metadata) -> dict:
    """Build a core-layer YAML entry, with a source deliberately unlike the mod's."""
    item = {"name": name, "source_file": "game/core/base/thing.rpy", "source_line": 99}
    item.update(metadata)
    return item


def _run(results: list[ExtractionResult], core_dir: Path) -> list:
    """Load the core layer for these results' categories and filter them."""
    layer = load_core_layer(core_dir, [r.category for r in results])
    return filter_core_duplicates(results, layer)


# --- flat topics --------------------------------------------------------------


def test_value_the_core_already_carries_is_dropped(tmp_path):
    _write_flat(tmp_path, "traits.yaml", [_core_entry("birth_control")])
    result = ExtractionResult(
        category = "traits",
        entries = [_entry("birth_control"), _entry("pregnancy_mod_nesting")],
    )

    _run([result], tmp_path)

    assert [e.name for e in result.entries] == ["pregnancy_mod_nesting"]


def test_source_file_and_line_do_not_prevent_a_match(tmp_path):
    # The mod reads the trait at its own path and line; it is still the same
    # value, so those two fields must stay out of the comparison.
    _write_flat(tmp_path, "traits.yaml", [_core_entry("polyamorous")])
    result = ExtractionResult(category = "traits", entries = [_entry("polyamorous")])

    _run([result], tmp_path)

    assert result.entries == []


def test_a_category_the_core_does_not_carry_is_untouched(tmp_path):
    _write_flat(tmp_path, "traits.yaml", [_core_entry("birth_control")])
    result = ExtractionResult(category = "personalities", entries = [_entry("dominant")])

    warnings = _run([result], tmp_path)

    assert [e.name for e in result.entries] == ["dominant"]
    assert warnings == []


def test_a_companion_file_counts_as_core(tmp_path):
    # fx_custom.yaml extends fx.yaml inside the same layer, so a value declared
    # there is just as much "already in the core layer".
    _write_flat(tmp_path, "fx.yaml", [], key = "effects")
    _write_flat(
        tmp_path, "fx_custom.yaml",
        [_core_entry("bamf", signature = "bamf() -> None")],
        key = "effects",
    )
    result = ExtractionResult(
        category = "fx",
        entries = [_entry("bamf", signature = "bamf() -> None"), _entry("mod_glow")],
    )

    _run([result], tmp_path)

    assert [e.name for e in result.entries] == ["mod_glow"]


def test_bare_string_entries_are_read(tmp_path):
    # interpolation_custom.yaml lists plain dotted paths, not mappings.
    _write_flat(tmp_path, "interpolation.yaml", [])
    _write_flat(tmp_path, "interpolation_custom.yaml", ["Player.name"], key = "paths")
    result = ExtractionResult(
        category = "interpolation",
        entries = [_entry("Player.name"), _entry("Mephista.name")],
    )

    _run([result], tmp_path)

    assert [e.name for e in result.entries] == ["Mephista.name"]


# --- metadata is part of the key ----------------------------------------------


def test_same_name_and_same_metadata_is_a_duplicate(tmp_path):
    _write_flat(
        tmp_path, "locations.yaml",
        [_core_entry("THE LAB", location_id = "loc_Lab", display_name = "The Lab")],
    )
    result = ExtractionResult(
        category = "locations",
        entries = [_entry("THE LAB", location_id = "loc_Lab", display_name = "The Lab")],
    )

    _run([result], tmp_path)

    assert result.entries == []


def test_same_name_but_different_metadata_survives(tmp_path):
    # merge() resolves a slugline through a dict the project layer wins, so
    # dropping this entry would silently reroute the scene to the game's room.
    _write_flat(
        tmp_path, "locations.yaml",
        [_core_entry("THE LAB", location_id = "loc_Lab", display_name = "The Lab")],
    )
    result = ExtractionResult(
        category = "locations",
        entries = [
            _entry("THE LAB", location_id = "loc_ModLab", display_name = "The Lab"),
        ],
    )

    warnings = _run([result], tmp_path)

    assert [e.name for e in result.entries] == ["THE LAB"]
    assert warnings == []


def test_a_differing_fx_signature_survives(tmp_path):
    _write_flat(
        tmp_path, "fx.yaml",
        [_core_entry("bamf", signature = "bamf(x = 0.5) -> None", call_mode = "label")],
        key = "effects",
    )
    result = ExtractionResult(
        category = "fx",
        entries = [_entry("bamf", signature = "bamf(x, y) -> None", call_mode = "label")],
    )

    _run([result], tmp_path)

    assert [e.name for e in result.entries] == ["bamf"]


def test_metadata_field_order_does_not_matter(tmp_path):
    _write_flat(
        tmp_path, "moods.yaml",
        [_core_entry("wistful", faces = "sad1,sad2", extra = "x")],
    )
    result = ExtractionResult(
        category = "moods",
        entries = [_entry("wistful", extra = "x", faces = "sad1,sad2")],
    )

    _run([result], tmp_path)

    assert result.entries == []


# --- per-character topics -----------------------------------------------------


def test_per_character_duplicate_is_dropped_for_that_character_only(tmp_path):
    _write_character(tmp_path, "faces", "JeanGrey", {"values": [_core_entry("smirk")]})
    result = ExtractionResult(
        category = "faces",
        per_character = {
            "JeanGrey": [_entry("smirk"), _entry("mod_blush")],
            "Rogue": [_entry("smirk")],
        },
    )

    _run([result], tmp_path)

    assert [e.name for e in result.per_character["JeanGrey"]] == ["mod_blush"]
    assert [e.name for e in result.per_character["Rogue"]] == ["smirk"]


def test_a_shared_core_value_masks_a_per_character_entry(tmp_path):
    # A shared mood is valid for every character, so a project entry filed
    # under one of them adds nothing.
    _write_character(tmp_path, "moods", "_shared", {"values": [_core_entry("happy")]})
    result = ExtractionResult(
        category = "moods",
        per_character = {"JeanGrey": [_entry("happy"), _entry("mod_broody")]},
    )

    _run([result], tmp_path)

    assert [e.name for e in result.per_character["JeanGrey"]] == ["mod_broody"]


def test_a_per_character_core_value_does_not_mask_a_shared_entry(tmp_path):
    # The reverse does not hold: dropping this would narrow the mood from
    # every character down to the one the core happens to declare it for.
    _write_character(tmp_path, "moods", "JeanGrey", {"values": [_core_entry("focused")]})
    result = ExtractionResult(category = "moods", entries = [_entry("focused")])

    _run([result], tmp_path)

    assert [e.name for e in result.entries] == ["focused"]


def test_subgroups_do_not_cross_match(tmp_path):
    _write_character(
        tmp_path, "arms", "JeanGrey",
        {"left_arm": [_core_entry("bra")], "values": []},
    )
    result = ExtractionResult(
        category = "arms",
        per_character = {
            "JeanGrey": [
                _entry("bra", subgroup = "left_arm"),
                _entry("bra", subgroup = "right_arm"),
            ],
        },
    )

    _run([result], tmp_path)

    kept = [(e.subgroup, e.name) for e in result.per_character["JeanGrey"]]
    assert kept == [("right_arm", "bra")]


def test_a_character_left_with_nothing_gets_no_file(tmp_path):
    # An emptied character must disappear from the result, or the writer emits
    # a file declaring an empty list of additions.
    _write_character(tmp_path, "faces", "Rogue", {"values": [_core_entry("glare")]})
    result = ExtractionResult(
        category = "faces",
        per_character = {"Rogue": [_entry("glare")], "JeanGrey": [_entry("mod_blush")]},
    )

    _run([result], tmp_path)

    assert list(result.per_character) == ["JeanGrey"]


# --- warnings -----------------------------------------------------------------


def test_the_warning_names_the_topic_and_every_dropped_value(tmp_path):
    _write_flat(
        tmp_path, "traits.yaml",
        [_core_entry("birth_control"), _core_entry("polyamorous")],
    )
    result = ExtractionResult(
        category = "traits",
        entries = [_entry("birth_control"), _entry("mod_only"), _entry("polyamorous")],
    )

    warnings = _run([result], tmp_path)

    assert len(warnings) == 1
    message = warnings[0].message
    assert message.startswith("traits: 2 value(s) already in the core allowlists")
    assert "birth_control" in message
    assert "polyamorous" in message
    assert "mod_only" not in message


def test_the_warning_is_recorded_on_the_result(tmp_path):
    # _write_meta reads result.warnings, so this is what puts the report in
    # _meta.yaml without any new plumbing.
    _write_flat(tmp_path, "traits.yaml", [_core_entry("birth_control")])
    result = ExtractionResult(category = "traits", entries = [_entry("birth_control")])

    warnings = _run([result], tmp_path)

    assert result.warnings == warnings


def test_a_per_character_warning_names_the_character(tmp_path):
    _write_character(tmp_path, "faces", "JeanGrey", {"values": [_core_entry("smirk")]})
    result = ExtractionResult(
        category = "faces", per_character = {"JeanGrey": [_entry("smirk")]},
    )

    warnings = _run([result], tmp_path)

    assert "JeanGrey: smirk" in warnings[0].message


def test_a_subgroup_shows_in_the_warning(tmp_path):
    _write_character(tmp_path, "arms", "JeanGrey", {"left_arm": [_core_entry("bra")]})
    result = ExtractionResult(
        category = "arms",
        per_character = {"JeanGrey": [_entry("bra", subgroup = "left_arm")]},
    )

    warnings = _run([result], tmp_path)

    assert "left_arm:bra" in warnings[0].message


# --- layer loading edge cases -------------------------------------------------


def test_an_unreadable_core_file_filters_nothing(tmp_path):
    (tmp_path / "traits.yaml").write_text("values: [oops\n", encoding = "utf-8")
    result = ExtractionResult(category = "traits", entries = [_entry("birth_control")])

    warnings = _run([result], tmp_path)

    assert [e.name for e in result.entries] == ["birth_control"]
    assert warnings == []


def test_an_empty_layer_reports_itself_as_empty(tmp_path):
    layer = load_core_layer(tmp_path, ["traits", "faces"])

    assert layer.is_empty()


def test_a_populated_layer_does_not(tmp_path):
    _write_flat(tmp_path, "traits.yaml", [_core_entry("birth_control")])

    assert not load_core_layer(tmp_path, ["traits"]).is_empty()


# --- end to end ---------------------------------------------------------------


def _subprocess_env() -> dict[str, str]:
    """Return an env dict with PYTHONPATH pointing at the package parent."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{PACKAGE_PARENT}{os.pathsep}{existing}" if existing else str(PACKAGE_PARENT)
    )
    return env


def _run_cli(out_dir: Path, *extra: str) -> subprocess.CompletedProcess:
    """Run the refresh CLI over the miniature fixtures."""
    return subprocess.run(
        [
            sys.executable, "-m", "tnh_refresh_allowlists",
            "--base-game", str(FIXTURES / "mini_tnh"),
            "--mod", str(FIXTURES / "mini_mod"),
            "--out", str(out_dir),
            "--repo-root", str(FIXTURES),
            *extra,
        ],
        capture_output = True,
        text = True,
        check = False,
        env = _subprocess_env(),
    )


def _mini_core(tmp_path: Path) -> Path:
    """A core layer carrying two of the values the mini mod's scan finds."""
    core = tmp_path / "core"
    _write_flat(core, "sfx.yaml", [_core_entry("phone_buzz")])
    _write_character(core, "faces", "Gamma", {"values": [_core_entry("neutral")]})
    return core


def test_cli_drops_core_values_on_a_mod_only_run(tmp_path):
    out_dir = tmp_path / "allowlists"
    completed = _run_cli(
        out_dir, "--no-include-tnh", "--core-allowlists", str(_mini_core(tmp_path)),
    )
    assert completed.returncode == 0, completed.stderr

    sfx = yaml.safe_load((out_dir / "sfx.yaml").read_text(encoding = "utf-8"))
    assert sfx["values"] == []

    faces = yaml.safe_load((out_dir / "faces" / "Gamma.yaml").read_text(encoding = "utf-8"))
    assert [item["name"] for item in faces["values"]] == ["mod_specific"]

    meta = yaml.safe_load((out_dir / "_meta.yaml").read_text(encoding = "utf-8"))
    assert meta["stats"]["sfx"] == 0
    assert meta["stats"]["faces"] == {"Gamma": 1}
    joined = " ".join(meta["warnings"])
    assert "phone_buzz" in joined
    assert "Gamma: neutral" in joined


def test_cli_does_not_filter_when_tnh_is_included(tmp_path):
    # A run with TNH either produces the core layer itself or was asked for
    # merged output; filtering either would gut it.
    out_dir = tmp_path / "allowlists"
    completed = _run_cli(out_dir, "--core-allowlists", str(_mini_core(tmp_path)))
    assert completed.returncode == 0, completed.stderr

    sfx = yaml.safe_load((out_dir / "sfx.yaml").read_text(encoding = "utf-8"))
    assert "phone_buzz" in {item["name"] for item in sfx["values"]}

    # The fixture raises an unrelated extractor warning of its own, so assert
    # on the absence of a filter report rather than on an empty list.
    meta = yaml.safe_load((out_dir / "_meta.yaml").read_text(encoding = "utf-8"))
    assert not any("core allowlists" in message for message in meta["warnings"])


def test_cli_dry_run_counts_are_the_filtered_ones(tmp_path):
    # The dry run announced 21 history events against a live 20 before this
    # filter existed; its summary must describe what a real run would write.
    completed = _run_cli(
        tmp_path / "out", "--no-include-tnh", "--dry-run",
        "--core-allowlists", str(_mini_core(tmp_path)),
    )

    assert completed.returncode == 0, completed.stderr
    assert "sfx: 0 entries" in completed.stdout
    assert not (tmp_path / "out").exists()


def test_cli_survives_a_missing_core_layer(tmp_path):
    completed = _run_cli(
        tmp_path / "out", "--no-include-tnh",
        "--core-allowlists", str(tmp_path / "nowhere"),
    )

    assert completed.returncode == 0
    assert "no core allowlists found" in completed.stderr
    sfx = yaml.safe_load((tmp_path / "out" / "sfx.yaml").read_text(encoding = "utf-8"))
    assert "phone_buzz" in {item["name"] for item in sfx["values"]}


def test_cli_does_not_abort_when_every_character_is_a_core_one(tmp_path):
    # The "no characters discovered" guard asks whether the scan found a game
    # at all. A mod that adds no character of its own is legitimate, so the
    # filter must run after that check, never before it.
    core = tmp_path / "core"
    _write_flat(core, "characters.yaml", [_core_entry("Gamma")])
    out_dir = tmp_path / "allowlists"

    completed = _run_cli(out_dir, "--no-include-tnh", "--core-allowlists", str(core))

    assert completed.returncode == 0, completed.stderr
    characters = yaml.safe_load(
        (out_dir / "characters.yaml").read_text(encoding = "utf-8"),
    )
    assert characters["values"] == []
