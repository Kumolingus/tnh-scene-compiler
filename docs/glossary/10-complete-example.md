## Complete example

```
Title: Morning in the kitchen
Scene Id: my_project_morning_kitchen
Character: JeanGrey
Scene Type: cinematic
Trigger: manual
Description: Jean and the player chat over breakfast.

INT. KITCHEN

The smell of coffee fills the air.

JEANGREY (happy)
Good morning, [player.petname]!

[[choice]]
= Good morning, Jean!
    [[approval JeanGrey love +small_stat]]
    JEANGREY (happy)
    Did you sleep well?

= *yawn*
    JEANGREY (amused)
    Not a morning person, huh?
[[/choice]]

[[if JeanGrey.love >= 500]]

JEANGREY (gentle)
I made you some coffee. Just the way you like it.

[[else]]

JEANGREY
There's coffee on the counter if you want some.

[[/if]]

[[fx knock_on_door()]]

JEANGREY (surprised)
Who could that be?

The door opens

PLAYER
It can't be...

Your eyes widen

IT'S...

JOHN CENAAAAAAAA
```
