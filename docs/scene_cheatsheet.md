# Scene cheatsheet

Copy-paste reference for `.scene` files. Every example is ready to use.

---

## Title page

Every scene starts with a title block, followed by a blank line:

```
Title: A short description
Scene Id: my_project_unique_id
Character: JeanGrey
Scene Type: cinematic
Trigger: manual
Description: Optional longer description.
```

**Scene types:** `cinematic`, `phone`, `texting`, `hub_option`

---

## Locations

```
INT. KITCHEN
INT. JEANGREY'S ROOM
INT. DANGER ROOM - NIGHT
```

Time suffixes: `- MORNING`, `- DAY`, `- EVENING`, `- NIGHT`

---

## Dialogue

```
JEANGREY
A simple line of dialogue.

JEANGREY (happy)
A line with a mood.

JEANGREY (happy, face=smile)
With mood and face.
```

> **Note:** Arm poses listed in the palette/allowlists are standing poses only.

### Text messages

```
JEANGREY (text)
This is a phone text message.

PLAYER (text)
The player replies by text.
```

---

## Narration

Any line that isn't a speaker, directive, or location:

```
The room falls silent. She looks out the window.
```

---

## Interpolation

Use square brackets for dynamic text:

```
JEANGREY
Hey, [player.petname]. How's [player.first_name] doing?
```

---

## Conditions

### Simple if

```
[[if JeanGrey.love >= 500]]

JEANGREY
I really care about you.

[[/if]]
```

### If / else

```
[[if JeanGrey.mood == "normal"]]

JEANGREY
Everything's fine.

[[else]]

JEANGREY
I don't want to talk right now.

[[/if]]
```

### If / elif / else

```
[[if JeanGrey.love >= 500]]

JEANGREY
You mean so much to me.

[[elif JeanGrey.love >= 200]]

JEANGREY
We're getting along well.

[[else]]

JEANGREY
Hey.

[[/if]]
```

### Condition shortcuts

The most common checks at a glance (the editor's Condition Builder writes
these for you — see the section headings below for what each means):

```
[[if JeanGrey.love >= 500]]           Love check (raw value)
[[if JeanGrey.has("shy")]]            Trait check
[[if JeanGrey.mood == "normal"]]      Normal mood
[[if JeanGrey.mood == "mad"]]         Status check
[[if JeanGrey.friends_with(Rogue)]]   Friendship check
[[if JeanGrey.did("kissed_player")]]  History check
[[if JeanGrey.nearby]]                Proximity check
[[if JeanGrey.desire >= 0.5]]         Character property (a number, compare it)
```

### Comparing numbers vs yes/no

Some checks answer **yes/no** (a trait, a mood, "are they nearby") — use
them bare. Others return a **number** (a friendship tier, a count, a stat
like `desire`) — you must **compare** it, or the check is true whenever the
number is non-zero, which is rarely what you mean. The Condition Builder
shows a "Compare:" row for these; by hand, add an operator and value:

```
[[if get_effective_friendship(JeanGrey, Rogue) >= 2]]   good friends or closer
[[if JeanGrey.get_friendship(Rogue) < 0]]               animosity
[[if JeanGrey.sex_experience > 0]]                       has any experience
```

### Relationship conditions

- **Love / Trust** — `JeanGrey.love >= 500` (raw value) or use a tier name
  (`>= medium`). How the character feels about the *player*.
- **Friendship check** — `JeanGrey.friends_with(Rogue)` — yes/no, are these
  two friends.
- **In a relationship** — `are_Characters_in_Partners([JeanGrey, Rogue])` —
  yes/no, are they dating each other.
- **Friendship tier** — `get_effective_friendship(JeanGrey, Rogue)` returns a
  number: enemies `-2`, rivals `-1`, acquaintances `0`, friends `1`, good
  friends `2`, best friends `3`. **Compare it** (`>= 2`, `< 0`).

```
[[if are_Characters_in_Partners([JeanGrey, Rogue])]]
[[if get_effective_friendship(JeanGrey, Rogue) >= 2]]
```

### Character-state conditions

- **Trait** — `JeanGrey.has("shy")` — yes/no, does she have this trait.
- **Mood** — `JeanGrey.mood == "normal"` (her normal mood) or another status.
- **Personality** — `JeanGrey.personality("bold")`, optionally with a level.
- **Nearby** — `JeanGrey.nearby` — yes/no, is she close to the player.
- **Character property** — a read-only stat on a companion, always a number:
  `desire`, `breast_size`, `sex_experience`, … Compare it.

