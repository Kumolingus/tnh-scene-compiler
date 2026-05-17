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

JEANGREY (happy, face=smile, pose=sitting)
With mood, face, and pose.
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

```
[[if JeanGrey.love >= 500]]           Love check (raw value)
[[if JeanGrey.has("shy")]]            Trait check
[[if JeanGrey.mood == "normal"]]      Normal mood
[[if JeanGrey.mood == "mad"]]         Status check
[[if JeanGrey.friends_with(Rogue)]]   Friendship check
[[if JeanGrey.did("kissed_player")]]  History check
[[if JeanGrey.nearby]]                Proximity check
```

Combine with `and`, `or`, `not`:

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
[[show JeanGrey mood=happy, face=smile, pose=sitting]]
[[hide JeanGrey]]
```

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
