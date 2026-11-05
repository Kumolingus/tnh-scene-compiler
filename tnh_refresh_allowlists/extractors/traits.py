"""Extract character trait names from TNH and the mod.

Scans for the sole literal argument of the flag-style trait methods —
``give_trait("x")``, ``check_trait("x")``, ``remove_trait("x")`` and the
older ``has_trait("x")`` — in either quote. Both ``.rpy`` files and the
game's ``.py`` modules are read: TNH 0.9c.beta.28 moved much of its logic
into Python. A trait given a value (``give_trait("records", data)``) or read
with ``get_trait`` holds data, not a flag, and a writer's ``[[give_trait]]``
would overwrite it with True, so those calls are not read. An f-string
argument names no single trait and is skipped. Trait names are game-wide,
so entries are flat (not per-character).
"""

from __future__ import annotations

import re

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import iter_all_sources, safe_read_text

_TRAIT_RE = re.compile(
    r"""(?:give_trait|check_trait|remove_trait|has_trait)\(\s*"""
    r"""(?P<quote>["'])(?P<name>[^"'{}\n]+)(?P=quote)\s*\)""",
    re.MULTILINE,
)


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` with one entry per unique trait name."""
    result = ExtractionResult(category = "traits")
    seen: set[str] = set()

    for path in iter_all_sources(context):
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
