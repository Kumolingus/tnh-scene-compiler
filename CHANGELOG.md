# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **`Target: true` on the title page — a scene about a character chosen at run
  time.** The scene compiles to `label <scene_id>(Target):` and `Target`
  becomes a reserved identifier usable wherever a character name is: as a
  condition-function argument (`[[if is_fertile(Target)]]`) and in
  interpolation (`[Target.name]`, for any suffix the allowlist exposes on a
  real character). One scene now covers what used to need one file per
  character — a consultation reading whichever girl was picked from a menu, a
  confession naming the other woman.
  It rides as a Ren'Py **label parameter** rather than a store channel because
  the engine scopes those dynamically (`renpy.exports.dynamic` in
  `Label.execute`): set on entry, restored on return, so nothing leaks past the
  scene and no clean-up line is needed — and there is nowhere to put one, since
  the dispatching `renpy.call` never returns to its caller.
  `Target` is reserved **whether or not it is declared**: naming it without
  `Target: true` is a compile error, not the silent scene-local lookup it would
  otherwise become, which evaluates to `None` and reads as "the condition is
  false". It is deliberately **not** a valid speaker and not valid in
  `[[show]]` / `[[hide]]`: moods, faces and arms are validated per character at
  compile time, and a face valid for the girl the writer had in mind but
  missing on another would compile clean and crash only when the second one is
  the target. The `uses_target` metadata flag, emitted hardcoded `False` since
  the hub was built, now reports the real value.
- **A line can say a value a function returns** — `[days_to_ovulation(Target)]`
  inside dialogue or narration, drawn from the same
  `condition_functions.yaml` as `[[if]]` (the two ask the same helpers the same
  question; a second allowlist would mean declaring each of them twice). Arity
  is checked as everywhere else, and the arguments obey the `[[if]]` grammar —
  `[fn(x) + 1]` stays refused.
  The call is **hoisted** into `$ _scene_text_N = fn(...)` on the line before
  rather than left in the string. Ren'Py would evaluate it in place
  (`config.interpolate_exprs` is true and `substitutions.py` runs `py_eval` on
  the bracket contents), but interpolation is re-evaluated on *every render* —
  the phone-text screen re-interpolates with `!i`, and any redraw repeats it.
  Hoisted, the helper runs exactly once, where the writer put it, and one that
  raises points at its own line instead of at a repaint.
- **An allowlist entry can declare `variants`** — one function listed as
  several named questions in the Condition Builder, each pinning some of its
  parameters. For a parameter that *replaces* the question rather than
  refining it, a bare field asks the writer to know the base game well enough
  to guess what the default means. A pinned parameter draws no widget: it is
  what makes the entry a different question, not a choice to revisit. A
  function declaring variants contributes those entries **instead of** one of
  its own — listing the unpinned form beside them would offer a third question
  resting on an invisible default.
- **`param_collection_mode`** — which of the three forms a character-collection
  field opens on, per parameter. The default is derived from the signature (a
  required collection is one the game fills from a location, so it leads with
  "Characters present here"), which is right for `are_Characters_friends` and
  `check_if_need_to_change` and wrong for a function asking about named
  characters. Nothing in a signature tells the two apart.
- **A "Glossary" button on every screen** — home, quick compile, a project's
  screen, and the editor toolbar it already had. The canonical format
  reference used to be unreachable until a scene was open. It reads bundled
  docs and needs no project, so nothing stopped it from being available
  earlier.
- `windows.py` — `open_singleton_window`, the "re-focus rather than stack a
  duplicate" rule the modeless reference windows share. It was copy-pasted at
  four call sites and the two new buttons would have made six.
  - It now **refuses** an attribute already holding something that is not one
    of our windows. Tk widgets carry their own attributes — `_w` is the
    widget's path name, a string — and the old inline version would have
    overwritten one, corrupting the owner silently, long after the click that
    did it. Found by a test that picked `_w` as its attribute name.
- **A mod-only refresh no longer files the game's own values as the mod's.**
  Several extractors learn a name from *usage* rather than from a declaration
  site — `history_events` matches every `History.check("…")`, `traits` every
  `check_trait("…")` — and the mod tree they scan contains the compiler's own
  compiled scenes. So a base-game name that any mod file merely *read* landed
  in the project layer as though the mod had introduced it. Nothing failed:
  `merge()` unions the layers and the value is in the base one anyway. What it
  undid was the split — the allowlist browser places a value by its
  `source_file` root, so a game value found under the mod's tree showed on the
  project side. `tnh_refresh_allowlists` now compares each extracted value
  against the core layer and leaves the duplicates out, reporting them per
  topic on the CLI and in `_meta.yaml`'s `warnings`. Measured on the pregnancy
  mod: 8 traits and 2 history events, every one of them TNH vocabulary.
  - Applies to **every** topic, and **only** when `--no-include-tnh` is set —
    that flag is what says "this layer may not hold game values". A run with
    TNH either produces the core layer itself or was asked for merged output
    on purpose, and filtering either would gut it.
  - The core layer defaults to the bundled `allowlists_base`; `--core-allowlists`
    points at another one. A missing or unreadable layer is reported and
    skipped, never fatal — the filter is layer hygiene, not a correctness gate.
  - **A duplicate is a match on the name *and* every metadata field.** `merge()`
    unions the plain sets, so dropping a duplicate trait can never make a scene
    fail — but it merges `locations`, `fx` and `moods` as dicts the project
    layer *wins*: a slugline's `location_id`, an effect's signature and call
    mode, a mood's face list. An entry reusing a core name with different
    metadata is a deliberate override and survives; dropping it would silently
    hand the writer the game's value instead.
  - The filter runs *after* the "no characters discovered" abort check and
    *before* the dry-run summary: a mod that adds no character of its own is
    legitimate, and a dry run must announce the counts a real run would write.

### Changed

- **`Player` is refused where the game structurally excludes it, and no longer
  offered there.** `are_Characters_friends([Player, JeanGrey])` compiled, ran,
  and was false forever: `Player` is not in the game's `all_Characters` at all,
  so no friendship record can involve it, `check_approval` returns 0 on sight,
  and `Partners` is already the player's own set. The player is the implicit
  other side of every relationship in TNH, never a participant you name — and
  across roughly 2000 calls the base game never passes it to one of these.
  - The Condition Builder stops offering it in those pickers, and the
    validator now rejects it with a message that says what to write instead
    (`check_approval(Character, None, "dating")`, or `get_present_Characters()`
    for the proximity check, whose reason is different).
  - **The line is argument versus subject.** `Player.History` (316 uses in the
    base game) and `Player.check_trait` (109) are ordinary things to ask
    about and stay valid. Only a bare `Player` handed to one of the ten
    guarded functions is refused.
  - `seen_Player_recently(Player)` is deliberately *not* guarded: it reads
    `Character.History`, which the player has, so it is a nonsensical question
    rather than an impossible one, and refusing it would claim more than the
    base game supports.
  - **This can fail a scene that used to compile.** Nothing in the 163
    authored scenes was affected, but a project that had one of these
    conditions was already getting a branch that never fired.
- **`Narrator` is gone from every character picker.** It is this compiler's own
  speaker label for narration lines, not a game object — it appears nowhere in
  the base game, so neither `f(Narrator)` nor `Narrator.anything` could mean
  anything.
- **"In a relationship" is now two entries**: *In a relationship* and *In a
  relationship, and the others know*. `are_Characters_in_Partners`'s
  `knows_about` is not a refinement — left at the game's default it also walks
  every *other* partner and fails on the first who has not been told about the
  character you asked about. "Is she the player's partner" therefore answered
  **False for someone who is**, as soon as a second, undisclosed partner
  existed. The plain entry pins it to `False`; the disclosure audit is a real
  question and keeps the other entry, under a name that says so.
  - Its character field now opens on "Pick characters". It is a required
    collection, so it used to lead with "everyone present here" — which asked
    whether every character in the room was a partner.
