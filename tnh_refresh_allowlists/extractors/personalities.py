"""Extract personality trait names used across TNH and the mod.

Collects, in either quote, from ``.rpy`` files and the game's ``.py`` modules:

- the first string argument of ``check_personality()``, ``set_personality()``
  and ``personality_score()``;
- the trait of ``update_personality(Character, "trait", …)``;
- the key of a ``personality["trait"]`` subscript — how TNH sets a score
  (``$ Rogue.personality["submissive"] = 1``) and the only way it reads the
  player's leanings.
"""

from __future__ import annotations

import re

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import iter_all_sources, safe_read_text

_NAME = r"""(?P<quote>["'])(?P<name>[^"'{}\n]+)(?P=quote)"""

_PERSONALITY_RE = re.compile(
    r"(?:(?:check_personality|set_personality|personality_score)\(\s*"
    r"|update_personality\(\s*[\w.]+\s*,\s*"
    r"|\bpersonality\[\s*)" + _NAME,
    re.MULTILINE,
)


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` with one entry per personality trait."""
    result = ExtractionResult(category = "personalities")
    seen: set[str] = set()

    for path in iter_all_sources(context):
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
