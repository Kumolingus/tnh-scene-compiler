"""Load allowlists from ``scenes_source/_allowlists/`` and expose lookups.

The validator needs fast ``in`` checks and "did you mean" suggestions, not
the full provenance-tagged data the cheatsheet uses. This module intentionally
reads the same YAML files as ``generate_cheatsheet`` but returns a stripped-
down view focused on validation.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _read_yaml(path: Path) -> dict[str, Any] | None:
    """Return the top-level mapping of ``path`` or ``None`` if missing/empty."""
    if not path.is_file():
        return None
    with path.open("r", encoding = "utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        return None
    return data


def _values_names(payload: dict[str, Any] | None, key: str = "values") -> list[str]:
    """Extract the ``name`` field of every entry under ``key``."""
    if not payload:
        return []
    entries = payload.get(key)
    if not isinstance(entries, list):
        return []
    return [
        item["name"]
        for item in entries
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]


def _build_location_map(
    auto_payload: dict[str, Any] | None,
    overrides_payload: dict[str, Any] | None,
) -> dict[str, str]:
    """Return ``{slugline_text: location_id}`` with overrides winning."""
    result: dict[str, str] = {}
    if auto_payload:
        for item in auto_payload.get("values", []) or []:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                loc_id = item.get("location_id")
                if isinstance(loc_id, str):
                    result[item["name"]] = loc_id
    if overrides_payload:
        for item in overrides_payload.get("overrides", []) or []:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                loc_id = item.get("location_id")
                if isinstance(loc_id, str):
                    result[item["name"]] = loc_id
    return result


def _build_interpolation_set(
    auto_payload: dict[str, Any] | None,
    custom_payload: dict[str, Any] | None,
) -> set[str]:
    """Return every allowed interpolation path (auto + custom)."""
    paths: set[str] = set(_values_names(auto_payload))
    if custom_payload:
        for item in custom_payload.get("paths", []) or []:
            if isinstance(item, str):
                paths.add(item)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                paths.add(item["name"])
    return paths


def _load_per_char_simple(dir_path: Path) -> dict[str, set[str]]:
    """Return ``{character: set(names)}`` for a simple ``values:`` per-char dir.

    Used by faces/poses/outfits where each character YAML carries a single
    ``values`` list with one name per entry.
    """
    result: dict[str, set[str]] = {}
    if not dir_path.is_dir():
        return result
    for yaml_file in sorted(dir_path.glob("*.yaml")):
        if yaml_file.name.startswith("_"):
            continue
        char = yaml_file.stem
        payload = _read_yaml(yaml_file)
        if payload is None:
            continue
        result[char] = set(_values_names(payload))
    return result


def _load_per_char_arms(
    dir_path: Path,
) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, set[str]]]:
    """Return ``(arms, left_arm, right_arm)`` dicts keyed by character.

    The arms YAML has three subgroups per character: ``arms``, ``left_arm``,
    ``right_arm``. The parenthetical grammar only accepts ``arms`` as a
    positional/named slot; ``left_arm`` and ``right_arm`` are named-only
    (§11.6 "Valid keys").
    """
    arms: dict[str, set[str]] = {}
    left: dict[str, set[str]] = {}
    right: dict[str, set[str]] = {}
    if not dir_path.is_dir():
        return arms, left, right
    for yaml_file in sorted(dir_path.glob("*.yaml")):
        if yaml_file.name.startswith("_"):
            continue
        char = yaml_file.stem
        payload = _read_yaml(yaml_file)
        if payload is None:
            continue
        arms[char] = set(_values_names(payload, key = "arms"))
        left[char] = set(_values_names(payload, key = "left_arm"))
        right[char] = set(_values_names(payload, key = "right_arm"))
    return arms, left, right


def _load_moods_with_shared(
    dir_path: Path,
) -> tuple[set[str], dict[str, set[str]]]:
    """Return ``(shared_moods, per_char_moods)``.

    The parenthetical check against a mood uses ``shared_moods`` combined with
    ``per_char_moods[C]``.
    Keeping the two apart lets error messages say "X is a shared mood,
    valid for every character" vs "X is valid for Rogue only".
    """
    shared: set[str] = set()
    per_char: dict[str, set[str]] = {}
    shared_path = dir_path / "_shared.yaml"
    shared_payload = _read_yaml(shared_path)
    if shared_payload is not None:
        shared = set(_values_names(shared_payload))
    if not dir_path.is_dir():
        return shared, per_char
    for yaml_file in sorted(dir_path.glob("*.yaml")):
        if yaml_file.name.startswith("_"):
            continue
        char = yaml_file.stem
        payload = _read_yaml(yaml_file)
        if payload is None:
            continue
        per_char[char] = set(_values_names(payload))
    return shared, per_char


@dataclass(slots=True)
class Allowlists:
    """Validator-facing view of the allowlists.

    Phase 6B adds per-character mood/face/pose/arms/outfit sets so the
    parenthetical grammar §11.6 can cross-lookup a value against every
    slot and suggest the right key when a writer picks the wrong one.

    Attributes:
        characters: PascalCase character identifiers from
            ``characters.yaml``. Used to validate SPEAKER tokens and
            attribute-access roots.
        locations: Slugline text -> location_id mapping, merged from
            ``locations.yaml`` and ``locations_overrides.yaml``.
        interpolation: Set of allowed interpolation paths.
        characters_upper: Pre-computed uppercase set so speaker tokens
            like ``JEANGREY`` can be checked in O(1).
        shared_moods: Global shared mood set (from ``moods/_shared.yaml``).
        char_moods: Per-character mood additions (not including the shared).
        char_faces / char_poses / char_outfits: one set per character.
        char_arms / char_left_arm / char_right_arm: three sets per character
            matching the YAML subgroups in ``arms/<Character>.yaml``.
        looks: Global look values (``looks.yaml``). Same list for every
            character.
        stages: Global stage values (``stages.yaml``).
    """

    characters: list[str] = field(default_factory=list)
    locations: dict[str, str] = field(default_factory=dict)
    interpolation: set[str] = field(default_factory=set)
    characters_upper: set[str] = field(default_factory=set)
    shared_moods: set[str] = field(default_factory=set)
    char_moods: dict[str, set[str]] = field(default_factory=dict)
    char_faces: dict[str, set[str]] = field(default_factory=dict)
    char_poses: dict[str, set[str]] = field(default_factory=dict)
    char_outfits: dict[str, set[str]] = field(default_factory=dict)
    char_arms: dict[str, set[str]] = field(default_factory=dict)
    char_left_arm: dict[str, set[str]] = field(default_factory=dict)
    char_right_arm: dict[str, set[str]] = field(default_factory=dict)
    looks: set[str] = field(default_factory=set)
    stages: set[str] = field(default_factory=set)
    sfx: set[str] = field(default_factory=set)
    mod_operations: set[str] = field(default_factory=set)
    fx: set[str] = field(default_factory=set)
    condition_functions: set[str] = field(default_factory=set)
    character_methods: set[str] = field(default_factory=set)
    traits: set[str] = field(default_factory=set)
    personalities: set[str] = field(default_factory=set)
    history_events: set[str] = field(default_factory=set)
    character_aliases: dict[str, str] = field(default_factory=dict)
    function_aliases: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, allowlists_dir: Path) -> Allowlists:
        """Read every YAML the validator needs. Missing files are tolerated."""
        characters = _values_names(_read_yaml(allowlists_dir / "characters.yaml"))
        locations = _build_location_map(
            _read_yaml(allowlists_dir / "locations.yaml"),
            _read_yaml(allowlists_dir / "locations_overrides.yaml"),
        )
        interpolation = _build_interpolation_set(
            _read_yaml(allowlists_dir / "interpolation.yaml"),
            _read_yaml(allowlists_dir / "interpolation_custom.yaml"),
        )

        shared_moods, char_moods = _load_moods_with_shared(allowlists_dir / "moods")
        char_faces = _load_per_char_simple(allowlists_dir / "faces")
        char_poses = _load_per_char_simple(allowlists_dir / "poses")
        char_outfits = _load_per_char_simple(allowlists_dir / "outfits")
        char_arms, char_left_arm, char_right_arm = _load_per_char_arms(
            allowlists_dir / "arms",
        )

        looks = set(_values_names(_read_yaml(allowlists_dir / "looks.yaml")))
        stages = set(_values_names(_read_yaml(allowlists_dir / "stages.yaml")))
        sfx = set(_values_names(_read_yaml(allowlists_dir / "sfx.yaml")))

        # Mod-operations allowlist (hand-maintained manual scaffold).
        mod_operations_payload = _read_yaml(allowlists_dir / "mod_operations.yaml")
        mod_operations: set[str] = set()
        if mod_operations_payload and isinstance(
            mod_operations_payload.get("operations"), list,
        ):
            for item in mod_operations_payload["operations"]:
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    mod_operations.add(item["name"])

        # Engine-effects allowlist (hand-maintained). Populated with the
        # TNH core helpers writers are allowed to trigger from [[fx]] —
        # phone_buzz, knock_on_door, bamf, and the displayables/effects
        # family. Schema parallels mod_operations.yaml.
        fx_payload = _read_yaml(allowlists_dir / "fx.yaml")
        fx: set[str] = set()
        if fx_payload and isinstance(fx_payload.get("effects"), list):
            for item in fx_payload["effects"]:
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    fx.add(item["name"])

        # Condition-functions allowlist (hand-maintained). Helpers
        # callable from [[if]] / [[elif]] / [[choice ... if]]. The
        # codegen wraps eligible calls so the testing hub can override
        # their return value at preview time without monkey-patching.
        condition_functions_payload = _read_yaml(
            allowlists_dir / "condition_functions.yaml",
        )
        condition_functions: set[str] = set()
        if condition_functions_payload and isinstance(
            condition_functions_payload.get("functions"), list,
        ):
            for item in condition_functions_payload["functions"]:
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    condition_functions.add(item["name"])

        character_methods_payload = _read_yaml(
            allowlists_dir / "character_methods.yaml",
        )
        character_methods: set[str] = set()
        if character_methods_payload and isinstance(
            character_methods_payload.get("methods"), list,
        ):
            for item in character_methods_payload["methods"]:
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    character_methods.add(item["name"])

        traits = set(_values_names(_read_yaml(allowlists_dir / "traits.yaml")))
        personalities = set(_values_names(
            _read_yaml(allowlists_dir / "personalities.yaml"),
        ))
        history_events = set(_values_names(
            _read_yaml(allowlists_dir / "history_events.yaml"),
        ))

        aliases_payload = _read_yaml(allowlists_dir / "aliases.yaml")
        character_aliases: dict[str, str] = {}
        function_aliases: dict[str, str] = {}
        if aliases_payload:
            raw_ca = aliases_payload.get("character_aliases")
            if isinstance(raw_ca, dict):
                character_aliases = {
                    str(k): str(v) for k, v in raw_ca.items()
                }
            raw_fa = aliases_payload.get("function_aliases")
            if isinstance(raw_fa, dict):
                function_aliases = {
                    str(k): str(v) for k, v in raw_fa.items()
                }

        return cls(
            characters = characters,
            locations = locations,
            interpolation = interpolation,
            characters_upper = {name.upper() for name in characters},
            shared_moods = shared_moods,
            char_moods = char_moods,
            char_faces = char_faces,
            char_poses = char_poses,
            char_outfits = char_outfits,
            char_arms = char_arms,
            char_left_arm = char_left_arm,
            char_right_arm = char_right_arm,
            looks = looks,
            stages = stages,
            sfx = sfx,
            mod_operations = mod_operations,
            fx = fx,
            condition_functions = condition_functions,
            character_methods = character_methods,
            traits = traits,
            personalities = personalities,
            history_events = history_events,
            character_aliases = character_aliases,
            function_aliases = function_aliases,
        )

    # --- Per-character slot membership helpers ----------------------------

    def is_mood(self, character: str, value: str) -> bool:
        if value in self.shared_moods:
            return True
        return value in self.char_moods.get(character, set())

    def is_face(self, character: str, value: str) -> bool:
        return value in self.char_faces.get(character, set())

    def is_pose(self, character: str, value: str) -> bool:
        return value in self.char_poses.get(character, set())

    def is_outfit(self, character: str, value: str) -> bool:
        return value in self.char_outfits.get(character, set())

    def is_arms_preset(self, character: str, value: str) -> bool:
        return value in self.char_arms.get(character, set())

    def is_left_arm(self, character: str, value: str) -> bool:
        return value in self.char_left_arm.get(character, set())

    def is_right_arm(self, character: str, value: str) -> bool:
        return value in self.char_right_arm.get(character, set())

    def is_look(self, value: str) -> bool:
        return value in self.looks

    def is_stage(self, value: str) -> bool:
        return value in self.stages

    def slots_for_value(self, character: str, value: str) -> list[str]:
        """Return every slot for which ``value`` is a valid token.

        Used by the cross-lookup error in §11.6 to suggest the correct
        slot when a writer puts a face name in the mood slot, etc.
        """
        hits: list[str] = []
        if self.is_mood(character, value):
            hits.append("mood")
        if self.is_face(character, value):
            hits.append("face")
        if self.is_pose(character, value):
            hits.append("pose")
        if self.is_outfit(character, value):
            hits.append("outfit")
        if self.is_arms_preset(character, value):
            hits.append("arms")
        if self.is_left_arm(character, value):
            hits.append("left_arm")
        if self.is_right_arm(character, value):
            hits.append("right_arm")
        if self.is_look(value):
            hits.append("look")
        if self.is_stage(value):
            hits.append("stage")
        return hits

    def suggest_character(self, upper_tag: str, *, max_suggestions: int = 3) -> list[str]:
        """Return characters whose uppercase form is closest to ``upper_tag``."""
        candidates = list(self.characters_upper)
        matches = difflib.get_close_matches(
            upper_tag, candidates, n = max_suggestions, cutoff = 0.5,
        )
        # Map the matched uppercase tags back to the canonical PascalCase form.
        upper_to_canonical = {name.upper(): name for name in self.characters}
        return [upper_to_canonical[m] for m in matches if m in upper_to_canonical]

    def match_location(self, text: str) -> str | None:
        """Try to match *text* against registered locations.

        Returns the canonical location key if found, ``None`` otherwise.
        First tries an exact lookup.  If that fails, tries to match against
        locations that contain ``[…]`` interpolation by collapsing each
        ``[IDENT.ATTR]`` to just ``IDENT`` and comparing (e.g.
        ``JEANGREY'S ROOM`` matches ``[JEANGREY.NAME]'S ROOM``).
        """
        if text in self.locations:
            return text
        for registered in self.locations:
            if "[" not in registered:
                continue
            simplified = re.sub(
                r"\[([A-Z_][A-Z0-9_]*)(?:\.[A-Za-z_.]+)?\]",
                r"\1",
                registered,
            )
            if simplified == text:
                return registered
        return None

    def suggest_slugline(self, text: str, *, max_suggestions: int = 3) -> list[str]:
        return difflib.get_close_matches(
            text, list(self.locations), n = max_suggestions, cutoff = 0.5,
        )

    def suggest_interpolation(self, path: str, *, max_suggestions: int = 3) -> list[str]:
        return difflib.get_close_matches(
            path, list(self.interpolation), n = max_suggestions, cutoff = 0.5,
        )

    def suggest_condition_function(self, name: str, *, max_suggestions: int = 3) -> list[str]:
        return difflib.get_close_matches(
            name, list(self.condition_functions), n = max_suggestions, cutoff = 0.5,
        )

    def suggest_character_method(self, name: str, *, max_suggestions: int = 3) -> list[str]:
        return difflib.get_close_matches(
            name, list(self.character_methods), n = max_suggestions, cutoff = 0.5,
        )

    # --- Multi-layer support ------------------------------------------------

    def merge(self, other: Allowlists) -> Allowlists:
        """Return a new ``Allowlists`` combining *self* (base) with *other* (mod).

        Sets are unioned, dicts are merged (other wins on key collision),
        lists are concatenated with dedup preserving order.
        """
        merged_chars = list(dict.fromkeys(self.characters + other.characters))
        merged_locations = {**self.locations, **other.locations}
        merged_interpolation = self.interpolation | other.interpolation

        return Allowlists(
            characters=merged_chars,
            locations=merged_locations,
            interpolation=merged_interpolation,
            characters_upper={n.upper() for n in merged_chars},
            shared_moods=self.shared_moods | other.shared_moods,
            char_moods=_merge_char_sets(self.char_moods, other.char_moods),
            char_faces=_merge_char_sets(self.char_faces, other.char_faces),
            char_poses=_merge_char_sets(self.char_poses, other.char_poses),
            char_outfits=_merge_char_sets(self.char_outfits, other.char_outfits),
            char_arms=_merge_char_sets(self.char_arms, other.char_arms),
            char_left_arm=_merge_char_sets(self.char_left_arm, other.char_left_arm),
            char_right_arm=_merge_char_sets(self.char_right_arm, other.char_right_arm),
            looks=self.looks | other.looks,
            stages=self.stages | other.stages,
            sfx=self.sfx | other.sfx,
            mod_operations=self.mod_operations | other.mod_operations,
            fx=self.fx | other.fx,
            condition_functions=self.condition_functions | other.condition_functions,
            character_methods=self.character_methods | other.character_methods,
            traits=self.traits | other.traits,
            personalities=self.personalities | other.personalities,
            history_events=self.history_events | other.history_events,
            character_aliases={**self.character_aliases, **other.character_aliases},
            function_aliases={**self.function_aliases, **other.function_aliases},
        )

    @classmethod
    def load_layered(cls, dirs: list[Path]) -> Allowlists:
        """Load allowlists from multiple directories and merge them in order.

        The first directory is the base layer; subsequent directories are
        mod layers that extend and override the base.  Missing directories
        are silently skipped.
        """
        result: Allowlists | None = None
        for d in dirs:
            if not d.is_dir():
                continue
            layer = cls.load(d)
            result = layer if result is None else result.merge(layer)
        return result if result is not None else cls()


def _merge_char_sets(
    base: dict[str, set[str]],
    mod: dict[str, set[str]],
) -> dict[str, set[str]]:
    """Union per-character sets from two layers."""
    merged = dict(base)
    for char, values in mod.items():
        if char in merged:
            merged[char] = merged[char] | values
        else:
            merged[char] = set(values)
    return merged
