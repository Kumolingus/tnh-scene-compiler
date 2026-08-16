# Using compiled scenes

How a compiled `.rpy` gets into a mod and actually runs. This is the
developer side of the format; a writer handing `.scene` files over never
needs it.

## Using compiled scenes

Compiling turns each `.scene` file into one `.rpy` holding a Ren'Py **label**
named after the scene's `Scene Id` (see [title page](#title-page)), plus a
metadata block the scene uses to register itself at boot. Cinematic scenes
also land in a generated `_events.rpy`, which hooks them into the game's
event system.

Nothing runs on its own except a cinematic scene with a real trigger.
Everything else waits to be called.

### The runtime bootstrap

Compiled scenes expect two things to exist before they load. Put this in an
`init python` block that runs early, replacing `my_mod` with your project
prefix:

```
init python:
    my_mod_scene_metadata = {}

    import sys, types
    if "my_mod_runtime" not in sys.modules:
        _mod = types.ModuleType("my_mod_runtime")
        _mod.scene_state = None
        sys.modules["my_mod_runtime"] = _mod
    import my_mod_runtime
```

`my_mod_scene_metadata` is the dict each compiled scene registers itself
into. `my_mod_runtime` is the module a scene reads on entry — the channel
your mod passes context through.

> Watch out: without the metadata dict the game crashes at launch, not at
> the moment a scene is called. If a fresh mod dies on boot right after you
> added compiled scenes, this bootstrap is missing.

> The **Create project** button writes these files for you, ready to copy
> into your mod's `game/` folder. It also writes a `testing_eval.rpy`, which
> you only need if you want to preview a specific branch by overriding its
> conditions — safe to ignore otherwise.

### Calling a scene

With the bootstrap in place, a scene is just a label — calling it is one
line, the `Scene Id` from the [title page](#title-page) and nothing else:

```
$ renpy.call("my_mod_greeting_jean")
```

> Watch out: `renpy.call` returns to your code when the scene ends, while
> `renpy.jump` does not come back. Use `call` unless you mean to hand
> control over for good.

### Passing state into a scene

Set `scene_state` on the runtime module before calling. The keys become
bare names the scene can test, the same way a scene-local flag does (see
[Conditions](#conditions)):

```
$ my_mod_runtime.scene_state = {"attitude": "friendly"}
$ renpy.call("my_mod_ask_about_jean")
```

The writer then branches on it without knowing where it came from:

```
[[if attitude == "friendly"]]

JEANGREY
Of course, ask me anything.

[[/if]]
```

Called with no state set, a scene runs on its defaults.

### Passing a target character

A scene declaring `Target: true` on its [title page](#title-page) compiles to
a label with one parameter, so the character rides as a call argument rather
than through the runtime module:

```
$ renpy.call("my_mod_fertility_reading", chosen_character)
```

Ren'Py scopes label parameters dynamically: `Target` is set when the label
starts and the previous value restored when it returns, so there is nothing
to clear afterwards — which matters here, because `renpy.call` never comes
back to the Python that called it.

Each compiled scene declares `"uses_target"` in its metadata block. Read that
rather than guessing: passing an argument to a label that takes none, or
omitting one it requires, raises from inside the scene.

### What calls what

A **cinematic** scene with a real trigger (sleeping, waking, …) is fired by
the game when its trigger and conditions are met — you write no call for it.
A cinematic scene with `Trigger: manual` is yours to call.

A **phone** or **texting** scene is called by your mod's phone dispatch, and
a **hub_option** scene by whatever menu or hub screen offers it. All three
are ordinary labels, so they are all the same one-line `renpy.call`.

### Recompiling

Editing a `.scene` and recompiling overwrites the old `.rpy`; the game picks
it up on the next launch.

> Watch out: renaming or deleting a `.scene` leaves its old `.rpy` behind.
> The compiler never deletes output it did not just write, so a stale label
> keeps working — and keeps answering to the old `Scene Id` — until you
> remove the file by hand.
