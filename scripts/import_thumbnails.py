"""Import character thumbnails from TNH-VisualReference.

Reads face and arm PNGs from a TNH-VisualReference checkout, resizes them
to lightweight thumbnails, and generates a ``_mapping.yaml`` that maps
allowlist names to thumbnail file paths.

Requires: Pillow (``pip install Pillow``).
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

try:
    from PIL import Image
except ImportError:
    print(
        "ERROR: Pillow is required for thumbnail generation.\n"
        "Install it with:  pip install Pillow",
        file=sys.stderr,
    )
    sys.exit(1)

FACE_THUMB_WIDTH = 156
ARMS_THUMB_WIDTH = 200

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWLISTS_DIR = REPO_ROOT / "allowlists_base"
OUTPUT_DIR = REPO_ROOT / "thumbnails"


# -- Allowlist reading -------------------------------------------------------

def _read_yaml(path: Path) -> dict[str, Any] | None:
    """Return the top-level mapping of *path* or ``None`` if missing."""
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        return None
    return data


def _values_names(payload: dict[str, Any] | None, key: str = "values") -> list[str]:
    """Extract ``name`` fields from a list stored under *key*."""
    if not payload:
        return []
    entries = payload.get(key)
    if not isinstance(entries, list):
        return []
    return [
        item["name"]
        for item in entries
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]


def _load_face_names(character: str) -> list[str]:
    """Return canonical face names for *character* from allowlists."""
    path = ALLOWLISTS_DIR / "faces" / f"{character}.yaml"
    return _values_names(_read_yaml(path))


def _load_arm_names(character: str) -> tuple[list[str], list[str], list[str]]:
    """Return (both_arms, left_arm, right_arm) name lists."""
    path = ALLOWLISTS_DIR / "arms" / f"{character}.yaml"
    payload = _read_yaml(path)
    if not payload:
        return [], [], []
    both = _values_names(payload, "arms")
    left = _values_names(payload, "left_arm")
    right = _values_names(payload, "right_arm")
    return both, left, right


# -- Shortname detection -----------------------------------------------------

def _detect_shortname(char_dir: Path) -> str | None:
    """Detect the character's filename prefix from existing PNGs.

    Looks in Faces/ first, then Arms/. Returns ``None`` if no PNGs exist.
    """
    for subdir in ("Faces", "Arms"):
        folder = char_dir / subdir
        if not folder.is_dir():
            continue
        pngs = sorted(folder.glob("*.png"))
        if pngs:
            # Shortname is everything before the first underscore
            stem = pngs[0].stem
            idx = stem.find("_")
            if idx > 0:
                return stem[:idx]
    return None


# -- PNG matching ------------------------------------------------------------

def _find_png(
    folder: Path,
    expected_filename: str,
    all_stems: set[str],
) -> Path | None:
    """Find a PNG file by exact name, falling back to fuzzy matching."""
    # Exact match
    candidate = folder / expected_filename
    if candidate.is_file():
        return candidate

    # Fuzzy match against actual filenames
    expected_stem = Path(expected_filename).stem
    matches = difflib.get_close_matches(expected_stem, all_stems, n=1, cutoff=0.8)
    if matches:
        fuzzy = folder / f"{matches[0]}.png"
        if fuzzy.is_file():
            return fuzzy

    return None


# -- Thumbnail generation ----------------------------------------------------

def _resize_and_save(src: Path, dst: Path, target_width: int) -> None:
    """Resize *src* to *target_width* (keeping aspect ratio) and save to *dst*."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        w, h = img.size
        if w <= 0:
            return
        ratio = target_width / w
        new_size = (target_width, max(1, int(h * ratio)))
        resized = img.resize(new_size, Image.LANCZOS)
        resized.save(dst, "PNG", optimize=True)


