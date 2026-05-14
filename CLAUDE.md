# TNH Scene Compiler — Project Instructions

## Overview

Fountain-TNH scene compiler: converts `.scene` files to Ren'Py `.rpy` scripts for The Null Hypothesis game. Three packages:
- `tnh_scene_compiler` — main compiler (CLI + GUI)
- `tnh_refresh_allowlists` — allowlist extraction from TNH source (characters, faces, moods, traits, personalities, history events, etc.)
- `tnh_generate_cheatsheet` — markdown cheatsheet generator

## Architecture

- **Config**: `tnh_scene_compiler.<prefix>.yaml`, loaded via `config.py`. Legacy `tnh_scene_compiler.yaml` supported.
- **Pipeline**: parse → DSL transform → validate → codegen.
- **Output**: pluggable callback system (`output.set_callback`) for CLI/GUI.
- **GUI**: Tkinter, wizard flow (Welcome → Quick/Project/Init screens), threaded compilation.
- **DSL**: `dsl.py` transforms writer-friendly syntax to canonical Ren'Py calls. Project aliases via `aliases.yaml`.
- **Condition Builder**: `condition_builder.py` — guided dialog for building `[[if]]` condition expressions. Pure-logic helpers (`build_condition`, `wrap_condition`) are testable without Tkinter.
- **New Scene Dialog**: `new_scene_dialog.py` — guided form for creating scenes with setup fields (title, character, scene type, trigger, location) and 4 example templates. Pure-logic helper (`build_scene_text`) testable without Tkinter.
- **Allowlists**: two-layer (base + project), loaded in `allowlists.py`, validated in `validator.py`.

## Naming Conventions

- `project_prefix` (not `mod_prefix`) — used everywhere in code, config, and YAML.
- `project_allowlists` (not `mod_allowlists`), `project_root` (not `mod_root`).
- Exception: `mod_operations` and `mod_set` are game engine terms and keep their names.

## Testing

- Framework: pytest
- 372 tests in `tests/`
- Run: `python -m pytest tests/ -q`

## Build

- PyInstaller: `pyinstaller tnh_scene_compiler.spec`
- Release: push a `v*` tag to trigger `.github/workflows/release.yml`
