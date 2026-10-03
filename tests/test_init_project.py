"""Project bootstrap: ``init`` and the app's Create project write a usable project.

Both paths read ``templates/*.tmpl`` and substitute ``{{project_prefix}}``. The
templates said ``{{mod_prefix}}`` from 0.1.0 until 0.2.1, so every generated
runtime stub kept the raw placeholder — ``{{mod_prefix}}_scene_metadata = {}``
is not valid Python — and the CLI never got that far, crashing on its own
option name.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tnh_scene_compiler.__main__ import main
from tnh_scene_compiler.config import config_filename, get_data_root, load_config

# A ``{{name}}`` placeholder as the generators look for it.
_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _templates() -> list[Path]:
    """Return every runtime-stub template ``init`` and Create project read."""
    templates = sorted((get_data_root() / "templates").glob("*.tmpl"))
    assert templates, "templates/*.tmpl is missing: there is nothing to generate stubs from"
    return templates


def test_templates_use_only_the_placeholder_the_generators_substitute() -> None:
    # The GUI's Create project (gui.py) runs the same single substitution as
    # `init`, so this is the guard for both: any other placeholder ships raw.
    for template in _templates():
        names = set(_PLACEHOLDER.findall(template.read_text(encoding = "utf-8")))
        assert names == {"project_prefix"}, f"{template.name}: {sorted(names)}"


@pytest.mark.parametrize("option", ["--project-prefix", "--mod-prefix"])
def test_init_writes_a_project_that_loads(tmp_path: Path, option: str) -> None:
    # `--mod-prefix` is the former spelling of the option, kept as an alias.
    assert main(["init", option, "my_mod", "--output-dir", str(tmp_path)]) == 0

    config = load_config(tmp_path / config_filename("my_mod"))
    assert config.project_prefix == "my_mod"

    for template in _templates():
        stub = (tmp_path / template.stem).read_text(encoding = "utf-8")
        assert "{{" not in stub, f"{template.stem} kept a raw placeholder"
        assert "my_mod_" in stub, f"{template.stem} never received the prefix"
