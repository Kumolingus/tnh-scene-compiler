"""Extract the list of valid sound-effect names from audio file directories.

Rules (spec §5.6):

- Scan the conventional audio folders only:
    - ``TheNullHypothesis/game/sounds/effects/``
    - ``TheNullHypothesis/game/sounds/interfaces/``
    - ``<mod>/game/<modprefix>/sounds/sfx/``
- Any ``.ogg``, ``.wav``, or ``.mp3`` file under those folders becomes a
  candidate. Name is the filename without extension.
- No scanning of ``renpy.play()`` calls.
"""

from __future__ import annotations

from pathlib import Path

from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import iter_audio_files


def _mod_sfx_roots(mod_root: Path) -> list[Path]:
    """Return every ``<mod>/game/<modprefix>/sounds/sfx`` folder under ``mod_root``."""
    game_dir = mod_root / "game"
    if not game_dir.exists():
        return []

    roots: list[Path] = []
    for candidate in sorted(game_dir.iterdir()):
        if not candidate.is_dir():
            continue
        sfx_dir = candidate / "sounds" / "sfx"
        if sfx_dir.exists() and sfx_dir.is_dir():
            roots.append(sfx_dir)
    return roots


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` listing every discovered SFX."""
    result = ExtractionResult(category = "sfx")

    roots: list[Path] = []
    if context.include_tnh:
        roots.append(context.base_game_root / "game" / "sounds" / "effects")
        roots.append(context.base_game_root / "game" / "sounds" / "interfaces")
    roots.extend(_mod_sfx_roots(context.mod_root))

    seen: set[str] = set()
    for root in roots:
        for audio in iter_audio_files(root):
            name = audio.stem
            if name in seen:
                continue
            seen.add(name)
            result.entries.append(
                AllowlistEntry(
                    name = name,
                    source_file = context.relative(audio),
                    source_line = 0,
                ),
            )

    return result
