"""A skip has to be justified, and the list of justified ones lives here.

Twice now a test withdrew itself from a passing run: the Tkinter suite when
Tcl broke (see test_tk_fixture_discipline.py), and a parametrised parser
case that ``return``ed early on ``-17`` while the grammar refused it — that
one reported PASSED for as long as it existed.

The general lesson is not about Tk or about ``-17``. It is that a skip reads
as "this environment cannot run the test" and gets used for "the data this
test needs is missing", which is a defect worth reporting rather than
passing over. So every ``pytest.skip`` in the suite is enumerated below with
its reason, and a new one fails this test until someone justifies it here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from _pytest.outcomes import Failed

from tests.conftest import require_base_allowlists

_TESTS_DIR = Path(__file__).parent

# file name -> why a skip there is legitimate. Keep this short; the point is
# that adding to it is a decision, not a reflex.
_SANCTIONED_SKIPS: dict[str, str] = {
    # A machine with no display genuinely cannot run them, and the opt-out
    # is deliberate. Everything else about Tk now fails instead.
    "conftest.py": "no display / explicit TNH_TESTS_SKIP_TK opt-out",
    # A catalog entry that needs a value only the writer can supply cannot
    # be round-tripped on defaults. Skipping lists it under -rs rather than
    # passing silently, which is the honest outcome for "nothing to test".
    "test_condition_builder_roundtrip.py": "entry needs a hand-typed value",
}


def _skip_call_sites(path: Path) -> list[int]:
    """Line numbers of ``pytest.skip(...)`` calls in *path*.

    Only calls: ``pytest.raises(pytest.skip.Exception)`` is an assertion
    *about* skipping, not a skip.
    """
    tree = ast.parse(path.read_text(encoding = "utf-8"), filename = str(path))
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "skip"
            and isinstance(func.value, ast.Name)
            and func.value.id == "pytest"
        ):
            lines.append(node.lineno)
    return lines


def test_every_skip_is_sanctioned() -> None:
    unsanctioned: list[str] = []
    for path in sorted(_TESTS_DIR.glob("*.py")):
        if path.name in _SANCTIONED_SKIPS:
            continue
        unsanctioned += [f"{path.name}:{line}" for line in _skip_call_sites(path)]

    assert not unsanctioned, (
        f"unsanctioned pytest.skip at {unsanctioned}. A skip means the "
        "environment cannot run the test — for missing or misshapen data, "
        "fail with a message saying what to regenerate. If it really is "
        "environmental, add the file to _SANCTIONED_SKIPS with its reason."
    )


def test_sanctioned_list_has_no_dead_entries() -> None:
    """An entry that no longer skips should leave, or the list stops meaning much."""
    dead = [
        name for name in _SANCTIONED_SKIPS
        if not _skip_call_sites(_TESTS_DIR / name)
    ]
    assert not dead, f"{dead} no longer skip; drop them from _SANCTIONED_SKIPS"


def test_no_parametrised_case_returns_early() -> None:
    """A test that returns instead of asserting still reports PASSED.

    This is how ``-17`` sat in the "allowed constructs" table for months
    while the grammar refused it: the case was listed, the test returned on
    it, and a comment pointed at a dedicated test that was never written.
    """
    offenders: list[str] = []
    for path in sorted(_TESTS_DIR.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding = "utf-8"), filename = str(path))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")):
                continue
            nested = {
                inner
                for child in ast.walk(node)
                if isinstance(child, (ast.FunctionDef, ast.Lambda)) and child is not node
                for inner in ast.walk(child)
            }
            offenders += [
                f"{path.name}:{sub.lineno} in {node.name}"
                for sub in ast.walk(node)
                if isinstance(sub, ast.Return) and sub not in nested
            ]

    assert not offenders, (
        f"early return in a test at {offenders}. Delete the case, assert the "
        "refusal, or skip it with a reason — returning reports PASSED while "
        "checking nothing."
    )


def test_missing_shipped_allowlists_fails_rather_than_skips(monkeypatch) -> None:
    """The three tests reading the shipped data must not go quiet."""
    import tnh_scene_compiler.allowlist_browser as browser

    monkeypatch.setattr(browser, "default_base_dir", lambda: None)
    with pytest.raises(Failed, match = "allowlists_base"):
        require_base_allowlists()
