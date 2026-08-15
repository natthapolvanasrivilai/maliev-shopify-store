"""Read-only Blender session preflight for PIMM production governance."""

from __future__ import annotations

import json
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


def main(argv: list[str] | None = None) -> int:
    """Print session evidence and reject any script-level mutation request."""

    effective_argv = list(sys.argv if argv is None else argv)
    forbidden = _mutation_arguments(effective_argv)
    if forbidden:
        raise SystemExit(f"read-only preflight rejects mutation flags: {', '.join(forbidden)}")
    arguments = _script_arguments(effective_argv)
    if arguments:
        raise SystemExit(f"read-only preflight rejects unknown arguments: {' '.join(arguments)}")
    import bpy

    print(json.dumps(inspect_open_session(bpy), sort_keys=True))
    return 0


if __name__ == "__main__":
    main()
