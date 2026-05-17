# Modder setup guide

How to integrate `tnh-scene-compiler` into your TNH mod project.

## Initial setup

### 1. Create a project

Click **Create project** on the welcome screen. Enter your mod prefix
(e.g. `my_mod`) and pick a folder. The app generates the config file
and runtime stubs for you.

An extracted TNH build (`.rpy` source files, not `.rpyc`) is required
for allowlist refresh of the base game.

This creates:

| File                      | Purpose                                                  |
| ------------------------- | -------------------------------------------------------- |
| `tnh_scene_compiler.yaml` | Project config — edit paths to match your layout         |
| `runtime_stub.rpy`        | Runtime module for scene state injection                 |
| `metadata_init.rpy`       | Empty metadata dict populated at boot by compiled scenes |
| `testing_eval.rpy`        | Optional — enables overriding conditions for previewing  |

### 2. Edit the config

Open `tnh_scene_compiler.yaml` and adjust:

```yaml
mod_prefix: my_mod

# Where your .scene source files live.
scenes_source: scenes_source/

# Where your project-specific allowlist extensions live.
project_allowlists: scenes_source/_allowlists/

# Where compiled .rpy files go (inside your mod's game/ tree).
output: MyMod/game/my_mod/scenes/

# Use the vanilla TNH allowlists shipped with the tool.
include_base_allowlists: true
```

### 3. Move the runtime stubs

Move the three `.rpy` stubs into your mod's `game/` directory so Ren'Py loads them at boot:

```
MyMod/game/my_mod/my_mod_runtime.rpy      ← runtime_stub.rpy
MyMod/game/my_mod/my_mod_metadata.rpy     ← metadata_init.rpy
MyMod/game/my_mod/my_mod_testing_eval.rpy ← testing_eval.rpy
```

Rename them to match your mod prefix. These files are generated once and committed to your repo — the compiler does not regenerate them.

### 4. Create your scenes directory

```
scenes_source/
├── _allowlists/       ← project-specific allowlist extensions (optional)
├── JeanGrey/          ← one directory per character
│   └── my_mod_dialogue_jeangrey_greeting.scene
├── Rogue/
└── LauraKinney/
```

## Allowlist configuration

### How allowlists work

The compiler validates every identifier in your `.scene` files (character names, moods, faces, locations, SFX, interpolation paths, etc.)
against YAML allowlists. Unknown values produce a compile error with a "did you mean?" suggestion.

### Two-layer architecture

1. **Base layer** — vanilla TNH data, ships in `allowlists_base/`
   inside the tool. Covers all base-game characters (including NPCs), locations,
   moods, faces, arms, poses, outfits, SFX, looks, stages, and
   interpolation paths.

2. **Project layer** — your mod's additions, under `project_allowlists`
   (configured in `tnh_scene_compiler.yaml`). Only provide files for
   what your mod adds. Missing files are fine — the base layer covers
   vanilla TNH.

Layers merge automatically: mod entries extend the base (sets are unioned, location overrides win on collision).

**Notes on base allowlists:**

- Arm allowlists only include standing poses (arms that are valid
  when the character is in a standing position). Other pose-specific
  arm variants are excluded because the compiler targets standing
  dialogue scenes.
- The FX extractor auto-discovers visual effects by scanning for
  functions with known effect signatures in the base game source. You
  do not need to manually enumerate effects — the refresh process
  picks them up automatically.

### What goes in the project layer

| File                        | When to add it                                                                         |
| --------------------------- | -------------------------------------------------------------------------------------- |
| `characters.yaml`           | Your project adds custom characters (e.g. an OC)                                      |
| `moods/<Char>.yaml`         | Your project adds custom moods for a character                                         |
| `faces/<Char>.yaml`         | Your project adds custom face expressions                                              |
| `traits.yaml`               | Your project adds custom traits (for `[[give_trait]]` / `[[if Character.has(...)]]`)   |
| `personalities.yaml`        | Your project adds custom personality axes (for `[[set_personality]]`)                  |
| `history_events.yaml`       | Your project adds custom events (for `[[record]]` / `[[if Character.did(...)]]`)       |
| `condition_functions.yaml`  | Your project defines custom `[[if]]`-callable helper functions                         |
| `run_operations.yaml`       | Your project defines custom `[[run]]`-callable helper functions                        |
| `fx.yaml`                   | Your project adds custom `[[fx]]` visual effects                                       |
| `interpolation_custom.yaml` | Your project adds custom `[path]` interpolation targets                                |
| `locations_overrides.yaml`  | Your project needs custom short-form sluglines for locations                            |

