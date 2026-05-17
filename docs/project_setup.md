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

# Where your mod-specific allowlist extensions live.
mod_allowlists: scenes_source/_allowlists/

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
├── _allowlists/       ← mod-specific allowlist extensions (optional)
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
   inside the tool. Covers all 31 base-game characters, locations,
   moods, faces, arms, poses, outfits, SFX, looks, stages, and
   interpolation paths.

2. **Mod layer** — your mod's additions, under `mod_allowlists`
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

### What goes in the mod layer

| File                        | When to add it                                                                         |
| --------------------------- | -------------------------------------------------------------------------------------- |
| `characters.yaml`           | Your mod adds a new character (e.g. an OC)                                             |
| `moods/<Char>.yaml`         | Your mod adds custom moods for a character                                             |
| `faces/<Char>.yaml`         | Your mod adds custom face expressions                                                  |
| `traits.yaml`               | Your mod introduces custom traits (for `[[give_trait]]` / `[[if Character.has(...)]]`) |
| `personalities.yaml`        | Your mod introduces custom personality axes (for `[[set_personality]]`)                |
| `history_events.yaml`       | Your mod introduces custom events (for `[[record]]` / `[[if Character.did(...)]]`)     |
| `condition_functions.yaml`  | Your mod defines `[[if]]`-callable helpers                                             |
| `run_operations.yaml`       | Your mod defines `[[run]]`-callable helpers                                            |
| `fx.yaml`                   | Your mod adds `[[fx]]`-callable visual effects                                         |
| `interpolation_custom.yaml` | Your mod adds custom `[path]` interpolation targets                                    |
| `locations_overrides.yaml`  | Your mod adds short-form sluglines for locations                                       |

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

The compiler merges this with the 31 vanilla characters from the base layer.

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


## Generating a cheatsheet for writers

The cheatsheet lists every valid character, mood, face, location, etc. — a reference writers keep open
while authoring scenes. A pre-generated cheatsheet is included in the docs folder of each release.

To regenerate it after allowlist changes, use the app's project settings (the **Generate cheatsheet**
button).

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
(shipped with the tool) nor your mod allowlists directory exist. Check
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
