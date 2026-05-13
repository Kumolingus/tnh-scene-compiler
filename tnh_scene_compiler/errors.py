"""Writer-facing error type with a ``path:line:col: message`` formatter.

Every compile-time problem raised by the lexer, parser, validator, or codegen
is an instance of :class:`CompileError`. The CLI catches them and renders
one line per error to stderr — never a Python traceback — per §11.16.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompileError(Exception):
    """A single compile-time failure surfaced to the writer.

    Attributes:
        path: Repo-relative or absolute path to the offending ``.scene`` file.
            The CLI may substitute a shortened path for display, but the
            internal value stays authoritative.
        line: 1-based line number of the offending construct.
        col: 1-based column number within that line.
        message: Plain-English description of the problem, action-oriented.
            Must not leak Python jargon or tracebacks to the writer.
        hint: Optional second line offering a suggested fix
            ("Did you mean 'worried1'?").
    """

    path: str
    line: int
    col: int
    message: str
    hint: str | None = None

    def format_for_user(self) -> str:
        """Return the canonical ``path:line:col: message[\\n  hint]`` rendering."""
        head = f"{self.path}:{self.line}:{self.col}: {self.message}"
        if self.hint:
            return f"{head}\n  {self.hint}"
        return head

    def __str__(self) -> str:  # pragma: no cover - thin wrapper
        return self.format_for_user()
