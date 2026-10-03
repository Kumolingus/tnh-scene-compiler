"""Tests for the ``Target: true`` title-page key and its reserved root.

A scene that declares a target compiles to a label taking one parameter, and
``Target`` stops resolving to scene-local state inside the body. A scene that
does not declare one must reject the name outright: without the check a bare
``Target`` falls through to ``_scene_state.get("Target")`` and evaluates to
``None`` at runtime, which reads as "the condition is false" rather than as a
mistake.
"""

from __future__ import annotations

from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.codegen import CodegenContext, generate
from tnh_scene_compiler.parser import parse
from tnh_scene_compiler.validator import validate


_CTX = CodegenContext(project_prefix = "testmod")

# A hub_option scene: the shape the feature was built for — a hub in .rpy
# picks the girl and hands her to the compiled label.
_HEAD = (
    "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: hub_option\n"
)


def _scene(body: str, *, target: bool):
    """Parse a hub_option scene with or without the ``Target`` declaration."""
    head = _HEAD + ("Target: true\n" if target else "")
    return parse(head + "\n" + body, path = "inline.scene")


# --- Title page ---------------------------------------------------------------


def test_target_defaults_to_false_when_key_absent() -> None:
    scene = _scene("JEANGREY\nHi.\n", target = False)
    assert scene.title_page.target is False


def test_target_key_parses_as_bool() -> None:
    scene = _scene("JEANGREY\nHi.\n", target = True)
    assert scene.title_page.target is True


# --- Codegen ------------------------------------------------------------------


def test_declared_target_becomes_a_label_parameter(allowlists: Allowlists) -> None:
    output = generate(_scene("JEANGREY\nHi.\n", target = True), allowlists, _CTX)

    assert "label s(Target):" in output
    assert "\"uses_target\": True" in output


def test_undeclared_target_keeps_the_bare_label(allowlists: Allowlists) -> None:
    output = generate(_scene("JEANGREY\nHi.\n", target = False), allowlists, _CTX)

    assert "label s:" in output
    assert "\"uses_target\": False" in output


def test_target_is_not_rewritten_as_scene_local_state(allowlists: Allowlists) -> None:
    """The whole point: ``Target`` must reach the helper, not a state dict.

    Every bare name that is not a character, ``player`` or a time/world key
    is rendered as ``_scene_state.get(...)``. If ``Target`` fell into that
    bucket the emitted call would pass ``None`` and the branch would simply
    never fire — valid Ren'Py, silent at runtime.
    """
    body = "[[if is_pregnant(Target)]]\nJEANGREY\nYes.\n[[/if]]\n"
    output = generate(_scene(body, target = True), allowlists, _CTX)

    # The call is wrapped for the testing hub, so assert on the argument
    # rather than on a bare call spelling.
    assert "(Target,)" in output
    assert "_scene_state.get('Target')" not in output
    assert "_scene_state.get(\"Target\")" not in output


# --- Validation ---------------------------------------------------------------


def test_condition_target_is_rejected_without_the_declaration(
    allowlists: Allowlists,
) -> None:
    body = "[[if is_pregnant(Target)]]\nJEANGREY\nYes.\n[[/if]]\n"

    errors = validate(_scene(body, target = False), allowlists)

    assert len(errors) == 1
    assert "Target" in errors[0].message
    assert "Target: true" in errors[0].message


def test_condition_target_passes_with_the_declaration(allowlists: Allowlists) -> None:
    body = "[[if is_pregnant(Target)]]\nJEANGREY\nYes.\n[[/if]]\n"

    assert validate(_scene(body, target = True), allowlists) == []


def test_target_interpolation_accepts_a_character_suffix(
    allowlists: Allowlists,
) -> None:
    # The fixture allowlist exposes ``JeanGrey.petname``, so ``petname`` is a
    # suffix a real character carries — and therefore one the target may use.
    body = "JEANGREY\nAbout [Target.petname].\n"

    assert validate(_scene(body, target = True), allowlists) == []


def test_target_interpolation_is_rejected_without_the_declaration(
    allowlists: Allowlists,
) -> None:
    body = "JEANGREY\nAbout [Target.petname].\n"

    errors = validate(_scene(body, target = False), allowlists)

    assert len(errors) == 1
    assert "Target: true" in errors[0].message


def test_unknown_target_suffix_is_rejected(allowlists: Allowlists) -> None:
    # ``bogus`` is a suffix no character carries in the fixture allowlist.
    body = "JEANGREY\nAbout [Target.bogus].\n"

    errors = validate(_scene(body, target = True), allowlists)

    assert len(errors) == 1
    assert "not a known value" in errors[0].message
    assert "Target.petname" in (errors[0].hint or "")


def test_bare_target_without_a_suffix_is_rejected(allowlists: Allowlists) -> None:
    """``[Target]`` interpolates a character object, which renders as repr."""
    body = "JEANGREY\nAbout [Target].\n"

    errors = validate(_scene(body, target = True), allowlists)

    assert len(errors) == 1
    assert "not a known value" in errors[0].message


def test_target_is_not_a_valid_speaker(allowlists: Allowlists) -> None:
    """The target never appears on stage — §11.3.1.

    Moods, faces and arms are validated per character at compile time, and the
    compiler cannot know which one will be passed. A face valid for the girl
    the writer had in mind and missing on another would compile clean and
    crash only when the second is the target.
    """
    scene = parse(
        _HEAD + "Target: true\n\nTARGET\nHi.\n", path = "inline.scene",
    )

    errors = validate(scene, allowlists)

    assert errors
    assert "not a known character" in errors[0].message


