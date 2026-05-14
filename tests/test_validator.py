"""Unit tests for :mod:`tnh_scene_compiler.validator`."""

from __future__ import annotations

from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.parser import parse
from tnh_scene_compiler.validator import validate


def _scene(text: str):
    return parse(text, path = "inline.scene")


def test_validate_flags_unknown_speaker(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "ZORRO\nEn garde.\n",
    )

    errors = validate(scene, allowlists)

    assert any("ZORRO" in err.message for err in errors)


def test_validate_offers_character_suggestion(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "JEANGRE\nLine.\n",  # missing Y
    )

    errors = validate(scene, allowlists)

    assert errors
    hint = errors[0].hint or ""
    assert "JeanGrey" in hint


def test_validate_unknown_slugline_with_suggestion(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "INT. JEANGREY'S RROM\n",  # typo
    )

    errors = validate(scene, allowlists)

    assert errors
    assert "not registered" in errors[0].message
    assert "JEANGREY'S ROOM" in (errors[0].hint or "")


def test_validate_strips_time_suffix_before_lookup(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "INT. JEANGREY'S ROOM - NIGHT\n",
    )

    errors = validate(scene, allowlists)

    # No slugline error -- the ``- NIGHT`` suffix is stripped for the lookup.
    slug_errors = [e for e in errors if "Slugline" in e.message]
    assert not slug_errors


def test_validate_flags_unknown_interpolation(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "JEANGREY\nHey [player.foo], wake up.\n",
    )

    errors = validate(scene, allowlists)

    assert any("player.foo" in e.message for e in errors)


def test_validate_rejects_expression_inside_brackets(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "JEANGREY\nHey [player.name + 1], wake up.\n",
    )

    errors = validate(scene, allowlists)

    assert any("not a plain path" in e.message for e in errors)


def test_validate_phone_scene_requires_openness_and_stage(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: phone\n\n",
    )

    errors = validate(scene, allowlists)

    messages = " | ".join(e.message for e in errors)
    assert "Openness" in messages
    assert "Stage" in messages


def test_validate_phone_scene_with_openness_and_stage_ok(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: phone\n"
        "Openness: open\nStage: due\n\n",
    )

    errors = validate(scene, allowlists)

    assert errors == []


def test_validate_texting_scene_rejects_explicit_spoken_medium(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: texting\n\n"
        "JEANGREY (spoken)\nHello.\n",
    )

    errors = validate(scene, allowlists)

    assert any("spoken" in e.message.lower() for e in errors)


def test_validate_texting_scene_with_plain_dialogue_ok(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: texting\n\n"
        "JEANGREY\nHello.\n",
    )

    errors = validate(scene, allowlists)

    assert errors == []


def test_validate_hub_option_is_accepted(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: hub_option\n\n"
        "JEANGREY\nHello.\n",
    )

    errors = validate(scene, allowlists)

    assert errors == []


def test_validate_flags_non_snake_case_scene_id(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: MyBadId\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n",
    )

    errors = validate(scene, allowlists)

    assert any("snake_case" in e.message for e in errors)


def test_validate_narrator_explicit_is_accepted(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "NARRATOR\nThe wind blew.\n",
    )

    errors = validate(scene, allowlists)

    assert not errors


def test_validate_clean_scene_produces_no_errors(fixtures_dir, allowlists: Allowlists) -> None:
    text = (fixtures_dir / "minimal_cinematic.scene").read_text(encoding = "utf-8")
    scene = parse(text, path = "minimal.scene")

    errors = validate(scene, allowlists)

    assert errors == []


# --- Parenthetical cross-lookup ---------------------------------


def _scene_with_paren(paren: str) -> str:
    return (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        f"JEANGREY {paren}\nHello.\n"
    )


def test_validate_unknown_mood_produces_cross_lookup_hint(allowlists: Allowlists) -> None:
    # "smirk" is a valid face for JeanGrey but not a valid mood.
    scene = _scene(_scene_with_paren("(smirk)"))

    errors = validate(scene, allowlists)

    assert errors
    assert "valid mood for JeanGrey" in errors[0].message
    assert "face" in (errors[0].hint or "")


def test_validate_shared_mood_is_accepted(allowlists: Allowlists) -> None:
    scene = _scene(_scene_with_paren("(happy)"))

    errors = validate(scene, allowlists)

    assert errors == []


