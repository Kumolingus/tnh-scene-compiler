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
    r'^[ \t]*define[ \t]+base_moods\["(?P<name>[^"]+)"\][ \t]*=[ \t]*\{',
    re.MULTILINE,
)

_PER_CHAR_RE = re.compile(
    r'^[ \t]*define[ \t]+(?P<character>[A-Z][A-Za-z0-9]+)_moods\["(?P<name>[^"]+)"\][ \t]*=[ \t]*\{',
    re.MULTILINE,
)

_LEGACY_BASE_PER_CHAR_RE = re.compile(
    r'^[ \t]*define[ \t]+base_moods_(?P<character>[A-Z][A-Za-z0-9]+)\["(?P<name>[^"]+)"\][ \t]*=[ \t]*\{',
    re.MULTILINE,
)

_FACES_KEY_RE = re.compile(r'"faces"[ \t]*:[ \t]*\{')

_FACE_ENTRY_RE = re.compile(r'"(?P<face>[^"]+)"[ \t]*:[ \t]*\{')


def _find_block_end(text: str, open_brace: int) -> int | None:
    depth = 0
    for i in range(open_brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return None


def _extract_mood_faces(cleaned: str, match_end: int) -> str:
    """Extract face names from the mood definition block starting at match_end - 1."""
    open_brace = match_end - 1
    end = _find_block_end(cleaned, open_brace)
    if end is None:
        return ""
    block = cleaned[open_brace + 1:end]

    faces_match = _FACES_KEY_RE.search(block)
    if not faces_match:
        return ""
    faces_open = faces_match.end() - 1 + (open_brace + 1)
    faces_end = _find_block_end(cleaned, faces_open)
    if faces_end is None:
        return ""
    faces_block = cleaned[faces_open + 1:faces_end]

    face_names = [m.group("face") for m in _FACE_ENTRY_RE.finditer(faces_block)]
    return ",".join(face_names)


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
            faces = _extract_mood_faces(cleaned, match.end())
            metadata: tuple[tuple[str, str], ...] = ()
            if faces:
                metadata = (("faces", faces),)
            result.entries.append(
                AllowlistEntry(
                    name = name,
                    source_file = context.relative(path),
                    source_line = line,
                    metadata = metadata,
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
                faces = _extract_mood_faces(cleaned, match.end())
                metadata = ()
                if faces:
                    metadata = (("faces", faces),)
                result.per_character.setdefault(character, []).append(
                    AllowlistEntry(
                        name = name,
                        source_file = context.relative(path),
                        source_line = line,
                        metadata = metadata,
                    ),
                )

    return result
