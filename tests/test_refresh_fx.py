"""Tests for the FX extractor: which base-game effects it lists, and how each is called."""

from __future__ import annotations

from pathlib import Path

from tnh_refresh_allowlists.extractors import fx
from tnh_refresh_allowlists.models import ScanContext


# effects.rpy as TNH 0.9c ships it, cut down: a label-only effect, an effect
# that is both a label and a function, an effect that lost its label and kept
# only its cinematic_ twin, and two helper functions that are not effects.
_EFFECTS_RPY = """init python:

    def play_random_effect(effects: list[str], x: float = 0.5) -> None:
        pass

    def smack(x: float = 0.5, y: float = 0.5) -> None:
        pass

    def pow_effect(x: float = 0.5, y: float = 0.5) -> None:
        pass

    def bamf(x: float = 0.5, y: float = 0.5, pause: bool = True) -> None:
        pass

label boom(x = 0.5, y = 0.5):
    return

label smack(x = 0.5, y = 0.5):
    return

label cinematic_bamf(x = 0.5, y = 0.5, pause = True):
    return

label cinematic_smack(x = 0.5, y = 0.5):
    return
"""

# animations.rpy as TNH 0.9c ships it: the animations are functions, next to
# rig helpers that must not become effects.
_KURT_ANIMATIONS_RPY = """init python:

    def KurtWagner_teleport_animators(source, rogue2d) -> list:
        return []

    def KurtWagner_animations_teleports_in(dialogue: str | None = None, x: float | None = None) -> None:
        pass
"""

_PHONE_EFFECTS_RPY = """init python:

    def phone_buzz(x: float = 0.5, y: float = 0.5, times: int = 1) -> None:
        pass
"""


def _write(path: Path, text: str) -> None:
    """Write ``text`` to ``path``, creating its parent folders."""
    path.parent.mkdir(parents = True, exist_ok = True)
    path.write_text(text, encoding = "utf-8")


def _context(tmp_path: Path) -> ScanContext:
    """Return a TNH-including scan context rooted in ``tmp_path``."""
    return ScanContext(
        base_game_root = tmp_path / "TheNullHypothesis",
        project_root = tmp_path / "mod",
        repo_root = tmp_path,
        include_tnh = True,
    )


def _entries_by_name(tmp_path: Path) -> dict[str, dict[str, str]]:
    """Run the extractor and return ``{name: metadata}`` for every entry."""
    result = fx.extract(_context(tmp_path))
    names = [entry.name for entry in result.entries]
    assert len(names) == len(set(names)), names
    return {entry.name: dict(entry.metadata) for entry in result.entries}


def _write_09c_tree(tmp_path: Path) -> None:
    """Lay out the 0.9c-shaped FX sources under ``tmp_path``."""
    game = tmp_path / "TheNullHypothesis" / "game"
    _write(game / "displayables" / "effects.rpy", _EFFECTS_RPY)
    # character.rpy is what makes a folder a character to the scanner.
    _write(game / "characters" / "KurtWagner" / "character.rpy", "")
    _write(game / "characters" / "KurtWagner" / "animations.rpy", _KURT_ANIMATIONS_RPY)
    _write(game / "core" / "phone" / "effects.rpy", _PHONE_EFFECTS_RPY)


def test_labels_are_called(tmp_path):
    _write_09c_tree(tmp_path)

    entries = _entries_by_name(tmp_path)

    assert entries["boom"]["call_mode"] == "label"


def test_a_name_that_is_both_label_and_function_stays_a_label(tmp_path):
    _write_09c_tree(tmp_path)

    entries = _entries_by_name(tmp_path)

    assert entries["smack"]["call_mode"] == "label"
    assert entries["smack"]["signature"] == "smack(x = 0.5, y = 0.5) -> None"


def test_an_effect_that_lost_its_label_is_listed_as_a_function(tmp_path):
    # bamf became a def in 0.9c; a `call bamf()` raises at runtime there.
    _write_09c_tree(tmp_path)

    entries = _entries_by_name(tmp_path)

    assert "call_mode" not in entries["bamf"]
    assert entries["bamf"]["signature"] == "bamf(x: float = 0.5, y: float = 0.5, pause: bool = True) -> None"


def test_effect_file_helpers_without_a_cinematic_twin_are_not_effects(tmp_path):
    _write_09c_tree(tmp_path)

    entries = _entries_by_name(tmp_path)

    assert "play_random_effect" not in entries
    assert "pow_effect" not in entries


def test_character_animations_written_as_functions_are_listed_as_functions(tmp_path):
    _write_09c_tree(tmp_path)

    entries = _entries_by_name(tmp_path)

    assert "call_mode" not in entries["KurtWagner_animations_teleports_in"]
    assert "KurtWagner_teleport_animators" not in entries


def test_mechanics_functions_are_found_anywhere_under_core(tmp_path):
    _write_09c_tree(tmp_path)

    entries = _entries_by_name(tmp_path)

    assert "call_mode" not in entries["phone_buzz"]


def test_mechanics_functions_still_found_in_the_09b_layout(tmp_path):
    game = tmp_path / "TheNullHypothesis" / "game"
    _write(game / "core" / "mechanics" / "phone.rpy", _PHONE_EFFECTS_RPY)

    entries = _entries_by_name(tmp_path)

    assert "phone_buzz" in entries


