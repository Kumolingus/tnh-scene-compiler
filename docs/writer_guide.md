# Writer Guide — Fountain-TNH Scene Compiler

This guide teaches you how to write scenes for The Null Hypothesis
using the Fountain-TNH format. It starts with the basics and works up
to advanced patterns. No programming experience required.

For the exact list of valid values (characters, moods, locations, SFX,
etc.), generate a cheatsheet by running `scripts/generate-cheatsheet.bat`
(Windows) or `python -m tnh_generate_cheatsheet` (any platform). Keep
that cheatsheet open alongside this guide.


---

## Getting started

### What is a .scene file?

A `.scene` file is a plain text file you write in any text editor
(Notepad, VS Code, Sublime Text — anything works). It describes one
scene: who speaks, what they say, where it happens, and what the
player can choose.

You write the scene in a simple, human-readable format. The compiler
then turns it into Ren'Py code that the game can run. You never touch
Ren'Py or Python directly.

### Where to put scene files

Place your `.scene` files under the `scenes_source/` directory, inside
a subfolder named after the owning character:

```
scenes_source/
  JeanGrey/
    late_night_talk.scene
    library_encounter.scene
  Rogue/
    rooftop_chat.scene
  LauraKinney/
    training_ground.scene
```

The character folder name must match exactly (PascalCase).

### How to compile

**Drag and drop (Windows):** Drop one or more `.scene` files onto
`scripts/compile.bat`. It compiles them and shows the result.
Double-click the script with no files to compile everything in
`scenes_source/`.

**Command line (any platform):**

```
python -m tnh_scene_compiler compile
```

This compiles every `.scene` file found under `scenes_source/`. To
compile specific files:

```
python -m tnh_scene_compiler compile path/to/scene.scene
```

To check your files without writing output:

```
python -m tnh_scene_compiler validate
```

The compiler tells you the file, line number, and a description for
every error it finds.


---

## The header

Every scene starts with a header at the top of the file. One key per
line, then a blank line before the body:

```
Title: Late Night Talk
Scene Id: my_mod_scene_jeangrey_late_night_talk
Character: JeanGrey
Scene Type: cinematic
Trigger: manual
```

| Key | What it means |
|---|---|
| `Title` | A human-readable name for this scene |
| `Scene Id` | A unique identifier — the developer provides this |
| `Character` | The owning character (PascalCase) |
| `Scene Type` | How the scene is presented (see "Scene types" below) |
| `Trigger` | When the scene fires (the developer provides this) |

The developer gives you the exact values for `Scene Id`, `Character`,
`Scene Type`, and `Trigger` when they assign you the scene. You do not
guess these.


---

## Five essential patterns

These five patterns cover 80% of scene writing.

### 1. Location (slugline)

An UPPERCASE line starting with `INT.` (indoor) or `EXT.` (outdoor)
sets the scene location:

```
INT. JEAN'S ROOM - NIGHT
```

The exact text must be a location the project recognizes. Check the
cheatsheet. Common forms:

```
INT. ROGUE'S ROOM - DAY
EXT. MANSION GROUNDS - NIGHT
INT. KITCHEN - DAY
```

### 2. Narration

A plain text paragraph with no speaker name. One blank line on each
side:

```
You wake up to your phone buzzing like crazy.

She sits on the edge of her bed and stares at the floor.
```

### 3. Dialogue

The speaker's name in UPPERCASE on its own line, then the spoken line
right below:

```
JEANGREY
I have something to tell you.

PLAYER
Go ahead.
```

`PLAYER` is the player character. Other valid speaker names are in the
cheatsheet.

### 4. Dialogue with a mood

Put the mood in parentheses on the speaker line:

```
JEANGREY (nervous)
Something happened.

JEANGREY (happy)
Great news!
```

Valid moods vary by character. Check the cheatsheet.

### 5. Choices

```
[[choice]]
= I'm listening.
    JEANGREY
    Thank you.

= Not now.
    JEANGREY (sad)
    ...okay.
[[/choice]]
```

Each option starts with `=` on its own line. The branch body is
indented by 4 spaces. After `[[/choice]]`, the scene continues and
all branches rejoin automatically.

You can put narration, dialogue, conditions, or any other pattern
inside a choice branch.


---

## Parentheticals in depth

A parenthetical can control more than just the mood. You have three
styles.

### Positional order

When you do not name the keys, values are assigned in this fixed
order:

