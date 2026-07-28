"""``Player`` is refused where the game structurally excludes it.

A compiler that accepts in silence says the condition is fine. These calls
are not merely unlikely — they are false whatever happens in the story,
because `Player` is not in the game's `all_Characters` at all
(`definitions.rpy` keeps `all_Characters_plus_Player` separate), so
`register_Friendships` never records a tie involving it and `check_approval`
opens with `if Character not in GameState.all_Companions: return 0`.

The line is **argument versus subject**. `Player.History` (316 uses in the
base game) and `Player.check_trait` (109) stay valid: the player is the
implicit other side of every relationship, so it is legitimate as the
subject of an attribute and never as a participant you name.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.parser import parse
from tnh_scene_compiler.validator import validate

BASE_ALLOWLISTS = Path(__file__).resolve().parents[1] / "allowlists_base"

_HEAD = (
    "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
    "Scene Type: cinematic\nTrigger: manual\n\n"
)


@pytest.fixture(scope="module")
def base_allow() -> Allowlists:
    return Allowlists.load(BASE_ALLOWLISTS)


def _errors(condition: str, allow: Allowlists) -> list[str]:
    scene = parse(_HEAD + f"[[if {condition}]]\nOk.\n[[/if]]\n", path="c.scene")
    return [e.message for e in validate(scene, allow)]


@pytest.mark.parametrize("condition", [
    "are_Characters_friends([Player, JeanGrey])",
    "are_Characters_friends([JeanGrey, Player], 2)",
    'are_Characters_in_Partners([Player], False)',
    'check_approval(Player, None, "dating")',
    "get_effective_friendship(Player, JeanGrey) >= 2",
    "get_Characters_opinion(JeanGrey, Player) >= 1",
    "get_base_friendship(Player, JeanGrey) >= 1",
    "get_max_friendship(Player, JeanGrey) >= 1",
    "get_best_Friend(Player, [JeanGrey, Rogue])",
    "get_worst_Enemy(JeanGrey, [Player, Rogue])",
    "Character_is_in_close_proximity(Player)",
])
def test_player_is_refused(condition: str, base_allow: Allowlists) -> None:
    messages = _errors(condition, base_allow)
    assert messages, f"{condition} should not validate"
    assert "cannot take 'Player'" in messages[0]


@pytest.mark.parametrize("condition", [
    # Subject, not participant.
    'chance_of_repeat_Event(Player.History, "asked_on_date") >= 0.5',
    'Player.History.check("asked_on_date") > 0',
    'Player.check_trait("has_family")',
    # The ordinary forms must be untouched.
    "are_Characters_friends([Rogue, JeanGrey])",
    "are_Characters_in_Partners([JeanGrey], False)",
    'check_approval(JeanGrey, None, "dating")',
    "get_effective_friendship(JeanGrey, Rogue) >= 2",
    # Not guarded: it reads Character.History, which the player has, so this
    # is a nonsensical question rather than an impossible one. Refusing it
    # would claim more than the base game supports.
    "seen_Player_recently(Player)",
])
def test_legitimate_uses_still_validate(
    condition: str, base_allow: Allowlists,
) -> None:
    assert _errors(condition, base_allow) == []


def test_the_error_says_what_to_write_instead(base_allow: Allowlists) -> None:
    """A writer told only "no" has to guess; the two families differ."""
    scene = parse(
        _HEAD + "[[if are_Characters_friends([Player, JeanGrey])]]\nOk.\n[[/if]]\n",
        path="c.scene",
    )
    relationship = validate(scene, base_allow)[0]
    assert "check_approval" in (relationship.hint or "")

    scene = parse(
        _HEAD + "[[if Character_is_in_close_proximity(Player)]]\nOk.\n[[/if]]\n",
        path="c.scene",
    )
    proximity = validate(scene, base_allow)[0]
    assert "get_present_Characters" in (proximity.hint or "")
    assert "check_approval" not in (proximity.hint or "")
