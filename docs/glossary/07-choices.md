## Choices

Offer the player a menu. Each option starts with `=`; its branch body is
indented four spaces:

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

After a branch runs, flow continues past `[[/choice]]` — unless the branch
ends with a `[[goto ...]]` to rejoin somewhere else.

### Conditional option (only shows if condition is met)

Add a trailing `[[if ...]]` to an option to show it only when the condition
holds:

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

> Watch out: if *every* option is hidden by its condition, the menu is
> silently skipped. Always leave one option with no condition, or guard the
> whole `[[choice]]` with an `[[if]]`.

### Choices during a phone conversation

When the phone is open, the option label is the player's *intent* (a short
description); the actual message goes in the branch as a `PLAYER (text)`
line:

```
[[choice]]
= Ask what's wrong
    PLAYER (text)
    Jean? What's wrong?

= Keep it light
    PLAYER (text)
    lol you up?
[[/choice]]
```
