# Quick start — your first scene in 5 minutes

## 1. Get the app

Download `TNHSceneCompiler.exe` from the
[Releases](https://github.com/Kumolingus/tnh-scene-compiler/releases) page.
Double-click to launch. No installation needed.

For character thumbnails in the palette, also download `thumbnails.zip` from
the same release and extract it next to the exe.

## 2. Create a new scene

Click **New scene** on the welcome screen. The editor opens with a
template:

```
Title:
Scene Id: my_project_
Character:
Scene Type: cinematic
Trigger: manual
```

Fill in the blanks:

```
Title: Jean says hello
Scene Id: my_project_hello_jean
Character: JeanGrey
Scene Type: cinematic
Trigger: manual
```

## 3. Set the location

Below the title block, add a blank line and a location:

```
INT. JEANGREY'S ROOM
```

You can also use the **Locs** tab in the palette on the right to insert
a location with one click.

## 4. Write dialogue

Add a character name in UPPERCASE, then the line below:

```
JEANGREY
Hey there! How are you?
```

Want an expression? Use the **Chars** tab in the palette — click a
character, pick a mood, and hit Insert:

```
JEANGREY (happy)
Hey there! How are you?
```

## 5. Add narration

Any line that isn't a character name, directive, or location is narration:

```
The room is quiet. Sunlight filters through the curtains.
```

## 6. Add a condition

Want dialogue that only shows if the player has enough love?

```
[[if JeanGrey.love >= 500]]

JEANGREY
I'm really glad you're here.

[[/if]]
```

Use the **Struct.** tab to insert an if/endif block quickly.

## 7. Add a choice

```
[[choice]]
= Tell her the truth
    JEANGREY (happy)
    Thank you for being honest.

= Change the subject
    JEANGREY (neutral)
    Alright then...
[[/choice]]
```

## 8. Save

Press **Ctrl+S** or click **Save**. Pick a filename like
`my_project_hello_jean.scene`.

## 9. Validate

Click **Validate** in the editor toolbar to check for errors.
Errors show up in the panel below with clickable line numbers.

## 10. Compile

Go back to the welcome screen, click **Quick compile**, add your
`.scene` file, choose an output folder, and click **Compile**.

Your `.rpy` file is ready.

## Tips

- Use the **Settings** button in the editor toolbar to configure
  project paths and preferences.
- The **About** button on the welcome screen shows version and links.

## What's next?

- See the [Integration guide](integration_guide.md) to drop compiled
  scenes into your mod.
- See the [Scene cheatsheet](scene_cheatsheet.md) for a copy-paste
  reference of every feature.
- Read the [Writer guide](writer_guide.md) for the complete guide.
