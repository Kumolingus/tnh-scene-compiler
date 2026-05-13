# tnh-scene-compiler

Fountain-TNH scene compiler for **The Null Hypothesis** (Ren'Py game).

Converts human-readable `.scene` files into native Ren'Py `.rpy` scripts,
with allowlist-driven validation, colored error reporting, and drag-and-drop
support on Windows.

## Who is this for?

- **TNH modders** who want authored dialogue scenes compiled to `.rpy`
  without hand-writing Ren'Py boilerplate.
- **Writers** contributing dialogue to any TNH mod — the `.scene` format
  is designed so non-programmers can write scenes in a plain text editor.

## Quick start

### 1. Get the tool

Clone (or add as a submodule in your mod repo):

```bash
git clone https://github.com/Ethyl39/tnh-scene-compiler.git
```

### 2. Install the dependency

The only runtime dependency is [PyYAML](https://pyyaml.org/):

```bash
pip install pyyaml
```

### 3. Initialize your mod project

```bash
python -m tnh_scene_compiler init --mod-prefix my_mod
```

This creates:
- `tnh_scene_compiler.yaml` — the project config file.
- Runtime `.rpy` stubs your mod needs (metadata dict, runtime module,
  testing-hub condition wrapper).

### 4. Write a scene

Create `scenes_source/JeanGrey/my_mod_dialogue_jeangrey_hello.scene`:

```
Title: Jean says hello
Scene Id: my_mod_dialogue_jeangrey_hello
Character: JeanGrey
Scene Type: cinematic
Trigger: manual
Description: A short greeting scene.

INT. JEANGREY'S ROOM

JEANGREY (happy)
Hey, [player.petname]. How's it going?
```

### 5. Compile

```bash
python -m tnh_scene_compiler compile --verbose
```

Or on Windows — drag `.scene` files onto `scripts/compile.bat`.

The compiled `.rpy` appears under your configured output directory.

## Commands

| Command | Purpose |
|---|---|
| `compile [files...]` | Compile `.scene` files to `.rpy`. Omit files to compile all. |
| `validate [files...]` | Parse + validate without writing output (for CI). |
| `init --mod-prefix <prefix>` | Bootstrap config + runtime stubs for a new mod. |

Common flags: `--config <path>` (force config location), `--verbose`.

## Configuration

Each mod repo has a `tnh_scene_compiler.yaml` at its root:

```yaml
mod_prefix: my_mod
scenes_source: scenes_source/
mod_allowlists: scenes_source/_allowlists/
output: game/my_mod/scenes/
include_base_allowlists: true
```

The compiler discovers this file by walking up from the current directory
(or from the first dropped file).

## Allowlist system

The compiler validates every character name, mood, face, location, SFX,
and interpolation path against YAML allowlists.

**Two-layer architecture:**

1. **Base layer** (`allowlists_base/`) — vanilla TNH data, ships with this tool.
2. **Mod layer** (`mod_allowlists` in your config) — your mod's additions
   (custom characters, mod operations, condition functions, etc.).

Layers merge automatically: the mod layer extends the base. A mod that adds
no custom data needs zero allowlist files.

## Drag-and-drop (Windows)

Drop `.scene` files onto `scripts/compile.bat`. A console window opens,
shows colored compilation output, and pauses so you can read the results.

## Documentation

| Document | Audience |
|---|---|
| [Format specification](docs/format_spec.md) | Developers building or extending the compiler |
| [Writer guide](docs/writer_guide.md) | Scene writers (non-programmers) |
| [Modder setup guide](docs/modder_setup.md) | Mod developers integrating the tool |

## As a git submodule

Add to your mod repo:

```bash
git submodule add https://github.com/Ethyl39/tnh-scene-compiler.git Tools/tnh-scene-compiler
```

Then point `PYTHONPATH` at the submodule root before invoking:

```powershell
$env:PYTHONPATH = "Tools/tnh-scene-compiler"
python -m tnh_scene_compiler compile --verbose
```

## Requirements

- Python 3.10+
- PyYAML >= 6.0

## License

MIT
