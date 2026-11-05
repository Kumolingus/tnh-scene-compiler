"""Extract base-game engine effect names and signatures from TNH source.

Scans three kinds of FX source:

1. **effects.rpy** — all Ren'Py ``label name(params):`` definitions in
   ``game/displayables/effects.rpy``, plus the ``def`` effects that have no
   label of their own but do have a ``cinematic_<name>`` label (``bamf``
   since TNH 0.9c) — the game pairs every scene effect with a cinematic
   variant, which is what sets them apart from the file's helper functions
   (``play_random_effect``, ``pow_effect`` …).
2. **animations.rpy** — all ``label name(params):`` definitions in
   ``game/characters/*/animations.rpy``, plus the character's animation
   functions: since TNH 0.9c.beta.28 every function of its
   ``init python in CHARACTERS.<Tag>.animations:`` store, before that the
   ``<Tag>_animations_*`` ``def`` functions of the default store (the file's
   other functions are rig helpers).
3. **Mechanics functions** — a known set (``phone_buzz``,
   ``knock_on_door``): a ``def`` in an ``init python:`` block under
   ``game/core/``, or, since TNH 0.9c.beta.28, a name the default store
   imports from a Python module (``from core.phone import buzz as
   phone_buzz``), read in that module.

A label is emitted with ``call_mode: label`` (compiled to ``call``), a
function without it (compiled to ``$``). When a name is both — 0.9c keeps a
label and a function for ``smack``, ``crack`` … — the label wins, so the
compiled call and its ``cinematic_`` override stay unchanged.

A function kept in a named store carries ``call``, the path a scene calls
it by (``CHARACTERS.LauraKinney.animations.sheathe_claws``,
``displayables.effects.bamf``). Its writer-facing name stays flat:
``<Tag>_animations_<function>`` for an animation, the same name the game's
own compatibility alias gives it, and the bare name for an effect. A scene
calls the function's home, not the alias the game keeps for old saves.

Project/mod-specific effects are NOT scanned here. They live in the
hand-maintained ``fx_custom.yaml`` allowlist (never regenerated) and are
merged with this auto-generated ``fx.yaml`` at load time — see
``tnh_scene_compiler.allowlists.Allowlists.load``.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from pathlib import Path

from ..models import AllowlistEntry, ExtractionResult, ScanContext, Warning
from ..scanner import safe_read_text, list_character_folders


_LABEL_DEF_RE = re.compile(
    r"^label\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\((?P<params>[^)]*)\))?\s*:",
    re.MULTILINE,
)

_FUNC_DEF_RE = re.compile(
    r"^(?P<indent>[ \t]+)def\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<params>[^)]*)\)"
    r"(?:\s*->\s*(?P<ret>[^:]+))?\s*:",
    re.MULTILINE,
)

# A Python block header at column 0: ``init -98 python:``,
# ``init python in CHARACTERS.LauraKinney.animations:``, ``python early:``.
_PYTHON_BLOCK_RE = re.compile(
    r"^(?:init(?:[ \t]+-?\d+)?[ \t]+)?python(?:[ \t]+early)?"
    r"(?:[ \t]+in[ \t]+(?P<store>[\w.]+))?(?:[ \t]+hide)?[ \t]*:",
)

# ``from module import a, b as c`` at any indentation, on one line or parenthesized.
_IMPORT_RE = re.compile(r"^[ \t]+from[ \t]+([\w.]+)[ \t]+import[ \t]+(\([^)]*\)|[^\n#]+)", re.MULTILINE)

# ``CHARACTERS.<Tag>.animations``, the store of a character's animations.
_ANIMATIONS_STORE_RE = re.compile(r"^CHARACTERS\.(?P<tag>[A-Za-z_]\w*)\.animations$")

_KNOWN_MECHANICS_FX: frozenset[str] = frozenset({
    "phone_buzz",
    "knock_on_door",
})


def _build_signature(name: str, raw_params: str, return_type: str | None) -> str:
    """Assemble a human-readable signature string from parsed components."""
    params = raw_params.strip() if raw_params else ""
    ret = return_type.strip() if return_type else "None"
    return f"{name}({params}) -> {ret}"


def _block_store(text: str, offset: int) -> str | None:
    """The store of the Python block holding *offset*: ``""`` for the default store.

    None when the nearest statement at column 0 before *offset* is no Python
    block header (the ``def`` sits in a label or a screen).
    """
    for line in reversed(text[:offset].splitlines()):
        if not line.strip() or line[0] in " \t#":
            continue
        match = _PYTHON_BLOCK_RE.match(line)
        if match is None:
            return None
        return match.group("store") or ""
    return None


def _is_block_level(indent: str) -> bool:
    """Whether a ``def`` indented by *indent* sits at its block's top level, not inside a function."""
    return indent in ("    ", "\t")


