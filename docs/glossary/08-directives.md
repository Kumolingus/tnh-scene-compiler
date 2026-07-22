## Directives

Directives are `[[...]]` blocks, each on its own line. They do the things a
plain dialogue or narration line can't: play a sound, change who's on
screen, branch, nudge a relationship, and so on.

### Effects

Visual / animation effects. The parentheses are required, even with no
arguments inside:

```
[[fx knock_on_door()]]
[[fx phone_buzz()]]
[[fx smack()]]
```

> In [cinematic scenes](#cinematic-scene), the compiler auto-selects the
> [cinematic variant](#cinematic-variant-of-an-effect). Write
> `[[fx bamf()]]` — the compiler handles the rest, and you
> never write a `cinematic_` name yourself.

> Watch out: the parentheses are required (`[[fx smack()]]`, not
> `[[fx smack]]`), and only positional arguments are allowed —
> `[[fx bamf(x=0.25)]]` is a compile error.

### Sound effects

```
[[sfx door_open]]
[[sfx phone_buzz]]
[[sfx door_open 2.0]]
```

An optional duration (in seconds) can follow the sound name: `[[sfx name]]` or `[[sfx name 2.0]]`.

> Watch out: `[[sfx]]` plays a sound *file* — no parentheses. If you want a
> visual effect (a function), that's `[[fx name()]]` instead.

### Pause

Hold for a beat — seconds, decimal or whole:

```
[[pause 1.5]]
```

### Show / Hide characters

`[[show]]` puts a character on screen — or updates how one who's already
there looks; `[[hide]]` takes a character off screen. Use them between
dialogue lines, when a visual change isn't tied to a spoken line. The
attributes are the same as a [dialogue parenthetical](#the-parenthetical),
all written as `key=value`:

```
[[show JeanGrey mood=happy]]
[[show JeanGrey mood=happy face=smile]]
[[show JeanGrey stage=middle outfit=Pajamas]]
[[hide JeanGrey]]
```

Valid keys: `mood`, `face`, `arms`, `left_arm`, `right_arm`, `outfit`,
`look`, `stage`, `fade`. `[[hide JeanGrey]]` takes no attributes. For a soft
entrance or exit, add a per-character fade: `[[show JeanGrey mood=happy fade=true]]`
and `[[hide JeanGrey fade]]`.

> Watch out: attributes are separated by **spaces, never commas** —
> `[[show JeanGrey mood=happy, face=smile]]` will not compile. `left_arm`
> and `right_arm` have no positional slot (they're named-only), and the arm
> poses in the palette are standing poses only.

### Fade to / from black

A full-screen cinematic fade — distinct from the per-character `fade`
above. Use it to skip over elided time:

```
[[fade to black]]
You spend the next few hours talking, the tension slowly bleeding away.
[[fade from black]]
```

An optional duration overrides the default: `[[fade to black 0.6]]`.

> Watch out: this fades the *whole screen*. To fade a single character in or
> out, use the per-character `fade` on `[[show]]` / `[[hide]]` above. Pair a
> `to` with a `from`; a stray repeat is a harmless no-op.

### Approval changes

Nudge how a character feels about the player. The axis is `love` or
`trust`; the sign (`+` or `-`) is mandatory:

```
[[approval JeanGrey love +small_stat]]
[[approval JeanGrey trust -medium_stat]]
```

Tiers: `tiny_stat` (+2), `small_stat` (+5), `medium_stat` (+10), `large_stat` (+20), `massive_stat` (+40). A plain number also works (`+25`). Named tiers are preferred.

> Watch out: the axis is only `love` or `trust`, and the sign is mandatory —
> `[[approval JeanGrey love small_stat]]` (no sign) is a compile error.

### Traits

Grant or revoke a character trait:

```
[[give_trait JeanGrey shy]]
[[remove_trait JeanGrey shy]]
```

> Watch out: the trait name is checked against the [allowlist](#allowlist) —
> a typo is a compile error (with a "did you mean…?" suggestion).

### History

A character's history is a permanent record of things that have happened to
them — a first kiss, a confession, a fight. `[[record]]` writes an event
into it, and it sticks across scenes and saved games. Later scenes react to
the past by checking it (the
[History condition](#story-location-time-conditions),
`JeanGrey.did("...")`).

```
[[record JeanGrey kissed_player]]
```

> Watch out: the event name must be a known history event, checked when you
> compile.

### Personality

A character's personality is a set of named leanings — `dominant`,
`submissive`, `protective`, `neurotic`, … — each held as a small number. The
game uses them to vary how a character behaves and which lines she gets, so
nudging one shapes who she becomes over time. `[[set_personality]]` sets a
leaning's score (a whole number); check it later in a
[condition](#conditions) (`JeanGrey.personality("dominant")`).

```
[[set_personality JeanGrey dominant 3]]
```

> Watch out: the score is a whole number, and the personality name is
> checked against the [allowlist](#allowlist).

### Phone

```
[[phone open JeanGrey]]
JEANGREY (text)
Hey, are you free?
[[phone close]]
```

`[[phone open JeanGrey]]` opens straight onto that character's text thread;
`[[phone open]]` with no name just opens the phone.

### Scene state

[Scene-local](#scene-local-vs-persistent-state) flags that live only for this
one scene run. Set one, then read it by bare name in a
[condition](#conditions):

```
[[set asked_nicely]]
[[set mood = "tense"]]

[[if asked_nicely]]
JEANGREY
Thanks for asking nicely.
[[/if]]
```

> Watch out: `[[set]]` is scene-local — it's forgotten when the scene ends,
> and you can't call a function in its value. For anything that must stick
> across scenes and saves, use the persistent directives
> ([approval](#approval-changes), [give_trait](#traits), [record](#history),
> [set_personality](#personality), or
> [run](#persistent-state-advanced)) — not `[[set]]`.

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

> Watch out: labels are local to the scene, and `[[goto]]` must point at one
> defined in the same scene. Prefer forward jumps — backward jumps are legal
> but easy to turn into an accidental loop.

### Call another scene

```
[[call another_scene_id]]
```

> Watch out: the target must be a real compiled scene id in the project (the
> `Scene Id` from its [title page](#title-page)). To reuse a shared beat,
> give it its own scene and call it here.

### Persistent state (advanced)

Most persistent changes have their own directive above —
[approval](#approval-changes), [give_trait](#traits), [record](#history),
[set_personality](#personality). `[[run]]` is the
catch-all for the rare change that has none: it calls a ready-made operation
your developer set up for the project. The operation names are specific to
your project, so a real call looks like this (yours will differ):

```
[[run my_project_record_choice(JeanGrey, "keep")]]
```

> Watch out: prefer the dedicated directives when one fits — they give
> clearer errors. Only operations your project has set up are accepted; if
> what you need isn't available, ask the developer.
