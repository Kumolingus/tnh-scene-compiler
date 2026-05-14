"""Extract character trait names from TNH and the mod.

Scans for string arguments passed to trait-related method calls:
``give_trait("...")``, ``check_trait("...")``, ``remove_trait("...")``,
and ``has_trait("...")``. Trait names are game-wide, so entries are flat
(not per-character).
"""

from __future__ import annotations

import re

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import iter_all_rpy, safe_read_text

# Matches give_trait("x"), check_trait("x"), remove_trait("x"), has_trait("x").
_TRAIT_RE = re.compile(
    r"""(?:give_trait|check_trait|remove_trait|has_trait)\(\s*"(?P<name>[^"]+)"\s*\)""",
    re.MULTILINE,
)


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` with one entry per unique trait name."""
    result = ExtractionResult(category = "traits")
    seen: set[str] = set()

    for path in iter_all_rpy(context):
        text = safe_read_text(path)
        if text is None:
            continue

        cleaned = strip_noise(text)

        for match in _TRAIT_RE.finditer(cleaned):
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
