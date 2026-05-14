"""Extract personality trait names used across TNH and the mod.

Scans for calls to ``check_personality()``, ``set_personality()``, and
``personality_score()`` and collects the first string argument of each.
"""

from __future__ import annotations

import re

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import iter_all_rpy, safe_read_text

# Matches check_personality("name"), check_personality("name", 3),
# set_personality("name", value), and personality_score("name").
_PERSONALITY_RE = re.compile(
    r'(?:check_personality|set_personality|personality_score)\(\s*"(?P<name>[^"]+)"',
    re.MULTILINE,
)


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` with one entry per personality trait."""
    result = ExtractionResult(category = "personalities")
    seen: set[str] = set()

    for path in iter_all_rpy(context):
        text = safe_read_text(path)
        if text is None:
            continue

        cleaned = strip_noise(text)

        for match in _PERSONALITY_RE.finditer(cleaned):
            name = match.group("name")
            if name in seen:
                continue
            seen.add(name)
            line = cleaned[: match.start()].count("\n") + 1
            result.entries.append(
                AllowlistEntry(
                    name = name,
                    source_file = context.relative(path),
                    source_line = line,
                ),
            )

    return result