def _scan_labels(path: Path, text: str, context: ScanContext) -> list[AllowlistEntry]:
    """Extract all label definitions from a file (effects.rpy, animations.rpy).

    Skips ``cinematic_`` prefixed labels — those are auto-derived at
    compile time from the base effect name + scene type.
    """
    entries: list[AllowlistEntry] = []
    for match in _LABEL_DEF_RE.finditer(text):
        name = match.group("name")
        if name.startswith("cinematic_"):
            continue
        raw_params = match.group("params") or ""
        line = text[: match.start()].count("\n") + 1
        sig = _build_signature(name, raw_params, "None")
        entries.append(AllowlistEntry(
            name=name,
            source_file=context.relative(path),
            source_line=line,
            metadata=(("signature", sig), ("call_mode", "label")),
        ))
    return entries


def _scan_effect_functions(
    path: Path,
    text: str,
    context: ScanContext,
    name_for: Callable[[str, str], str | None],
) -> list[AllowlistEntry]:
    """Extract the block-level ``def`` effects of an FX source file.

    path     -- the file being scanned (effects.rpy or an animations.rpy)
    text     -- its content
    context  -- the scan context, for the relative source path
    name_for -- ``(store, function) -> writer-facing name``, or None for a
                function that is no effect; the caller's selection rule

    Returns one entry per accepted function, without a ``call_mode`` so the
    compiler emits it as a ``$`` Python call, and with ``call`` when the
    function lives in a named store.
    """
    entries: list[AllowlistEntry] = []
    for match in _FUNC_DEF_RE.finditer(text):
        if not _is_block_level(match.group("indent")):
            continue
        store = _block_store(text, match.start())
        if store is None:
            continue
        function = match.group("name")
        name = name_for(store, function)
        if name is None:
            continue
        line = text[: match.start()].count("\n") + 1
        metadata: tuple[tuple[str, str], ...] = (
            ("signature", _build_signature(name, match.group("params") or "", match.group("ret"))),
        )
        if store:
            metadata += (("call", f"{store}.{function}"),)
        entries.append(AllowlistEntry(
            name=name,
            source_file=context.relative(path),
            source_line=line,
            metadata=metadata,
        ))
    return entries


def _animation_name(tag: str) -> Callable[[str, str], str | None]:
    """The selection rule for the animation functions of character *tag*."""
    def name_for(store: str, function: str) -> str | None:
        if store:
            match = _ANIMATIONS_STORE_RE.match(store)
            return f"{tag}_animations_{function}" if match and match.group("tag") == tag else None
        return function if "_animations_" in function else None
    return name_for


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