```
(mood, face, arms, look, outfit, stage)
```

Examples:

```
JEANGREY (happy)                          -> mood=happy
JEANGREY (sad, crying)                    -> mood=sad, face=crying
JEANGREY (sad, crying, covering_face)     -> mood=sad, face=crying, arms=covering_face
JEANGREY (vulnerable, worried1, crossed, at_player)
                                          -> mood=vulnerable, face=worried1,
                                             arms=crossed, look=at_player
```

### Named style

Use `key=value` pairs in any order:

```
JEANGREY (mood=sad)
JEANGREY (face=smirk, arms=hips)
JEANGREY (look=away, mood=nervous, arms=fidgeting)
```

### Mixed style — positional first, named second

```
JEANGREY (happy, face=worried1, look=at_player)
```

You cannot put named values before positional ones.
`(face=smirk, happy)` is an error.

### Skipping a positional slot

Use a single underscore `_` to skip a slot. Useful when you only want
to change an attribute that is not first:

```
JEANGREY (_, smirk)              -> face=smirk only
JEANGREY (_, _, crossed)         -> arms=crossed only
```

### Multiline parentheticals

When a line has four or more attributes, break it across two lines for
readability:

```
JEANGREY
(mood=sad, face=sympathetic, arms=shrug, right_arm=neutral, look=at_player, outfit=Pajamas)
You're a terrible liar, [player.petname].
```

### All available attributes

| Attribute | Purpose |
|---|---|
| `mood` | Overall emotional feel (happy, sad, nervous, vulnerable...) |
| `face` | Facial expression (smile, worried1, crying, smirk...) |
| `arms` | Both-arms pose (crossed, hips, shrug...) |
| `left_arm` / `right_arm` | Per-arm pose (named-only, no positional slot) |
| `look` | Where they look (at_player, away, down, up...) |
| `outfit` | Clothing (only when it changes mid-scene) |
| `stage` | Position on stage (left, middle, right) |
| `pose` | Full-body pose preset |

Exact valid values per character are in the cheatsheet.

### Cross-lookup errors

The compiler validates every attribute against the character who owns
the line. If `smirk` is a valid face for JeanGrey but not for Rogue,
using it on a Rogue line is an error. Always check the cheatsheet for
the specific character.


---

## Phone and text messages

### The `(text)` medium

`(text)` on a dialogue line turns it into a text message instead of a
spoken line:

```
JEANGREY (text)
I can't sleep.

JEANGREY (text)
Are you awake?
```

`(text)` is mutually exclusive with visual attributes. A text message
has no face or arms. `(text, face=smirk)` is an error.

### Player replies by text

When the player picks a `[[choice]]` while texting, the option label
is a button — not the actual message. Keep the label short (the
intent), and put the real message in the branch body:

```
[[choice]]
= Ask what's wrong
    PLAYER (text)
    Jean? What's wrong?

    JEANGREY (text)
    It's nothing.

= Ask directly
    PLAYER (text)
    Do you have any idea what time it is? What is it?

    JEANGREY (text)
    Sorry about that.
[[/choice]]
```

At runtime the player picks the short label; the full message then
appears in the chat thread.


---

## Conditions

### `[[if]]`, `[[elif]]`, `[[else]]`

Show different content based on game state or earlier choices:

```
[[if JeanGrey.love >= 500]]

JEANGREY (happy)
I love spending time with you.

[[elif JeanGrey.love >= 200]]

JEANGREY (neutral)
It's nice to hang out.

[[else]]

JEANGREY (distant)
I guess it's okay.

[[/if]]
```

### What you can and cannot use in conditions

| Construct | Allowed? |
|---|---|
| Comparisons: `==`, `!=`, `<`, `<=`, `>`, `>=` | Yes |
| Logic: `and`, `or`, `not` | Yes |
| Literals: integers, floats, strings, `True`, `False`, `None` | Yes |
| Attribute access: `JeanGrey.love`, `player.petname` | Yes |
| `in` / `not in`: `"fire" in JeanGrey.traits` | Yes |
| Parentheses for grouping | Yes |
| Arithmetic (`+`, `-`, `*`, `/`) | No |
| Function calls | No, except developer-registered helpers |
| f-strings, lambdas, comprehensions, slicing | No |

If you need arithmetic or something fancier, ask the developer. They
either register a helper function or help you restructure the logic.


