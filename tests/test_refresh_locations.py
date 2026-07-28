"""Tests for the locations extractor."""

from __future__ import annotations

from tnh_refresh_allowlists.extractors import locations


def test_extracts_explicit_dict_locations(mini_context):
    result = locations.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert "SCHOOL LIBRARY" in names
    assert "CAFETERIA" in names


def test_skips_copy_locations_and_warns(mini_context):
    result = locations.extract(mini_context)
    names = {entry.name for entry in result.entries}
    assert "loc_SchoolSite_LibraryBackroom" not in names
    assert any("LibraryBackroom" in warning.message for warning in result.warnings)


def test_entries_carry_metadata(mini_context):
    result = locations.extract(mini_context)
    library = next(entry for entry in result.entries if entry.name == "SCHOOL LIBRARY")
    metadata = dict(library.metadata)
    assert metadata.get("location_id") == "loc_SchoolSite_Library"
    assert metadata.get("display_name") == "School Library"


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
        'define all_Locations["loc_Bedroom"] = {\n    "name": _("My Room"),\n}\n'
        'define all_Locations["loc_Shower"] = {\n    "name": _("My Room"),\n}\n',
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
        'define all_Locations["loc_X_Y"] = {\n    "name": _("Y"),\n}\n',
        encoding = "utf-8",
    )
    (dup_root / "game" / "locations" / "b.rpy").write_text(
        'define all_Locations["loc_X_Y"] = {\n    "name": _("Y duplicate"),\n}\n',
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
