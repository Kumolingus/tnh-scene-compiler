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

## Testing

- Framework: pytest
- 398 tests in `tests/`
- Run: `python -m pytest tests/ -q`

## Thumbnails

- **Import**: `python scripts/import_thumbnails.py <path-to-TNH-VisualReference>` reads face/arm PNGs, resizes via Pillow, outputs to `thumbnails/` with `_mapping.yaml`.
- **Runtime**: `tnh_scene_compiler/thumbnails.py` — `ThumbnailStore` singleton, lazy-cached `tk.PhotoImage` objects. No Pillow at runtime.
- **GUI**: previews in `_CharacterInsertDialog` (column 2), `_DirectiveDialog._build_show` (column 2), `_PaletteSidebar._refresh_visuals` (compound buttons for Faces/Arms).
- **Settings**: `show_thumbnails: bool` in `AppSettings` (default `True`).
- **Bundle**: `thumbnails/` included in PyInstaller `datas` in `.spec`.
- **Mapping keys**: face names match allowlist names; arm keys are prefixed with `both_`/`left_`/`right_`.
- **Fuzzy matching**: the import script handles typos in source filenames (e.g. `appaled` → `appalled`).

## Build

- PyInstaller: `pyinstaller tnh_scene_compiler.spec`
- Release: push a `v*` tag to trigger `.github/workflows/release.yml`
