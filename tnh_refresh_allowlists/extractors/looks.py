"""Extract the list of valid look directions.

Rules (spec §5.4):

- V1 ships a hardcoded baseline (``at_player``, ``away``, ``down``, ``up``,
  ``left``, ``right``, ``neutral``) shared across every character.
- TNH base source contains no direct ``change_look(...)`` calls, so the
  mod-side scan that the spec mentions has nothing to pick up yet.
  When the mod (or a future extension) introduces custom look names, add
  a scanner here that greps for the actual registration pattern.

For simplicity, V1 emits a flat ``looks.yaml`` rather than a per-character
file tree. A per-character split is future work, driven by real data.
"""

from __future__ import annotations

from ..models import AllowlistEntry, ExtractionResult, ScanContext

_HARDCODED_LOOKS: tuple[str, ...] = (
    "at_player",
    "away",
    "closed",
    "down",
    "left",
    "neutral",
    "right",
    "up",
)


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` containing the hardcoded look baseline."""
    result = ExtractionResult(category = "looks")
    for name in _HARDCODED_LOOKS:
        result.entries.append(
            AllowlistEntry(name = name, source_file = "<builtin>", source_line = 0),
        )
    return result
