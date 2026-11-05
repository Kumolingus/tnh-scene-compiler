"""Tests for the locations extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import locations


def test_extracts_explicit_dict_locations(mini_context):
    result = locations.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert "SCHOOL LIBRARY" in names
    assert "CAFETERIA" in names


def test_a_copy_takes_its_parents_name(mini_context):
    # The backroom copies the library and keeps its name, so the library
    # (declared first) keeps the slugline and the copy is reported.
    result = locations.extract(mini_context)
    library = [entry for entry in result.entries if entry.name == "SCHOOL LIBRARY"]
    assert [dict(entry.metadata)["location_id"] for entry in library] == ["SchoolSite.Library"]
    assert any(
        "SchoolSite.LibraryBackroom" in warning.message and "SchoolSite.Library " in warning.message
        for warning in result.warnings
    )


def _beta28_rooms(tmp_path, rooms_text: str):
    """Scan one TNH file holding *rooms_text*, the way TNH 0.9c.beta.28 lays out a bedroom."""
    from tnh_refresh_allowlists.models import ScanContext

    game_root = tmp_path / "tnh"
    (game_root / "game" / "locations").mkdir(parents = True)
    (game_root / "game" / "locations" / "rooms.rpy").write_text(rooms_text, encoding = "utf-8")
    project_root = tmp_path / "mod"
    (project_root / "game").mkdir(parents = True)
    return locations.extract(ScanContext(
        base_game_root = game_root,
        project_root = project_root,
        repo_root = tmp_path,
        include_tnh = True,
    ))


# TNH 0.9c.beta.28 declares a girl's room once as a template, copies it into
# the school (`XavierSchool.RogueRoom`, the room the game builds) and disables
# the template; a shower copies the school shower, then takes the template's
# fields (locations/XavierSchool/RogueRoom/location.rpy).
_BETA28_ROOMS = (
    'init -1:\n'
    '    define ALL_LOCATIONS["RogueRoom"] = {\n'
    '        "name": _("[Rogue.name]\'s Room"),\n'
    '        "tag": "RogueRoom",\n'
    '    }\n'
    '    define ALL_LOCATIONS["RogueShower"] = {\n'
    '        "name": _("[Rogue.name]\'s Shower"),\n'
    '    }\n'
    'define ALL_LOCATIONS["XavierSchool.Shower"] = {\n'
    '    "states": {"open": True},\n'
    '}\n'
    'define ALL_LOCATIONS["XavierSchool.RogueRoom"] = ALL_LOCATIONS["RogueRoom"].copy()\n'
    'define ALL_LOCATIONS["XavierSchool.RogueShower"] = ALL_LOCATIONS["XavierSchool.Shower"].copy()\n'
    'init python:\n'
    '    ALL_LOCATIONS["XavierSchool.RogueRoom"].update({\n'
    '        "module": "XavierSchool",\n'
    '    })\n'
    '    ALL_LOCATIONS["XavierSchool.RogueShower"].update(ALL_LOCATIONS["RogueShower"])\n'
    '    ALL_LOCATIONS["RogueRoom"].update({\n'
    '        "enabled": False\n'
    '    })\n'
    '    ALL_LOCATIONS["RogueShower"].update({\n'
    '        "enabled": False\n'
    '    })\n'
)


def test_a_slugline_names_the_copy_the_game_builds_not_the_disabled_template(tmp_path):
    result = _beta28_rooms(tmp_path, _BETA28_ROOMS)
    ids = {entry.name: dict(entry.metadata)["location_id"] for entry in result.entries}
    assert ids["[ROGUE.NAME]'S ROOM"] == "XavierSchool.RogueRoom"
    assert ids["[ROGUE.NAME]'S SHOWER"] == "XavierSchool.RogueShower"
    assert "RogueRoom" not in ids.values() and "RogueShower" not in ids.values()


def test_a_copys_own_name_wins_over_its_parents(tmp_path):
    result = _beta28_rooms(tmp_path, _BETA28_ROOMS.replace(
        '"module": "XavierSchool",\n',
        '"module": "XavierSchool",\n        "name": _("Rogue\'s Bedroom"),\n',
    ))
    ids = {entry.name: dict(entry.metadata)["location_id"] for entry in result.entries}
    assert ids["ROGUE'S BEDROOM"] == "XavierSchool.RogueRoom"
    assert "[ROGUE.NAME]'S ROOM" not in ids


def test_the_off_map_holding_places_have_no_slugline(tmp_path):
    # TNH 0.9c.beta.28 parks characters who are off the map in two named
    # locations with no scene behind them (core/locations/definitions.rpy);
    # a slugline there would stage the player in an empty room.
    result = _beta28_rooms(tmp_path, (
        'define ALL_LOCATIONS["hold"] = {\n    "name": "Away",\n    "tag": "Away",\n}\n'
        'define ALL_LOCATIONS["busy"] = {\n    "name": "Busy",\n    "tag": "Busy",\n}\n'
        'define ALL_LOCATIONS["BayvilleTown.Mall"] = {\n    "name": _("Mall"),\n}\n'
    ))
    assert {entry.name for entry in result.entries} == {"MALL"}


def test_a_copy_of_an_unknown_location_is_reported(tmp_path):
    result = _beta28_rooms(tmp_path, 'define ALL_LOCATIONS["A.B"] = ALL_LOCATIONS["Nowhere"].copy()\n')
    assert result.entries == []
    assert any("A.B" in warning.message and "Nowhere" in warning.message for warning in result.warnings)


def test_entries_carry_metadata(mini_context):
    result = locations.extract(mini_context)
    library = next(entry for entry in result.entries if entry.name == "SCHOOL LIBRARY")
    metadata = dict(library.metadata)
    assert metadata.get("location_id") == "SchoolSite.Library"
    assert metadata.get("display_name") == "School Library"


def test_reads_bare_room_keys_as_well_as_dotted_ids(mini_context):
    # TNH 0.9c.beta.28 keys a location either by area and room
    # ("XavierSchool.Infirmary") or by a bare room key ("CharlesXavierRoom").
    result = locations.extract(mini_context)
    cafeteria = next(entry for entry in result.entries if entry.name == "CAFETERIA")
    assert dict(cafeteria.metadata).get("location_id") == "Cafeteria"


def test_source_line_is_one_based(mini_context):
    result = locations.extract(mini_context)
    library = next(entry for entry in result.entries if entry.name == "SCHOOL LIBRARY")
    assert library.source_line == 1


def test_first_declaration_keeps_a_shared_slugline_and_warns(tmp_path):
    """Two locations with the same display name yield one slugline, not two.

    TNH does this for real: ``loc_PlayerShower`` carries the bedroom's name.
    Emitting both leaves the winner to dict-insertion order downstream, which
    silently sends a writer's slugline to whichever was read last.
    """
    from tnh_refresh_allowlists.models import ScanContext

    game_root = tmp_path / "tnh"
    (game_root / "game" / "locations").mkdir(parents = True)
    (game_root / "game" / "locations" / "rooms.rpy").write_text(
        'define ALL_LOCATIONS["loc_Bedroom"] = {\n    "name": _("My Room"),\n}\n'
        'define ALL_LOCATIONS["loc_Shower"] = {\n    "name": _("My Room"),\n}\n',
        encoding = "utf-8",
    )

    project_root = tmp_path / "mod"
    (project_root / "game").mkdir(parents = True)

    context = ScanContext(
        base_game_root = game_root,
        project_root = project_root,
        repo_root = tmp_path,
        include_tnh = True,
    )
    result = locations.extract(context)

    entries = [entry for entry in result.entries if entry.name == "MY ROOM"]
    assert len(entries) == 1
    assert dict(entries[0].metadata).get("location_id") == "loc_Bedroom"
    assert any(
        "loc_Shower" in warning.message and "loc_Bedroom" in warning.message
        for warning in result.warnings
    )


def test_deduplicates_same_location_id(tmp_path):
    """Re-declarations with the same location_id do not create duplicate entries."""
    from tnh_refresh_allowlists.models import ScanContext

    dup_root = tmp_path / "tnh"
    (dup_root / "game" / "locations").mkdir(parents = True)
    (dup_root / "game" / "locations" / "a.rpy").write_text(
        'define ALL_LOCATIONS["loc_X_Y"] = {\n    "name": _("Y"),\n}\n',
        encoding = "utf-8",
    )
    (dup_root / "game" / "locations" / "b.rpy").write_text(
        'define ALL_LOCATIONS["loc_X_Y"] = {\n    "name": _("Y duplicate"),\n}\n',
        encoding = "utf-8",
    )

    project_root = tmp_path / "mod"
    (project_root / "game").mkdir(parents = True)

    context = ScanContext(
        base_game_root = dup_root,
        project_root = project_root,
        repo_root = tmp_path,
        include_tnh = True,
    )
    result = locations.extract(context)
    entries = [entry for entry in result.entries if dict(entry.metadata).get("location_id") == "loc_X_Y"]
    assert len(entries) == 1
