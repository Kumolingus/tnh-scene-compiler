"""Unit tests for :mod:`tnh_scene_compiler.validator`."""

from __future__ import annotations

from tnh_scene_compiler.allowlists import Allowlists, signature_arity
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


def test_validate_look_set_all_members_accepted(allowlists: Allowlists) -> None:
    scene = _scene(_scene_with_paren("(face=smirk, look={down|away})"))

    errors = validate(scene, allowlists)

    assert errors == []


def test_validate_look_set_rejects_an_unknown_member(allowlists: Allowlists) -> None:
    scene = _scene(_scene_with_paren("(look={down|bogus_value})"))

    errors = validate(scene, allowlists)

    assert errors
    assert "valid look for JeanGrey" in errors[0].message


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


# -- signature_arity helper ---------------------------------------------------


def test_signature_arity_all_defaults() -> None:
    assert signature_arity("bamf(x = 0.5, y = 0.5) -> None") == (0, 2)


def test_signature_arity_required_positional() -> None:
    assert signature_arity("f(Character, preference)") == (2, 2)


def test_signature_arity_typed_required() -> None:
    # The `| None` union annotation must not confuse the parser.
    assert signature_arity("f(Character: CharacterClass | None) -> bool") == (1, 1)


def test_signature_arity_no_params() -> None:
    assert signature_arity("f() -> None") == (0, 0)


def test_signature_arity_mixed_required_and_default() -> None:
    assert signature_arity("f(a, b, c = 1, d = 2) -> None") == (2, 4)


def test_signature_arity_varargs_is_unbounded() -> None:
    assert signature_arity("f(a, *rest) -> None") == (1, None)


def test_signature_arity_unparseable_returns_none() -> None:
    assert signature_arity("not a signature !!!") is None
    assert signature_arity("") is None


# -- run / fx / condition-function arity --------------------------------------

_ARITY_HEAD = (
    "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
    "Scene Type: cinematic\nTrigger: manual\n\n"
)


def _arity_allowlists() -> Allowlists:
    """Allowlists carrying signatures so the arity checks engage.

    Names registered without a signature (``no_sig_fx`` / ``no_sig_run``)
    exercise the graceful skip: the name passes, but no arity check runs.
    """
    return Allowlists(
        characters = ["JeanGrey", "Rogue", "Narrator", "Player"],
        characters_upper = {"JEANGREY", "ROGUE", "NARRATOR", "PLAYER"},
        fx = {"bamf", "phone_buzz", "no_sig_fx"},
        fx_signatures = {
            "bamf": (
                "bamf(x = 0.5, y = 0.5, initial = 1.0, final_alpha = 0.0, "
                "pause = True) -> None"
            ),
            "phone_buzz": "phone_buzz() -> None",
        },
        run_operations = {"record_player_preference", "retire_for_the_night", "no_sig_run"},
        run_operation_signatures = {
            "record_player_preference": (
                "pregnancy_mod_record_player_preference(Character, preference)"
            ),
            "retire_for_the_night": (
                "pregnancy_mod_announcement_retire_for_the_night(Character)"
            ),
        },
        condition_functions = {
            "ready_for_parenthood", "announcer_was_present", "are_Characters_friends",
        },
        condition_function_signatures = {
            "ready_for_parenthood": (
                "pregnancy_mod_ready_for_parenthood(Character: CharacterClass | None) -> bool"
            ),
            "announcer_was_present": (
                "pregnancy_mod_announcement_announcer_was_present() -> bool"
            ),
            "are_Characters_friends": (
                "are_Characters_friends(Characters, level: int = 1) -> bool"
            ),
        },
    )


def test_fx_arity_within_bounds_ok() -> None:
    scene = _scene(_ARITY_HEAD + "[[fx bamf(0.5, 0.5)]]\n")
    assert validate(scene, _arity_allowlists()) == []


