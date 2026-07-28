"""The Tkinter tests must not be able to withdraw themselves from a run.

Two failure modes, both of which had actually happened:

1. A module defines its own ``tk_root``. That is a second ``tk.Tk()`` in one
   process, which intermittently breaks Tcl for whatever runs next.
2. The shared fixture answers a broken Tcl with ``pytest.skip``. A full run
   then reported ``797 passed, 73 skipped`` — green — with ~50 dialog tests,
   the condition-builder round-trip sweep among them, never executed.

Both rules are documented; documentation did not keep either from happening,
so they are asserted here.
"""

from __future__ import annotations

import ast
import tkinter as tk
from pathlib import Path

import pytest

from tests import conftest

_TESTS_DIR = Path(__file__).parent


def _module_level_function_names(path: Path) -> set[str]:
    """Names of the functions defined at module level in *path*."""
    tree = ast.parse(path.read_text(encoding = "utf-8"), filename = str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_no_module_defines_its_own_tk_root() -> None:
    """``tk_root`` lives in conftest.py and nowhere else."""
    offenders = sorted(
        path.name
        for path in _TESTS_DIR.glob("test_*.py")
        if "tk_root" in _module_level_function_names(path)
    )
    assert not offenders, (
        f"{offenders} define their own tk_root. Use the session-scoped "
        "fixture from conftest.py: a second tk.Tk() in one process breaks "
        "Tcl for whichever module runs next."
    )


def test_shared_fixture_is_session_scoped() -> None:
    # pytest 8 exposed the marker as ``_pytestfixturefunction``; pytest 9
    # wraps the fixture in a FixtureFunctionDefinition carrying
    # ``_fixture_function_marker``. Read whichever is present so a pytest
    # bump surfaces as "attribute gone", not as a silently vacuous test.
    marker = getattr(conftest.tk_root, "_fixture_function_marker", None)
    if marker is None:
        marker = conftest.tk_root._pytestfixturefunction
    assert marker.scope == "session"


def test_tk_failure_raises_where_tk_is_expected(monkeypatch) -> None:
    """A broken Tcl on a machine with a display fails; it does not skip."""
    monkeypatch.setattr(conftest, "tk_is_expected_to_work", lambda: True)
    monkeypatch.delenv(conftest.SKIP_TK_ENV, raising = False)
    monkeypatch.setattr(
        tk, "Tk", lambda: (_ for _ in ()).throw(tk.TclError("boom")),
    )

    with pytest.raises(RuntimeError, match = "expected to work"):
        next(conftest.tk_root.__wrapped__())


def test_tk_failure_skips_when_genuinely_headless(monkeypatch) -> None:
    """No display is a real reason to skip — that path stays."""
    monkeypatch.setattr(conftest, "tk_is_expected_to_work", lambda: False)
    monkeypatch.delenv(conftest.SKIP_TK_ENV, raising = False)
    monkeypatch.setattr(
        tk, "Tk", lambda: (_ for _ in ()).throw(tk.TclError("no display")),
    )

    with pytest.raises(pytest.skip.Exception):
        next(conftest.tk_root.__wrapped__())


def test_opt_out_env_var_skips(monkeypatch) -> None:
    monkeypatch.setenv(conftest.SKIP_TK_ENV, "1")

    with pytest.raises(pytest.skip.Exception):
        next(conftest.tk_root.__wrapped__())


@pytest.mark.parametrize(
    ("os_name", "platform", "env", "expected"),
    [
        ("nt", "win32", {}, True),
        ("posix", "darwin", {}, True),
        ("posix", "linux", {}, False),
        ("posix", "linux", {"DISPLAY": ":0"}, True),
        ("posix", "linux", {"WAYLAND_DISPLAY": "wayland-0"}, True),
    ],
)
def test_tk_is_expected_to_work(
    monkeypatch, os_name: str, platform: str, env: dict[str, str],
    expected: bool,
) -> None:
    import os as os_module
    import sys as sys_module

    monkeypatch.setattr(os_module, "name", os_name)
    monkeypatch.setattr(sys_module, "platform", platform)
    for key in ("DISPLAY", "WAYLAND_DISPLAY"):
        monkeypatch.delenv(key, raising = False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    assert conftest.tk_is_expected_to_work() is expected
