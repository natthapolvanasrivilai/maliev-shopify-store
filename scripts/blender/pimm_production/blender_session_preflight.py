"""Read-only Blender session preflight for PIMM production governance."""

from __future__ import annotations

import json
import sys
from typing import Any


MUTATION_FLAGS = frozenset(
    {"--render", "--render-anim", "--save", "--save-as", "--python-expr", "--python-text"}
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


def _script_arguments(argv: list[str]) -> list[str]:
    return argv[argv.index("--") + 1 :] if "--" in argv else []


def main(argv: list[str] | None = None) -> int:
    """Print session evidence and reject any script-level mutation request."""

    arguments = _script_arguments(list(sys.argv if argv is None else argv))
    forbidden = sorted(set(arguments).intersection(MUTATION_FLAGS))
    if forbidden:
        raise SystemExit(f"read-only preflight rejects mutation flags: {', '.join(forbidden)}")
    if arguments:
        raise SystemExit(f"read-only preflight rejects unknown arguments: {' '.join(arguments)}")
    import bpy

    print(json.dumps(inspect_open_session(bpy), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
