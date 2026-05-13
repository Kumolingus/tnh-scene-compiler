"""Data classes shared by the loader and the renderer."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Entry:
    """One named allowlist entry, carrying a provenance label.

    Attributes:
        name: The value itself (mood name, slugline text, interpolation path, ...).
        provenance: A short tag shown to the reader when the origin matters
            (e.g. ``"shared"``, ``"character"``, ``"auto"``, ``"override"``,
            ``"custom"``). Empty string when provenance is irrelevant for that
            category.
        metadata: Optional extra key/value pairs emitted alongside the entry in
            tables (e.g. ``location_id`` for locations). Stored as a tuple so
            the dataclass stays frozen/hashable.
    """

    name: str
    provenance: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(slots=True)
class CharacterData:
    """Per-character authoring values grouped by category.

    Each list contains :class:`Entry` objects. Lists are kept separately so
    the renderer can emit one table per category under a character heading.
    ``arms_left`` and ``arms_right`` carry the subgroup split produced by the
    arms extractor (``left_arm``, ``right_arm`` YAML keys).

    Attributes:
        name: The character's PascalCase identifier (e.g. ``"JeanGrey"``).
        moods: Character-specific moods, excluding the shared list.
        faces: All face values for this character.
        poses: All pose values for this character.
        arms: Both-arms presets (YAML ``arms`` subgroup).
        arms_left: Left-arm values (YAML ``left_arm`` subgroup).
        arms_right: Right-arm values (YAML ``right_arm`` subgroup).
        outfits: All outfit values for this character.
    """

    name: str
    moods: list[Entry] = field(default_factory = list)
    faces: list[Entry] = field(default_factory = list)
    poses: list[Entry] = field(default_factory = list)
    arms: list[Entry] = field(default_factory = list)
    arms_left: list[Entry] = field(default_factory = list)
    arms_right: list[Entry] = field(default_factory = list)
    outfits: list[Entry] = field(default_factory = list)

    def has_any(self) -> bool:
        """Return ``True`` if this character has at least one authoring value."""
        return bool(
            self.moods
            or self.faces
            or self.poses
            or self.arms
            or self.arms_left
            or self.arms_right
            or self.outfits,
        )


@dataclass(slots=True)
class CheatsheetData:
    """All data loaded from scenes_source/_allowlists/ ready for rendering.

    The loader produces one of these; the renderer consumes it and emits the
    markdown cheatsheet. No I/O happens inside the renderer.

    Attributes:
        generated_at: ISO-8601 timestamp from the allowlists ``_meta.yaml`` run
            (or a fresh one when ``_meta.yaml`` is missing).
        source_label: Human-readable origin label (``"TNH + Mod"`` or similar),
            read from any flat allowlist file.
        characters: Full speaker list from ``characters.yaml`` (every entry,
            sorted alphabetically, ``<builtin>`` preserved).
        stages: Entries from ``stages.yaml``.
        locations: Merged ``locations.yaml`` + ``locations_overrides.yaml``.
            Override entries carry ``provenance="override"``, auto entries
            carry ``provenance="auto"``.
        sfx: Entries from ``sfx.yaml``.
        looks: Entries from ``looks.yaml``.
        shared_moods: Entries from ``moods/_shared.yaml``. Empty when the file
            is absent.
        interpolation: Merged ``interpolation.yaml`` + ``interpolation_custom.yaml``.
            Auto paths carry ``provenance="auto"``, custom paths carry
            ``provenance="custom"``.
        condition_functions: Entries from the manual
            ``condition_functions.yaml`` (each entry's ``metadata`` holds
            ``signature`` and ``source_file``).
        per_character: Mapping character-name -> :class:`CharacterData`,
            populated only for characters that have at least one authoring
            value across moods/faces/poses/arms/outfits.
        warnings: Non-fatal loader warnings (missing file, malformed entry,
            ...). Surfaced by the CLI in verbose mode.
    """

    generated_at: str = ""
    source_label: str = ""
    characters: list[Entry] = field(default_factory = list)
    stages: list[Entry] = field(default_factory = list)
    locations: list[Entry] = field(default_factory = list)
    sfx: list[Entry] = field(default_factory = list)
    looks: list[Entry] = field(default_factory = list)
    shared_moods: list[Entry] = field(default_factory = list)
    interpolation: list[Entry] = field(default_factory = list)
    condition_functions: list[Entry] = field(default_factory = list)
    per_character: dict[str, CharacterData] = field(default_factory = dict)
    warnings: list[str] = field(default_factory = list)
