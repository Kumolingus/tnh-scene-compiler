# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

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
- The Condition Builder's "Standalone function" type now does the same:
  per-parameter fields from `condition_functions.yaml` instead of one
  free-text "Arguments" box.
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
- The Condition Builder can now combine two guided conditions with `and` /
  `or` via a new "Combine with" selector, instead of requiring a hand-edit
  after inserting a single condition. (Internally, the per-clause UI — type
  selector, dynamic parameter fields, condition assembly — moved into a
  reusable `_ConditionClausePanel`, embedded once or twice depending on the
  combine mode.)

### Removed

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

### Changed

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

## [0.1.1] - 2026-06-08

### Added

- `[[fade to black]]` / `[[fade from black]]` directive for full-screen cinematic fades. Compiles to the base-game `fade_to_black(delay)` / `fade_in_from_black(delay)` helpers (default `0.4`s; optional duration override, e.g. `[[fade to black 0.6]]`). Distinct from the per-character `[[show … fade=true]]` / `[[hide … fade]]`.
- `[[hide <Character> fade]]` — dissolve transition (`fade = 0.5`) when a character exits the scene.
- `[[show … fade=true]]` — passes the fade flag through to `add_Characters` so a character can dissolve in.
- Two-layer FX allowlist: a hand-maintained `fx_custom.yaml` (project/mod effects, never regenerated by a refresh) merges over the auto-generated base-game `fx.yaml`, so mod-specific `[[fx]]` effects survive an allowlist refresh. The `init` / refresh scaffolding now creates `fx_custom.yaml`.

### Changed

- `[[hide <Character>]]` now emits `hide_Character(...)` instead of `remove_Characters(...)`, avoiding the outfit-change ("dressing") animation when a character leaves the stage.
- `_CINEMATIC_FX_OVERRIDES` is now an exhaustive 20-entry map; the blind `cinematic_` auto-prefix was removed, so only effects with a compatible `cinematic_` variant are rewritten. `knock_on_door` is deliberately excluded (incompatible `cinematic_knock` signature).
- The FX extractor no longer scans mod source for effects — project effects live in `fx_custom.yaml` instead of being re-discovered on every refresh.

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
