"""Extract the list of valid interpolation paths usable inside ``[...]``.

Rules (spec §5.7):

- Hardcoded baseline, extended per-character for each character discovered
  on disk.
- ``interpolation_custom.yaml`` is a manual file (scaffold) the dev fills
  in when a project needs extra paths; it is preserved across runs and
  is not overwritten by this extractor.
"""

from __future__ import annotations

from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import list_character_folders


# Player interpolation roots must be PascalCase to match the TNH store
# variable name — ``default Player = PlayerClass(...)`` in
# ``TheNullHypothesis/game/characters/Player/character.rpy:1``. The base
# game writes dialogues as ``[Player.first_name]``, never
# ``[player.first_name]``. Lowercase would pass the compiler's
# allowlist check but crash at runtime with
# ``NameError: name 'player' is not defined`` the moment Ren'Py's
# ``!i`` re-interpolation (phone-text screen render) evaluates the
# stored template.
_PLAYER_PATHS: tuple[str, ...] = (
    "Player.name",
    "Player.first_name",
    "Player.petname",
)

_CHARACTER_PATH_SUFFIXES: tuple[str, ...] = (
    "name",
    "petname",
    "Player_petname",
)

_WORLD_PATHS: tuple[str, ...] = (
    "day",
    "time_index",
    "weekday",
    "season",
    "chapter",
    "chapter_day",
    "season_day",
)


def _discover_character_tags(context: ScanContext) -> list[str]:
    """Return the PascalCase character tags visible from TNH plus the mod.

    ``Player`` lives under ``characters/Player/`` but is already covered
    explicitly by ``_PLAYER_PATHS`` (which includes ``first_name`` —
    Player-specific, absent from the standard ``name``/``petname``/
    ``Player_petname`` triple). Exclude it here to avoid emitting
    duplicate ``Player.name`` / ``Player.petname`` entries from both
    sources.
    """
    tags: list[str] = []
    seen: set[str] = {"Player"}

    if context.include_tnh:
        tnh_chars = context.base_game_root / "game" / "characters"
        for folder in list_character_folders(tnh_chars):
            if folder.name not in seen:
                tags.append(folder.name)
                seen.add(folder.name)

    game_dir = context.project_root / "game"
    if game_dir.exists():
        for prefix in sorted(game_dir.iterdir()):
            if not prefix.is_dir():
                continue
            characters_dir = prefix / "characters"
            if not characters_dir.exists():
                continue
            for folder in list_character_folders(characters_dir):
                if folder.name not in seen:
                    tags.append(folder.name)
                    seen.add(folder.name)

    return tags


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` listing every hardcoded path."""
    result = ExtractionResult(category = "interpolation")

    for path in _PLAYER_PATHS:
        result.entries.append(
            AllowlistEntry(name = path, source_file = "<builtin>", source_line = 0),
        )

    for tag in _discover_character_tags(context):
        # Character tags are PascalCase and match the store variable name
        # exactly (``JeanGrey``, ``Rogue``, ``LauraKinney``) — that's what
        # Ren'Py's ``[...]`` interpolation resolves against at runtime.
        # An earlier draft lowercased the first letter (``jeanGrey.petname``)
        # on the mistaken assumption that TNH exposed a camelCase alias; no
        # such alias exists, and the phone-text screen's ``!i`` re-interpolation
        # crashes with ``NameError: name 'jeanGrey' is not defined`` on any
        # message authored against the old convention.
        for suffix in _CHARACTER_PATH_SUFFIXES:
            path = f"{tag}.{suffix}"
            result.entries.append(
                AllowlistEntry(name = path, source_file = "<builtin>", source_line = 0),
            )

    for path in _WORLD_PATHS:
        result.entries.append(
            AllowlistEntry(name = path, source_file = "<builtin>", source_line = 0),
        )

    return result
