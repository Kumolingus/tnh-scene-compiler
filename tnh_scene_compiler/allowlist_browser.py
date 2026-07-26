"""In-app allowlist browser: read every allowlist, edit the hand-maintained ones.

The allowlists are the tool's contract with the game — the set of characters,
moods, faces, locations, traits, effects and functions a ``.scene`` may name.
They ship in two layers, and the browser keeps them apart so a writer can see
*where* a value comes from:

* **base** — ``allowlists_base/``, bundled with the tool (the game's own values);
* **project** — ``<project>/_allowlists/``, generated from the mod + game sources.

Editing is deliberately narrow. Most files are rewritten wholesale by
``python -m tnh_refresh_allowlists`` on every refresh, so a hand edit there is
silently lost; those are read-only here. Only the five files the refresh
preserves are editable, and only in the project layer — the base layer lives
inside the PyInstaller bundle at runtime, where writes go to a temp directory
that disappears.

Editing is raw YAML on purpose: these files carry hand-written header comments
documenting their own schema, and a ``yaml.safe_load`` / ``safe_dump``
round-trip would delete every one of them.

The model and the readers (:func:`load_topic`, :func:`validate_topic_yaml`) are
pure and importable without Tkinter; :class:`AllowlistBrowserDialog` is the thin
UI on top.
"""

from __future__ import annotations

import importlib.util
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

import yaml

# Browsing reads the whole allowlist tree at once — around a hundred files. The
# libyaml-backed loader parses them ~7x faster than the pure-Python one and is
# the same safe subset; it is absent from some installs (and possibly from a
# frozen build, if the C extension is not bundled), so fall back silently.
try:
    from yaml import CSafeLoader as _LOADER
except ImportError:  # pragma: no cover - depends on the PyYAML build
    _LOADER = yaml.SafeLoader

# Pseudo-character used by per-character topics that also carry a shared file
# (``moods/_shared.yaml`` holds the moods valid for everyone).
SHARED_LABEL = "(shared)"

# How a file is kept up to date. This drives what the UI lets you do with it.
#   generated — rewritten by every ``tnh_refresh_allowlists`` run; editing it
#               here would be undone by the next refresh, so: read-only.
#   manual    — created once as a scaffold, then never touched by the refresh
#               (``__main__._MANUAL_SCAFFOLDS``, plus the empty-result skip for
#               ``condition_functions``); editable in the project layer.
#   developer — no extractor and no scaffold: hand-maintained by the tool's
#               author in the base layer. Read-only from the app.
MAINTENANCE_GENERATED = "generated"
MAINTENANCE_MANUAL = "manual"
MAINTENANCE_DEVELOPER = "developer"

_MAINTENANCE_BLURBS = {
    MAINTENANCE_GENERATED: (
        "Generated from the game and the mod by the allowlist refresh. Read-only "
        "here — the next refresh rewrites this file, so an edit would be lost. "
        "Ask the developer if a value you need is missing."
    ),
    MAINTENANCE_MANUAL: (
        "Hand-maintained. The allowlist refresh creates this file once and never "
        "rewrites it, so what you add here survives. Edits apply to the project "
        "layer only."
    ),
    MAINTENANCE_DEVELOPER: (
        "Hand-maintained by the tool's developer, in the base layer that ships "
        "inside the app. Read-only here."
    ),
}


# The two sidebar groups, split by where each *value* comes from. A generated
# file mixes both — the refresh scans the game and the mod into one
# ``traits.yaml`` — so the split happens per entry, not per file, and a list is
# shown twice: its game values under Core game, its project values under
# Project. No displayed list ever mixes the two.
SECTION_CORE = "Core game"
SECTION_PROJECT = "Project"

ORIGIN_CORE = "core"
ORIGIN_PROJECT = "project"

# ``source_file`` roots that mean "this came with the game" even though they are
# not a path under the base-game root: engine builtins (interpolation paths,
# looks, Player/Narrator) and the base layer's own ``game/...`` convention.
_CORE_SENTINEL_ROOTS = frozenset({"<builtin>", "game"})

# Sidebar tints: section headings, and lists this project adds nothing to.
_HEADING_FG = "#7A7A7A"
_EMPTY_FG = "#5A5A5A"

# Column (in monospace characters) where a value's layer badge starts.
_BADGE_COLUMN = 32


