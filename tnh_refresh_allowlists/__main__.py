"""Command-line entry for ``python -m tnh_refresh_allowlists``.

Extractors are split in two groups:

* flat extractors emit a single ``<category>.yaml`` (characters, stages, sfx);
* per-character extractors emit one file per character under
  ``<category>/<Character>.yaml`` (faces, poses, arms, outfits).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .extractors import (
    arms,
    characters,
    condition_functions,
    faces,
    history_events,
    interpolation,
    locations,
    looks,
    moods,
    outfits,
    personalities,
    poses,
    sfx,
    stages,
    traits,
)
from .models import ExtractionResult, ScanContext
from .writer import write_flat, write_per_character


_Extractor = Callable[[ScanContext], ExtractionResult]

_FLAT_EXTRACTORS: tuple[_Extractor, ...] = (
    characters.extract,
    stages.extract,
    sfx.extract,
    locations.extract,
    looks.extract,
    interpolation.extract,
    condition_functions.extract,
    traits.extract,
    personalities.extract,
    history_events.extract,
)

_PER_CHARACTER_EXTRACTORS: tuple[_Extractor, ...] = (
    faces.extract,
    poses.extract,
    arms.extract,
    outfits.extract,
    moods.extract,
)


_MANUAL_SCAFFOLDS: tuple[tuple[str, str], ...] = (
    (
        "locations_overrides.yaml",
        "# Manual overrides for slugline -> location_id mapping.\n"
        "# Entries here win over the auto-generated locations.yaml.\n"
        "# Delete an entry to revert to auto.\n"
        "overrides: []\n",
    ),
    (
        "interpolation_custom.yaml",
        "# Project-specific interpolation paths the Fountain-TNH compiler\n"
        "# should accept inside [...]. The compiler merges this list with\n"
        "# the auto-generated interpolation.yaml.\n"
        "# Each entry is a dotted path; no expressions, no calls.\n"
        "paths: []\n",
    ),
    (
        "condition_functions.yaml",
        "# Functions callable from [[if]] expressions inside a .scene file.\n"
        "# Every entry is an explicit contract: adding a function here exposes\n"
        "# it to non-dev writers, and the mod commits to keeping its signature\n"
        "# stable across releases.\n"
        "#\n"
        "# Example:\n"
        "# functions:\n"
        "#   - name: check_approval\n"
        "#     signature: \"check_approval(Character, threshold: str) -> bool\"\n"
        "#     source_file: TheNullHypothesis/game/core/mechanics/approval.rpy\n"
        "functions: []\n",
    ),
    (
        "run_operations.yaml",
        "# Operations callable from [[run]] inside a .scene file.\n"
        "# These write persistent state (Character traits, History, mod\n"
        "# attributes) and must be hand-maintained: adding an entry here\n"
        "# exposes the helper to non-dev writers, and the mod commits to\n"
        "# keeping its signature stable across releases.\n"
        "#\n"
        "# Each entry's ``name`` is matched against the call target used in\n"
        "# [[run]] — either the bare function name (``mymod_set_stage``)\n"
        "# or the final attribute of a dotted method chain\n"
        "# (``JeanGrey.give_trait(\"x\")`` matches ``give_trait``).\n"
        "#\n"
        "# Example:\n"
        "# operations:\n"
        "#   - name: give_trait\n"
        "#     signature: \"<Character>.give_trait(trait_name: str)\"\n"
        "#     source_file: TheNullHypothesis/game/core/base/character.rpy\n"
        "operations: []\n",
    ),
)


def _ensure_manual_scaffolds(out: Path) -> int:
    """Create stub manual files on first run; leave existing files untouched."""
    written = 0
    out.mkdir(parents = True, exist_ok = True)
    for filename, content in _MANUAL_SCAFFOLDS:
        path = out / filename
        if path.exists():
            continue
        path.write_text(content, encoding = "utf-8", newline = "\n")
        written += 1
    return written


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog = "tnh_refresh_allowlists",
        description = "Scan TNH + mod sources and emit YAML allowlists.",
    )
    parser.add_argument("--base-game", type = Path, default = Path("./TheNullHypothesis/"))
    parser.add_argument("--mod", type = Path, default = Path("./PregnancyMod/"))
    parser.add_argument("--out", type = Path, default = Path("./scenes_source/_allowlists/"))
    parser.add_argument("--no-include-tnh", dest = "include_tnh", action = "store_false")
    parser.add_argument("--repo-root", type = Path, default = Path.cwd())
    parser.add_argument("--dry-run", action = "store_true")
    parser.add_argument("--verbose", action = "store_true")
    return parser.parse_args(argv)


def _source_label(include_tnh: bool) -> str:
    return "TNH + Mod" if include_tnh else "Mod"


def _write_meta(
    out_dir: Path,
    *,
    context: ScanContext,
    results: list[ExtractionResult],
    generated_at: datetime,
) -> Path:
    """Write ``_meta.yaml`` summarising the run."""
    stats: dict[str, int | dict[str, int]] = {}
    warnings: list[str] = []
    for result in results:
        if result.per_character:
            stats[result.category] = {char: len(entries) for char, entries in result.per_character.items()}
        else:
            stats[result.category] = len(result.entries)
        for warning in result.warnings:
            warnings.append(warning.message)

    payload = {
        # Date-only: multiple refreshes in the same day keep the YAML
        # byte-identical, so the allowlist diffs never flip just
        # because the timestamp moved forward by a few minutes.
        "generated_at": generated_at.date().isoformat(),
        "tool_version": "1.0.0",
        "base_game_root": context.relative(context.base_game_root),
        "project_root": context.relative(context.project_root),
        "include_tnh": context.include_tnh,
        "stats": stats,
        "warnings": warnings,
    }

    out_path = out_dir / "_meta.yaml"
    out_dir.mkdir(parents = True, exist_ok = True)
    out_path.write_text(
        yaml.safe_dump(payload, sort_keys = False, allow_unicode = True, default_flow_style = False),
        encoding = "utf-8",
        newline = "\n",
    )
    return out_path


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    base_game = args.base_game.resolve()
    mod = args.mod.resolve()
    out = args.out.resolve()
    repo_root = args.repo_root.resolve()

    if not base_game.exists():
        print(f"tnh_refresh_allowlists: base-game root not found at {base_game}", file = sys.stderr)
        return 1
    if not mod.exists():
        print(f"tnh_refresh_allowlists: mod root not found at {mod}", file = sys.stderr)
        return 1

    context = ScanContext(
        base_game_root = base_game,
        project_root = mod,
        repo_root = repo_root,
        include_tnh = args.include_tnh,
    )

    generated_at = datetime.now(timezone.utc)
    source_label = _source_label(args.include_tnh)

    flat_results: list[ExtractionResult] = []
    for extractor in _FLAT_EXTRACTORS:
        result = extractor(context)
        flat_results.append(result)
        if args.verbose:
            print(f"  {result.category}: {len(result.entries)} entries, {len(result.warnings)} warnings")

    per_character_results: list[ExtractionResult] = []
    for extractor in _PER_CHARACTER_EXTRACTORS:
        result = extractor(context)
        per_character_results.append(result)
        if args.verbose:
            total_entries = sum(len(entries) for entries in result.per_character.values())
            print(
                f"  {result.category}: {len(result.per_character)} characters, "
                f"{total_entries} entries, {len(result.warnings)} warnings",
            )

    characters_result = next((r for r in flat_results if r.category == "characters"), None)
    real_characters = [
        entry
        for entry in (characters_result.entries if characters_result else [])
        if entry.source_file != "<builtin>"
    ]
    if not real_characters:
        print("tnh_refresh_allowlists: no characters discovered — aborting", file = sys.stderr)
        return 1

    if args.dry_run:
        print("tnh_refresh_allowlists: dry-run summary")
        for result in flat_results:
            print(f"  {result.category}: {len(result.entries)} entries")
        for result in per_character_results:
            total = sum(len(entries) for entries in result.per_character.values())
            print(f"  {result.category}: {len(result.per_character)} characters, {total} entries")
        return 0

    files_written = 0
    for result in flat_results:
        # Skip extractors that exist only to own a manual scaffold (their
        # ExtractionResult is always empty by contract).
        if not result.entries and result.category in ("condition_functions",):
            continue
        write_flat(result, out, source_label = source_label, generated_at = generated_at)
        files_written += 1
    for result in per_character_results:
        paths = write_per_character(result, out, source_label = source_label, generated_at = generated_at)
        files_written += len(paths)

    files_written += _ensure_manual_scaffolds(out)

    all_results = flat_results + per_character_results
    _write_meta(out, context = context, results = all_results, generated_at = generated_at)
    files_written += 1

    print(f"tnh_refresh_allowlists: wrote {files_written} files to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
