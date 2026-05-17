# Integration guide — using compiled scenes in your mod

You wrote a `.scene` file in the editor, compiled it, and got a `.rpy`
file. This guide explains how to drop it into your mod so it actually
runs in the game.

## What the compiler produces

For each `.scene` file, the compiler outputs one `.rpy` file containing:

- A **Ren'Py label** named after your `Scene Id`
- A **metadata block** that registers the scene at boot
- For cinematic scenes: an `_events.rpy` file that hooks the scene
  into TNH's event system

## Quick path — one-off scene, no project

1. Open the app, click **Quick compile**
2. Add your `.scene` file, pick an output folder, compile
3. Copy the `.rpy` output into your mod's `game/` tree (anywhere
   Ren'Py can find it)
4. Call it from your mod code:

```renpy
$ renpy.call("my_mod_greeting_jean")
```

That's it for a basic scene. For automatic event triggering (cinematic
scenes that fire on sleep, wake, etc.), use the project workflow below.

## Project workflow

### 1. Create a project

On the welcome screen, click **Create project**. Pick a name (e.g.
`my_mod`) and a folder. The app generates a config file and three
**runtime files** that your mod needs to work with compiled scenes.

### 2. Add the runtime bootstrap to your mod

Compiled scenes need a few lines of setup in your mod. Add this to
any `init python` block that runs early (before the compiled scenes
load):

```renpy
init python:
    my_mod_scene_metadata = {}

    import sys, types
    if "my_mod_runtime" not in sys.modules:
        _mod = types.ModuleType("my_mod_runtime")
        _mod.scene_state = None
        sys.modules["my_mod_runtime"] = _mod
    import my_mod_runtime
```

That's it. Replace `my_mod` with your project prefix everywhere.

**What this does:**

- `my_mod_scene_metadata` — a dict where each compiled scene
  registers itself at boot. Without it, the game crashes on launch.
- `my_mod_runtime` — a module that compiled scenes read at entry.
  It's the channel your mod uses to pass context into a scene. For
  example, if a dialogue should vary based on a character's attitude:

```renpy
$ my_mod_runtime.scene_state = {"attitude": "friendly"}
$ renpy.call("my_mod_ask_about_jean")
```

The scene author writes `[[if attitude == "friendly"]]` and it works.
When you call a scene without setting state, it runs with defaults.

> **Quick option:** the **Create project** button generates `.rpy`
> files containing this code — you can copy them into your mod's
> `game/` folder without touching your existing files. It also
> generates a `testing_eval.rpy` — only relevant if you build a
> testing hub that needs to preview scene branches with fake condition
> values (e.g. testing a high-love dialogue path without actually
> having high love). Safe to ignore otherwise.

### 3. Place the compiled scenes

```
YourMod/
  game/
    my_mod/
      scenes/
        JeanGrey/
          my_mod_greeting_jean.rpy
        _events.rpy
```

### 4. Compile and place scenes

Open the project from the welcome screen, write scenes in the editor,
and compile. The compiled `.rpy` files go to the output folder
configured in your project (typically `YourMod/game/my_mod/scenes/`).

## How scenes get triggered

| Scene Type                              | How it runs                                                        |
| --------------------------------------- | ------------------------------------------------------------------ |
| `cinematic` with trigger (sleep, wake…) | TNH fires it automatically when trigger + conditions met.          |
| `cinematic` with `Trigger: manual`      | Your mod calls `$ renpy.call("my_mod_scene_id")`.                  |
| `phone`                                 | Your mod's phone dispatch calls the label directly.                |
| `texting`                               | Same as phone — called directly by mod code.                       |
| `hub_option`                            | Called from a menu or hub screen in your mod.                      |

## Recompiling

Edit the `.scene` file, recompile. The compiler overwrites the old
`.rpy`. Ren'Py picks up the change on next launch.

> **Tip:** If you rename or delete a `.scene` file, also delete the
> old `.rpy` file manually. The compiler doesn't clean up stale output.
