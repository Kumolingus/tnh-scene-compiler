define Alpha_all_Clothes["blue_jeans"] = {
    "name": _("blue jeans"),
    "short_name": _("jeans"),

    "type": "pants",
}

define Alpha_all_Clothes["white_tshirt"] = {
    "name": _("white t-shirt"),

    "type": "top",
}

# Duplicate key — should be deduplicated.
define Alpha_all_Clothes["blue_jeans"] = {
    "name": _("blue jeans"),

    "type": "pants",
}