def test_fx_arity_max_bound_ok() -> None:
    scene = _scene(_ARITY_HEAD + "[[fx bamf(1, 2, 3, 4, 5)]]\n")
    assert validate(scene, _arity_allowlists()) == []


def test_fx_arity_too_many_is_rejected() -> None:
    scene = _scene(_ARITY_HEAD + "[[fx bamf(1, 2, 3, 4, 5, 6)]]\n")
    errors = validate(scene, _arity_allowlists())
    assert errors
    assert "at most 5 arguments" in errors[0].message
    assert "got 6" in errors[0].message
    assert "bamf" in (errors[0].hint or "")


def test_fx_arity_skipped_without_signature() -> None:
    scene = _scene(_ARITY_HEAD + "[[fx no_sig_fx(1, 2, 3)]]\n")
    assert validate(scene, _arity_allowlists()) == []


def test_run_arity_exact_ok() -> None:
    scene = _scene(_ARITY_HEAD + "[[run record_player_preference(Rogue, \"keep\")]]\n")
    assert validate(scene, _arity_allowlists()) == []


def test_run_arity_too_few_is_rejected() -> None:
    scene = _scene(_ARITY_HEAD + "[[run record_player_preference(Rogue)]]\n")
    errors = validate(scene, _arity_allowlists())
    assert errors
    assert "exactly 2 arguments" in errors[0].message
    assert "got 1" in errors[0].message


def test_run_arity_single_required_ok() -> None:
    scene = _scene(_ARITY_HEAD + "[[run retire_for_the_night(Rogue)]]\n")
    assert validate(scene, _arity_allowlists()) == []


def test_run_arity_skipped_without_signature() -> None:
    scene = _scene(_ARITY_HEAD + "[[run no_sig_run(1, 2, 3)]]\n")
    assert validate(scene, _arity_allowlists()) == []


def test_condition_function_arity_ok() -> None:
    scene = _scene(
        _ARITY_HEAD
        + "[[if ready_for_parenthood(JeanGrey)]]\nShe nods.\n[[/if]]\n",
    )
    assert validate(scene, _arity_allowlists()) == []


def test_condition_function_arity_too_few_is_rejected() -> None:
    scene = _scene(
        _ARITY_HEAD + "[[if ready_for_parenthood()]]\nShe nods.\n[[/if]]\n",
    )
    errors = validate(scene, _arity_allowlists())
    assert errors
    assert "exactly 1 argument" in errors[0].message


def test_condition_function_arity_too_many_is_rejected() -> None:
    scene = _scene(
        _ARITY_HEAD
        + "[[if announcer_was_present(JeanGrey)]]\nShe nods.\n[[/if]]\n",
    )
    errors = validate(scene, _arity_allowlists())
    assert errors
    # A zero-parameter function reads as "exactly 0", not "at most 0".
    assert "exactly 0 arguments" in errors[0].message
    assert "got 1" in errors[0].message


def test_friends_with_sugar_transforms_to_single_list_arg_arity_ok() -> None:
    # Regression: are_Characters_friends(Characters, level=1) requires 1
    # arg minimum, 2 max. The DSL used to emit it as 2 separate positional
    # args (Character, Y) instead of one list [Character, Y] — this test
    # locks in the corrected 1-arg shape passing arity validation.
    scene = _scene(
        _ARITY_HEAD + "[[if JeanGrey.friends_with(Rogue)]]\nShe nods.\n[[/if]]\n",
    )
    assert validate(scene, _arity_allowlists()) == []


# -- character-property validation --------------------------------------------

_PROP_HEAD = (
    "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
    "Scene Type: cinematic\nTrigger: manual\n\n"
)


def _prop_allowlists() -> Allowlists:
    return Allowlists(
        characters = ["JeanGrey", "Rogue", "Narrator", "Player"],
        characters_upper = {"JEANGREY", "ROGUE", "NARRATOR", "PLAYER"},
        character_properties = {"desire", "breast_size", "love"},
        character_property_types = {
            "desire": "float", "breast_size": "int", "love": "int",
        },
    )