- **`AND`, `OR`, `NOT` and `IN` can be written in capitals**, and that is what
  the Condition Builder now inserts. Lowercase remains valid and no scene has
  to change — the two are the same expression. Capitals separate the glue
  between conditions from the conditions themselves, which is how the builder's
  own dropdown has always labelled them; it lowercased them on the way out,
  the one place the dialog disagreed with its own labels.
  - `True`, `False` and `None` stay case-sensitive. They are values a
    condition compares *against*, so they belong to the condition, not to the
    glue — and relaxing them would quietly turn a misspelled state key into a
    constant.
  - The cost: a scene-local state key can no longer be named `AND`, `Or`,
    `NOT` or `In` in any casing.
- **Per-arm poses are reachable from the character insert dialog**, behind an
  "Override each arm" checkbox that reveals a `Left arm` and a `Right arm` row.
  `left_arm` / `right_arm` have always been legal named-only keys in the
  parenthetical grammar, but the form only ever offered the `arms` preset, so
  reaching them meant typing by hand. The `[[show]]` form gets the same
  checkbox over the rows it already had.
  - **It reveals, it does not switch modes.** `change_arms` takes the preset as
    its defaults and lets a side kwarg override that side alone
    (`npcs.rpy:256`), so `arms=crossed, right_arm=hip` — "crossed, but the
    right arm on the hip" — is meaningful, and an exclusive toggle would have
    made it unreachable from the GUI. The preset row stays visible and in play.
  - A hint under the rows states the part that is easy to get wrong: with no
    preset there are no defaults, so a side left empty is posed `neutral`
    rather than left as it was. Now specced in `docs/format_spec.md` §6.4 and
    in the in-app glossary.
  - Hiding the rows clears them — a slot the writer can no longer see must not
    keep feeding the inserted line.
- **Glossary and Allowlists sit together in the header, on every screen.** They
  had drifted into three different zones: Allowlists in quick compile's action
  row but in a project's scene-list row, Glossary in the header on a project
  but the action row in quick compile. Both open a window to read and neither
  acts on the scene selection, so they are grouped the way the editor toolbar
  already grouped them, away from Compile / Validate and away from the
  per-scene buttons.
  - The order is `Glossary`, `Allowlists`, `Settings` left to right, on every
    screen and in the editor toolbar. The toolbar read backwards: these are
    packed `side=RIGHT`, where the first widget packed lands furthest right,
    so listing them in reading order reverses them on screen.
  - A project's header packs its path label **last** as part of this. `pack`
    hands out width in packing order and the project path is the one label
    with no bound on its length, so packed first it took what it wanted and
    pushed the buttons off the edge — visible at any width once a fourth
    button joined. Packed last it gets the remainder and clips instead.
- **Text medium hides the visual rows instead of greying them out.** A phone
  text carries no mood/face/arms/outfit/look, so the insert form now shrinks to
  the medium and the preview rather than showing six dead dropdowns.
- **`_DirectiveDialog` reaches its widgets by slot name.** The per-character
  refill recovered each combo from `grid_slaves` at the slot's index in `_vars`
  plus one; adding any non-field row to a form would have silently shifted that
  and left the writer picking from another character's poses. Widgets are
  registered in `_widgets[key]` as `(caption, input)` when built.

### Fixed

- **The testing hub can no longer force a value-returning condition to a
  boolean.** Its override is three-state (real / `True` / `False`), which is
  meaningful for a predicate and wrong for a count: a tester forcing `True` on
  `last_birth_baby_count` made every `== N` comparison false and dropped the
  preview into the fallback branch — and, now that a line can say a returned
  value, would render "True" where the writer asked for the number. The codegen
  reads the declared return type from the entry's `signature` and skips the
  wrapper for anything that is not `-> bool`; an entry with no declared return
  type is unchanged. This also unwrapped `get_Location()`, whose override would
  have replaced a `Location` object with a boolean.
- **Negative numbers are usable again — they never worked.** `-17` was listed
  as an allowed literal in §11.9.1 of the authoring conventions, and the
  grammar refused it outright with "Arithmetic is not allowed". That mattered
  beyond tidiness: the friendship tiers run to `-1` (rivals) and `-2`
  (enemies), and every doc naming that scale tells writers to compare against
  it, so `get_effective_friendship(A, B) >= -1` was a promised question the
  compiler would not accept.
  - A `-` **directly before a number** is now part of the literal, the same
    value-position rule that lets `[` open a list without allowing
    subscripting. Arithmetic stays refused: `x - 1`, `-x` and `-(3)` are
    unchanged.
  - **How it hid for so long:** the parametrised parser test listed `-17` with
    an expected rendering, then returned early on that one case, pointing at a
    "dedicated test below" that did not exist. It reported PASSED and checked
    nothing.
- **A condition you grouped with parentheses is now compiled the way you
  grouped it.** `[[if not (a and b)]]` was emitted as `not a and b`, which
  Python reads as `(not a) and b` — a different question, silently. Same for
  `(a or b) and c`, `a and (b or c)`, and any grouping that contradicts the
  natural precedence of `and` / `or` / `not`. The compiler reported nothing:
  the output was valid Ren'Py, it just took the other branch.
  - The parser drops the parentheses on purpose — the shape of the tree is
    what carries the grouping — so a renderer has to rebuild them from
    precedence. Neither of the two did. Both do now, from one shared table.
  - No authored scene was affected: none of them grouped a boolean condition
    (the 163 scenes recompile byte for byte). But the format documented
    parentheses as available all along, so this was reachable by anyone who
    followed the cheatsheet.
  - The regression tests compare **meaning**, not text: the emitted line is
    re-parsed with Python's own `ast` and matched against the condition as
    written. A string assertion is what let this through — one test had the
    flattened form written down as its expected value.
- **The character preview showed one thumbnail, not the combination.** Picking
  a face and then arms left the face on screen: both insert dialogs looked up
  face → arms → left arm → right arm and stopped at the first image they found,
  so every slot below the highest one filled was unreachable. In the `[[show]]`
  form that meant `left_arm` and `right_arm` could only ever be previewed with
  every other slot empty. The preview now renders **one captioned thumbnail per
  filled slot**, side by side, which is what a writer is actually assembling.
  - A slot whose value has no capture is skipped rather than drawn as an empty
    box, and the caption names the slot as well as the value — `crossed` as a
    left arm and `crossed` as a right arm are two different pictures sitting
    next to each other.
  - The `Insert — <Character>` form no longer stretches. Its fields moved into
    a frame of their own: the preview used to span their rows, and a ~385px
    arms thumbnail had grid spread that surplus across them, pulling the
    combos apart. The dialog is narrower and shorter than before.
  - Covered by `tests/test_thumbnail_preview.py`, which drives both real
    dialogs and counts what the preview frame holds. The selection rule
    (`selected_visual_slots`) and the slot dispatch (`ThumbnailStore.get_slot`)
    are pure and tested on their own.
- **The glossary described the partner check wrongly.** It read
  "`are_Characters_in_Partners([JeanGrey, Rogue])` — yes/no, are they dating
  each other". The function asks whether each character listed is a partner of
  the **player**; naming two asks whether they are *both* the player's
  partners. The example sat directly under the friendship checks, which really
  are about two characters, so the shape of the section taught the wrong
  reading.
