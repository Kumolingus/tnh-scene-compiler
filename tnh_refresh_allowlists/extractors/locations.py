"""Extract location slugline → location_id mappings.

Rules (spec §5.2):

- Scan every ``.rpy`` across TNH (when included) and the mod for
  ``define ALL_LOCATIONS["<location_id>"] = {`` declarations with an
  explicit dict body. TNH 0.9c.beta.28 keys a location by area and room
  (``BayvilleTown.Mall``) or by a bare room key (``PlayerRoom``).
- Use a naive brace counter to isolate the dict body, then find the
  ``"name": _("human text")`` (or ``"name": "human text"``) entry.
- Derive the slugline as ``display_name.upper()``.
- Emit one flat file ``locations.yaml`` with entries of the form::

    - name: "BAYVILLE MALL"
      source_file: ...
      source_line: 1
      location_id: BayvilleTown.Mall
      display_name: Bayville Mall

- Also emit a ``locations_overrides.yaml`` scaffold on first run, never
  overwritten on subsequent runs, for manual slugline-to-location_id
  overrides a project may need.

- A slugline is emitted once. When two locations declare the same ``name``
  the first declaration keeps the slugline and the other is reported as a
  warning, since a scene addresses a location by slugline and nothing else.

TNH 0.9c.beta.28 declares a character's room once as a template
(``ALL_LOCATIONS["RogueRoom"]``), copies it into an area
(``define ALL_LOCATIONS["XavierSchool.RogueRoom"] = ALL_LOCATIONS["RogueRoom"].copy()``),
which is the room the game builds, and disables the template
(``ALL_LOCATIONS["RogueRoom"].update({"enabled": False})``). So:

- A ``.copy()`` location takes the name its parent declares, unless a later
  ``ALL_LOCATIONS[id].update(...)`` gives it one: a dict with a ``"name"``,
  or another location's fields (``.update(ALL_LOCATIONS["RogueShower"])``).
  The last update that names it wins.
- A location an update disables (``"enabled": False``) has no slugline: no
  scene can open in a room the game does not build.
- The two places TNH parks characters who are off the map, ``hold``
  ("Away") and ``busy`` (``core/locations/definitions.rpy``), have no
  slugline either: they have no scene behind them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext, Warning
from ..scanner import iter_all_rpy, safe_read_text

_ID = r'[A-Za-z_][A-Za-z0-9_.]*'
_LOCATION_ID = r'(?P<location_id>' + _ID + r')'

_EXPLICIT_LOCATION_RE = re.compile(
    r'^[ \t]*define[ \t]+ALL_LOCATIONS\[\s*"' + _LOCATION_ID + r'"\s*\][ \t]*=[ \t]*\{',
    re.MULTILINE,
)

_COPY_LOCATION_RE = re.compile(
    r'^[ \t]*define[ \t]+ALL_LOCATIONS\[\s*"' + _LOCATION_ID + r'"\s*\][ \t]*='
    r'[ \t]*ALL_LOCATIONS\[\s*"(?P<parent>' + _ID + r')"\s*\]\.copy\(\)',
    re.MULTILINE,
)

# ``ALL_LOCATIONS["id"].update({...})`` or ``.update(ALL_LOCATIONS["other"])``.
_UPDATE_RE = re.compile(
    r'ALL_LOCATIONS\[\s*"' + _LOCATION_ID + r'"\s*\]\.update\(\s*'
    r'(?:\{|ALL_LOCATIONS\[\s*"(?P<source>' + _ID + r')"\s*\])',
)

_NAME_RE = re.compile(
    r'"name"\s*:\s*(?:_\(\s*)?"(?P<display>[^"]+)"\s*\)?',
)

_DISABLED_RE = re.compile(r'"enabled"\s*:\s*False\b')

# Where TNH keeps characters who are off the map (`default Away =
# LocationClass("hold")`): named locations with nothing to stage.
_HOLDING_PLACES = frozenset({"hold", "busy"})


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


def _top_level(body: str) -> str:
    """*body* without its nested dicts, so a nested ``"name"`` is not the location's."""
    depth = 0
    kept: list[str] = []
    for char in body:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif depth == 0:
            kept.append(char)
    return "".join(kept)


def _own_name(body: str) -> str | None:
    """The ``"name"`` a dict body sets at its own level."""
    match = _NAME_RE.search(_top_level(body))
    return match.group("display") if match else None


@dataclass
class _Declaration:
    """What the scanned files say about one location id.

    ``updates`` holds, in source order, ``("name", display)`` for an update
    dict that names the location and ``("fields", id)`` for
    ``.update(ALL_LOCATIONS[id])``.
    """

    source_file: str
    source_line: int
    name: str | None = None
    parent: str | None = None
    updates: list[tuple[str, str]] = field(default_factory = list)
    disabled: bool = False


