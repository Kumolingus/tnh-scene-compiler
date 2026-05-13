define all_Locations["loc_SchoolSite_Library"] = {
    "name": _("School Library"),
    "tag": "Library",
    "module": "SchoolSite",
    "traits": {
        "public": True,
        "indoor": True,
    },
}

define all_Locations["loc_SchoolSite_Cafeteria"] = {
    "name": _("Cafeteria"),
    "tag": "Cafeteria",
    "module": "SchoolSite",
    "traits": {
        "public": True,
    },
}

# This one uses .copy() and should trigger a warning, not an entry.
define all_Locations["loc_SchoolSite_LibraryBackroom"] = all_Locations["loc_SchoolSite_Library"].copy()
