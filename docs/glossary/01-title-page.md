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

> Watch out: `Scene Id` must be unique across the whole project and start
> with your project's prefix. `Character` must match a real character
> exactly (PascalCase, e.g. `JeanGrey`). And don't forget the blank line
> between the title block and the body — without it the first body line is
> read as another title field.
