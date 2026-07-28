"""Read the core allowlist layer and drop project values it already carries.

A project layer holds what the *mod* adds; the game's own vocabulary lives in
the compiler's bundled ``allowlists_base``. Several extractors learn a name
from *usage* rather than from a declaration site — ``history_events`` matches
every ``History.check("…")``, ``traits`` every ``check_trait("…")`` — and the
mod tree they scan contains the compiler's own output. So a base-game name
that any mod file merely *reads* gets filed in the project layer as though the
mod had introduced it.

Nothing breaks at validation: :meth:`Allowlists.merge` unions the layers and
the value sits in the core one anyway. What breaks is the *split* — the
allowlist browser places a value by its ``source_file`` root, so a game value
found under the mod's tree shows on the project side of the sidebar, undoing
"the project layer holds only what the mod adds".

Two rules govern the filter:

* **It applies only to a mod-only run** (``--no-include-tnh``). That flag is
  what says "this layer may not hold game values". A run *with* it either
  produces the core layer itself or was asked for merged output on purpose,
  and filtering either would gut the result.
* **A duplicate is a match on the name *and* every metadata field**, not on
  the name alone. ``merge`` unions the plain sets, so dropping a duplicate
  trait can never make a scene fail — but it merges the metadata-bearing
  topics as dicts where the project layer *wins*: ``locations`` maps a
  slugline to a ``location_id``, ``fx`` a name to a signature and call mode,
  ``moods`` a mood to its face list. A project entry that reuses a core name
  with different metadata is a deliberate override; dropping it would silently
  hand the writer the game's value instead. Comparing the whole entry costs
  nothing on the topics that carry no metadata, where the key degrades to the
  name.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .models import ExtractionResult, Warning

# An entry reduced to what makes it a duplicate: its subgroup (per-character
# topics partition into ``arms`` / ``left_arm`` / ``right_arm``; empty for the
# rest), its name, and its metadata fields as an order-independent set.
EntryKey = tuple[str, str, frozenset[tuple[str, str]]]

# The three fields every allowlist entry carries. Everything else in the
# mapping is metadata and takes part in the comparison; ``source_file`` and
# ``source_line`` do not — the same value found at a different line is still
# the same value.
_STANDARD_FIELDS = frozenset({"name", "source_file", "source_line"})

# The top-level key holding the entry list, for the files that do not use
# ``values``.
_LIST_KEYS: dict[str, str] = {
    "fx.yaml": "effects",
    "fx_custom.yaml": "effects",
    "condition_functions.yaml": "functions",
    "run_operations.yaml": "operations",
    "interpolation_custom.yaml": "paths",
    "locations_overrides.yaml": "overrides",
}

# Hand-maintained files that extend a generated one in the same layer. The
# compiler merges each pair when it loads, so a value declared in the
# companion is just as much "already in the core layer" as one in the
# generated file.
_COMPANION_FILES: dict[str, tuple[str, ...]] = {
    "fx": ("fx_custom.yaml",),
    "interpolation": ("interpolation_custom.yaml",),
    "locations": ("locations_overrides.yaml",),
}


def default_core_dir() -> Path | None:
    """Return the bundled ``allowlists_base`` directory, or ``None`` if absent.

    Resolved from this package's own location rather than through
    ``tnh_scene_compiler.config.get_data_root``: the refresh tool ships with
    the source checkout only — it is absent from the frozen application — so
    that helper's frozen branch can never apply here, and importing the
    compiler package for one path would couple the two for nothing.
    """
    candidate = Path(__file__).resolve().parents[1] / "allowlists_base"
    return candidate if candidate.is_dir() else None


def _read_payload(path: Path) -> dict[str, Any]:
    """Return the parsed mapping at *path*, or an empty one when unreadable.

    A core layer that is missing, truncated or invalid must not abort a
    refresh: the filter is layer hygiene, never a correctness gate. An
    unreadable file simply contributes no known names, so every project value
    survives.
    """
    if not path.is_file():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding = "utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _entry_key(item: Any, subgroup: str = "") -> EntryKey | None:
    """Reduce one YAML entry to its :data:`EntryKey`, or ``None`` if malformed.

    Accepts both entry shapes found in the layer: a mapping with a ``name``
    (every generated file) and a bare string (``interpolation_custom.yaml``
    lists plain dotted paths). Values are coerced to ``str`` so a field YAML
    happened to type as a number or a bool still compares against the
    extractor's string metadata.
    """
    if isinstance(item, str):
        return (subgroup, item, frozenset())
    if not isinstance(item, dict):
        return None
    name = item.get("name")
    if not isinstance(name, str):
        return None
    metadata = frozenset(
        (key, str(value))
        for key, value in item.items()
        if key not in _STANDARD_FIELDS
    )
    return (subgroup, name, metadata)


def _read_flat(path: Path) -> set[EntryKey]:
    """Return the entry keys of a single flat allowlist file."""
    payload = _read_payload(path)
    items = payload.get(_LIST_KEYS.get(path.name, "values"))
    if not isinstance(items, list):
        return set()
    keys = (_entry_key(item) for item in items)
    return {key for key in keys if key is not None}


def _read_character_file(path: Path) -> set[EntryKey]:
    """Return the entry keys of one per-character file, subgroups included.

    Every list-valued top-level key is an entry list: ``values`` for the
    unpartitioned topics, and one key per subgroup for ``arms``. The
    non-list keys (``character``, ``source``, ``generated_at``,
    ``inherits_from_shared``) are skipped by that same test.
    """
    payload = _read_payload(path)
    keys: set[EntryKey] = set()
    for group_name, items in payload.items():
        if not isinstance(items, list):
            continue
        subgroup = "" if group_name == "values" else group_name
        for item in items:
            key = _entry_key(item, subgroup)
            if key is not None:
                keys.add(key)
    return keys


@dataclass(slots = True)
class CoreLayer:
    """The names a core allowlist layer already carries, ready to compare.

    Attributes:
        flat: ``category -> entry keys``, for the topics stored as a single
            file (``traits``, ``history_events``, ``locations``, …).
        per_character: ``category -> character -> entry keys``, for the topics
            stored as a directory of per-character files (``faces``, ``arms``,
            ``moods``, …).
        shared: ``category -> entry keys`` read from a per-character topic's
            ``_shared.yaml``. Kept apart from :attr:`per_character` because
            the two are not interchangeable: a shared value is valid for every
            character, so it masks a per-character project entry, while a
            per-character core value must not mask a project entry declared as
            shared.
    """

    flat: dict[str, set[EntryKey]] = field(default_factory = dict)
    per_character: dict[str, dict[str, set[EntryKey]]] = field(default_factory = dict)
    shared: dict[str, set[EntryKey]] = field(default_factory = dict)

    def is_empty(self) -> bool:
        """Whether the layer contributed no names at all."""
        return not (self.flat or self.per_character or self.shared)


def load_core_layer(core_dir: Path, categories: Iterable[str]) -> CoreLayer:
    """Read the core layer's entry keys for each of *categories*.

    A category is per-character when the layer stores it as a directory and
    flat when it stores it as ``<category>.yaml`` — reading the shape off
    disk rather than off a hardcoded list keeps this in step with the
    extractors on its own. A category the layer does not carry at all
    contributes nothing and leaves the project's values untouched.
    """
    layer = CoreLayer()
    for category in categories:
        category_dir = core_dir / category
        if category_dir.is_dir():
            per_char: dict[str, set[EntryKey]] = {}
            shared: set[EntryKey] = set()
            for path in sorted(category_dir.glob("*.yaml")):
                keys = _read_character_file(path)
                if path.stem == "_shared":
                    shared |= keys
                elif keys:
                    per_char[path.stem] = keys
            if per_char:
                layer.per_character[category] = per_char
            if shared:
                layer.shared[category] = shared
            continue

        keys = _read_flat(core_dir / f"{category}.yaml")
        for companion in _COMPANION_FILES.get(category, ()):
            keys |= _read_flat(core_dir / companion)
        if keys:
            layer.flat[category] = keys
    return layer


def _key_of(entry: Any) -> EntryKey:
    """Reduce an :class:`AllowlistEntry` to the same key shape as the layer."""
    return (entry.subgroup or "", entry.name, frozenset(entry.metadata))


def _label(key: EntryKey) -> str:
    """Render a dropped entry for a warning message, subgroup included."""
    subgroup, name, _ = key
    return f"{subgroup}:{name}" if subgroup else name


def _drop_known(entries: list[Any], known: set[EntryKey]) -> list[EntryKey]:
    """Remove from *entries*, in place, every entry whose key is in *known*.

    Returns the keys removed, in the order they were declared.
    """
    if not known:
        return []
    dropped: list[EntryKey] = []
    kept: list[Any] = []
    for entry in entries:
        key = _key_of(entry)
        if key in known:
            dropped.append(key)
        else:
            kept.append(entry)
    entries[:] = kept
    return dropped


def filter_core_duplicates(
    results: Iterable[ExtractionResult],
    layer: CoreLayer,
) -> list[Warning]:
    """Drop every extracted value the core *layer* already carries.

    Mutates each :class:`ExtractionResult` in place and appends one
    :class:`Warning` per affected category to that result, so the run summary
    picks them up through the existing ``warnings`` channel. The same warnings
    are returned, in category order, for the caller to print.
    """
    warnings: list[Warning] = []
    for result in results:
        core_per_char = layer.per_character.get(result.category, {})
        core_shared = layer.shared.get(result.category, set())
        details: list[str] = []
        dropped_count = 0

        if core_per_char or core_shared or result.per_character:
            # Per-character topic. A shared core value is valid for every
            # character, so it masks a project entry filed under any of them;
            # the reverse does not hold, which is why a project entry in the
            # shared pot is only ever compared against the core's shared pot.
            shared_dropped = _drop_known(result.entries, core_shared)
            if shared_dropped:
                dropped_count += len(shared_dropped)
                details.append(
                    "_shared: " + ", ".join(_label(key) for key in shared_dropped),
                )
            for character in sorted(result.per_character):
                known = core_per_char.get(character, set()) | core_shared
                dropped = _drop_known(result.per_character[character], known)
                if not dropped:
                    continue
                dropped_count += len(dropped)
                details.append(
                    f"{character}: " + ", ".join(_label(key) for key in dropped),
                )
            # A character left with nothing to add gets no file at all,
            # rather than one declaring an empty list.
            for character in [c for c, e in result.per_character.items() if not e]:
                del result.per_character[character]
        else:
            dropped = _drop_known(result.entries, layer.flat.get(result.category, set()))
            if dropped:
                dropped_count += len(dropped)
                details.append(", ".join(_label(key) for key in dropped))

        if not dropped_count:
            continue
        warning = Warning(
            message = (
                f"{result.category}: {dropped_count} value(s) already in the core "
                f"allowlists, not written to the project layer "
                f"({'; '.join(details)})"
            ),
        )
        result.warnings.append(warning)
        warnings.append(warning)
    return warnings