---

## Scene-local state

### `[[set]]` — recording a decision

Record something the player chose so later parts of the scene can
react:

```
[[choice]]
= Ask gently
    [[set asked_nicely]]
    ...

= Ask bluntly
    [[set asked_bluntly]]
    ...
[[/choice]]

[[if asked_nicely]]

JEANGREY (happy)
Thanks for being considerate.

[[else]]

JEANGREY (annoyed)
You're not being very subtle.

[[/if]]
```

### Forms

```
[[set key]]                  # sets key to true
[[set key = value]]          # sets explicit value (true, false, int, "string")
```

### Scope

State only exists for the duration of the scene. It is not saved, not
remembered across scenes. For persistent state (character stats, mod
variables), ask the developer — that requires a `[[mod_set]]`
directive.


---

## More directives

### Labels and goto

By default, choice branches rejoin after `[[/choice]]`. When you need
one branch to jump somewhere else:

```
[[choice]]
= Normal path
    ...

= Skip to the end
    [[goto scene_ending]]
[[/choice]]

Normal flow continues here.

JEANGREY
More dialogue.

[[label scene_ending]]

JEANGREY
Alright, goodnight.
```

Rules:
- Labels are scoped to a single scene. Each label name must be unique.
- `[[goto]]` usually jumps forward. Backward jumps are allowed but
  use them with care — they can create loops.

### Scene chaining — `[[call]]`

At any point (usually at the end), hand off to another scene:

```
[[call my_mod_scene_jeangrey_followup]]
```

The target scene id is given by the developer. The current scene ends
(or resumes after the called scene returns, depending on placement).

### Showing and hiding characters

Change a character's visual state between dialogue blocks without
making them speak:

```
[[show JeanGrey face=worried1 arms=crossed look=at_player]]
[[show JeanGrey look=away]]
[[hide JeanGrey]]
```

Uses the same attributes as parentheticals, but always in `key=value`
form. Common uses:

- Bringing a character on stage: `[[show Rogue stage=left]]`
- Shifting their gaze: `[[show JeanGrey look=away]]`
- Removing a character: `[[hide JeanGrey]]`

### Sound effects (SFX) and pauses

```
[[pause 0.5]]               # 0.5-second silence
[[pause 2]]                 # 2-second silence

[[sfx phone_buzz]]          # plays the sound once
[[sfx phone_buzz 0.3]]      # plays it for 0.3 seconds
```

Valid SFX names are in the cheatsheet.

### Engine effects (FX)

Visual effects the game engine draws (a screen shake, a knock overlay,
a flash). Use `[[fx]]`, not `[[sfx]]`:

```
[[fx phone_buzz()]]          # phone shake + implicit short pause
[[fx knock_on_door()]]       # knock overlay + implicit short pause
```

Parentheses are required, even when empty. Do not confuse the two:
- `[[sfx something]]` plays a sound file.
- `[[fx something()]]` runs a visual effect.

Valid FX names are in the cheatsheet. If what you need is not listed,
ask the developer.

### Phone UI

```
[[phone open]]               # opens the phone
[[phone open JeanGrey]]      # opens on Jean's chat thread
[[phone close]]              # closes the phone
```

Used in cinematic scenes that involve texting. Not needed in `phone`
or `texting` scene types — those already run in phone mode.

### Approval changes

The developer may set up `[[mod_set]]` operations that modify game
state (approval ratings, flags, relationship values). The developer
tells you the exact syntax when it is needed:

```
[[mod_set approval_up JeanGrey 10]]
```

You cannot invent `[[mod_set]]` operations. Each one must be
registered by the developer.


---

## Interpolation

### Putting variables into text

Place a variable path inside single brackets within dialogue or
narration:

```
JEANGREY
Hey [player.petname], good morning.

You knock on [jeangrey.petname]'s door.
```

### Rules

- Only direct variable paths. No expressions, no calculations.
- The root name must be a recognized character or variable.
- Valid interpolation paths are in the cheatsheet.


---

## Scene types

The `Scene Type` header key controls how the scene is presented.

| Scene Type | What it is for | Notes |
|---|---|---|
| `cinematic` | Full-screen story scene with visuals, pauses, SFX | Requires a `Trigger` key |
| `phone` | Phone conversation, mostly text messages | Add `Openness` and `Stage` keys |
| `texting` | Pure text exchange, no visuals at all | All dialogue lines forced to `(text)` |
| `hub_option` | Short scene triggered from a hub menu option | No `Trigger` key |

