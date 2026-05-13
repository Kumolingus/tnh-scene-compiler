"""AST node definitions for the Fountain-TNH compiler.

Phase 6A covers the subset needed for cinematic scenes without directives or
parentheticals. Later phases extend this module with :class:`Parenthetical`,
:class:`IfChain`, :class:`Choice`, :class:`Directive` families, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TitlePage:
    """Parsed title page.

    Attributes:
        title: Human-readable scene title (``Title:`` key).
        scene_id: Mod-prefixed snake_case scene identifier (``Scene Id:`` key).
        character: Owning character in PascalCase (``Character:`` key).
        scene_type: One of ``cinematic``, ``phone``, ``texting``, ``hub_option``.
        trigger: Trigger enum value; ``None`` when omitted for non-cinematic.
        description: Optional one-line summary (``Description:`` key).
        conditions: Optional raw condition string (``Conditions:`` key).
        priority: Optional event priority (``Priority:`` key). Default 50
            is applied by the codegen, not the parser.
        repeatable: Optional bool (``Repeatable:`` key).
        tags: Optional list of mod-prefixed tag strings (``Tags:`` key).
        location: Optional slugline text implying ``set_scene`` at entry
            (``Location:`` key).
        format_version: Optional format version override (``Format:`` key).
        source_line: 1-based line where the title page starts (always 1).
    """

    title: str
    scene_id: str
    character: str
    scene_type: str
    trigger: str | None = None
    description: str | None = None
    conditions: str | None = None
    priority: int | None = None
    repeatable: bool | None = None
    tags: tuple[str, ...] = ()
    location: str | None = None
    format_version: int | None = None
    openness: str | None = None
    stage: str | None = None
    source_line: int = 1


@dataclass(frozen=True, slots=True)
class Slugline:
    """A Fountain-style slugline (``INT.`` / ``EXT.`` / ``INT./EXT.`` / ``I/E.``).

    The validator resolves :attr:`text` against the location allowlist to
    emit ``location_id``; the AST only carries the raw text and source
    position so errors can point at the original spelling.
    """

    prefix: str
    text: str
    line: int
    col: int


@dataclass(frozen=True, slots=True)
class Parenthetical:
    """Visual attributes carried by a dialogue line's parenthetical.

    Slot order matches §11.6:
    ``(mood, face, arms, look, outfit, stage)``. Named-only slots
    (``left_arm``, ``right_arm``, ``pose``) have no positional index.

    Each slot holds either the value string or ``None`` when unspecified.
    The ``medium`` slot is ``"spoken"`` (default), ``"text"`` (phone-text
    line), or ``None`` when not explicitly set — ``None`` and ``"spoken"``
    are interchangeable at codegen time.
    """

    mood: str | None = None
    face: str | None = None
    arms: str | None = None
    look: str | None = None
    outfit: str | None = None
    stage: str | None = None
    left_arm: str | None = None
    right_arm: str | None = None
    pose: str | None = None
    medium: str | None = None
    line: int = 0
    col: int = 0

    def has_visuals(self) -> bool:
        """Return ``True`` when any visual slot is set. Medium is ignored."""
        return any((
            self.mood, self.face, self.arms, self.look, self.outfit,
            self.stage, self.left_arm, self.right_arm, self.pose,
        ))


@dataclass(frozen=True, slots=True)
class DialogueBlock:
    """One dialogue block: a speaker on its own line, followed by prose.

    ``parenthetical`` carries the §11.6 visual/medium attributes when
    present; ``None`` means the speaker line was bare.
    """

    speaker: str
    text: str
    line: int
    col: int
    parenthetical: Parenthetical | None = None


@dataclass(frozen=True, slots=True)
class NarrationBlock:
    """A narrator paragraph: plain prose with no preceding speaker."""

    text: str
    line: int
    col: int


@dataclass(frozen=True, slots=True)
class Pause:
    """``[[pause N]]`` directive."""

    seconds: float
    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class Sfx:
    """``[[sfx name]]`` or ``[[sfx name N]]`` directive.

    ``duration`` is ``None`` when the author only wrote ``[[sfx name]]``
    (play through, no cap). When set, it caps playback at ``N`` seconds.
    """

    name: str
    duration: float | None = None
    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class SetDirective:
    """``[[set key]]`` or ``[[set key = value]]``.

    ``value`` is ``True`` for the bare ``[[set key]]`` form; otherwise one of
    ``bool``, ``int``, ``float``, or ``str``.
    """

    key: str
    value: bool | int | float | str
    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class Label:
    """``[[label name]]`` — scene-local anchor for :class:`Goto`."""

    name: str
    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class Goto:
    """``[[goto name]]`` — unconditional jump to a scene-local :class:`Label`."""

    name: str
    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class ModSet:
    """``[[mod_set <call>]]`` — allowlisted persistent-state mutation.

    Attributes:
        call_text: The raw call expression between ``[[mod_set`` and ``]]``,
            kept verbatim for codegen. Stored as a string rather than a
            full AST since §11.12 freezes the allowlisted operations as
            explicit contracts; the parser only checks that the target
            function/method matches an allowlist entry.
        target_name: The function name (bare) or last attribute
            (``Char.method`` -> ``method``) used for allowlist lookup.
    """

    call_text: str
    target_name: str
    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class FxCall:
    """``[[fx <call>]]`` — allowlisted engine-effect invocation.

    Distinct from :class:`ModSet`: ``fx`` is side-effect only (plays a
    visual / transient animation via a TNH core helper like
    ``phone_buzz()`` or ``knock_on_door()``), while ``mod_set`` writes
    persistent state. Keeping them separate makes the intent of each
    scene line obvious to a reader and lets the allowlists stay
    purpose-specific: ``fx.yaml`` lists engine effects,
    ``mod_operations.yaml`` lists state mutations.

    Attributes match :class:`ModSet` — ``call_text`` is the verbatim
    source to splice into ``$ …``, ``target_name`` is the allowlist key.
    """

    call_text: str
    target_name: str
    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class CallScene:
    """``[[call <scene_id>]]`` — chain another scene label."""

    scene_id: str
    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class Approval:
    """``[[approval Char love +large_stat]]`` — call ``update_approval(...)``.

    Maps to TNH's ``update_approval(Character, flavor, value)`` helper at
    ``core/mechanics/approval.rpy:59``. The two flavours TNH branches on
    are ``"love"`` and ``"trust"``; any other value would raise at runtime
    (the helper relies on ``shade`` being set in those two branches), so
    the parser keeps that enum closed.

    Attributes:
        character: PascalCase identifier; cross-checked against
            ``characters.yaml`` by the validator.
        axis: ``"love"`` or ``"trust"``.
        magnitude_text: The magnitude as written, kept verbatim for
            codegen — either a stat-tier name (``tiny_stat``,
            ``small_stat``, ``medium_stat``, ``large_stat``,
            ``massive_stat``) or a positive integer literal as a string.
            TNH defines the stat-tier constants at
            ``core/mechanics/approval.rpy:1-7`` so referencing them by
            name in the emitted ``$ update_approval(...)`` line keeps the
            output readable and benefits from any base-game rebalance.
        sign: ``"+"`` or ``"-"``. Required (no implicit sign) so a writer
            cannot accidentally swap the direction of an approval change.
    """

    character: str
    axis: str
    magnitude_text: str
    sign: str
    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class PhoneOpen:
    """``[[phone open]]`` or ``[[phone open <Character>]]``.

    ``character`` is the optional PascalCase character name when the
    author supplied one; ``None`` means "open the generic phone view".
    """

    character: str | None = None
    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class PhoneClose:
    """``[[phone close]]`` — close the in-game phone overlay."""

    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class Show:
    """``[[show <Character> attr=val ...]]`` — visual change without dialogue.

    ``attrs`` uses the parenthetical's named slot vocabulary (no positional,
    no ``text`` medium). The validator cross-checks values against the
    character's per-slot allowlist the same way it does for dialogue lines.
    """

    character: str
    attrs: dict[str, str]
    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class Hide:
    """``[[hide <Character>]]`` — remove the character from the scene."""

    character: str
    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class ChoiceOption:
    """One branch inside a :class:`Choice` block.

    Attributes:
        text: The label the player sees (may contain ``[interpolation]``).
        condition: Optional expression from a trailing ``[[if ...]]`` on the
            ``= Option`` line; ``None`` means the option is always offered.
        body: Nested body nodes that run when the player picks this option.
    """

    text: str
    condition: object | None  # Expr; kept as object to avoid an AST cycle.
    body: tuple[BodyNode, ...]  # type: ignore[name-defined]
    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class Choice:
    """``[[choice]]`` / ``= Option`` / ``[[/choice]]`` block.

    Branches fall through to the statement after ``[[/choice]]`` when their
    body ends without a :class:`Goto`, matching spec §11.9 "Choices".
    """

    options: tuple[ChoiceOption, ...]
    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class IfBranch:
    """One ``if`` / ``elif`` / ``else`` branch.

    ``condition`` is an :class:`~.expr_parser.Expr` for the ``if`` and
    ``elif`` branches, and ``None`` for the ``else`` branch. ``body`` is
    the list of body nodes nested inside this branch — itself a tuple of
    :data:`BodyNode` so conditionals nest.
    """

    condition: object | None  # Expr from expr_parser; kept as object to avoid a circular import.
    body: tuple[BodyNode, ...]  # type: ignore[name-defined]
    line: int = 0
    col: int = 0


@dataclass(frozen=True, slots=True)
class IfChain:
    """A ``[[if]]`` / ``[[elif]]`` / ``[[else]]`` / ``[[/if]]`` block.

    ``branches`` lists the branches in source order. The first is always
    an ``if`` with a non-``None`` condition; subsequent branches can be
    ``elif`` or ``else``. A lone ``else`` must be the last branch.
    """

    branches: tuple[IfBranch, ...]
    line: int = 0
    col: int = 0


# ``BodyNode`` enumerates every statement the parser can produce in a scene
# body. Extended in later phases — readers should treat the list as open.
BodyNode = (
    Slugline | DialogueBlock | NarrationBlock
    | Pause | Sfx | SetDirective | Label | Goto | IfChain
    | CallScene | PhoneOpen | PhoneClose | Show | Hide | Choice | ModSet | FxCall
)


@dataclass(frozen=True, slots=True)
class Scene:
    """A fully parsed scene ready for validation and codegen.

    Attributes:
        source_path: Path of the ``.scene`` file, used in error messages.
        title_page: Parsed title page — always present after a successful
            parse.
        body: Ordered list of body nodes.
    """

    source_path: str
    title_page: TitlePage
    body: tuple[BodyNode, ...] = field(default_factory=tuple)
