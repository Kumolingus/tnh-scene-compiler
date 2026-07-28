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

# The compiler can only place a character at one of the three on-screen slots
# that ``add_Characters`` understands (see ``codegen._STAGE_DIRECTION_MAP``).
# TNH also defines far-stage X-coordinates (``stage_far_left``,
# ``stage_far_far_right``, …) for absolute ``show_Character(x=…)`` placement,
# but the compiler has no emission path for those. Excluding them here keeps
# the allowlist to the values a scene can actually use — a far-stage becomes a
# "not a valid stage" compile error instead of a silent no-op in the output.
_EMITTABLE_STAGES = frozenset({"stage_left", "stage_center", "stage_right"})


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
        name = match.group("name")
        if name not in _EMITTABLE_STAGES:
            # Far-stage coordinate with no add_Characters emission path — skip.
            continue
        line_number = cleaned[: match.start()].count("\n") + 1
        result.entries.append(
            AllowlistEntry(
                name = name,
                source_file = context.relative(path),
                source_line = line_number,
            ),
        )

    return result
