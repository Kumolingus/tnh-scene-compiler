define ALL_LOCATIONS["SchoolSite.Library"] = {
    "name": _("School Library"),
    "tag": "Library",
    "module": "SchoolSite",
    "traits": {
        "public": True,
        "indoor": True,
    },
}

define ALL_LOCATIONS["Cafeteria"] = {
    "name": _("Cafeteria"),
    "tag": "Cafeteria",
    "module": "SchoolSite",
    "traits": {
        "public": True,
    },
}

# This one uses .copy() and should trigger a warning, not an entry.
define ALL_LOCATIONS["SchoolSite.LibraryBackroom"] = ALL_LOCATIONS["SchoolSite.Library"].copy()
