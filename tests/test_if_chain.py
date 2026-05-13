"""Parser + codegen tests for ``[[if]]`` / ``[[elif]]`` / ``[[else]]``."""

from __future__ import annotations

import pytest

from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.ast_nodes import IfChain, NarrationBlock
from tnh_scene_compiler.codegen import CodegenContext, generate
from tnh_scene_compiler.errors import CompileError
from tnh_scene_compiler.parser import parse

_PREFIX = (
    "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
    "Scene Type: cinematic\nTrigger: manual\n\n"
)

_CTX = CodegenContext(project_prefix = "testmod")


def test_parse_simple_if_block() -> None:
    src = _PREFIX + (
        "[[if lied]]\n"
        "She looks away.\n"
        "[[/if]]\n"
    )

    scene = parse(src, path = "inline.scene")

    ifs = [n for n in scene.body if isinstance(n, IfChain)]
    assert len(ifs) == 1
    assert len(ifs[0].branches) == 1
    assert isinstance(ifs[0].branches[0].body[0], NarrationBlock)


def test_parse_if_elif_else() -> None:
    src = _PREFIX + (
        "[[if a]]\n"
        "One.\n"
        "[[elif b]]\n"
        "Two.\n"
        "[[else]]\n"
        "Three.\n"
        "[[/if]]\n"
    )

    scene = parse(src, path = "inline.scene")

    chain = next(n for n in scene.body if isinstance(n, IfChain))
    assert len(chain.branches) == 3
    assert chain.branches[0].condition is not None
    assert chain.branches[1].condition is not None
    assert chain.branches[2].condition is None


def test_parse_nested_if() -> None:
    src = _PREFIX + (
        "[[if outer]]\n"
        "[[if inner]]\n"
        "Nested.\n"
        "[[/if]]\n"
        "[[/if]]\n"
    )

    scene = parse(src, path = "inline.scene")

    outer = next(n for n in scene.body if isinstance(n, IfChain))
    inner = outer.branches[0].body[0]
    assert isinstance(inner, IfChain)


def test_parse_unclosed_if_errors() -> None:
    src = _PREFIX + "[[if a]]\nBody.\n"

    with pytest.raises(CompileError) as excinfo:
        parse(src, path = "inline.scene")

    assert "/if" in excinfo.value.message


def test_parse_stray_elif_errors() -> None:
    src = _PREFIX + "[[elif foo]]\n"

    with pytest.raises(CompileError) as excinfo:
        parse(src, path = "inline.scene")

    assert "elif" in excinfo.value.message


def test_codegen_emits_nested_if_elif_else(allowlists: Allowlists) -> None:
    src = _PREFIX + (
        "[[if JeanGrey.love >= 500]]\n"
        "JEANGREY\nOne.\n"
        "[[elif JeanGrey.love >= 300]]\n"
        "JEANGREY\nTwo.\n"
        "[[else]]\n"
        "JEANGREY\nThree.\n"
        "[[/if]]\n"
    )

    scene = parse(src, path = "inline.scene")
    output = generate(scene, allowlists, _CTX)

    assert "if JeanGrey.love >= 500:" in output
    assert "elif JeanGrey.love >= 300:" in output
    assert "else:" in output


def test_codegen_scene_local_reference_rewrites_to_dict(allowlists: Allowlists) -> None:
    src = _PREFIX + (
        "[[set lied]]\n"
        "[[if lied]]\n"
        "JEANGREY\nLine.\n"
        "[[/if]]\n"
    )

    scene = parse(src, path = "inline.scene")
    output = generate(scene, allowlists, _CTX)

    assert "_scene_state['lied'] = True" in output
    # Reference inside the [[if]] resolves to the dict getter.
    assert "if _scene_state.get('lied'):" in output


def test_codegen_expression_with_function_call(allowlists: Allowlists) -> None:
    src = _PREFIX + (
        "[[if check_approval(JeanGrey, \"love\")]]\n"
        "JEANGREY\nLine.\n"
        "[[/if]]\n"
    )

    scene = parse(src, path = "inline.scene")
    output = generate(scene, allowlists, _CTX)

    assert "check_approval(JeanGrey, \"love\")" in output


def test_codegen_empty_branch_gets_pass(allowlists: Allowlists) -> None:
    # Comment-only branch body should still emit a ``pass`` so Ren'Py lints.
    src = _PREFIX + (
        "[[if a]]\n"
        "# just a comment\n"
        "[[/if]]\n"
    )

    scene = parse(src, path = "inline.scene")
    output = generate(scene, allowlists, _CTX)

    assert "if a:" in output or "if _scene_state.get('a'):" in output
    # A ``pass`` sits under the ``if``.
    assert "pass" in output
