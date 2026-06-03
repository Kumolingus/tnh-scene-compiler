"""Unit tests for :mod:`tnh_scene_compiler.codegen`."""

from __future__ import annotations

from pathlib import Path

from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.codegen import (
    CodegenContext,
    generate,
    generate_event_entry,
    generate_events_rpy,
)
from tnh_scene_compiler.parser import parse


# All tests in this file use a "testmod" prefix so assertions don't depend
# on the pregnancy mod's concrete prefix.
_CTX = CodegenContext(project_prefix = "testmod")


def test_codegen_scene_rpy_has_label_but_no_event_block(
    fixtures_dir: Path,
    allowlists: Allowlists,
) -> None:
    text = (fixtures_dir / "minimal_cinematic.scene").read_text(encoding = "utf-8")
    scene = parse(text, path = "minimal.scene")

    output = generate(scene, allowlists, _CTX)

    # Phase 6D: event registration is centralised in _events.rpy; the
    # per-scene .rpy must carry only the label block.
    assert "define all_Events" not in output
    assert "label mymod_scene_minimal:" in output
    assert "$ ongoing_Event = True" in output
    assert "$ ongoing_Event = False" in output
    assert output.rstrip().endswith("return")


def test_generate_event_entry_emits_events_block(
    fixtures_dir: Path,
) -> None:
    text = (fixtures_dir / "minimal_cinematic.scene").read_text(encoding = "utf-8")
    scene = parse(text, path = "minimal.scene")

    entry = generate_event_entry(scene)

    assert "define all_Events['mymod_scene_minimal']" in entry
    assert "\"flags\": {\"manual\"}" in entry


def test_generate_events_rpy_aggregates_cinematic_scenes(
    fixtures_dir: Path,
) -> None:
    text_a = (fixtures_dir / "minimal_cinematic.scene").read_text(encoding = "utf-8")
    text_b = (fixtures_dir / "narration_only.scene").read_text(encoding = "utf-8")
    scene_a = parse(text_a, path = "a.scene")
    scene_b = parse(text_b, path = "b.scene")

    output = generate_events_rpy([scene_a, scene_b], _CTX)

    assert "Auto-generated" in output
    assert "define all_Events['mymod_scene_minimal']" in output
    assert "define all_Events['mymod_scene_narration_only']" in output


def test_generate_events_rpy_empty_scene_list_still_produces_header() -> None:
    output = generate_events_rpy([], _CTX)

    assert "Auto-generated" in output
    assert "define all_Events" not in output


