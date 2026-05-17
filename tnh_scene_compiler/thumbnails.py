"""Runtime thumbnail loader for character face and arm previews.

Reads ``_mapping.yaml`` from the bundled ``thumbnails/`` directory and
serves ``tk.PhotoImage`` objects with lazy caching.  No Pillow dependency
at runtime — uses native Tk 8.6+ PNG support.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Any

import yaml

from .config import get_data_root


class ThumbnailStore:
    """Loads ``_mapping.yaml`` and serves cached ``tk.PhotoImage`` objects."""

    def __init__(self, thumbnails_dir: Path, mapping: dict[str, Any]) -> None:
        self._dir = thumbnails_dir
        self._faces: dict[str, dict[str, str]] = mapping.get("faces", {})
        self._arms: dict[str, dict[str, str]] = mapping.get("arms", {})
        self._cache: dict[str, tk.PhotoImage] = {}

    @classmethod
    def load(cls) -> ThumbnailStore | None:
        """Load from ``get_data_root() / 'thumbnails'``.

        Returns ``None`` if the thumbnails directory or mapping file is
        missing.
        """
        thumbnails_dir = get_data_root() / "thumbnails"
        mapping_path = thumbnails_dir / "_mapping.yaml"
        if not mapping_path.is_file():
            return None
        try:
            with mapping_path.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (OSError, yaml.YAMLError):
            return None
        if not isinstance(data, dict):
            return None
        return cls(thumbnails_dir, data)

    def _load_image(self, rel_path: str) -> tk.PhotoImage | None:
        """Return a cached ``PhotoImage`` for *rel_path*, or ``None``."""
        cached = self._cache.get(rel_path)
        if cached is not None:
            return cached
        full = self._dir / rel_path
        if not full.is_file():
            return None
        try:
            img = tk.PhotoImage(file=str(full))
        except tk.TclError:
            return None
        self._cache[rel_path] = img
        return img

    def get_face(self, character: str, name: str) -> tk.PhotoImage | None:
        """Return thumbnail for a face expression, or ``None``."""
        char_map = self._faces.get(character)
        if not char_map:
            return None
        rel = char_map.get(name)
        if not rel:
            return None
        return self._load_image(rel)

    def get_arms(self, character: str, name: str) -> tk.PhotoImage | None:
        """Return thumbnail for a both-arms preset, or ``None``."""
        return self._get_arm(character, f"both_{name}")

    def get_left_arm(self, character: str, name: str) -> tk.PhotoImage | None:
        """Return thumbnail for a left arm pose, or ``None``."""
        return self._get_arm(character, f"left_{name}")

    def get_right_arm(self, character: str, name: str) -> tk.PhotoImage | None:
        """Return thumbnail for a right arm pose, or ``None``."""
        return self._get_arm(character, f"right_{name}")

    def _get_arm(self, character: str, key: str) -> tk.PhotoImage | None:
        char_map = self._arms.get(character)
        if not char_map:
            return None
        rel = char_map.get(key)
        if not rel:
            return None
        return self._load_image(rel)

    def has_character(self, character: str) -> bool:
        """Return ``True`` if any thumbnails exist for *character*."""
        return bool(self._faces.get(character) or self._arms.get(character))

    def available_arms(self, character: str) -> set[str]:
        """Return arm preset names that have a thumbnail for *character*."""
        char_map = self._arms.get(character, {})
        return {k.removeprefix("both_") for k in char_map if k.startswith("both_")}

    def available_left_arms(self, character: str) -> set[str]:
        """Return left arm names that have a thumbnail for *character*."""
        char_map = self._arms.get(character, {})
        return {k.removeprefix("left_") for k in char_map if k.startswith("left_")}

    def available_right_arms(self, character: str) -> set[str]:
        """Return right arm names that have a thumbnail for *character*."""
        char_map = self._arms.get(character, {})
        return {k.removeprefix("right_") for k in char_map if k.startswith("right_")}


# -- Module-level singleton ---------------------------------------------------

_store: ThumbnailStore | None = None
_loaded = False


def get_store() -> ThumbnailStore | None:
    """Return the module-level ``ThumbnailStore`` singleton.

    Returns ``None`` if thumbnails are not available.  The mapping is
    parsed once on first call.
    """
    global _store, _loaded
    if not _loaded:
        _store = ThumbnailStore.load()
        _loaded = True
    return _store
