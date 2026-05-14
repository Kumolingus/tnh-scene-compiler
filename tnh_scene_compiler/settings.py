"""Application-level settings stored in the user's app data directory.

Settings are distinct from project config: they control how the tool
behaves regardless of which project is loaded (UI preferences, display
options).  Stored as YAML in ``%APPDATA%/tnh_scene_compiler/settings.yaml``
(Windows) or ``~/.config/tnh_scene_compiler/settings.yaml`` (other OS).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml


def _settings_dir() -> Path:
    """Return the platform-appropriate directory for app settings."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "tnh_scene_compiler"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "tnh_scene_compiler"
    return Path.home() / ".config" / "tnh_scene_compiler"


def _settings_path() -> Path:
    return _settings_dir() / "settings.yaml"


@dataclass
class AppSettings:
    """User preferences for the tool."""

    featured_characters_only: bool = True

    def save(self) -> None:
        """Persist current settings to disk."""
        path = _settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {}
        for f in fields(self):
            data[f.name] = getattr(self, f.name)
        path.write_text(
            yaml.safe_dump(data, sort_keys=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls) -> AppSettings:
        """Load settings from disk, falling back to defaults."""
        path = _settings_path()
        if not path.is_file():
            return cls()
        try:
            with path.open("r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh)
        except (OSError, yaml.YAMLError):
            return cls()
        if not isinstance(raw, dict):
            return cls()
        kwargs: dict[str, Any] = {}
        for f in fields(cls):
            if f.name in raw and isinstance(raw[f.name], type(f.default)):
                kwargs[f.name] = raw[f.name]
        return cls(**kwargs)