def test_codegen_emits_set_the_scene_for_body_slugline(
    fixtures_dir: Path,
    allowlists: Allowlists,
) -> None:
    text = (fixtures_dir / "minimal_cinematic.scene").read_text(encoding = "utf-8")
    scene = parse(text, path = "minimal.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ set_the_scene(location = \"loc_XavierSchool_JeanGreyRoom\"" in output


def test_codegen_title_page_location_emits_set_the_scene(
    fixtures_dir: Path,
    allowlists: Allowlists,
) -> None:
    text = (fixtures_dir / "with_location_key.scene").read_text(encoding = "utf-8")
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ set_the_scene(location = \"loc_XavierSchool_PlayerRoom\"" in output


def test_codegen_narration_uses_bare_quoted_string(
    fixtures_dir: Path,
    allowlists: Allowlists,
) -> None:
    text = (fixtures_dir / "narration_only.scene").read_text(encoding = "utf-8")
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "    \"The room was quiet. Too quiet.\"" in output
    assert "    \"You walked to the window.\"" in output


def test_codegen_dialogue_emits_speaker_and_text(
    fixtures_dir: Path,
    allowlists: Allowlists,
) -> None:
    text = (fixtures_dir / "minimal_cinematic.scene").read_text(encoding = "utf-8")
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "    ch_JeanGrey \"Hey [player.petname], you awake?\"" in output


def test_codegen_interpolation_is_passed_through(
    allowlists: Allowlists,
) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "JEANGREY\nHey [player.petname].\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "[player.petname]" in output


def test_event_entry_conditions_wrap_into_condition_class(
    fixtures_dir: Path,
) -> None:
    text = (fixtures_dir / "with_conditions.scene").read_text(encoding = "utf-8")
    scene = parse(text, path = "inline.scene")

    entry = generate_event_entry(scene)

    assert "\"conditions\": ConditionClass(" in entry
    assert "JeanGrey.love >= 500" in entry
    assert "\"flags\": {\"sleeping\"}" in entry
    assert "\"priority\": 175" in entry
    assert "\"repeatable\": True" in entry
    assert "\"tags\": {\"mymod_tagged\"}" in entry


def test_event_entry_default_priority_is_50() -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
    )
    scene = parse(text, path = "inline.scene")

    entry = generate_event_entry(scene)

    assert "\"priority\": 50" in entry


def test_codegen_parenthetical_mood_emits_change_mood(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "JEANGREY (happy)\nLine.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ JeanGrey.change_mood(\"happy\")" in output
    assert "ch_JeanGrey \"Line.\"" in output
    # The mood call must precede the dialogue line.
    assert output.index("change_mood") < output.index("ch_JeanGrey \"Line.\"")


def test_codegen_arms_with_left_and_right_args(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "JEANGREY (arms=crossed, left_arm=extended, right_arm=hip)\nLine.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    expected = (
        "$ JeanGrey.change_arms(\"crossed\", "
        "left_arm = \"extended\", right_arm = \"hip\")"
    )
    assert expected in output


def test_codegen_face_look_outfit_all_emit_change_calls(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "JEANGREY (face=smirk, look=at_player, outfit=Pajamas)\nLine.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ JeanGrey.change_face(\"smirk\")" in output
    assert "$ JeanGrey.eyes = \"at_player\"" in output
    assert (
        "$ JeanGrey.change_face("
        "getattr(JeanGrey, \"face\", None), eyes = \"at_player\")"
    ) in output
    assert (
        "$ change_Outfit(JeanGrey, "
        "JeanGrey.Wardrobe.Outfits[\"Pajamas\"], instant = True)"
    ) in output


def test_codegen_stage_emits_add_characters_with_mapped_direction(
    allowlists: Allowlists,
) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "JEANGREY (_, _, _, _, _, stage_left)\nLine.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    # stage_left (allowlist form) maps to "left" (add_Characters arg).
    assert (
        "$ add_Characters(JeanGrey, direction = \"left\", fade = False)"
    ) in output


def test_codegen_stage_unmapped_value_emits_todo(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "JEANGREY (_, _, _, _, _, stage_far_far_left)\nLine.\n"
    )
    # Need to extend the allowlist fixture for this stage value.
    from dataclasses import replace
    extended = replace(
        allowlists,
        stages = allowlists.stages | {"stage_far_far_left"},
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, extended, _CTX)

    assert "# TODO(stage): 'stage_far_far_left'" in output


def test_codegen_pause_emits_renpy_pause(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "[[pause 0.5]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ renpy.pause(0.5)" in output


def test_codegen_sfx_emits_sound_play(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "[[sfx phone_buzz]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ renpy.sound.play(\"phone_buzz.ogg\")" in output


def test_codegen_set_initializes_and_writes_scene_state(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "[[set keep = true]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert (
        "$ _scene_state = "
        "dict(getattr(testmod_runtime, 'scene_state', None) or {})"
    ) in output
    assert "$ _scene_state['keep'] = True" in output


def test_codegen_label_and_goto_use_local_dot_labels(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "[[label mid]]\n\n[[goto mid]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "label .mid:" in output
    assert "jump .mid" in output


def test_codegen_show_emits_add_characters_and_change_calls(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "[[show JeanGrey stage=stage_left mood=happy face=smirk]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert (
        "$ add_Characters(JeanGrey, direction = \"left\", fade = False)"
    ) in output
    assert "$ JeanGrey.change_mood(\"happy\")" in output
    assert "$ JeanGrey.change_face(\"smirk\")" in output


def test_codegen_show_emits_state_changes_before_add_characters(
    allowlists: Allowlists,
) -> None:
    """State changes (outfit, mood, face, arms) must precede add_Characters."""
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "[[show JeanGrey stage=stage_center outfit=Pajamas mood=happy face=smirk arms=crossed]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    # Pin the relative ordering: every state-change line is above the
    # add_Characters line.
    outfit_idx = output.index("change_Outfit(JeanGrey")
    mood_idx = output.index("change_mood(\"happy\")")
    face_idx = output.index("change_face(\"smirk\")")
    arms_idx = output.index("change_arms(\"crossed\")")
    add_idx = output.index("add_Characters(JeanGrey,")

    assert outfit_idx < add_idx, "Outfit must change before add_Characters"
    assert mood_idx < add_idx, "Mood must change before add_Characters"
    assert face_idx < add_idx, "Face must change before add_Characters"
    assert arms_idx < add_idx, "Arms must change before add_Characters"
    assert outfit_idx < mood_idx


def test_codegen_hide_emits_hide_character(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "[[hide JeanGrey]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ hide_Character(JeanGrey, fade = False)" in output


def test_codegen_hide_fade_emits_dissolve(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "[[hide JeanGrey fade]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ hide_Character(JeanGrey, fade = 0.5)" in output


def test_codegen_fade_to_black_emits_base_game_helper(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "[[fade to black]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ fade_to_black(0.4)" in output


def test_codegen_fade_from_black_emits_base_game_helper(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "[[fade from black]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ fade_in_from_black(0.4)" in output


def test_codegen_fade_with_explicit_duration(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "[[fade to black 0.6]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ fade_to_black(0.6)" in output


def test_codegen_show_fade_emits_add_characters_with_fade(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "[[show JeanGrey stage=stage_center fade=true]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "add_Characters(JeanGrey, direction = \"middle\", fade = True)" in output


def test_codegen_call_emits_ren_py_call(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "[[call mymod_scene_next]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "call mymod_scene_next" in output


def test_codegen_phone_open_and_close(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "[[phone open JeanGrey]]\n\n[[phone close]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ open_texts(JeanGrey)" in output
    assert "$ renpy.hide_screen(\"phone_screen\")" in output


def test_codegen_text_medium_emits_phone_text_helper(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "JEANGREY (text)\nI can't settle tonight.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ receive_text(JeanGrey, \"I can't settle tonight.\")" in output
    # And the spoken form should NOT appear for this line.
    assert "JeanGrey \"I can't settle tonight.\"" not in output


def test_codegen_text_medium_emits_send_text_for_player(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "PLAYER (text)\nI'm here.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ send_text(current_phone_Chat, \"I'm here.\")" in output


def test_codegen_phone_scene_omits_ongoing_event_wrapping(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: phone\n"
        "Openness: open\nStage: due\n\n"
        "JEANGREY (text)\nHi.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    # Phone scenes are called by mod code, not the event scheduler.
    assert "ongoing_Event = True" not in output
    assert "ongoing_Event = False" not in output
    # Openness/Stage are emitted as header comments for dev reference.
    assert "# Openness: open" in output
    assert "# Stage: due" in output


def test_codegen_texting_scene_forces_phone_text_medium(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: texting\n\n"
        "JEANGREY\nHello.\nJEANGREY\nHow are you?\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ receive_text(JeanGrey, \"Hello.\")" in output
    assert "JeanGrey \"Hello.\"" not in output


def test_codegen_hub_option_has_no_event_wrapping(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: hub_option\n\n"
        "JEANGREY\nHi.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "ongoing_Event" not in output


def test_generate_events_rpy_skips_non_cinematic_scenes(
    allowlists: Allowlists,
) -> None:
    phone_src = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: phone\n"
        "Openness: open\nStage: due\n\n"
        "JEANGREY\nHi.\n"
    )
    scene = parse(phone_src, path = "inline.scene")

    events = generate_events_rpy([scene], _CTX)

    assert "define all_Events" not in events


def test_codegen_escapes_backslash_and_quote(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\nTrigger: manual\n\n"
        "JEANGREY\nShe said \"hi\" and C:\\\\Users is scary.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "\\\"hi\\\"" in output


# --- Testing-hub metadata block ----------------------------------------------


def test_codegen_emits_metadata_block_with_core_fields(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\nDescription: Hub preview only.\n\n"
        "JEANGREY\nHi.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    # Block precedes the label so module-level dict assignment runs at boot.
    metadata_idx = output.find("testmod_scene_metadata[")
    label_idx = output.find("label s:")
    assert 0 < metadata_idx < label_idx
    assert "\"character\": \"JeanGrey\"" in output
    assert "\"scene_type\": \"cinematic\"" in output
    assert "\"description\": \"Hub preview only.\"" in output
    assert "\"uses_target\": False" in output


def test_codegen_metadata_phone_carries_openness_and_stage(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: phone\n"
        "Openness: open\nStage: due\n\nJEANGREY\nText.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "\"openness\": \"open\"" in output
    assert "\"stage_key\": \"due\"" in output


def test_codegen_metadata_collects_bool_toggles_from_set(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\n[[set picked]]\n[[set explained = false]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert (
        "{\"path\": \"explained\", \"kind\": \"bool\", "
        "\"choices\": [False, True], \"default\": False}"
    ) in output
    assert (
        "{\"path\": \"picked\", \"kind\": \"bool\", "
        "\"choices\": [False, True], \"default\": False}"
    ) in output


def test_codegen_metadata_collects_string_choices_from_compare(
    allowlists: Allowlists,
) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\n[[set reason = \"automatic\"]]\n"
        "[[if reason == \"conversation\"]]\nJEANGREY\nA.\n[[else]]\n"
        "JEANGREY\nB.\n[[/if]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert (
        "{\"path\": \"reason\", \"kind\": \"str\", "
        "\"choices\": [\"automatic\", \"conversation\"], "
        "\"default\": \"automatic\"}"
    ) in output


def test_codegen_metadata_ignores_condition_function_calls(
    allowlists: Allowlists,
) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\n[[if testmod_ready_for_parenthood(JeanGrey)]]\n"
        "JEANGREY\nA.\n[[/if]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    # Condition functions read live game state -- never appear as state_specs.
    assert "\"state_specs\": []" in output
    assert "testmod_ready_for_parenthood" not in output.split("label s:")[0]


def test_codegen_metadata_collects_bare_if_as_bool_toggle(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\n[[if picked]]\nJEANGREY\nA.\n[[/if]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert (
        "{\"path\": \"picked\", \"kind\": \"bool\", "
        "\"choices\": [False, True], \"default\": False}"
    ) in output


def test_codegen_seeds_scene_state_from_override_store_var(
    allowlists: Allowlists,
) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\nJEANGREY\nHi.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert (
        "$ _scene_state = "
        "dict(getattr(testmod_runtime, 'scene_state', None) or {})"
    ) in output


# --- Condition-function override wrapping -----------------------------------


def test_codegen_wraps_allowlisted_condition_call(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\n[[if ready_for_parenthood(JeanGrey)]]\n"
        "JEANGREY\nA.\n[[/if]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert (
        "if testmod_testing_eval_condition("
        "'ready_for_parenthood', ready_for_parenthood, (JeanGrey,), ('JeanGrey',))"
    ) in output


def test_codegen_metadata_lists_overridable_condition(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\n[[if ready_for_parenthood(JeanGrey)]]\n"
        "JEANGREY\nA.\n[[/if]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert (
        "{\"name\": \"ready_for_parenthood\", "
        "\"args\": [\"JeanGrey\"], \"kind\": \"bool\"}"
    ) in output


def test_codegen_does_not_wrap_unallowlisted_call(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\n[[if unknown_helper(JeanGrey)]]\n"
        "JEANGREY\nA.\n[[/if]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "if unknown_helper(JeanGrey):" in output
    assert "testmod_testing_eval_condition" not in output
    assert "\"condition_specs\": []" in output


def test_codegen_does_not_wrap_call_with_literal_arg(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\n[[if check_approval(JeanGrey, \"high\")]]\n"
        "JEANGREY\nA.\n[[/if]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "if check_approval(JeanGrey, \"high\"):" in output
    assert "testmod_testing_eval_condition" not in output


def test_codegen_dedupes_repeated_condition_calls(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\n[[if ready_for_parenthood(JeanGrey)]]\n"
        "JEANGREY\nA.\n[[/if]]\n[[if ready_for_parenthood(JeanGrey)]]\n"
        "JEANGREY\nB.\n[[/if]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    # Two wrapped call sites...
    assert output.count("testmod_testing_eval_condition") == 2
    # ...but only one entry in condition_specs.
    assert output.count(
        "{\"name\": \"ready_for_parenthood\", "
        "\"args\": [\"JeanGrey\"], \"kind\": \"bool\"}"
    ) == 1


def test_codegen_wraps_condition_call_inside_choice_option_condition(
    allowlists: Allowlists,
) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\n[[choice]]\n"
        "= Option A [[if ready_for_parenthood(JeanGrey)]]\n"
        "JEANGREY\nA.\n[[/choice]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "testmod_testing_eval_condition" in output
    assert "\"name\": \"ready_for_parenthood\"" in output


# --- called_scenes metadata --------------------------------------------------


def test_codegen_metadata_lists_called_scene_ids(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: parent\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\nJEANGREY\nGoing to talk.\n"
        "[[call other_scene]]\n[[call yet_another]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "\"called_scenes\": [\"other_scene\", \"yet_another\"]" in output


def test_codegen_metadata_dedupes_called_scene_ids(allowlists: Allowlists) -> None:
    text = (
        "Title: T\nScene Id: parent\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\n[[call sub]]\n[[call sub]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "\"called_scenes\": [\"sub\"]" in output


def test_codegen_metadata_called_scenes_walks_into_branches(
    allowlists: Allowlists,
) -> None:
    text = (
        "Title: T\nScene Id: parent\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\n[[set picked]]\n[[if picked]]\n"
        "[[call branch_target]]\n[[/if]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "\"called_scenes\": [\"branch_target\"]" in output


def test_codegen_metadata_called_scenes_empty_when_no_calls(
    allowlists: Allowlists,
) -> None:
    text = (
        "Title: T\nScene Id: standalone\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\nJEANGREY\nNo chain.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "\"called_scenes\": []" in output


# --- Cinematic location/character cleanup (TNH end-of-event pattern) -------


def test_codegen_cinematic_passes_show_characters_false_to_set_the_scene(
    allowlists: Allowlists,
) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\nINT. JEANGREY'S ROOM\n\nJEANGREY\nHi.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert (
        "$ set_the_scene(location = \"loc_XavierSchool_JeanGreyRoom\", "
        "greetings = False, show_Characters = False)"
    ) in output
    # The cinematic slugline must also clear Present so a later
    # add_Characters cannot re-render a stray NPC (show_Characters=False
    # only suppresses rendering, it does not empty Location.Present).
    assert "$ remove_everyone_but([], send_Offscreen = True)" in output


def test_codegen_phone_omits_show_characters_flag(
    allowlists: Allowlists,
) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: phone\n"
        "Openness: open\nStage: due\n\nINT. JEANGREY'S ROOM\n\nJEANGREY\nHi.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "show_Characters = False" not in output


def test_codegen_cinematic_clears_stage_at_scene_end(
    allowlists: Allowlists,
) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\nJEANGREY\nBye.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    cleanup = output.index("$ set_the_scene(show_Characters = False, silent = True)")
    end_event = output.index("$ ongoing_Event = False")
    assert cleanup < end_event


def test_codegen_phone_does_not_emit_end_stage_cleanup(
    allowlists: Allowlists,
) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: phone\n"
        "Openness: open\nStage: due\n\nJEANGREY\nText.\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "set_the_scene(show_Characters = False, silent = True)" not in output


def test_codegen_emits_approval_with_named_stat_tier(
    allowlists: Allowlists,
) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\n"
        "[[approval JeanGrey love +large_stat]]\n"
        "[[approval JeanGrey trust -medium_stat]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ update_approval(JeanGrey, \"love\", large_stat)" in output
    assert "$ update_approval(JeanGrey, \"trust\", -medium_stat)" in output


def test_codegen_emits_approval_with_integer_literal(
    allowlists: Allowlists,
) -> None:
    text = (
        "Title: T\nScene Id: s\nCharacter: JeanGrey\nScene Type: cinematic\n"
        "Trigger: manual\n\n"
        "[[approval Rogue love +25]]\n"
    )
    scene = parse(text, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "$ update_approval(Rogue, \"love\", 25)" in output
