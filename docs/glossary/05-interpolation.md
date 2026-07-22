## Interpolation

Drop a live value into any line — dialogue, narration, or an option label —
with `[square brackets]`:

```
JEANGREY
Morning, [Player.name]. Sleep okay?

You knock on [JeanGrey.petname]'s door.
```

Common paths:

- `Player.name`, `Player.first_name`, `Player.petname` — the player.
- `<Character>.petname` — what the player calls that character.
- `<Character>.name` — their full name.
- `<Character>.Player_petname` — what that character calls the player.
- `day`, `season`, `time_index` — world values.

> Watch out: names are **case-sensitive** — it's `Player` and `JeanGrey`
> (PascalCase), never `player` or `jeangrey`. Only paths in the
> [allowlist](#allowlist) work; an
> unknown one is a compile error (with a suggestion). You can't put an
> expression in the brackets — `[day + 1]` is not allowed, only a single
> value path.
