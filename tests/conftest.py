"""Shared pytest fixtures for tnh-scene-compiler tests.

Merges fixtures from compile_scenes, refresh_allowlists, and
generate_cheatsheet test suites.
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path

import pytest

from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.codegen import CodegenContext
from tnh_refresh_allowlists.models import ScanContext


FIXTURES = Path(__file__).parent / "fixtures"


# --- Tkinter fixtures ---------------------------------------------------------


# Opt out of the Tkinter-level tests on a machine that cannot run them and
# is not auto-detected below. Set it to any non-empty value.
SKIP_TK_ENV = "TNH_TESTS_SKIP_TK"


def tk_is_expected_to_work() -> bool:
    """True where a missing Tk means "broken", not "absent".

    Windows and macOS always have a window server, so a ``TclError`` there
    is a real fault. On POSIX, no ``DISPLAY`` and no ``WAYLAND_DISPLAY``
    means genuinely headless, and skipping is the honest outcome.
    """
    if os.name == "nt" or sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


@pytest.fixture(scope="session")
def tk_root():
    """One withdrawn Tk root for the whole session.

    Session-scoped, and shared by every Tkinter-level module: a *second*
    ``tk.Tk()`` in the same process intermittently fails to re-init Tcl
    ("Can't find a usable init.tcl", ``invalid command name
    "tcl_findLibrary"``), which took whichever module ran later down with
    it. Each test still builds its own dialog (a ``Toplevel``) on this root.
    Two modules did shadow this fixture with a module-scoped copy; the ban
    is enforced by ``test_tk_fixture_discipline.py``.

    **A failure here fails the run.** Skipping is reserved for a machine
    that genuinely has no display (see :func:`tk_is_expected_to_work`) or
    that opted out via ``TNH_TESTS_SKIP_TK``. It used to skip on any
    ``TclError``, which meant a broken Tcl silently withdrew ~50 dialog
    tests — including the condition-builder round-trip sweep — from a run
    that still reported success. A regression test that opts itself out
    proves nothing, and one that does it quietly is worse than absent.
    """
    if os.environ.get(SKIP_TK_ENV):
        pytest.skip(f"Tkinter tests disabled via {SKIP_TK_ENV}")
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - environment-dependent
        if not tk_is_expected_to_work():
            pytest.skip(f"no Tk display available: {exc}")
        raise RuntimeError(
            f"Tk failed to start where it is expected to work: {exc}. "
            "The Tkinter-level tests cannot run, and passing them over "
            "silently would hide a GUI regression. Set "
            f"{SKIP_TK_ENV}=1 to opt out deliberately.",
        ) from exc
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


def require_base_allowlists() -> Path:
    """The bundled ``allowlists_base/``, or fail the test.

    A handful of tests read the *shipped* data instead of a hand-built
    ``Allowlists``, which makes them the ones checking what a user actually
    receives — and almost nothing else in the suite would notice the
    directory going missing, since the rest builds its own fixtures.

    They used to skip here. A skip says "this environment cannot run the
    test"; a directory that is versioned in the repo going missing says the
    checkout is broken, which is a result worth reporting rather than
    passing over in a green run. Same reasoning as :func:`tk_root`.
    """
    from tnh_scene_compiler.allowlist_browser import default_base_dir

    base = default_base_dir()
    if base is None:
        pytest.fail(
            "allowlists_base/ is missing from the checkout. It ships with the "
            "repo and is what the tests covering the shipped data read — "
            "restore it rather than running without them.",
        )
    return base


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
        char_outfits = {"JeanGrey": {"casual", "Pajamas"}, "Rogue": set()},
        char_arms = {"JeanGrey": {"crossed", "covering_face"}, "Rogue": set()},
        char_left_arm = {"JeanGrey": {"bra", "extended"}, "Rogue": set()},
        char_right_arm = {"JeanGrey": {"bra", "hip"}, "Rogue": set()},
        looks = {"at_player", "away", "down"},
        stages = {"stage_left", "stage_center", "stage_right"},
        sfx = {"phone_buzz", "click", "door_open"},
        run_operations = {"give_trait", "mymod_set_stage"},
        fx = {"phone_buzz", "knock_on_door", "bamf"},
        condition_functions = {"check_approval", "is_pregnant", "ready_for_parenthood"},
        traits = {"shy", "bold", "romantic"},
        personalities = {"dominant", "submissive", "loner"},
        history_events = {"kissed_player", "fought_villain"},
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
