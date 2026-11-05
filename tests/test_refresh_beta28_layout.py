"""The extractors read TNH 0.9c.beta.28's layout.

beta.28 moved every character's data from default-store names
(``define Rogue_faces["smile"]``) into the character's named store
(``define CHARACTERS.Rogue.faces["smile"]``), and the shared moods from
``base_moods`` to ``BASE.moods``. A refresh against beta.28 found no face,
arm, mood, feature or garment at all, so these tests lay the files out the
way beta.28 does (``characters/Rogue/definitions/*.rpy``,
``characters/Rogue/clothing/items/*.rpy``, ``core/characters/moods.rpy``).

The flat lists drifted too: items registered in bulk, trait and history
calls in single quotes or in ``.py`` modules, and ``History.update`` as the
recording call.
"""

from __future__ import annotations

from pathlib import Path

from tnh_refresh_allowlists.extractors import (
    arms,
    clothing_items,
    faces,
    features,
    history_events,
    inventory_items,
    moods,
    outfits,
    personalities,
    traits,
)
from tnh_refresh_allowlists.models import ScanContext


def _context(tmp_path: Path, files: dict[str, str]) -> ScanContext:
    """A TNH-including scan of a game holding *files* (path under ``game/`` -> text)."""
    game = tmp_path / "TheNullHypothesis" / "game"
    for relative, text in files.items():
        path = game / relative
        path.parent.mkdir(parents = True, exist_ok = True)
        path.write_text(text, encoding = "utf-8")
    (tmp_path / "mod" / "game").mkdir(parents = True)
    return ScanContext(
        base_game_root = tmp_path / "TheNullHypothesis",
        project_root = tmp_path / "mod",
        repo_root = tmp_path,
        include_tnh = True,
    )


def _names(result, character: str, subgroup: str | None = None) -> set[str]:
    return {entry.name for entry in result.per_character.get(character, []) if entry.subgroup == subgroup}


def test_faces_are_read_from_the_characters_store(tmp_path):
    context = _context(tmp_path, {"characters/Rogue/definitions/expressions.rpy": (
        'define CHARACTERS.Rogue.faces["smile"] = {"mouth": "smile"}\n'
        'define CHARACTERS.Rogue.faces["worried1"] = {"brows": "worried"}\n'
    )})

    assert _names(faces.extract(context), "Rogue") == {"smile", "worried1"}


def test_arm_poses_and_presets_are_read_from_the_characters_store(tmp_path):
    context = _context(tmp_path, {
        "characters/Rogue/images/standing/standing.rpy": (
            'define CHARACTERS.Rogue.poses["standing"] = {\n'
            '    "left_arm": {"neutral", "hip"},\n'
            '    "right_arm": {"neutral", "wave"},\n'
            '}\n'
        ),
        "characters/Rogue/definitions/expressions.rpy": 'define CHARACTERS.Rogue.arms["crossed"] = ("crossed", "crossed")\n',
    })

    result = arms.extract(context)

    assert _names(result, "Rogue", "left_arm") == {"neutral", "hip"}
    assert _names(result, "Rogue", "right_arm") == {"neutral", "wave"}
    assert "crossed" in _names(result, "Rogue", "arms")


def test_shared_and_character_moods_are_read_from_their_stores(tmp_path):
    context = _context(tmp_path, {
        "core/characters/moods.rpy": 'define BASE.moods["normal"] = {\n    "faces": {},\n}\n',
        "characters/Rogue/definitions/moods.rpy": 'define CHARACTERS.Rogue.moods["sulky"] = {\n    "faces": {},\n}\n',
    })

    result = moods.extract(context)

    assert "normal" in {entry.name for entry in result.entries}
    assert "sulky" in _names(result, "Rogue")


def test_features_are_read_from_the_characters_store(tmp_path):
    context = _context(tmp_path, {"characters/Rogue/definitions/features.rpy": (
        'define CHARACTERS.Rogue.supported_features = {\n    "love",\n    "trust",\n}\n'
    )})

    assert _names(features.extract(context), "Rogue") == {"love", "trust"}


def test_garments_are_read_from_the_characters_clothes(tmp_path):
    # beta.28 renamed `<Tag>_all_Clothes` to `CHARACTERS.<Tag>.clothes`; the
    # inventory key keeps the owner prefix (ClothingClass.unique_tag).
    context = _context(tmp_path, {"characters/Rogue/clothing/items/black_NIN_shirt.rpy": (
        'define CHARACTERS.Rogue.clothes["black_NIN_shirt"] = {\n    "name": _("black NIN shirt"),\n}\n'
    )})

    assert _names(clothing_items.extract(context), "Rogue") == {"Rogue_black_NIN_shirt"}


def _flat_names(result) -> set[str]:
    return {entry.name for entry in result.entries}


