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
