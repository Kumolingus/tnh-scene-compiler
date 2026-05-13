# Auto-generated from minimal.scene. Do not edit by hand.

init python:
    testmod_scene_metadata["mymod_scene_minimal"] = {
        "character": "JeanGrey",
        "scene_type": "cinematic",
        "openness": "",
        "stage_key": "",
        "description": "",
        "state_specs": [],
        "condition_specs": [],
        "called_scenes": [],
        "uses_target": False,
    }

label mymod_scene_minimal:
    $ ongoing_Event = True
    $ _scene_state = dict(getattr(testmod_runtime, 'scene_state', None) or {})

    $ set_the_scene(location = "loc_XavierSchool_JeanGreyRoom", greetings = False, show_Characters = False)
    "She sits on her bed and sighs."
    ch_JeanGrey "Hey [player.petname], you awake?"
    "You nod silently."
    ch_JeanGrey "Good. I need you here tonight."

    $ set_the_scene(show_Characters = False, silent = True)
    $ ongoing_Event = False
    return
