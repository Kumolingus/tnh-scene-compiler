# Modder setup guide

How to integrate `tnh-scene-compiler` into your TNH mod project.

## Prerequisites

- Python 3.10+
- PyYAML (`pip install pyyaml`)
- An extracted TNH build (`.rpy` source files, not `.rpyc`)

## Option A: Git submodule (recommended)

Add the tool to your mod repo:

```bash
git submodule add https://github.com/Ethyl39/tnh-scene-compiler.git Tools/tnh-scene-compiler
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

## Option B: Standalone clone

Clone the tool anywhere and point `PYTHONPATH` at it. No install step
needed beyond PyYAML.

## Initial setup

### 1. Bootstrap config and runtime stubs

From your mod repo root:

```bash
python -m tnh_scene_compiler init --mod-prefix my_mod
```

This creates:

| File | Purpose |
|---|---|
| `tnh_scene_compiler.yaml` | Project config — edit paths to match your layout |
| `runtime_stub.rpy` | Runtime module for scene state injection |
| `metadata_init.rpy` | Empty metadata dict populated at boot by compiled scenes |
| `testing_eval.rpy` | Condition wrapper for the testing hub |

### 2. Edit the config

Open `tnh_scene_compiler.yaml` and adjust:

```yaml
mod_prefix: my_mod

# Where your .scene source files live.
scenes_source: scenes_source/

# Where your mod-specific allowlist extensions live.
mod_allowlists: scenes_source/_allowlists/

# Where compiled .rpy files go (inside your mod's game/ tree).
output: MyMod/game/my_mod/scenes/

# Use the vanilla TNH allowlists shipped with the tool.
include_base_allowlists: true
```

### 3. Move the runtime stubs

Move the three `.rpy` stubs into your mod's `game/` directory so Ren'Py
loads them at boot:

```
MyMod/game/my_mod/my_mod_runtime.rpy      ← runtime_stub.rpy
MyMod/game/my_mod/my_mod_metadata.rpy     ← metadata_init.rpy
MyMod/game/my_mod/my_mod_testing_eval.rpy ← testing_eval.rpy
```

Rename them to match your mod prefix. These files are generated once
and committed to your repo — the compiler does not regenerate them.

### 4. Create your scenes directory

```
scenes_source/
├── _allowlists/       ← mod-specific allowlist extensions (optional)
├── JeanGrey/          ← one directory per character
│   └── my_mod_dialogue_jeangrey_greeting.scene
├── Rogue/
└── LauraKinney/
```

## Allowlist configuration

### How allowlists work

The compiler validates every identifier in your `.scene` files (character
names, moods, faces, locations, SFX, interpolation paths, etc.) against
YAML allowlists. Unknown values produce a compile error with a "did you
mean?" suggestion.

### Two-layer architecture

1. **Base layer** — vanilla TNH data, ships in `allowlists_base/` inside
   the tool. Covers all 31 base-game characters, locations, moods, faces,
   arms, poses, outfits, SFX, looks, stages, and interpolation paths.

2. **Mod layer** — your mod's additions, under `mod_allowlists` (configured
   in `tnh_scene_compiler.yaml`). Only provide files for what your mod
   adds. Missing files are fine — the base layer covers vanilla TNH.

Layers merge automatically: mod entries extend the base (sets are unioned,
location overrides win on collision).

### What goes in the mod layer

| File | When to add it |
|---|---|
| `characters.yaml` | Your mod adds a new character (e.g. an OC) |
| `moods/<Char>.yaml` | Your mod adds custom moods for a character |
| `faces/<Char>.yaml` | Your mod adds custom face expressions |
| `condition_functions.yaml` | Your mod defines `[[if]]`-callable helpers |
| `mod_operations.yaml` | Your mod defines `[[mod_set]]`-callable helpers |
| `fx.yaml` | Your mod adds `[[fx]]`-callable visual effects |
| `interpolation_custom.yaml` | Your mod adds custom `[path]` interpolation targets |
| `locations_overrides.yaml` | Your mod adds short-form sluglines for locations |

### Example: adding a custom character

Create `scenes_source/_allowlists/characters.yaml`:

```yaml
source: MyMod
generated_at: '2026-05-13'
values:
  - name: MyOC
    source_file: MyMod/game/my_mod/characters.rpy
    source_line: 42
