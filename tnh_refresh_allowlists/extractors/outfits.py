"""Extract outfit names per character.

Rules (spec §5.4):

- Scan every ``.rpy`` across TNH (when included) and the mod.
- Match ``OutfitClass(<Character>, "<name>", ...)`` constructor calls — this
  is the canonical registration pattern observed in base-game character
  folders under ``clothing/outfits.rpy``.
- Produce one output file per character under ``outfits/<Character>.yaml``.
- Duplicate outfit names per character are deduplicated, keeping the first
  occurrence.
"""

from __future__ import annotations

import re

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import iter_all_rpy, safe_read_text

_OUTFIT_RE = re.compile(
    r'OutfitClass\s*\(\s*(?P<character>[A-Z][A-Za-z0-9]+)\s*,\s*"(?P<name>[^"]+)"',
    re.DOTALL,
)

# Generic identifiers used as function parameters or stand-ins for "any
# character", never a real instance. The regex above cannot distinguish
# `OutfitClass(Character, "...")` in a helper from
# `OutfitClass(JeanGrey, "...")` in a real definition, so we filter here.
_GENERIC_IDENTIFIERS: frozenset[str] = frozenset(
    {"Character", "Companion", "NPC", "Owner", "Silhouette", "Sprite", "Outfit", "Self"},
)


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` keyed by character with an outfit list each."""
    result = ExtractionResult(category = "outfits")

    for path in iter_all_rpy(context):
        text = safe_read_text(path)
        if text is None:
            continue

        cleaned = strip_noise(text)
        seen_per_character: dict[str, set[str]] = {}
        for match in _OUTFIT_RE.finditer(cleaned):
            character = match.group("character")
            if character in _GENERIC_IDENTIFIERS:
                continue
            name = match.group("name")
            seen = seen_per_character.setdefault(character, set())
            if name in seen:
                continue
            seen.add(name)

            line = cleaned[: match.start()].count("\n") + 1
            entry = AllowlistEntry(
                name = name,
                source_file = context.relative(path),
                source_line = line,
            )
            result.per_character.setdefault(character, []).append(entry)

    _deduplicate_global(result)
    return result


def _deduplicate_global(result: ExtractionResult) -> None:
    """Drop duplicate outfit names per character across multiple source files."""
    for character, entries in result.per_character.items():
        seen: set[str] = set()
        deduped: list[AllowlistEntry] = []
        for entry in entries:
            if entry.name in seen:
                continue
            seen.add(entry.name)
            deduped.append(entry)
        result.per_character[character] = deduped