- **No test can withdraw itself from a passing run any more — the suite reports
  962 passed, 0 skipped.** Read both numbers: a suite whose GUI half can skip
  itself and still report success is worth less than its test count suggests.
  This went wrong three separate ways.
  - **A duplicate Tk root.** `tk_root` was module-scoped in
    `test_condition_builder_dialog.py`, and two further modules defined their
    own — a second `tk.Tk()` in one process, which intermittently fails to
    re-init Tcl (`invalid command name "tcl_findLibrary"`) for whatever runs
    next. The shared fixture answered that by skipping, so a run could report
    `797 passed, 73 skipped` — no failure — with roughly fifty dialog tests,
    the condition-builder round-trip sweep among them, never executed. There is
    now exactly one session-scoped root in `conftest.py` and every dialog test
    builds its `Toplevel` on it. A `TclError` where Tk is expected to work —
    Windows, macOS, or a POSIX session with a display — now **fails**; skipping
    survives only for a genuinely headless machine, or via
    `TNH_TESTS_SKIP_TK=1` for a deliberate opt-out.
  - **Five skips waiting on data rather than on an environment**, together
    covering fifteen tests: three on the bundled `allowlists_base/` going
    missing (the six tests that check what a user actually receives — nothing
    else in the suite reads the shipped data, so their loss would have been
    silent and precisely targeted), and two on the *shape* of that data,
    feeding nine tests including the ones asserting the insert dialogs emit a
    line that compiles. The second pair would have gone quiet exactly when it
    mattered most: after a TNH re-extraction reshaped the visual slots. All
    five now fail, with a message naming what to regenerate.
  - **Two entries that were not untestable, only untested.** A declared-choice
    field opens blank on purpose, so the round-trip sweep now answers it from
    the same allowlist that populates the combo. The widget is unchanged — a
    blank field keeping `Insert` disabled is the affordance working, and
    pre-filling it to satisfy a test would have let the test degrade the
    product.
  - Two tests keep it that way, because writing the rule down did not:
    `test_tk_fixture_discipline.py` parses every test module and fails on a
    `tk_root` defined outside `conftest.py` — that rule was already in the
    project instructions when it was broken twice — and
    `tests/test_no_silent_skips.py` requires every `pytest.skip` to be listed
    with a reason, forbids the list rotting, and forbids a test `return`ing
    early.

## [0.2.0] - 2026-07-26

### Added

- **A "Using compiled scenes" section in the in-app glossary** — how a
  compiled `.rpy` gets into a mod and runs: a scene is a label, so
  `renpy.call("<Scene Id>")` is the whole story, plus the runtime bootstrap
  (the `<prefix>_scene_metadata` dict and `<prefix>_runtime` module) whose
  absence crashes the game at boot rather than at the call, passing
  `scene_state` into a scene, what calls what per scene type, and the stale
  `.rpy` left behind by a renamed `.scene`. Condensed from
  `docs/integration_guide.md`, which remains the long form. Until now the
  glossary covered only the writer's half of the format, so a solo modder
  had nothing in-app about wiring the output up.
- Glossary invariants under test: every `[label](#anchor)` cross-reference
  resolves to a section that exists (a renamed section otherwise leaves a
  link that silently goes nowhere), and no section smuggles in a markdown
  table, which the parser would render as raw pipes.
- **List and tuple literals in `[[if]]` expressions** (`[JeanGrey, Rogue]`,
  `(5, 2)`), the two shapes several allowlisted base-game functions require
  and no writer could express. `ListExpr` carries an `is_tuple` flag rather
  than adding a node kind, so every tree-walker keeps working. Subscripting
  stays forbidden: a `[` following a value is still an indexing error, only a
  `[` in value position opens a list. Sets and dicts stay out — the base game
  types these parameters `Iterable`, so a list is enough. Spec updated at
  §11.9.1 of the dialogue-authoring reference.
- **The character-collection field offers three modes**: "Characters present
  here" and "Characters visible here" (each with the location widget's
  "Current location" toggle, emitting `get_present_Characters(get_Location())`)
  alongside naming characters explicitly. A required collection leads with
  "present here" — how the game actually fills these arguments; an optional
  one (`arriving_Characters = None`) stays on the explicit pick, since
  defaulting it to everyone present would silently change the question.
- **The date field leads with "when an event last happened"** — a character
  and a history event assembled into `Char.History.check_when("kissed_player")`
  — with a plain-language **Day + time-of-day** form (Morning … Late Night)
  behind the second mode, in place of the raw `tuple[int, int]` text field a
  non-developer can't read. The moment these functions want is one the game
  stored, not a day number a writer knows.
- **`Character.History` is usable as a function argument.**
  `character_properties.yaml` grew a `usable_bare: false` flag: the validator
  accepts the name, the builder does not offer it as a standalone check (an
  object, so `[[if JeanGrey.History]]` is always true). With it,
  `chance_of_repeat_Event` gets a `<Character>.History` dropdown and is
  writable at all for the first time.
- **A `run_operations` entry for `check_if_need_to_change`** in the base
  layer — the sanctioned way to actually play the outfit-change / cleanup
  interaction, now that the condition form is side-effect free.
- **A `clothing_items` allowlist, extracted per character** (331 garments in
  the current build). The emitted value is the **inventory key**
  `JeanGrey_beige_cargo_pants`, not the bare id: `InventoryClass.add` files a
  garment under `Item.tag` (`f"{Owner.tag}_{string}"`), so the bare id would
  have suggested values that silently never match. The `string` parameter of
  `Character.Inventory.get_active` / `get_number` now resolves through a new
  `inventory_strings` source — the flat items plus that character's clothing,
  since one lookup reaches both. Clothing *types* (`pants`, `bra`, …) are a
  separate, smaller id space and are not collected.
- **An `inventory_items` allowlist**, extracted from the `all_Items` keys (58
  in the current build), feeding the `string` parameter of
  `Character.Inventory.get_active("...")` and `get_number("...")` — the last
  free-text parameter left on a listed condition. Clothing was left out of
  this first pass because it is stored under its own tag rather than the item
  key (`inventory.rpy:79-82`); the `clothing_items` allowlist above closes
  that gap, and the two now feed the same dropdown.
- Extractor tests for the new allowlists (`features`, `inventory_items`,
  `clothing_items`), including that a per-character set is never flattened
  across characters.
- **A `features` allowlist, extracted per character.** `tnh_refresh_allowlists`
  gains a `features` extractor reading each `<Character>_supported_features`
  set, emitting `features/<Character>.yaml` like faces and outfits do, and the
  browser lists it as its own topic. `Character.feature_enabled("...")` is fed
  by it and is the first `param_choices` source that **varies by character**:
  the dropdown re-populates from the character selected in the same form, the
  way the built-in mood check already does. The sets justify it — they run
  from 2 entries (CharlesXavier) to 23 (Rogue) and share no single common
  value, so one flat list would have suggested `date` for a character who has
  no date. With no character picked, or one carrying no declared set, the
  union of every known set is offered rather than an empty dropdown. The
  writer cheatsheet grows a per-character **Features** subsection to match.
- **Dropdowns on the last character methods that were still free text**:
  `check_trait` and `get_trait` suggest the known traits, `check_personality`
  the 8 personality traits, and the two inventory checks (`get_active`,
  `get_number`) offer their `filter` as `None` / `"gifts"` / `"key_gifts"` —
  the only two filter types the game defines, and all 58 of its items set one.
  `check_trait` and `check_personality` had been left bare on purpose because
  the Trait and Personality checks compile to them; that was the wrong call.
  They are still listed in the "Character method (any)" picker, so leaving
  their form worse than the neighbouring entry's only made sense from inside
  the code. Each carries a note pointing at the friendlier built-in.
