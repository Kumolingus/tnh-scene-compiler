## Conditions

`[[if]]` blocks show or skip content based on the game state. Everything
between `[[if ...]]` and its closing `[[/if]]` only plays when the condition
is true.

### Simple if

```
[[if JeanGrey.love >= 500]]

JEANGREY
I really care about you.

[[/if]]
```

> Watch out: every `[[if]]` needs a matching `[[/if]]`. Forgetting it is the
> most common condition error.

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

Some checks answer a plain **yes/no** — does she have a trait, is she in a
mood, is she nearby. Use those on their own:

```
[[if JeanGrey.has("shy")]]
[[if JeanGrey.nearby]]
```

Others give back a **number** — a friendship tier, a count, a stat like
`desire`. Here's the catch: a number on its own counts as "yes" whenever it
isn't zero, and that includes *negative* numbers like the tiers for enemies
or rivals. So a bare number check is almost never what you mean — you nearly
always want to **compare** it with an operator (see
[Comparison operators](#comparison-operators)):

```
[[if get_effective_friendship(JeanGrey, Rogue) >= 2]]   good friends or closer
[[if JeanGrey.get_friendship(Rogue) < 0]]               animosity
[[if JeanGrey.sex_experience > 0]]                       has any experience
```

### Relationship conditions

How a character feels — about the player, and about other characters:

- **Love / Trust** — `JeanGrey.love >= 500` (raw value) or use a tier name
  (`>= medium`). How the character feels about the *player*.
- **Friendship check** — `JeanGrey.friends_with(Rogue)` — yes/no, are these
  two friends.
- **In a relationship** — `are_Characters_in_Partners([JeanGrey], False)` —
  yes/no, is she one of the **player's** partners. Note this one is about the
  player, not about the two characters you name: listing several asks whether
  they are *all* partners of the player, not whether they are dating each
  other.
- **Friendship tier** — `get_effective_friendship(JeanGrey, Rogue)` returns a
  number: enemies `-2`, rivals `-1`, acquaintances `0`, friends `1`, good
  friends `2`, best friends `3`. **Compare it** (`>= 2`, `< 0`).

```
[[if are_Characters_in_Partners([JeanGrey], False)]]
[[if get_effective_friendship(JeanGrey, Rogue) >= 2]]
```

> Watch out: a group of characters goes in **square brackets** —
> `are_Characters_in_Partners([JeanGrey, Rogue], False)`, not
> `(JeanGrey, Rogue)`.

> The second argument is worth understanding. Left at `True`, the check also
> demands that every *other* partner has been told about the character you
> asked about — so it answers `False` for someone who really is a partner, as
> soon as a second partner exists who does not know. Pass `False` for a plain
> "are they together". The Condition Builder offers the two as separate
> entries so you never have to remember this: "In a relationship" and
> "In a relationship, and the others know".

### Character-state conditions

What one character is like, and how she is right now:

- **Trait** — `JeanGrey.has("shy")` — yes/no, does she have this trait
  (granted by the [give_trait directive](#traits)).
- **Mood** — `JeanGrey.mood == "normal"` (her normal mood) or another status.
- **Personality** — `JeanGrey.personality("dominant")` gives back her score
  for that leaning (a number, compare it); add a level to get a yes/no,
  `JeanGrey.personality("dominant", 1)`. See the [Personality directive](#personality)
  for what personalities are.
- **Nearby** — `JeanGrey.nearby` — yes/no, is she close to the player.
- **Character property** — a read-only stat on a companion, always a number:
  `desire`, `breast_size`, `sex_experience`, … Compare it.

```
[[if JeanGrey.has("shy") AND JeanGrey.desire >= 0.5]]
[[if JeanGrey.mood == "mad"]]
```

### Story, location & time conditions

What has already happened, and where things stand in the world:

- **History** — `JeanGrey.did("kissed_player")` — yes/no, has this happened
  (written by the [record directive](#history)).
- **Location** — `get_present_Characters(...)`, `get_Room_Owner(...)` — who's
  where. Often used with `in`: `Rogue in get_present_Characters(...)`.
- **Days since** — `get_time_since(date)` returns a number of days; compare it.

### Scene flags & world state

Choices the player made earlier in this same scene, plus the game's clock
and calendar:

- **Scene flags** — a flag you set earlier in this scene with the
  [set directive](#scene-state) is read back by its bare name:
  `[[if asked_nicely]]`. It only exists for the current scene run.
- **Time of day** — `time_index` is `0` morning, `1` day, `2` evening,
  `3` night: `[[if time_index == 3]]`.
- **Story progress** — `chapter`, `day`, `season`, `weekday` are numbers you
  can compare: `[[if chapter >= 2]]`.

### Combining conditions

Combine any of the above with `AND`, `OR`, `NOT`:

```
[[if JeanGrey.love >= 500 AND JeanGrey.mood == "normal"]]
[[if NOT JeanGrey.has("angry")]]
```

> Capitals are just a habit that makes the joins easy to spot in a long
> condition — `and`, `or`, `not` in lowercase mean exactly the same thing and
> always will. The Condition Builder writes them in capitals.

> Watch out: `AND` binds tighter than `OR` (same as most languages), so
> `a OR b AND c` means `a OR (b AND c)`. When you mix them, add parentheses
> to say exactly what you mean: `(a OR b) AND c`.
