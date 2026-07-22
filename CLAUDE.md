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
- **Condition Builder**: `condition_builder.py` — guided dialog for building `[[if]]` condition expressions from any number of clauses (each after the first joined with and/or via its own operator; "+ Add condition" / "Remove"). Per-clause UI lives in `_ConditionClausePanel`, whose type selector is two-level (Category -> Condition) built from `build_condition_catalog` (built-in checks + allowlist functions grouped/labelled; a promoted function jumps straight to its param form). The dialog holds a scrollable list of clauses. Pure-logic helpers (`build_condition`, `build_condition_catalog`, `join_conditions`, `resolve_method_path`, `wrap_condition`) are testable without Tkinter.
- **New Scene Dialog**: `new_scene_dialog.py` — guided form for creating scenes with setup fields (title, character, scene type, trigger, location) and 4 example templates. Pure-logic helper (`build_scene_text`) testable without Tkinter.
- **Glossary**: `glossary.py` — a non-modal reference window (editor toolbar "Glossary" button) with a searchable section list + copyable code examples, parsed at runtime from the bundled `docs/glossary/*.md` files (one per top-level section, numbered for order; read in name order, concatenated, then parsed). Prose/notes render in a read-only `Text` widget so inline `[label](#section-slug)` cross-reference links are clickable (jump to that section). Pure parser (`parse_glossary`) + `slugify` / `parse_inline_links` testable without Tkinter; the glossary folder is in the `.spec` datas.
- **Allowlists**: two-layer (base + project), loaded in `allowlists.py`, validated in `validator.py`.
- **Allowlist browser**: `allowlist_browser.py` — a non-modal window (buttons on `ProjectScreen`, `QuickScreen`, and the editor toolbar). Callers without a `Config` (quick mode) pass `default_base_dir()` and `project_dir=None`, so the window is base-only and read-only there.
  - **Two axes, do not conflate them.** *Origin* (`ORIGIN_CORE` / `ORIGIN_PROJECT`) is per **value** and drives the sidebar split and editability (`is_editable_in` — the project side is always editable, the core side never). *Maintenance* is per **file** and is purely informational: `survives_refresh` decides whether saving warns. They cross freely — `condition_functions.yaml` is refresh-safe yet holds game-origin values from the base layer.
  - **Do not re-lock the generated files.** `tnh_refresh_allowlists` needs an extracted base game; a project that cannot run it has no other way to fill an allowlist, and the compiler's `merge()` carries every field (including `character_methods` / `character_properties`, which have no extractor at all). The overwrite risk is surfaced — inline warning plus a one-per-list `askokcancel` on save, tracked in `_warned_keys` — not prevented.
  - `classify_origin` is the rule: base layer → always core; project layer → compare the entry's `source_file` root against `base_game_root` / `project_root` from that layer's `_meta.yaml`, with `_CORE_SENTINEL_ROOTS` (`<builtin>`, `game`) counting as core and anything unplaceable (no source, `manual`) falling to project. A generated file legitimately holds both.
  - `ALLOWLIST_TOPICS` is the catalogue; `maintenance` is `generated` (rewritten by `tnh_refresh_allowlists`), `manual` (the 5 files the refresh preserves — assert-locked by a test against `_MANUAL_SCAFFOLDS`), or `developer` (hand-maintained in the base layer). `is_editable_in(origin)` is the only editability gate; `blurb(origin)` is the per-side explanation.
  - Editing is raw YAML so the files' hand-written header comments survive a save (a `safe_load`/`safe_dump` round-trip would delete them), gated by `validate_topic_yaml`.
  - **Performance is load-bearing here** — a full read is ~100 YAML files and the sidebar needs it at open. Three things keep it at ~180 ms: the libyaml `CSafeLoader` (7x, with an `ImportError` fallback), `_META_CACHE` (`_meta.yaml` was over half of all parses), and `_groups` reading each list once and splitting both sides in memory. Do not reintroduce a per-origin read. `Reload` drops `_groups_cache`, `_name_index`, and the meta cache.
  - Pure helpers (`classify_origin`, `read_layer_meta`, `load_topic`, `read_layer`, `topic_characters`, `topic_path`, `validate_topic_yaml`) are testable without Tkinter.

## Naming Conventions

- `project_prefix` (not `mod_prefix`) — used everywhere in code, config, and YAML.
- `project_allowlists` (not `mod_allowlists`), `project_root` (not `mod_root`).

## Testing

- Framework: pytest
- 623 tests in `tests/`
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