- **"Love / trust (combined or by tier)" and "Friends (a group, at a tier)"**
  join the Relationships category. `check_approval` and
  `are_Characters_friends` had been treated as duplicates of the Love / Trust
  and Friendship built-in checks, but each built-in only reaches part of them:
  the simple check tests one axis against a plain number, while
  `check_approval` also tests love and trust *added together* and accepts a
  named relationship threshold ("friendship", "dating", …) that compares both
  axes against that tier's own pair; the `.friends_with` sugar hardcodes two
  characters and never emits `level`, while the function takes a whole group
  at any tier. Both now offer dropdowns for those values.
  `check_approval`'s declared signature also gains the `= None` defaults it
  was missing — without them the builder emitted `check_approval(A, , )`.
- **The pre-filled parameter values now reach the character methods too.**
  `History.check` and `History.check_when` offer a dropdown of the known
  history events and one of the 11 history trackers (`'persistent'`,
  `'season'`, `'chapter'`, …) instead of two free-text fields, and `get_trait`
  suggests the known traits. Both History methods also gained a note: the
  count check explains what a tracker window is, and `check_when` explains
  that a never-recorded event answers `(-1, -1, -1.0)` — which reads as "very
  long ago" if you feed it to "Periods since a date" unguarded. `get_status`
  and `is_in_normal_mood` are left bare: they are what the Mood and status
  checks already compile to, so the guided form belongs on those, not on the
  raw method.
- Three regression tests over every `param_choices` declared in the shipped
  base allowlists: each resolves to a non-empty option list (a mistyped
  dynamic `source` silently degrades to free text), each targets a parameter
  the signature actually has, and each fixed list contains the parameter's own
  default (or the dropdown opens on a value absent from itself).
- **Condition Builder pre-fills parameter values instead of always asking the
  writer to type them.** A function or method parameter now picks its widget
  from the signature: a declared `param_choices` list (same schema as
  `fx.yaml`, now honoured for `condition_functions.yaml` and
  `character_methods.yaml`) becomes an editable dropdown of suggestions; a
  single `Character` a picker; a `Character` collection (`Characters`, or a
  container type like `Iterable[Character]`) a multi-select that assembles a
  list literal (`[JeanGrey, Rogue]`); a single location (a `Location` /
  `location` parameter) a **"Current location?"** toggle — ticked (default)
  inserts `get_Location()` for the current room, unticked reveals a dropdown of
  the known sluglines (inserted quoted); a `bool` a `True` / `False` picker. The dropdowns stay editable so a
  project whose allowlist doesn't carry a value can still type it. Other
  free-string parameters (a history event key) are left as free text —
  declare `param_choices` for them when a fixed list helps.
- The Condition Builder's character multi-select is picked in a dedicated
  **"Choose characters" window** (a `Choose… (N)` button opens it), so picking
  from a large cast no longer cramps the condition panel.
- `param_choices` gains a **dynamic source** form
  (`{source: history_events, quote: true}`) that pulls a named allowlist set
  (`history_events`, `characters`, `traits`, `locations`, …) at render time —
  so e.g. the `Item` argument of "Chance of a repeat event" now suggests every
  known history event instead of asking the writer to type a bare string.
- **Plain-language help notes** on the trickier condition functions and body
  properties (best/worst friend of a group, "in a relationship", seen
  recently, characters present/visible, chance of a repeat event, needs to
  change clothes, breast/ass size), so the builder explains what a check does
  and what its arguments mean. The misleading "Days since a date" entry is
  renamed **"Periods since a date (4/day)"** — it counts time-of-day periods
  (4 per day), not days.
- **Every allowlist is editable on the project side**, not just the five the
  refresh preserves. Locking the generated ones assumed our workflow is
  everyone's: `tnh_refresh_allowlists` needs an extracted base game, and a
  project that cannot run it (or that writes its allowlists by hand) had no
  other way to fill a list. The clobber risk only exists for projects that do
  run the refresh, so it is surfaced where it bites instead of pre-empted — an
  inline warning in the editor, and a one-per-list confirmation on save. Files
  the refresh leaves alone save silently. This also covers
  `character_methods.yaml` / `character_properties.yaml`, which have no
  extractor and no scaffold: `Allowlists.merge` carries them, so a project may
  legitimately ship its own.
