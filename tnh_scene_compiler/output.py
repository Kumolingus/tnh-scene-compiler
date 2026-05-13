"""Colored console output for the compiler CLI.

Uses ANSI escape codes directly — no external dependency. Windows 10+
supports them natively; older terminals get plain text via TTY detection.

A pluggable callback allows the GUI (or any other frontend) to capture
messages instead of printing to stderr.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

# ---------------------------------------------------------------------------
# Pluggable output callback
# ---------------------------------------------------------------------------

_callback: Callable[[str, str], None] | None = None


def set_callback(cb: Callable[[str, str], None] | None) -> None:
    """Install (or remove) a callback that receives ``(level, text)`` pairs.

    When a callback is set, none of the output functions write to stderr.
    """
    global _callback
    _callback = cb


def _supports_color(stream=None) -> bool:
    """Return ``True`` if the output stream likely supports ANSI colors."""
    if stream is None:
        stream = sys.stderr
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if not hasattr(stream, "isatty"):
        return False
    return stream.isatty()


_COLOR = _supports_color()

_RESET = "\033[0m"
_BOLD = "\033[1m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_DIM = "\033[2m"


def _fmt(text: str, code: str) -> str:
    if not _COLOR:
        return text
    return f"{code}{text}{_RESET}"


def header(text: str) -> None:
    """Print a bold section header."""
    if _callback is not None:
        _callback("header", text)
        return
    print(_fmt(text, _BOLD), file=sys.stderr)


def success(text: str) -> None:
    """Print a green success line."""
    if _callback is not None:
        _callback("success", text)
        return
    print(_fmt(f"  OK  {text}", _GREEN), file=sys.stderr)


def error(text: str) -> None:
    """Print a red error line."""
    if _callback is not None:
        _callback("error", text)
        return
    print(_fmt(f"  ERR {text}", _RED), file=sys.stderr)


def warning(text: str) -> None:
    """Print a yellow warning line."""
    if _callback is not None:
        _callback("warning", text)
        return
    print(_fmt(f" WARN {text}", _YELLOW), file=sys.stderr)


def info(text: str) -> None:
    """Print a dim info line."""
    if _callback is not None:
        _callback("info", text)
        return
    print(_fmt(f"      {text}", _DIM), file=sys.stderr)


def compile_error_detail(formatted: str) -> None:
    """Print a pre-formatted ``path:line:col: message`` error."""
    if _callback is not None:
        _callback("compile_error", formatted)
        return
    print(_fmt(formatted, _RED), file=sys.stderr)


def summary(compiled: int, total: int, had_errors: bool) -> None:
    """Print the final compilation summary."""
    msg = f"Compiled {compiled}/{total} scene{'s' if total != 1 else ''}."
    if had_errors:
        error(msg)
    elif compiled == total:
        success(msg)
    else:
        warning(msg)
