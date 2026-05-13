"""Extract the list of valid arm poses per character and slot.

Rules (spec §5.4):

- Find every ``define <Character>_poses["<pose_name>"] = {`` block.
- Walk the block with a naive brace counter to isolate its body.
- Inside the body, find the set literals keyed on ``"arms"``, ``"left_arm"``,
  and ``"right_arm"``; extract every string literal from each set.
- Additionally, scan every ``define <Character>_arms["<preset>"]`` top-level
  declaration and register the preset name under the ``arms`` subgroup.
  Presets defined this way are valid arguments to ``<Char>.change_arms(...)``
  and must appear in the allowlist even when no existing pose references
  them (e.g. ``clenched``, ``shrug``, ``hips`` — declared in
  ``<Character>/definitions/expressions.rpy`` but not always referenced
  from the smaller ``<Character>/images/standing/standing.rpy`` pose set).
- Produce one file per character, with three subgroups:
  ``arms``, ``left_arm``, ``right_arm``.
"""

from __future__ import annotations

import re

from ..comments import strip_noise
from ..models import AllowlistEntry, ExtractionResult, ScanContext
from ..scanner import iter_all_rpy, safe_read_text

_POSE_START_RE = re.compile(
    r'^[ \t]*define[ \t]+(?P<character>[A-Z][A-Za-z0-9]+)_poses\["(?P<pose>[^"]+)"\][ \t]*=[ \t]*\{',
    re.MULTILINE,
)

_ARMS_PRESET_RE = re.compile(
    r'^[ \t]*define[ \t]+(?P<character>[A-Z][A-Za-z0-9]+)_arms\["(?P<preset>[^"]+)"\]',
    re.MULTILINE,
)

_SLOT_RE = re.compile(
    r'"(?P<slot>arms|left_arm|right_arm)"[ \t]*:[ \t]*\{(?P<body>[^{}]*)\}',
    re.DOTALL,
)

_STRING_RE = re.compile(r'"(?P<value>[^"]+)"')


def _find_block_end(text: str, open_brace_index: int) -> int | None:
    """Return the index of the matching closing brace, or ``None`` if unbalanced."""
    depth = 0
    for index in range(open_brace_index, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` partitioned by character and slot."""
    result = ExtractionResult(category = "arms")

    for path in iter_all_rpy(context):
        text = safe_read_text(path)
        if text is None:
            continue

        cleaned = strip_noise(text)
        for match in _POSE_START_RE.finditer(cleaned):
            character = match.group("character")
            open_brace = match.end() - 1
            end = _find_block_end(cleaned, open_brace)
            if end is None:
                continue

            block_body = cleaned[open_brace + 1 : end]
            block_start_offset = open_brace + 1

            seen: set[tuple[str, str]] = set()
            for slot_match in _SLOT_RE.finditer(block_body):
                slot = slot_match.group("slot")
                body = slot_match.group("body")
                for value_match in _STRING_RE.finditer(body):
                    value = value_match.group("value")
                    key = (slot, value)
                    if key in seen:
                        continue
                    seen.add(key)

                    absolute_offset = block_start_offset + slot_match.start() + value_match.start()
                    line = cleaned[: absolute_offset].count("\n") + 1
                    entry = AllowlistEntry(
                        name = value,
                        source_file = context.relative(path),
                        source_line = line,
                        subgroup = slot,
                    )
                    result.per_character.setdefault(character, []).append(entry)

        # Second pass: pick up every ``define <Character>_arms["preset"]``
        # top-level definition so standalone arm presets that no pose
        # references (e.g. JeanGrey_arms["clenched"]) still land in the
        # ``arms`` subgroup. Without this, the compiler rejects legitimate
        # values like ``clenched`` / ``shrug`` / ``hips`` even though
        # ``<Char>.change_arms("clenched")`` works at runtime.
        for preset_match in _ARMS_PRESET_RE.finditer(cleaned):
            character = preset_match.group("character")
            preset = preset_match.group("preset")
            line = cleaned[: preset_match.start()].count("\n") + 1
            entry = AllowlistEntry(
                name = preset,
                source_file = context.relative(path),
                source_line = line,
                subgroup = "arms",
            )
            result.per_character.setdefault(character, []).append(entry)

    _deduplicate_across_poses(result)
    return result


def _deduplicate_across_poses(result: ExtractionResult) -> None:
    """Drop duplicate (slot, name) pairs per character, keeping the earliest one."""
    for character, entries in result.per_character.items():
        seen: set[tuple[str | None, str]] = set()
        deduped: list[AllowlistEntry] = []
        for entry in entries:
            key = (entry.subgroup, entry.name)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entry)
        result.per_character[character] = deduped
