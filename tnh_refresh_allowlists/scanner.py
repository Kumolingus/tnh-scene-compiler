"""Filesystem traversal helpers used by extractors."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .models import ScanContext


def iter_rpy_files(root: Path) -> Iterable[Path]:
    """Yield every ``.rpy`` file under ``root`` in sorted order.

    Skips anything under a ``.playtest`` or ``.renpy-validation`` directory.
    """
    if not root.exists():
        return

    for path in sorted(root.rglob("*.rpy")):
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        yield path


def iter_all_rpy(context: ScanContext) -> Iterable[Path]:
    """Yield every ``.rpy`` file across TNH (when included) and the mod."""
    if context.include_tnh:
        yield from iter_rpy_files(context.base_game_root)
    yield from iter_rpy_files(context.project_root)


def safe_read_text(path: Path) -> str | None:
    """Return ``path``'s text as UTF-8, or ``None`` on decode error."""
    try:
        return path.read_text(encoding = "utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def iter_audio_files(root: Path, extensions: tuple[str, ...] = (".ogg", ".wav", ".mp3")) -> Iterable[Path]:
    """Yield every audio file under ``root`` matching one of ``extensions``."""
    if not root.exists():
        return

    for ext in extensions:
        yield from sorted(root.rglob(f"*{ext}"))


def list_character_folders(characters_root: Path) -> list[Path]:
    """Return the list of PascalCase character folders under ``characters_root``.

    A folder qualifies as a character folder when its name starts with an
    uppercase ASCII letter and it contains a ``character.rpy`` file directly
    (not in a deeper subfolder). When a folder does not contain
    ``character.rpy`` but its own immediate subfolders do (TNH's
    ``Silhouettes/`` grouping folder, for example), the scan recurses one
    level and emits those subfolders instead. The grouping folder itself
    is never listed as a character.
    """
    if not characters_root.exists():
        return []

    out: list[Path] = []
    for candidate in sorted(characters_root.iterdir()):
        if not candidate.is_dir():
            continue
        if not candidate.name or not candidate.name[0].isupper():
            continue

        if (candidate / "character.rpy").exists():
            out.append(candidate)
            continue

        # Grouping folder — recurse one level.
        for sub in sorted(candidate.iterdir()):
            if not sub.is_dir():
                continue
            if not sub.name or not sub.name[0].isupper():
                continue
            if (sub / "character.rpy").exists():
                out.append(sub)

    return out
