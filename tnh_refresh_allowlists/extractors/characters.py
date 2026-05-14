"""Extract the list of valid character speakers.

Rules (spec §5.1):

- Walk ``TheNullHypothesis/game/characters/*/`` and the mod's
  ``game/<modprefix>/characters/*/`` looking for PascalCase folders that
  contain at least one ``.rpy`` file.
- Additionally, scan every mod ``.rpy`` for
  ``define ch_<Name> = Character(...)`` declarations. Mods often define
  lightweight NPCs (``ch_Mephista``, ``ch_DreamFigure``, …) without
  giving them a full ``characters/<Name>/`` folder; those still need to
  be valid speakers in authored scenes, otherwise the compiler rejects
  legitimate dialogue.
- Explicitly add ``Player`` and ``Narrator`` even if no folder exists for them.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import iter_all_rpy, list_character_folders, safe_read_text

_CH_DEFINE_RE = re.compile(
    r'^[ \t]*define[ \t]+ch_(?P<name>[A-Z][A-Za-z0-9]+)[ \t]*=[ \t]*Character[ \t]*\(',
    re.MULTILINE,
)


def _find_mod_characters_root(project_root: Path) -> Path | None:
    """Return the mod's ``characters/`` folder if the mod ships one, else None.

    The mod's prefix folder under ``game/`` is discovered by listing ``game/``
    subdirectories; the first subfolder that contains a ``characters/``
    subdirectory is picked.
    """
    game_dir = project_root / "game"
    if not game_dir.exists():
        return None

    for candidate in sorted(game_dir.iterdir()):
        if not candidate.is_dir():
            continue
        characters_dir = candidate / "characters"
        if characters_dir.exists() and characters_dir.is_dir():
            return characters_dir
    return None


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` with one entry per discovered character."""
    result = ExtractionResult(category = "characters")

    # Base-game characters.
    if context.include_tnh:
        tnh_chars = context.base_game_root / "game" / "characters"
        for folder in list_character_folders(tnh_chars):
            result.entries.append(
                AllowlistEntry(
                    name = folder.name,
                    source_file = context.relative(folder),
                    source_line = 1,
                ),
            )

    # Mod characters.
    mod_chars = _find_mod_characters_root(context.project_root)
    if mod_chars is not None:
        for folder in list_character_folders(mod_chars):
            already_known = any(entry.name == folder.name for entry in result.entries)
            if already_known:
                continue
            result.entries.append(
                AllowlistEntry(
                    name = folder.name,
                    source_file = context.relative(folder),
                    source_line = 1,
                ),
            )

    # Lightweight NPCs defined via ``define ch_<Name> = Character(...)``.
    # These mod-side speakers have no ``characters/<Name>/`` folder but
    # are referenced by ``ch_<Name>`` in authored dialogue, so they must
    # land in the allowlist.
    for path in iter_all_rpy(context):
        text = safe_read_text(path)
        if text is None:
            continue
        cleaned = strip_noise(text)
        for match in _CH_DEFINE_RE.finditer(cleaned):
            name = match.group("name")
            if any(entry.name == name for entry in result.entries):
                continue
            line = cleaned[: match.start()].count("\n") + 1
            result.entries.append(
                AllowlistEntry(
                    name = name,
                    source_file = context.relative(path),
                    source_line = line,
                ),
            )

    # Explicit additions.
    for synthetic in ("Player", "Narrator"):
        if not any(entry.name == synthetic for entry in result.entries):
            result.entries.append(
                AllowlistEntry(name = synthetic, source_file = "<builtin>", source_line = 0),
            )

    return result
