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
