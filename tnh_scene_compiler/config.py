"""Load and validate ``tnh_scene_compiler.yaml`` configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_CONFIG_FILENAME = "tnh_scene_compiler.yaml"


@dataclass(frozen=True, slots=True)
class RefreshConfig:
    """Optional settings for the allowlist-refresh tool."""

    base_game: Path
    mod_root: Path


@dataclass(frozen=True, slots=True)
class Config:
    """Resolved configuration for a single mod project."""

    mod_prefix: str
    scenes_source: Path
    mod_allowlists: Path
    output: Path
    include_base_allowlists: bool
    refresh: RefreshConfig | None
    config_dir: Path

    @property
    def base_allowlists_dir(self) -> Path | None:
        """Path to the base allowlists shipped with the tool, or ``None``."""
        if not self.include_base_allowlists:
            return None
        tool_root = Path(__file__).resolve().parent.parent
        candidate = tool_root / "allowlists_base"
        if candidate.is_dir():
            return candidate
        return None


class ConfigError(Exception):
    """Raised when the configuration file is missing or invalid."""


def find_config(start: Path) -> Path | None:
    """Walk up from *start* until a ``tnh_scene_compiler.yaml`` is found."""
    current = start.resolve()
    while True:
        candidate = current / _CONFIG_FILENAME
        if candidate.is_file():
            return candidate
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

    mod_prefix = raw.get("mod_prefix")
    if not mod_prefix or not isinstance(mod_prefix, str):
        raise ConfigError("'mod_prefix' is required in config and must be a non-empty string.")
    if not _is_valid_prefix(mod_prefix):
        raise ConfigError(
            f"'mod_prefix' must match [a-z][a-z0-9_]*, got: {mod_prefix!r}"
        )

    scenes_source = _resolve(config_dir, raw.get("scenes_source", "scenes_source/"))
    mod_allowlists = _resolve(config_dir, raw.get("mod_allowlists", "scenes_source/_allowlists/"))

    default_output = f"game/{mod_prefix}/scenes/"
    output = _resolve(config_dir, raw.get("output", default_output))

    include_base = raw.get("include_base_allowlists", True)
    if not isinstance(include_base, bool):
        include_base = True

    refresh_raw = raw.get("refresh")
    refresh: RefreshConfig | None = None
    if isinstance(refresh_raw, dict):
        refresh = RefreshConfig(
            base_game=_resolve(config_dir, refresh_raw.get("base_game", "../TheNullHypothesis/")),
            mod_root=_resolve(config_dir, refresh_raw.get("mod_root", ".")),
        )

    return Config(
        mod_prefix=mod_prefix,
        scenes_source=scenes_source,
        mod_allowlists=mod_allowlists,
        output=output,
        include_base_allowlists=include_base,
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
