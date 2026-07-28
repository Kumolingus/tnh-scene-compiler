## Key terms

Plain-language definitions for the words that come up throughout this
reference.

### Directive

An instruction in double square brackets on its own line, like
`[[show JeanGrey]]` or `[[pause 1]]`. Directives do the things a plain
dialogue or narration line can't — put a character on screen, play a sound,
branch, change a relationship. The full list is in the [Directives](#directives) section.

### Condition

A yes/no test on the current game state. Conditions decide whether an
`[[if]]` block plays or a choice option appears — for example
`[[if JeanGrey.love >= 500]]`. See the [Conditions](#conditions) section.

### Allowlist

The list of values the game actually supports — every character, mood,
face, arm pose, location, sound, and function a scene is allowed to name.
The compiler checks everything you write against this list, so a typo or an
unknown value is caught when you compile (with a "did you mean…?"
suggestion) instead of breaking the game.
Moods, faces, arm poses, and outfits are named in a
[dialogue parenthetical](#the-parenthetical) or a
[show directive](#show-hide-characters); places in a
[slugline](#locations); sounds and effects in a
[directive](#directives).

**Browse it:** the **Allowlists** button — on the project screen, the
quick-compile screen, and in the editor toolbar — opens every list, split in
two:

- **Core game** — what The Null Hypothesis itself accepts. Always read-only:
  these values are read out of the game's own files. If one you need is
  missing, it has to exist in the game first.
- **Project** — what this project adds on top. **Every list is editable here**,
  including the ones showing nothing yet (they appear greyed out); that is
  where you add a value the game doesn't have.

A list with values on both sides is shown on both, never merged — so you can
always tell a mood the game ships from one the project invented.

One caveat, and only for some setups. A project can fill its allowlists with a
**refresh** tool that re-reads the game and the project and rewrites most of
these files; an edit made here to one of those is undone the next time it runs,
so the value belongs at the source instead. That tool ships with the developer
build, not with this application — when it isn't there, nothing can overwrite
what you save and the window says nothing about it. When it is, the window
names the affected files and asks before saving one.

### Comparison operators

When a check involves a number, you compare it with one of these:

- `==` — equal to
- `!=` — not equal to
- `>` — greater than
- `>=` — greater than or equal to
- `<` — less than
- `<=` — less than or equal to

Example: `[[if JeanGrey.love >= 500]]` means "love is 500 or more".

### Cinematic scene

A full-screen story moment — as opposed to a phone, texting, or hub-option
scene. Its `Scene Type` is `cinematic`. Only cinematic scenes fire
themselves from the game state; the other types are opened by the mod's own
code.

**How one gets played:** a cinematic scene registers itself as an event. At
the moment named by its `Trigger` (going to sleep, waking up, travelling…),
the game gathers every scene whose [Conditions](#conditions) are currently
met and plays the one with the highest `Priority`. A scene only fires again
if it's marked `Repeatable`. That's why the [title page](#title-page) fields
matter — together they decide when your scene shows up. The full list is in
[Cinematic scene fields](#cinematic-scene-fields).

### Cinematic variant (of an effect)

Some `[[fx]]` [effects](#effects) have a special full-screen version used
inside [cinematic scenes](#cinematic-scene). You always write the plain name
(`[[fx bamf()]]`); the compiler automatically swaps in the cinematic version
when the scene is cinematic. You never write a `cinematic_` name yourself.

### Scene-local vs persistent state

**Scene-local** state is a flag that lives only for the current run of one
scene. You make it with `[[set]]` and read it by bare name in a condition,
and it's forgotten the moment the scene ends (see [Scene state](#scene-state)).
**Persistent** state — love
and trust, traits, history, personality — survives across scenes and saved
games; you change it with the persistent directives:
[approval](#approval-changes), [give_trait](#traits), [record](#history),
[set_personality](#personality), or [run](#persistent-state-advanced).
