"""Extract mood identifiers from TNH and the mod, split into shared vs per-character.

Rules (spec §5.3):

- Keys declared via ``define base_moods["<name>"]`` go into the shared pool
  and are emitted to ``moods/_shared.yaml``.
- Keys declared via ``define <Character>_moods["<name>"]`` (or the legacy
  ``define base_moods_<Character>["<name>"]`` variant) go into the per-
  character pool and are emitted to ``moods/<Character>.yaml``. Per-
  character files get an ``inherits_from_shared: _shared.yaml`` pointer
  so consumers assemble the full list for one character.
"""

from __future__ import annotations

import re

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import iter_all_rpy, safe_read_text

_SHARED_RE = re.compile(
    r'^[ \t]*define[ \t]+base_moods\["(?P<name>[^"]+)"\]',
    re.MULTILINE,
)

_PER_CHAR_RE = re.compile(
    r'^[ \t]*define[ \t]+(?P<character>[A-Z][A-Za-z0-9]+)_moods\["(?P<name>[^"]+)"\]',
    re.MULTILINE,
)

_LEGACY_BASE_PER_CHAR_RE = re.compile(
    r'^[ \t]*define[ \t]+base_moods_(?P<character>[A-Z][A-Za-z0-9]+)\["(?P<name>[^"]+)"\]',
    re.MULTILINE,
)


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` with shared entries plus per-character pots."""
    result = ExtractionResult(category = "moods")
    shared_seen: set[str] = set()
    per_char_seen: dict[str, set[str]] = {}

    for path in iter_all_rpy(context):
        text = safe_read_text(path)
        if text is None:
            continue

        cleaned = strip_noise(text)

        for match in _SHARED_RE.finditer(cleaned):
            name = match.group("name")
            if name in shared_seen:
                continue
            shared_seen.add(name)
            line = cleaned[: match.start()].count("\n") + 1
            result.entries.append(
                AllowlistEntry(
                    name = name,
                    source_file = context.relative(path),
                    source_line = line,
                ),
            )

        for pattern in (_PER_CHAR_RE, _LEGACY_BASE_PER_CHAR_RE):
            for match in pattern.finditer(cleaned):
                character = match.group("character")
                name = match.group("name")
                seen = per_char_seen.setdefault(character, set())
                if name in seen:
                    continue
                seen.add(name)
                line = cleaned[: match.start()].count("\n") + 1
                result.per_character.setdefault(character, []).append(
                    AllowlistEntry(
                        name = name,
                        source_file = context.relative(path),
                        source_line = line,
                    ),
                )

    return result
