"""Extract the list of valid stage position constants.

Rules (spec §5.5):

- Scan ``TheNullHypothesis/game/core/definitions/definitions.rpy`` for
  ``define stage_<name> = <value>`` lines and list every matching name.
- Short, stable list; no fallback discovery across other files.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext, Warning

_STAGE_RE = re.compile(r"^[ \t]*define[ \t]+(?P<name>stage_[A-Za-z0-9_]+)[ \t]*=", re.MULTILINE)


def _definitions_path(context: ScanContext) -> Path:
    return context.base_game_root / "game" / "core" / "definitions" / "definitions.rpy"


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` with one entry per stage constant."""
    result = ExtractionResult(category = "stages")

    if not context.include_tnh:
        return result

    path = _definitions_path(context)
    if not path.exists():
        result.warnings.append(
            Warning(
                message = f"Expected file not found: {context.relative(path)}",
                source_file = context.relative(path),
            ),
        )
        return result

    try:
        text = path.read_text(encoding = "utf-8")
    except UnicodeDecodeError:
        result.warnings.append(
            Warning(
                message = "Could not read file as UTF-8",
                source_file = context.relative(path),
            ),
        )
        return result

    cleaned = strip_noise(text)
    for match in _STAGE_RE.finditer(cleaned):
        line_number = cleaned[: match.start()].count("\n") + 1
        result.entries.append(
            AllowlistEntry(
                name = match.group("name"),
                source_file = context.relative(path),
                source_line = line_number,
            ),
        )

    return result
