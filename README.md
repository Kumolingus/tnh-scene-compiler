# tnh-scene-compiler

Fountain-TNH scene compiler for **The Null Hypothesis** (Ren'Py game).

Converts human-readable `.scene` files into native Ren'Py `.rpy` scripts,
with allowlist-driven validation, colored error reporting, and a Tkinter GUI.

## Who is this for?

- **Writers** contributing dialogue to any TNH project — the `.scene` format
  is designed so non-programmers can write scenes in a plain text editor.
- **Modders** who want authored dialogue scenes compiled to `.rpy`
  without hand-writing Ren'Py boilerplate.

## Quick start — GUI

### Download the executable

Grab `TNHSceneCompiler.exe` from the
[Releases](https://github.com/Kumolingus/tnh-scene-compiler/releases) page.
No Python installation needed.

### Quick compile (writers)

1. Launch the app.
2. Click **Quick compile**.
3. Add your `.scene` files (browse or drag-and-drop).
4. Choose an output folder.
5. Click **Compile**.

Quick compile uses the base game allowlists only — no project setup required.

### Project mode (modders)

1. Click **Create new project** and fill in the project name + folder.
2. The app creates `tnh_scene_compiler.<name>.yaml` and scaffolds the directory.
3. Drop your `.scene` files in `scenes_source/`.
4. Click **Compile** or **Validate** in the project workspace.

## Quick start — CLI

### 1. Install the dependency

```bash
pip install pyyaml
```

### 2. Initialize your project

```bash
python -m tnh_scene_compiler init --project-prefix my_project
```

This creates:
- `tnh_scene_compiler.my_project.yaml` — the project config file.
- Runtime `.rpy` stubs your project needs.

### 3. Write a scene

Create `scenes_source/JeanGrey/my_project_dialogue_jeangrey_hello.scene`:

```
Title: Jean says hello
Scene Id: my_project_dialogue_jeangrey_hello
Character: JeanGrey
Scene Type: cinematic
Trigger: manual
Description: A short greeting scene.

INT. JEANGREY'S ROOM

JEANGREY (happy)
Hey, [player.petname]. How's it going?
```

### 4. Compile

```bash
python -m tnh_scene_compiler compile --verbose
```

Or on Windows — drag `.scene` files onto `scripts/compile.bat`.

## Commands

| Command | Purpose |
|---|---|
| `compile [files...]` | Compile `.scene` files to `.rpy`. Omit files to compile all. |
| `validate [files...]` | Parse + validate without writing output (for CI). |
| `init --project-prefix <prefix>` | Bootstrap config + runtime stubs for a new project. |

Common flags: `--config <path>` (force config location), `--verbose`.

## Configuration

Each project has a `tnh_scene_compiler.<prefix>.yaml` at its root:

```yaml
project_prefix: my_project
scenes_source: scenes_source/
project_allowlists: scenes_source/_allowlists/
output: game/my_project/scenes/
include_base_allowlists: true
```

The compiler discovers this file by walking up from the current directory.
The legacy `tnh_scene_compiler.yaml` filename is still supported.

## Writer-friendly conditions (DSL)

Scene writers can use intuitive syntax in `[[if ...]]` conditions.
The compiler translates it into Ren'Py code automatically.

```
[[if JeanGrey.love >= medium]]
[[if JeanGrey.trust >= small]]
[[if JeanGrey.has("shy")]]
[[if JeanGrey.mood == "normal"]]
[[if JeanGrey.mood == "mad"]]
[[if JeanGrey.friends_with(Rogue)]]
[[if JeanGrey.did("kissed_player")]]
[[if JeanGrey.nearby]]
```

The original function-call syntax is also supported:

```
[[if check_approval(JeanGrey, "love", "medium_stat")]]
[[if JeanGrey.check_trait("shy")]]
[[if JeanGrey.is_in_normal_mood()]]
[[if JeanGrey.get_status() == "mad"]]
[[if are_Characters_friends(JeanGrey, Rogue)]]
[[if JeanGrey.History.check("kissed_player") > 0]]
[[if Character_is_in_close_proximity(JeanGrey)]]
```

Both forms produce identical Ren'Py output. The DSL syntax is recommended
for readability; the function-call syntax is available for advanced users
or cases the DSL does not cover.

### Project-level aliases

Projects can define custom aliases in `scenes_source/_allowlists/aliases.yaml`:

```yaml
character_aliases:
  is_pregnant: pregnancy_mod_is_pregnant
  ready_for_parenthood: pregnancy_mod_ready_for_parenthood

function_aliases:
  get_weather: my_project_get_weather
```

This lets writers use `JeanGrey.is_pregnant()` instead of
`pregnancy_mod_is_pregnant(JeanGrey)`.

## Allowlist system

The compiler validates every character name, mood, face, location, SFX,
interpolation path, effect, and condition function against YAML allowlists.

**Two-layer architecture:**

1. **Base layer** (`allowlists_base/`) — vanilla TNH data, ships with this tool.
2. **Project layer** (`project_allowlists` in your config) — your project's additions
   (custom characters, operations, condition functions, aliases, etc.).

Layers merge automatically: the project layer extends the base.

## GUI features

- **Welcome screen** with New scene / Quick compile / Open project / Create project.
- **Recent projects** list with persistence.
- **Per-file status indicators** (pending / running / ok / error) during compilation.
- **Drag-and-drop** support for `.scene` files (requires `tkinterdnd2`).
- **Project settings** editor (paths, allowlists, base game options).
- **Colored output pane** with real-time compilation feedback.
- **Dark theme** with colored action buttons (compile, validate, edit, back).
- **Integrated scene editor** with:
  - Syntax highlighting for `.scene` format.
  - Insertion palette with colored tabs: Characters, Locations, Directives, FX/SFX, Structures, Visuals.
  - Character dialog for selecting medium, mood, face, pose, arms, outfit, look.
  - Directive dialogs with per-directive forms and live preview.
  - Inline validation with error navigation.
  - Undo/redo, save, new scene template.

## Distribution

### Pre-built executable

Download from [Releases](https://github.com/Kumolingus/tnh-scene-compiler/releases).
Built with PyInstaller, no Python required.

### From source

```bash
pip install pyyaml
pip install tkinterdnd2  # optional, for drag-and-drop
python -m tnh_scene_compiler.gui
```

## Documentation

| Document | Audience |
|---|---|
| [Format specification](docs/format_spec.md) | Developers building or extending the compiler |
| [Writer guide](docs/writer_guide.md) | Scene writers (non-programmers) |
| [Modder setup guide](docs/modder_setup.md) | Project developers integrating the tool |

## Requirements

- Python 3.10+
- PyYAML >= 6.0
- tkinterdnd2 >= 0.3 (optional, for drag-and-drop in GUI)

## License

MIT
