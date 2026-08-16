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

### Saying a number the game works out

The same brackets can hold a call to one of the project's allowlisted
functions, so a value the game computes can be said out loud:

```
KARAKY
Her window opens in [my_project_days_until_window(Target)] days.
```

It is the same list of functions you use in a
[condition](#conditions) — anything you can ask in an `[[if]]`, you can also
say. Which lets you get the plural right:

```
[[if my_project_days_until_window(Target) == 1]]
KARAKY
Her window opens tomorrow.
[[else]]
KARAKY
Her window opens in [my_project_days_until_window(Target)] days.
[[/if]]
```

> Watch out: names are **case-sensitive** — it's `Player` and `JeanGrey`
> (PascalCase), never `player` or `jeangrey`. Only paths in the
> [allowlist](#allowlist) work; an
> unknown one is a compile error (with a suggestion). You can't put an
> expression in the brackets — `[day + 1]` and `[some_check(X) + 1]` are not
> allowed, only a single value path or a single function call. If the wording
> around a number gets awkward, ask your developer for a function that returns
> the whole phrase — the scene format cannot do arithmetic, on purpose.