def _module_file(game: Path, module: str) -> Path | None:
    """The ``.py`` file of a dotted game module, or None."""
    path = game.joinpath(*module.split("."))
    for candidate in (path.with_suffix(".py"), path / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _module_function(game: Path, module: str, name: str, depth: int = 0) -> tuple[Path, ast.FunctionDef] | None:
    """The module-level ``def`` that ``module.name`` names, following re-exports."""
    path = _module_file(game, module)
    if path is None or depth > 8:
        return None
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return path, node
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if (alias.asname or alias.name) == name:
                    if node.level:
                        parts = package.split(".")
                        parts = parts[:len(parts) - node.level + 1]
                        target = ".".join(parts + ([node.module] if node.module else []))
                    else:
                        target = node.module or ""
                    return _module_function(game, target, alias.name, depth + 1)
    return None


def _scan_imported_mechanics(
    game: Path, wanted: set[str], context: ScanContext, result: ExtractionResult,
) -> list[AllowlistEntry]:
    """Find the mechanics FX the default store imports from a Python module.

    TNH 0.9c.beta.28 binds them in ``definitions/core.rpy``
    (``from core.phone import buzz as phone_buzz``); the signature is read
    from the module's ``def`` and written under the store name.
    """
    entries: list[AllowlistEntry] = []
    for rpy_file in sorted(game.rglob("*.rpy")):
        if not wanted:
            break
        text = safe_read_text(rpy_file)
        if not text:
            continue
        for match in _IMPORT_RE.finditer(text):
            if _block_store(text, match.start()) != "":
                continue
            module = match.group(1)
            for part in match.group(2).strip("() \n").split(","):
                original, _, alias = (piece.strip() for piece in part.partition(" as "))
                bound = alias or original
                if bound not in wanted:
                    continue
                found = _module_function(game, module, original)
                if found is None:
                    result.warnings.append(Warning(
                        message=f"{bound} is imported from {module}, which defines no function {original}",
                        source_file=context.relative(rpy_file),
                    ))
                    continue
                path, node = found
                source = path.read_text(encoding="utf-8")
                header = re.compile(
                    rf"^def\s+{re.escape(original)}\s*\((?P<params>[^)]*)\)(?:\s*->\s*(?P<ret>[^:]+))?\s*:",
                    re.MULTILINE,
                ).search(source)
                params = header.group("params") if header else ast.unparse(node.args)
                ret = header.group("ret") if header else None
                entries.append(AllowlistEntry(
                    name=bound,
                    source_file=context.relative(path),
                    source_line=node.lineno,
                    metadata=(("signature", _build_signature(bound, params, ret)),),
                ))
                wanted.discard(bound)
    return entries


def extract(context: ScanContext) -> ExtractionResult:
    """Return an :class:`ExtractionResult` listing every discovered FX with signatures."""
    result = ExtractionResult(category="fx")
    seen: set[str] = set()

    def add(entries: list[AllowlistEntry]) -> None:
        for entry in entries:
            if entry.name not in seen:
                seen.add(entry.name)
                result.entries.append(entry)

    # --- Base game: effects.rpy ---
    if context.include_tnh:
        game = context.base_game_root / "game"
        effects_path = game / "displayables" / "effects.rpy"
        text = safe_read_text(effects_path)
        if text:
            add(_scan_labels(effects_path, text, context))
            # cinematic_ labels are skipped as entries but still name the
            # effects the game treats as scene effects.
            cinematic_twins = {
                match.group("name")[len("cinematic_"):]
                for match in _LABEL_DEF_RE.finditer(text)
                if match.group("name").startswith("cinematic_")
            }
            add(_scan_effect_functions(
                effects_path, text, context,
                lambda store, name: name if name in cinematic_twins else None,
            ))

        # --- Base game: characters/*/animations.rpy ---
        chars_root = game / "characters"
        for char_dir in list_character_folders(chars_root):
            anim_path = char_dir / "animations.rpy"
            anim_text = safe_read_text(anim_path)
            if not anim_text:
                continue
            add(_scan_labels(anim_path, anim_text, context))
            add(_scan_effect_functions(anim_path, anim_text, context, _animation_name(char_dir.name)))

        # --- Base game: mechanics (phone_buzz, knock_on_door) ---
        # The whole of core/: 0.9b kept them in core/mechanics/, 0.9c split
        # that folder per domain (core/phone/, core/behavior/), and
        # 0.9c.beta.28 moved them into Python modules the store imports.
        mechanics_dir = game / "core"
        if mechanics_dir.is_dir():
            for rpy_file in sorted(mechanics_dir.rglob("*.rpy")):
                mech_text = safe_read_text(rpy_file)
                if not mech_text:
                    continue
                add(_scan_mechanics_functions(rpy_file, mech_text, context))
        missing = set(_KNOWN_MECHANICS_FX) - seen
        if missing and game.is_dir():
            add(_scan_imported_mechanics(game, missing, context, result))

    return result
