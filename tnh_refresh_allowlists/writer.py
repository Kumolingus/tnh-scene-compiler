"""Emit YAML allowlists in the frozen schema."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .models import AllowlistEntry, ExtractionResult


def _format_generated_at(generated_at: datetime | None) -> str:
    """Render the ``generated_at`` stamp as a plain ``YYYY-MM-DD`` date.

    Date-only keeps the YAMLs stable within a single working day: multiple
    refreshes in the same session produce identical output, so the only
    diff on an unchanged extraction is zero files, not N files with a
    fresh ISO timestamp on the ``generated_at`` header line.
    """
    return (generated_at or datetime.now(timezone.utc)).date().isoformat()


def _dump_yaml(data: Any, out_path: Path) -> None:
    """Write ``data`` to ``out_path`` as UTF-8 YAML with LF line endings."""
    out_path.parent.mkdir(parents = True, exist_ok = True)
    text = yaml.safe_dump(
        data,
        sort_keys = False,
        allow_unicode = True,
        default_flow_style = False,
        width = 120,
    )
    out_path.write_text(text, encoding = "utf-8", newline = "\n")


def _serialize_entries(entries: Iterable[AllowlistEntry]) -> list[dict[str, Any]]:
    """Sort ``entries`` alphabetically by name and return a YAML-ready list.

    Metadata pairs on each entry are emitted as additional top-level keys
    after the three standard fields, in declaration order.
    """
    serialized: list[dict[str, Any]] = []
    for entry in sorted(entries, key = lambda e: e.name.lower()):
        item: dict[str, Any] = {
            "name": entry.name,
            "source_file": entry.source_file,
            "source_line": entry.source_line,
        }
        for key, value in entry.metadata:
            item[key] = value
        serialized.append(item)
    return serialized


def write_flat(
    result: ExtractionResult,
    out_dir: Path,
    *,
    source_label: str,
    generated_at: datetime | None = None,
) -> Path:
    """Write a single flat allowlist file, e.g. ``characters.yaml``.

    Returns the output path.
    """
    timestamp = _format_generated_at(generated_at)

    payload = {
        "source": source_label,
        "generated_at": timestamp,
        "values": _serialize_entries(result.entries),
    }

    out_path = out_dir / f"{result.category}.yaml"
    _dump_yaml(payload, out_path)
    return out_path


def write_per_character(
    result: ExtractionResult,
    out_dir: Path,
    *,
    source_label: str,
    generated_at: datetime | None = None,
) -> list[Path]:
    """Write one YAML file per character under ``out_dir / result.category / <Char>.yaml``.

    Entries with no :attr:`AllowlistEntry.subgroup` are serialised under a
    top-level ``values`` key. Entries with a ``subgroup`` are partitioned
    into separate lists keyed on the subgroup name (e.g. ``arms``,
    ``left_arm``, ``right_arm``). A character whose entries mix both styles
    gets both ``values`` and the subgroup keys side by side — this is
    uncommon but supported for flexibility.

    Additionally, when :attr:`ExtractionResult.entries` is populated
    (typically the "shared" pot in the moods extractor), a companion file
    ``<category>/_shared.yaml`` is emitted. Per-character files gain an
    ``inherits_from_shared: _shared.yaml`` pointer so consumers know how
    to assemble the complete list for one character.

    Returns the list of paths written.
    """
    timestamp = _format_generated_at(generated_at)
    category_dir = out_dir / result.category
    category_dir.mkdir(parents = True, exist_ok = True)

    paths: list[Path] = []

    has_shared = bool(result.entries)
    if has_shared:
        shared_payload: dict[str, Any] = {
            "source": source_label,
            "generated_at": timestamp,
            "values": _serialize_entries(result.entries),
        }
        shared_path = category_dir / "_shared.yaml"
        _dump_yaml(shared_payload, shared_path)
        paths.append(shared_path)

    for character, entries in sorted(result.per_character.items()):
        # Partition entries by subgroup.
        groups: dict[str, list[AllowlistEntry]] = {}
        for entry in entries:
            key = entry.subgroup if entry.subgroup else "values"
            groups.setdefault(key, []).append(entry)

        payload: dict[str, Any] = {
            "character": character,
            "source": source_label,
            "generated_at": timestamp,
        }
        if has_shared:
            payload["inherits_from_shared"] = "_shared.yaml"
        for group_name in sorted(groups):
            payload[group_name] = _serialize_entries(groups[group_name])

        out_path = category_dir / f"{character}.yaml"
        _dump_yaml(payload, out_path)
        paths.append(out_path)
    return paths
