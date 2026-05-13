"""Load YAML allowlists from ``scenes_source/_allowlists/`` into a CheatsheetData.

The loader never raises on a missing optional file: it records a warning and
keeps going. This matches the cheatsheet-generation contract — a partially
populated allowlist set still produces a useful document.

Merge rules (from the rework plan, step 5):

* ``locations.yaml`` (auto) + ``locations_overrides.yaml`` (manual). When a
  slugline appears in both, the override wins and the entry is tagged
  ``"override"``. Auto-only entries are tagged ``"auto"``.
* ``moods/_shared.yaml`` + ``moods/<Character>.yaml``. The shared list is
  attached to :attr:`CheatsheetData.shared_moods` once; each character keeps
  only their specific moods (``CharacterData.moods``) to avoid duplication.
* ``interpolation.yaml`` (auto) + ``interpolation_custom.yaml`` (manual).
  Concatenated; auto entries tagged ``"auto"``, custom entries tagged
  ``"custom"``. Duplicates are preserved — the compiler will dedupe later.
* ``condition_functions.yaml`` is manual only. Metadata is reflected into
  per-entry ``metadata`` tuples (``signature``, ``source_file``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import CharacterData, CheatsheetData, Entry

_PER_CHARACTER_CATEGORIES = ("moods", "faces", "poses", "arms", "outfits")


def _read_yaml(path: Path) -> dict[str, Any] | None:
    """Read a YAML file and return its top-level mapping, or ``None`` on miss."""
    if not path.is_file():
        return None
    with path.open("r", encoding = "utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        return None
    return data


def _entries_from_values(
    values: list[dict[str, Any]] | None,
    *,
    provenance: str = "",
) -> list[Entry]:
    """Convert a YAML ``values: [...]`` list to :class:`Entry` objects.

    Fields other than ``name``, ``source_file`` and ``source_line`` are kept as
    metadata so category-specific info (``location_id``, ``display_name``, ...)
    survives to the renderer.
    """
    if not values:
        return []
    entries: list[Entry] = []
    skip_keys = {"name", "source_file", "source_line"}
    for item in values:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str):
            continue
        metadata = tuple(
            (key, str(value))
            for key, value in item.items()
            if key not in skip_keys and value is not None
        )
        entries.append(Entry(name = name, provenance = provenance, metadata = metadata))
    return entries


def _load_characters(allowlists: Path, data: CheatsheetData) -> None:
    """Populate ``data.characters`` from ``characters.yaml``."""
    payload = _read_yaml(allowlists / "characters.yaml")
    if payload is None:
        data.warnings.append("characters.yaml missing or unreadable")
        return
    data.characters = _entries_from_values(payload.get("values"))
    if not data.source_label and isinstance(payload.get("source"), str):
        data.source_label = payload["source"]


def _load_stages(allowlists: Path, data: CheatsheetData) -> None:
    payload = _read_yaml(allowlists / "stages.yaml")
    if payload is None:
        data.warnings.append("stages.yaml missing or unreadable")
        return
    data.stages = _entries_from_values(payload.get("values"))


def _load_sfx(allowlists: Path, data: CheatsheetData) -> None:
    payload = _read_yaml(allowlists / "sfx.yaml")
    if payload is None:
        data.warnings.append("sfx.yaml missing or unreadable")
        return
    data.sfx = _entries_from_values(payload.get("values"))


def _load_looks(allowlists: Path, data: CheatsheetData) -> None:
    payload = _read_yaml(allowlists / "looks.yaml")
    if payload is None:
        data.warnings.append("looks.yaml missing or unreadable")
        return
    data.looks = _entries_from_values(payload.get("values"))


def _load_locations(allowlists: Path, data: CheatsheetData) -> None:
    """Merge ``locations.yaml`` with ``locations_overrides.yaml``.

    Entries are matched by ``name`` (the slugline text). Overrides win.
    """
    auto_payload = _read_yaml(allowlists / "locations.yaml")
    override_payload = _read_yaml(allowlists / "locations_overrides.yaml")

    auto_entries = _entries_from_values(
        auto_payload.get("values") if auto_payload else None,
        provenance = "auto",
    )
    override_entries = _entries_from_values(
        override_payload.get("overrides") if override_payload else None,
        provenance = "override",
    )

    by_name: dict[str, Entry] = {entry.name: entry for entry in auto_entries}
    for entry in override_entries:
        by_name[entry.name] = entry

    data.locations = sorted(by_name.values(), key = lambda entry: entry.name.lower())


def _load_interpolation(allowlists: Path, data: CheatsheetData) -> None:
    """Concatenate ``interpolation.yaml`` (auto) and ``interpolation_custom.yaml``."""
    auto_payload = _read_yaml(allowlists / "interpolation.yaml")
    custom_payload = _read_yaml(allowlists / "interpolation_custom.yaml")

    auto_entries = _entries_from_values(
        auto_payload.get("values") if auto_payload else None,
        provenance = "auto",
    )

    # The custom file uses ``paths:`` rather than ``values:`` and entries can be
    # either bare strings or mappings with a ``name`` field. Normalise here.
    custom_entries: list[Entry] = []
    raw_paths = custom_payload.get("paths") if custom_payload else None
    if isinstance(raw_paths, list):
        for item in raw_paths:
            if isinstance(item, str):
                custom_entries.append(Entry(name = item, provenance = "custom"))
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                custom_entries.append(Entry(name = item["name"], provenance = "custom"))

    data.interpolation = auto_entries + custom_entries


def _load_condition_functions(allowlists: Path, data: CheatsheetData) -> None:
    """Load the manual ``condition_functions.yaml``.

    Each function is emitted with ``signature`` and ``source_file`` as metadata
    so the renderer can show them as a single compact table.
    """
    payload = _read_yaml(allowlists / "condition_functions.yaml")
    if payload is None:
        data.warnings.append("condition_functions.yaml missing or unreadable")
        return

    functions = payload.get("functions")
    if not isinstance(functions, list):
        return

    entries: list[Entry] = []
    for func in functions:
        if not isinstance(func, dict) or not isinstance(func.get("name"), str):
            continue
        metadata = (
            ("signature", str(func.get("signature", ""))),
            ("source_file", str(func.get("source_file", ""))),
        )
        entries.append(Entry(name = func["name"], metadata = metadata))
    data.condition_functions = entries


def _load_shared_moods(allowlists: Path, data: CheatsheetData) -> None:
    payload = _read_yaml(allowlists / "moods" / "_shared.yaml")
    if payload is None:
        return
    data.shared_moods = _entries_from_values(payload.get("values"))


def _ensure_character(data: CheatsheetData, name: str) -> CharacterData:
    char = data.per_character.get(name)
    if char is None:
        char = CharacterData(name = name)
        data.per_character[name] = char
    return char


def _load_per_character(allowlists: Path, data: CheatsheetData) -> None:
    """Scan each per-character YAML directory and populate ``data.per_character``.

    A character is added to :attr:`CheatsheetData.per_character` only when it
    contributes at least one entry across the five categories. This keeps the
    "Per-character authoring values" section from listing speakers that have
    no authoring surface.
    """
    for category in _PER_CHARACTER_CATEGORIES:
        category_dir = allowlists / category
        if not category_dir.is_dir():
            data.warnings.append(f"{category}/ directory missing")
            continue

        for yaml_file in sorted(category_dir.glob("*.yaml")):
            if yaml_file.name.startswith("_"):
                continue

            character_name = yaml_file.stem
            payload = _read_yaml(yaml_file)
            if payload is None:
                continue
            char = _ensure_character(data, character_name)
            _populate_category(char, category, payload)

    # Drop any character that ended up empty (defensive — _populate_category
    # should not add empty stubs, but guard anyway).
    data.per_character = {
        name: char for name, char in data.per_character.items() if char.has_any()
    }


def _populate_category(char: CharacterData, category: str, payload: dict[str, Any]) -> None:
    """Fill the matching list on ``char`` from a per-character YAML payload."""
    if category == "moods":
        char.moods = _entries_from_values(payload.get("values"))
    elif category == "faces":
        char.faces = _entries_from_values(payload.get("values"))
    elif category == "poses":
        char.poses = _entries_from_values(payload.get("values"))
    elif category == "outfits":
        char.outfits = _entries_from_values(payload.get("values"))
    elif category == "arms":
        char.arms = _entries_from_values(payload.get("arms"))
        char.arms_left = _entries_from_values(payload.get("left_arm"))
        char.arms_right = _entries_from_values(payload.get("right_arm"))


def _load_meta(allowlists: Path, data: CheatsheetData) -> None:
    payload = _read_yaml(allowlists / "_meta.yaml")
    if payload is None:
        return
    generated_at = payload.get("generated_at")
    if isinstance(generated_at, str):
        data.generated_at = generated_at


def load(allowlists_dir: Path) -> CheatsheetData:
    """Load every allowlist YAML under ``allowlists_dir`` and return a snapshot.

    ``allowlists_dir`` is typically ``scenes_source/_allowlists/``. Missing
    files produce warnings rather than exceptions; the renderer tolerates
    empty sections and emits an explicit "no entries" note.
    """
    data = CheatsheetData()
    _load_characters(allowlists_dir, data)
    _load_stages(allowlists_dir, data)
    _load_locations(allowlists_dir, data)
    _load_sfx(allowlists_dir, data)
    _load_looks(allowlists_dir, data)
    _load_interpolation(allowlists_dir, data)
    _load_condition_functions(allowlists_dir, data)
    _load_shared_moods(allowlists_dir, data)
    _load_per_character(allowlists_dir, data)
    _load_meta(allowlists_dir, data)
    return data