- The Allowlists browser splits every list in two — **Core game** and
  **Project** — by where each *value* comes from, not by which file holds it.
  A refresh run with `--include-tnh` scans the game and the mod into the same
  `traits.yaml`, so the split is per entry: it reads each entry's
  `source_file` against the `base_game_root` / `project_root` recorded in
  `_meta.yaml` (with `<builtin>` counting as the game, and an entry with no
  recorded source counting as the project's). A list with values on both sides
  is listed under both headings and never shown merged. Core is always
  read-only; only the project side of a hand-maintained file is editable. A
  project that never runs the refresh against the game still sees its own
  values under Project, and the game's under Core, which is the point.
- In-app **Allowlists** browser (an "Allowlists" button on the project screen,
  on the quick-compile screen, and in the editor toolbar). It lists all 21
  allowlists — characters, moods, faces, arm
  poses, outfits, looks, stages, locations, traits, personalities, history
  events, sfx, fx, interpolation paths, condition functions, run operations,
  character methods/properties — with each value tagged by the layer it comes
  from (`game`, `project`, or both), the fields that matter next to it
  (signature, type, location_id, notes…), and a per-character picker for the
  per-character ones. Search matches a list's name *or* any value inside it,
  across every character, so typing `shy` finds Traits.
  Answers "what can I actually write here, and what does the base game
  already have?" without leaving the app or regenerating the cheatsheet.
- The browser also **edits** the five allowlists the refresh preserves
  (`locations_overrides`, `fx_custom`, `interpolation_custom`,
  `condition_functions`, `run_operations`), in the project layer only. The
  other files are read-only on purpose: `tnh_refresh_allowlists` rewrites
  them wholesale, so an edit there would be silently lost — the window says
  which regime each file is under. Editing is raw YAML with a schema check on
  save (valid YAML, expected top-level key, every entry named); a
  `safe_load`/`safe_dump` round-trip would have deleted the hand-written
  header comments that document each file.
- The Condition Builder gained a "?" quick-access button (next to the
  Category selector) that opens the Glossary pre-filtered to the current
  category's conditions section. The glossary's Conditions section was
  enriched with per-family explanations + examples (Relationship /
  Character-state / Story-location-time conditions, and a "Comparing numbers
  vs yes/no" note), which the Glossary surfaces as searchable sections. The
  Glossary window gained `search=` (open pre-filtered) and `modal=` (grab when
  opened from the modal Condition Builder, so it's interactive) parameters.
- The Condition Builder's "Condition type" selector is now two-level
  (Category -> Condition). Built-in checks and the base-game/mod functions
  are grouped into Relationships / Character state / Story & history /
  Location & time / Advanced, so a useful function (e.g. "In a relationship",
  "Effective friendship (tier)") is pickable directly instead of buried under
  the generic "Standalone function". Functions route into a category by their
  allowlist `category` and show a friendly `label` (new optional allowlist
  field, falls back to the function name); the generic "Standalone function
  (any)" / "Character method (any)" escape hatches remain under Advanced.
  A sugar duplicate is not surfaced individually only where the built-in check
  covers the function's whole surface — currently just
  `Character_is_in_close_proximity`.
- The Condition Builder can now combine **any number** of clauses, not just
  one. Each clause after the first carries its own AND/OR operator; a
  "+ Add condition" button appends clauses (the list scrolls) and each has a
  "Remove" button. Clauses join in order via `join_conditions`; note `and`
  binds tighter than `or` in Python, so a mixed chain follows that precedence.
  Internally the per-clause UI — type selector, dynamic parameter fields,
  condition assembly — lives in a reusable `_ConditionClausePanel`, embedded
  once per clause.
- In-app **Glossary** window (a "Glossary" button in the editor toolbar). A
  separate, non-modal reference: a searchable section list on the left, the
  selected section's prose + copyable code examples on the right (each example
  has a "Copy" button). Content is parsed at runtime from the bundled
  `docs/glossary/*.md` files (one per top-level section, numbered for order),
  so the reference lives in the repo, not the code. The parser
  (`glossary.parse_glossary`) is pure/testable; the glossary folder is
  bundled into the exe (`.spec` datas).
- The Glossary content was expanded and rewritten for non-dev writers: a new
  **Key terms** section (allowlist, directive, condition, comparison
  operators, how a cinematic scene gets played, cinematic variant, scene-local
  vs persistent state), full coverage of every directive (`fade to/from
  black`, `give_trait` / `remove_trait`, `record`, `set_personality`, `run`,
  plus per-character `fade` and `stage` on `[[show]]`), plain-language intros
  on the condition families, and a "Watch out" note per directive/condition
  for the common pitfalls.
- The Glossary now supports clickable cross-reference links: prose written
  as `[label](#section-slug)` renders as a link (blue, underlined) that jumps
  to that section, clearing any active search first. Prose/notes render in a
  read-only `Text` widget (auto-sized to content) so links are individually
  clickable; a `slugify` / `parse_inline_links` pair (pure, tested) backs it,
  and a test asserts every shipped link resolves to a real section.
- New "Character property" condition type + a `character_properties.yaml`
  allowlist (chantier B). Read-only companion `@property` accessors — `desire`,
  `breast_size`, `ass_size`, `sex_experience`, `dirty_talk_experience`,
  `throat_training`, `anal_training`, `toy_experience`, plus the raw `love` /
  `trust` int values — can now be used bare in a condition
  (`[[if JeanGrey.desire >= 0.5]]`), guided by a categorized picker that reuses
  the comparison affordance (they're numbers). Hand-maintained (no extractor),
  same as `character_methods.yaml`; each entry carries a `type` (drives the
  comparison) and optional `category` / `notes`. The validator checks the
  property *name* (like traits) and does not enforce which characters actually
  have it (these live on companions), so the writer is responsible for using
  them on a companion.
- The Condition Builder now offers an inline comparison for functions/methods
  whose return value is a **number** rather than a yes/no. When the selected
  entry's signature returns an `int` / `float` / a `*Tier`/`*Level` IntEnum
  (detected by `return_is_comparable`), a "Compare:" row appears — an operator
  (`>=`, `<`, `==`, …, default `>=`) plus a value — producing e.g.
  `get_effective_friendship(A, B) >= 2` instead of a bare, truthy-when-nonzero
  call. A "(no comparison)" choice keeps the raw call for the rare deliberate
  case. This mechanically closes the tier/int footgun the previous release only
  warned about via a `notes:` label (the labels are now trimmed to a scale
  reference). Bool-returning entries show no comparison row (bare is correct).
- 6 new base-game entries in `condition_functions.yaml` / `character_methods.yaml`,
  found by a bounded audit of `core/mechanics/`/`core/definitions/` for
  read-only, dialogue-relevant functions not yet registered (see
  `docs/condition_function_audit.md` for the full survey, including what
  was deliberately excluded and why): `get_effective_friendship`,
  `get_Characters_opinion`, `get_base_friendship`, `get_max_friendship`
  (Relationships — return the real `FriendshipTier`, not just a bool like
  the already-registered `are_Characters_friends`); `Character.Inventory.
  get_active` / `Character.Inventory.get_number` (new Inventory category —
  same two-level attribute-chain path as the existing `History.check`).
- `condition_functions.yaml` / `character_methods.yaml` entries can carry an
  optional `notes:` field (writer-facing). The Condition Builder shows it as
  a per-selection note label that updates when the function/method changes.
  Used to warn that the tier/int-returning friendship helpers
  (`get_effective_friendship` & co, `get_friendship`) return a number to
  compare (`>= 2`, `< 0`), not a yes/no — a bare `[[if get_effective_
  friendship(A, B)]]` is truthy for enemies too, which is rarely intended.
- The scene editor's `[[show]]` insert form now exposes all 9 attributes the
  directive grammar accepts — `stage`, `left_arm`, `right_arm`, and `fade`
  joined `mood`/`face`/`arms`/`outfit`/`look`. `stage` and the two split-arm
  slots were already populated in `stages.yaml` / `arms/<Character>.yaml` and
  used elsewhere in the editor (the Visuals palette tab), but the combined
  insert form silently dropped them, forcing writers to hand-type those
  attributes instead of picking from real allowlist values.
- The `[[run]]` insert form now builds one field per parameter from the
  operation's `run_operations.yaml` signature, pre-filled with its declared
  default — mirroring the treatment `[[fx]]` already had. Previously the
  writer had to hand-type the entire call, including argument order, with no
  guidance despite the signature already being on file.
- Condition functions get the same per-parameter fields, built from
  `condition_functions.yaml`, instead of one free-text "Arguments" box.
- New Condition Builder type, "Character method", for guided
  `[[if Character.method(...)]]` conditions (`check_trait`, `get_status`,
  `History.check`, …) driven by `character_methods.yaml` — a category of
  condition that was previously usable only by hand-typing the exact call,
  even though `character_methods.yaml` is explicitly curated for this
  purpose. The loader now also captures each method's `signature:` field
  (it was being read from the YAML and discarded).
- Arity validation for `[[fx]]`, `[[run]]`, and `[[if]]` condition-function
  calls. The `signature:` already stored next to each `fx.yaml` /
  `run_operations.yaml` / `condition_functions.yaml` entry is now parsed for
  its positional arity (required count + maximum), and a call with too few or
  too many arguments is a compile error instead of valid-looking Ren'Py that
  raises `TypeError` at runtime — the project's dominant crash class.
  Signatures are parsed via `ast`, so type annotations
  (`Character: CharacterClass | None`), default values, and `*args` are all
  handled; an entry with no signature (or an unparseable one) keeps the
  previous name-only check, so the change is purely additive on the existing
  scene corpus.
- A `look`/gaze value can now be a **set** for a livelier, random-drawn gaze:
  `look={down|neutral}` (members separated by `|` or `,`) compiles to the native
  `change_face(..., eyes={"down", "neutral"})` set idiom, so the sprite draws a
  member each render. A single value still compiles to `eyes="down"`. Every set
  member is validated against the `looks` allowlist.
- `condition_functions.yaml`, `run_operations.yaml`, and `character_methods.yaml`
  entries can now carry an optional `category:` field. The Condition Builder's
  "Standalone function" / "Character method" types and the editor's "run
  function" form group their pick-list by category (with an "Other" fallback
  for projects that haven't added categories yet) instead of one flat
  alphabetical list — the base-game allowlists ship with categories filled in
  (Approval, Relationships, Location, Time, Clothing, History, Character
  status for condition functions; Traits, Personality, Mood and status,
  Relationships, Features, History for character methods).
- Every per-parameter field (`[[fx]]`, `[[run]]`, standalone condition
  functions, character methods) now renders a character-picker dropdown
  instead of a free-text box when the parameter's signature expects a single
  `Character` — either a bare `Character` parameter name (the `[[run]]`
  convention) or a `Character`/`CharacterClass` type hint. Parameters typed as
  a collection of characters (`Iterable[CharacterClass]`, `list[Character]`, …)
  are left as free text since they need a value the single-picker can't
  express.

### Changed

- **The cheatsheet now describes every allowlist layer, not just one.**
  `tnh_generate_cheatsheet` read a single directory, so a project whose own
  allowlists hold only its additions would have produced a cheatsheet with
  none of the game's values — the document a writer relies on to know what
  they may type. New `loader.load_layered()` merges layers in order (later
  wins on a name collision, matching `Allowlists.merge`), and the CLI prepends
  the bundled base layer unless `--no-base-allowlists` is passed. `load()` is
  unchanged for single-layer callers. The merged document keeps the *base*
  layer's source label, since the project's alone would label a game-wide
  cheatsheet "Mod".
- The Glossary's "Cinematic scene" and "How a cinematic scene gets played"
  key terms merged into a single "Cinematic scene" section — the second was
  the second half of the first's definition, and splitting them put the
  answer one click away from the question.
- The Glossary gained the cross-reference links it was missing: every mention
  of the allowlist, of a directive that a condition reads back
  (`give_trait` / `record` / `set`), of the persistent-state directives, and
  of the title-page fields is now clickable. The "compare it with an
  operator" link in Conditions pointed at the near-empty "Key terms" intro
  instead of "Comparison operators".
- **Behaviour change (property validation):** a bare `Character.<attr>` in a
  condition used to pass validation unchecked. Now, when a
  `character_properties.yaml` is present, `<attr>` is validated against it and
  an unregistered name is a compile error (with a suggestion). This catches
  typos but tightens what compiles. Verified against the full 161-scene corpus
  (zero new errors) before shipping; a project with no `character_properties.yaml`
  keeps the old pass-through behaviour. DSL sugar (`.love >= tier`, `.mood`,
  `.nearby`, `.has(...)`) is unaffected — it's rewritten to calls before the
  check — and `love` / `trust` are registered so the numeric approval form
  (`.love >= 500`) still validates.
- The `Format:` title-page field and the `INT.`/`EXT.` slugline prefix are
  no longer stored in the AST — both parsed values were dead (never read by
  the validator or codegen). Author-facing syntax is unchanged: `Format:`
  stays an accepted title-page key and the slugline prefix is still required
  to recognise a slugline.
- `_DirectiveDialog._build_fx` / `_build_sfx` (and their supporting
  `_build_fx_args`) are removed from `editor.py`. Neither `fx` nor `sfx` was
  ever routed to `_DirectiveDialog` — real `[[fx]]`/`[[sfx]]` insertion goes
  through the FX/SFX palette tab's `_FxParamDialog`/`_SfxParamDialog` — so
  this was dead, and a stale duplicate at that (it didn't use
  `fx_param_choices` for enum dropdowns like the live dialog does).
- The FX-signature parameter parser (`name`/`type`/`default` extraction) moved
  from `editor.py` (`_parse_fx_signature`) to `allowlists.py`
  (`parse_signature_params`), since it is now shared by the `[[fx]]`,
  `[[run]]`, and condition-builder per-parameter forms.

### Fixed

- **The Condition Builder emitted conditions that could not compile.** Three
  widgets produced text the `[[if]]` grammar rejects outright, so five listed
  entries (`are_Characters_friends`, `are_Characters_in_Partners`,
  `get_best_Friend`, `get_worst_Enemy`, `check_if_need_to_change`) and the
  date field's day form were unusable end to end:
  - the character multi-select wrote a set literal `{JeanGrey, Rogue}` — "Set/dict
    literals are not allowed";
  - an empty multi-select wrote `set()` — "Condition function 'set' is not
    registered";
  - the date field's day form wrote `(5, 2)` — "Expected ')' to close the
    parenthesised expression".

  None of this was visible to the test suite, which asserted on the string
  `get_condition()` returns without ever feeding it back through the parser
  and validator. `tests/test_condition_builder_roundtrip.py` now sweeps every
  catalog entry and does exactly that, against the shipped base allowlists.
- `check_if_need_to_change`'s curated signature defaults `check` to `True`, so
  a condition built without touching it asks a question instead of playing the
  outfit-change interaction as a side effect. The deliberate form moved to
  `[[run check_if_need_to_change(...)]]` (see above).
- A `[[run]]` operation that is not registered now says where a mod's own
  helpers belong, guidance that used to appear only when the whole allowlist
  was empty.
- **The Condition Builder could insert a call with an empty argument.**
  `is_valid` only checked the condition type's own fields, never the ones
  derived from a signature, so a guided form left partly blank still enabled
  Insert and wrote `get_effective_friendship(, ) >= 500` into the scene — a
  syntax error that surfaced only at compile time. Two changes: a `Character`
  parameter now pre-selects the first character instead of opening blank
  (matching the built-in checks and the location widget), and Insert stays
  disabled while any signature field is still empty.
- **`Character.get_friendship()` was documented as a raw score.** It delegates
  straight to `get_Characters_opinion`, so it returns a `FriendshipTier`
  (-2 enemies … 3 best friends). The old note suggested comparisons like
  `>= 50`, which can never be true. The signature, the parameter name and the
  note now match the base game, and the note points at the friendlier
  "Opinion of another (tier)" condition that does the same thing.
- Every `source_line` in `character_methods.yaml` now matches the base game
  again — 9 of the 12 had drifted (`feature_enabled` was 39 lines off). The
  file is hand-maintained, with no extractor to catch this.
- Condition Builder help text (the grey type descriptions and the per-entry
  notes) now reflows to the panel width instead of keeping the hand-wrapped
  source line breaks, which had left ragged, oddly-broken lines.
- A location parameter set to "Current location" no longer nests
  `get_Location()` inside itself: for an optional location (like
  `get_Location`'s own argument) the current-room case now omits the argument
  entirely (`get_Location()`, not `get_Location(get_Location())`). The slugline
  dropdown is also hidden while "Current location" is ticked.
- `arriving_Characters` (in "Needs to change clothes") is now recognised as a
  character collection and gets the multi-select, like `Characters` — the
  allowlist had stripped its type, so it was falling back to free text.
- `INT. [PLAYER.FIRST_NAME]'S ROOM` opened the shower. TNH declares
  `loc_PlayerShower` with the bedroom's `name`, so both derived the same
  slugline, both were emitted, and `_build_location_map` kept whichever was
  read last — the shower. The refresh now emits a slugline once: the first
  declaration keeps it and the collision is reported as a warning naming both
  ids. `allowlists_base` ships an override giving the shower a slugline of its
  own (`[PLAYER.FIRST_NAME]'S SHOWER`), so it stays reachable instead of
  becoming unaddressable.
- A mod-only refresh (`--no-include-tnh`) copied the engine builtins into the
  project's own allowlists: `Player` and `Narrator`, the eight look
  directions, and the Player/world interpolation paths — all of them already
  in `allowlists_base`, and all of them showing up on the project side of the
  browser as values that came with the game. The flag now gates them, so a
  project's files hold only what the project adds. Nothing is lost to a
  writer: every consumer merges the base layer in, which is where these
  belong.
- Per-character interpolation paths (`<Tag>.name`, `.petname`,
  `.Player_petname`) reported `<builtin>` as their source instead of the
  `characters/<Tag>/` folder they were discovered in. Since the browser
  classifies an entry as game- or project-owned from its `source_file`, a
  project that ships its own characters saw their interpolation paths filed
  under the game — and therefore read-only.
- The Allowlists browser warned about the allowlist refresh overwriting an
  edit even where the refresh does not exist. It ships with the source
  checkout, not with the packaged application — whose users therefore had no
  way to act on the warning, and nothing that could overwrite their work. The
  warning, and the confirmation on save, are now gated on
  `refresh_tool_available()`, which probes for the module instead of assuming
  it is there.
- The browser's edit view announced game values inside project files that hold
  none — 15 arm poses for a file that no longer exists, 3 stage positions, 310
  traits. It counted the *merged* view's core-origin values, so it was
  reporting the base layer, which lives in an entirely different file. It now
  counts only what the file being edited actually contains. Its wording was
  wrong too: it blamed "this project's refresh scanning the game into the same
  file", which stopped happening once the project layer was trimmed to the
  mod's own values. What remains are engine builtins (`Player`, `Narrator`,
  `day`, the looks) that every project's allowlist repeats — on the real
  corpus, 3 lists out of 21 rather than nearly all of them.
- The Glossary clipped the **last line of every multi-line paragraph**. The
  height fit used Tk's `count -displaylines` raw, but that returns the number
  of display-line *breaks* (one less than the number of lines), so a 3-line
  block was rendered 2 lines tall. Text simply stopped mid-sentence (the
  "Condition" term ended at "— for example"). Single-line blocks were correct
  by accident, which is why the truncation looked sporadic.
- The Glossary's interpolation examples used lowercase `[player.petname]` /
  `[player.first_name]`, which don't match the interpolation allowlist
  (`Player.*`, PascalCase) and fail validation. Corrected to `Player.*` and
  PascalCase character names (e.g. `[JeanGrey.petname]`), matching the real
  scene corpus. (Carried over from the old `scene_cheatsheet.md`.)
- The `scene_cheatsheet.md` Show/Hide example showed a comma between `[[show]]`
  attributes (`mood=happy, face=smile`), which does not compile — the directive
  grammar is space-separated. Corrected to `mood=happy face=smile` and the
  valid attribute keys were listed. (Same root cause as the editor `[[show]]`
  form fix.) The cheatsheet also gained character-property and number-return
  comparison condition examples.
- The scene editor's `[[show]]` insert form joined multiple attributes with
  `, ` (e.g. `mood=happy, face=smile`). The directive grammar expects
  space-separated `key=value` tokens; the trailing comma stayed glued to the
  previous value after `shlex.split()`, so any multi-attribute `[[show]]`
  built from that form failed allowlist validation with a value nobody
  actually typed (e.g. mood `"happy,"`).
- A `look=` gaze no longer wipes the character's brows and mouth. The old
  codegen emitted `change_face(getattr(Char, "face", None), eyes=…)`, but there
  is no `Char.face` attribute (`FACE_PARTS = ("brows", "eyes", "mouth")`), so
  `change_face(None, …)` reset brows and mouth to "neutral" every time —
  undoing any `face=` / `mood=` set in the same parenthetical. A paired
  `face`+`look` now folds into one `change_face("<face>", eyes=…)` call, and a
  gaze-only `look` passes the current brows/mouth through so only the eyes move.
- The faces extractor no longer emits a duplicate when the base game declares
  the same face name for a character twice (e.g. LauraKinney `squint` at two
  lines). Each distinct name is kept once (first occurrence), so the generated
  `faces/<Char>.yaml` and the cheatsheet no longer list it twice.
- **Crash fix:** the `Character.friends_with(Y)` DSL sugar compiled to
  `are_Characters_friends(Character, Y)` — two positional arguments — but the
  real base-game function takes one iterable:
  `are_Characters_friends(Characters: Iterable[CharacterClass], level=1)`.
  A lone `CharacterClass` bound to that parameter has no `__iter__`, but does
  have a string-keyed `__getitem__` inherited from `TraitClass`; Python's
  legacy `__getitem__`-based iteration fallback then calls it with `0`, `1`,
  `2`, … forever, since `dict.get(int_key, default)` never raises
  `IndexError` for a missing key — the game hangs with no error the moment
  the condition is evaluated. Fixed by emitting a genuine list literal
  (`are_Characters_friends([Character, Y])`); the expression grammar gained a
  `ListExpr` node — parser-unreachable, used only by this DSL rewrite — since
  it previously had no way to construct one. No scene in the current corpus
  used `.friends_with()` yet, so nothing shipped was actually affected, but
  the Condition Builder's "Friendship check" type pointed writers straight at
  the bug.
- The Visuals palette tab's preview panel no longer blanks when the mouse
  leaves a thumbnail button or when switching category/character — it keeps
  showing the last hovered image until a new one is hovered. Also reordered
  the category list so `Arms` / `Left Arm` / `Right Arm` (full-body pose
  shots) precede `Faces` (tight crops): checking a face used to require
  leaving the category that shows the pose, and the old blank-on-leave
  preview meant there was no way to see both without re-hovering each time.

### Removed

- **The Condition Builder's "Standalone function (any)" entry under Advanced.**
  It had become a pure duplicate: every allowlist function is promoted to its
  own named entry in the selector (an uncategorised one lands under Advanced),
  so of the 23 functions it listed, 20 were already one click away under a
  readable label — and the remaining 3 are the raw form of the Love / Trust,
  Friendship and Nearby built-in checks. Worse, it grouped them by the raw
  allowlist `category` field, a second taxonomy that put the same function
  under "Approval" there and "Relationships" in the main selector. Nothing
  became unreachable. Advanced now holds only "Character method (any)", which
  is not a duplicate — character methods are never promoted individually.
- The `pose` visual slot is gone from the scene vocabulary. It was accepted
  by the grammar (`(… pose=…)` and `[[show … pose=…]]`) and validated against
  a per-character `poses/<Char>.yaml` allowlist, but the codegen had no
  `change_pose` emission path (no such API in the base game) so a pose only
  ever produced a `# TODO` comment — a silent no-op in the output. Using
  `pose=` is now a compile error (`unknown attribute`). The `poses` extractor,
  the `poses/<Char>.yaml` allowlists, `Allowlists.char_poses` / `is_pose`, the
  cheatsheet `Poses` sections, and the editor pose widgets were all removed.
- Far-stage positions (`stage_far_left`, `stage_far_right`,
  `stage_far_far_left`, `stage_far_far_right`, `stage_far_far_far_right`) are
  no longer extracted into the `stages` allowlist. They are valid TNH
  X-coordinates used by `show_Character(x=…)`, but the compiler only emits the
  three slot-based `add_Characters` directions (`stage_left`, `stage_center`,
  `stage_right`); a far-stage previously produced a `# TODO` no-op. Using one
  is now a compile error (`not a valid stage`).

## [0.1.1] - 2026-06-08

### Added

- `[[fade to black]]` / `[[fade from black]]` directive for full-screen cinematic fades. Compiles to the base-game `fade_to_black(delay)` / `fade_in_from_black(delay)` helpers (default `0.4`s; optional duration override, e.g. `[[fade to black 0.6]]`). Distinct from the per-character `[[show … fade=true]]` / `[[hide … fade]]`.
- `[[hide <Character> fade]]` — dissolve transition (`fade = 0.5`) when a character exits the scene.
- `[[show … fade=true]]` — passes the fade flag through to `add_Characters` so a character can dissolve in.
- Two-layer FX allowlist: a hand-maintained `fx_custom.yaml` (project/mod effects, never regenerated by a refresh) merges over the auto-generated base-game `fx.yaml`, so mod-specific `[[fx]]` effects survive an allowlist refresh. The `init` / refresh scaffolding now creates `fx_custom.yaml`.

### Changed

- `[[hide <Character>]]` now emits `hide_Character(...)` instead of `remove_Characters(...)`, avoiding the outfit-change ("dressing") animation when a character leaves the stage.
- `_CINEMATIC_FX_OVERRIDES` is now an exhaustive 20-entry map; the blind `cinematic_` auto-prefix was removed, so only effects with a compatible `cinematic_` variant are rewritten. `knock_on_door` is deliberately excluded (incompatible `cinematic_knock` signature).

### Fixed

- Cinematic sluglines now empty `Location.Present`, not just suppress
  rendering. The codegen follows each cinematic `set_the_scene(...,
  show_Characters = False)` with `remove_everyone_but([], send_Offscreen
  = True)`, so a later `add_Characters` can no longer re-render a
  character left over from the previous location. Uses the
  `hide_Character` path, so no `set_Outfits` re-dress animation runs.

## [0.1.0] - 2026-05-17

### Added

- **Visual thumbnails** for character faces and arms in the editor GUI:
  - Face and arm pose thumbnails displayed in `_CharacterInsertDialog`, `[[show]]` directive dialog, and Visuals palette tab.
  - Import script (`scripts/import_thumbnails.py`) generates thumbnails from a TNH-VisualReference checkout via Pillow.
  - `_mapping.yaml` provides explicit allowlist-name-to-image mapping with fuzzy matching for source filename typos.
  - `show_thumbnails` setting in application preferences (default: on).
  - Thumbnails bundled in PyInstaller builds.
- Fountain-TNH scene compiler (`tnh_scene_compiler`) — converts `.scene` files to Ren'Py `.rpy` scripts.
- Allowlist refresh tool (`tnh_refresh_allowlists`) — scans a TNH base game build to generate YAML allowlists.
- Cheatsheet generator (`tnh_generate_cheatsheet`) — produces a writer-facing markdown reference from allowlists.
- Two-layer allowlist system: base vanilla TNH allowlists ship with the tool, project-specific extensions merge on top.
- Config-driven `project_prefix` — the metadata dict, runtime module, and condition wrapper names are no longer hardcoded.
- Project config via `tnh_scene_compiler.<prefix>.yaml` with auto-discovery (walks up directories). Legacy `tnh_scene_compiler.yaml` filename supported as fallback.
- CLI with `compile`, `validate`, and `init` subcommands.
- Colored console output (ANSI, no external dependency).
- Windows drag-and-drop via `scripts/compile.bat`.
- Runtime stub templates generated by `init` command.
- Pre-built vanilla TNH allowlists (31 characters, 31 locations, 47 effects, 14 condition functions, 10 character methods, 51+ YAML files).
- 319 unit tests covering lexer, parser, codegen, validator, allowlist refresh, and cheatsheet generation.
- Documentation: format specification, writer guide, modder setup guide.
- **Tkinter GUI** with wizard-style flow:
  - Welcome screen: Quick compile / Open project / Create project.
  - Quick compile mode: compile `.scene` files against base game only, no project setup required.
  - Project mode: full workspace with auto-discovered scenes and custom allowlists.
  - Per-file status indicators (pending / running / ok / error) in real-time.
  - Drag-and-drop support via `tkinterdnd2` (optional dependency, graceful fallback).
  - Recent projects persistence (`%APPDATA%/tnh-scene-compiler/recent_projects.json`).
  - Project settings editor (paths, allowlists, base game options).
- **Integrated scene editor** with insertion palette:
  - Full text editor with syntax highlighting (sluglines, speakers, directives, comments, interpolation).
  - Line numbers, undo/redo, Tab-to-spaces, Ctrl+/ comment toggle.
  - Sidebar palette with colored section tabs (Chars, Locs, Directives, FX/SFX, Structures, Visuals).
  - Character insertion dialog: select medium (spoken/text), mood, face, pose, arms, outfit, look with live preview.
  - Directive insertion dialogs: per-directive forms (show, hide, approval, pause, set, call, etc.) with live preview.
  - Visuals tab: character + category dropdowns to insert `[[show]]` directives.
  - Location categories by school floor (Basement, Ground floor, Girls'/Boys' floor, Attic, Outdoors, Outside school).
  - Character categories (Featured characters, NPCs, Player/Narrator).
  - FX/SFX split into generic effects, character effects, and sounds.
  - Call scene directive with project scene ID autocomplete.
  - Inline validation: parse + validate on buffer, error underline, click-to-navigate.
  - New scene creation with title page template.
  - Save/Save As with unsaved changes prompt on back navigation.
  - Editor preserves calling screen state (Quick/Project) on return.
  - Dark-themed output pane with colored log messages.
- **DSL transformation layer** for writer-friendly condition syntax:
  - `Character.love >= medium` → `check_approval(Character, "love", "medium_stat")`.
  - `Character.has("trait")` → `Character.check_trait("trait")`.
  - `Character.mood == "normal"` → `Character.is_in_normal_mood()`.
  - `Character.friends_with(Other)` → `are_Characters_friends(Character, Other)`.
  - `Character.did("event")` → `Character.History.check("event") > 0`.
  - `Character.nearby` → `Character_is_in_close_proximity(Character)`.
  - `Character.personality("trait", threshold)` → `Character.check_personality("trait", threshold)`.
  - Original function-call syntax remains supported.
- **Project-level aliases** (`aliases.yaml`): `character_aliases` and `function_aliases` allow projects to define custom DSL mappings (e.g. `JeanGrey.is_pregnant()` → `pregnancy_mod_is_pregnant(JeanGrey)`).
- **Fuzzy location matching**: writers can type `JEANGREY'S ROOM` instead of `[JEANGREY.NAME]'S ROOM` — the compiler resolves interpolated location names automatically.
- **Condition Builder dialog**: guided UI in the editor's Struct. palette tab for building `[[if]]` condition expressions. Dropdown-driven — select condition type, character, and parameters with live preview. Supports all 8 DSL condition forms plus standalone functions. Wrap mode selector (if block, elif, expression only).
- **Traits allowlist and extractor**: new `traits.yaml` allowlist and `traits` extractor that scans for `give_trait`/`check_trait`/`remove_trait`/`has_trait` calls. Condition builder shows known traits in a dropdown when available.
- **Personalities allowlist and extractor**: new `personalities.yaml` allowlist and `personalities` extractor that scans for `check_personality`/`set_personality` calls. Wired into the condition builder.
- **History events allowlist and extractor**: new `history_events.yaml` allowlist and `history_events` extractor that scans for `History.check`/`History.add`/`History.record` and `.did()` calls. Wired into the condition builder.
- **New Scene dialog**: guided form replaces the raw template when creating a new scene. Fill in Title (auto-generates Scene Id), Character (dropdown from allowlists), Scene Type (adapts fields: Trigger for cinematic, Openness+Stage for phone), Location. Choose from 4 starting templates: empty, simple dialogue, dialogue with choices, conditional scene. Live preview.
- **Cheatsheet DSL conditions section**: the generated `Authoring_Cheatsheet.md` now documents all writer-friendly condition shorthands with syntax and examples.
- **Condition function validation**: `[[if ...]]` expressions are now validated against `condition_functions.yaml` (standalone functions) and `character_methods.yaml` (character methods).
- Base allowlists for `fx.yaml` (47 engine effects), `condition_functions.yaml` (14 functions), and `character_methods.yaml` (10 methods).
- Pluggable output system (`output.set_callback`) allowing CLI and GUI to share the same compiler pipeline.
- PyInstaller spec (`tnh_scene_compiler.spec`) for single-file `.exe` builds.
- GitHub Actions release workflow (`.github/workflows/release.yml`) — builds `.exe` and creates GitHub Release on tag `v*`.
- GUI entry point: `tnh-scene-compiler-gui` (via `[project.gui-scripts]`).
- Optional dependencies: `tkinterdnd2` (drag-and-drop), `pyinstaller` (build).

### Changed

- Renamed `mod_prefix` → `project_prefix`, `mod_allowlists` → `project_allowlists`, `mod_root` → `project_root` throughout code, config, and YAML files.
- Config filename changed from `tnh_scene_compiler.yaml` to `tnh_scene_compiler.<prefix>.yaml`.
- Empty `mod_operations` and `fx` allowlists now produce informative errors instead of silently passing validation.
- `summary()` in `output.py` now routes through `success()` instead of direct `print()`.
- `_resolve_config`, `_build_allowlists`, `_compile_one`, `_iter_scene_files` made public for GUI reuse.
- `Config.base_allowlists_dir` uses `get_data_root()` for PyInstaller compatibility.
