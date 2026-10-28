# TNH Scene Compiler — Project Instructions

## Overview

Fountain-TNH scene compiler: converts `.scene` files to Ren'Py `.rpy` scripts for The Null Hypothesis game. Three packages:
- `tnh_scene_compiler` — main compiler (CLI + GUI)
- `tnh_refresh_allowlists` — allowlist extraction from TNH source (characters, faces, moods, traits, personalities, history events, etc.)
- `tnh_generate_cheatsheet` — markdown cheatsheet generator

The tool serves every TNH mod creator, not one mod: no rule here encodes a particular mod's workflow, and the docs, messages and examples stay free of any one mod's content.

## Commands

- Tests: `python -m pytest tests/ -q` — 1000 tests, **0 skipped**: read both numbers.
- CLI (`compile`, `validate`, `init`), GUI, allowlist refresh, cheatsheet, thumbnail import, release build: `docs/dev_guide.md`.
- Build: `pyinstaller tnh_scene_compiler.spec`. Release: push a `v*` tag to trigger `.github/workflows/release.yml`.
- Thumbnails are not bundled in the exe: `scripts/build_release.py` ships `thumbnails.zip`, to unzip next to the exe after every build (the script wipes `dist/`).

## Architecture

- **Pipeline**: parse → DSL transform (`dsl.py`, project aliases in `aliases.yaml`) → validate (`validator.py`) → codegen (`codegen.py`). Config `tnh_scene_compiler.<prefix>.yaml`, loaded by `config.py`.
- **Allowlists**: two layers, `allowlists_base/` (the game) and the project's own, merged in memory only. Anything that reports what a writer may type reads both layers.
- **GUI**: Tkinter. Pure-logic helpers stay testable without Tk. UI preferences live in `AppSettings` (`settings.py`, stored in `%APPDATA%`) with a control in `_SettingsDialog`, never in the project config.

Before changing a module, read its section in `docs/design_notes.md`: `Target`, overridable condition calls, the `[[if]]` grammar, the Condition Builder, the New Scene Dialog and Glossary, allowlists (core and project layers, `include_tnh`, sluglines), modeless windows, the allowlist browser, naming, tests, thumbnails.

## Rules that cross modules

- The `[[if]]` grammar (`expr_parser.py`) and §11.9.1 of the mod repo's `Docs/TNH_Modding/11_dialogue_authoring.md` change together: the doc is the writer-facing contract. Likewise `docs/glossary/` and `docs/integration_guide.md`.
- Renderers put parentheses back from `precedence()` / `parenthesize()`, the single source of truth. A string assertion cannot catch a flattened expression: `tests/test_expr_precedence.py` re-parses the output with Python's `ast`.
- A Condition Builder widget's output must compile: `tests/test_condition_builder_roundtrip.py` runs every catalog entry through `parse` + `validate`.
- Naming: `project_prefix`, `project_allowlists`, `project_root` — never `mod_*` — including the `{{project_prefix}}` template placeholder (`tests/test_init_project.py`).

## Tests

- A test may not withdraw itself from a passing run (`tests/test_no_silent_skips.py`): every `pytest.skip` is listed in `_SANCTIONED_SKIPS` with its reason, missing or misshapen data fails with a message naming what to regenerate, and no test ends with an early `return`.
- Tk tests use the session-scoped `tk_root` fixture of `conftest.py`, never a module-scoped one (`test_tk_fixture_discipline.py`). A Tk failure fails the run.
