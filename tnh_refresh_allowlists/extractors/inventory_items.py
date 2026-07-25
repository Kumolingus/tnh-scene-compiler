"""Extract the inventory item keys.

Rules:

- Scan every ``.rpy`` across TNH (when included) and the mod.
- Match ``define all_Items["<key>"] = {...}`` — the registration pattern used
  by ``game/inventory/<key>.rpy``.
- Produce a single flat ``inventory_items.yaml``.

The key is what ``Character.Inventory.get_active(string=...)`` /
``get_number(string=...)`` take: ``Inventory.add`` stores a plain item under
``Item.string`` (``core/definitions/inventory.rpy``), which is this key.

Clothing is deliberately **not** collected. It goes through the other branch
of the same method — ``Items[Item.tag]``, where ``tag`` falls back to the
clothing id — and those ids live in per-character ``Clothes`` mappings with a
different shape. A writer needing one types it; the dropdown stays editable.
"""

from __future__ import annotations

import re

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import iter_all_rpy, safe_read_text

_ITEM_RE = re.compile(r'define\s+all_Items\s*\[\s*"(?P<name>[^"]+)"\s*\]')


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` with one entry per inventory item key."""
    result = ExtractionResult(category = "inventory_items")
    seen: set[str] = set()

    for path in iter_all_rpy(context):
        text = safe_read_text(path)
        if text is None:
            continue

        cleaned = strip_noise(text)
        for match in _ITEM_RE.finditer(cleaned):
            name = match.group("name")
            if name in seen:
                continue
            seen.add(name)

            line = cleaned[: match.start()].count("\n") + 1
            result.entries.append(
                AllowlistEntry(
                    name = name,
                    source_file = context.relative(path),
                    source_line = line,
                ),
            )

    result.entries.sort(key = lambda entry: entry.name)
    return result
