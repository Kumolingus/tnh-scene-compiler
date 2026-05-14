"""Load and validate ``tnh_scene_compiler.<prefix>.yaml`` configuration."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def get_data_root() -> Path:
    """Return the root directory for bundled data files.

    Inside a PyInstaller bundle ``sys.frozen`` is set and data lives
    under ``sys._MEIPASS``.  Otherwise fall back to the repository root
    (one level above this package).
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


_CONFIG_GLOB = "tnh_scene_compiler.*.yaml"
_CONFIG_LEGACY = "tnh_scene_compiler.yaml"


def config_filename(project_prefix: str) -> str:
    """Return the canonical config filename for *project_prefix*."""
    return f"tnh_scene_compiler.{project_prefix}.yaml"


@dataclass(frozen=True, slots=True)
class RefreshConfig:
    """Optional settings for the allowlist-refresh tool."""

    base_game: Path
    project_root: Path


@dataclass(frozen=True, slots=True)
class Config:
    """Resolved configuration for a single mod project."""

    project_prefix: str
    scenes_source: Path
    project_allowlists: Path
    output: Path
    include_base_allowlists: bool
    featured_characters_only: bool
    refresh: RefreshConfig | None
    config_dir: Path

    @property
    def base_allowlists_dir(self) -> Path | None:
        """Path to the base allowlists shipped with the tool, or ``None``."""
        if not self.include_base_allowlists:
            return None
        candidate = get_data_root() / "allowlists_base"
        if candidate.is_dir():
            return candidate
        return None


class ConfigError(Exception):
    """Raised when the configuration file is missing or invalid."""


def find_config(start: Path) -> Path | None:
    """Walk up from *start* looking for a config file.

    Searches for ``tnh_scene_compiler.*.yaml`` first, then falls back
    to the legacy ``tnh_scene_compiler.yaml``.  Returns ``None`` when
    nothing is found or when multiple new-style files exist in the
    same directory (ambiguous — user must specify).
    """
    current = start.resolve()
    while True:
        matches = sorted(current.glob(_CONFIG_GLOB))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None
        legacy = current / _CONFIG_LEGACY
        if legacy.is_file():
            return legacy
        parent = current.parent
        if parent == current:
            return None
        current = parent


def load_config(path: Path) -> Config:
    """Read, validate, and resolve a ``tnh_scene_compiler.yaml``."""
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise ConfigError(f"Config file must be a YAML mapping: {path}")

    config_dir = path.resolve().parent

    project_prefix = raw.get("project_prefix")
    if not project_prefix or not isinstance(project_prefix, str):
        raise ConfigError("'project_prefix' is required in config and must be a non-empty string.")
    if not _is_valid_prefix(project_prefix):
        raise ConfigError(
            f"'project_prefix' must match [a-z][a-z0-9_]*, got: {project_prefix!r}"
        )

    scenes_source = _resolve(config_dir, raw.get("scenes_source", "scenes_source/"))
    project_allowlists = _resolve(config_dir, raw.get("project_allowlists", "scenes_source/_allowlists/"))

    default_output = f"game/{project_prefix}/scenes/"
    output = _resolve(config_dir, raw.get("output", default_output))

    include_base = raw.get("include_base_allowlists", True)
    if not isinstance(include_base, bool):
        include_base = True

    featured_only = raw.get("featured_characters_only", True)
    if not isinstance(featured_only, bool):
        featured_only = True

    refresh_raw = raw.get("refresh")
    refresh: RefreshConfig | None = None
    if isinstance(refresh_raw, dict):
        refresh = RefreshConfig(
            base_game=_resolve(config_dir, refresh_raw.get("base_game", "../TheNullHypothesis/")),
            project_root=_resolve(config_dir, refresh_raw.get("project_root", ".")),
        )

    return Config(
        project_prefix=project_prefix,
        scenes_source=scenes_source,
        project_allowlists=project_allowlists,
        output=output,
        include_base_allowlists=include_base,
        featured_characters_only=featured_only,
        refresh=refresh,
        config_dir=config_dir,
    )


def _resolve(base: Path, relative: str | Any) -> Path:
    """Resolve a path relative to the config directory."""
    if not isinstance(relative, str):
        relative = str(relative)
    p = Path(relative)
    if p.is_absolute():
        return p
    return (base / p).resolve()


def _is_valid_prefix(prefix: str) -> bool:
    """Check that *prefix* looks like a valid Python/Ren'Py identifier prefix."""
    if not prefix:
        return False
    if not prefix[0].isalpha() or prefix[0].isupper():
        return False
    return all(c.isalnum() or c == "_" for c in prefix)