@dataclass(frozen=True, slots=True)
class AllowlistTopic:
    """One browsable allowlist — a YAML file, or a directory of per-character ones.

    Attributes:
        key: Stable identifier used for lookups and deep links.
        title: Display name in the sidebar.
        filename: File name, or directory name when ``per_character``.
        item_key: Top-level YAML key holding the list of entries.
        per_character: Whether the topic is a directory with one file per
            character.
        has_shared: Whether a per-character topic also has a ``_shared.yaml``.
        maintenance: One of the ``MAINTENANCE_*`` constants.
        summary: Plain-language description aimed at a non-developer writer.
    """

    key: str
    title: str
    filename: str
    item_key: str
    per_character: bool
    has_shared: bool
    maintenance: str
    summary: str

    @property
    def survives_refresh(self) -> bool:
        """Whether ``tnh_refresh_allowlists`` leaves this file alone.

        Informational, not a permission: a project that never runs the refresh —
        no extracted base game, or allowlists written by hand — is free to edit
        anything, and the tool must not assume our workflow is everyone's.
        """
        return self.maintenance != MAINTENANCE_GENERATED

    def is_editable_in(self, origin: str) -> bool:
        """Whether this list is editable on *origin*'s side of the split.

        Only ever the project side: the game's values are the game's, and the
        base layer ships inside the app bundle, where a write lands in a temp
        directory and is lost.
        """
        return origin == ORIGIN_PROJECT

    def blurb(self, origin: str, *, refresh_available: bool = True) -> str:
        """Return what the reader may do with this list, on one side of the split.

        Args:
            origin: which side of the split is being shown.
            refresh_available: whether the allowlist refresh can be run from
                this install. When it cannot — the packaged app ships the GUI
                alone — there is nothing that could overwrite an edit, so the
                warning is dropped rather than shown to someone who has no way
                to act on it.
        """
        if origin == ORIGIN_CORE:
            return (
                "These values come with The Null Hypothesis. Read-only — they are "
                "read from the game's own files, so a value you need that is "
                "missing has to exist in the game first."
            )
        if self.survives_refresh or not refresh_available:
            return "Yours to edit. What you put here stays."
        return (
            "Yours to edit — but this is one of the files the allowlist refresh "
            "rewrites from your project's source. Since this install can run the "
            "refresh, add the value at the source instead; an edit made here "
            "would be lost the next time it runs."
        )


@dataclass(frozen=True, slots=True)
class AllowlistValue:
    """A single allowed value and where it came from."""

    name: str
    origin: str  # ORIGIN_CORE | ORIGIN_PROJECT
    source: str = ""  # the source_file it was scanned from, if any
    details: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class LayerMeta:
    """The roots a layer's ``_meta.yaml`` declares, used to classify entries."""

    base_game_root: str = ""
    project_root: str = ""


@dataclass(frozen=True, slots=True)
class AllowlistGroup:
    """A named list of values inside a topic (an arms subgroup, or the whole file)."""

    title: str
    values: tuple[AllowlistValue, ...]


ALLOWLIST_TOPICS: tuple[AllowlistTopic, ...] = (
    # -- Core game: derived from the game + mod sources, read-only --------
    AllowlistTopic(
        key="characters", title="Characters",
        filename="characters.yaml", item_key="values",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary=(
            "Every character a scene may name — as a SPEAKER line, in a [[show]] "
            "directive, or as the root of an interpolation like [JeanGrey.name]. "
            "Spelling is exact, PascalCase."
        ),
    ),
    AllowlistTopic(
        key="moods", title="Moods",
        filename="moods", item_key="values",
        per_character=True, has_shared=True, maintenance=MAINTENANCE_GENERATED,
        summary=(
            "The mood values a character accepts in a parenthetical — "
            "JEANGREY (happy). Shared moods work for everyone; the rest are "
            "per-character."
        ),
    ),
    AllowlistTopic(
        key="faces", title="Faces",
        filename="faces", item_key="values",
        per_character=True, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary="Face values for the face= slot, one set per character.",
    ),
    AllowlistTopic(
        key="arms", title="Arm poses",
        filename="arms", item_key="arms",
        per_character=True, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary=(
            "Arm poses, in three slots: arms= takes a preset pose, while "
            "left_arm= and right_arm= are named-only and set one side at a time."
        ),
    ),
    AllowlistTopic(
        key="outfits", title="Outfits",
        filename="outfits", item_key="values",
        per_character=True, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary="Outfit values for the outfit= slot, one set per character.",
    ),
    AllowlistTopic(
        key="features", title="Features",
        filename="features", item_key="values",
        per_character=True, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary=(
            "Feature names for the Character.feature_enabled(\"...\") condition, "
            "one set per character — they share no common value."
        ),
    ),
    AllowlistTopic(
        key="clothing_items", title="Clothing items",
        filename="clothing_items", item_key="values",
        per_character=True, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary=(
            "Clothing inventory keys for Character.Inventory.get_active(\"...\"), "
            "one set per character. Prefixed with the owner's tag — that is the "
            "string the inventory files a garment under."
        ),
    ),
    AllowlistTopic(
        key="looks", title="Looks",
        filename="looks.yaml", item_key="values",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary="Where a character is looking — the look= slot. Same list for everyone.",
    ),
    AllowlistTopic(
        key="stages", title="Stage positions",
        filename="stages.yaml", item_key="values",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary="Where a character stands on screen — the stage= slot.",
    ),
    AllowlistTopic(
        key="locations", title="Locations",
        filename="locations.yaml", item_key="values",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary=(
            "Every place a slugline may name (INT. KITCHEN). The name is what you "
            "write; location_id is what the game calls it."
        ),
    ),
    AllowlistTopic(
        key="traits", title="Traits",
        filename="traits.yaml", item_key="values",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary=(
            "Trait names for [[give_trait]] / [[remove_trait]] and the "
            "Character.has(\"...\") condition."
        ),
    ),
    AllowlistTopic(
        key="inventory_items", title="Inventory items",
        filename="inventory_items.yaml", item_key="values",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary=(
            "Item keys for the Character.Inventory.get_active(\"...\") / "
            "get_number(\"...\") conditions. Plain items only — clothing is "
            "keyed separately and is not extracted."
        ),
    ),
    AllowlistTopic(
        key="personalities", title="Personalities",
        filename="personalities.yaml", item_key="values",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary=(
            "Personality leanings for [[set_personality]] and the "
            "Character.personality(\"...\") condition."
        ),
    ),
    AllowlistTopic(
        key="history_events", title="History events",
        filename="history_events.yaml", item_key="values",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary=(
            "Event names for [[record]] and the Character.did(\"...\") condition — "
            "the permanent record a later scene can react to."
        ),
    ),
    AllowlistTopic(
        key="sfx", title="Sound effects",
        filename="sfx.yaml", item_key="values",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary="Sound files playable with [[sfx name]].",
    ),
    AllowlistTopic(
        key="fx", title="Effects (game)",
        filename="fx.yaml", item_key="effects",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary="Visual effects from the base game, callable with [[fx name()]].",
    ),
    AllowlistTopic(
        key="interpolation", title="Interpolation paths",
        filename="interpolation.yaml", item_key="values",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_GENERATED,
        summary=(
            "The live values you can drop into a line with [square brackets], "
            "like [Player.name]. Case-sensitive."
        ),
    ),
    AllowlistTopic(
        key="character_methods", title="Character methods",
       
        filename="character_methods.yaml", item_key="methods",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_DEVELOPER,
        summary=(
            "Methods callable on a character in a condition, like "
            "JeanGrey.friends_with(Rogue)."
        ),
    ),
    AllowlistTopic(
        key="character_properties", title="Character properties",
       
        filename="character_properties.yaml", item_key="properties",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_DEVELOPER,
        summary=(
            "Read-only stats usable bare in a condition, like JeanGrey.desire. "
            "A number, so compare it with an operator."
        ),
    ),
    # -- Project: hand-maintained, editable in the project layer ----------
    AllowlistTopic(
        key="locations_overrides", title="Location overrides",
        filename="locations_overrides.yaml", item_key="overrides",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_MANUAL,
        summary=(
            "Manual slugline -> location_id fixes. An entry here beats the "
            "generated Locations list; remove it to fall back to automatic."
        ),
    ),
    AllowlistTopic(
        key="fx_custom", title="Effects (project)",
        filename="fx_custom.yaml", item_key="effects",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_MANUAL,
        summary=(
            "Visual effects the project adds on top of the game's. Same [[fx]] "
            "syntax; listed separately so a refresh never drops them."
        ),
    ),
    AllowlistTopic(
        key="interpolation_custom", title="Interpolation (project)",
       
        filename="interpolation_custom.yaml", item_key="paths",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_MANUAL,
        summary=(
            "Extra interpolation paths the project defines. One dotted path per "
            "entry — no expressions, no calls."
        ),
    ),
    AllowlistTopic(
        key="condition_functions", title="Condition functions",
       
        filename="condition_functions.yaml", item_key="functions",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_MANUAL,
        summary=(
            "Helpers a writer may call inside [[if]]. Adding one is a promise to "
            "keep its signature stable, so this list is curated by hand."
        ),
    ),
    AllowlistTopic(
        key="run_operations", title="Run operations",
       
        filename="run_operations.yaml", item_key="operations",
        per_character=False, has_shared=False, maintenance=MAINTENANCE_MANUAL,
        summary=(
            "Operations callable with [[run]] — the catch-all for a persistent "
            "change with no dedicated directive."
        ),
    ),
)

