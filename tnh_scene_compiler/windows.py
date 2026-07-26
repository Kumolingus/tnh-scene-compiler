"""Shared helpers for the non-modal reference windows.

The glossary and the allowlist browser are both opened from several screens
(welcome, quick, project, editor toolbar) and both are *modeless* — they stay
up beside the window that opened them. That combination needs a rule for what
a second click on the button does, and the rule is the same for both: bring
the existing window back rather than stack a duplicate on top of it.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import TypeVar

_W = TypeVar("_W", bound=tk.Toplevel)


def open_singleton_window(
    owner: tk.Misc, attribute: str, factory: Callable[[], _W],
) -> _W:
    """Open *factory*'s window once per *owner*, re-focusing it if already up.

    *attribute* names where the window is remembered on *owner*
    (e.g. ``"_glossary"``). A window the user has closed leaves a dead
    reference behind, which ``winfo_exists`` is what distinguishes from a live
    one — a plain ``is not None`` check would refuse to ever reopen it.

    Restoring takes all three steps: ``deiconify`` for a minimised window,
    ``lift`` for one buried behind the caller, ``focus_set`` so the writer can
    type in it straight away. Returns the live window.

    Raises ``ValueError`` if *attribute* is already taken by something that is
    not one of our windows. Tk widgets carry internal attributes of their own
    — ``_w`` is the widget's path name — and overwriting one would corrupt the
    owner silently, long after the click that did it.
    """
    existing = getattr(owner, attribute, None)
    if isinstance(existing, tk.Toplevel):
        if existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_set()
            return existing
    elif existing is not None:
        raise ValueError(
            f"{type(owner).__name__}.{attribute} already holds "
            f"{type(existing).__name__}, not a window — pick another name",
        )
    window = factory()
    setattr(owner, attribute, window)
    return window
