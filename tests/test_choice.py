"""Parser + codegen tests for ``[[choice]]`` blocks."""

from __future__ import annotations

import pytest

from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.ast_nodes import Choice, NarrationBlock
from tnh_scene_compiler.codegen import CodegenContext, generate
from tnh_scene_compiler.errors import CompileError
from tnh_scene_compiler.parser import parse

_PREFIX = (
    "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
    "Scene Type: cinematic\nTrigger: manual\n\n"
)

_CTX = CodegenContext(mod_prefix = "testmod")


def test_parse_minimal_choice_block() -> None:
    src = _PREFIX + (
        "[[choice]]\n"
        "= Option A\n"
        "    Body A.\n"
        "= Option B\n"
        "    Body B.\n"
        "[[/choice]]\n"
    )

    scene = parse(src, path = "inline.scene")

    choice = next(n for n in scene.body if isinstance(n, Choice))
    assert len(choice.options) == 2
    assert choice.options[0].text == "Option A"
    assert choice.options[1].text == "Option B"


def test_parse_option_with_condition() -> None:
    src = _PREFIX + (
        "[[choice]]\n"
        "= Offer gift [[if JeanGrey.love >= 500]]\n"
        "    Body.\n"
        "[[/choice]]\n"
    )

    scene = parse(src, path = "inline.scene")

    choice = next(n for n in scene.body if isinstance(n, Choice))
    assert choice.options[0].text == "Offer gift"
    assert choice.options[0].condition is not None


def test_parse_option_body_nodes_are_preserved() -> None:
    src = _PREFIX + (
        "[[choice]]\n"
        "= Option\n"
        "    Narration line.\n"
        "[[/choice]]\n"
    )

    scene = parse(src, path = "inline.scene")

    choice = next(n for n in scene.body if isinstance(n, Choice))
    body = choice.options[0].body
    assert any(isinstance(n, NarrationBlock) for n in body)


def test_parse_unclosed_choice_errors() -> None:
    src = _PREFIX + "[[choice]]\n= Option\n    Body.\n"

    with pytest.raises(CompileError) as excinfo:
        parse(src, path = "inline.scene")

    assert "/choice" in excinfo.value.message


def test_parse_choice_without_options_errors() -> None:
    src = _PREFIX + "[[choice]]\n[[/choice]]\n"

    with pytest.raises(CompileError) as excinfo:
        parse(src, path = "inline.scene")

    assert "options" in excinfo.value.message


def test_parse_stray_option_at_top_level_errors() -> None:
    src = _PREFIX + "= Stray option\n"

    with pytest.raises(CompileError) as excinfo:
        parse(src, path = "inline.scene")

    assert "[[choice]]" in excinfo.value.message


def test_codegen_choice_emits_menu(allowlists: Allowlists) -> None:
    src = _PREFIX + (
        "[[choice]]\n"
        "= First\n"
        "    JEANGREY\n    One.\n"
        "= Second\n"
        "    JEANGREY\n    Two.\n"
        "[[/choice]]\n"
    )
    scene = parse(src, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "menu:" in output
    assert "\"First\":" in output
    assert "\"Second\":" in output


def test_codegen_option_condition_emits_if_clause(allowlists: Allowlists) -> None:
    src = _PREFIX + (
        "[[choice]]\n"
        "= Offer [[if JeanGrey.love >= 500]]\n"
        "    JEANGREY\n    Thanks.\n"
        "[[/choice]]\n"
    )
    scene = parse(src, path = "inline.scene")

    output = generate(scene, allowlists, _CTX)

    assert "\"Offer\" if JeanGrey.love >= 500:" in output
