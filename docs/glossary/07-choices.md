## Choices

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

### Conditional option (only shows if condition is met)

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
