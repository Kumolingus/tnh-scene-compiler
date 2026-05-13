"""Unit tests for :mod:`tnh_generate_cheatsheet.renderer`."""

from __future__ import annotations

from pathlib import Path

from tnh_generate_cheatsheet.loader import load
from tnh_generate_cheatsheet.models import CharacterData, CheatsheetData, Entry
from tnh_generate_cheatsheet.renderer import (
    _render_character,
    _render_condition_functions,
    _render_interpolation,
    _render_locations,
    _render_per_character,
    _render_speakers,
    render,
)


def test_render_speakers_emits_uppercase_and_pascal_pair() -> None:
    entries = [Entry(name = "JeanGrey"), Entry(name = "Rogue")]

    output = _render_speakers(entries)

    assert "| `JEANGREY` | `JeanGrey` |" in output
    assert "| `ROGUE` | `Rogue` |" in output
    assert "|---|---|" in output


def test_render_speakers_narrator_has_blank_slot() -> None:
    entries = [Entry(name = "Narrator"), Entry(name = "JeanGrey")]

    output = _render_speakers(entries)

    assert "_(leave speaker blank)_" in output
    assert "`narrator`" in output


def test_render_locations_includes_provenance_tag() -> None:
    entries = [
        Entry(
            name = "CLASSROOM",
            provenance = "auto",
            metadata = (("location_id", "loc_Classroom"), ("display_name", "Classroom")),
        ),
        Entry(
            name = "KITCHEN",
            provenance = "override",
            metadata = (("location_id", "loc_Kitchen"), ("display_name", "Manual K.")),
        ),
    ]

    output = _render_locations(entries)

    assert "| `CLASSROOM` | `loc_Classroom` | Classroom | auto |" in output
    assert "| `KITCHEN` | `loc_Kitchen` | Manual K. | override |" in output


def test_render_interpolation_labels_auto_and_custom() -> None:
    entries = [
        Entry(name = "day", provenance = "auto"),
        Entry(name = "mod.pregnancy_stage", provenance = "custom"),
    ]

    output = _render_interpolation(entries)

    assert "| `[day]` | auto |" in output
    assert "| `[mod.pregnancy_stage]` | custom |" in output


def test_render_condition_functions_shows_signature() -> None:
    entries = [
        Entry(
            name = "check_approval",
            metadata = (
                ("signature", "check_approval(Character, threshold: str) -> bool"),
                ("source_file", "core/mechanics/approval.rpy"),
            ),
        ),
    ]

    output = _render_condition_functions(entries)

    assert "`check_approval`" in output
    assert "check_approval(Character, threshold: str) -> bool" in output


def test_render_character_skips_empty_subsections() -> None:
    char = CharacterData(
        name = "Rogue",
        faces = [Entry(name = "glare")],
    )

    output = _render_character(char)

    assert "### Rogue" in output
    assert "#### Faces" in output
    assert "| `glare` |" in output
    # No empty mood/pose/etc. heading should appear.
    assert "#### Moods" not in output
    assert "#### Poses" not in output
    assert "#### Arms" not in output


def test_render_per_character_sorts_alphabetically() -> None:
    per_char = {
        "Rogue": CharacterData(name = "Rogue", faces = [Entry(name = "glare")]),
        "JeanGrey": CharacterData(name = "JeanGrey", faces = [Entry(name = "smile")]),
    }

    output = _render_per_character(per_char)

    assert output.index("### JeanGrey") < output.index("### Rogue")


def test_render_empty_sections_produce_placeholder_note() -> None:
    data = CheatsheetData(generated_at = "2026-04-23", source_label = "Mod")

    output = render(data)

    assert "_No characters registered yet._" in output
    assert "_No character-specific authoring values registered yet._" in output


def test_render_fills_template_placeholders_from_real_fixture(allowlists_dir: Path) -> None:
    """Smoke test: render() on real fixture data leaves no unreplaced placeholder."""
    data = load(allowlists_dir)

    output = render(data)

    assert "{{generated_at}}" not in output
    assert "{{source_label}}" not in output
    assert "{{speakers}}" not in output
    assert "{{per_character}}" not in output
    assert "{{condition_functions}}" not in output
