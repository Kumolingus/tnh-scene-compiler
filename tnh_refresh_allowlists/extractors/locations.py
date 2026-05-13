"""Extract location slugline → location_id mappings.

Rules (spec §5.2):

- Scan every ``.rpy`` across TNH (when included) and the mod for
  ``define all_Locations["loc_..."] = {`` declarations with an explicit
  dict body.
- Use a naive brace counter to isolate the dict body, then find the
  ``"name": _("human text")`` (or ``"name": "human text"``) entry.
- Derive the slugline as ``display_name.upper()``.
- Emit one flat file ``locations.yaml`` with entries of the form::

    - name: "BAYVILLE MALL"
      source_file: ...
      source_line: 1
      location_id: loc_BayvilleTown_Mall
      display_name: Bayville Mall

- Also emit a ``locations_overrides.yaml`` scaffold on first run, never
  overwritten on subsequent runs, for manual slugline-to-location_id
  overrides a project may need.

Limitations (V2):

- Locations declared as ``all_Locations["loc_x"] = all_Locations["loc_y"].copy()``
  are skipped. A future pass can resolve them by looking up the parent's
  name, but for now the author receives a warning.
"""

from __future__ import annotations

import re

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext, Warning
from ..scanner import iter_all_rpy, safe_read_text

_EXPLICIT_LOCATION_RE = re.compile(
    r'^[ \t]*define[ \t]+all_Locations\[\s*"(?P<location_id>loc_[A-Za-z0-9_]+)"\s*\][ \t]*=[ \t]*\{',
    re.MULTILINE,
)

_COPY_LOCATION_RE = re.compile(
    r'^[ \t]*define[ \t]+all_Locations\[\s*"(?P<location_id>loc_[A-Za-z0-9_]+)"\s*\][ \t]*='
    r'[ \t]*all_Locations\[',
    re.MULTILINE,
)

_NAME_RE = re.compile(
    r'"name"\s*:\s*(?:_\(\s*)?"(?P<display>[^"]+)"\s*\)?',
)


def _find_block_end(text: str, open_brace_index: int) -> int | None:
    depth = 0
    for index in range(open_brace_index, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` with one slugline entry per location."""
    result = ExtractionResult(category = "locations")
    seen_ids: set[str] = set()

    for path in iter_all_rpy(context):
        text = safe_read_text(path)
        if text is None:
            continue

        cleaned = strip_noise(text)

        # Explicit dict locations.
        for match in _EXPLICIT_LOCATION_RE.finditer(cleaned):
            location_id = match.group("location_id")
            if location_id in seen_ids:
                continue

            open_brace = match.end() - 1
            end = _find_block_end(cleaned, open_brace)
            if end is None:
                result.warnings.append(
                    Warning(
                        message = f"Unbalanced braces for {location_id}",
                        source_file = context.relative(path),
                    ),
                )
                continue

            body = cleaned[open_brace + 1 : end]
            name_match = _NAME_RE.search(body)
            if name_match is None:
                result.warnings.append(
                    Warning(
                        message = f"Location {location_id} has no 'name' field",
                        source_file = context.relative(path),
                    ),
                )
                continue

            display_name = name_match.group("display")
            slugline = display_name.upper()
            line = cleaned[: match.start()].count("\n") + 1

            result.entries.append(
                AllowlistEntry(
                    name = slugline,
                    source_file = context.relative(path),
                    source_line = line,
                    metadata = (
                        ("location_id", location_id),
                        ("display_name", display_name),
                    ),
                ),
            )
            seen_ids.add(location_id)

        # .copy()-style locations — warn and skip for V1.
        for match in _COPY_LOCATION_RE.finditer(cleaned):
            location_id = match.group("location_id")
            if location_id in seen_ids:
                continue
            line = cleaned[: match.start()].count("\n") + 1
            result.warnings.append(
                Warning(
                    message = (
                        f"Location {location_id} is declared via .copy() and is not resolved "
                        f"in V1; add it manually to locations_overrides.yaml if needed"
                    ),
                    source_file = f"{context.relative(path)}:{line}",
                ),
            )

    return result
