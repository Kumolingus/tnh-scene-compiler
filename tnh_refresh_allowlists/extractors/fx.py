"""Extract engine effect names and signatures from TNH + mod source.

Scans three kinds of FX source:

1. **effects.rpy** — all Ren'Py ``label name(params):`` definitions in
   ``game/displayables/effects.rpy``.
2. **animations.rpy** — all ``label name(params):`` definitions in
   ``game/characters/*/animations.rpy``.
3. **Mechanics functions** — ``def`` functions in ``init python:`` blocks
   whose names match a known set (``phone_buzz``, ``knock_on_door``).
4. **Mod FX** — ``def`` functions in the mod source whose names match
   entries already present in the output ``fx.yaml`` (preserves
   mod-specific effects across refreshes).
"""

from __future__ import annotations

import re
from pathlib import Path

from ..models import AllowlistEntry, ExtractionResult, ScanContext, Warning
from ..scanner import safe_read_text, list_character_folders


_LABEL_DEF_RE = re.compile(
    r"^label\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\((?P<params>[^)]*)\))?\s*:",
    re.MULTILINE,
)

_FUNC_DEF_RE = re.compile(
    r"^[ \t]+def\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<params>[^)]*)\)"
    r"(?:\s*->\s*(?P<ret>[^:]+))?\s*:",
    re.MULTILINE,
)

_KNOWN_MECHANICS_FX: frozenset[str] = frozenset({
    "phone_buzz",
    "knock_on_door",
})


def _build_signature(name: str, raw_params: str, return_type: str | None) -> str:
    """Assemble a human-readable signature string from parsed components."""
    params = raw_params.strip() if raw_params else ""
    ret = return_type.strip() if return_type else "None"
    return f"{name}({params}) -> {ret}"


def _scan_labels(path: Path, text: str, context: ScanContext) -> list[AllowlistEntry]:
    """Extract all label definitions from a file (effects.rpy, animations.rpy)."""
    entries: list[AllowlistEntry] = []
    for match in _LABEL_DEF_RE.finditer(text):
        name = match.group("name")
        raw_params = match.group("params") or ""
        line = text[: match.start()].count("\n") + 1
        sig = _build_signature(name, raw_params, "None")
        entries.append(AllowlistEntry(
            name=name,
            source_file=context.relative(path),
            source_line=line,
            metadata=(("signature", sig),),
        ))
    return entries


def _scan_mechanics_functions(
    path: Path, text: str, context: ScanContext,
) -> list[AllowlistEntry]:
    """Extract known mechanics FX from def statements in init python blocks."""
    entries: list[AllowlistEntry] = []
    for match in _FUNC_DEF_RE.finditer(text):
        name = match.group("name")
        if name not in _KNOWN_MECHANICS_FX:
            continue
        raw_params = match.group("params") or ""
        ret = match.group("ret")
        line = text[: match.start()].count("\n") + 1
        sig = _build_signature(name, raw_params, ret)
        entries.append(AllowlistEntry(
            name=name,
            source_file=context.relative(path),
            source_line=line,
            metadata=(("signature", sig),),
        ))
    return entries


def _scan_mod_functions(
    path: Path, text: str, context: ScanContext, known_names: frozenset[str],
) -> list[AllowlistEntry]:
    """Extract mod FX functions by matching against known names."""
    if not known_names:
        return []
    entries: list[AllowlistEntry] = []
    for match in _FUNC_DEF_RE.finditer(text):
        name = match.group("name")
        if name not in known_names:
            continue
        raw_params = match.group("params") or ""
        ret = match.group("ret")
        line = text[: match.start()].count("\n") + 1
        sig = _build_signature(name, raw_params, ret)
        entries.append(AllowlistEntry(
            name=name,
            source_file=context.relative(path),
            source_line=line,
            metadata=(("signature", sig),),
        ))
    return entries


def _read_existing_mod_fx_names(out_dir: Path, base_game_prefix: str) -> frozenset[str]:
    """Read existing fx.yaml and return names whose source_file points to the mod."""
    import yaml

    fx_path = out_dir / "fx.yaml"
    if not fx_path.is_file():
        return frozenset()
    try:
        with fx_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError):
        return frozenset()
    if not isinstance(data, dict):
        return frozenset()
    effects = data.get("effects") or data.get("values")
    if not isinstance(effects, list):
        return frozenset()
    names: set[str] = set()
    for item in effects:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        src = item.get("source_file", "")
        if isinstance(name, str) and isinstance(src, str):
            if not src.startswith(base_game_prefix):
                names.add(name)
    return frozenset(names)


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` listing every discovered FX with signatures."""
    result = ExtractionResult(category="fx")
    seen: set[str] = set()

    # --- Base game: effects.rpy ---
    if context.include_tnh:
        effects_path = context.base_game_root / "game" / "displayables" / "effects.rpy"
        text = safe_read_text(effects_path)
        if text:
            for entry in _scan_labels(effects_path, text, context):
                if entry.name not in seen:
                    seen.add(entry.name)
                    result.entries.append(entry)

        # --- Base game: characters/*/animations.rpy ---
        chars_root = context.base_game_root / "game" / "characters"
        for char_dir in list_character_folders(chars_root):
            anim_path = char_dir / "animations.rpy"
            anim_text = safe_read_text(anim_path)
            if not anim_text:
                continue
            for entry in _scan_labels(anim_path, anim_text, context):
                if entry.name not in seen:
                    seen.add(entry.name)
                    result.entries.append(entry)

        # --- Base game: mechanics (phone_buzz, knock_on_door) ---
        mechanics_dir = context.base_game_root / "game" / "core" / "mechanics"
        if mechanics_dir.is_dir():
            for rpy_file in sorted(mechanics_dir.rglob("*.rpy")):
                mech_text = safe_read_text(rpy_file)
                if not mech_text:
                    continue
                for entry in _scan_mechanics_functions(rpy_file, mech_text, context):
                    if entry.name not in seen:
                        seen.add(entry.name)
                        result.entries.append(entry)

    # --- Mod FX: preserve existing mod entries by re-scanning source ---
    base_prefix = context.relative(context.base_game_root)
    mod_fx_names = _read_existing_mod_fx_names(
        context.project_root.parent / "scenes_source" / "_allowlists",
        base_prefix,
    )
    if mod_fx_names:
        from ..scanner import iter_rpy_files

        for rpy_file in iter_rpy_files(context.project_root):
            mod_text = safe_read_text(rpy_file)
            if not mod_text:
                continue
            for entry in _scan_mod_functions(rpy_file, mod_text, context, mod_fx_names):
                if entry.name not in seen:
                    seen.add(entry.name)
                    result.entries.append(entry)

    return result
