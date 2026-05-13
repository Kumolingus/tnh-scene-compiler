"""Colored console output for the compiler CLI.

Uses ANSI escape codes directly — no external dependency. Windows 10+
supports them natively; older terminals get plain text via TTY detection.
"""

from __future__ import annotations

import os
import sys


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
    print(_fmt(text, _BOLD), file=sys.stderr)


def success(text: str) -> None:
    """Print a green success line."""
    print(_fmt(f"  OK  {text}", _GREEN), file=sys.stderr)


def error(text: str) -> None:
    """Print a red error line."""
    print(_fmt(f"  ERR {text}", _RED), file=sys.stderr)


def warning(text: str) -> None:
    """Print a yellow warning line."""
    print(_fmt(f" WARN {text}", _YELLOW), file=sys.stderr)


def info(text: str) -> None:
    """Print a dim info line."""
    print(_fmt(f"      {text}", _DIM), file=sys.stderr)


def compile_error_detail(formatted: str) -> None:
    """Print a pre-formatted ``path:line:col: message`` error."""
    print(_fmt(formatted, _RED), file=sys.stderr)


def summary(compiled: int, total: int, had_errors: bool) -> None:
    """Print the final compilation summary."""
    msg = f"Compiled {compiled}/{total} scene{'s' if total != 1 else ''}."
    if had_errors:
        error(msg)
    elif compiled == total:
        print(_fmt(f"  OK  {msg}", _GREEN), file=sys.stderr)
    else:
        warning(msg)
