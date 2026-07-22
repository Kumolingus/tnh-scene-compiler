## Dialogue

A speaker name in UPPERCASE on its own line; the line(s) below are what they
say, ending at the next blank line:

```
JEANGREY
A simple line of dialogue.

JEANGREY (happy)
A line with a mood.

JEANGREY (happy, face=smile)
With mood and face.
```

### The parenthetical

The `(...)` after the speaker sets her visual state. The positional order is
`mood, face, arms, look, outfit, stage`, and every value is checked against
the [allowlist](#allowlist):

```
JEANGREY (happy)                     mood only
JEANGREY (sad, crying)               mood + face, by position
JEANGREY (mood=sad, face=crying)     the same, named
JEANGREY (_, smirk)                  skip mood, set face (the _)
```

Use `_` to skip a positional slot. Named values (`key=value`) may be in any
order but must come *after* any positional ones. `left_arm` and `right_arm`
are named-only. For four or more attributes, put the parenthetical on its
own line under the speaker:

```
JEANGREY
(mood=sad, face=sympathetic, arms=shrug, right_arm=neutral, look=at_player)
You're a terrible liar, [Player.name].
```

> Watch out: put plain (positional) values first and `key=value` values
> after — `(happy, face=smirk)` works, but `(face=smirk, happy)` doesn't.
> Don't set the same slot twice: `(happy, mood=sad)` is an error. And mind
> the separators — a dialogue parenthetical uses **commas**, while the
> [show directive](#show-hide-characters) uses **spaces**.

### Text messages

A `(text)` line goes into the phone thread opened by the
[phone directive](#phone):

```
JEANGREY (text)
This is a phone text message.

PLAYER (text)
The player replies by text.
```

> Watch out: `(text)` can't be combined with visual attributes — a phone
> text has no face, arms, or look.
