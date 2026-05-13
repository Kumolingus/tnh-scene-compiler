#!/usr/bin/env bash
# Fountain-TNH Scene Compiler — CLI entry point.
# Usage: ./compile.sh [file1.scene file2.scene ...]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOOL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

export PYTHONPATH="${TOOL_ROOT}:${PYTHONPATH:-}"

if [ $# -eq 0 ]; then
    python3 -m tnh_scene_compiler compile --verbose
else
    python3 -m tnh_scene_compiler compile --verbose "$@"
fi