```
[[if JeanGrey.has("shy") and JeanGrey.desire >= 0.5]]
[[if JeanGrey.mood == "mad"]]
```

### Story, location & time conditions

- **History** — `JeanGrey.did("kissed_player")` — yes/no, has this happened.
- **Location** — `get_present_Characters(...)`, `get_Room_Owner(...)` — who's
  where. Often used with `in`: `Rogue in get_present_Characters(...)`.
- **Days since** — `get_time_since(date)` returns a number of days; compare it.

Combine any of the above with `and`, `or`, `not`:

```
[[if JeanGrey.love >= 500 and JeanGrey.mood == "normal"]]
[[if not JeanGrey.has("angry")]]
```

---

## Choices

```
[[choice]]
= Tell her the truth
    JEANGREY (happy)
    Thank you for being honest.

= Lie to her
    JEANGREY (angry)
    I can tell you're not being sincere.

= Stay silent
    She looks at you, waiting.
[[/choice]]
```

### Conditional option (only shows if condition is met)

```
[[choice]]
= Comfort her
    JEANGREY (happy)
    That means a lot.

= Kiss her [[if JeanGrey.love >= 500]]
    JEANGREY (blushing)
    Oh...!
[[/choice]]
```

---

## Directives

### Effects

```
[[fx knock_on_door()]]
[[fx phone_buzz()]]
[[fx smack()]]
```

> In cinematic scenes, the compiler auto-selects the cinematic
> variant. Write `[[fx bamf()]]` — the compiler handles the rest.

### Sound effects

```
[[sfx door_open]]
[[sfx phone_buzz]]
[[sfx door_open 2.0]]
```

An optional duration (in seconds) can follow the sound name: `[[sfx name]]` or `[[sfx name 2.0]]`.

### Pause

```
[[pause 1.5]]
```

### Approval changes

```
[[approval JeanGrey love +small_stat]]
[[approval JeanGrey trust -medium_stat]]
```

Tiers: `tiny_stat` (+2), `small_stat` (+5), `medium_stat` (+10), `large_stat` (+20), `massive_stat` (+40). Sign is mandatory.

### Show / Hide characters

```
[[show JeanGrey mood=happy]]
[[show JeanGrey mood=happy face=smile]]
[[hide JeanGrey]]
```

Attributes are separated by spaces (not commas). Valid keys:
`mood`, `face`, `arms`, `left_arm`, `right_arm`, `outfit`, `look`, `stage`, `fade`.

### Phone

```
[[phone open JeanGrey]]
JEANGREY (text)
Hey, are you free?
[[phone close]]
```

### Scene state

```
[[set asked_nicely]]
[[set mood = "tense"]]

[[if asked_nicely]]
JEANGREY
Thanks for asking nicely.
[[/if]]
```

### Labels and jumps

```
[[label start_loop]]

JEANGREY
Want to try again?

[[choice]]
= Yes
    [[goto start_loop]]
= No
    JEANGREY
    Okay, see you later.
[[/choice]]
```

### Call another scene

```
[[call another_scene_id]]
```

---

## Comments

```
# This line is ignored by the compiler.
```

---

## Complete example

```
Title: Morning in the kitchen
Scene Id: my_project_morning_kitchen
Character: JeanGrey
Scene Type: cinematic
Trigger: manual
Description: Jean and the player chat over breakfast.

INT. KITCHEN

The smell of coffee fills the air.

JEANGREY (happy)
Good morning, [player.petname]!

[[choice]]
= Good morning, Jean!
    [[approval JeanGrey love +small_stat]]
    JEANGREY (happy)
    Did you sleep well?

= *yawn*
    JEANGREY (amused)
    Not a morning person, huh?
[[/choice]]

[[if JeanGrey.love >= 500]]

JEANGREY (gentle)
I made you some coffee. Just the way you like it.

[[else]]

JEANGREY
There's coffee on the counter if you want some.

[[/if]]

[[fx knock_on_door()]]

JEANGREY (surprised)
Who could that be?

The door opens

PLAYER
It can't be...

Your eyes widen

IT'S...

JOHN CENAAAAAAAA
```
