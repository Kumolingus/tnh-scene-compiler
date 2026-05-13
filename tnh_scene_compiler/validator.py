"""AST validator. Consumes a :class:`Scene` and the allowlists, returns
a list of :class:`CompileError`. The list is the contract — no exceptions
fly out of this module so the CLI can report multiple problems in one run.

Phase 6A checks (subset of §11.16):

* Scene Type must be ``cinematic`` in 6A. Other scene types are recognised
  but the codegen path is not implemented yet; they raise a blocking error
  here so writers know the feature is coming rather than getting a garbled
  ``.rpy``.
* Scene Id must be mod-prefixed and snake_case — enforced loosely (non-empty,
  identifier-ish, contains no whitespace). A full per-mod prefix check is a
  future concern.
* Character must be a known character from the allowlist.
* Dialogue speakers must resolve to a known character (UPPERCASE form).
  Narrator is implicit — speaking with ``NARRATOR`` is allowed and maps to
  the default narrator.
* Sluglines must be known locations. Time-of-day suffixes (``- NIGHT``,
  ``- MORNING``, ``- DAY``, ``- EVENING``) are stripped before the lookup
  so the same slugline + suffix combo is not a separate allowlist entry.
* Interpolation paths inside dialogue/narration text must be known.
* Interpolation expressions (anything inside ``[...]`` that isn't a plain
  path) are rejected — scene files never execute Python via interpolation.
"""

from __future__ import annotations

import re

from .allowlists import Allowlists
from .ast_nodes import (
    Approval,
    Choice,
    DialogueBlock,
    FxCall,
    Goto,
    Hide,
    IfChain,
    Label,
    ModSet,
    NarrationBlock,
    Parenthetical,
    PhoneOpen,
    Scene,
    Sfx,
    Show,
    Slugline,
)
from .errors import CompileError

_SCENE_ID_SHAPE = re.compile(r"^[a-z][a-z0-9_]*$")

# Time-of-day suffix stripped from sluglines before the allowlist lookup.
_TIME_SUFFIXES: tuple[str, ...] = (" - MORNING", " - DAY", " - EVENING", " - NIGHT")

# Matches ``[path]`` inside a string — the ``[`` must be unescaped. Ren'Py's
# own convention for literal brackets is ``[[``, so we consume them first to
# avoid treating them as interpolations.
_RE_INTERPOLATION = re.compile(r"\[([^\[\]]+)\]")

# A path is at most a dotted identifier chain: ``player.name``, ``day``,
# ``JeanGrey.pregnancy_stage``. No function calls, no arithmetic, no
# f-strings. Anything else inside ``[...]`` is rejected.
_RE_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")


def _strip_time_suffix(text: str) -> str:
    """Return ``text`` without a trailing time-of-day suffix, if any."""
    for suffix in _TIME_SUFFIXES:
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def _iter_interpolations(s: str) -> list[tuple[str, int]]:
    """Yield ``(path, column_offset)`` pairs for every ``[...]`` in ``s``.

    Ren'Py doubles the bracket (``[[``) to mean a literal ``[`` — we skip
    those so they are not misread as interpolation openings.
    """
    results: list[tuple[str, int]] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "[":
            if i + 1 < n and s[i + 1] == "[":
                # Literal ``[``. Skip the escape sequence.
                i += 2
                continue
            # Find the matching ``]``. The inner must not contain another ``[``.
            end = s.find("]", i + 1)
            if end == -1:
                # Unterminated interpolation — let the validator surface this.
                results.append((s[i + 1:], i + 1))
                return results
            inner = s[i + 1:end]
            # Reject nested brackets.
            if "[" in inner:
                results.append((inner, i + 1))
                i = end + 1
                continue
            results.append((inner, i + 1))
            i = end + 1
            continue
        i += 1
    return results


def _validate_interpolations_in(
    text: str,
    *,
    source_line: int,
    source_col: int,
    allow: Allowlists,
    errors: list[CompileError],
    path: str,
) -> None:
    """Scan ``text`` for ``[...]`` and check every path against the allowlist."""
    for inner, col_offset in _iter_interpolations(text):
        path_text = inner.strip()
        if not _RE_PATH.match(path_text):
            errors.append(CompileError(
                path = path,
                line = source_line,
                col = source_col + col_offset,
                message = (
                    f"Interpolation {inner!r} is not a plain path. Only dotted "
                    "identifier chains (e.g. `[player.name]`) are allowed."
                ),
            ))
            continue
        if path_text not in allow.interpolation:
            suggestions = allow.suggest_interpolation(path_text)
            hint = f"Did you mean: {', '.join(suggestions)}?" if suggestions else None
            errors.append(CompileError(
                path = path,
                line = source_line,
                col = source_col + col_offset,
                message = f"Interpolation path {path_text!r} is not a known value.",
                hint = hint,
            ))