# TNH 0.9c.beta.28 moves the effects into named stores and the mechanics into
# Python modules the default store imports (displayables/effects.rpy,
# characters/LauraKinney/animations.rpy, definitions/core.rpy, core/phone/effects.py).
_BETA28_EFFECTS_RPY = """init python in displayables.effects:

    def play_random(effects: list[str], x: float = 0.5) -> None:
        pass

    def bamf(x: float = 0.5, y: float = 0.5, pause: bool = True) -> None:
        pass

label cinematic_bamf(x = 0.5, y = 0.5, pause = True):
    return
"""

_BETA28_LAURA_ANIMATIONS_RPY = """init python in CHARACTERS.LauraKinney.animations:

    from renpy import exports as renpy

    def unsheathe_claws(x: float = 0.675, y: float = 0.25, hand: str = "both") -> None:
        def inner() -> None:
            pass

    def sheathe_claws(x: float = 0.675, y: float = 0.25, hand: str = "both") -> None:
        pass
"""

_BETA28_KURT_ANIMATIONS_RPY = """init python in CHARACTERS.KurtWagner:

    def teleport_animators(source, rogue2d) -> list:
        return []

init python in CHARACTERS.KurtWagner.animations:

    def teleports_in(dialogue: str | None = None, x: float | None = None) -> None:
        pass
"""

_BETA28_CORE_RPY = """init -98 python:

    from core.behavior import (
        knock_on_door,
    )
    from core.phone import (
        ChatClass,
        buzz as phone_buzz,
    )
"""


def _write_beta28_tree(tmp_path: Path) -> None:
    """Lay out the 0.9c.beta.28-shaped FX sources under ``tmp_path``."""
    game = tmp_path / "TheNullHypothesis" / "game"
    _write(game / "displayables" / "effects.rpy", _BETA28_EFFECTS_RPY)
    for tag, text in (("LauraKinney", _BETA28_LAURA_ANIMATIONS_RPY), ("KurtWagner", _BETA28_KURT_ANIMATIONS_RPY)):
        _write(game / "characters" / tag / "character.rpy", "")
        _write(game / "characters" / tag / "animations.rpy", text)
    _write(game / "definitions" / "core.rpy", _BETA28_CORE_RPY)
    _write(game / "core" / "behavior" / "__init__.py", "from .knocking import knock_on_door\n")
    _write(game / "core" / "behavior" / "knocking.py", (
        "def knock_on_door(x: float = 0.5, y: float = 0.4, times: int = 1) -> None:\n"
        "    pass\n"
    ))
    _write(game / "core" / "phone" / "__init__.py", "from .effects import buzz\nfrom .chats import ChatClass\n")
    _write(game / "core" / "phone" / "effects.py", (
        "def buzz(x: float = 0.5, y: float = 0.5, times: int = 1) -> None:\n"
        "    pass\n"
    ))


def test_a_character_animation_in_its_named_store_keeps_the_flat_name_and_calls_its_home(tmp_path):
    # The writer names it the way the game's own compatibility alias does;
    # the scene calls the function where the game keeps it.
    _write_beta28_tree(tmp_path)

    entries = _entries_by_name(tmp_path)

    laura = entries["LauraKinney_animations_sheathe_claws"]
    assert laura["call"] == "CHARACTERS.LauraKinney.animations.sheathe_claws"
    assert laura["signature"] == (
        'LauraKinney_animations_sheathe_claws(x: float = 0.675, y: float = 0.25, hand: str = "both") -> None'
    )
    assert entries["KurtWagner_animations_teleports_in"]["call"] == "CHARACTERS.KurtWagner.animations.teleports_in"
    # A nested helper, an import and the character's own store are no effects.
    assert "LauraKinney_animations_inner" not in entries
    assert not any("teleport_animators" in name for name in entries)


def test_an_effect_in_the_effects_store_calls_its_home(tmp_path):
    _write_beta28_tree(tmp_path)

    entries = _entries_by_name(tmp_path)

    assert entries["bamf"]["call"] == "displayables.effects.bamf"
    assert "play_random" not in entries


def test_a_mechanics_effect_the_store_imports_is_found_in_its_module(tmp_path):
    _write_beta28_tree(tmp_path)

    entries = _entries_by_name(tmp_path)

    assert entries["phone_buzz"]["signature"] == "phone_buzz(x: float = 0.5, y: float = 0.5, times: int = 1) -> None"
    assert entries["knock_on_door"]["signature"] == "knock_on_door(x: float = 0.5, y: float = 0.4, times: int = 1) -> None"
    # A store name needs no other call path.
    assert "call" not in entries["phone_buzz"] and "call" not in entries["knock_on_door"]


def test_nothing_is_listed_without_the_base_game(tmp_path):
    _write_09c_tree(tmp_path)
    context = _context(tmp_path)
    context = ScanContext(
        base_game_root = context.base_game_root,
        project_root = context.project_root,
        repo_root = context.repo_root,
        include_tnh = False,
    )

    assert fx.extract(context).entries == []
