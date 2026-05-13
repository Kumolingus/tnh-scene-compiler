"""Render a :class:`CheatsheetData` into the final ``Authoring_Cheatsheet.md``.

The renderer is a pure function: it reads a template file, fills every
``{{placeholder}}`` with generated markdown, and returns the resulting string.
No file writes happen here — the CLI handles I/O.

Section-rendering helpers are independent so tests can cover them one by one
without assembling a full document.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .models import CharacterData, CheatsheetData, Entry

DEFAULT_TEMPLATE_PATH = Path(__file__).parent / "templates" / "cheatsheet.md.tmpl"


def _sorted_entries(entries: list[Entry]) -> list[Entry]:
    """Stable alphabetical sort by entry name (case-insensitive)."""
    return sorted(entries, key = lambda entry: entry.name.lower())


def _empty_note(what: str) -> str:
    """Placeholder markdown for an empty section."""
    return f"_No {what} registered yet._"


def _render_speakers(entries: list[Entry]) -> str:
    """Emit the Speakers table: UPPERCASE form and PascalCase reference."""
    if not entries:
        return _empty_note("characters")

    lines = [
        "| Write in dialogue | Refer to as (in `[[if]]`, interpolation) |",
        "|---|---|",
    ]
    for entry in _sorted_entries(entries):
        # Builtins like Narrator need a special rendering because the dialogue
        # convention is to leave the speaker tag blank.
        if entry.name == "Narrator":
            lines.append("| _(leave speaker blank)_ | `narrator` |")
            continue
        uppercase = entry.name.upper()
        lines.append(f"| `{uppercase}` | `{entry.name}` |")
    return "\n".join(lines)


def _render_single_column(entries: list[Entry], header: str) -> str:
    """Emit a one-column table of value names."""
    if not entries:
        return _empty_note(header.lower())

    lines = [f"| {header} |", "|---|"]
    lines.extend(f"| `{entry.name}` |" for entry in _sorted_entries(entries))
    return "\n".join(lines)


def _render_stages(entries: list[Entry]) -> str:
    return _render_single_column(entries, "Stage")


def _render_sfx(entries: list[Entry]) -> str:
    return _render_single_column(entries, "SFX name")


def _render_looks(entries: list[Entry]) -> str:
    return _render_single_column(entries, "Look")


def _render_shared_moods(entries: list[Entry]) -> str:
    return _render_single_column(entries, "Mood")


def _render_locations(entries: list[Entry]) -> str:
    """Emit the Locations table with slugline / location_id / display_name / source."""
    if not entries:
        return _empty_note("locations")

    lines = [
        "| Slugline text | Location ID | Display name | Source |",
        "|---|---|---|---|",
    ]
    for entry in _sorted_entries(entries):
        meta = dict(entry.metadata)
        location_id = meta.get("location_id", "")
        display_name = meta.get("display_name", "")
        source = entry.provenance or ""
        lines.append(
            f"| `{entry.name}` | `{location_id}` | {display_name} | {source} |",
        )
    return "\n".join(lines)


def _render_interpolation(entries: list[Entry]) -> str:
    """Emit the Interpolation paths table with path and source tag."""
    if not entries:
        return _empty_note("interpolation paths")

    lines = ["| Path | Source |", "|---|---|"]
    for entry in _sorted_entries(entries):
        lines.append(f"| `[{entry.name}]` | {entry.provenance or 'auto'} |")
    return "\n".join(lines)


def _render_condition_functions(entries: list[Entry]) -> str:
    """Emit the Condition functions table with name, signature, source file."""
    if not entries:
        return _empty_note("condition functions")

    lines = [
        "| Name | Signature | Source file |",
        "|---|---|---|",
    ]
    for entry in _sorted_entries(entries):
        meta = dict(entry.metadata)
        signature = meta.get("signature", "")
        source_file = meta.get("source_file", "")
        lines.append(f"| `{entry.name}` | `{signature}` | `{source_file}` |")
    return "\n".join(lines)


def _render_character_subsection(title: str, entries: list[Entry]) -> list[str]:
    """Emit the ``#### <title>`` block for one character category.

    Returns the block's lines (or an empty list when the list is empty, so the
    character heading does not show empty sub-sections).
    """
    if not entries:
        return []

    block = [f"#### {title}", "", "| Value |", "|---|"]
    block.extend(f"| `{entry.name}` |" for entry in _sorted_entries(entries))
    block.append("")
    return block


def _render_character(char: CharacterData) -> str:
    """Emit the ``### <Character>`` section with all non-empty subsections."""
    lines: list[str] = [f"### {char.name}", ""]

    lines.extend(_render_character_subsection("Moods (character-specific)", char.moods))
    lines.extend(_render_character_subsection("Faces", char.faces))
    lines.extend(_render_character_subsection("Poses", char.poses))
    lines.extend(_render_character_subsection("Arms", char.arms))
    lines.extend(_render_character_subsection("Left arm", char.arms_left))
    lines.extend(_render_character_subsection("Right arm", char.arms_right))
    lines.extend(_render_character_subsection("Outfits", char.outfits))

    # Trim trailing blank line left by the last sub-section for tidy output.
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _render_per_character(per_character: dict[str, CharacterData]) -> str:
    """Emit every per-character block sorted alphabetically by name."""
    if not per_character:
        return _empty_note("character-specific authoring values")

    blocks: list[str] = []
    for name in sorted(per_character):
        char = per_character[name]
        if not char.has_any():
            continue
        blocks.append(_render_character(char))
    return "\n\n".join(blocks)


# ``_SECTION_RENDERERS`` maps template placeholders to a callable that pulls
# the relevant data off a :class:`CheatsheetData` and returns a markdown block.
_SECTION_RENDERERS: dict[str, Callable[[CheatsheetData], str]] = {
    "speakers": lambda data: _render_speakers(data.characters),
    "stages": lambda data: _render_stages(data.stages),
    "locations": lambda data: _render_locations(data.locations),
    "sfx": lambda data: _render_sfx(data.sfx),
    "looks": lambda data: _render_looks(data.looks),
    "shared_moods": lambda data: _render_shared_moods(data.shared_moods),
    "per_character": lambda data: _render_per_character(data.per_character),
    "interpolation": lambda data: _render_interpolation(data.interpolation),
    "condition_functions": lambda data: _render_condition_functions(data.condition_functions),
}


def render(data: CheatsheetData, *, template_path: Path | None = None) -> str:
    """Return the full cheatsheet markdown built from ``data`` and the template.

    The template file is the single source of truth for static prose; only
    ``{{placeholder}}`` tokens are substituted. Unknown placeholders are left
    untouched and will surface visibly in the output — this is deliberate, so
    typos are caught on first run instead of silently erased.
    """
    path = template_path or DEFAULT_TEMPLATE_PATH
    text = path.read_text(encoding = "utf-8")

    text = text.replace("{{generated_at}}", data.generated_at or "unknown")
    text = text.replace("{{source_label}}", data.source_label or "unknown")

    for placeholder, renderer in _SECTION_RENDERERS.items():
        text = text.replace("{{" + placeholder + "}}", renderer(data))

    return text
