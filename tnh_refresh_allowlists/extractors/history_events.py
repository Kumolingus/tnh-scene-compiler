"""Extract history event names from TNH and the mod.

Scans for the literal first argument of the History tracking API, in either
quote and followed by more arguments or not
(``History.check('sleepover', tracker = 'yesterday')``):

- ``History.update`` — the recording call since TNH 0.9c.beta.28
  (``core/base/history.py``); ``add`` and ``record``, its older spellings
- ``History.check``, ``check_when``, ``remove``
- ``.did("event_name")`` (DSL sugar)

Both ``.rpy`` files and the game's ``.py`` modules are read. An f-string
argument names no single event and is skipped.
"""

from __future__ import annotations

import re

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import iter_all_sources, safe_read_text

_LITERAL = r"""\(\s*(?P<quote>["'])(?P<name>[^"'{}\n]+)(?P=quote)\s*[,)]"""

_HISTORY_API_RE = re.compile(
    r"History\.(?:update|check|check_when|remove|add|record)" + _LITERAL,
    re.MULTILINE,
)

# .did("...") — DSL sugar that also appears in source
_DID_RE = re.compile(r"\.did" + _LITERAL, re.MULTILINE)


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` with one entry per history event."""
    result = ExtractionResult(category = "history_events")
    seen: set[str] = set()

    for path in iter_all_sources(context):
        text = safe_read_text(path)
        if text is None:
            continue

        cleaned = strip_noise(text)

        for pattern in (_HISTORY_API_RE, _DID_RE):
            for match in pattern.finditer(cleaned):
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