_TOPICS_BY_KEY = {topic.key: topic for topic in ALLOWLIST_TOPICS}

# Detail fields worth showing next to a value, in display order. Anything not
# listed is appended afterwards so a new YAML field never silently vanishes.
_DETAIL_ORDER = (
    "signature", "type", "location_id", "display_name", "faces", "label",
    "category", "call_mode", "notes",
)
_DETAIL_HIDDEN = frozenset({"name", "source_file", "source_line", "param_choices"})


def topic_by_key(key: str) -> AllowlistTopic | None:
    """Return the topic registered under *key*, or ``None``."""
    return _TOPICS_BY_KEY.get(key)


def refresh_tool_available() -> bool:
    """Whether ``tnh_refresh_allowlists`` can be run from this install.

    It ships with the source checkout but not with the packaged application —
    the frozen build is the GUI alone. Someone using the app therefore has no
    way to regenerate an allowlist, so warning them that a refresh would
    overwrite their edit describes a tool they do not have.
    """
    try:
        return importlib.util.find_spec("tnh_refresh_allowlists") is not None
    except (ImportError, ValueError):  # pragma: no cover - defensive
        return False


def default_base_dir() -> Path | None:
    """Return the bundled base allowlists directory, or ``None`` if absent.

    Used by the callers that have no :class:`~tnh_scene_compiler.config.Config`
    to ask — quick mode compiles against the base game alone, and would
    otherwise open the browser on nothing at all.
    """
    from .config import get_data_root

    candidate = get_data_root() / "allowlists_base"
    return candidate if candidate.is_dir() else None


def topic_path(topic: AllowlistTopic, directory: Path, character: str = "") -> Path:
    """Return the YAML path for *topic* inside an allowlists *directory*.

    Args:
        topic: The topic to locate.
        directory: An allowlists layer root.
        character: For a per-character topic, the character to read, or
            :data:`SHARED_LABEL` for its shared file. Ignored otherwise.
    """
    if not topic.per_character:
        return directory / topic.filename
    stem = "_shared" if character == SHARED_LABEL else character
    return directory / topic.filename / f"{stem}.yaml"


def _read_yaml(path: Path) -> dict[str, Any] | None:
    """Return the top-level mapping of *path*, or ``None`` if missing/unreadable."""
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.load(handle, Loader=_LOADER)  # noqa: S506 - safe loader
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


