"""Extract the feature names each character supports.

Rules:

- Scan every ``.rpy`` across TNH (when included) and the mod.
- Match ``define <Character>_supported_features = {"a", "b", ...}`` — the
  registration pattern used by ``characters/<Character>/definitions/features.rpy``
  and read back by ``NPCClass.supported_features``
  (``core/definitions/npcs.rpy``).
- Produce one output file per character under ``features/<Character>.yaml``.
- Duplicate names within a character are dropped, keeping the first occurrence.

The sets are genuinely per-character and share no common value: in the
2026-07 build they range from 2 entries (CharlesXavier) to 23 (Rogue), which
is why this is extracted per character rather than as one flat list.

``Character.feature_enabled(name)`` also answers True for a *trait* of the
same name, but traits carry their own allowlist — only the declared feature
sets are collected here.
"""

from __future__ import annotations

import re

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import iter_all_rpy, safe_read_text

_FEATURES_RE = re.compile(
    r"define\s+(?P<character>[A-Z][A-Za-z0-9]+)_supported_features\s*=\s*"
    r"\{(?P<body>[^}]*)\}",
    re.DOTALL,
)
_VALUE_RE = re.compile(r'"(?P<name>[^"]+)"')


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` keyed by character with a feature list each."""
    result = ExtractionResult(category = "features")

    for path in iter_all_rpy(context):
        text = safe_read_text(path)
        if text is None:
            continue

        cleaned = strip_noise(text)
        for block in _FEATURES_RE.finditer(cleaned):
            character = block.group("character")
            entries = result.per_character.setdefault(character, [])
            seen = {entry.name for entry in entries}
            body_start = block.start("body")

            for match in _VALUE_RE.finditer(block.group("body")):
                name = match.group("name")
                if name in seen:
                    continue
                seen.add(name)

                line = cleaned[: body_start + match.start()].count("\n") + 1
                entries.append(
                    AllowlistEntry(
                        name = name,
                        source_file = context.relative(path),
                        source_line = line,
                    ),
                )

    return result
