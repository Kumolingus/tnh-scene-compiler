"""Command-line entry for ``python -m tnh_scene_compiler``.

Subcommands
-----------
compile   Compile ``.scene`` files to ``.rpy``.
validate  Parse + validate without writing output.
init      Bootstrap a new mod project (config + runtime stubs).

Exit codes:

* 0 — success.
* 1 — one or more scenes failed.
* 2 — setup error (config missing, bad paths).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from .allowlists import Allowlists
from .ast_nodes import Scene
from .codegen import CodegenContext, generate, generate_events_rpy
from .config import Config, ConfigError, config_filename, find_config, get_data_root, load_config
from .errors import CompileError
from . import output as out
from .parser import parse
from .validator import validate


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(
        prog="tnh_scene_compiler",
        description="Fountain-TNH scene compiler for The Null Hypothesis.",
    )
    sub = top.add_subparsers(dest="command")

    # -- compile ------------------------------------------------------------
    p_compile = sub.add_parser(
        "compile",
        help="Compile .scene files to .rpy.",
    )
    p_compile.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Specific .scene files to compile (omit to compile all).",
    )
    _add_common_args(p_compile)

    # -- validate -----------------------------------------------------------
    p_validate = sub.add_parser(
        "validate",
        help="Parse and validate without writing output.",
    )
    p_validate.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Specific .scene files to validate (omit to validate all).",
    )
    _add_common_args(p_validate)

    # -- init ---------------------------------------------------------------
    p_init = sub.add_parser(
        "init",
        help="Bootstrap a new mod project.",
    )
    p_init.add_argument(
        "--mod-prefix",
        required=True,
        help="Mod prefix (e.g. 'my_romance_mod').",
    )
    p_init.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Directory to write generated files into (default: current dir).",
    )

    return top


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to tnh_scene_compiler.<prefix>.yaml (default: auto-discover).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print one line per compiled scene.",
    )


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------

def resolve_config(
    config_path: Path | None,
    start: Path | None = None,
) -> Config:
    """Find and load the config file, or raise ``ConfigError``."""
    if config_path is None:
        if start is None:
            start = Path.cwd()
        config_path = find_config(start)
    if config_path is None:
        raise ConfigError(
            "No tnh_scene_compiler.*.yaml found. "
            "Run 'tnh_scene_compiler init' or pass --config."
        )
    return load_config(config_path)


def _resolve_config(args: argparse.Namespace) -> Config:
    """CLI wrapper: resolve config or exit."""
    start = Path.cwd()
    if hasattr(args, "files") and args.files:
        start = args.files[0].resolve().parent
    try:
        return resolve_config(args.config, start)
    except ConfigError as exc:
        out.error(str(exc))
        sys.exit(2)


def build_allowlists(cfg: Config) -> Allowlists:
    """Layer base + mod allowlists per config. Raises ``ConfigError``."""
    dirs: list[Path] = []
    base = cfg.base_allowlists_dir
    if base is not None:
        dirs.append(base)
    if cfg.project_allowlists.is_dir():
        dirs.append(cfg.project_allowlists)

    if not dirs:
        raise ConfigError("No allowlists directories found (neither base nor mod).")

    return Allowlists.load_layered(dirs)


def _build_allowlists(cfg: Config) -> Allowlists:
    """CLI wrapper: build allowlists or exit."""
    try:
        return build_allowlists(cfg)
    except ConfigError as exc:
        out.error(str(exc))
        sys.exit(2)


# ---------------------------------------------------------------------------
# Scene discovery
# ---------------------------------------------------------------------------

def iter_scene_files(root: Path) -> Iterable[Path]:
    """Yield every ``.scene`` file under *root* except the ``_allowlists/`` tree."""
    for path in sorted(root.rglob("*.scene")):
        if "_allowlists" in path.parts:
            continue
        yield path


# ---------------------------------------------------------------------------
# Compilation core
# ---------------------------------------------------------------------------

def compile_one(
    source: Path,
    allow: Allowlists,
    ctx: CodegenContext,
    *,
    repo_root: Path,
) -> tuple[Scene | None, str, list[CompileError]]:
    """Compile one ``.scene`` file.  Returns ``(scene, rpy_text, errors)``."""
    try:
        display_path = source.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        display_path = source.as_posix()

    text = source.read_text(encoding="utf-8")
    try:
        scene = parse(text, path=display_path)
    except CompileError as exc:
        return (None, "", [exc])

    errors = validate(scene, allow)
    if errors:
        return (scene, "", errors)

    return (scene, generate(scene, allow, ctx), [])


# ---------------------------------------------------------------------------
# Subcommand: compile
# ---------------------------------------------------------------------------

def _cmd_compile(args: argparse.Namespace) -> int:
    cfg = _resolve_config(args)
    allow = _build_allowlists(cfg)
    ctx = CodegenContext(project_prefix=cfg.project_prefix)
    repo_root = cfg.config_dir

    if args.files:
        sources = args.files
    else:
        if not cfg.scenes_source.is_dir():
            out.error(f"Scenes source not found: {cfg.scenes_source}")
            return 2
        sources = list(iter_scene_files(cfg.scenes_source))

    if not sources:
        out.warning("No .scene files found.")
        return 0

    out.header(f"Compiling {len(sources)} scene(s)...")

    total = 0
    written = 0
    had_errors = False
    compiled_scenes: list[Scene] = []

    for source in sources:
        total += 1
        scene, rpy, errors = compile_one(source, allow, ctx, repo_root=repo_root)
        if errors:
            had_errors = True
            for err in errors:
                out.compile_error_detail(err.format_for_user())
            continue

        assert scene is not None
        target_dir = cfg.output / scene.title_page.character
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / (source.stem + ".rpy")
        target_path.write_text(rpy, encoding="utf-8", newline="\n")
        written += 1
        compiled_scenes.append(scene)
        if args.verbose:
            out.success(target_path.name)

    if not had_errors:
        cfg.output.mkdir(parents=True, exist_ok=True)
        events_path = cfg.output / "_events.rpy"
        events_path.write_text(
            generate_events_rpy(compiled_scenes, ctx),
            encoding="utf-8",
            newline="\n",
        )
        if args.verbose:
            cinematic_count = sum(
                1 for s in compiled_scenes if s.title_page.scene_type == "cinematic"
            )
            out.info(f"Events registry: {cinematic_count} cinematic entries -> {events_path.name}")

    out.summary(written, total, had_errors)
    return 1 if had_errors else 0


# ---------------------------------------------------------------------------
# Subcommand: validate
# ---------------------------------------------------------------------------

def _cmd_validate(args: argparse.Namespace) -> int:
    cfg = _resolve_config(args)
    allow = _build_allowlists(cfg)
    repo_root = cfg.config_dir

    if args.files:
        sources = args.files
    else:
        if not cfg.scenes_source.is_dir():
            out.error(f"Scenes source not found: {cfg.scenes_source}")
            return 2
        sources = list(iter_scene_files(cfg.scenes_source))

    if not sources:
        out.warning("No .scene files found.")
        return 0

    out.header(f"Validating {len(sources)} scene(s)...")

    total = 0
    valid = 0
    had_errors = False

    for source in sources:
        total += 1
        try:
            display_path = source.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            display_path = source.as_posix()

        text = source.read_text(encoding="utf-8")
        try:
            scene = parse(text, path=display_path)
        except CompileError as exc:
            had_errors = True
            out.compile_error_detail(exc.format_for_user())
            continue

        errors = validate(scene, allow)
        if errors:
            had_errors = True
            for err in errors:
                out.compile_error_detail(err.format_for_user())
        else:
            valid += 1
            if args.verbose:
                out.success(source.name)

    out.summary(valid, total, had_errors)
    return 1 if had_errors else 0


# ---------------------------------------------------------------------------
# Subcommand: init
# ---------------------------------------------------------------------------

def _cmd_init(args: argparse.Namespace) -> int:
    project_prefix = args.project_prefix
    output_dir = args.output_dir.resolve()

    out.header(f"Initializing mod project with prefix '{project_prefix}'...")

    config_path = output_dir / config_filename(project_prefix)
    if config_path.exists():
        out.warning(f"Config already exists: {config_path}")
    else:
        config_path.write_text(
            _INIT_CONFIG_TEMPLATE.format(project_prefix=project_prefix),
            encoding="utf-8",
            newline="\n",
        )
        out.success(f"Created {config_path.name}")

    templates_dir = get_data_root() / "templates"
    if not templates_dir.is_dir():
        out.warning("Templates directory not found — skipping runtime stubs.")
        return 0

    for tmpl_file in sorted(templates_dir.glob("*.tmpl")):
        content = tmpl_file.read_text(encoding="utf-8")
        content = content.replace("{{project_prefix}}", project_prefix)
        out_name = tmpl_file.stem
        out_path = output_dir / out_name
        if out_path.exists():
            out.warning(f"Already exists: {out_name}")
        else:
            out_path.write_text(content, encoding="utf-8", newline="\n")
            out.success(f"Created {out_name}")

    out.info("Done. Move the .rpy stubs into your mod's game/ directory.")
    return 0


_INIT_CONFIG_TEMPLATE = """\
# tnh_scene_compiler.{project_prefix}.yaml — configuration for the Fountain-TNH compiler.

# REQUIRED: your project's unique prefix.
project_prefix: {project_prefix}

# Directory containing .scene source files (relative to this file).
scenes_source: scenes_source/

# Project-specific allowlists (relative to this file).
project_allowlists: scenes_source/_allowlists/

# Output directory for compiled .rpy files (relative to this file).
output: game/{project_prefix}/scenes/

# Include the base TNH allowlists shipped with the compiler.
include_base_allowlists: true

# Optional: paths for the allowlist-refresh tool.
# refresh:
#   base_game: ../TheNullHypothesis/
#   project_root: .
"""


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    dispatch = {
        "compile": _cmd_compile,
        "validate": _cmd_validate,
        "init": _cmd_init,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 2

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