def _entry_details(item: Any) -> tuple[tuple[str, str], ...]:
    """Return the ``(field, value)`` pairs worth displaying for one entry."""
    if not isinstance(item, dict):
        return ()
    details: list[tuple[str, str]] = []
    for key in _DETAIL_ORDER:
        text = _one_line(item.get(key))
        if text:
            details.append((key, text))
    for key, value in item.items():
        if key in _DETAIL_HIDDEN or key in _DETAIL_ORDER:
            continue
        text = _one_line(value)
        if text:
            details.append((str(key), text))
    return tuple(details)


def _one_line(value: Any) -> str:
    """Render a scalar YAML field as one line, or ``""`` if it is not a scalar.

    A folded ``notes:`` block arrives with embedded newlines; collapsing them
    keeps one detail on one row so the value list stays column-aligned.
    """
    if not isinstance(value, (str, int, float, bool)):
        return ""
    return " ".join(str(value).split())


# Two tiny files read once per allowlist file otherwise — over half of all the
# YAML parsing a full read used to do. Cleared by the window's Reload.
_META_CACHE: dict[Path, LayerMeta] = {}


def clear_meta_cache() -> None:
    """Forget the memoised ``_meta.yaml`` payloads."""
    _META_CACHE.clear()


def read_layer_meta(directory: Path | None) -> LayerMeta:
    """Read a layer's ``_meta.yaml`` for the roots that classify its entries."""
    if directory is None:
        return LayerMeta()
    cached = _META_CACHE.get(directory)
    if cached is not None:
        return cached
    payload = _read_yaml(directory / "_meta.yaml") or {}
    meta = LayerMeta(
        base_game_root=str(payload.get("base_game_root") or ""),
        project_root=str(payload.get("project_root") or ""),
    )
    _META_CACHE[directory] = meta
    return meta


def classify_origin(source_file: str, *, layer: str, meta: LayerMeta) -> str:
    """Decide whether one entry came from the game or from the project.

    The base layer ships with the tool and *is* the game, so everything in it is
    core. In the project layer the refresh records where it scanned each value
    from, and that ``source_file`` is what tells a game value apart from a mod
    one inside the same generated file.

    Anything the rule cannot place falls to the project side: an entry with no
    ``source_file`` was written by hand into a project file, which is exactly
    what the project side is for.
    """
    if layer == "base":
        return ORIGIN_CORE
    root = source_file.split("/", 1)[0].split("\\", 1)[0]
    if not root:
        return ORIGIN_PROJECT
    if meta.project_root and root == meta.project_root:
        return ORIGIN_PROJECT
    if root in _CORE_SENTINEL_ROOTS:
        return ORIGIN_CORE
    if meta.base_game_root and root == meta.base_game_root:
        return ORIGIN_CORE
    return ORIGIN_PROJECT


def _read_entries(
    payload: dict[str, Any] | None, item_key: str, *, layer: str, meta: LayerMeta,
) -> list[AllowlistValue]:
    """Turn one YAML payload's entry list into origin-tagged values.

    Tolerates both entry shapes in use: a mapping carrying ``name`` (most
    files) and a bare string (``interpolation_custom.yaml`` paths).
    """
    if not payload:
        return []
    entries = payload.get(item_key)
    if not isinstance(entries, list):
        return []
    values: list[AllowlistValue] = []
    for item in entries:
        if isinstance(item, str) and item.strip():
            values.append(
                AllowlistValue(
                    item.strip(), classify_origin("", layer=layer, meta=meta),
                ),
            )
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            source = _one_line(item.get("source_file"))
            values.append(
                AllowlistValue(
                    item["name"],
                    classify_origin(source, layer=layer, meta=meta),
                    source,
                    _entry_details(item),
                ),
            )
    return values


def _subgroup_keys(topic: AllowlistTopic) -> tuple[str, ...]:
    """Return the YAML keys a topic reads, in display order."""
    if topic.key == "arms":
        return ("arms", "left_arm", "right_arm")
    return (topic.item_key,)


def read_layer(
    topic: AllowlistTopic, directory: Path | None, character: str = "",
    *, layer: str = "project",
) -> dict[str, list[AllowlistValue]]:
    """Read one layer of *topic*, as ``{subgroup_key: values}``.

    Returns an empty mapping when the layer is absent — a project that has not
    been refreshed yet, or a tool run with the base layer disabled.
    """
    if directory is None or not directory.is_dir():
        return {}
    meta = read_layer_meta(directory)
    payload = _read_yaml(topic_path(topic, directory, character))
    return {
        key: _read_entries(payload, key, layer=layer, meta=meta)
        for key in _subgroup_keys(topic)
    }