def test_validate_character_specific_mood_is_accepted(allowlists: Allowlists) -> None:
    scene = _scene(_scene_with_paren("(focused)"))

    errors = validate(scene, allowlists)

    assert errors == []


def test_validate_unknown_face_without_cross_match(allowlists: Allowlists) -> None:
    scene = _scene(_scene_with_paren("(face=nonsense_value)"))

    errors = validate(scene, allowlists)

    assert errors
    assert "valid face for JeanGrey" in errors[0].message
    assert errors[0].hint is None


def test_validate_unknown_stage_with_suggestion(allowlists: Allowlists) -> None:
    scene = _scene(_scene_with_paren("(_, _, _, _, _, bogus)"))

    errors = validate(scene, allowlists)

    assert errors
    assert "stage" in errors[0].message


# --- Directive validation ----------------------------------------


def test_validate_unknown_sfx_is_rejected(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[sfx nope_sfx]]\n",
    )

    errors = validate(scene, allowlists)

    assert errors
    assert "SFX" in errors[0].message


def test_validate_goto_to_missing_label_is_rejected(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[goto nowhere]]\n",
    )

    errors = validate(scene, allowlists)

    assert errors
    assert "nowhere" in errors[0].message


def test_validate_duplicate_label_is_rejected(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[label x]]\n\n[[label x]]\n",
    )

    errors = validate(scene, allowlists)

    assert errors
    assert "twice" in errors[0].message


def test_validate_run_allowed_operation(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[run JeanGrey.give_trait(\"x\")]]\n",
    )

    errors = validate(scene, allowlists)

    assert errors == []


def test_validate_run_unknown_operation_is_rejected(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[run JeanGrey.nuke_the_world()]]\n",
    )

    errors = validate(scene, allowlists)

    assert errors
    assert "nuke_the_world" in errors[0].message


# -- give_trait / remove_trait ------------------------------------------------


def test_validate_give_trait_known(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[give_trait JeanGrey shy]]\n",
    )

    assert validate(scene, allowlists) == []


def test_validate_give_trait_unknown_character(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[give_trait UnknownChar shy]]\n",
    )

    errors = validate(scene, allowlists)
    assert errors
    assert "UnknownChar" in errors[0].message


def test_validate_give_trait_unknown_trait(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[give_trait JeanGrey nonexistent_trait]]\n",
    )

    errors = validate(scene, allowlists)
    assert errors
    assert "nonexistent_trait" in errors[0].message


def test_validate_remove_trait_known(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[remove_trait JeanGrey bold]]\n",
    )

    assert validate(scene, allowlists) == []


# -- record -------------------------------------------------------------------


def test_validate_record_known(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[record JeanGrey kissed_player]]\n",
    )

    assert validate(scene, allowlists) == []


def test_validate_record_unknown_event(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[record JeanGrey made_up_event]]\n",
    )

    errors = validate(scene, allowlists)
    assert errors
    assert "made_up_event" in errors[0].message


# -- set_personality ----------------------------------------------------------


def test_validate_set_personality_known(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[set_personality JeanGrey dominant 3]]\n",
    )

    assert validate(scene, allowlists) == []


def test_validate_set_personality_unknown_trait(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[set_personality JeanGrey fake_personality 3]]\n",
    )

    errors = validate(scene, allowlists)
    assert errors
    assert "fake_personality" in errors[0].message


# -- fx -----------------------------------------------------------------------


def test_validate_fx_allowed_effect(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[fx phone_buzz()]]\n",
    )

    errors = validate(scene, allowlists)

    assert errors == []


def test_validate_fx_unknown_effect_is_rejected(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[fx ragnarok()]]\n",
    )

    errors = validate(scene, allowlists)

    assert errors
    assert "ragnarok" in errors[0].message


def test_validate_approval_allowed_character(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[approval JeanGrey love +large_stat]]\n",
    )

    errors = validate(scene, allowlists)

    assert errors == []


def test_validate_approval_unknown_character_is_rejected(allowlists: Allowlists) -> None:
    scene = _scene(
        "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
        "Scene Type: cinematic\nTrigger: manual\n\n"
        "[[approval Bishop trust -medium_stat]]\n",
    )

    errors = validate(scene, allowlists)

    assert errors
    assert "Bishop" in errors[0].message
    assert "characters.yaml" in errors[0].message
