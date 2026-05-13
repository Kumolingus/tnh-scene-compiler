"""Emit an empty scaffold for condition functions.

This extractor does **not** discover anything from source code. The
``condition_functions.yaml`` file lists helpers that writers are allowed
to call from ``[[if]]`` expressions — an explicit API surface the dev
curates by hand so nothing private leaks into writer-accessible scope.

The scaffold is created on first run and preserved on subsequent runs.
The extractor always returns an empty :class:`ExtractionResult`; the
``__main__`` orchestrator is responsible for emitting the scaffold file
(see :data:`tnh_refresh_allowlists.__main__._MANUAL_SCAFFOLDS`).
"""

from __future__ import annotations

from ..models import ExtractionResult, ScanContext


def extract(context: ScanContext) -> ExtractionResult:
    """Return an empty :class:`ExtractionResult`; scaffold handled by main."""
    return ExtractionResult(category = "condition_functions")