def _process_faces(
    character: str,
    shortname: str,
    char_dir: Path,
    width: int,
) -> dict[str, str]:
    """Generate face thumbnails. Returns mapping {name: relative_path}."""
    faces_dir = char_dir / "Faces"
    if not faces_dir.is_dir():
        return {}

    names = _load_face_names(character)
    if not names:
        return {}

    all_stems = {p.stem for p in faces_dir.glob("*.png")}
    mapping: dict[str, str] = {}
    skipped = 0

    for name in names:
        expected = f"{shortname}_{name}.png"
        src = _find_png(faces_dir, expected, all_stems)
        if src is None:
            skipped += 1
            continue

        rel = f"faces/{character}/{name}.png"
        dst = OUTPUT_DIR / rel
        _resize_and_save(src, dst, width)
        mapping[name] = rel

    total = len(names)
    matched = total - skipped
    print(f"  Faces: {matched}/{total} matched", end="")
    if skipped:
        print(f" ({skipped} skipped)")
    else:
        print()

    return mapping


def _process_arms(
    character: str,
    shortname: str,
    char_dir: Path,
    width: int,
) -> dict[str, str]:
    """Generate arm thumbnails. Returns mapping {prefixed_name: relative_path}."""
    arms_dir = char_dir / "Arms"
    if not arms_dir.is_dir():
        return {}

    both, left, right = _load_arm_names(character)
    if not both and not left and not right:
        return {}

    all_stems = {p.stem for p in arms_dir.glob("*.png")}
    mapping: dict[str, str] = {}
    total = 0
    skipped = 0

    for _side_label, side_prefix, names in [
        ("both", "both", both),
        ("left", "left", left),
        ("right", "right", right),
    ]:
        for name in names:
            total += 1
            expected = f"{shortname}_{side_prefix}_{name}.png"
            src = _find_png(arms_dir, expected, all_stems)
            if src is None:
                skipped += 1
                continue

            key = f"{side_prefix}_{name}"
            rel = f"arms/{character}/{key}.png"
            dst = OUTPUT_DIR / rel
            _resize_and_save(src, dst, width)
            mapping[key] = rel

    matched = total - skipped
    print(f"  Arms:  {matched}/{total} matched", end="")
    if skipped:
        print(f" ({skipped} skipped)")
    else:
        print()

    return mapping


# -- Main --------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import character thumbnails from TNH-VisualReference.",
    )
    parser.add_argument(
        "visual_ref_dir",
        type=Path,
        help="Path to the TNH-VisualReference repository root.",
    )
    parser.add_argument(
        "--face-width",
        type=int,
        default=FACE_THUMB_WIDTH,
        help=f"Thumbnail width for faces (default: {FACE_THUMB_WIDTH}px).",
    )
    parser.add_argument(
        "--arms-width",
        type=int,
        default=ARMS_THUMB_WIDTH,
        help=f"Thumbnail width for arms (default: {ARMS_THUMB_WIDTH}px).",
    )
    args = parser.parse_args()

    face_width = args.face_width
    arms_width = args.arms_width

    ref_dir: Path = args.visual_ref_dir.resolve()
    characters_dir = ref_dir / "characters"
    if not characters_dir.is_dir():
        print(
            f"ERROR: {characters_dir} is not a directory.\n"
            "Expected a TNH-VisualReference checkout with a characters/ folder.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Clean previous output
    if OUTPUT_DIR.is_dir():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    faces_mapping: dict[str, dict[str, str]] = {}
    arms_mapping: dict[str, dict[str, str]] = {}
    total_generated = 0
    total_skipped = 0

    for char_dir in sorted(characters_dir.iterdir()):
        if not char_dir.is_dir():
            continue
        character = char_dir.name

        shortname = _detect_shortname(char_dir)
        if shortname is None:
            print(f"{character}: no PNGs found, skipping")
            continue

        print(f"{character} (shortname: {shortname}):")

        face_map = _process_faces(character, shortname, char_dir, face_width)
        arm_map = _process_arms(character, shortname, char_dir, arms_width)

        if face_map:
            faces_mapping[character] = face_map
        if arm_map:
            arms_mapping[character] = arm_map

        total_generated += len(face_map) + len(arm_map)

    # Write mapping
    mapping_data = {
        "generated_at": datetime.date.today().isoformat(),
        "source": str(ref_dir),
        "face_width": face_width,
        "arms_width": arms_width,
        "faces": faces_mapping,
        "arms": arms_mapping,
    }
    mapping_path = OUTPUT_DIR / "_mapping.yaml"
    mapping_path.write_text(
        yaml.safe_dump(mapping_data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    print(f"\nDone: {total_generated} thumbnails generated.")
    print(f"Mapping written to {mapping_path}")


if __name__ == "__main__":
    main()