def load_topic(
    topic: AllowlistTopic,
    base_dir: Path | None,
    project_dir: Path | None,
    character: str = "",
    *,
    origin: str = "",
) -> list[AllowlistGroup]:
    """Read both layers of *topic*, keeping only values from *origin*.

    Passing no *origin* returns everything, which is what the search index
    wants. The window always asks for one side, so no list it displays ever
    mixes game values with project ones.
    """
    base = read_layer(topic, base_dir, character, layer="base")
    project = read_layer(topic, project_dir, character, layer="project")

    groups: list[AllowlistGroup] = []
    for key in _subgroup_keys(topic):
        merged: dict[str, AllowlistValue] = {}
        for values in (base.get(key, []), project.get(key, [])):
            for value in values:
                if origin and value.origin != origin:
                    continue
                previous = merged.get(value.name)
                if previous is not None and previous.origin != value.origin:
                    # Same name on both sides (a project redefining a game
                    # value): keep it visible under each, never merged.
                    continue
                # The project layer is read second and wins on details, matching
                # the compiler's own merge.
                merged[value.name] = AllowlistValue(
                    value.name, value.origin, value.source or (
                        previous.source if previous else ""
                    ),
                    value.details or (previous.details if previous else ()),
                )
        title = key if len(_subgroup_keys(topic)) > 1 else ""
        groups.append(
            AllowlistGroup(title, tuple(sorted(merged.values(), key=lambda v: v.name.lower()))),
        )
    return groups


def topic_characters(
    topic: AllowlistTopic, base_dir: Path | None, project_dir: Path | None,
) -> list[str]:
    """Return the characters a per-character *topic* has files for, both layers."""
    if not topic.per_character:
        return []
    names: set[str] = set()
    for directory in (base_dir, project_dir):
        if directory is None:
            continue
        topic_dir = directory / topic.filename
        if not topic_dir.is_dir():
            continue
        names.update(
            path.stem for path in topic_dir.glob("*.yaml") if not path.stem.startswith("_")
        )
    ordered = sorted(names)
    if topic.has_shared:
        ordered.insert(0, SHARED_LABEL)
    return ordered