def test_known_property_passes() -> None:
    scene = _scene(_PROP_HEAD + "[[if JeanGrey.desire >= 0.5]]\nOk.\n[[/if]]\n")
    assert validate(scene, _prop_allowlists()) == []


def test_unknown_property_is_rejected_with_suggestion() -> None:
    scene = _scene(_PROP_HEAD + "[[if JeanGrey.desrie >= 0.5]]\nOk.\n[[/if]]\n")
    errors = validate(scene, _prop_allowlists())
    assert errors
    assert "desrie" in errors[0].message
    assert "character_properties.yaml" in errors[0].message
    assert "desire" in (errors[0].hint or "")


def test_numeric_approval_form_passes_when_love_registered() -> None:
    # `X.love >= 500` (numeric threshold) isn't rewritten by the DSL sugar
    # (only tier names are), so it reaches the property validator as a bare
    # attribute — must pass because love is a registered property.
    scene = _scene(_PROP_HEAD + "[[if JeanGrey.love >= 500]]\nOk.\n[[/if]]\n")
    assert validate(scene, _prop_allowlists()) == []


def test_property_check_skipped_when_allowlist_empty() -> None:
    # A project without a character_properties.yaml keeps the previous
    # behaviour: bare attribute access passes unvalidated (not newly rejected).
    empty = Allowlists(
        characters = ["JeanGrey"], characters_upper = {"JEANGREY"},
    )
    scene = _scene(_PROP_HEAD + "[[if JeanGrey.whatever >= 1]]\nOk.\n[[/if]]\n")
    assert validate(scene, empty) == []


def test_sugar_is_not_flagged_as_property() -> None:
    # .mood/.nearby are rewritten to calls before the attribute check; none
    # should surface as an unknown property.
    allow = _prop_allowlists()
    for cond in (
        'JeanGrey.mood == "normal"',
        "JeanGrey.nearby",
    ):
        scene = _scene(_PROP_HEAD + f"[[if {cond}]]\nOk.\n[[/if]]\n")
        errors = [e for e in validate(scene, allow) if "property" in e.message.lower()]
        assert errors == [], (cond, errors)


def test_object_property_passes_as_a_call_argument() -> None:
    # chance_of_repeat_Event's first argument is a bare `Char.History`, which
    # reaches the property validator (attributes inside call args are
    # collected). Registering History — even as `usable_bare: false`, which
    # only hides it from the builder — must make the whole condition validate.
    allow = Allowlists(
        characters = ["JeanGrey"], characters_upper = {"JEANGREY"},
        character_properties = {"desire", "History"},
        character_properties_bare = {"desire"},
        condition_functions = {"chance_of_repeat_Event"},
        condition_function_signatures = {
            "chance_of_repeat_Event":
                "chance_of_repeat_Event(History, Item: str, chance: float = 0) -> float",
        },
    )
    scene = _scene(
        _PROP_HEAD
        + '[[if chance_of_repeat_Event(JeanGrey.History, "kissed") >= 0.5]]\n'
        + "Ok.\n[[/if]]\n",
    )
    assert validate(scene, allow) == []


def test_method_call_target_is_not_flagged_as_property() -> None:
    # Char.History.check(...) is a method call — its attribute target must not
    # be mistaken for a bare property.
    allow = Allowlists(
        characters = ["JeanGrey"], characters_upper = {"JEANGREY"},
        character_properties = {"desire"},
        character_methods = {"check"},
        character_method_signatures = {
            "check": "Character.History.check(item: str) -> int",
        },
    )
    scene = _scene(
        _PROP_HEAD + '[[if JeanGrey.History.check("kissed") > 0]]\nOk.\n[[/if]]\n',
    )
    errors = [e for e in validate(scene, allow) if "property" in e.message.lower()]
    assert errors == []