The developer tells you which type to use. Most scenes are
`cinematic`.


---

## Complete example

A cinematic scene using most of the patterns covered above:

```
Title: Late Night Conversation
Scene Id: my_mod_scene_jeangrey_late_night
Character: JeanGrey
Scene Type: cinematic
Trigger: manual

INT. JEAN'S ROOM - NIGHT

You approach her door. There is no answer, but it's unlocked.
You let yourself in.

[[show JeanGrey stage=middle outfit=Pajamas face=worried1 arms=crossed]]

Jean looks exhausted and disheveled.

[[pause 1]]

JEANGREY (vulnerable, face=worried1, arms=crossed, look=at_player)
[player.petname]? What are you doing here...

JEANGREY (vulnerable)
We can talk in the morning.

[[pause 0.7]]

You gently raise your hand.

[[choice]]
= I couldn't sleep.
    [[set lied_about_sleep]]

    JEANGREY (sad, face=sympathetic, arms=shrug)
    You're a terrible liar.

= Tell me what's wrong.
    [[set asked_directly]]

    JEANGREY (vulnerable)
    You're right. It can't wait.
[[/choice]]

[[pause 1]]

You sit down beside her.

[[show JeanGrey mood=nervous]]

Jean takes a deep breath.

[[pause 1.5]]

JEANGREY (vulnerable, look=away)
I need to tell you something.

[[pause 2]]

The words hang in the air.

[[if lied_about_sleep]]

JEANGREY (sad)
I shouldn't have kept you up.

[[else]]

JEANGREY (vulnerable)
Thank you for coming.

[[/if]]

[[pause 1]]

[[call my_mod_scene_jeangrey_followup]]
```

### A phone scene

```
Title: Rogue Checks In
Scene Id: my_mod_scene_rogue_phone_check_in
Character: Rogue
Scene Type: phone
Trigger: manual

ROGUE (text)
Hey sugar, you up?

ROGUE (text)
Need to ask you somethin'.

[[choice]]
= I'm here.
    ROGUE (text)
    Good.

    ROGUE (text)
    You free tonight?

= What is it?
    ROGUE (text)
    Straight to the point huh.

    ROGUE (text)
    You free tonight?
[[/choice]]
```


---

## Common errors and troubleshooting

### "Unknown mood/face for Character X"

The name you used is not in the character's allowlist. Check the
cheatsheet. If the mood genuinely does not exist, ask the developer.

### "Slot already filled"

You wrote the same slot twice, e.g. `(happy, mood=sad)`. Pick one.

### "Named after positional"

You wrote `(face=smirk, happy)`. Positional values must come first.
Fix: `(happy, face=smirk)` or use all named: `(mood=happy, face=smirk)`.

### "Unknown location"

Your slugline does not match any registered location. Check the
cheatsheet. Exact capitalization matters. Some locations require a
time-of-day suffix like `- NIGHT`.

### "Unknown interpolation path"

You wrote `[player.foo]` but `player.foo` is not in the allowed list.
Check the cheatsheet.

### "Arbitrary expression not allowed"

You wrote a function call or arithmetic in an `[[if]]` or `[[set]]`
that the compiler does not permit. Tell the developer what you are
trying to check — they register a helper or help you restructure.

### "Label 'X' is not defined"

You used `[[goto X]]` but there is no `[[label X]]` in the scene.
Add the label or remove the goto.

### "Loop detected via goto"

A `[[goto]]` creates an infinite loop. Use a forward-pointing label or
add a condition to break out.

### General troubleshooting steps

1. Read the error message — it gives the file, line, and a
   description.
2. Check the cheatsheet for valid values.
3. Look at an existing `.scene` file that does something similar and
   copy the pattern.
4. Ask the developer. Paste the error message exactly as it appears.


---

## What you cannot do

The format deliberately forbids:

- Arbitrary Python or Ren'Py code.
- Defining your own locations, outfits, moods, or SFX — those are
  registered by the developer.
- Calling any function that is not allowlisted.
- Loops (`while`, `for`).
- Writing directly to character stats — only through
  developer-provided `[[mod_set]]` operations.

If you need something the format does not express, ask the developer.
They either add a new directive, register a helper function, or write
that section in `.rpy` themselves and ask you for the dialogue content.
