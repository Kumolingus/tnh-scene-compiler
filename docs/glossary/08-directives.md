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