def _validate_title_page(
    scene: Scene,
    allow: Allowlists,
    errors: list[CompileError],
) -> None:
    tp = scene.title_page
    path = scene.source_path

    if not _SCENE_ID_SHAPE.match(tp.scene_id):
        errors.append(CompileError(
            path = path,
            line = 1,
            col = 1,
            message = (
                f"Scene Id {tp.scene_id!r} is not snake_case. Scene Ids must "
                "start with a lowercase letter and contain only lowercase "
                "letters, digits, and underscores."
            ),
        ))

    if allow.characters and tp.character not in allow.characters:
        suggestions = allow.suggest_character(tp.character.upper())
        hint = f"Did you mean: {', '.join(suggestions)}?" if suggestions else None
        errors.append(CompileError(
            path = path,
            line = 1,
            col = 1,
            message = f"Character {tp.character!r} is not a registered character.",
            hint = hint,
        ))

    # Phone scenes require Openness + Stage keys per §11.13. Texting and
    # hub_option are dispatched by the mod but have no such requirement.
    if tp.scene_type == "phone":
        if not tp.openness:
            errors.append(CompileError(
                path = path, line = 1, col = 1,
                message = "Phone scenes require an 'Openness' title-page field.",
            ))
        if not tp.stage:
            errors.append(CompileError(
                path = path, line = 1, col = 1,
                message = "Phone scenes require a 'Stage' title-page field.",
            ))

    # Title-page Location, if set, must resolve.
    if tp.location:
        looked_up = _strip_time_suffix(tp.location)
        if allow.locations and looked_up not in allow.locations:
            suggestions = allow.suggest_slugline(looked_up)
            hint = f"Did you mean: {', '.join(suggestions)}?" if suggestions else None
            errors.append(CompileError(
                path = path,
                line = 1,
                col = 1,
                message = f"Location {tp.location!r} is not a registered slugline.",
                hint = hint,
            ))


def _validate_slugline(
    slug: Slugline,
    allow: Allowlists,
    errors: list[CompileError],
    path: str,
) -> None:
    looked_up = _strip_time_suffix(slug.text)
    if allow.locations and looked_up not in allow.locations:
        suggestions = allow.suggest_slugline(looked_up)
        hint = f"Did you mean: {', '.join(suggestions)}?" if suggestions else None
        errors.append(CompileError(
            path = path,
            line = slug.line,
            col = slug.col,
            message = f"Slugline location {slug.text!r} is not registered.",
            hint = hint,
        ))


def _validate_dialogue_for_texting_scene(
    block: DialogueBlock,
    errors: list[CompileError],
    path: str,
) -> None:
    """§11.13 texting rule: every dialogue line is text medium.

    Writers should leave the parenthetical off entirely (codegen auto-
    promotes to phone-text); explicit ``(spoken)`` is the only violation
    we care about, and it is a blocking error rather than a warning so
    the writer notices before the scene reaches playtest.
    """
    if block.parenthetical is not None and block.parenthetical.medium == "spoken":
        errors.append(CompileError(
            path = path,
            line = block.line,
            col = block.col,
            message = (
                "Texting scenes emit every dialogue as phone text. "
                "'(spoken)' medium is not allowed here."
            ),
        ))


def _validate_dialogue(
    block: DialogueBlock,
    allow: Allowlists,
    errors: list[CompileError],
    path: str,
) -> None:
    # Narrator is implicit in §11.5 but also allowed as an explicit speaker.
    pascal_speaker: str | None = None
    upper_to_pascal = {name.upper(): name for name in allow.characters}
    if block.speaker == "NARRATOR":
        pass
    elif allow.characters_upper and block.speaker not in allow.characters_upper:
        suggestions = allow.suggest_character(block.speaker)
        hint = f"Did you mean: {', '.join(suggestions)}?" if suggestions else None
        errors.append(CompileError(
            path = path,
            line = block.line,
            col = block.col,
            message = f"Speaker {block.speaker!r} is not a known character.",
            hint = hint,
        ))
    else:
        pascal_speaker = upper_to_pascal.get(block.speaker, block.speaker)

    if block.parenthetical is not None and pascal_speaker is not None:
        _validate_parenthetical(block.parenthetical, pascal_speaker, allow, errors, path)

    _validate_interpolations_in(
        block.text,
        source_line = block.line,
        source_col = block.col,
        allow = allow,
        errors = errors,
        path = path,
    )


