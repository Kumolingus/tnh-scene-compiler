"""Shared pytest fixtures for tnh-scene-compiler tests.

Merges fixtures from compile_scenes, refresh_allowlists, and
generate_cheatsheet test suites.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.codegen import CodegenContext
from tnh_refresh_allowlists.models import ScanContext


FIXTURES = Path(__file__).parent / "fixtures"


# --- compile_scenes fixtures --------------------------------------------------


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to the compile_scenes fixture root."""
    return FIXTURES


@pytest.fixture
def allowlists() -> Allowlists:
    """A minimal Allowlists object with the characters/locations/interpolation
    a scene may reference in the fixtures.

    Per-character mood/face/arms/look/outfit sets are small but distinct per
    slot so the validator's cross-lookup has a non-trivial search
    space (a value belongs to exactly one slot unless the test wants the
    opposite).
    """
    return Allowlists(
        characters = ["JeanGrey", "Rogue", "LauraKinney", "Narrator", "Player"],
        locations = {
            "JEANGREY'S ROOM": "loc_XavierSchool_JeanGreyRoom",
            "PLAYER'S ROOM": "loc_XavierSchool_PlayerRoom",
        },
        interpolation = {"player.name", "player.petname", "JeanGrey.petname", "day"},
        characters_upper = {"JEANGREY", "ROGUE", "LAURAKINNEY", "NARRATOR", "PLAYER"},
        shared_moods = {"happy", "sad", "neutral"},
        char_moods = {"JeanGrey": {"focused", "telepathic"}, "Rogue": set()},
        char_faces = {
            "JeanGrey": {"smirk", "worried1", "sympathetic"},
            "Rogue": {"glare"},
        },
        char_poses = {"JeanGrey": {"standing", "sitting"}, "Rogue": set()},
        char_outfits = {"JeanGrey": {"casual", "Pajamas"}, "Rogue": set()},
        char_arms = {"JeanGrey": {"crossed", "covering_face"}, "Rogue": set()},
        char_left_arm = {"JeanGrey": {"bra", "extended"}, "Rogue": set()},
        char_right_arm = {"JeanGrey": {"bra", "hip"}, "Rogue": set()},
        looks = {"at_player", "away", "down"},
        stages = {"stage_left", "stage_center", "stage_right"},
        sfx = {"phone_buzz", "click", "door_open"},
        mod_operations = {"give_trait", "mymod_set_stage"},
        fx = {"phone_buzz", "knock_on_door", "bamf"},
        condition_functions = {"check_approval", "is_pregnant", "ready_for_parenthood"},
    )


@pytest.fixture
def codegen_ctx() -> CodegenContext:
    """A CodegenContext for tests using a non-production prefix."""
    return CodegenContext(project_prefix = "testmod")


# --- refresh_allowlists fixtures ---------------------------------------------


@pytest.fixture
def refresh_fixtures_dir() -> Path:
    """Path to the refresh_allowlists fixture root."""
    return FIXTURES / "refresh_allowlists"


@pytest.fixture
def mini_context() -> ScanContext:
    """A :class:`ScanContext` pointing at the miniature TNH + mod fixtures."""
    base = FIXTURES / "refresh_allowlists"
    return ScanContext(
        base_game_root = base / "mini_tnh",
        project_root = base / "mini_mod",
        repo_root = base,
        include_tnh = True,
    )


@pytest.fixture
def mini_mod_only_context() -> ScanContext:
    """A :class:`ScanContext` that excludes TNH (mod-only scan)."""
    base = FIXTURES / "refresh_allowlists"
    return ScanContext(
        base_game_root = base / "mini_tnh",
        project_root = base / "mini_mod",
        repo_root = base,
        include_tnh = False,
    )


# --- generate_cheatsheet fixtures --------------------------------------------


@pytest.fixture
def allowlists_dir() -> Path:
    """Path to the miniature ``_allowlists/`` fixture directory."""
    return FIXTURES / "cheatsheet" / "_allowlists"


@pytest.fixture
def expected_cheatsheet_path() -> Path:
    """Path to the pinned expected markdown output for the snapshot test."""
    return FIXTURES / "cheatsheet" / "expected_cheatsheet.md"
