# Fountain-TNH Format Specification

Version: **1** (initial) Tool: `tnh-scene-compiler`

This document is the authoritative reference for the **Fountain-TNH** scene authoring format consumed by the `tnh-scene-compiler` tool. It
defines every syntactic construct the compiler accepts, the validation rules applied at compile time, and the Ren'Py code the compiler
emits.

For a writer-facing quick-start with no grammar theory, see the companion `Authoring_Guide_For_Writers.md` (generated per project by
`tnh_generate_cheatsheet`). This document targets developers integrating the compiler into a TNH mod project.

---

## 1. Overview and goals

### 1.1 Goals

- Writers with zero programming or Ren'Py knowledge produce working
  scenes using a plain text editor.
- The format is readable by a non-technical reader.
- All authoring content is text, version-controllable, diff-friendly.
- Engine-level features the scenes need (moods, visuals, conditions,
choices, state, phone mode, SFX, scene chaining) are expressible with a small fixed vocabulary.
- Errors are caught at compile time, with source file + line pointing
  at the mistake.
- Zero runtime overhead: `.scene` -> `.rpy` is a build step; the game
  runs vanilla Ren'Py.

### 1.2 Non-goals

- **Not pure Fountain.** Files use a superset of the Fountain
screenplay format. Final Draft, Highland, and other Fountain editors will not compile them. Writers edit in plain text editors (VS Code,
Notepad, Sublime).
- **Not a general-purpose DSL.** The format is deliberately narrow:
anything the grammar does not express is either refactored by the writer or escalated to the developer.
- **Not for every scene.** Interactive hubs and menus with re-entrant
flow stay in hand-written `.rpy`. Writers may author the content inside those hubs (the options' payload scenes), not the hub shell itself.

---

## 2. File conventions

| Property        | Value                                                                      |
| --------------- | -------------------------------------------------------------------------- |
| Extension       | `.scene`                                                                   |
| Encoding        | UTF-8, LF line endings, no BOM                                             |
| Granularity     | One scene per file                                                         |
| Source location | `scenes_source/<Character>/<scene_name>.scene` (relative to project root)  |
| Compiled output | `game/{mod_prefix}/scenes/<Character>/<scene_name>.rpy` (see `output` key) |

The **Scene Id** is derived from the title page, not the file path. The source directory tree under `scenes_source/` is organisational --
the compiler does not enforce a match between the directory name and the `Character` field, but keeping them aligned is strongly
recommended.

The `scenes_source/_allowlists/` subtree is reserved for YAML allowlist files and is excluded from scene discovery.

---

## 3. Title page

The title page is the first block of the file: key-value metadata lines at the top, one per line, `Key: Value`, no indentation, followed by
a mandatory blank line before the body.

```
Title: Jean's Greeting
Scene Id: my_mod_dialogue_jeangrey_greeting
Character: JeanGrey
Scene Type: cinematic
Trigger: sleeping
Description: Late-night check-in after the training session.
Conditions: JeanGrey.love >= 300
Priority: 100
Repeatable: false
Tags: my_mod_chapter_one
Location: JEANGREY'S ROOM
```

### 3.1 Field reference

| Key           | Required | Type             | Meaning                                          |
| ------------- | -------- | ---------------- | ------------------------------------------------ |
| `Title`       | Yes      | string           | Human-readable name (not used at runtime).       |
| `Scene Id`    | Yes      | snake_case id    | Ren'Py label + `all_Events` key. [^id]           |
| `Character`   | Yes      | PascalCase       | Owning character. Must match `characters.yaml`   |
| `Scene Type`  | Yes      | enum             | `cinematic`/`phone`/`texting`/`hub_option` [^st] |
| `Trigger`     | [^tr]    | enum             | Event trigger. [^trv]                            |
| `Description` | No       | free-form string | One-line summary for tooling (not at runtime).   |
| `Conditions`  | No       | expression       | Condition expression; commas = `and`. [^cond]    |
| `Priority`    | No       | int              | Event priority. Default: 50.                     |
| `Repeatable`  | No       | bool             | Can fire more than once. Default: `false`.       |
| `Tags`        | No       | comma-sep list   | Extra flags on event entry. Mod-prefixed.        |
| `Location`    | No       | slugline text    | Implies `set_the_scene()`. Validated.            |
| `Format`      | No       | int              | Override format version. Default: `1`.           |

[^id]: Must start with `{mod_prefix}`. Unique across all project scenes.
[^st]: Drives compilation target (see section 13).
[^tr]: Required for `cinematic`; optional otherwise.
[^trv]: `manual`, `sleeping`, `waking`, `traveling`,
  `getting_ready_for_bed`, or custom mod-prefixed flag. Defaults to
  `manual` when omitted for non-cinematic types.
[^cond]: Evaluated by TNH's `ConditionClass`.

Any key not listed above is a compile error.

---

## 4. Comments

Within the body, a line where `#` is the first non-whitespace character is a comment. The compiler strips it from the generated `.rpy`.
Inline `#` trailing a normal line is **not** a comment -- write comments on their own line.

```
# This section covers the middle act.

JEANGREY (happy)
I'm fine.                    # this is NOT treated as a comment
```

`#` was chosen over HTML-style `<!-- -->` or `//` to keep the format ASCII-clean and Ren'Py-idiomatic. HTML-style comments are a compile
error.

---

## 5. Body patterns

The body starts after the blank line that ends the title page. It contains free-flowing narration, dialogue blocks, sluglines, and
directives.

### 5.1 Narration (action blocks)

Plain text paragraphs with no preceding speaker become narrator lines. Separate from surrounding content with blank lines.

```
You wake up to your phone buzzing like crazy.

She sits on her bed and sighs.
```

Compiles to `"You wake up to your phone buzzing like crazy."` using the default narrator character.

### 5.2 Dialogue lines

```
CHARACTER
Dialogue text.

CHARACTER (mood)
Dialogue text.

CHARACTER (mood, face, arms, look, outfit, stage)
Dialogue text.

CHARACTER (face=worried1, arms=crossed)
Dialogue text.

CHARACTER
(mood=sad, face=sympathetic, arms=shrug, right_arm=neutral, look=at_player)
Dialogue text.
```

Rules:

- **Speaker name** in UPPERCASE, on its own line, matches a character
tag registered in the allowlists (`JEANGREY`, `ROGUE`, `PLAYER`, `NARRATOR`). Plain text lines without a preceding speaker are narration
(section 5.1).
- **Parenthetical** (optional) follows the speaker on the same line
  OR on the next line (multiline form, preferred for 4+ attributes).
- **Dialogue text** on the next line(s), ends at the first blank line.
- A blank line separates one dialogue block from the next.

Speaker mapping: spoken dialogue emits `ch_<PascalCase>` (the TNH convention for the Ren'Py Character sayer, e.g. `ch_JeanGrey`). The
PascalCase form (`JeanGrey`) is the `CompanionClass` instance that owns the attributes (mood/face/outfit) and is the target for
`change_mood()` / `change_face()` calls, but is not a valid Ren'Py Sayer.

### 5.3 Sluglines and scene setup

Fountain-style sluglines set the location.

```
INT. JEANGREY'S ROOM
```

Rules:

- Must start with `INT.`, `EXT.`, `INT./EXT.`, or `I/E.`.
- The text after the prefix is looked up in the project's locations allowlist. Each project ships a `locations.yaml` (and optional
  `locations_overrides.yaml`) mapping human-readable names to TNH location IDs:
  ```yaml
  values:
    - name: "JEANGREY'S ROOM"
      location_id: "loc_XavierSchool_JeanGreyRoom"
    - name: "PLAYER'S ROOM"
      location_id: "loc_XavierSchool_PlayerRoom"
  ```
- If the slugline text is not in the table, the compiler reports an error with fuzzy-match suggestions.
- Compiles to `$ set_the_scene(location = "loc_...", greetings = False)`.
- For **cinematic** scenes, the codegen also passes
  `show_Characters = False` to `set_the_scene()` so the destination
  starts with a clean stage. The writer then opts in to specific
  characters via `[[show <C>]]` or by having them speak. This mirrors
  the TNH base-game event pattern.
- Phone / texting / hub_option scenes do not get this cleanup -- they manage character visibility through their callers.

The title page's `Location:` key implies an initial slugline; if the body opens with its own slugline, the body slugline takes precedence.

#### Time-of-day suffixes

Sluglines may carry a time suffix:

```
INT. JEANGREY'S ROOM - NIGHT
INT. XAVIER SCHOOL - GIRLS HALLWAY - MORNING
```

The suffix (` - MORNING`, ` - DAY`, ` - EVENING`, ` - NIGHT`) is stripped before the location lookup. The codegen emits `$ time_index = N`
before `set_the_scene()` so the background renders with the correct lighting.

| Suffix      | `time_index` value |
| ----------- | ------------------ |
| `- MORNING` | 0                  |
| `- DAY`     | 1                  |
| `- EVENING` | 2                  |
| `- NIGHT`   | 3                  |

#### Cinematic end-of-scene cleanup

Cinematic scenes emit `$ set_the_scene(show_Characters = False, silent = True)` right before `$ ongoing_Event = False` at the end of the
label. This drops every visible character so gameplay resumes on a clean stage -- characters shown during the cinematic do not linger after
the event ends. The author does not need to write a trailing `[[hide <C>]]` for every character used in the scene.

---

## 6. Parenthetical grammar

Parentheticals control the visual state of a character on a dialogue line. They appear in `()` after the speaker name.

### 6.1 Slots and positional order

```
(mood, face, arms, look, outfit, stage)
```

The positional order is fixed. Changing it requires a format version bump.

### 6.2 Three valid styles

**1. Positional only** -- tokens without `=`, assigned left to right:

```
JEANGREY (happy)                                   -> mood=happy
JEANGREY (sad, crying, covering_face)              -> mood=sad, face=crying, arms=covering_face
```

**2. Named only** -- `key=value`, any order:

```
JEANGREY (mood=sad, face=crying)
JEANGREY (face=smirk, arms=hips)
```

**3. Mixed** -- positional first, named second. Never named then positional:

```
JEANGREY (happy, face=worried1, look=at_player)
  -> mood=happy (positional), face=worried1 (named),
     look=at_player (named)
```

### 6.3 Skipping a positional slot

`_` as a positional token skips that slot (leave the value unchanged):

```
JEANGREY (_, smirk)                                -> face=smirk
JEANGREY (_, _, crossed)                           -> arms=crossed
```

### 6.4 Valid keys

`mood`, `face`, `arms`, `left_arm`, `right_arm`, `look`, `outfit`, `stage`, `pose`. Any other key is a compile error.

`left_arm` and `right_arm` are named-only -- they have no positional slot. Use them when the `arms` preset (both arms at once) is not
precise enough.

### 6.5 Multiline form

For readability when 4+ attributes are present, put the parenthetical on the line after the speaker:

```
JEANGREY
(mood=sad, face=sympathetic, arms=shrug, right_arm=neutral, look=at_player, outfit=Pajamas)
You're a terrible liar, [player.petname].
```

### 6.6 Cross-lookup error

When a value is invalid for the slot assigned by position but valid for a different slot, the compiler names the plausible alternative:

```
scenes/jeangrey/greeting.scene:42:10
  JEANGREY (worried1)
            ^^^^^^^^
  "worried1" is not a valid mood for JeanGrey.
  It is a valid face -- did you mean (face=worried1)?
```

This is always blocking -- the compiler never auto-corrects. Writers fix explicitly.

### 6.7 Error conditions

All of the following are blocking at compile time:

| Condition              | Example               | Error                                                 |
| ---------------------- | --------------------- | ----------------------------------------------------- |
| Named after positional | `(face=smirk, happy)` | Positional values must come before named ones.        |
| Slot filled twice      | `(happy, mood=sad)`   | Slot 'mood' is already set to 'happy'.                |
| Unknown key            | `(???=value)`         | Unknown attribute '???'. Valid: mood, face, arms, ... |
| Unknown value for slot | `(worried1)` as mood  | Cross-lookup suggestion (section 6.6).                |

Ambiguity by position is not an error: a value valid for multiple slots gets assigned to the slot its position selects. `(neutral)` is
always `mood=neutral`, even if `neutral` is also a valid face. Writers wanting the face use `(_, neutral)` or `(face=neutral)`.

---

## 7. Dialogue medium

The reserved parenthetical value `text` switches a line to phone-text medium:

```
JEANGREY (text)
I can't settle tonight.

JEANGREY (text)
I'm not panicking.
```

`text` is mutually exclusive with visual attributes -- phone texts have no face/arms/look. Combining them is a compile error.

`spoken` is the default medium. It is legal but redundant to write explicitly.

When the speaker is `PLAYER`, `(text)` compiles to `$ send_text(current_phone_Chat, "...")`. For any other character, it compiles to `$
receive_text(<Character>, "...")`.

---

## 8. Directives

All directives are `[[...]]` blocks on their own line. One directive per line.

### 8.1 pause

```
[[pause 0.5]]
[[pause 1]]
[[pause 2]]
```

Decimal or integer seconds. Compiles to `$ renpy.pause(N)`.

### 8.2 sfx (sound effects)

```
[[sfx phone_buzz]]
[[sfx phone_buzz 0.3]]
```

Second argument (optional) is duration in seconds. Sound files are expected under `game/{mod_prefix}/sounds/sfx/<name>.ogg`. The name is
validated against the SFX allowlist at compile time. Unknown name is a compile error.

Compiles to `$ renpy.sound.play("<name>.ogg")`, optionally followed by `$ renpy.pause(N)` when a duration is specified.

### 8.3 fx (engine effects)

```
[[fx phone_buzz()]]
[[fx knock_on_door()]]
[[fx bamf(0.5, 0.5, 1.0)]]
```

Calls an engine-level visual/transient effect. Parentheses are required even when no arguments are passed. Positional arguments only --
keyword arguments are a compile error.

Names are validated against `_allowlists/fx.yaml`. Unknown name is a compile error.

#### Compilation output

The emitted code depends on the effect's `call_mode` metadata in `fx.yaml`:

- **`call_mode: label`** (effects defined as Ren'Py labels in `effects.rpy`, `animations.rpy`, etc.): compiles to `call <name>(args)`.
- **No `call_mode`** (plain Python functions like `phone_buzz`, `knock_on_door`): compiles to `$ <name>(args)`.

#### Cinematic auto-prefixing

In **cinematic** scenes (`Scene Type: cinematic`), the compiler automatically emits the `cinematic_` variant of the effect name. Writers
always write the base name:

```
[[fx bamf()]]
```

The compiler emits `call cinematic_bamf()` in cinematic scenes and `call bamf()` in other scene types. For a handful of effects with
non-standard cinematic names, a fixed override table maps the base name to the cinematic variant (e.g. `knock_on_door` -> `cinematic_knock`,
`phone_buzz` -> `cinematic_phone_buzz`).

The `cinematic_` variants do **not** appear in `fx.yaml` -- they are auto-derived at compile time. Writers never need to reference them
directly.

#### fx.yaml entry structure

Each entry in `fx.yaml` uses the `effects` key (not `values`) and carries metadata beyond the name:

```yaml
effects:
- name: bamf
  source_file: game/displayables/effects.rpy
  source_line: 132
  signature: bamf(x = 0.5, y = 0.5, initial = 1.0, ...) -> None
  call_mode: label
- name: phone_buzz
  source_file: game/core/mechanics/phone.rpy
  source_line: 3
  signature: "phone_buzz(x: float = 0.5, ...) -> None"
- name: LauraKinney_animations_unsheathes_claws
  source_file: game/characters/LauraKinney/animations.rpy
  source_line: 1
  signature: LauraKinney_animations_unsheathes_claws(..., hand = "both") -> None
  call_mode: label
  param_choices:
    hand:
    - '"both"'
    - '"left"'
    - '"right"'
```

| Field           | Required | Meaning                                              |
| --------------- | -------- | ---------------------------------------------------- |
| `name`          | Yes      | Function/label name as written in `[[fx]]`.          |
| `signature`     | Yes      | Full Python signature (for GUI and cheatsheet).      |
| `call_mode`     | No       | `"label"` = Ren'Py label → `call`; absent → `$`.     |
| `param_choices` | No       | Param name → valid values list (GUI autocompletion). |
| `source_file`   | No       | Provenance (for allowlist refresh).                  |
| `source_line`   | No       | Provenance (for allowlist refresh).                  |

#### Directive disambiguation

| Directive                          | Use for                   | Validated against             |
| ---------------------------------- | ------------------------- | ----------------------------- |
| `[[sfx name]]`                     | A `.ogg` sound file       | `sfx.yaml`                    |
| `[[fx name(...)]]`                 | Visual effect function    | `fx.yaml`                     |
| `[[run call]]`                     | Persistent state mutation | `run_operations.yaml`         |
| `[[approval Char axis +/-N]]`      | Move love/trust           | enums + `characters.yaml`     |
| `[[give_trait Char trait]]`        | Grant a trait             | `characters` + `traits.yaml`  |
| `[[remove_trait Char trait]]`      | Revoke a trait            | `characters` + `traits.yaml`  |
| `[[record Char event]]`            | Record history event      | `characters` + `history.yaml` |
| `[[set_personality Char trait N]]` | Set personality score     | `characters` + `person.yaml`  |

Rule of thumb: if the target is a sound file, use `[[sfx]]`. If it is a Python function that draws or animates something for a beat and
returns, use `[[fx]]`. If it grants or revokes a trait, use `[[give_trait]]` / `[[remove_trait]]`. If it records a history event, use
`[[record]]`. If it sets a personality score, use `[[set_personality]]`. If it nudges a character's love/trust, use `[[approval]]`. For any
other persistent state mutation not covered by a dedicated directive, use `[[run]]`.

### 8.4 set (scene-local state)

```
[[set lied_about_sleep]]
[[set attempts = 3]]
[[set wants_to_keep = true]]
```

- Single token sets that key to `true` in the scene-local state dict.
- `key = value` sets an explicit value (`true`, `false`, int, quoted string).
- Scene-local state lives in a dict reset per scene run; accessed in conditions as bare names: `[[if lied_about_sleep]]`.
- For mod-wide persistent state, use `[[run]]` instead (section 8.12).

Function calls are not allowed in `[[set]]` values.

### 8.5 label

```
[[label after_phone_check]]
```

- Labels are local to the scene. Must be unique within a scene.
- Compiles to a Ren'Py dot-label (`.after_phone_check:`) scoped to the enclosing scene label.

### 8.6 goto

```
[[goto after_phone_check]]
```

- Jumps to a label within the same scene. Forward and (discouraged) backward jumps are both legal.
- Compiles to `jump .after_phone_check`.
- The target must be defined in the scene. Unresolved targets are a compile error.

### 8.7 if / elif / else

```
[[if <expression>]]
...
[[elif <expression>]]
...
[[else]]
...
[[/if]]
```

- `<expression>` is evaluated at runtime against the restricted grammar defined in section 9.
- Scene-local state is accessible by bare name (`lied_about_sleep`, `attempts > 2`).
- Character attributes are accessible by dotted path (`JeanGrey.love >= 500`).
- Helper functions are callable only if registered in `condition_functions.yaml`. Arbitrary Python is not allowed.
- Unknown symbols are a compile error with suggestions.
- Nesting is allowed.

### 8.8 choice

```
[[choice]]
= Option 1 text
    [[set branch_a]]
    Prose or directives inside the branch.

    CHARACTER
    Response.

= Option 2 text
    [[set branch_b]]
    ...
[[/choice]]
```

Rules:

- Each option starts with `=` on its own line, followed by the option label text.
- Branch body is indented (4 spaces).
- Branches may contain any directive or dialogue.
- Branches implicitly fall through to the statement after
  `[[/choice]]`. Use `[[goto <label>]]` at the end of a branch for
  non-default rejoin points.
- Options may have a display condition via a trailing `if`:
  ```
  = Give her the gift  [[if player.has_item("flower")]]
      ...
  ```
If all options fail their condition the menu silently skips -- writers must provide a fallback option or guard the entire `[[choice]]` with
`[[if]]`.

#### Phone replies inside choices

When a choice happens while the phone overlay is open (or in a `phone` / `texting` scene), the option **label** should be a short
description of the player's intent, **not** the SMS text itself. The actual message goes in the branch body via a `PLAYER (text)` line:

```
[[choice]]
= Ask what's wrong
    PLAYER (text)
    Jean? What's wrong?

    [[set asked_whats_wrong]]
    ...

= Ask directly
    PLAYER (text)
    Do you have any idea what time it is? What is it?

    [[set asked_directly]]
    ...
[[/choice]]
```

This mirrors the TNH base-game idiom: the menu label reads as a neutral intent ("Have her come over", "Pass"), and the branch body sends the
colloquial message. Authoring the SMS as the menu label is visually incoherent with the rest of the game -- Ren'Py menus are list-style
buttons, not chat bubbles.

### 8.9 call (scene chaining)

```
[[call my_mod_dialogue_jeangrey_discussion]]
```

- Chains another scene at any point in the current one.
- Target scene id must exist in the project's compiled set.
- Compiles to `call <target_label>`.

### 8.10 show / hide

```
[[show JeanGrey stage=middle outfit=Pajamas face=worried1 arms=crossed]]
[[show JeanGrey look=at_player]]
[[hide JeanGrey]]
```

- Used between dialogue blocks when a visual change is not tied to a
  specific line of dialogue.
- Same slot vocabulary as the dialogue parenthetical, all named.
- `[[hide]]` removes a character from the scene; no attributes
  accepted.
- `[[show]]` with a `stage` attribute compiles to
  `$ add_Characters(<Char>, direction = "<mapped>", fade = False)`.
- Other attributes compile to the corresponding `change_*` calls.

### 8.11 phone (UI switch)

```
[[phone open]]
[[phone open JeanGrey]]
[[phone close]]
```

- Opens/closes the in-game phone overlay.
- Opening with a character argument opens directly onto that
  character's text thread (compiles to `$ open_texts(<Char>)`).
- Opening without a character compiles to
  `$ renpy.show_screen("phone_screen")`.
- Closing compiles to `$ renpy.hide_screen("phone_screen")`.

### 8.12 run (persistent state)

```
[[run JeanGrey.trait("my_mod_discussed_topic") = true]]
```

- For persistent state changes the scene must commit (traits, History, attributes).
- Only operations from the `run_operations.yaml` allowlist are accepted. Arbitrary Python is banned.
- Compiles to `$ <call_text>` verbatim (the call text has already passed through the safe-subset expression parser).
- Prefer the dedicated directives (`[[give_trait]]`,
  `[[remove_trait]]`, `[[record]]`, `[[set_personality]]`,
  `[[approval]]`) when they cover the operation -- they enforce
  tighter validation and produce better error messages. Use `[[run]]`
  only for operations that have no dedicated directive.

### 8.13 approval

```
[[approval JeanGrey love +large_stat]]
[[approval Rogue trust -medium_stat]]
[[approval LauraKinney love +25]]
```

- Calls TNH's `update_approval(Character, flavor, value)` helper.
- **Character**: PascalCase identifier; cross-checked against `characters.yaml`.
- **Axis**: exactly one of `love` or `trust` -- the only flavours TNH branches on. Other values are a compile error.
- **Sign**: mandatory `+` or `-` immediately before the magnitude.
  No implicit sign.
- **Magnitude**: either a stat-tier name or a positive integer literal (>= 1).

| Stat tier      | Value |
| -------------- | ----- |
| `tiny_stat`    | 2     |
| `small_stat`   | 5     |
| `medium_stat`  | 10    |
| `large_stat`   | 20    |
| `massive_stat` | 40    |

Named tiers are preferred; they keep the emitted line readable and benefit from any base-game rebalance.

- Compiles to `$ update_approval(<Character>, "<axis>", [-]<magnitude>)`.
- Use `[[approval]]` instead of `[[run update_approval(...)]]`. The
  dedicated directive enforces the closed enums and produces better
  error messages.

### 8.14 give_trait

```
[[give_trait JeanGrey shy]]
```

- Grants a character trait.
- Character is validated against `characters.yaml`.
- Trait is validated against `traits.yaml` (with fuzzy suggestions on mismatch).
- Compiles to `$ JeanGrey.give_trait("shy")`.

### 8.15 remove_trait

```
[[remove_trait JeanGrey shy]]
```

- Revokes a character trait.
- Same validation as `[[give_trait]]`.
- Compiles to `$ JeanGrey.remove_trait("shy")`.

### 8.16 record

```
[[record JeanGrey kissed_player]]
```

- Records a history event for a character.
- Character is validated against `characters.yaml`.
- Event is validated against `history_events.yaml` (with fuzzy suggestions).
- Compiles to `$ JeanGrey.History.add("kissed_player")`.

### 8.17 set_personality

```
[[set_personality JeanGrey dominant 3]]
```

- Sets a personality score for a character.
- Character validated against `characters.yaml`.
- Trait validated against `personalities.yaml` (with fuzzy suggestions).
- Value must be an integer.
- Compiles to `$ JeanGrey.set_personality("dominant", 3)`.

---

## 9. Expression grammar (safe subset)

The compiler parses `[[if]]`, `[[elif]]`, and option-condition expressions through a custom safe-subset parser -- not `eval`, not
`ast.literal_eval`. The grammar is fixed and deliberately narrow. Extending it requires a format version bump.

### 9.1 Allowed constructs

| Construct           | Example                           | Notes                                  |
| ------------------- | --------------------------------- | -------------------------------------- |
| Boolean operators   | `a and b`, `a or b`, `not a`      | Short-circuit semantics.               |
| Comparisons         | `x == y`, `x != y`, `x >= y`      | -------------------------------------- |
| Chained comparisons | `0 < x < 100`                     | Same semantics as Python.              |
| Membership          | `"x" in collection`               | -------------------------------------- |
| Integer literals    | `0`, `42`, `-17`                  | -------------------------------------- |
| Float literals      | `0.5`, `-1.25`                    | -------------------------------------- |
| String literals     | `"text"`, `'text'`                | Double or single quotes.               |
| Boolean literals    | `True`, `False`                   | Capitalised.                           |
| Null literal        | `None`                            | -------------------------------------- |
| Parentheses         | `(a or b) and c`                  | For grouping only.                     |
| Attribute access    | `JeanGrey.love`, `player.petname` | Root must resolve (see 9.2).           |
| Nested attribute    | `JeanGrey.wardrobe.current`       | Plain attribute per hop, no subscript. |
| Bare identifier     | `asked_nicely`                    | Resolved as scene-local state key.     |
| Function call       | `my_mod_check(JeanGrey, "love")`  | Must be in `condition_functions.yaml`. |

### 9.2 Allowed identifier roots

The left side of the first `.` (or a standalone name) must be one of:

- A character name registered in `characters.yaml` (e.g. `JeanGrey`, `Rogue`, `LauraKinney`).
- `player`.
- A time/world key: `day`, `time_index`, `weekday`, `season`, `chapter`, `chapter_day`, `season_day`.
- A scene-local state key previously introduced by `[[set]]`.
- A function name registered in `condition_functions.yaml`.

Any other root is a compile error with a "Did you mean ...?" suggestion.

### 9.3 Forbidden constructs

| Construct                 | Example          | Error message                            |
| ------------------------- | ---------------- | ---------------------------------------- |
| Arithmetic                | `a + 1`, `x * 2` | Not allowed. Use a helper or split.      |
| Subscript/indexing        | `x[0]`, `d["k"]` | Not allowed. Use attribute or helper.    |
| Slicing                   | `x[1:3]`         | Not allowed.                             |
| f-strings                 | `f"{x}"`         | Not allowed.                             |
| Lambdas                   | `lambda x: x`    | Not allowed.                             |
| Comprehensions            | `[x for x in y]` | Not allowed.                             |
| Ternary                   | `a if b else c`  | Not allowed. Use `[[if]]`/`[[else]]`.    |
| Walrus                    | `(x := 1)`       | Not allowed.                             |
| Bitwise                   | `a & b`, `~a`    | Not allowed.                             |
| Unary minus on identifier | `-JeanGrey.love` | Only allowed on numeric literals.        |
| Non-allowlisted fn call   | `eval("...")`    | Function not allowlisted for conditions. |

### 9.4 Rationale

- The grammar fits every condition observed in real TNH mod scenes (approval checks, trait presence, state flags, chapter/season gating).
- Banning arithmetic and arbitrary calls prevents writers from inlining game logic that belongs in the mod code.
- Banning subscript/indexing forces use of named helpers, which the developer reviews before allowlisting.
- The failure mode is always a clear compile-time error, never silent runtime misbehaviour.

### 9.5 Error reporting format

```
scenes/jeangrey/greeting.scene:58:6
  [[if JeanGrey.love + Rogue.love >= 1000]]
                    ^
  Arithmetic is not allowed in [[if]] expressions.
  Suggestion: register a helper function (e.g. total_love(a, b)) in
  _allowlists/condition_functions.yaml, then call it here.
```

---

## 10. Interpolation

Variables are referenced with `[path]` Ren'Py-style inside any string (dialogue, option label, narration):

```
JEANGREY
Hey [player.petname], wake up.

You knock on [jeangrey.petname]'s door.
```

- Allowed paths are registered in the interpolation allowlist (`interpolation.yaml` + `interpolation_custom.yaml`). Typical entries include:
`player.name`, `player.petname`, `player.first_name`, `<Character>.petname`, `<Character>.name`, `<Character>.Player_petname`, `day`,
`time_index`, `season`.
- Unknown path is a compile error with fuzzy-match suggestions.
- Arbitrary expressions in brackets (`[x + 1]`) are forbidden.
- Compiles to native Ren'Py `[...]` interpolation, which is rendered at runtime. The compiler does not escape brackets -- they pass through
  verbatim to the `.rpy` output.

---

## 11. Scene-local state vs mod state

### 11.1 Scene-local state

- Written via `[[set key]]` or `[[set key = value]]`.
- Read via bare names in expressions (`[[if key]]`, `[[if key == "x"]]`).
- Lives in a `_scene_state` dict initialised at scene entry, discarded at scene exit.
- Use for branching decisions inside one scene.

### 11.2 Mod state

- Written via `[[run]]`, `[[approval]]`, `[[give_trait]]`, `[[remove_trait]]`, `[[record]]`, or `[[set_personality]]`.
- Calls through to Character traits, History, personality scores, or registered mod attributes.
- Persists across scenes and saves.

### 11.3 Enforcement

A scene never writes to base-game state directly; it may read any game state in `[[if]]` conditions. `[[set]]` targeting a Character
attribute is a compile error -- use `[[run]]`.

### 11.4 Scene state injection

Compiled scenes initialise their scene-local dict from a standalone Python module at entry:

```python
$ _scene_state = dict(getattr({mod_prefix}_runtime, 'scene_state', None) or {})
```

This lets your mod pass context into a scene before calling it — for example, setting which character is the target of a conversation, or
which attitude branch to take. In normal gameplay the value is `None` and the dict comes out empty.

`{mod_prefix}_runtime` is a Python module created by the runtime stub. Its globals live outside the Ren'Py store, so they survive across
`renpy.invoke_in_new_context` boundaries (useful if you need to preview scenes in isolation).

#### Condition-function wrapping

Calls to allowlisted condition functions where every argument is a bare Character or `player` Name are wrapped by the codegen:

```python
# Source:
[[if my_mod_is_ready(JeanGrey)]]

# Compiled:
if my_mod_testing_eval_condition(
    'my_mod_is_ready',
    my_mod_is_ready,
    (JeanGrey,),
    ('JeanGrey',),
):
```

The wrapper consults `{mod_prefix}_runtime.condition_overrides`. In normal gameplay the attribute is `None` and the wrapper short-circuits
to `fn(*args)` — the runtime cost is one `getattr` and one `is None` check. This enables previewing specific scene branches by overriding
condition results without meeting the actual game conditions.

Calls with literal or attribute arguments are compiled directly and not wrapped.

---

## 12. Allowlists

The compiler uses YAML allowlists to validate every name that appears in a scene against the set of values the game actually supports. Two
layers of allowlists are merged at load time:

1. **Base allowlists** (`allowlists_base/` inside the
   `tnh-scene-compiler` package) -- ship with the tool and cover
   TNH's base-game characters, locations, moods, faces, arms,
   outfits, looks, stages, SFX, and interpolation paths.
2. **Project allowlists** (`scenes_source/_allowlists/` or the path
   configured under `project_allowlists` in
   `tnh_scene_compiler.yaml`) -- project-specific additions. The mod
   layer extends the base: new characters, new moods, custom SFX,
   mod-specific operations, etc.

Base and project layers are merged with set-union semantics: if a value appears in either layer, it is valid. Per-character dicts are merged per
key. The `include_base_allowlists` config option (default `true`) controls whether the base layer is included at all.

### 12.1 Allowlist files

| #  | File(s)                                    | Validates                            | Layer       |
| -- | ------------------------------------------ | ------------------------------------ | ----------- |
| 1  | `characters.yaml`                          | Speakers, show/hide, approval        | auto/manual |
| 2  | `moods/_shared.yaml`, `moods/<Char>.yaml`  | `mood` slot values                   | auto        |
| 3  | `faces/<Char>.yaml`                        | `face` slot values                   | auto        |
| 4  | `arms/<Char>.yaml`                         | `arms`/`left_arm`/`right_arm`        | auto        |
| 5  | `outfits/<Char>.yaml`                      | `outfit` slot values                 | auto        |
| 6  | `poses/<Char>.yaml`                        | `pose` slot values                   | auto        |
| 7  | `looks.yaml`                               | `look` slot values (global)          | auto        |
| 8  | `stages.yaml`                              | `stage` slot values (global)         | auto        |
| 9  | `locations.yaml` + `*_overrides`           | Slugline → location ID               | auto+manual |
| 10 | `sfx.yaml`                                 | `[[sfx]]` names                      | auto        |
| 11 | `interpolation.yaml` + `*_custom`          | `[...]` interpolation paths          | auto+manual |
| 12 | `run_operations.yaml`                      | `[[run]]` operations                 | manual      |
| 13 | `fx.yaml`                                  | `[[fx]]` functions + signatures      | auto        |
| 14 | `condition_functions.yaml`                 | `[[if]]`/`[[elif]]` functions        | manual      |
| 15 | `traits.yaml`                              | `[[give_trait]]`/`[[remove_trait]]`  | auto        |
| 16 | `history_events.yaml`                      | `[[record]]` event names             | auto        |
| 17 | `personalities.yaml`                       | `[[set_personality]]` traits         | auto        |
| 18 | `_meta.yaml`                               | Metadata only (not validated)        | auto        |

### 12.2 Regenerating allowlists

Use **Refresh allowlists** in the app's project settings to regenerate the auto-generated allowlist
files from the TNH base game and the project source. Manual allowlists (`run_operations.yaml`,
`condition_functions.yaml`, `locations_overrides.yaml`, `interpolation_custom.yaml`) are not overwritten
— the developer maintains them by hand. `fx.yaml` is auto-generated with signatures and `call_mode` metadata.

Writers can read allowlists for reference but should not edit them. If a new mood/face/location is needed, the developer adds it to the mod
and refreshes the allowlists.

### 12.3 Allowlist file structure notes

#### fx.yaml

Uses an `effects` key (not `values`) at the top level. Each entry carries `signature`, optional `call_mode`, and optional `param_choices`
metadata. See section 8.3 for the full entry structure and how `call_mode` drives codegen behaviour.

#### arms/<Char>.yaml

Arm allowlists only include **standing poses** -- non-standing poses (sex scene poses, special interaction poses) are excluded from the
allowlist because the compiled scenes target standing character presentation. The file separates `arms` (both-arm presets), `left_arm`, and
`right_arm` into distinct top-level keys.

#### moods/<Char>.yaml

Mood entries include a `faces` metadata field listing the face expressions associated with that mood in the base game:

```yaml
values:
- name: aggressive
  source_file: ...
  faces: angry2,angry3,appalled2
- name: alert
  source_file: ...
  faces: neutral,squint,suspicious1
```

This metadata is informational -- the compiler does not enforce that a `face` parenthetical matches its sibling `mood`'s face list, but the
GUI and cheatsheet use it to suggest coherent face/mood combinations to writers.

---

## 13. Scene types and compilation targets

| Scene Type   | Compiles to           | Event reg | Trigger     |
| ------------ | --------------------- | --------- | ----------- |
| `cinematic`  | label + `_events.rpy` | Yes       | **Yes**     |
| `phone`      | `label <scene_id>:`   | No        | No (manual) |
| `texting`    | `label <scene_id>:`   | No        | No (manual) |
| `hub_option` | `label <scene_id>:`   | No        | No (manual) |

**Key behaviours per type:**

- **`cinematic`**: Body wrapped with `$ ongoing_Event = True` /
`False`. End-of-scene cleanup via `set_the_scene(show_Characters = False, silent = True)`. Event registered with Trigger/Conditions from
title page.
- **`phone`**: Called by mod phone dispatch code.
- **`texting`**: All dialogue forced to `text` medium; other
  directives work normally.
- **`hub_option`**: Called by a hub `.rpy` file. Minimal wrapping.

### 13.1 Cinematic scene structure

```
# Auto-generated from scenes_source/JeanGrey/greeting.scene. Do not edit by hand.

init python:
    my_mod_scene_metadata["my_mod_dialogue_jeangrey_greeting"] = {
        "character": "JeanGrey",
        "scene_type": "cinematic",
        ...
    }

label my_mod_dialogue_jeangrey_greeting:
    $ ongoing_Event = True
    $ _scene_state = dict(getattr(my_mod_runtime, 'scene_state', None) or {})

    $ set_the_scene(location = "loc_XavierSchool_JeanGreyRoom", greetings = False, show_Characters = False)

    "She sits on her bed and sighs."
    ch_JeanGrey "Hey [player.petname], you awake?"
    "You nod silently."
    ch_JeanGrey "Good. I need you here tonight."

    $ set_the_scene(show_Characters = False, silent = True)
    $ ongoing_Event = False
    return
```

### 13.2 Events registry

The `_events.rpy` file is a consolidated output containing every cinematic scene's `define all_Events[...] = {...}` block:

```
# Auto-generated by tnh-scene-compiler from scenes_source/**/*.scene.
# Do not edit by hand.

define all_Events["my_mod_dialogue_jeangrey_greeting"] = {
    "conditions": ConditionClass("JeanGrey.love >= 300"),
    "flags": {"sleeping"},
    "priority": 100,
    "repeatable": False,
}
```

Phone, texting, and hub_option scenes do not appear in `_events.rpy`.

---

## 14. Compilation pipeline overview

Open the app and use **Quick compile** or **Open project** to compile scenes. Without explicit file
selection, the compiler discovers all `.scene` files under the configured `scenes_source` directory
(excluding `_allowlists/`).

### 14.1 Pipeline stages

```
.scene (source)
  -> lexer   -> tokens
  -> parser  -> AST
  -> validator (names, expressions, labels, state, allowlists)
  -> codegen -> .rpy
```

### 14.2 Failure behaviour

On failure:

- Returns exit code **1**.
- Emits errors as `file.scene:line:col: <message>` to stderr.
- Writes nothing to the output folder. Partial output is never produced.

On success:

- Returns exit code **0**.
- Writes one `.rpy` per scene under
  `<output>/<Character>/`.
- Writes `<output>/_events.rpy` with all `all_Events[...]` entries.
- Writes nothing else.

### 14.3 Validate-only mode

Use the **Validate** button in the editor to parse and validate without writing output. Same error
reporting as compile.

### 14.4 Config resolution

The compiler looks for `tnh_scene_compiler.yaml` by walking up from the working directory (or the first
file's parent). The app resolves this automatically when you open a project.

---

## 15. Scene metadata and preview infrastructure

The compiler generates metadata and runtime stubs that enable scene discovery, dispatching, and previewing. Even if your mod doesn't build
a dedicated preview tool, the metadata is useful for listing available scenes and their properties at runtime.

### 15.1 Per-scene metadata block

Above each compiled `label`, the codegen emits an `init python:` block declaring one entry in the `{mod_prefix}_scene_metadata` dict. This
block describes the scene's character, type, state variables, conditions, and called scenes:

```python
init python:
    my_mod_scene_metadata['my_mod_dialogue_jeangrey_greeting'] = {
        "character": "JeanGrey",
        "scene_type": "cinematic",
        "description": "Late-night check-in after the training session.",
        "state_specs": [
            {"path": "checked_immediately", "kind": "bool",
             "choices": [False, True], "default": False},
        ],
        "condition_specs": [
            {"name": "my_mod_check_readiness",
             "args": ["JeanGrey"], "kind": "bool"},
        ],
        "called_scenes": [
            "my_mod_dialogue_jeangrey_discussion",
        ],
        "uses_target": False,
    }
```

**`state_specs`** are harvested by walking the AST: `[[set X]]` / `[[set X = V]]` declarations, plus bare Name references and `==` / `!=`
comparisons against literals in `[[if]]`, `[[elif]]`, and `[[choice]]` conditions.

**`condition_specs`** are harvested the same way: every function call where the target is in `condition_functions.yaml` and every argument
is a bare Character / `player` Name produces one entry, deduplicated within the scene.

**`called_scenes`** lists every scene id reached via `[[call <id>]]` inside the body, including calls nested in `[[if]]` / `[[choice]]`
branches (order-preserving, deduplicated).

Removing a `.scene` removes its `.rpy` on the next compile and the metadata entry disappears with it -- no central registry to
resynchronise.

### 15.2 Condition wrapper

The codegen emits a condition wrapper function (`{mod_prefix}_testing_eval_condition`) via the `testing_eval.rpy.tmpl` runtime stub.
Eligible condition calls are routed through this wrapper, which allows overriding condition results at runtime — useful for previewing
specific dialogue branches without meeting the actual game conditions (see §11.4).

### 15.3 Runtime module

The runtime stub creates a `{mod_prefix}_runtime` Python module registered in `sys.modules`. This module's globals (`scene_state`,
`condition_overrides`) survive Ren'Py's rollback mechanism and `renpy.invoke_in_new_context` boundaries. In normal gameplay both
attributes are `None`. See §11.4 for how your mod can use `scene_state` to pass context into a scene.

### 15.4 Metadata init

The `metadata_init.rpy.tmpl` template creates the `{mod_prefix}_scene_metadata` dict at store scope so compiled scene `init python:` blocks
can populate it at boot.

### 15.5 Compiler unit tests

The `tnh-scene-compiler` ships with a pytest test suite under `tests/` covering the lexer, parser, expression parser, parenthetical parser,
directive parser, validator, codegen, and end-to-end compilation. Fixtures are `.scene` files under `tests/fixtures/`.

---

## 16. Error reporting contract

The compiler's error messages are part of the authoring experience. Required properties:

- One error per mistake, not a cascade.
- `path:line:col` prefix always present.
- Error message phrased in plain English, action-oriented ("is not a valid mood", "did you mean...", "slot already filled").
- No stack traces or Python tracebacks visible to the writer.
- Exit 1 on any error; success is total silence (or a brief stats line when `--verbose` is set).

### 16.1 Error catalogue

| Class                    | Example              | Error pattern                       |
| ------------------------ | -------------------- | ----------------------------------- |
| Missing title-page field | No `Scene Id`        | Missing required field 'Scene Id'.  |
| Unknown character        | `ZORRO (happy)`      | Not a known character.              |
| Unknown slot value       | `(worried1)` as mood | Cross-lookup suggestion (§6.6).     |
| Unknown slot key         | `(???=x)`            | Unknown attribute. Valid: mood, ... |
| Named after positional   | `(face=a, happy)`    | Positional must come before named.  |
| Slot filled twice        | `(happy, mood=sad)`  | Slot 'mood' already set to 'happy'. |
| Unknown slugline         | `INT. THE MOON`      | Not registered. Did you mean ...?   |
| Unknown SFX              | `[[sfx nope]]`       | Not registered. Did you mean ...?   |
| Unknown FX               | `[[fx nope()]]`      | Not registered. Did you mean ...?   |
| FX keyword arg           | `[[fx f(k=0.25)]]`   | Keywords not allowed in `[[fx]]`.   |
| Unknown interpolation    | `[player.foo]`       | Not a known interpolation path.     |
| Unresolved goto          | `[[goto nowhere]]`   | Label not defined in this scene.    |
| Duplicate label          | Two `[[label x]]`    | Defined twice (line N and M).       |
| Arbitrary expr in set    | `[[set x = foo(1)]]` | Function calls not allowed in set.  |
| Exclusive medium         | `(text, face=smirk)` | Cannot combine text with visuals.   |
| Forbidden expression     | `[[if x + 1 > 0]]`   | Arithmetic not allowed in `[[if]]`. |
| Non-allowlisted fn       | `[[if eval("...")]]` | Not allowlisted for conditions.     |

---

## 17. What the format deliberately does not support

The compiler rejects, with an error pointing at the rejected construct:

- **Arbitrary Python expressions** outside of `[[if]]`.
- **Function calls** not present in the run-operations or condition-functions allowlists.
- **Inline `.rpy` escape hatches.** There is no "raw Ren'Py" mode.
- **Screen definitions, transforms, `init python:` blocks, image declarations.** These belong in hand-written `.rpy`.
- **Loops or while constructs.** Flow control is limited to branching via `[[if]]` and `[[choice]]`.

When a scene needs something the format does not express, the writer escalates to the developer, who either:

1. Adds a helper to the appropriate allowlist (`run_operations.yaml`, `condition_functions.yaml`, `fx.yaml`).
2. Adds a new directive to the format (bumps the format version, regenerates scenes).
3. Takes the scene out of the `.scene` pipeline and hand-writes the label in `.rpy`.

---

## 18. Format versioning

The format carries a version number. The title page may override it:

```
Format: 1
```

Default: the project's configured default version (currently **1**). Breaking changes to the grammar (new positional slot order, new
required title-page field, changed expression semantics) bump the major version. The compiler refuses scenes with an unsupported version.

Non-breaking additions (new optional title-page key, new directive, new allowlist file) do not require a version bump -- they are
backwards-compatible.

Initial version: **1**.

---

## Appendix A: tnh_scene_compiler.yaml reference

The configuration file lives at the project root and is discovered by walking up from the current directory.

```yaml
# REQUIRED: your mod's unique prefix (lowercase snake_case).
mod_prefix: my_mod

# Directory containing .scene source files (relative to this file).
scenes_source: scenes_source/

# Mod-specific allowlists directory (relative to this file).
project_allowlists: scenes_source/_allowlists/

# Output directory for compiled .rpy files (relative to this file).
output: game/my_mod/scenes/

# Include the base TNH allowlists shipped with the compiler.
include_base_allowlists: true

# Optional: paths for the allowlist-refresh tool.
# refresh:
#   base_game: ../TheNullHypothesis/
#   mod_root: .
```

| Key                       | Required | Default                        | Description                                             |
| ------------------------- | -------- | ------------------------------ | ------------------------------------------------------- |
| `mod_prefix`              | Yes      | ------------------------------ | Unique prefix (`[a-z][a-z0-9_]*`). [^mp]                |
| `scenes_source`           | No       | `scenes_source/`               | Root directory for `.scene` files.                      |
| `project_allowlists`          | No       | `scenes_source/_allowlists/`   | Directory for project-specific allowlist YAMLs.             |
| `output`                  | No       | `game/{prefix}/scenes/`        | Output directory for compiled `.rpy` files.             |
| `include_base_allowlists` | No       | `true`                         | Merge base TNH allowlists beneath the project layer.        |
| `refresh.base_game`       | No       | `../TheNullHypothesis/`        | Path to the TNH base game (for the refresh tool).       |
| `refresh.mod_root`        | No       | `.`                            | Path to the mod root (for the refresh tool).            |

[^mp]: Used in label names, runtime module names, and metadata dict
names.

---

## Appendix B: Runtime stubs

Clicking **Create project** in the app (with prefix `my_mod`) generates:

1. `tnh_scene_compiler.yaml` -- project configuration (Appendix A).
2. `runtime_stub.rpy` -- creates the `{mod_prefix}_runtime` Python module in `sys.modules`.
3. `metadata_init.rpy` -- initialises the `{mod_prefix}_scene_metadata` dict at store scope.
4. `testing_eval.rpy` -- the condition-override wrapper function.

These `.rpy` files must be placed into the mod's `game/` directory. The `mod_prefix` placeholder is replaced with the actual prefix during
generation.

---

## Appendix C: Complete minimal example

### Source: `scenes_source/JeanGrey/greeting.scene`

```
Title: Jean's Morning Greeting
Scene Id: my_mod_dialogue_jeangrey_greeting
Character: JeanGrey
Scene Type: cinematic
Trigger: waking
Conditions: JeanGrey.love >= 200
Priority: 75
Repeatable: false

INT. JEANGREY'S ROOM - MORNING

# Jean is already awake when the player arrives.

JEANGREY (happy)
Good morning, [player.petname].

[[choice]]
= Greet her warmly
    PLAYER
    Morning, Jean. Sleep well?

    [[set greeted_warmly]]

    JEANGREY (happy, face=smile)
    Better than usual, actually.

= Be direct
    PLAYER
    We need to talk about yesterday.

    [[set was_direct]]

    JEANGREY (sad, face=worried1)
    I know. I've been thinking about it too.
[[/choice]]

[[if greeted_warmly]]
JEANGREY
Thanks for asking. It means a lot.
[[/if]]

[[if was_direct]]
JEANGREY (_, sympathetic)
Let's sit down.

[[approval JeanGrey love +small_stat]]
[[/if]]
```

### Config: `tnh_scene_compiler.yaml`

```yaml
mod_prefix: my_mod
scenes_source: scenes_source/
project_allowlists: scenes_source/_allowlists/
output: game/my_mod/scenes/
include_base_allowlists: true
```

### Compile

Open the app and click **Compile** (or **Quick compile** with the file selected).

### Output

- `game/my_mod/scenes/JeanGrey/greeting.rpy` -- the compiled label.
- `game/my_mod/scenes/_events.rpy` -- the consolidated event registry.