# Slot-name -> callable checking whether a value belongs in that slot for a
# given character. Separated from the cross-lookup table so each slot's
# rejection message can include the exact §11.6 phrasing ("valid face for
# JeanGrey", etc.).
_SLOT_CHECKS: dict[str, str] = {
    "mood": "mood",
    "face": "face",
    "arms": "arms preset",
    "look": "look",
    "outfit": "outfit",
    "stage": "stage",
    "left_arm": "left_arm value",
    "right_arm": "right_arm value",
    "pose": "pose",
}


def _check_slot_value(
    allow: Allowlists,
    character: str,
    slot: str,
    value: str,
) -> bool:
    """Return ``True`` when ``value`` is valid for ``slot`` on ``character``."""
    if slot == "mood":
        return allow.is_mood(character, value)
    if slot == "face":
        return allow.is_face(character, value)
    if slot == "pose":
        return allow.is_pose(character, value)
    if slot == "outfit":
        return allow.is_outfit(character, value)
    if slot == "arms":
        return allow.is_arms_preset(character, value)
    if slot == "left_arm":
        return allow.is_left_arm(character, value)
    if slot == "right_arm":
        return allow.is_right_arm(character, value)
    if slot == "look":
        return allow.is_look(value)
    if slot == "stage":
        return allow.is_stage(value)
    return False


def _validate_slot(
    allow: Allowlists,
    character: str,
    slot: str,
    value: str,
    *,
    paren: Parenthetical,
    errors: list[CompileError],
    path: str,
) -> None:
    """Emit a §11.6 error when ``value`` does not belong in ``slot``.

    Uses the cross-lookup: if the value is valid in a *different* slot,
    the error names that slot as a "did you mean" hint.
    """
    # Skip the check when the per-character allowlist is empty — that means
    # the allowlists haven't been generated yet (common in unit tests that
    # bypass ``Allowlists.load``), and we shouldn't fail scenes for that.
    if slot in ("mood",) and not (allow.shared_moods or allow.char_moods):
        return
    if slot in ("face", "pose", "outfit", "arms", "left_arm", "right_arm"):
        lookups: dict[str, dict[str, set[str]]] = {
            "face": allow.char_faces,
            "pose": allow.char_poses,
            "outfit": allow.char_outfits,
            "arms": allow.char_arms,
            "left_arm": allow.char_left_arm,
            "right_arm": allow.char_right_arm,
        }
        if not lookups[slot]:
            return
    if slot == "look" and not allow.looks:
        return
    if slot == "stage" and not allow.stages:
        return

    if _check_slot_value(allow, character, slot, value):
        return

    other_slots = [
        other for other in _SLOT_CHECKS
        if other != slot and _check_slot_value(allow, character, other, value)
    ]
    hint: str | None = None
    if other_slots:
        first = other_slots[0]
        hint = (
            f"It is a valid {_SLOT_CHECKS[first]} — did you mean ({first}={value})?"
        )

    errors.append(CompileError(
        path = path,
        line = paren.line,
        col = paren.col,
        message = (
            f"{value!r} is not a valid {_SLOT_CHECKS[slot]} for {character}."
        ),
        hint = hint,
    ))


def _validate_parenthetical(
    paren: Parenthetical,
    character: str,
    allow: Allowlists,
    errors: list[CompileError],
    path: str,
) -> None:
    """Run §11.6 value checks on every populated slot of ``paren``."""
    slots = (
        ("mood", paren.mood),
        ("face", paren.face),
        ("arms", paren.arms),
        ("look", paren.look),
        ("outfit", paren.outfit),
        ("stage", paren.stage),
        ("left_arm", paren.left_arm),
        ("right_arm", paren.right_arm),
        ("pose", paren.pose),
    )
    for slot, value in slots:
        if value is None:
            continue
        _validate_slot(
            allow, character, slot, value,
            paren = paren, errors = errors, path = path,
        )


