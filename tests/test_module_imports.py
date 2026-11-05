"""Functions the game keeps out of its default store, and names it retired.

A compiled scene runs in TNH's default store. Since 0.9c.beta.28 the game
holds most of its code in Python modules and binds only some names into that
store (``game/definitions/core.rpy``); a function such as
``core.time.get_time_since`` exists but is not one of them, so a scene calling
it by name raises ``NameError`` in play while compiling cleanly. An allowlist
entry names its ``module``, and the compiled file imports it, the way the
game's own ``.rpy`` files do.

The same update removed or renamed names a scene may still use; the
``retired`` mapping turns each into an error that says what replaced it,
instead of a near-miss spelling suggestion.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import require_base_allowlists
from tnh_scene_compiler.allowlists import Allowlists
from tnh_scene_compiler.codegen import CodegenContext, generate
from tnh_scene_compiler.parser import parse
from tnh_scene_compiler.validator import validate

_HEAD = (
    "Title: T\nScene Id: s\nCharacter: JeanGrey\n"
    "Scene Type: cinematic\nTrigger: manual\n\n"
)
_CTX = CodegenContext(project_prefix = "testmod")


def _allow(**overrides) -> Allowlists:
    fields = dict(
        characters = ["JeanGrey", "Rogue", "Player"],
        characters_upper = {"JEANGREY", "ROGUE", "PLAYER"},
        condition_functions = {"get_time_since", "chance_of_repeat", "is_close_by"},
        condition_function_signatures = {
            "get_time_since": "get_time_since(date: tuple[int, int]) -> int",
            "chance_of_repeat": "chance_of_repeat(History, item: str) -> float",
            "is_close_by": "is_close_by(Character) -> bool",
        },
        run_operations = {"needs_to_change", "reset_mood"},
        function_modules = {
            "get_time_since": "core.time",
            "chance_of_repeat": "core.base",
            "reset_mood": "core.behavior",
        },
    )
    fields.update(overrides)
    return Allowlists(**fields)


def _compile(body: str, allow: Allowlists) -> str:
    scene = parse(_HEAD + body, path = "inline.scene")
    assert validate(scene, allow) == []
    return generate(scene, allow, _CTX)


def _import_lines(output: str) -> list[str]:
    lines = output.splitlines()
    start = lines.index("init python:")
    block = []
    for line in lines[start + 1:]:
        if not line.startswith("    from "):
            break
        block.append(line.strip())
    return block


# -- Codegen -----------------------------------------------------------------


def test_a_condition_calling_a_module_function_imports_it_before_the_label() -> None:
    output = _compile(
        "[[if get_time_since((5, 2)) >= 4]]\nLine.\n[[/if]]\n", _allow(),
    )

    assert _import_lines(output) == ["from core.time import get_time_since"]
    assert output.index("from core.time import get_time_since") < output.index("label s:")


def test_one_line_per_module_in_sorted_order() -> None:
    output = _compile(
        '[[if chance_of_repeat(JeanGrey.History, "kissed") >= 0.5 '
        "and get_time_since((5, 2)) >= 4]]\nLine.\n[[/if]]\n",
        _allow(),
    )

    assert _import_lines(output) == [
        "from core.base import chance_of_repeat",
        "from core.time import get_time_since",
    ]


def test_names_from_one_module_share_a_line() -> None:
    allow = _allow(function_modules = {
        "get_time_since": "core.time", "chance_of_repeat": "core.time",
    })
    output = _compile(
        '[[if chance_of_repeat(JeanGrey.History, "kissed") >= 0.5 '
        "or get_time_since((5, 2)) >= 4]]\nLine.\n[[/if]]\n",
        allow,
    )

    assert _import_lines(output) == ["from core.time import chance_of_repeat, get_time_since"]


def test_a_nested_branch_and_a_choice_condition_count() -> None:
    output = _compile(
        "[[if JeanGrey.nearby]]\n"
        "[[if get_time_since((5, 2)) >= 4]]\nLine.\n[[/if]]\n"
        "[[/if]]\n"
        "[[choice]]\n"
        '= Ask [[if chance_of_repeat(JeanGrey.History, "kissed") >= 0.5]]\n'
        "    Body.\n"
        "[[/choice]]\n",
        _allow(),
    )

    assert _import_lines(output) == [
        "from core.base import chance_of_repeat",
        "from core.time import get_time_since",
    ]


def test_a_run_operation_and_a_call_inside_its_arguments_are_imported() -> None:
    output = _compile(
        "[[run reset_mood(JeanGrey)]]\n"
        "[[run needs_to_change([JeanGrey], get_time_since((5, 2)))]]\n",
        _allow(),
    )

    assert _import_lines(output) == [
        "from core.behavior import reset_mood",
        "from core.time import get_time_since",
    ]


def test_a_value_said_in_a_line_is_imported_too() -> None:
    # `[fn(...)]` in dialogue, narration or a choice option draws from the
    # same allowlist as [[if]], so it needs the same import.
    output = _compile(
        "JEANGREY\nIt has been [get_time_since((5, 2))] periods.\n\n"
        'The odds are [chance_of_repeat(JeanGrey.History, "kissed")].\n',
        _allow(interpolation = {"JeanGrey.name"}),
    )

    assert _import_lines(output) == [
        "from core.base import chance_of_repeat",
        "from core.time import get_time_since",
    ]


def test_a_value_said_in_a_choice_option_is_imported() -> None:
    output = _compile(
        "[[choice]]\n"
        "= Wait [get_time_since((5, 2))] periods\n"
        "    Body.\n"
        "[[/choice]]\n",
        _allow(),
    )

    assert _import_lines(output) == ["from core.time import get_time_since"]


def test_a_scene_calling_only_store_functions_has_no_import_block() -> None:
    output = _compile("[[if is_close_by(JeanGrey)]]\nLine.\n[[/if]]\n", _allow())

    # The testing-hub metadata block is the only init python block left.
    assert output.count("init python:") == 1
    assert " import " not in output


# -- Loading -----------------------------------------------------------------


def test_module_and_retired_keys_load_from_both_files(tmp_path: Path) -> None:
    (tmp_path / "condition_functions.yaml").write_text(
        "functions:\n"
        "  - name: get_time_since\n"
        "    module: core.time\n"
        "  - name: is_close_by\n"
        "  - name: bad_module\n"
        "    module: \"core.time; import os\"\n"
        "retired:\n"
        "  get_Location: \"Use Player.Location.\"\n",
        encoding = "utf-8",
    )
    (tmp_path / "run_operations.yaml").write_text(
        "operations:\n  - name: reset_mood\n    module: core.behavior\n",
        encoding = "utf-8",
    )
    (tmp_path / "character_methods.yaml").write_text(
        "methods:\n  - name: get_default_mood\n"
        "retired:\n  default_mood: \"Renamed get_default_mood.\"\n",
        encoding = "utf-8",
    )

    allow = Allowlists.load(tmp_path)

    # Not a dotted identifier: never spliced into an import line.
    assert allow.function_modules == {"get_time_since": "core.time", "reset_mood": "core.behavior"}
    assert allow.retired_condition_functions == {"get_Location": "Use Player.Location."}
    assert allow.retired_character_methods == {"default_mood": "Renamed get_default_mood."}


def test_the_project_layer_wins_on_a_module() -> None:
    base = Allowlists(function_modules = {"f": "core.time", "g": "core.base"})
    project = Allowlists(function_modules = {"f": "my_project.helpers"})

    assert base.merge(project).function_modules == {"f": "my_project.helpers", "g": "core.base"}


# -- Retired names -----------------------------------------------------------


@pytest.fixture(scope = "module")
def base_allow() -> Allowlists:
    return Allowlists.load(require_base_allowlists())


def _errors(body: str, allow: Allowlists):
    return validate(parse(_HEAD + body, path = "inline.scene"), allow)


def test_a_retired_condition_function_says_what_replaced_it(base_allow: Allowlists) -> None:
    errors = _errors("[[if are_Characters_friends([JeanGrey, Rogue])]]\nOk.\n[[/if]]\n", base_allow)

    assert [e.message for e in errors] == [
        "Condition function 'are_Characters_friends' no longer exists in the game.",
    ]
    assert "are_friends" in errors[0].hint


def test_a_retired_character_method_says_what_replaced_it(base_allow: Allowlists) -> None:
    errors = _errors('[[if JeanGrey.feature_enabled("date")]]\nOk.\n[[/if]]\n', base_allow)

    assert [e.message for e in errors] == [
        "Character method 'feature_enabled' no longer exists in the game.",
    ]
    assert "is_feature_enabled" in errors[0].hint


def test_a_retired_function_inside_a_run_argument_is_refused(base_allow: Allowlists) -> None:
    # The operation is registered, so only its argument can be wrong — and
    # nothing else reads a [[run]] argument before the game does.
    errors = _errors(
        "[[run needs_to_change(get_present_Characters(get_Location()))]]\n", base_allow,
    )

    assert sorted(e.message for e in errors) == [
        "Function 'get_Location' no longer exists in the game.",
        "Function 'get_present_Characters' no longer exists in the game.",
    ]
    assert any("Player.Location.Present" in (e.hint or "") for e in errors)


def test_a_project_function_under_a_retired_name_still_compiles(base_allow: Allowlists) -> None:
    project = Allowlists(
        condition_functions = {"get_Location"},
        condition_function_signatures = {"get_Location": "get_Location() -> Location"},
    )
    allow = base_allow.merge(project)

    assert _errors("[[if get_Location()]]\nOk.\n[[/if]]\n", allow) == []
    assert _errors("[[run needs_to_change([JeanGrey], get_Location())]]\n", allow) == []


# -- The shipped base layer --------------------------------------------------


def test_every_module_held_base_function_compiles_with_its_import(base_allow: Allowlists) -> None:
    held = {
        name: module for name, module in base_allow.function_modules.items()
        if name in base_allow.condition_functions
    }
    assert held, "allowlists_base declares no module-held condition function"
    for name, module in sorted(held.items()):
        # Arity is checked, so give each one the arguments its signature needs.
        arguments = {
            "get_time_since": "(5, 2)",
            "chance_of_repeat": 'JeanGrey.History, "kissed_player"',
            "get_max_friendship": "JeanGrey, Rogue",
        }[name]
        output = generate(
            parse(_HEAD + f"[[if {name}({arguments})]]\nOk.\n[[/if]]\n", path = "inline.scene"),
            base_allow, _CTX,
        )
        assert f"    from {module} import {name}" in output.splitlines()