def test_target_is_not_valid_in_show(allowlists: Allowlists) -> None:
    scene = parse(
        _HEAD + "Target: true\n\n[[show Target]]\n\nJEANGREY\nHi.\n",
        path = "inline.scene",
    )

    errors = validate(scene, allowlists)

    assert errors
    assert "not registered" in errors[0].message


# --- Function calls inside text ----------------------------------------------


def test_allowlisted_call_in_text_validates(allowlists: Allowlists) -> None:
    body = "JEANGREY\nShe is [is_pregnant(Target)].\n"

    assert validate(_scene(body, target = True), allowlists) == []


def test_unlisted_call_in_text_is_rejected(allowlists: Allowlists) -> None:
    body = "JEANGREY\nShe is [not_a_helper(Target)].\n"

    errors = validate(_scene(body, target = True), allowlists)

    assert errors
    assert "not_a_helper" in errors[0].message


def test_call_in_text_rejects_an_undeclared_target(allowlists: Allowlists) -> None:
    body = "JEANGREY\nShe is [is_pregnant(Target)].\n"

    errors = validate(_scene(body, target = False), allowlists)

    assert any("Target: true" in e.message for e in errors)


def test_arithmetic_in_text_is_still_rejected(allowlists: Allowlists) -> None:
    """The bracket is not an escape hatch into arbitrary Python."""
    body = "JEANGREY\nIn [day + 1] days.\n"

    errors = validate(_scene(body, target = True), allowlists)

    assert errors


def test_call_in_dialogue_is_hoisted_into_an_assignment(
    allowlists: Allowlists,
) -> None:
    """Evaluated once, on the line that says it — not on every render."""
    body = "JEANGREY\nShe is [is_pregnant(Target)].\n"

    output = generate(_scene(body, target = True), allowlists, _CTX)

    assert "$ _scene_text_0 = " in output
    assert "[_scene_text_0]" in output
    assert "[is_pregnant(Target)]" not in output
    # The assignment has to precede the line that reads it.
    assert output.index("_scene_text_0 = ") < output.index("[_scene_text_0]")


def test_call_in_narration_is_hoisted_too(allowlists: Allowlists) -> None:
    body = "She is [is_pregnant(Target)] today.\n"

    output = generate(_scene(body, target = True), allowlists, _CTX)

    assert "$ _scene_text_0 = " in output
    assert "\"She is [_scene_text_0] today.\"" in output


def test_two_calls_on_one_line_get_distinct_variables(
    allowlists: Allowlists,
) -> None:
    body = "JEANGREY\n[is_pregnant(Target)] and [ready_for_parenthood(Target)].\n"

    output = generate(_scene(body, target = True), allowlists, _CTX)

    assert "$ _scene_text_0 = " in output
    assert "$ _scene_text_1 = " in output
    assert "[_scene_text_0] and [_scene_text_1]" in output


# --- Hub overridability -------------------------------------------------------


def _allowlists_with_signatures(base: Allowlists, **signatures: str) -> Allowlists:
    """Copy ``base`` with declared return types on its condition functions."""
    import dataclasses

    return dataclasses.replace(base, condition_function_signatures = dict(signatures))


def test_target_argument_keeps_a_call_overridable(allowlists: Allowlists) -> None:
    """The reason predicates take only a character and never a value string.

    A literal argument makes a call unoverridable, so the hub could not flip
    it. ``Target`` has to count as a character argument or the whole
    one-predicate-per-value shape buys nothing.
    """
    body = "[[if is_pregnant(Target)]]\nJEANGREY\nYes.\n[[/if]]\n"

    output = generate(_scene(body, target = True), allowlists, _CTX)

    assert "testmod_testing_eval_condition(" in output
    assert "\"args\": [\"Target\"]" in output


def test_a_value_returning_function_is_not_offered_as_an_override(
    allowlists: Allowlists,
) -> None:
    """The hub's override is three-state, which is wrong for a number.

    Forcing ``True`` on a count makes every ``== N`` comparison false and
    renders "True" where the writer asked for the value.
    """
    allow = _allowlists_with_signatures(
        allowlists, is_pregnant = "is_pregnant(Character) -> int",
    )
    body = "JEANGREY\nIn [is_pregnant(Target)] days.\n"

    output = generate(_scene(body, target = True), allow, _CTX)

    assert "testmod_testing_eval_condition(" not in output
    assert "\"condition_specs\": []" in output
    assert "$ _scene_text_0 = is_pregnant(Target)" in output


def test_a_bool_returning_function_stays_overridable(
    allowlists: Allowlists,
) -> None:
    allow = _allowlists_with_signatures(
        allowlists, is_pregnant = "is_pregnant(Character) -> bool",
    )
    body = "[[if is_pregnant(Target)]]\nJEANGREY\nYes.\n[[/if]]\n"

    output = generate(_scene(body, target = True), allow, _CTX)

    assert "testmod_testing_eval_condition(" in output


def test_plain_paths_are_left_in_the_string(allowlists: Allowlists) -> None:
    """Ren'Py resolves a plain path itself; hoisting it would buy nothing."""
    body = "JEANGREY\nHey [player.petname].\n"

    output = generate(_scene(body, target = False), allowlists, _CTX)

    assert "[player.petname]" in output
    assert "_scene_text_0" not in output
