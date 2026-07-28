"""Extract the inventory keys of every character's clothing.

Rules:

- Scan every ``.rpy`` across TNH (when included) and the mod.
- Match ``define <Character>_all_Clothes["<id>"] = {`` — one file per garment
  under ``characters/<Character>/clothing/items/<id>.rpy``.
- Produce one output file per character under ``clothing_items/<Character>.yaml``.
- Duplicate ids within a character are dropped, keeping the first occurrence.

**The emitted name is the inventory key, not the id.** ``InventoryClass.add``
files a garment under ``Item.tag`` while a plain item goes under
``Item.string`` (``core/definitions/inventory.rpy``), and ``ClothingClass.tag``
is ``f"{self.Owner.tag}_{self.string}"`` (``core/definitions/clothing.rpy``).
So the string ``Character.Inventory.get_active(...)`` wants is
``JeanGrey_beige_cargo_pants``, never ``beige_cargo_pants`` — emitting the bare
id would suggest values that silently never match.

The owner prefix is the *owner's* tag, which is normally the character wearing
it but does not have to be (``add`` takes ``Owner = False`` to preserve
ownership when a garment changes hands). The dropdown these feed stays
editable for that case.

Clothing *types* (``pants``, ``bra``, … — the keys of ``Character.Clothes``)
are a different, much smaller id space and are deliberately not collected here.
"""

from __future__ import annotations

import re

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import iter_all_rpy, safe_read_text

_CLOTHING_RE = re.compile(
    r"define\s+(?P<character>[A-Z][A-Za-z0-9]+)_all_Clothes\s*\[\s*"
    r"[\"'](?P<item>[^\"']+)[\"']\s*\]\s*=",
)


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` keyed by character with its inventory keys."""
    result = ExtractionResult(category = "clothing_items")

    for path in iter_all_rpy(context):
        text = safe_read_text(path)
        if text is None:
            continue

        cleaned = strip_noise(text)
        for match in _CLOTHING_RE.finditer(cleaned):
            character = match.group("character")
            key = f"{character}_{match.group('item')}"
            entries = result.per_character.setdefault(character, [])
            if any(entry.name == key for entry in entries):
                continue

            entries.append(
                AllowlistEntry(
                    name = key,
                    source_file = context.relative(path),
                    source_line = cleaned[: match.start()].count("\n") + 1,
                ),
            )

    return result
