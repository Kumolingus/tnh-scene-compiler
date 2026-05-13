"""Strip comments and triple-quoted strings from ``.rpy`` source before regex scans.

The extractors feed this helper their raw file text and receive a "safe" text
where comment lines and string literals that span multiple lines have been
replaced by blanks of equal length. Line and column numbers stay consistent with
the original, so matches can still report accurate source_line values.
"""

from __future__ import annotations

import re

_TRIPLE = re.compile(r'(""".*?"""|\'\'\'.*?\'\'\')', re.DOTALL)


def strip_noise(source: str) -> str:
    """Return ``source`` with comment lines and triple-quoted blocks blanked out.

    Whitespace and line count are preserved so line numbers remain valid.
    """
    # Blank out triple-quoted strings first, preserving newlines.
    def blank_triple(match: re.Match[str]) -> str:
        body = match.group(0)
        return "".join(char if char == "\n" else " " for char in body)

    cleaned = _TRIPLE.sub(blank_triple, source)

    # Blank comment lines. Ren'Py uses ``#`` like Python.
    lines = cleaned.splitlines(keepends = True)
    out_lines: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            out_lines.append(" " * (len(line) - 1) + ("\n" if line.endswith("\n") else ""))
        else:
            out_lines.append(line)
    return "".join(out_lines)
