"""Extract history event names from TNH and the mod.

Scans for event strings passed to the History tracking API:

- ``History.check("event_name")``
- ``History.add("event_name")``
- ``History.record("event_name")``
- ``.did("event_name")`` (DSL sugar)
"""

from __future__ import annotations

import re

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import iter_all_rpy, safe_read_text

# Matches History.check("..."), History.add("..."), History.record("...")
_HISTORY_API_RE = re.compile(
    r'History\.(?:check|add|record)\(\s*"(?P<name>[^"]+)"\s*\)',
    re.MULTILINE,
)

# Matches .did("...") — DSL sugar that also appears in source
_DID_RE = re.compile(
    r'\.did\(\s*"(?P<name>[^"]+)"\s*\)',
    re.MULTILINE,
)


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` with one entry per history event."""
    result = ExtractionResult(category = "history_events")
    seen: set[str] = set()

    for path in iter_all_rpy(context):
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
