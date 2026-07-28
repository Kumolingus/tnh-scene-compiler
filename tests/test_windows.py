"""The singleton-window rule behind every Glossary / Allowlists button.

Six call sites share it, so the behaviour is tested once here rather than six
times: a second click brings the open window back, and a window the user has
closed can be opened again. Getting the second half wrong is the plausible
regression — a plain ``is not None`` check leaves a dead reference behind and
silently refuses to reopen.
"""

from __future__ import annotations

import tkinter as tk

import pytest

from tnh_scene_compiler.windows import open_singleton_window

# ``tk_root`` is the session-scoped fixture in conftest.py.


def _factory(root, calls: list[int]):
    """A factory that records how many times it actually built a window."""
    def build() -> tk.Toplevel:
        calls.append(1)
        win = tk.Toplevel(root)
        win.withdraw()
        return win
    return build


def test_first_call_builds_and_remembers(tk_root):
    owner = tk.Frame(tk_root)
    calls: list[int] = []
    win = open_singleton_window(owner, "_glossary", _factory(tk_root, calls))
    try:
        assert calls == [1]
        assert owner._glossary is win
    finally:
        win.destroy()
        owner.destroy()


def test_second_call_refocuses_instead_of_stacking(tk_root):
    owner = tk.Frame(tk_root)
    calls: list[int] = []
    factory = _factory(tk_root, calls)
    first = open_singleton_window(owner, "_glossary", factory)
    try:
        again = open_singleton_window(owner, "_glossary", factory)
        assert again is first
        assert calls == [1], "a duplicate window was built"
    finally:
        first.destroy()
        owner.destroy()


def test_a_closed_window_can_be_reopened(tk_root):
    """The dead reference must not lock the button out for the rest of the run."""
    owner = tk.Frame(tk_root)
    calls: list[int] = []
    factory = _factory(tk_root, calls)
    first = open_singleton_window(owner, "_glossary", factory)
    first.destroy()

    second = open_singleton_window(owner, "_glossary", factory)
    try:
        assert second is not first
        assert calls == [1, 1]
    finally:
        second.destroy()
        owner.destroy()


def test_an_attribute_taken_by_something_else_is_refused(tk_root):
    """``_w`` is Tkinter's own widget path name — a string, on every widget.

    Found the hard way: this helper's first test picked ``_w`` as its
    attribute and got an ``AttributeError`` from deep inside. Worse than the
    crash was what came next — the helper would have *overwritten* the
    widget's path with a Toplevel, corrupting the owner well after the click.
    """
    owner = tk.Frame(tk_root)
    calls: list[int] = []
    try:
        with pytest.raises(ValueError, match="not a window"):
            open_singleton_window(owner, "_w", _factory(tk_root, calls))
        assert calls == []
        assert isinstance(owner._w, str), "the owner's own attribute survived"
    finally:
        owner.destroy()


def test_two_attributes_on_one_owner_are_independent(tk_root):
    """A screen opens both the glossary and the allowlist browser."""
    owner = tk.Frame(tk_root)
    calls: list[int] = []
    factory = _factory(tk_root, calls)
    a = open_singleton_window(owner, "_glossary", factory)
    b = open_singleton_window(owner, "_allowlist_browser", factory)
    try:
        assert a is not b
        assert calls == [1, 1]
    finally:
        a.destroy()
        b.destroy()
        owner.destroy()
