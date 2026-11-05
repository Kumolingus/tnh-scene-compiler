"""Extract the inventory item keys.

Rules:

- Scan every ``.rpy`` across TNH (when included) and the mod.
- Match ``define ALL_ITEMS["<key>"] = {...}`` — the registration pattern used
  by ``game/inventory/<key>.rpy``.
- Read ``define ALL_ITEMS |= {...}`` with :mod:`ast`: a dict literal, or the
  comprehension over a literal tuple of rows that TNH 0.9c.beta.28 registers
  its piercings with (``game/inventory/piercings.rpy``). A key the source
  computes is skipped with a warning.
- Produce a single flat ``inventory_items.yaml``.

The key is what ``Character.Inventory.get_active(tag)`` /
``get_number(tag)`` take: ``Inventory.add`` stores a plain item under its
``tag`` (``get_Item_key`` in ``core/inventory/utilities.py``), and an item's
tag is its ``ALL_ITEMS`` key.

Clothing is deliberately **not** collected. ``get_Item_key`` stores it under
its ``unique_tag`` instead, and those ids live in per-character ``Clothes``
mappings with a different shape. A writer needing one types it; the dropdown
stays editable.
"""

from __future__ import annotations

import ast
import re

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext, Warning
from ..scanner import iter_all_rpy, safe_read_text

_ITEM_RE = re.compile(r'define\s+ALL_ITEMS\s*\[\s*"(?P<name>[^"]+)"\s*\]')
_BULK_RE = re.compile(r"define\s+ALL_ITEMS\s*\|=\s*(?=\{)")

_OPENERS = {"{": "}", "[": "]", "(": ")"}


def _balanced_end(text: str, start: int) -> int | None:
    """The index just past the bracket that closes the one at ``text[start]``.

    String literals are stepped over, so a brace inside a name does not count.
    Returns None when the bracket never closes.
    """
    stack: list[str] = []
    index = start
    while index < len(text):
        char = text[index]
        if char in "\"'":
            close = text.find(char, index + 1)
            while close != -1 and text[close - 1] == "\\":
                close = text.find(char, close + 1)
            if close == -1:
                return None
            index = close + 1
            continue
        if char in _OPENERS:
            stack.append(_OPENERS[char])
        elif stack and char == stack[-1]:
            stack.pop()
            if not stack:
                return index + 1
        index += 1
    return None


def _literal_keys(node: ast.expr) -> tuple[list[tuple[str, int]], bool]:
    """The string keys a ``|=`` right-hand side registers, with their line in it.

    Returns ``(keys, complete)``: ``complete`` is False when some key is
    computed rather than written in the source.
    """
    if isinstance(node, ast.Dict):
        keys = [(key.value, key.lineno) for key in node.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)]
        return keys, len(keys) == len(node.keys)

    if not (isinstance(node, ast.DictComp) and len(node.generators) == 1
            and isinstance(node.key, ast.Name)):
        return [], False
    generator = node.generators[0]
    if isinstance(generator.target, ast.Name):
        position = None if generator.target.id == node.key.id else -1
    elif isinstance(generator.target, ast.Tuple):
        names = [element.id if isinstance(element, ast.Name) else None for element in generator.target.elts]
        position = names.index(node.key.id) if node.key.id in names else -1
    else:
        return [], False
    if position == -1 or generator.ifs or not isinstance(generator.iter, (ast.Tuple, ast.List)):
        return [], False

    keys: list[tuple[str, int]] = []
    rows = generator.iter.elts
    for row in rows:
        cell = row
        if position is not None:
            if not isinstance(row, (ast.Tuple, ast.List)) or len(row.elts) <= position:
                continue
            cell = row.elts[position]
        if isinstance(cell, ast.Constant) and isinstance(cell.value, str):
            keys.append((cell.value, row.lineno))
    return keys, len(keys) == len(rows)


def _bulk_items(cleaned: str) -> tuple[list[tuple[str, int]], int]:
    """The ``(key, line)`` pairs every ``define ALL_ITEMS |=`` of a file registers.

    Returns them with the number of statements that could not be read whole.
    """
    keys: list[tuple[str, int]] = []
    unread = 0
    for match in _BULK_RE.finditer(cleaned):
        start = match.end()
        end = _balanced_end(cleaned, start)
        try:
            node = ast.parse(cleaned[start:end], mode = "eval").body if end else None
        except SyntaxError:
            node = None
        if node is None:
            unread += 1
            continue
        found, complete = _literal_keys(node)
        unread += not complete
        first_line = cleaned[:start].count("\n") + 1
        keys.extend((key, first_line + line - 1) for key, line in found)
    return keys, unread


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` with one entry per inventory item key."""
    result = ExtractionResult(category = "inventory_items")
    seen: set[str] = set()

    for path in iter_all_rpy(context):
        text = safe_read_text(path)
        if text is None:
            continue

        cleaned = strip_noise(text)
        found = [
            (match.group("name"), cleaned[: match.start()].count("\n") + 1)
            for match in _ITEM_RE.finditer(cleaned)
        ]
        bulk, unread = _bulk_items(cleaned)
        if unread:
            result.warnings.append(Warning(
                message = f"{unread} `define ALL_ITEMS |=` statement(s) hold keys this scan cannot read; those keys are not listed",
                source_file = context.relative(path),
            ))

        for name, line in found + bulk:
            if name in seen:
                continue
            seen.add(name)
            result.entries.append(
                AllowlistEntry(
                    name = name,
                    source_file = context.relative(path),
                    source_line = line,
                ),
            )

    result.entries.sort(key = lambda entry: entry.name)
    return result
