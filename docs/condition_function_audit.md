# Base-game condition-function audit — 2026-07-20

Dev-only working note, not shipped in releases (see `_DEV_ONLY_DOCS` in
`scripts/build_release.py`). Records a survey of the TNH base game for
read-only functions/methods worth registering in `condition_functions.yaml`
(standalone) or `character_methods.yaml` (`Character.method()`), so a future
session can pick this up without repeating the exploration.

## Why this exists

Item 4 of a Condition Builder feedback round: "check all base-game functions
usable in a discussion not yet in the compiler." The existing allowlists
(14 standalone + 10 character methods, both base layer) were already a
deliberate, fairly thorough hand-curation — this was a bounded top-up pass,
not a from-scratch audit.

## Method

1. A fork agent surveyed `core/mechanics/*.rpy` and `core/definitions/*.rpy`
   (`D:\Projets\Development\NullHypothesisPregnancyMod\TheNullHypothesis\game\`),
   filtering for: read-only (no `set_*`/`add_*`/`give_*`/`apply_*`/`update_*`/
   `distribute_*`/`register_*`/`remove_*` side-effect naming), takes a
   `Character`/`CharacterClass` (or nothing) as primary arg or is a method on
   `CharacterClass`/`NPCClass`, and returns something a writer would plausibly
   branch on (bool/enum/tier/count/string) rather than `None` or a complex
   object.
   - **Fully read**: `core/definitions/conditions.rpy`, `companions.rpy`,
     `state.rpy`, `interactions.rpy` — all turned out to be internal engine
     plumbing except `companions.rpy` (see "Flagged" below).
   - **Signature-grepped**: `core/definitions/{friendship,humhums,jobs,quests,
     inventory,trivia}.rpy`, `core/mechanics/{relationship,statuses,quirks,
     social,personalities,reactions,flirting,cheating,party,texting,phone,
     sleeping,behavior,progression,scores,gifts,weather,locations,
     interactions}.rpy`. Most hits were setters/mutators or UI/display flows
     — confirms the original curation left little low-hanging fruit.
   - **Not touched** (named audio/graphics/combat/UI-rendering/save-load/
     testing/benchmarks/plumbing files, out of scope): see the full exclusion
     list in [[project_compiler_editor_gui_cleanup]] memory if needed, or
     just re-run the same survey — it's cheap.
2. Every claim below was independently re-verified against live source
   (not just trusted from the fork) before being written down here.
3. A qmd cross-check (`collection: index`, lexical + vector queries) against
   `Docs/index/base_game/` caught 2 more read-only symbols the manual grep
   pass hadn't surfaced (`group_Characters`, `get_available_Character_
   mediations`, both in `core/mechanics/friendship.rpy`) — see "Considered
   and excluded" below. **Lesson for next time: run the qmd/index check
   FIRST, not as an afterthought** — it's faster than blind grep and would
   have caught these in the first pass.

## Recommended additions (6) — ready to implement, no schema changes needed

| Name | File:line | Signature | Category | Notes |
|---|---|---|---|---|
| `get_effective_friendship` | `core/mechanics/friendship.rpy:115` | `get_effective_friendship(A: CharacterClass, B: CharacterClass) -> FriendshipTier` | Relationships | Standalone. Returns the real tier (not just bool like `are_Characters_friends`) — `FriendshipTier` is an `IntEnum` (Enemies=-2, Rivals=-1, Acquaintances=0, Friends=1, GoodFriends=2, BestFriends=3), so `get_effective_friendship(A, B) >= 2` works. Note the numeric mapping in the YAML `notes:` since the compiler's expression grammar can't resolve `FriendshipTier.Friends` as a bare name (not a registered character/time-key — would resolve as scene-local, wrong). **Tier-footgun mitigation (see below).** |
| `get_Characters_opinion` | `core/mechanics/friendship.rpy:102` | `get_Characters_opinion(A: CharacterClass, B: CharacterClass) -> FriendshipTier` | Relationships | Standalone. One-directional (A's opinion of B) — NOT symmetric with `get_Characters_opinion(B, A)`. |
| `get_base_friendship` | `core/mechanics/friendship.rpy:123` | `get_base_friendship(A: CharacterClass, B: CharacterClass) -> FriendshipTier` | Relationships | Standalone. Pre-modifier baseline tier, excludes temporary mood-based swings. |
| `get_max_friendship` | `core/mechanics/friendship.rpy:131` | `get_max_friendship(A: CharacterClass, B: CharacterClass) -> FriendshipTier` | Relationships | Standalone. Historical peak tier ever reached — useful for "they used to be close" branches. |
| `Inventory.get_active` | `core/definitions/inventory.rpy:113` | `Character.Inventory.get_active(string: str, filter: str \| None = None, Owner: Any = False) -> bool` | Inventory *(new category)* | Character method, two-level path — same shape `resolve_method_path` already handles for `History.check`. Confirmed attach point: `self.Inventory = InventoryClass(self)` at `core/definitions/characters.rpy:34`. |
| `Inventory.get_number` | `core/definitions/inventory.rpy:110` | `Character.Inventory.get_number(string: str, filter: str \| None = None, Owner: Any = False) -> int` | Inventory | Character method, same path as above. Item count. |

Implementation is identical to the last round's pattern: add a `category:`
+ `signature:` entry to `allowlists_base/condition_functions.yaml` (the 4
Relationships) and `allowlists_base/character_methods.yaml` (the 2
Inventory) — no code changes needed, the category/signature loading and
GUI grouping already exist.

## Tier/int-return footgun and its mitigation

The 4 Relationships functions return a `FriendshipTier` (an `IntEnum` where
0 = Acquaintances and **negative values = Rivals/Enemies**), and the already-
registered method `get_friendship` returns a raw int score. The Condition
Builder's "Standalone function" / "Character method" flows insert a **bare
call** with no comparison: `[[if get_effective_friendship(A, B)]]`. In
Python that is truthy for **any non-zero tier — including enemies** — which
is almost the opposite of what a writer usually means ("are they friends").

Fix (this session): a `notes` field on `condition_functions.yaml` /
`character_methods.yaml` entries, loaded into `Allowlists.
condition_function_notes` / `character_method_notes` and shown as a warmer-
coloured per-selection note label in the Condition Builder (updates when the
function/method changes, distinct from the static per-type description). The
5 tier/int-returning entries carry a note telling the writer to compare the
result (`>= 2`, `< 0`, ...) rather than use it bare. This does **not** remove
the footgun mechanically (the builder still can't append a comparison for
you — that would be a bigger feature: a comparison affordance on non-bool
functions), it just makes it visible to the GUI writer who never sees the
YAML. Considered dropping the 4 tier functions instead, but they add real
expressiveness `are_Characters_friends` (bool, level-thresholded) can't
(exact/`<`/`>` tier comparisons), so they were kept with the warning.

## Considered and excluded

- **`Character.status`** (`core/definitions/npcs.rpy:408`, `@property ->
  dict[str, int]`, flags like `"horny"`/`"nympho"`) — read-only and clearly
  dialogue-relevant, but requires dict subscript access (`Character.status
  ["horny"]`). The expression grammar (`tnh_scene_compiler/expr_parser.py`)
  has no `Subscript` node at all (`Expr = Literal | Name | Attribute | Call
  | UnaryNot | BoolOp | Compare | Member | ListExpr`) — would need a real
  grammar extension, not an allowlist entry.
- **`BaseCompanionClass` bare properties** (`core/definitions/companions.rpy`,
  ~lines 223-414): `desire: float`, `breast_size`/`ass_size: int 0-6`,
  `sex_experience`/`dirty_talk_experience`/`throat_training`/
  `anal_training`/`toy_experience: int`. All read-only, all genuinely
  dialogue-relevant (arousal/experience-gated branches) — but they're bare
  properties (`Character.desire`, no call), and `character_methods.yaml` /
  `_validate_method_call` are built specifically around **called** attribute
  chains. Exposing these needs a new mechanism analogous to the existing
  `love`/`trust`/`mood` DSL sugar (`dsl.py`) — a real feature decision, not
  a data entry. Worth a future session on its own if the dev wants it.
- **`QuestTrackerClass.check`** (`core/definitions/quests.rpy:134`,
  `check(Quest_string, not_found=False) -> bool`) — likely `Player.Quests.
  check(...)`, i.e. Player-scoped rather than per-NPC-`Character`. Exact
  attachment point wasn't confirmed; flagged rather than proposed blind.
- **`group_Characters`** (`core/mechanics/friendship.rpy:158`,
  `group_Characters(Characters: Iterable[CharacterClass]) ->
  list[CharacterClass]`) — read-only, but returns a list with no simple
  boolean/scalar check a writer would branch on directly.
- **`get_available_Character_mediations`** (`core/mechanics/friendship.rpy:203`,
  `(Character: CharacterClass, Characters: Iterable[CharacterClass]) ->
  list[CharacterClass]`) — same list-return issue; would need `X in
  get_available_Character_mediations(...)`, which the Condition Builder
  doesn't guide (only hand-typing via "Expression only" mode), and the
  underlying feature (mediating multi-character conflicts) is a narrow use
  case for this mod's focus.
- `register_Friendships`, `create_friendship_key`, `distribute_friendship`,
  `distribute_animosity`, `distribute_animosity_from_cheating`,
  `set_friendship_tier`, `mediate_relationship` — all mutators or internal
  plumbing, excluded by the read-only filter.

## Status

Implemented. All 6 recommended additions landed in `allowlists_base/
condition_functions.yaml` (4 Relationships) and `allowlists_base/
character_methods.yaml` (2 Inventory). The 4 friendship functions'
signatures use explicit `A: Character, B: Character` type hints (not the
bare-`Character`-name convention `get_best_Friend`/`get_worst_Enemy` use)
so the editor's per-parameter form renders a character-picker dropdown for
*both* arguments, not just a first bare-named one — verified end-to-end
(`is_character_param` returns `True` for both `A` and `B` on all 4; a
compound condition combining one of each new entry validated cleanly
through the real `parse()`/`validate()` pipeline). 483 tests still green
(no test changes needed — purely additive allowlist data, no code path
changed). See [[project_compiler_editor_gui_cleanup]] memory for the full
session history this continues from.