Every file you add in your project's `_allowlists/` directory is **merged with the base game layer** at compile time. You only need to list
your additions — the base game values are included automatically.

### Example: adding a custom character

Create `scenes_source/_allowlists/characters.yaml`:

```yaml
source: MyMod
generated_at: "2026-05-13"
values:
  - name: MyOC
    source_file: MyMod/game/my_mod/characters.rpy
    source_line: 42
```

The compiler merges this with the base-game characters from the base layer.

### Example: adding a run operation

Create `scenes_source/_allowlists/run_operations.yaml`:

```yaml
operations:
  - name: my_mod_record_choice
    signature: my_mod_record_choice(value)
    notes: |
      Records the player's dialogue choice into store.my_mod_choice.
      Valid values: "accept", "refuse".
```

Writers can now use `[[run my_mod_record_choice("accept")]]` in their scenes.

### Example: adding custom traits

If your mod introduces traits that don't exist in the base game, create `scenes_source/_allowlists/traits.yaml`:

```yaml
source: MyMod
values:
  - name: my_mod_pregnant
  - name: my_mod_aware_of_pregnancy
```

Writers can now use these traits in directives and conditions:

```
[[give_trait JeanGrey my_mod_pregnant]]
[[if JeanGrey.has("my_mod_pregnant")]]
```

The same pattern works for **personalities** and **history events**:

```yaml
# scenes_source/_allowlists/personalities.yaml
source: MyMod
values:
  - name: maternal

# scenes_source/_allowlists/history_events.yaml
source: MyMod
values:
  - name: learned_about_pregnancy
  - name: told_partner
```

These values are merged with the base game allowlists. They appear in the editor dropdowns and are accepted by the validator.

### Refreshing allowlists from the base game

If TNH updates and you need fresh vanilla allowlists, use **Refresh allowlists** in the app's project
settings. The app reads the `refresh` section of your config:

```yaml
refresh:
  base_game: ../TheNullHypothesis/
  mod_root: MyMod/
```

This scans the base game `.rpy` files and regenerates the YAML allowlists.

## Compilation workflow

### Using the app

- **Full project**: open the app, click **Open project**, then **Compile**. All `.scene` files under
  `scenes_source/` are compiled and `.rpy` output is written to your configured output directory.
- **Specific files**: use **Quick compile** and add the files you want to compile.
- **Validate only**: click the **Validate** button in the editor toolbar — parses and validates
  without writing output.


## Cheatsheet for writers

The editor's palette already shows all available characters, moods, faces, arms, FX, and locations with thumbnail
previews. For an offline reference, a cheatsheet is included in the docs folder (`docs/scene_cheatsheet.md`) with
copy-paste examples for every directive.

## Directory layout summary

After setup, your mod repo looks like:

```
my-tnh-mod/
├── tnh_scene_compiler.yaml        <- config
├── scenes_source/
│   ├── _allowlists/               <- mod-specific extensions
│   │   ├── characters.yaml        <- only if adding characters
│   │   ├── run_operations.yaml    <- your [[run]] helpers
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
│           └── scenes/            <- compiled output
│               ├── JeanGrey/
│               ├── Rogue/
│               └── _events.rpy
└── Docs/
    └── Authoring_Cheatsheet.md    <- generated
```

## Troubleshooting

**"No tnh_scene_compiler.yaml found"** — the app could not locate the
config file. Use **Open project** and navigate to the folder containing
your `tnh_scene_compiler.yaml`.

**"No allowlists directories found"** — neither the base allowlists
(shipped with the tool) nor your project allowlists directory exist. Check
that `include_base_allowlists: true` is set in your config.

**Unknown character/mood/face errors** — the value is not in any
allowlist. Either add it to your mod's allowlist extension or check
the cheatsheet for valid values.

## Thumbnails

Thumbnails provide visual previews of character faces and arms in the GUI editor. They are **not** bundled inside the executable — they
ship as a separate `thumbnails.zip` archive alongside the release.

### Installing thumbnails

Extract `thumbnails.zip` so that the `thumbnails/` folder sits next to the executable:

```
TNHSceneCompiler-v1.2.0/
├── TNHSceneCompiler.exe
├── thumbnails/          ← extract here
│   ├── _mapping.yaml
│   ├── JeanGrey/
│   ├── Rogue/
│   └── ...
└── docs/
```

The editor detects the `thumbnails/` directory at startup and enables visual previews
automatically. Without it, the editor still works -- you just won't see face/arm previews.
