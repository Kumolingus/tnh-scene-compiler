"""Tests for the allowlist browser: the pure readers, the game/project origin
classification, the editable-file rules, plus a guarded Tkinter smoke."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

import pytest

from tnh_scene_compiler.allowlist_browser import (
    ALLOWLIST_TOPICS,
    MAINTENANCE_DEVELOPER,
    MAINTENANCE_GENERATED,
    ORIGIN_CORE,
    ORIGIN_PROJECT,
    SECTION_CORE,
    SECTION_PROJECT,
    SHARED_LABEL,
    AllowlistBrowserDialog,
    LayerMeta,
    classify_origin,
    default_base_dir,
    refresh_tool_available,
    load_topic,
    read_layer,
    read_layer_meta,
    topic_by_key,
    topic_characters,
    topic_path,
    validate_topic_yaml,
)

# The files ``tnh_refresh_allowlists`` leaves alone: the five manual scaffolds
# (``__main__._MANUAL_SCAFFOLDS``, plus the empty-result skip that preserves
# ``condition_functions.yaml``) and the two with no extractor at all. Editing
# anything outside this set is still allowed — a project that never runs the
# refresh has no other way in — but it only survives until the next run.
_SURVIVES_REFRESH = {
    "locations_overrides.yaml",
    "interpolation_custom.yaml",
    "fx_custom.yaml",
    "condition_functions.yaml",
    "run_operations.yaml",
    "character_methods.yaml",
    "character_properties.yaml",
}

_GAME = "TheNullHypothesis"
_MOD = "MyMod"


@pytest.fixture
def layers(tmp_path: Path) -> tuple[Path, Path]:
    """Build a two-layer tree shaped like a real one.

    The project layer is what a refresh with ``--include-tnh`` produces: one
    file per list holding both the game's values and the mod's, told apart only
    by each entry's ``source_file``.
    """
    base = tmp_path / "allowlists_base"
    project = tmp_path / "_allowlists"
    (base / "faces").mkdir(parents=True)
    (base / "moods").mkdir(parents=True)
    (project / "faces").mkdir(parents=True)

    (base / "_meta.yaml").write_text(
        f"base_game_root: {_GAME}\nproject_root: /tmp/empty\n", encoding="utf-8",
    )
    (project / "_meta.yaml").write_text(
        f"base_game_root: {_GAME}\nproject_root: {_MOD}\n", encoding="utf-8",
    )

    (base / "traits.yaml").write_text(
        "values:\n"
        "- name: shy\n"
        "  source_file: game/traits.rpy\n"
        "- name: brave\n"
        "  source_file: game/traits.rpy\n",
        encoding="utf-8",
    )
    (project / "traits.yaml").write_text(
        "values:\n"
        f"- name: shy\n  source_file: {_GAME}/game/traits.rpy\n"
        f"- name: brave\n  source_file: {_GAME}/game/traits.rpy\n"
        f"- name: pregnant\n  source_file: {_MOD}/game/state.rpy\n",
        encoding="utf-8",
    )
    (base / "faces" / "JeanGrey.yaml").write_text(
        "values:\n- name: smile\n  source_file: game/faces.rpy\n", encoding="utf-8",
    )
    (project / "faces" / "JeanGrey.yaml").write_text(
        "values:\n"
        f"- name: smile\n  source_file: {_GAME}/game/faces.rpy\n"
        f"- name: bump\n  source_file: {_MOD}/game/faces.rpy\n",
        encoding="utf-8",
    )
    (project / "faces" / "Rogue.yaml").write_text(
        f"values:\n- name: smirk\n  source_file: {_GAME}/game/faces.rpy\n",
        encoding="utf-8",
    )
    (base / "moods" / "_shared.yaml").write_text(
        "values:\n- name: normal\n  source_file: game/moods.rpy\n", encoding="utf-8",
    )
    (base / "character_properties.yaml").write_text(
        "properties:\n- name: desire\n  type: float\n  notes: 0.0 to 1.0\n"
        "  source_file: game/npcs.rpy\n",
        encoding="utf-8",
    )
    (base / "interpolation.yaml").write_text(
        "values:\n- name: Player.name\n  source_file: <builtin>\n", encoding="utf-8",
    )
    (project / "interpolation_custom.yaml").write_text(
        "# hand-written header\npaths:\n- JeanGrey.petname\n", encoding="utf-8",
    )
    (project / "run_operations.yaml").write_text(
        "operations:\n- name: mymod_do_thing\n", encoding="utf-8",
    )
    return base, project


# -- Catalogue ----------------------------------------------------------------


class TestCatalogue:
    def test_survives_refresh_matches_the_files_the_refresh_leaves_alone(self) -> None:
        survives = {t.filename for t in ALLOWLIST_TOPICS if t.survives_refresh}
        assert survives == _SURVIVES_REFRESH

    def test_survives_refresh_is_exactly_not_generated(self) -> None:
        for topic in ALLOWLIST_TOPICS:
            assert topic.survives_refresh == (
                topic.maintenance != MAINTENANCE_GENERATED
            )

    def test_nothing_is_editable_on_the_core_side(self) -> None:
        # The game's values are the game's, and the base layer ships read-only
        # inside the app bundle.
        for topic in ALLOWLIST_TOPICS:
            assert not topic.is_editable_in(ORIGIN_CORE)

    def test_every_list_is_editable_on_the_project_side(self) -> None:
        # A project that cannot run the refresh — no extracted base game — must
        # still be able to fill any allowlist by hand. Regenerated files warn on
        # save instead of being locked.
        for topic in ALLOWLIST_TOPICS:
            assert topic.is_editable_in(ORIGIN_PROJECT)

    def test_core_blurb_never_invites_an_edit(self) -> None:
        for topic in ALLOWLIST_TOPICS:
            assert "Read-only" in topic.blurb(ORIGIN_CORE)

    def test_project_blurb_always_invites_an_edit(self) -> None:
        for topic in ALLOWLIST_TOPICS:
            assert "Yours to edit" in topic.blurb(ORIGIN_PROJECT)

    def test_generated_project_blurb_still_warns_about_the_refresh(self) -> None:
        topic = topic_by_key("traits")
        assert topic.maintenance == MAINTENANCE_GENERATED
        assert "would be lost" in topic.blurb(ORIGIN_PROJECT)

    def test_developer_topics_are_refresh_safe(self) -> None:
        # No extractor and no scaffold: the refresh never writes them, so a
        # project-layer copy persists. The compiler's merge() carries them.
        topic = topic_by_key("character_properties")
        assert topic.maintenance == MAINTENANCE_DEVELOPER
        assert topic.survives_refresh
        assert "Yours to edit. What you put here stays." in topic.blurb(ORIGIN_PROJECT)

    def test_no_refresh_warning_where_the_refresh_cannot_be_run(self) -> None:
        # The packaged app ships the GUI alone, so its users have no way to
        # regenerate an allowlist and nothing can overwrite their edit.
        topic = topic_by_key("traits")
        assert topic.maintenance == MAINTENANCE_GENERATED
        with_tool = topic.blurb(ORIGIN_PROJECT, refresh_available=True)
        without = topic.blurb(ORIGIN_PROJECT, refresh_available=False)
        assert "would be lost" in with_tool
        assert "would be lost" not in without
        assert "Yours to edit" in without

    def test_refresh_availability_is_probed_not_assumed(self) -> None:
        # Truthful in both contexts: importable from a source checkout, absent
        # from the frozen build (which bundles run_gui.py's import graph only).
        import importlib.util

        assert refresh_tool_available() == (
            importlib.util.find_spec("tnh_refresh_allowlists") is not None
        )

    def test_keys_are_unique(self) -> None:
        keys = [t.key for t in ALLOWLIST_TOPICS]
        assert len(keys) == len(set(keys))

    def test_topic_by_key_round_trip(self) -> None:
        assert topic_by_key("traits") is not None
        assert topic_by_key("no-such-topic") is None

    def test_real_base_layer_covers_every_flat_topic(self) -> None:
        # Guards against a topic naming a file that does not exist in the
        # shipped base allowlists (a typo would render an always-empty section).
        base = default_base_dir()
        if base is None:  # pragma: no cover - dev checkout without data
            pytest.skip("no bundled allowlists_base")
        missing = [
            t.filename for t in ALLOWLIST_TOPICS
            if not (base / t.filename).exists()
        ]
        # fx_custom / interpolation_custom / locations_overrides / run_operations
        # are project-only scaffolds; everything else must exist in the base.
        assert set(missing) <= {
            "fx_custom.yaml", "interpolation_custom.yaml",
            "locations_overrides.yaml", "run_operations.yaml",
        }


# -- Origin classification ----------------------------------------------------


class TestClassifyOrigin:
    META = LayerMeta(base_game_root=_GAME, project_root=_MOD)

    def test_base_layer_is_always_core(self) -> None:
        # Whatever a base-layer entry claims as its source, the layer ships with
        # the tool and is the game.
        assert classify_origin("", layer="base", meta=LayerMeta()) == ORIGIN_CORE
        assert classify_origin(
            f"{_MOD}/x.rpy", layer="base", meta=self.META,
        ) == ORIGIN_CORE

    def test_project_layer_splits_on_the_source_root(self) -> None:
        assert classify_origin(
            f"{_GAME}/game/traits.rpy", layer="project", meta=self.META,
        ) == ORIGIN_CORE
        assert classify_origin(
            f"{_MOD}/game/state.rpy", layer="project", meta=self.META,
        ) == ORIGIN_PROJECT

    def test_builtin_sentinel_counts_as_core(self) -> None:
        # Interpolation paths and looks carry "<builtin>": engine values.
        assert classify_origin(
            "<builtin>", layer="project", meta=self.META,
        ) == ORIGIN_CORE

    def test_entry_without_a_source_falls_to_the_project(self) -> None:
        # run_operations.yaml records no source; it is written by hand, there.
        assert classify_origin("", layer="project", meta=self.META) == ORIGIN_PROJECT

    def test_unknown_root_falls_to_the_project(self) -> None:
        # locations_overrides.yaml uses "manual"; anything unrecognised is the
        # project's, which is the safe side — it never claims to be the game's.
        assert classify_origin(
            "manual", layer="project", meta=self.META,
        ) == ORIGIN_PROJECT

    def test_windows_separators_are_handled(self) -> None:
        assert classify_origin(
            f"{_MOD}\\game\\state.rpy", layer="project", meta=self.META,
        ) == ORIGIN_PROJECT

    def test_without_meta_everything_project_side_is_the_project(self) -> None:
        # A tool run against a hand-written allowlist tree with no _meta.yaml.
        meta = LayerMeta()
        assert classify_origin(
            f"{_GAME}/x.rpy", layer="project", meta=meta,
        ) == ORIGIN_PROJECT

    def test_read_layer_meta(self, layers) -> None:
        base, project = layers
        assert read_layer_meta(project) == LayerMeta(_GAME, _MOD)
        assert read_layer_meta(None) == LayerMeta()
        assert read_layer_meta(Path("nope")) == LayerMeta()


# -- Reading ------------------------------------------------------------------


class TestReading:
    def test_topic_path_flat_and_per_character(self, layers) -> None:
        base, _ = layers
        assert topic_path(topic_by_key("traits"), base) == base / "traits.yaml"
        assert topic_path(topic_by_key("faces"), base, "JeanGrey") == (
            base / "faces" / "JeanGrey.yaml"
        )
        assert topic_path(topic_by_key("moods"), base, SHARED_LABEL) == (
            base / "moods" / "_shared.yaml"
        )

    def test_missing_layer_reads_empty(self) -> None:
        assert read_layer(topic_by_key("traits"), None) == {}
        assert read_layer(topic_by_key("traits"), Path("nope")) == {}

    def test_no_list_mixes_the_two_origins(self, layers) -> None:
        base, project = layers
        for origin in (ORIGIN_CORE, ORIGIN_PROJECT):
            groups = load_topic(topic_by_key("traits"), base, project, origin=origin)
            for group in groups:
                assert all(v.origin == origin for v in group.values)

    def test_game_values_inside_a_generated_project_file_stay_core(
        self, layers,
    ) -> None:
        # The whole point: project/traits.yaml holds shy+brave (game) and
        # pregnant (mod). Only pregnant is the project's.
        base, project = layers
        core = load_topic(topic_by_key("traits"), base, project, origin=ORIGIN_CORE)
        proj = load_topic(topic_by_key("traits"), base, project, origin=ORIGIN_PROJECT)
        assert [v.name for v in core[0].values] == ["brave", "shy"]
        assert [v.name for v in proj[0].values] == ["pregnant"]

    def test_a_value_in_both_layers_is_listed_once(self, layers) -> None:
        base, project = layers
        core = load_topic(topic_by_key("traits"), base, project, origin=ORIGIN_CORE)
        assert [v.name for v in core[0].values].count("shy") == 1

    def test_project_only_layer_needs_no_base(self, layers) -> None:
        # A dev who never runs the refresh against the game still sees their own
        # values on the project side.
        _, project = layers
        proj = load_topic(topic_by_key("traits"), None, project, origin=ORIGIN_PROJECT)
        assert [v.name for v in proj[0].values] == ["pregnant"]

    def test_no_origin_filter_returns_everything(self, layers) -> None:
        base, project = layers
        every = load_topic(topic_by_key("traits"), base, project)
        assert {v.name for v in every[0].values} == {"shy", "brave", "pregnant"}

    def test_values_are_sorted_case_insensitively(self, layers) -> None:
        base, project = layers
        groups = load_topic(topic_by_key("traits"), base, project, origin=ORIGIN_CORE)
        names = [v.name for v in groups[0].values]
        assert names == sorted(names, key=str.lower)

    def test_details_are_carried(self, layers) -> None:
        base, _ = layers
        groups = load_topic(
            topic_by_key("character_properties"), base, None, origin=ORIGIN_CORE,
        )
        desire = next(v for v in groups[0].values if v.name == "desire")
        assert ("type", "float") in desire.details
        assert ("notes", "0.0 to 1.0") in desire.details

    def test_source_file_is_kept_out_of_the_details(self, layers) -> None:
        # It drives the origin split and the badge, not a detail row.
        base, project = layers
        groups = load_topic(topic_by_key("traits"), base, project, origin=ORIGIN_CORE)
        shy = next(v for v in groups[0].values if v.name == "shy")
        assert all(field != "source_file" for field, _ in shy.details)
        assert shy.source.endswith("traits.rpy")

    def test_multi_line_detail_is_collapsed_to_one_line(self, tmp_path: Path) -> None:
        # A folded `notes:` block would otherwise break the column alignment.
        project = tmp_path / "_allowlists"
        project.mkdir()
        (project / "character_properties.yaml").write_text(
            "properties:\n- name: desire\n  notes: >\n    first line\n    second line\n",
            encoding="utf-8",
        )
        groups = load_topic(topic_by_key("character_properties"), None, project)
        notes = dict(groups[0].values[0].details)["notes"]
        assert notes == "first line second line"

    def test_bare_string_entries_are_read_as_project(self, layers) -> None:
        # interpolation_custom.yaml holds plain strings, not name: mappings.
        _, project = layers
        groups = load_topic(
            topic_by_key("interpolation_custom"), None, project, origin=ORIGIN_PROJECT,
        )
        assert [v.name for v in groups[0].values] == ["JeanGrey.petname"]

    def test_builtin_interpolation_lands_on_the_core_side(self, layers) -> None:
        base, project = layers
        core = load_topic(
            topic_by_key("interpolation"), base, project, origin=ORIGIN_CORE,
        )
        assert [v.name for v in core[0].values] == ["Player.name"]

    def test_arms_topic_yields_its_three_subgroups(self, tmp_path: Path) -> None:
        project = tmp_path / "_allowlists"
        (project / "arms").mkdir(parents=True)
        (project / "arms" / "Rogue.yaml").write_text(
            "arms:\n- name: crossed\nleft_arm:\n- name: down\nright_arm:\n- name: up\n",
            encoding="utf-8",
        )
        groups = load_topic(topic_by_key("arms"), None, project, "Rogue")
        assert [g.title for g in groups] == ["arms", "left_arm", "right_arm"]
        assert [v.name for v in groups[1].values] == ["down"]

    def test_characters_union_both_layers_with_shared_first(self, layers) -> None:
        base, project = layers
        faces = topic_characters(topic_by_key("faces"), base, project)
        assert faces == ["JeanGrey", "Rogue"]
        moods = topic_characters(topic_by_key("moods"), base, project)
        assert moods[0] == SHARED_LABEL

    def test_flat_topic_has_no_characters(self, layers) -> None:
        base, project = layers
        assert topic_characters(topic_by_key("traits"), base, project) == []

    def test_unreadable_yaml_is_tolerated(self, tmp_path: Path) -> None:
        project = tmp_path / "_allowlists"
        project.mkdir()
        (project / "traits.yaml").write_text("values: [unclosed\n", encoding="utf-8")
        groups = load_topic(topic_by_key("traits"), None, project)
        assert groups[0].values == ()


# -- Validation ---------------------------------------------------------------


class TestValidateTopicYaml:
    def test_accepts_a_good_file(self) -> None:
        topic = topic_by_key("run_operations")
        assert validate_topic_yaml(topic, "operations:\n- name: give_trait\n") is None

    def test_accepts_an_empty_list(self) -> None:
        topic = topic_by_key("run_operations")
        assert validate_topic_yaml(topic, "operations: []\n") is None

    def test_accepts_a_null_list(self) -> None:
        topic = topic_by_key("run_operations")
        assert validate_topic_yaml(topic, "operations:\n") is None

    def test_accepts_bare_strings(self) -> None:
        topic = topic_by_key("interpolation_custom")
        assert validate_topic_yaml(topic, "paths:\n- Player.name\n") is None

    def test_rejects_broken_yaml(self) -> None:
        topic = topic_by_key("run_operations")
        error = validate_topic_yaml(topic, "operations: [oops\n")
        assert error and "not valid YAML" in error

    def test_rejects_an_empty_file(self) -> None:
        topic = topic_by_key("run_operations")
        error = validate_topic_yaml(topic, "\n")
        assert error and "operations: []" in error

    def test_rejects_a_missing_top_level_key(self) -> None:
        topic = topic_by_key("run_operations")
        error = validate_topic_yaml(topic, "functions:\n- name: x\n")
        assert error and "'operations:'" in error

    def test_rejects_a_bare_list(self) -> None:
        topic = topic_by_key("run_operations")
        error = validate_topic_yaml(topic, "- name: x\n")
        assert error and "bare list" in error

    def test_rejects_a_non_list_value(self) -> None:
        topic = topic_by_key("run_operations")
        error = validate_topic_yaml(topic, "operations: nope\n")
        assert error and "must be a list" in error

    def test_rejects_an_entry_without_a_name(self) -> None:
        topic = topic_by_key("run_operations")
        error = validate_topic_yaml(topic, "operations:\n- signature: f()\n")
        assert error and "Entry 1" in error

    def test_rejects_a_non_mapping_entry(self) -> None:
        topic = topic_by_key("run_operations")
        error = validate_topic_yaml(topic, "operations:\n- [a, b]\n")
        assert error and "Entry 1" in error


# -- Dialog (guarded Tkinter) -------------------------------------------------


@pytest.fixture(scope="module")
def tk_root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no Tk display available: {exc}")
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


def _rows(dlg: AllowlistBrowserDialog) -> list[str]:
    return [dlg._listbox.get(i) for i in range(dlg._listbox.size())]


def _section_of(dlg: AllowlistBrowserDialog, title: str) -> list[str]:
    """Return the topic titles listed under each heading, keyed by heading."""
    grouped: dict[str, list[str]] = {}
    heading = ""
    for row in _rows(dlg):
        if row.startswith(" "):
            grouped.setdefault(heading, []).append(row.strip())
        else:
            heading = row
    return grouped.get(title, [])


def test_dialog_lists_both_sides(tk_root, layers) -> None:
    base, project = layers
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        headings = [r for r in _rows(dlg) if not r.startswith(" ")]
        assert headings == [SECTION_CORE, SECTION_PROJECT]
        # Traits has values on both sides, so it is listed under both.
        assert "Traits" in _section_of(dlg, SECTION_CORE)
        assert "Traits" in _section_of(dlg, SECTION_PROJECT)
        # A heading row is not selectable.
        assert dlg._visible[_rows(dlg).index(SECTION_CORE)] is None
    finally:
        dlg.destroy()


def test_core_hides_a_list_it_has_nothing_for(tk_root, layers) -> None:
    base, project = layers
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        # Location overrides are the project's alone.
        assert "Location overrides" in _section_of(dlg, SECTION_PROJECT)
        assert "Location overrides" not in _section_of(dlg, SECTION_CORE)
    finally:
        dlg.destroy()


def test_project_lists_everything_so_any_list_can_be_filled_by_hand(
    tk_root, layers,
) -> None:
    # Hiding an empty list would hide the only route a project that cannot run
    # the refresh has to extend it.
    base, project = layers
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        titles = _section_of(dlg, SECTION_PROJECT)
        assert len(titles) == len(ALLOWLIST_TOPICS)
        assert "Character properties" in titles  # game-only in this tree
        assert "Stage positions" in titles
    finally:
        dlg.destroy()


def test_dialog_shows_only_that_side_s_values(tk_root, layers) -> None:
    base, project = layers
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        traits = topic_by_key("traits")
        dlg._select_topic(traits, ORIGIN_CORE)
        dlg.update()
        core = _all_label_texts(dlg._content)
        assert "shy" in core and "brave" in core
        assert "pregnant" not in core

        dlg._select_topic(traits, ORIGIN_PROJECT)
        dlg.update()
        proj = _all_label_texts(dlg._content)
        assert "pregnant" in proj
        assert "shy" not in proj
    finally:
        dlg.destroy()


def test_dialog_search_matches_within_a_side(tk_root, layers) -> None:
    base, project = layers
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        dlg._search_var.set("pregnant")
        # The value only exists on the project side, so only that side lists it.
        assert "Traits" in _section_of(dlg, SECTION_PROJECT)
        assert "Traits" not in _section_of(dlg, SECTION_CORE)
    finally:
        dlg.destroy()


def test_dialog_search_covers_every_character_not_just_the_first(
    tk_root, layers,
) -> None:
    # "smirk" only exists on Rogue, who is not the character Faces opens on.
    base, project = layers
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        dlg._search_var.set("smirk")
        assert "Faces" in _section_of(dlg, SECTION_CORE)
    finally:
        dlg.destroy()


def test_dialog_reads_each_side_once(tk_root, layers, monkeypatch) -> None:
    # Reading the real layers costs ~0.5 s, so re-rendering must not re-read.
    import tnh_scene_compiler.allowlist_browser as module

    base, project = layers
    calls: list[tuple[str, str, str]] = []
    real = module.load_topic
    monkeypatch.setattr(
        module, "load_topic",
        lambda topic, b, p, character="", *, origin="": (
            calls.append((topic.key, character, origin))
            or real(topic, b, p, character, origin=origin)
        ),
    )
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        # Building the sidebar needs to know which side has values, so the whole
        # tree is read once at open — and never twice.
        assert calls, "opening should have read the layers"
        assert len(calls) == len(set(calls))

        before = len(calls)
        traits = topic_by_key("traits")
        dlg._select_topic(traits, ORIGIN_CORE)
        dlg._select_topic(traits, ORIGIN_PROJECT)
        dlg._select_topic(topic_by_key("looks"), ORIGIN_CORE)
        dlg._select_topic(traits, ORIGIN_CORE)
        dlg.update()
        assert len(calls) == before, "navigating must serve from the cache"
    finally:
        dlg.destroy()


def test_dialog_reload_picks_up_a_change_made_on_disk(tk_root, layers) -> None:
    base, project = layers
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        dlg._select_topic(topic_by_key("traits"), ORIGIN_PROJECT)
        dlg.update()
        assert "telepath" not in _all_label_texts(dlg._content)

        # Stand-in for an allowlist refresh run while the window is open.
        (project / "traits.yaml").write_text(
            f"values:\n- name: telepath\n  source_file: {_MOD}/game/state.rpy\n",
            encoding="utf-8",
        )
        dlg._reload()
        dlg.update()
        assert "telepath" in _all_label_texts(dlg._content)
    finally:
        dlg.destroy()


def test_dialog_edit_button_on_every_project_list_and_no_core_one(
    tk_root, layers,
) -> None:
    base, project = layers
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        for key in ("traits", "run_operations", "character_properties"):
            dlg._select_topic(topic_by_key(key), ORIGIN_PROJECT)
            dlg.update()
            assert "Edit" in _all_button_texts(dlg._header), key

            dlg._select_topic(topic_by_key(key), ORIGIN_CORE)
            dlg.update()
            assert "Edit" not in _all_button_texts(dlg._header), key
    finally:
        dlg.destroy()


def test_dialog_warns_once_before_saving_a_regenerated_file(
    tk_root, layers, monkeypatch,
) -> None:
    base, project = layers
    asked: list[str] = []
    monkeypatch.setattr(
        "tnh_scene_compiler.allowlist_browser.messagebox.askokcancel",
        lambda title, message, **kw: asked.append(message) or True,
    )
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        for _ in range(2):
            dlg._select_topic(topic_by_key("traits"), ORIGIN_PROJECT)
            dlg._start_edit()
            dlg.update()
            dlg._edit_text.delete("1.0", tk.END)
            dlg._edit_text.insert("1.0", "values:\n- name: telepath\n")
            dlg._save_edit()
        # Warned on the first save, not on every save of the same list.
        assert len(asked) == 1
        assert "rewritten by the allowlist refresh" in asked[0]
        assert (project / "traits.yaml").read_text(encoding="utf-8") == (
            "values:\n- name: telepath\n"
        )
    finally:
        dlg.destroy()


def test_dialog_declining_the_warning_leaves_the_file_alone(
    tk_root, layers, monkeypatch,
) -> None:
    base, project = layers
    before = (project / "traits.yaml").read_text(encoding="utf-8")
    monkeypatch.setattr(
        "tnh_scene_compiler.allowlist_browser.messagebox.askokcancel",
        lambda title, message, **kw: False,
    )
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        dlg._select_topic(topic_by_key("traits"), ORIGIN_PROJECT)
        dlg._start_edit()
        dlg.update()
        dlg._edit_text.delete("1.0", tk.END)
        dlg._edit_text.insert("1.0", "values:\n- name: telepath\n")
        dlg._save_edit()
        assert (project / "traits.yaml").read_text(encoding="utf-8") == before
        assert dlg._editing  # the typed text is not thrown away
    finally:
        dlg.destroy()


def test_dialog_saves_a_refresh_safe_file_without_asking(
    tk_root, layers, monkeypatch,
) -> None:
    base, project = layers
    monkeypatch.setattr(
        "tnh_scene_compiler.allowlist_browser.messagebox.askokcancel",
        lambda *a, **kw: pytest.fail("should not warn for a refresh-safe file"),
    )
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        dlg._select_topic(topic_by_key("run_operations"), ORIGIN_PROJECT)
        dlg._start_edit()
        dlg.update()
        dlg._edit_text.delete("1.0", tk.END)
        dlg._edit_text.insert("1.0", "operations:\n- name: mymod_other\n")
        dlg._save_edit()
        assert not dlg._editing
    finally:
        dlg.destroy()


def test_editor_says_when_the_file_also_holds_game_values(tk_root, layers) -> None:
    # The value list is filtered to one side, the file on disk is not. The
    # editor must not look like it opened "the project's values" alone.
    base, project = layers
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        dlg._select_topic(topic_by_key("traits"), ORIGIN_PROJECT)
        dlg._start_edit()
        dlg.update()
        # project/traits.yaml holds shy+brave (game) alongside pregnant (mod).
        assert "2 of the entries below came with the game" in _all_label_texts(
            dlg._content,
        )
    finally:
        dlg.destroy()


def test_editor_stays_quiet_when_the_file_is_the_project_s_alone(
    tk_root, layers,
) -> None:
    base, project = layers
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        dlg._select_topic(topic_by_key("run_operations"), ORIGIN_PROJECT)
        dlg._start_edit()
        dlg.update()
        assert "came with the game" not in _all_label_texts(dlg._content)
    finally:
        dlg.destroy()


def test_editor_counts_only_the_edited_file_not_the_base_layer(
    tk_root, layers,
) -> None:
    # Regression: the count came from the merged view, so it included the base
    # layer — a different file entirely. It announced game values inside project
    # files that hold none, and even inside one that does not exist.
    base, project = layers
    assert (base / "character_properties.yaml").is_file()
    assert not (project / "character_properties.yaml").is_file()

    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        dlg._select_topic(topic_by_key("character_properties"), ORIGIN_PROJECT)
        dlg._start_edit()
        dlg.update()
        assert "came with the game" not in _all_label_texts(dlg._content)
    finally:
        dlg.destroy()


def test_editor_counts_builtins_the_project_file_really_repeats(
    tk_root, layers,
) -> None:
    # The mod-only refresh still writes engine builtins into the project's own
    # interpolation.yaml, so the note is right there — and says how many.
    base, project = layers
    (project / "interpolation.yaml").write_text(
        "values:\n"
        "- name: day\n  source_file: <builtin>\n"
        "- name: Player.name\n  source_file: <builtin>\n"
        f"- name: JeanGrey.bump\n  source_file: {_MOD}/game/state.rpy\n",
        encoding="utf-8",
    )
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        dlg._select_topic(topic_by_key("interpolation"), ORIGIN_PROJECT)
        dlg._start_edit()
        dlg.update()
        assert "2 of the entries below came with the game" in _all_label_texts(
            dlg._content,
        )
    finally:
        dlg.destroy()


def test_dialog_creates_a_project_file_that_did_not_exist(tk_root, layers) -> None:
    # character_properties.yaml is game-only here; a project must be able to add
    # its own, and the compiler's merge() picks it up.
    base, project = layers
    path = project / "character_properties.yaml"
    assert not path.exists()
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        dlg._select_topic(topic_by_key("character_properties"), ORIGIN_PROJECT)
        dlg._start_edit()
        dlg.update()
        # The scaffold offered for a missing file is the bare top-level key.
        assert dlg._edit_text.get("1.0", "end-1c").strip() == "properties: []"
        dlg._edit_text.delete("1.0", tk.END)
        dlg._edit_text.insert("1.0", "properties:\n- name: mymod_stress\n  type: int\n")
        dlg._save_edit()
        assert path.exists()
        dlg.update()
        assert "mymod_stress" in _all_label_texts(dlg._content)
    finally:
        dlg.destroy()


def test_dialog_save_writes_the_project_layer_and_keeps_comments(
    tk_root, layers,
) -> None:
    base, project = layers
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        dlg._select_topic(topic_by_key("interpolation_custom"), ORIGIN_PROJECT)
        dlg._start_edit()
        dlg.update()
        assert dlg._edit_text is not None
        dlg._edit_text.delete("1.0", tk.END)
        dlg._edit_text.insert("1.0", "# hand-written header\npaths:\n- Rogue.petname\n")
        dlg._save_edit()

        written = (project / "interpolation_custom.yaml").read_text(encoding="utf-8")
        assert written == "# hand-written header\npaths:\n- Rogue.petname\n"
        assert not dlg._editing
    finally:
        dlg.destroy()


def test_dialog_save_invalidates_the_cache(tk_root, layers) -> None:
    base, project = layers
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        dlg._select_topic(topic_by_key("interpolation_custom"), ORIGIN_PROJECT)
        dlg.update()
        assert "JeanGrey.petname" in _all_label_texts(dlg._content)

        dlg._start_edit()
        dlg.update()
        dlg._edit_text.delete("1.0", tk.END)
        dlg._edit_text.insert("1.0", "paths:\n- Rogue.petname\n")
        dlg._save_edit()
        dlg.update()

        labels = _all_label_texts(dlg._content)
        assert "Rogue.petname" in labels
        assert "JeanGrey.petname" not in labels
    finally:
        dlg.destroy()


def test_dialog_save_refuses_invalid_yaml(tk_root, layers, monkeypatch) -> None:
    base, project = layers
    path = project / "interpolation_custom.yaml"
    before = path.read_text(encoding="utf-8")
    errors: list[str] = []
    monkeypatch.setattr(
        "tnh_scene_compiler.allowlist_browser.messagebox.showerror",
        lambda title, message, **kw: errors.append(message),
    )
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        dlg._select_topic(topic_by_key("interpolation_custom"), ORIGIN_PROJECT)
        dlg._start_edit()
        dlg.update()
        dlg._edit_text.delete("1.0", tk.END)
        dlg._edit_text.insert("1.0", "paths: [broken\n")
        dlg._save_edit()

        assert errors and "not valid YAML" in errors[0]
        assert path.read_text(encoding="utf-8") == before  # untouched
        assert dlg._editing  # stays in the editor so the text isn't lost
    finally:
        dlg.destroy()


def test_dialog_edit_without_a_project_layer_explains_itself(
    tk_root, layers, monkeypatch,
) -> None:
    base, _ = layers
    infos: list[str] = []
    monkeypatch.setattr(
        "tnh_scene_compiler.allowlist_browser.messagebox.showinfo",
        lambda title, message, **kw: infos.append(message),
    )
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=None)
    try:
        dlg._select_topic(topic_by_key("run_operations"), ORIGIN_PROJECT)
        dlg._start_edit()
        assert infos and "no project open" in infos[0]
        assert not dlg._editing
    finally:
        dlg.destroy()


def test_base_only_session_still_shows_the_game_values(tk_root) -> None:
    # Quick mode has no Config and no project layer. The browser must fall back
    # to the bundled base allowlists instead of opening on nothing.
    base = default_base_dir()
    if base is None:  # pragma: no cover - dev checkout without bundled data
        pytest.skip("no bundled allowlists_base")
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=None)
    try:
        dlg._select_topic(topic_by_key("traits"), ORIGIN_CORE)
        dlg.update()
        rendered = _all_label_texts(dlg._content)
        assert "value" in rendered  # the "N values" count line
        assert "No values" not in rendered
    finally:
        dlg.destroy()


def test_dialog_keeps_a_gap_between_a_long_name_and_its_badge(
    tk_root, tmp_path: Path,
) -> None:
    # A name past the badge column used to run straight into it ("…nightproject").
    project = tmp_path / "_allowlists"
    project.mkdir()
    long_name = "pregnancy_mod_announcement_retire_for_the_night"
    (project / "run_operations.yaml").write_text(
        f"operations:\n- name: {long_name}\n", encoding="utf-8",
    )
    dlg = AllowlistBrowserDialog(tk_root, base_dir=None, project_dir=project)
    try:
        dlg._select_topic(topic_by_key("run_operations"), ORIGIN_PROJECT)
        dlg.update()
        assert f"{long_name}  hand-written" in _all_label_texts(dlg._content)
    finally:
        dlg.destroy()


def test_dialog_per_character_topic_switches_character(tk_root, layers) -> None:
    base, project = layers
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        dlg._select_topic(topic_by_key("faces"), ORIGIN_CORE)
        dlg.update()
        assert dlg._character == "JeanGrey"
        assert "smile" in _all_label_texts(dlg._content)

        dlg._character = "Rogue"
        dlg._render()
        dlg.update()
        assert "smirk" in _all_label_texts(dlg._content)
        assert "smile" not in _all_label_texts(dlg._content)
    finally:
        dlg.destroy()


def test_dialog_per_character_split_is_per_character(tk_root, layers) -> None:
    base, project = layers
    dlg = AllowlistBrowserDialog(tk_root, base_dir=base, project_dir=project)
    try:
        faces = topic_by_key("faces")
        dlg._select_topic(faces, ORIGIN_PROJECT)
        dlg._character = "JeanGrey"
        dlg._render()
        dlg.update()
        # Only the mod-added face, not the game's.
        rendered = _all_label_texts(dlg._content)
        assert "bump" in rendered
        assert "smile" not in rendered
    finally:
        dlg.destroy()


def _all_label_texts(widget: tk.Widget) -> str:
    """Return everything rendered below *widget* — ttk.Label text and Text bodies."""
    from tkinter import ttk

    parts: list[str] = []
    for child in widget.winfo_children():
        if isinstance(child, ttk.Label):
            parts.append(str(child.cget("text")))
        elif isinstance(child, tk.Text):
            parts.append(child.get("1.0", "end-1c"))
        parts.append(_all_label_texts(child))
    return "\n".join(parts)


def _all_button_texts(widget: tk.Widget) -> list[str]:
    """Collect the text of every ttk.Button below *widget*, recursively."""
    from tkinter import ttk

    found: list[str] = []
    for child in widget.winfo_children():
        if isinstance(child, ttk.Button):
            found.append(str(child.cget("text")))
        found.extend(_all_button_texts(child))
    return found
