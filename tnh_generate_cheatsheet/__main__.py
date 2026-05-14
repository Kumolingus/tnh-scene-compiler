"""Command-line entry for ``python -m tnh_generate_cheatsheet``.

Reads the YAML allowlists produced by ``tnh_refresh_allowlists`` and rewrites
``Docs/Authoring_Cheatsheet.md`` in place. Safe to re-run: output is
deterministic, so a no-op run produces an identical file modulo the
``{{generated_at}}`` field.

Exit codes:

* 0 — success.
* 1 — unrecoverable error (missing allowlists directory, template missing,
  write failure).
* 2 — ``--check`` mode: generated output differs from the existing file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .loader import load
from .renderer import render


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog = "tnh_generate_cheatsheet",
        description = "Regenerate Docs/Authoring_Cheatsheet.md from the YAML allowlists.",
    )
    parser.add_argument(
        "--allowlists",
        type = Path,
        required = True,
        help = "Directory holding the generated YAML allowlists.",
    )
    parser.add_argument(
        "--output",
        type = Path,
        required = True,
        help = "Destination markdown file.",
    )
    parser.add_argument(
        "--check",
        action = "store_true",
        help = "Do not write. Exit 2 if the generated content differs from the existing file.",
    )
    parser.add_argument(
        "--verbose",
        action = "store_true",
        help = "Print loader warnings and per-category counts to stderr.",
    )
    return parser.parse_args(argv)


def _log_verbose(data, stream) -> None:
    """Print counts and warnings. ``stream`` is a file-like object so tests can capture output."""
    print(f"tnh_generate_cheatsheet: source_label={data.source_label or 'unknown'}", file = stream)
    print(f"  characters: {len(data.characters)}", file = stream)
    print(f"  stages: {len(data.stages)}", file = stream)
    print(f"  locations: {len(data.locations)}", file = stream)
    print(f"  sfx: {len(data.sfx)}", file = stream)
    print(f"  looks: {len(data.looks)}", file = stream)
    print(f"  shared_moods: {len(data.shared_moods)}", file = stream)
    print(f"  interpolation: {len(data.interpolation)}", file = stream)
    print(f"  condition_functions: {len(data.condition_functions)}", file = stream)
    print(f"  per_character: {len(data.per_character)} characters", file = stream)
    for warning in data.warnings:
        print(f"  warning: {warning}", file = stream)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    allowlists = args.allowlists.resolve()
    output = args.output.resolve()

    if not allowlists.is_dir():
        print(
            f"tnh_generate_cheatsheet: allowlists directory not found at {allowlists}",
            file = sys.stderr,
        )
        return 1

    data = load(allowlists)
    if args.verbose:
        _log_verbose(data, sys.stderr)

    try:
        rendered = render(data)
    except FileNotFoundError as exc:
        print(f"tnh_generate_cheatsheet: template missing: {exc}", file = sys.stderr)
        return 1

    if args.check:
        existing = output.read_text(encoding = "utf-8") if output.is_file() else ""
        if existing == rendered:
            print("tnh_generate_cheatsheet: up to date")
            return 0
        print(
            "tnh_generate_cheatsheet: output differs from existing file "
            f"({output}) — run without --check to update.",
            file = sys.stderr,
        )
        return 2

    output.parent.mkdir(parents = True, exist_ok = True)
    output.write_text(rendered, encoding = "utf-8", newline = "\n")
    print(f"tnh_generate_cheatsheet: wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
