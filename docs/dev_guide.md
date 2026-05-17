# Developer guide — running from source

This guide is for developers who run the compiler from source (not the
standalone app). It covers setup, CLI usage, submodule integration, and
release builds.

---

## Prerequisites

- Python 3.10+
- PyYAML (`pip install pyyaml`)
- An extracted TNH build (`.rpy` source files, not `.rpyc`) for
  allowlist refresh of the base game

Optional (for specific tasks):

- Pillow (`pip install Pillow`) for thumbnail generation
- PyInstaller (`pip install pyinstaller`) for building the standalone exe
- tkinterdnd2 (`pip install tkinterdnd2`) for GUI drag-and-drop support

---

## Setup

### Option A: Git submodule (recommended for mod repos)

Add the tool to your mod repository:

```bash
git submodule add https://github.com/Ethyl39/tnh-scene-compiler.git \
    Tools/tnh-scene-compiler
```

Make sure `PYTHONPATH` includes the submodule root before invoking:

```powershell
# PowerShell
$env:PYTHONPATH = "Tools/tnh-scene-compiler"
python -m tnh_scene_compiler compile --verbose
```

```bash
# Bash
export PYTHONPATH="Tools/tnh-scene-compiler"
python3 -m tnh_scene_compiler compile --verbose
```

To update the tool later:

```bash
git submodule update --remote Tools/tnh-scene-compiler
```

### Option B: Standalone clone

Clone the tool anywhere and point `PYTHONPATH` at it. No install step
needed beyond PyYAML.

```bash
git clone https://github.com/Ethyl39/tnh-scene-compiler.git
export PYTHONPATH="/path/to/tnh-scene-compiler"
```

### PYTHONPATH configuration

The package is not installed via pip. Every invocation requires that
`PYTHONPATH` includes the repository root (where the
`tnh_scene_compiler/` package directory lives). The convenience scripts
under `scripts/` set this automatically.

---

## CLI commands

### compile

Compiles `.scene` files to `.rpy`:

```bash
python -m tnh_scene_compiler compile --verbose
```

Without file arguments, discovers all `.scene` files under the
configured `scenes_source/` directory (excluding `_allowlists/`).

Compile specific files:

```bash
python -m tnh_scene_compiler compile scenes_source/JeanGrey/my_scene.scene
```

### validate

Parse and validate without writing output. Same error reporting as
compile:

```bash
python -m tnh_scene_compiler validate --verbose
```

Useful for CI or pre-commit checks. Exit code 0 = valid, 1 = errors.

### init

Bootstrap a new project config and runtime stubs:

```bash
python -m tnh_scene_compiler init --mod-prefix my_mod
```

Creates:

| File                       | Purpose                                          |
| -------------------------- | ------------------------------------------------ |
| `tnh_scene_compiler.yaml`  | Project config (edit paths to match your layout) |
| `runtime_stub.rpy`         | Runtime module for scene state injection         |
| `metadata_init.rpy`        | Empty metadata dict populated at boot            |
| `testing_eval.rpy`         | Condition wrapper for the testing hub            |

### GUI

Launch the graphical editor/compiler:

```bash
python -m tnh_scene_compiler.gui
```

---

## Refreshing allowlists from CLI

Regenerate YAML allowlists from the TNH base game and mod source:

```bash
python -m tnh_refresh_allowlists \
  --base-game ../TheNullHypothesis \
  --out scenes_source/_allowlists \
  --verbose
```

The `refresh` section of `tnh_scene_compiler.yaml` provides default
paths:

```yaml
refresh:
  base_game: ../TheNullHypothesis/
  mod_root: MyMod/
```

Convenience batch script: `scripts/refresh-allowlists.bat` (sets
`PYTHONPATH` and passes arguments through).

---

## Generating cheatsheet from CLI

Regenerate the writer-facing cheatsheet from the current allowlists:

```bash
python -m tnh_generate_cheatsheet \
  --allowlists scenes_source/_allowlists \
  --out Docs/Authoring_Cheatsheet.md
```

Convenience batch script: `scripts/generate-cheatsheet.bat`.

---

## Drag-and-drop via scripts/compile.bat

Drop `.scene` files onto `scripts/compile.bat` (Windows) or run
`scripts/compile.sh` (Linux/macOS) to compile without typing the full
command. Double-clicking without arguments compiles the full project.

These scripts auto-discover Python, set `PYTHONPATH`, and invoke the
compiler with `--verbose`.

---

## Importing thumbnails

Generate face/arm thumbnails from the TNH-VisualReference checkout:

```bash
python scripts/import_thumbnails.py
```

By default reads from `external/TNH-VisualReference`. Pass an explicit
path to override:

```bash
python scripts/import_thumbnails.py path/to/TNH-VisualReference
```

Requires Pillow. The script also generates FX effect thumbnails from
`effects/_fx_mapping.yaml`.

Convenience batch script: `scripts/import-thumbnails.bat`.

---

## Building a release

The release build script automates the full packaging pipeline:

```bash
python scripts/build_release.py
```

Steps performed:

1. Cleans `dist/` and `build/` directories
2. Generates thumbnails if missing or stale
3. Runs PyInstaller to produce the standalone executable
4. Packages `thumbnails.zip` as a separate archive
5. Copies `docs/` into the release folder (excludes `dev_guide.md`)

Output: `dist/TNHSceneCompiler-<version>/`. The folder is
self-contained and ready to distribute.

---

## Wrapper script example (PowerShell)

For mod repos that use the submodule, a thin wrapper integrates the
compiler into the build pipeline:

```powershell
param(
    [switch]$Verbose
)

$toolRoot = Join-Path $PSScriptRoot "tnh-scene-compiler"
$env:PYTHONPATH = $toolRoot

$args = @("compile")
if ($Verbose) { $args += "--verbose" }

python -m tnh_scene_compiler @args
exit $LASTEXITCODE
```

---

## CI integration

Example GitHub Actions step for scene validation:

```yaml
- name: Validate scenes
  run: |
    pip install pyyaml
    export PYTHONPATH=Tools/tnh-scene-compiler
    python -m tnh_scene_compiler validate
```

Exit code 0 = all scenes valid, 1 = errors found.

The repository ships a release workflow at
`.github/workflows/release.yml` triggered on `v*` tags. It builds the
exe on Windows and Linux, generates thumbnails, and publishes a GitHub
release with artifacts.

---

## Running tests

The test suite uses pytest:

```bash
python -m pytest tests/ -q
```

Fixtures live under `tests/fixtures/`. Tests cover the lexer, parser,
expression parser, parenthetical parser, directive parser, validator,
codegen, and end-to-end compilation.
