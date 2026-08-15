"""Read-only Blender session preflight for PIMM production governance."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


MUTATION_FLAGS = frozenset(
    {
        "-a",
        "-f",
        "--render",
        "--render-anim",
        "--render-frame",
        "--save",
        "--save-as",
        "--save-as-mainfile",
        "--save-mainfile",
        "--python",
        "--python-expr",
        "--python-text",
        "--python-console",
    }
)
APPROVED_PREFLIGHT_PATH = Path(__file__).resolve()


def inspect_open_session(bpy: Any) -> dict[str, object]:
    """Serialize only current Blender session state; never change it."""

    scene = bpy.context.scene
    return {
        "filepath": bpy.data.filepath,
        "dirty": bpy.data.is_dirty,
        "scene": scene.name,
        "view_layer": bpy.context.view_layer.name,
        "unit_system": scene.unit_settings.system,
        "length_unit": scene.unit_settings.length_unit,
        "scale_length": scene.unit_settings.scale_length,
        "selected_objects": sorted(obj.name for obj in bpy.context.selected_objects),
        "active_object": bpy.context.view_layer.objects.active.name
        if bpy.context.view_layer.objects.active
        else None,
        "libraries": sorted(library.filepath for library in bpy.data.libraries),
    }


def _mutation_arguments(argv: list[str]) -> list[str]:
    """Find render/save/code-execution flags anywhere in Blender's command line."""

    forbidden: list[str] = []
    for argument in argv[1:]:
        option = argument.split("=", 1)[0]
        if option in MUTATION_FLAGS or (option.startswith("-f") and option != "--factory-startup"):
            forbidden.append(option)
    return sorted(set(forbidden))


def _script_arguments(argv: list[str]) -> list[str]:
    return argv[argv.index("--") + 1 :] if "--" in argv else []


def _preflight_script_errors(argv: list[str]) -> list[str]:
    """Require exactly one canonical ``-P`` reference to this checked-in script."""

    script_positions = [index for index, argument in enumerate(argv[1:], start=1) if argument == "-P"]
    malformed = [argument for argument in argv[1:] if argument.startswith("-P") and argument != "-P"]
    errors: list[str] = []
    if malformed:
        errors.append("read-only preflight rejects malformed -P invocation")
    if not script_positions:
        errors.append("read-only preflight requires exactly one -P invocation")
        return errors
    if len(script_positions) != 1:
        errors.append("read-only preflight requires exactly one -P invocation")
        return errors
    script_position = script_positions[0]
    if script_position + 1 >= len(argv) or argv[script_position + 1].startswith("-"):
        errors.append("read-only preflight -P is missing script path")
        return errors
    if argv[script_position + 1] != str(APPROVED_PREFLIGHT_PATH):
        errors.append("read-only preflight -P must reference the canonical approved checked-in script")
    return errors


def validate_invocation(argv: list[str]) -> list[str]:
    """Return any mutation or non-canonical checked-in-script invocation errors."""

    forbidden = _mutation_arguments(argv)
    errors = [f"read-only preflight rejects mutation flags: {', '.join(forbidden)}"] if forbidden else []
    errors.extend(_preflight_script_errors(argv))
    arguments = _script_arguments(argv)
    if arguments:
        errors.append(f"read-only preflight rejects unknown arguments: {' '.join(arguments)}")
    return errors


def main(argv: list[str] | None = None) -> int:
    """Print session evidence and reject any script-level mutation request."""

    effective_argv = list(sys.argv if argv is None else argv)
    errors = validate_invocation(effective_argv)
    if errors:
        raise SystemExit("\n".join(errors))
    import bpy

    print(json.dumps(inspect_open_session(bpy), sort_keys=True))
    return 0


if __name__ == "__main__":
    main()