def _validate_narration(
    block: NarrationBlock,
    allow: Allowlists,
    errors: list[CompileError],
    path: str,
) -> None:
    _validate_interpolations_in(
        block.text,
        source_line = block.line,
        source_col = block.col,
        allow = allow,
        errors = errors,
        path = path,
    )


def _validate_labels_and_gotos(
    scene: Scene,
    errors: list[CompileError],
) -> None:
    """Check that every :class:`Label` is unique and every :class:`Goto` resolves."""
    path = scene.source_path
    labels: dict[str, int] = {}
    for node in scene.body:
        if isinstance(node, Label):
            if node.name in labels:
                errors.append(CompileError(
                    path = path,
                    line = node.line,
                    col = node.col,
                    message = (
                        f"Label {node.name!r} is defined twice "
                        f"(also on line {labels[node.name]})."
                    ),
                ))
            else:
                labels[node.name] = node.line
    for node in scene.body:
        if isinstance(node, Goto) and node.name not in labels:
            errors.append(CompileError(
                path = path,
                line = node.line,
                col = node.col,
                message = f"Label {node.name!r} is not defined in this scene.",
            ))


def _validate_sfx(
    node: Sfx,
    allow: Allowlists,
    errors: list[CompileError],
    path: str,
) -> None:
    sfx_set = getattr(allow, "sfx", None)
    if sfx_set and node.name not in sfx_set:
        errors.append(CompileError(
            path = path,
            line = node.line,
            col = node.col,
            message = f"SFX {node.name!r} is not registered.",
        ))


def _validate_character_reference(
    character: str,
    *,
    line: int,
    col: int,
    allow: Allowlists,
    errors: list[CompileError],
    path: str,
    context: str,
) -> None:
    """Validate that ``character`` is registered. Used by show/hide/phone."""
    if allow.characters and character not in allow.characters:
        suggestions = allow.suggest_character(character.upper())
        hint = f"Did you mean: {', '.join(suggestions)}?" if suggestions else None
        errors.append(CompileError(
            path = path,
            line = line,
            col = col,
            message = f"{context}: character {character!r} is not registered.",
            hint = hint,
        ))


def _validate_show(
    node: Show,
    allow: Allowlists,
    errors: list[CompileError],
    path: str,
) -> None:
    _validate_character_reference(
        node.character,
        line = node.line, col = node.col,
        allow = allow, errors = errors, path = path,
        context = "[[show]]",
    )
    # Cross-check each slot value against the character's per-slot allowlist
    # by piggy-backing on the parenthetical validator: build a Parenthetical
    # from the show attrs and reuse the slot checks.
    paren = Parenthetical(
        mood = node.attrs.get("mood"),
        face = node.attrs.get("face"),
        arms = node.attrs.get("arms"),
        look = node.attrs.get("look"),
        outfit = node.attrs.get("outfit"),
        stage = node.attrs.get("stage"),
        left_arm = node.attrs.get("left_arm"),
        right_arm = node.attrs.get("right_arm"),
        pose = node.attrs.get("pose"),
        line = node.line,
        col = node.col,
    )
    _validate_parenthetical(paren, node.character, allow, errors, path)


def _validate_hide(
    node: Hide,
    allow: Allowlists,
    errors: list[CompileError],
    path: str,
) -> None:
    _validate_character_reference(
        node.character,
        line = node.line, col = node.col,
        allow = allow, errors = errors, path = path,
        context = "[[hide]]",
    )


def _validate_phone_open(
    node: PhoneOpen,
    allow: Allowlists,
    errors: list[CompileError],
    path: str,
) -> None:
    if node.character is None:
        return
    _validate_character_reference(
        node.character,
        line = node.line, col = node.col,
        allow = allow, errors = errors, path = path,
        context = "[[phone open]]",
    )


def _validate_mod_set(
    node: ModSet,
    allow: Allowlists,
    errors: list[CompileError],
    path: str,
) -> None:
    """Ensure the [[mod_set]] target is registered in mod_operations.yaml."""
    if not allow.mod_operations:
        # Allowlist empty — either not loaded (unit tests) or the writer
        # hasn't registered any op yet. Flag it so the failure mode is
        # informative rather than a silent pass.
        errors.append(CompileError(
            path = path,
            line = node.line,
            col = node.col,
            message = (
                f"[[mod_set {node.call_text}]] — the mod-operations "
                "allowlist is empty. Add the operation to "
                "scenes_source/_allowlists/mod_operations.yaml."
            ),
        ))
        return
    if node.target_name not in allow.mod_operations:
        errors.append(CompileError(
            path = path,
            line = node.line,
            col = node.col,
            message = (
                f"Operation {node.target_name!r} is not registered in "
                "mod_operations.yaml."
            ),
        ))