def test_items_registered_in_bulk_are_read(tmp_path):
    # beta.28 registers its piercings with one comprehension over a tuple of
    # rows (inventory/piercings.rpy) instead of one `define ALL_ITEMS["x"]` each.
    context = _context(tmp_path, {
        "inventory/piercings.rpy": (
            'init:\n'
            '    define ALL_ITEMS |= {\n'
            '        tag: {\n'
            '            "name": name,\n'
            '            "price": price,\n'
            '        }\n'
            '\n'
            '        for tag, name, price in (\n'
            '            ("belly_piercings_barbell", _("barbell belly piercing"), 3),\n'
            '            ("labia_piercings_ring", _("ring labia piercing"), RelativeThreshold("piercing", 3.0)),\n'
            '        )\n'
            '    }\n'
        ),
        "inventory/extras.rpy": 'define ALL_ITEMS |= {"spare_key": {"name": _("spare key")}}\n',
        "inventory/flowers.rpy": 'define ALL_ITEMS["flowers"] = {\n    "name": _("flowers"),\n}\n',
    })

    result = inventory_items.extract(context)

    assert _flat_names(result) == {"belly_piercings_barbell", "labia_piercings_ring", "spare_key", "flowers"}
    belly = next(entry for entry in result.entries if entry.name == "belly_piercings_barbell")
    assert (belly.source_file, belly.source_line) == ("TheNullHypothesis/game/inventory/piercings.rpy", 9)


def test_traits_are_read_in_either_quote_and_from_python_modules(tmp_path):
    # beta.28 writes most trait checks in single quotes and moved much of its
    # logic into `.py` modules, where the `.rpy`-only, double-quote scan saw none.
    # A trait given a value, or only read for one, holds data rather than a
    # flag: a writer's [[give_trait]] would overwrite it with True.
    context = _context(tmp_path, {
        "characters/Rogue/events/date.rpy": (
            'define e = EventClass(conditions = ["Rogue.check_trait(\'romantic\')"])\n'
            '$ Rogue.give_trait("shy")\n'
            '$ Rogue.give_trait("birth_records", records)\n'
            '$ Rogue.give_trait(f"{name}_dynamic")\n'
        ),
        "core/sex/climax.py": 'def end(C):\n    C.remove_trait("orgasming")\n    return C.get_trait(\'ejaculating\')\n',
        "core/base/notes.py": '"""\nC.give_trait("inside_docstring")\n"""\n# C.give_trait("commented_out")\n',
    })

    assert _flat_names(traits.extract(context)) == {"romantic", "shy", "orgasming"}


def test_python_outside_the_game_folder_is_not_scanned(tmp_path):
    # The build ships the Python standard library under lib/ and the engine
    # under renpy/: thousands of files no writer's trait or event comes from.
    context = _context(tmp_path, {"characters/Rogue/date.rpy": '$ Rogue.give_trait("shy")\n'})
    library = tmp_path / "TheNullHypothesis" / "lib" / "python3.12" / "stray.py"
    library.parent.mkdir(parents = True)
    library.write_text('C.give_trait("from_the_library")\nHistory.update("from_the_library")\n', encoding = "utf-8")

    assert _flat_names(traits.extract(context)) == {"shy"}
    assert _flat_names(history_events.extract(context)) == set()


def test_outfits_built_on_the_store_character_are_read(tmp_path):
    # Outfits are built inside the character's named store, where the
    # character itself is reached as `store.<Tag>` (KittyPryde on beta.28).
    context = _context(tmp_path, {"characters/KittyPryde/clothing/outfits.rpy": (
        'init python in CHARACTERS.KittyPryde:\n'
        '    import store\n'
        '    def default_Outfits():\n'
        '        Outfits = []\n'
        '        Outfits.append(OutfitClass(store.KittyPryde, "Nude"))\n'
        '        Outfits.append(OutfitClass(\n'
        '            KittyPryde,\n'
        '            "Casual 1",\n'
        '        ))\n'
        '        return Outfits\n'
    )})

    assert _names(outfits.extract(context), "KittyPryde") == {"Nude", "Casual 1"}


def test_personalities_set_and_read_through_the_dict_are_read(tmp_path):
    # The game sets a score by assigning into `personality` (quirk events),
    # shifts it with update_personality, and reads the player's leanings by
    # subscript only (events/ch1/s4_finale.rpy).
    context = _context(tmp_path, {
        "characters/Rogue/quirk.rpy": (
            '$ Rogue.personality["submissive"] = 1\n'
            'define e = EventClass(conditions = "Rogue.check_personality(\'neurotic\', 2)")\n'
            '$ update_personality(Rogue, "protective", -1)\n'
        ),
        "events/finale.rpy": 'if Player.personality["determined"] >= Player.personality[trait]:\n    pass\n',
        "core/characters/talk.py": 'def pick(C):\n    return C.check_personality(\'loner\')\n',
    })

    assert _flat_names(personalities.extract(context)) == {"submissive", "neurotic", "protective", "determined", "loner"}


def test_history_events_recorded_by_update_are_read(tmp_path):
    # beta.28's HistoryClass records with `update` (core/base/history.py) and
    # reads with `check('x', tracker = ...)`; it has no `add` or `record`.
    context = _context(tmp_path, {
        "characters/JeanGrey/debrief.rpy": (
            '$ JeanGrey.History.update("discussed_breeding")\n'
            'define e = EventClass(conditions = "JeanGrey.History.check(\'sleepover\', tracker = \'yesterday\')")\n'
            '$ JeanGrey.History.update(f"bought_{item}")\n'
        ),
        "core/activities/cinema.py": 'def watch(C):\n    C.History.update(\'seen_ron_bic1\')\n',
    })

    assert _flat_names(history_events.extract(context)) == {"discussed_breeding", "sleepover", "seen_ron_bic1"}