```

The compiler merges this with the 31 vanilla characters from the base layer.

### Example: adding a mod operation

Create `scenes_source/_allowlists/mod_operations.yaml`:

```yaml
operations:
  - name: my_mod_record_choice
    signature: my_mod_record_choice(value)
    notes: |
      Records the player's dialogue choice into store.my_mod_choice.
      Valid values: "accept", "refuse".
```

Writers can now use `[[mod_set my_mod_record_choice("accept")]]` in their
scenes.

### Refreshing allowlists from the base game

If TNH updates and you need fresh vanilla allowlists, configure the
`refresh` section in your config:

```yaml
refresh:
  base_game: ../TheNullHypothesis/
  mod_root: MyMod/
```

Then run:

```bash
python -m tnh_refresh_allowlists \
  --base-game ../TheNullHypothesis \
  --out scenes_source/_allowlists \
  --verbose
```

This scans the base game `.rpy` files and regenerates the YAML allowlists.

## Compilation workflow

### Full project compilation

```bash
python -m tnh_scene_compiler compile --verbose
```

Compiles every `.scene` under `scenes_source/` and writes `.rpy` files to
your configured output directory. Also generates `_events.rpy` with the
consolidated event registry.

### Specific files only

```bash
python -m tnh_scene_compiler compile scenes_source/JeanGrey/my_scene.scene
```

### Validation without output

```bash
python -m tnh_scene_compiler validate --verbose
```

Parses and validates every scene but writes nothing. Useful for CI or
pre-commit checks.

### Drag-and-drop (Windows)

Drop `.scene` files onto `Tools/tnh-scene-compiler/scripts/compile.bat`.
The console window shows colored output and pauses at the end.

## Generating a cheatsheet for writers

The cheatsheet lists every valid character, mood, face, location, etc. —
a reference writers keep open while authoring scenes.

```bash
python -m tnh_generate_cheatsheet \
  --allowlists scenes_source/_allowlists \
  --out Docs/Authoring_Cheatsheet.md
```

Or on Windows: `Tools/tnh-scene-compiler/scripts/generate-cheatsheet.bat`.

Regenerate the cheatsheet whenever allowlists change.

## Integrating with a build script

Example PowerShell wrapper (`Tools/Compile-Scenes.ps1`):

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

## CI integration

Example GitHub Actions step:

```yaml
- name: Validate scenes
  run: |
    pip install pyyaml
    export PYTHONPATH=Tools/tnh-scene-compiler
    python -m tnh_scene_compiler validate
```

Exit code 0 = all scenes valid, 1 = errors found.

## Directory layout summary

After setup, your mod repo looks like:

```
my-tnh-mod/
├── tnh_scene_compiler.yaml        ← config
├── scenes_source/
│   ├── _allowlists/               ← mod-specific extensions
│   │   ├── characters.yaml        ← only if adding characters
│   │   ├── mod_operations.yaml    ← your [[mod_set]] helpers
│   │   └── condition_functions.yaml
│   ├── JeanGrey/
│   │   └── my_mod_dialogue_jeangrey_greeting.scene
│   └── Rogue/
│       └── my_mod_dialogue_rogue_chat.scene
├── MyMod/
│   └── game/
│       └── my_mod/
│           ├── my_mod_runtime.rpy
│           ├── my_mod_metadata.rpy
│           ├── my_mod_testing_eval.rpy
│           └── scenes/            ← compiled output
│               ├── JeanGrey/
│               ├── Rogue/
│               └── _events.rpy
├── Tools/
│   └── tnh-scene-compiler/        ← git submodule
└── Docs/
    └── Authoring_Cheatsheet.md    ← generated
```

## Troubleshooting

**"No tnh_scene_compiler.yaml found"** — the compiler could not locate
the config file. Either `cd` to your mod repo root or pass
`--config path/to/tnh_scene_compiler.yaml`.

**"No allowlists directories found"** — neither the base allowlists
(shipped with the tool) nor your mod allowlists directory exist. Check
that `include_base_allowlists: true` is set and that the tool's
`allowlists_base/` directory is present.

**Unknown character/mood/face errors** — the value is not in any
allowlist. Either add it to your mod's allowlist extension or check the
cheatsheet for valid values.

**Import errors when running** — make sure `PYTHONPATH` includes the
tool's root directory (where `tnh_scene_compiler/` lives).
