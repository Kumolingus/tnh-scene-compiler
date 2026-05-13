init -1:
    define Alpha_poses = {}

define Alpha_poses["standing"] = {
    "name": _("Standing"),

    "arms": {"crossed", "neutral"},
    "left_arm": {"bra", "crossed", "hip", "neutral"},
    "right_arm": {"crossed", "hip", "neutral"},
}

define Alpha_poses["sitting"] = {
    "name": _("Sitting"),

    "arms": {"lap"},
    "left_arm": {"lap", "resting"},
    "right_arm": {"lap", "resting", "phone"},
}
