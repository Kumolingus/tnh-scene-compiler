## Title page

Every scene starts with a title block — one `Key: Value` per line, no
indentation — followed by a blank line before the body begins:

```
Title: A short description
Scene Id: my_project_unique_id
Character: JeanGrey
Scene Type: cinematic
Trigger: manual
Description: Optional longer description.
```

**Required:** `Title`, `Scene Id`, `Character`, `Scene Type` (plus `Trigger`
for cinematic scenes).

**Scene types:** `cinematic`, `phone`, `texting`, `hub_option`

### Cinematic scene fields

A [cinematic](#cinematic-scene) scene fires itself when the game state
matches. These optional fields decide when. They are ordinary title-page
lines — same `Key: Value` shape, in the same block as the required fields,
above the blank line that starts the body:

```
Title: Jean waits up for you
Scene Id: my_project_jean_waits_up
Character: JeanGrey
Scene Type: cinematic
Trigger: sleeping
Conditions: JeanGrey.love >= 300
Priority: 100
Repeatable: false
Location: JEANGREY'S ROOM

INT. JEANGREY'S ROOM - NIGHT

She's still awake when you come in.

JEANGREY (gentle)
I couldn't sleep either.
```

Read together: *when the player goes to sleep, if Jean's love is 300 or
more, play this in her room — once.*

- **Trigger** — when it becomes eligible: `manual`, `sleeping`, `waking`,
  `traveling`, `getting_ready_for_bed`.
- **Conditions** — a condition expression (see [Conditions](#conditions)); a
  comma means `and`.
- **Priority** — higher wins when several scenes are eligible at once
  (default 50).
- **Repeatable** — `true` to let it fire more than once (default `false`).
- **Location** — sets the opening location (same names as a
  [slugline](#locations)).

### Scenes about someone chosen while playing

Sometimes a scene is written once but played about a *different* character
each time — a doctor reading whichever girl the player picked from his menu,
a confession naming the other woman. Add `Target: true` and write `Target`
wherever you would write her name:

```
Title: The fertility reading
Scene Id: my_project_fertility_reading
Character: Karaky
Scene Type: hub_option
Target: true

KARAKY
Let me look at [Target.name].

[[if my_project_is_very_fertile(Target)]]
KARAKY
She runs hot. More than she should.
[[/if]]
```

The game decides who `Target` is when it plays the scene, so you write one
file instead of one per character.

- Use it in a [condition](#conditions) anywhere a character goes:
  `[[if some_check(Target)]]`.
- Use `[Target.name]`, `[Target.petname]` and the other character paths in
  your lines, exactly like `[JeanGrey.name]`.

> Watch out: `Target` cannot **speak** and cannot be shown or hidden — only
> the named characters can. Her expressions differ from one girl to the next,
> and the compiler has no way to know which one will be handed in, so it
> refuses rather than let a face break on the wrong character. Write the
> scene with a named speaker talking *about* her. And `Target` only exists
> when you declared `Target: true` — using it otherwise is an error, not a
> blank.

> Watch out: `Scene Id` must be unique across the whole project and start
> with your project's prefix. `Character` must match a real character
> exactly (PascalCase, e.g. `JeanGrey`). And don't forget the blank line
> between the title block and the body — without it the first body line is
> read as another title field.
