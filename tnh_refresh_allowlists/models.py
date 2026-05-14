"""Data classes shared by every extractor."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AllowlistEntry:
    """One entry in a generated allowlist.

    Attributes:
        name: The value itself (e.g. a mood name, a slugline, a character tag).
        source_file: Repo-relative path of the file where the value was found.
        source_line: 1-based line number in ``source_file``.
        subgroup: Optional sub-list name. When set, per-character writers
            emit this entry under the ``subgroup`` key instead of ``values``.
            Example: the arms extractor uses ``"arms"``, ``"left_arm"``,
            ``"right_arm"`` to partition entries within one character file.
        metadata: Optional extra fields emitted alongside the entry in the
            output YAML. Stored as a tuple of ``(key, value)`` pairs so the
            dataclass stays frozen/hashable. Example: the locations extractor
            attaches ``("location_id", "loc_XavierSchool_PlayerRoom")``.
    """

    name: str
    source_file: str
    source_line: int
    subgroup: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(slots=True)
class Warning:
    """A non-blocking issue reported during extraction.

    Attributes:
        message: Human-readable description.
        source_file: Repo-relative path of the file involved, if any.
    """

    message: str
    source_file: str | None = None


@dataclass(slots=True)
class ExtractionResult:
    """Output of a single extractor.

    Attributes:
        category: A short identifier (e.g. ``"characters"``) used as the output
            file basename or subfolder.
        entries: Flat list of entries when the extractor produces a single file.
        per_character: Mapping ``character -> entries`` when the extractor
            produces one file per character.
        warnings: Non-blocking issues collected during extraction.
    """

    category: str
    entries: list[AllowlistEntry] = field(default_factory = list)
    per_character: dict[str, list[AllowlistEntry]] = field(default_factory = dict)
    warnings: list[Warning] = field(default_factory = list)


@dataclass(slots=True)
class ScanContext:
    """Read-only context passed to every extractor.

    Attributes:
        base_game_root: Absolute path to the extracted TNH build root.
        project_root: Absolute path to the mod source root.
        repo_root: Absolute path used to compute repo-relative source paths.
        include_tnh: Whether to include values derived from the TNH build.
    """

    base_game_root: Path
    project_root: Path
    repo_root: Path
    include_tnh: bool = True

    def relative(self, path: Path) -> str:
        """Return ``path`` relative to ``repo_root`` as a forward-slash string."""
        try:
            return path.resolve().relative_to(self.repo_root.resolve()).as_posix()
        except ValueError:
            return path.as_posix()