def _validate_fx(
    node: FxCall,
    allow: Allowlists,
    errors: list[CompileError],
    path: str,
) -> None:
    """Ensure the [[fx]] target is registered in fx.yaml."""
    if not allow.fx:
        errors.append(CompileError(
            path = path,
            line = node.line,
            col = node.col,
            message = (
                f"[[fx {node.call_text}]] — the engine-effects allowlist "
                "is empty. Add the effect to "
                "scenes_source/_allowlists/fx.yaml."
            ),
        ))
        return
    if node.target_name not in allow.fx:
        errors.append(CompileError(
            path = path,
            line = node.line,
            col = node.col,
            message = (
                f"Engine effect {node.target_name!r} is not registered in "
                "fx.yaml."
            ),
        ))


def _validate_approval(
    node: Approval,
    allow: Allowlists,
    errors: list[CompileError],
    path: str,
) -> None:
    """Cross-check the [[approval]] character against characters.yaml.

    Axis and magnitude were already constrained by the parser to TNH's
    closed enums. The remaining validation is the same one we run for
    every dialogue speaker — the character must exist in the
    base-game-derived characters allowlist. When the allowlist is empty
    (unit tests load fixtures without it) we skip silently rather than
    flag every line.
    """
    if not allow.characters:
        return
    if node.character not in allow.characters:
        errors.append(CompileError(
            path = path, line = node.line, col = node.col,
            message = (
                f"Character {node.character!r} (in [[approval]]) is not "
                "registered in characters.yaml."
            ),
        ))


def _validate_choice(
    node: Choice,
    allow: Allowlists,
    errors: list[CompileError],
    path: str,
    *,
    scene_type: str,
) -> None:
    for option in node.options:
        # Option text may contain [path] interpolation per §11.10.
        _validate_interpolations_in(
            option.text,
            source_line = option.line,
            source_col = option.col,
            allow = allow,
            errors = errors,
            path = path,
        )
        _validate_node_list(
            option.body, allow, errors, path, scene_type = scene_type,
        )


def _validate_node_list(
    nodes,
    allow: Allowlists,
    errors: list[CompileError],
    path: str,
    *,
    scene_type: str,
) -> None:
    """Recurse into body nodes, validating each. Used by IfChain / Choice."""
    for node in nodes:
        if isinstance(node, Slugline):
            _validate_slugline(node, allow, errors, path)
        elif isinstance(node, DialogueBlock):
            _validate_dialogue(node, allow, errors, path)
            if scene_type == "texting":
                _validate_dialogue_for_texting_scene(node, errors, path)
        elif isinstance(node, NarrationBlock):
            _validate_narration(node, allow, errors, path)
        elif isinstance(node, Sfx):
            _validate_sfx(node, allow, errors, path)
        elif isinstance(node, Show):
            _validate_show(node, allow, errors, path)
        elif isinstance(node, Hide):
            _validate_hide(node, allow, errors, path)
        elif isinstance(node, PhoneOpen):
            _validate_phone_open(node, allow, errors, path)
        elif isinstance(node, IfChain):
            for branch in node.branches:
                _validate_node_list(
                    branch.body, allow, errors, path, scene_type = scene_type,
                )
        elif isinstance(node, Choice):
            _validate_choice(node, allow, errors, path, scene_type = scene_type)
        elif isinstance(node, ModSet):
            _validate_mod_set(node, allow, errors, path)
        elif isinstance(node, FxCall):
            _validate_fx(node, allow, errors, path)
        elif isinstance(node, Approval):
            _validate_approval(node, allow, errors, path)


def validate(scene: Scene, allow: Allowlists) -> list[CompileError]:
    """Return every error in ``scene``. Empty list means "ready to codegen"."""
    errors: list[CompileError] = []
    _validate_title_page(scene, allow, errors)

    _validate_node_list(
        scene.body, allow, errors, scene.source_path,
        scene_type = scene.title_page.scene_type,
    )
    _validate_labels_and_gotos(scene, errors)
    return errors
