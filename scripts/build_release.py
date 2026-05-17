"""Build a local release: exe via PyInstaller + thumbnails.zip.

Usage:
    python scripts/build_release.py

Produces in ``dist/TNHSceneCompiler-<version>/``:
    TNHSceneCompiler-<version>.exe   — the application (no thumbnails)
    thumbnails.zip                   — thumbnails to unzip next to the exe
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _get_version() -> str:
    sys.path.insert(0, str(REPO_ROOT))
    from tnh_scene_compiler import __version__
    return __version__


def main() -> int:
    version = _get_version()

    # --- Generate thumbnails ---
    thumbnails_dir = REPO_ROOT / "thumbnails"
    import_script = REPO_ROOT / "scripts" / "import_thumbnails.py"

    if not thumbnails_dir.is_dir() or not (thumbnails_dir / "_mapping.yaml").is_file():
        print("Generating thumbnails...")
        result = subprocess.run(
            [sys.executable, str(import_script)],
            cwd=str(REPO_ROOT),
        )
        if result.returncode != 0:
            print("WARNING: thumbnail generation failed, zip will be skipped")

    # --- Clean previous build ---
    for d in ("dist", "build"):
        target = REPO_ROOT / d
        if target.is_dir():
            shutil.rmtree(target)
            print(f"Cleaned {d}/")

    # --- Build exe ---
    print("\nBuilding executable...")
    spec = REPO_ROOT / "tnh_scene_compiler.spec"
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", str(spec)],
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        print("ERROR: PyInstaller build failed")
        return 1

    # --- Move into versioned folder ---
    dist = REPO_ROOT / "dist"
    release_dir = dist / f"TNHSceneCompiler-{version}"
    release_dir.mkdir(parents=True, exist_ok=True)

    exe_name = f"TNHSceneCompiler-{version}.exe"
    exe_src = dist / exe_name
    if exe_src.is_file():
        shutil.move(str(exe_src), str(release_dir / exe_name))

    # --- Copy docs ---
    docs_src = REPO_ROOT / "docs"
    if docs_src.is_dir():
        docs_dst = release_dir / "docs"
        shutil.copytree(str(docs_src), str(docs_dst))
        print(f"Copied docs/ ({len(list(docs_dst.iterdir()))} files)")

    # --- Package thumbnails ---
    if thumbnails_dir.is_dir():
        print("\nPackaging thumbnails.zip...")
        shutil.make_archive(str(release_dir / "thumbnails"), "zip", str(REPO_ROOT), "thumbnails")

    print(f"\nBuild complete. Contents of dist/TNHSceneCompiler-{version}/:")
    for f in sorted(release_dir.iterdir()):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f.name}  ({size_mb:.1f} MB)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
