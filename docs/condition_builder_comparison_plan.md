# Plan — comparison affordance (A) + bare property checks (B)

Dev-only planning note (excluded from release builds, see `_DEV_ONLY_DOCS`
in `scripts/build_release.py`). Two backlog chantiers deferred during the
2026-07-20 condition-function audit. Written so a future session can pick
either up without re-deriving the design. Companion to
`docs/condition_function_audit.md`.

> **Status: chantiers A and B are both DONE (2026-07-20).**
>
> **A** — `signature_return_type` / `return_is_comparable` (+ shared
> `type_is_comparable`) in `allowlists.py`, `compare_op`/`compare_value` on
> `build_condition` (+ `_append_comparison`), a per-selection "Compare:" row
> in `_ConditionClausePanel` (`_build_comparison(frame, is_comparable)` /
> `_current_comparison`), `is_valid` gating. Phase-1 value input is a plain
> entry (the Phase-2 `value_choices` tier-name dropdown remains a possible
> follow-up).
>
> **B** — `character_properties.yaml` (base layer, hand-maintained: the 8
> companion `@property` stats + `love`/`trust`), loaded into
> `Allowlists.character_properties` / `_types` / `_categories` / `_notes` (+
> merge). New "Character property" condition type
> (`_params_property` + `build_condition` "property" branch producing
> `Character.<prop>` + comparison). Validator: `_collect_bare_attributes` +
> `_validate_condition_attributes` reject an unregistered bare
> `RegisteredChar.<attr>`, guarded to skip when the property allowlist is empty
> (preserves old pass-through). The product gate was cleared by the user ("go
> B"); the semi-breaking-validation gate was cleared by grepping the corpus
> (no bare attribute conditions existed) and validating all 161 scenes (zero
> new errors). `love`/`trust` were added to properties so the numeric approval
> form (`.love >= 500`, not rewritten by the tier-name sugar) still validates.
>
> The rest of this note is the original pre-implementation plan, kept for
> reference.

Grounding facts checked against live source before writing:
- The Condition Builder inserts a **bare call** for the function/method
  types (`build_condition` in `condition_builder.py`). No comparison.
- Function/method **return types are already in the signatures**
  (`-> FriendshipTier`, `-> int`, `-> bool`) — parsed today only for arity
  (`signature_arity`), not exposed as a type.
- The validator only collects/validates `Call` nodes
  (`_collect_calls` / `_validate_condition_calls`). A **bare `Character.<attr>`
  in a condition passes validation with no error today** (verified:
  `[[if JeanGrey.desire >= 0.5]]` produced zero errors against a minimal
  allowlist). So bare property access already "works" unvalidated.
- `_render_expr` already renders a bare `Attribute` as `Root.parts` — codegen
  needs no change for either chantier.

---

## Chantier A — comparison affordance (do this first)

**Goal.** When a selected condition function / character method returns a
comparable non-bool (int, a tier `IntEnum`, float), the builder offers an
operator (`>=`, `>`, `<`, `<=`, `==`, `!=`) + a value, producing
`get_effective_friendship(A, B) >= 2` instead of the bare call. Mechanically
closes the tier/int footgun that the `notes:` label only warns about today.

**Design decisions to lock first**
1. *Which return types get the comparison UI?* Parse the return type from the
   signature (everything after `->`, strip whitespace and a trailing
   `| None`). Treat as numeric-comparable: `int`, `float`, and anything
   ending in `Tier` or `Level` (heuristic for IntEnum ladders like
   `FriendshipTier`). `bool` → no comparison (bare is correct). Everything
   else (`str | None`, `tuple`, `set[...]`, `Character | None`) → no
   comparison offered (keep bare; those are rare and not sensibly `>=`-d).
   Keep this as a pure `return_is_comparable(signature) -> bool` helper in
   `allowlists.py` so it's unit-testable and the heuristic lives in one place.
   Escape hatch if the heuristic ever misfires: an explicit `compare: true |
   false` field on the allowlist entry overrides the auto-detection.
2. *Default behavior for comparable returns.* Default the operator to `>=`
   with the value **required** (so `is_valid()` gates insert until filled) —
   nudges the writer into a comparison rather than a footgun. Offer an
   explicit "bare (no comparison)" operator choice for the rare deliberate
   truthy use.
3. *Value input.* Phase 1: a plain value entry (numbers) + keep the existing
   `notes:` label explaining the scale (e.g. the FriendshipTier mapping).
   Phase 2 (optional): a data-driven `value_choices:` field on the entry
   (mirrors fx `param_choices`) mapping labels → values, so a tier function
   can offer a `GoodFriends (2)` dropdown. Keeps the compiler project-agnostic
   — no hardcoded `FriendshipTier` in the tool.

**Implementation steps**
1. `allowlists.py`: `signature_return_type(signature) -> str` +
   `return_is_comparable(return_type) -> bool` (pure, unit-tested). Optionally
   load a `compare` / `value_choices` field (parallel to `category`/`notes`).
2. `condition_builder.py` `build_condition`: add `compare_op: str = ""`,
   `compare_value: str = ""`; for the `function`/`method` kinds, append
   ` {op} {value}` when `compare_op` is set and not the bare sentinel. Pure
   unit tests.
3. `_ConditionClausePanel._params_function` / `_params_method`: after the
   per-parameter fields, when the selected entry's return type is comparable,
   show an operator combobox + value entry (or a `value_choices` dropdown).
   Rebuild them in the existing `_on_func_change` / `_on_method_change`
   callbacks (return type changes with the selection). Feed `compare_op` /
   `compare_value` into `get_condition`.
4. `_REQUIRED_VARS` / `is_valid`: when a comparison is shown and the operator
   is not "bare", require the value.
5. Tests: pure `build_condition` with comparison; `return_is_comparable`
   truth table; a Tkinter dialog test (`tests/test_condition_builder_dialog.py`)
   — a tier function shows the operator widget, a bool function does not.
6. Docs: `docs/writer_guide.md` note; `CHANGELOG.md`. Soften the `notes:`
   wording on the tier entries once the UI guides the comparison (the note
   becomes a scale reference rather than the primary guardrail).

**Size/value.** Medium feature, high value — retires a real footgun. Self-
contained in the compiler; no scenes-submodule change (comparison is a
builder concern, the allowlist entries already exist).

---

## Chantier B — bare property checks (depends on A)

**Goal.** Expose a curated set of read-only companion properties
(`desire`, `breast_size`, `sex_experience`, …) as first-class condition
operands: `[[if JeanGrey.desire >= 0.5]]`, guided + validated. Reuses A's
operator/value UI.

**⚠ Product gate (decide before any code).** These properties are explicit
stats (arousal, body, sexual experience). Surfacing them to non-dev writers
is a product decision, separate from the technical work. The mod's domain
covers it, but it needs the dev's explicit go-ahead.

**⚠ Semi-breaking validator change.** Today a bare `Character.<attr>` in a
condition is **not validated at all** (passes silently). B adds validation
that would start **rejecting** bare attributes not in the property allowlist.
Before shipping: grep the scene corpus
(`external/pregnancy-mod-scenes/scenes_source/`) for existing bare
`Char.<attr>` uses in `[[if]]`/`[[choice ... if]]`; if any exist that aren't
the DSL sugar (`.love`/`.trust`/`.mood`/`.nearby`), decide allowlist-gate vs
warn-only, or grandfather them.

**Design decisions**
1. New hand-curated allowlist `character_properties.yaml` (base layer) — no
   extractor (same as `character_methods.yaml`, a manual scaffold). Schema:
   `name`, `type` (int/float/bool/str), `category`, optional `notes`,
   optional `value_choices`, `source_file`/`source_line`. Curated safe set
   from `core/definitions/companions.rpy`: `desire`, `breast_size`,
   `ass_size`, `sex_experience`, `dirty_talk_experience`, `throat_training`,
   `anal_training`, `toy_experience` (all `@property`, read-only).
2. Per-character applicability: these live on `CompanionClass` — Player /
   Narrator / non-companion NPCs lack them. Validate the property **name**
   against the allowlist (like traits/moods); do not try to enforce which
   characters have it. Document that the writer is responsible.

**Implementation steps**
1. `allowlists.py`: load `character_properties.yaml` into
   `Allowlists.character_properties` (+ signatures/categories/notes parallel
   to methods), + merge.
2. `validator.py`: extend condition validation to check bare `Character.<part>`
   attribute operands. After the DSL transform (which already rewrites
   `.love`/`.trust`/`.mood`/`.nearby`), any residual single-part `Attribute`
   in a condition should validate `<part>` against `character_properties`,
   else a "unknown property" error with `did you mean` suggestions. Care:
   don't false-reject the already-rewritten sugar, and don't touch dotted
   store/time keys used elsewhere. New tests: accept known property, reject
   unknown, sugar still passes, existing corpus still compiles.
3. `condition_builder.py`: new condition type `property` — char picker +
   category+property dropdown (`group_by_category`, reuse) + A's operator/
   value widget. `build_condition` gains a `property` branch producing
   `Character.<prop> <op> <value>`.
4. Codegen: verify no change needed (bare Attribute already renders). Add a
   codegen test to lock it.
5. Tests + docs (`writer_guide.md`, `CHANGELOG.md`) + `character_properties.yaml`
   in the base layer. Scenes-submodule mod layer optional (only if the mod
   adds its own read-only properties later).

**Size/value.** Larger than A (new allowlist + semi-breaking validator +
new builder type), and more speculative (adds arousal/experience-gated
authoring that writers may or may not want). Do only after A and after the
product gate.

---

## Sequencing

1. **A first** — closes a concrete existing footgun and builds the shared
   operator/value UI brick.
2. **B second, gated** — reuses A's UI; needs the product decision + the
   corpus-grep on the semi-breaking validation change.

Each chantier is one self-contained compiler commit (+ submodule pointer
bump), following the same discipline as the audit round. Neither needs a
scenes-submodule content change for the base functionality.
