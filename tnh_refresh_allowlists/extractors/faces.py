"""Extract the list of valid face expressions per character.

Rules (spec §5.4):

- Scan every ``.rpy`` across TNH (when included) and the mod.
- Match ``define <Character>_faces["<name>"]`` declarations; the
  character name is inferred from the identifier before ``_faces``.
- Produce one output file per character under ``faces/<Character>.yaml``.
"""

from __future__ import annotations

import re

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import iter_all_rpy, safe_read_text

_FACE_RE = re.compile(
    r'^[ \t]*define[ \t]+(?P<character>[A-Z][A-Za-z0-9]+)_faces\["(?P<name>[^"]+)"\]',
    re.MULTILINE,
)


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` keyed by character with a face list each."""
    result = ExtractionResult(category = "faces")

    for path in iter_all_rpy(context):
        text = safe_read_text(path)
        if text is None:
            continue

        cleaned = strip_noise(text)
        for match in _FACE_RE.finditer(cleaned):
            character = match.group("character")
            name = match.group("name")
            line = cleaned[: match.start()].count("\n") + 1
            entry = AllowlistEntry(
                name = name,
                source_file = context.relative(path),
                source_line = line,
            )
            result.per_character.setdefault(character, []).append(entry)

    return result
