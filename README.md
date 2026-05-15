# TNH Scene Compiler

Write dialogue scenes for **The Null Hypothesis** in plain text,
compile them to Ren'Py code.

## Get started

Download the app from the
[Releases](https://github.com/Kumolingus/tnh-scene-compiler/releases)
page — no Python needed.

### I want to write a scene right now

Open the app, click **New scene**, fill in the guided form (title,
character, scene type), pick a starting template, and start writing.
See the [Quick start guide](docs/quick_start.md) for a 5-minute walkthrough.

### I want to compile scenes I already wrote

Open the app, click **Quick compile**, add your `.scene` files, and hit
**Compile**. The compiled `.rpy` files appear in the output folder.

### I want to manage a full project

Click **Create project**, pick a name and folder. The app sets everything
up. See the [Project setup guide](docs/project_setup.md) for details.

## What does a `.scene` file look like?

```
Title: A morning chat
Scene Id: my_project_morning_chat
Character: JeanGrey
Scene Type: cinematic
Trigger: manual

INT. KITCHEN

JEANGREY (happy)
Good morning! Sleep well?

PLAYER
Not really...

JEANGREY (concerned)
What happened?

[[if JeanGrey.love >= 500]]

JEANGREY
You know you can tell me anything.

[[/if]]
```

That's it. No Ren'Py syntax to learn. The compiler handles the rest.

## Documentation

| Document | What's inside |
|---|---|
| [Quick start](docs/quick_start.md) | Write and compile your first scene in 5 minutes |
| [Scene cheatsheet](docs/scene_cheatsheet.md) | One-page reference — copy-paste examples for every feature |
| [Writer guide](docs/writer_guide.md) | Complete guide for scene writers |
| [Project setup](docs/project_setup.md) | Setting up and managing a project |
| [Format specification](docs/format_spec.md) | Technical spec for developers |

The integrated editor also includes a **Condition Builder** — open it
from the Struct. palette tab to browse every available condition type
and build expressions without memorizing the syntax.

## From source (for developers)

```bash
pip install pyyaml
pip install tkinterdnd2  # optional, for drag-and-drop
python -m tnh_scene_compiler.gui
```

CLI: `python -m tnh_scene_compiler compile --verbose`

### Import visual thumbnails

The editor can display character face and arm thumbnails alongside the
text labels. To generate them from a
[TNH-VisualReference](https://github.com/Kumolingus/TNH-VisualReference)
checkout:

```bash
pip install Pillow
python scripts/import_thumbnails.py path/to/TNH-VisualReference
```

This creates a `thumbnails/` directory with resized PNGs and a mapping
file. The thumbnails are bundled into the release `.exe` automatically.

## License

MIT