def _scan(context: ScanContext, result: ExtractionResult) -> dict[str, _Declaration]:
    """Read every declaration, copy and update of ``ALL_LOCATIONS``, in file order."""
    declarations: dict[str, _Declaration] = {}
    updates: list[tuple[str, tuple[str, str] | None, bool]] = []

    for path in iter_all_rpy(context):
        text = safe_read_text(path)
        if text is None:
            continue
        cleaned = strip_noise(text)
        relative = context.relative(path)

        found: list[tuple[int, str, _Declaration]] = []
        for match in _EXPLICIT_LOCATION_RE.finditer(cleaned):
            open_brace = match.end() - 1
            end = _find_block_end(cleaned, open_brace)
            if end is None:
                result.warnings.append(Warning(
                    message = f"Unbalanced braces for {match.group('location_id')}",
                    source_file = relative,
                ))
                continue
            line = cleaned[: match.start()].count("\n") + 1
            found.append((match.start(), match.group("location_id"), _Declaration(
                relative, line, name = _own_name(cleaned[open_brace + 1 : end]),
            )))
        for match in _COPY_LOCATION_RE.finditer(cleaned):
            line = cleaned[: match.start()].count("\n") + 1
            found.append((match.start(), match.group("location_id"), _Declaration(
                relative, line, parent = match.group("parent"),
            )))
        for _, location_id, declaration in sorted(found, key = lambda item: item[0]):
            # A re-declaration of an id keeps the first one.
            declarations.setdefault(location_id, declaration)

        for match in _UPDATE_RE.finditer(cleaned):
            location_id = match.group("location_id")
            if match.group("source"):
                updates.append((location_id, ("fields", match.group("source")), False))
                continue
            open_brace = match.end() - 1
            end = _find_block_end(cleaned, open_brace)
            if end is None:
                continue
            body = cleaned[open_brace + 1 : end]
            name = _own_name(body)
            disables = bool(_DISABLED_RE.search(_top_level(body)))
            updates.append((location_id, ("name", name) if name else None, disables))

    # Updates run after the declarations (an `init python` block after the
    # `define`s), so they apply once every file is read.
    for location_id, update, disables in updates:
        declaration = declarations.get(location_id)
        if declaration is None:
            continue
        if update is not None:
            declaration.updates.append(update)
        declaration.disabled = declaration.disabled or disables
    return declarations


def _declared_name(
    location_id: str,
    declarations: dict[str, _Declaration],
    seen: frozenset[str] = frozenset(),
) -> str | None:
    """The name a location is declared with: its own dict's, or the one it copies."""
    declaration = declarations.get(location_id)
    if declaration is None or location_id in seen:
        return None
    if declaration.name is not None:
        return declaration.name
    if declaration.parent is not None:
        return _declared_name(declaration.parent, declarations, seen | {location_id})
    return None


def _resolved_name(location_id: str, declarations: dict[str, _Declaration]) -> str | None:
    """The name a location ends with: the last update that names it, else the declared one."""
    name = _declared_name(location_id, declarations)
    for kind, value in declarations[location_id].updates:
        candidate = value if kind == "name" else _declared_name(value, declarations)
        if candidate is not None:
            name = candidate
    return name


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` with one slugline entry per location."""
    result = ExtractionResult(category = "locations")
    declarations = _scan(context, result)
    # slugline -> the location_id that claimed it. A slugline is the only
    # handle a scene has on a location, so it must map to exactly one id.
    seen_sluglines: dict[str, str] = {}

    for location_id, declaration in declarations.items():
        if declaration.disabled or location_id in _HOLDING_PLACES:
            continue
        where = f"{declaration.source_file}:{declaration.source_line}"
        if declaration.parent is not None and declaration.parent not in declarations:
            result.warnings.append(Warning(
                message = f"Location {location_id} copies {declaration.parent}, which no scanned file declares",
                source_file = where,
            ))
            continue

        display_name = _resolved_name(location_id, declarations)
        if display_name is None:
            result.warnings.append(Warning(
                message = f"Location {location_id} has no 'name' field",
                source_file = declaration.source_file,
            ))
            continue
        slugline = display_name.upper()

        # Two locations can carry the same "name" — TNH gives the player's
        # shower the bedroom's display name. Emitting both would leave the
        # winner to dict-insertion order in ``Allowlists._build_location_map``,
        # which silently sends a writer's slugline to whichever was read
        # last. The first declaration keeps the slugline; the other is reported.
        claimed_by = seen_sluglines.get(slugline)
        if claimed_by is not None:
            result.warnings.append(Warning(
                message = (
                    f"Location {location_id} declares the same name as {claimed_by}, "
                    f"so both derive the slugline {slugline!r}. {claimed_by} keeps it. "
                    f"Give {location_id} its own slugline in locations_overrides.yaml "
                    f"if a scene needs to open there."
                ),
                source_file = where,
            ))
            continue

        result.entries.append(AllowlistEntry(
            name = slugline,
            source_file = declaration.source_file,
            source_line = declaration.source_line,
            metadata = (
                ("location_id", location_id),
                ("display_name", display_name),
            ),
        ))
        seen_sluglines[slugline] = location_id

    return result