def validate_topic_yaml(topic: AllowlistTopic, text: str) -> str | None:
    """Check edited YAML against *topic*'s schema; return an error, or ``None``.

    Deliberately shallow: it catches the mistakes that would make the compiler
    silently ignore the file (broken YAML, wrong top-level key, an entry with no
    name) without second-guessing the fields a project may legitimately add.
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return f"The file is not valid YAML:\n\n{exc}"
    if data is None:
        return f"The file is empty. It needs at least '{topic.item_key}: []'."
    if not isinstance(data, dict):
        return "The file must start with 'key: value' lines, not a bare list."
    if topic.item_key not in data:
        return (
            f"The top-level key '{topic.item_key}:' is missing. "
            f"The compiler reads the entries from it, so the file would be ignored."
        )
    entries = data[topic.item_key]
    if entries is None:
        return None
    if not isinstance(entries, list):
        return f"'{topic.item_key}:' must be a list of entries."
    for index, item in enumerate(entries, start=1):
        if isinstance(item, str):
            continue
        if not isinstance(item, dict):
            return f"Entry {index} under '{topic.item_key}:' must be a 'name: ...' mapping."
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            return f"Entry {index} under '{topic.item_key}:' has no 'name:'."
    return None


# -- Window ------------------------------------------------------------------


class AllowlistBrowserDialog(tk.Toplevel):
    """Non-modal allowlist browser: read every layer, edit the manual files."""

    def __init__(
        self,
        master: tk.Widget,
        *,
        base_dir: Path | None,
        project_dir: Path | None,
        search: str = "",
    ) -> None:
        super().__init__(master)
        self.title("Allowlists — what the game accepts")
        self.geometry("900x660")
        self.minsize(600, 420)

        self._base_dir = base_dir
        self._project_dir = project_dir
        # The selection is a list *and a side of the split*: the same allowlist
        # appears under Core game and under Project, showing different values.
        self._current: tuple[AllowlistTopic, str] | None = None
        self._character = ""
        self._editing = False
        self._edit_text: tk.Text | None = None
        # Lists already warned about this session (see _save_edit).
        self._warned_keys: set[str] = set()
        # Reading every layer costs ~0.5 s over a real project, so both the
        # rendered groups and the name index are cached. "Reload" drops them,
        # which is how an allowlist refresh run beside the window gets picked up.
        self._groups_cache: dict[tuple[str, str, str], list[AllowlistGroup]] = {}
        # (topic key, origin) -> lowercase value names. Drives both the sidebar
        # (a list only appears on a side that has values) and the search.
        self._name_index: dict[tuple[str, str], set[str]] | None = None
        # Parallel to the listbox rows: the (topic, origin) at each visible
        # index, or None for a section heading, which is not selectable.
        self._visible: list[tuple[AllowlistTopic, str] | None] = []

        body = ttk.Frame(self, padding=8)
        body.pack(fill=tk.BOTH, expand=True)

        paned = ttk.PanedWindow(body, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        self._build_sidebar(paned)
        self._build_content_pane(paned)

        if search:
            self._search_var.set(search)
        else:
            self._refresh_list()
        first = next((entry for entry in self._visible if entry is not None), None)
        if first is not None:
            self._select_topic(*first)

        self.bind("<Escape>", lambda _e: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._center_on(master)

    # -- Layout ------------------------------------------------------------

    def _build_sidebar(self, paned: ttk.PanedWindow) -> None:
        side = ttk.Frame(paned, padding=(0, 0, 6, 0))
        paned.add(side, weight=0)

        self._search_var = tk.StringVar()
        ttk.Entry(side, textvariable=self._search_var).pack(fill=tk.X, pady=(0, 4))
        self._search_var.trace_add("write", lambda *_: self._refresh_list())

        list_frame = ttk.Frame(side)
        list_frame.pack(fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self._listbox = tk.Listbox(
            list_frame, width=28, activestyle="none",
            bg="#1E1E1E", fg="#D4D4D4",
            selectbackground="#264F78", selectforeground="#FFFFFF",
            highlightthickness=0, borderwidth=0, exportselection=False,
            yscrollcommand=scroll.set,
        )
        scroll.configure(command=self._listbox.yview)
        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

    def _build_content_pane(self, paned: ttk.PanedWindow) -> None:
        container = ttk.Frame(paned)
        paned.add(container, weight=1)

        # The header (title, summary, buttons) is fixed; only the value list
        # below it scrolls, and it scrolls inside its own Text viewport. A Text
        # sized to its full content inside a scrolling canvas made Tk lay out
        # every row of a 300-value topic up front — a third of a second per
        # render — for no benefit.
        self._header = ttk.Frame(container)
        self._header.pack(fill=tk.X)

        self._content = ttk.Frame(container)
        self._content.pack(fill=tk.BOTH, expand=True)

    # -- Topic list --------------------------------------------------------

    def _refresh_list(self) -> None:
        query = self._search_var.get().lower().strip()
        self._listbox.delete(0, tk.END)
        self._visible = []
        for origin, heading in (
            (ORIGIN_CORE, SECTION_CORE), (ORIGIN_PROJECT, SECTION_PROJECT),
        ):
            rows = [
                topic for topic in ALLOWLIST_TOPICS
                if self._shows_on(topic, origin)
                and (not query or self._topic_matches(topic, origin, query))
            ]
            if not rows:
                continue
            self._visible.append(None)
            self._listbox.insert(tk.END, heading)
            self._listbox.itemconfigure(tk.END, foreground=_HEADING_FG)
            for topic in rows:
                self._visible.append((topic, origin))
                self._listbox.insert(tk.END, f"    {topic.title}")
                # Dim the lists this project adds nothing to, so "what does this
                # project actually extend?" still reads at a glance now that
                # every list is listed under Project.
                if not self._ensure_name_index()[(topic.key, origin)]:
                    self._listbox.itemconfigure(tk.END, foreground=_EMPTY_FG)

    def _shows_on(self, topic: AllowlistTopic, origin: str) -> bool:
        """Whether a list belongs on *origin*'s side of the sidebar.

        Every list is listed under Project, even with nothing in it — that is
        where you go to add the first entry, and hiding it would hide the only
        route a project has to extend that list. Core only shows what it has.
        """
        if origin == ORIGIN_PROJECT:
            return True
        return bool(self._ensure_name_index()[(topic.key, origin)])

    def _topic_matches(self, topic: AllowlistTopic, origin: str, query: str) -> bool:
        # The list's own words are free; fall back to its values so typing a
        # value name like "shy" finds the list that holds it.
        if query in f"{topic.title} {topic.summary}".lower():
            return True
        return any(query in name for name in self._ensure_name_index()[(topic.key, origin)])

    def _ensure_name_index(self) -> dict[str, set[str]]:
        """Build (once) the lowercase value names of every topic, all characters."""
        if self._name_index is None:
            # Reading every layer takes about half a second on a real project;
            # it happens on the first search only, but say so meanwhile.
            self.configure(cursor="watch")
            self.update_idletasks()
            try:
                self._name_index = self._build_name_index()
            finally:
                self.configure(cursor="")
        return self._name_index

    def _build_name_index(self) -> dict[tuple[str, str], set[str]]:
        """Read every list, every character, bucketed by origin."""
        index: dict[tuple[str, str], set[str]] = {
            (topic.key, origin): set()
            for topic in ALLOWLIST_TOPICS
            for origin in (ORIGIN_CORE, ORIGIN_PROJECT)
        }
        for topic in ALLOWLIST_TOPICS:
            characters = topic_characters(
                topic, self._base_dir, self._project_dir,
            ) or [""]
            for character in characters:
                for origin in (ORIGIN_CORE, ORIGIN_PROJECT):
                    index[(topic.key, origin)].update(
                        value.name.lower()
                        for group in self._groups(topic, character, origin)
                        for value in group.values
                    )
        return index

    def _groups(
        self, topic: AllowlistTopic, character: str, origin: str,
    ) -> list[AllowlistGroup]:
        """Return one side of a list's values, reading from disk at most once."""
        key = (topic.key, character, origin)
        if key not in self._groups_cache:
            # Read the layers once and split, rather than once per side: asking
            # load_topic for each origin separately doubled the YAML parsing.
            every = load_topic(topic, self._base_dir, self._project_dir, character)
            for side in (ORIGIN_CORE, ORIGIN_PROJECT):
                self._groups_cache[(topic.key, character, side)] = [
                    AllowlistGroup(
                        group.title,
                        tuple(v for v in group.values if v.origin == side),
                    )
                    for group in every
                ]
        return self._groups_cache[key]

    def _reload(self) -> None:
        """Drop the caches and re-read from disk (e.g. after an allowlist refresh)."""
        self._groups_cache.clear()
        clear_meta_cache()
        self._name_index = None
        self._refresh_list()
        self._render()

    def _on_select(self, _event: object = None) -> None:
        selection = self._listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if 0 <= index < len(self._visible):
            entry = self._visible[index]
            if entry is not None:
                self._select_topic(*entry)

    def _select_topic(self, topic: AllowlistTopic, origin: str = ORIGIN_CORE) -> None:
        characters = topic_characters(topic, self._base_dir, self._project_dir)
        self._current = (topic, origin)
        self._character = characters[0] if characters else ""
        self._editing = False
        self._render()

    # -- Rendering ---------------------------------------------------------

    def _render(self) -> None:
        for widget in (*self._header.winfo_children(), *self._content.winfo_children()):
            widget.destroy()
        if self._current is None:
            return
        topic, origin = self._current

        self._render_header(topic, origin)
        if self._editing:
            self._render_editor(topic)
        else:
            self._render_values(topic, origin)

    def _render_header(self, topic: AllowlistTopic, origin: str) -> None:
        bar = ttk.Frame(self._header)
        bar.pack(fill=tk.X, padx=8, pady=(6, 2))
        ttk.Label(bar, text=topic.title, font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT)
        # The same list appears on both sides, so name the side being shown.
        ttk.Label(
            bar,
            text=SECTION_PROJECT if origin == ORIGIN_PROJECT else SECTION_CORE,
            font=("Segoe UI", 9), foreground=_HEADING_FG,
        ).pack(side=tk.LEFT, padx=(8, 0))

        if not self._editing:
            ttk.Button(bar, text="Reload", command=self._reload).pack(
                side=tk.RIGHT, padx=(4, 0),
            )
        if topic.is_editable_in(origin) and not self._editing:
            ttk.Button(bar, text="Edit", command=self._start_edit).pack(side=tk.RIGHT)
        elif self._editing:
            ttk.Button(
                bar, text="Cancel", style="Danger.TButton", command=self._cancel_edit,
            ).pack(side=tk.RIGHT, padx=(4, 0))
            ttk.Button(
                bar, text="Save", style="Compile.TButton", command=self._save_edit,
            ).pack(side=tk.RIGHT)

        if topic.per_character:
            characters = topic_characters(topic, self._base_dir, self._project_dir)
            if characters:
                picker = ttk.Combobox(
                    bar, values=characters, state="readonly", width=18,
                )
                picker.set(self._character)
                picker.bind("<<ComboboxSelected>>", self._on_character_change)
                picker.pack(side=tk.RIGHT, padx=(0, 8))

        self._paragraph(self._header, topic.summary, "#C8C8C8")
        self._paragraph(
            self._header,
            topic.blurb(origin, refresh_available=refresh_tool_available()),
            "#E0A030",
        )

    def _render_values(self, topic: AllowlistTopic, origin: str) -> None:
        groups = self._groups(topic, self._character, origin)
        total = sum(len(group.values) for group in groups)
        if not total:
            self._paragraph(
                self._content,
                "Nothing on this side yet."
                if origin == ORIGIN_PROJECT
                else "No values. The base allowlists may be missing from the install.",
                "#9A9A9A",
            )
            return

        ttk.Label(
            self._content,
            text=f"{total} value{'s' if total != 1 else ''}",
            font=("Segoe UI", 8), foreground="#7A7A7A",
        ).pack(anchor=tk.W, padx=8, pady=(4, 2))

        # One Text widget for the whole list, not a widget per value: a big
        # topic runs to several hundred entries, and building that many ttk
        # frames/labels took over a second. It also makes values selectable.
        frame = ttk.Frame(self._content)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        # Lines are not wrapped, so the name/layer columns stay aligned — which
        # means a long signature needs a horizontal scrollbar to be reachable.
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        hscroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL)
        view = tk.Text(
            frame, wrap=tk.NONE, font=("Consolas", 10),
            bg="#1E1E1E", fg="#C8C8C8", relief=tk.FLAT, borderwidth=0,
            highlightthickness=0, padx=0, pady=0,
            cursor="arrow", takefocus=0,
            yscrollcommand=scroll.set, xscrollcommand=hscroll.set,
        )
        scroll.configure(command=view.yview)
        hscroll.configure(command=view.xview)
        view.tag_configure("group", foreground="#D4D4D4", font=("Consolas", 10, "bold"))
        view.tag_configure("value", foreground="#9CDCFE")
        view.tag_configure("badge", foreground="#6A6A6A")
        view.tag_configure("detail", foreground="#8A8A8A")
        view.tag_configure("empty", foreground="#6A6A6A")

        for group in groups:
            if group.title:
                view.insert(tk.END, f"{group.title}\n", "group")
            if not group.values:
                view.insert(tk.END, "    (none)\n", "empty")
                continue
            for value in group.values:
                # Pad to a column, but never let a long name touch its badge.
                gap = " " * max(2, _BADGE_COLUMN - len(value.name))
                view.insert(tk.END, f"{value.name}{gap}", "value")
                view.insert(tk.END, f"{_source_badge(value)}\n", "badge")
                for field, text in value.details:
                    view.insert(tk.END, f"    {field}: {text}\n", "detail")

        view.configure(state=tk.DISABLED)
        hscroll.pack(side=tk.BOTTOM, fill=tk.X)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        view.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _paragraph(
        self, parent: tk.Widget, text: str, colour: str, *, indent: int = 8,
    ) -> None:
        # A wrapping ttk.Label, not a Text: measuring a Text's wrapped height
        # costs ~45 ms per call (``count -displaylines`` forces a relayout), and
        # these paragraphs carry no clickable links to justify it.
        label = ttk.Label(
            parent, text=text, foreground=colour, font=("Segoe UI", 9),
            justify=tk.LEFT, wraplength=560,
        )
        label.pack(fill=tk.X, anchor=tk.W, padx=(indent, 8), pady=(0, 4))

        def rewrap(event: tk.Event) -> None:
            # Guarded so setting wraplength (which fires <Configure> again)
            # converges instead of looping.
            width = max(200, event.width - 8)
            if label.cget("wraplength") != width:
                label.configure(wraplength=width)

        label.bind("<Configure>", rewrap)

    # -- Editing -----------------------------------------------------------

    def _render_editor(self, topic: AllowlistTopic) -> None:
        path = self._edit_path(topic)
        self._paragraph(
            self._content,
            f"Editing {path}. Comments are preserved — the file is saved exactly "
            "as typed, after a YAML check.",
            "#9A9A9A",
        )
        # The list above is filtered to one side; the file is not. Say so rather
        # than let the editor look like it opened "the project's values".
        #
        # Count only what *this file* holds. Asking the merged view for its core
        # values counts the base layer too, which lives in an entirely different
        # file — it reported 15 game arm poses for a project file that no longer
        # exists.
        core_count = sum(
            1
            for values in read_layer(
                topic, self._project_dir, self._character, layer="project",
            ).values()
            for value in values
            if value.origin == ORIGIN_CORE
        )
        if core_count:
            self._paragraph(
                self._content,
                f"Note: {core_count} of the entries below came with the game "
                "rather than from this project — engine values such as Player, "
                "Narrator or day, which every project's allowlist repeats. They "
                "are listed under Core game, not here, so the list above is "
                "shorter than the file. Leave them as they are.",
                "#E0A030",
            )
        if not topic.survives_refresh and refresh_tool_available():
            self._paragraph(
                self._content,
                "Heads up: the allowlist refresh rewrites this file, and this "
                "install can run it. Add the value at your project's source "
                "instead — what you save here would be lost on the next run.",
                "#E0A030",
            )
        frame = ttk.Frame(self._content)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        text = tk.Text(
            frame, wrap=tk.NONE, font=("Consolas", 10),
            bg="#252526", fg="#D4D4D4", insertbackground="#D4D4D4",
            relief=tk.FLAT, padx=6, pady=4, highlightthickness=0,
            yscrollcommand=scroll.set,
        )
        scroll.configure(command=text.yview)
        try:
            text.insert("1.0", path.read_text(encoding="utf-8"))
        except OSError:
            text.insert("1.0", f"{topic.item_key}: []\n")
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._edit_text = text

    def _edit_path(self, topic: AllowlistTopic) -> Path:
        # Editing always targets the project layer: the base layer ships inside
        # the app bundle, where a write lands in a temp dir and is lost.
        assert self._project_dir is not None
        return topic_path(topic, self._project_dir, self._character)

    def _start_edit(self) -> None:
        if self._current is None:
            return
        if self._project_dir is None:
            messagebox.showinfo(
                "No project layer",
                "These edits apply to a project's own allowlists, and this session "
                "has no project open. Open a project first.",
                parent=self,
            )
            return
        self._editing = True
        self._render()

    def _cancel_edit(self) -> None:
        self._editing = False
        self._edit_text = None
        self._render()

    def _save_edit(self) -> None:
        if self._current is None or self._edit_text is None:
            return
        topic, _origin = self._current
        content = self._edit_text.get("1.0", "end-1c")
        error = validate_topic_yaml(topic, content)
        if error is not None:
            messagebox.showerror("Not saved", error, parent=self)
            return
        # Confirm once per session for the files the refresh rewrites — but only
        # where the refresh actually exists. The packaged app ships the GUI
        # alone, so asking its users about a tool they cannot run would be a
        # prompt with no possible action behind it.
        if (
            not topic.survives_refresh
            and refresh_tool_available()
            and topic.key not in self._warned_keys
        ):
            proceed = messagebox.askokcancel(
                "This file is regenerated",
                f"{topic.filename} is rewritten by the allowlist refresh, and "
                "this install can run it.\n\n"
                "Add the value at your project's source instead — an edit saved "
                "here will be lost the next time the refresh runs.\n\n"
                "Save anyway?",
                parent=self,
            )
            if not proceed:
                return
            self._warned_keys.add(topic.key)
        path = self._edit_path(topic)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
        except OSError as exc:
            messagebox.showerror("Not saved", f"Could not write {path}:\n\n{exc}", parent=self)
            return
        self._editing = False
        self._edit_text = None
        # The file on disk changed under the caches; drop them so the value list
        # and the name index reflect what was just written. Both sides go: an
        # entry can carry a source_file that puts it on the Core side.
        for origin in (ORIGIN_CORE, ORIGIN_PROJECT):
            self._groups_cache.pop((topic.key, self._character, origin), None)
        self._name_index = None
        self._render()

    # -- Plumbing ----------------------------------------------------------

    def _on_character_change(self, event: tk.Event) -> None:
        self._character = event.widget.get()
        self._render()

    def _close(self) -> None:
        self.destroy()

    def _center_on(self, master: tk.Widget) -> None:
        self.update_idletasks()
        try:
            x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
            y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except tk.TclError:
            pass


def _source_badge(value: AllowlistValue) -> str:
    """Return the short provenance label shown at the right of a value row.

    The side of the split already says game or project, so the badge carries the
    finer detail instead: which tree it was scanned from, ``<builtin>`` for an
    engine value, or "hand-written" for an entry with no recorded source.
    """
    if not value.source:
        return "hand-written"
    return value.source.split("/", 1)[0].split("\\", 1)[0]
