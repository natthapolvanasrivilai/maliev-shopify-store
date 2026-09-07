"""Initialize editable PIMM part labels from their original CAD names.

Run this in a background Blender process with a PIMM master opened. By
default only blank labels are initialized, preserving any names the owner has
already edited manually. ``--force`` is available for a deliberate reset.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import bpy


def blender_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(blender_args())


def sync_open_master(*, force: bool = False) -> dict[str, int | str]:
    products = sorted(
        (obj for obj in bpy.data.objects if obj.get("pimm_stable_id")),
        key=lambda obj: str(obj.get("pimm_stable_id")),
    )
    if not products:
        raise RuntimeError("no PIMM product objects found in the opened master")

    machine = str(products[0].get("pimm_machine", "")).upper()
    if machine not in {"30G", "50G"}:
        raise RuntimeError(f"unsupported PIMM machine: {machine!r}")

    changed = 0
    preserved = 0
    for obj in products:
        original = str(obj.get("pimm_original_cad_name", ""))
        if not original.strip():
            raise RuntimeError(f"{obj.name} has no original CAD name")
        raw_current = str(obj.get("pimm_part_name", ""))
        current = raw_current.strip()
        if current and not force and current != original.strip():
            preserved += 1
            continue
        if raw_current != original:
            obj["pimm_part_name"] = original
            changed += 1

    remaining_blank = sum(
        not str(obj.get("pimm_part_name", "")).strip() for obj in products
    )
    if remaining_blank:
        raise RuntimeError(f"{remaining_blank} product labels remain blank")

    return {
        "machine": machine,
        "objects": len(products),
        "changed": changed,
        "preserved": preserved,
        "remaining_blank": remaining_blank,
    }


def main() -> None:
    args = parse_args()
    result = sync_open_master(force=args.force)
    master_path = Path(bpy.data.filepath).resolve()
    if not master_path.name:
        raise RuntimeError("opened master has no filepath")
    temporary = master_path.with_name(master_path.stem + ".part-name.tmp.blend")
    if temporary.exists():
        temporary.unlink()
    bpy.ops.wm.save_as_mainfile(filepath=str(temporary), check_existing=False)
    os.replace(temporary, master_path)
    print(
        "PIMM_PART_NAME_SYNC "
        f"machine={result['machine']} objects={result['objects']} "
        f"changed={result['changed']} preserved={result['preserved']} "
        f"remaining_blank={result['remaining_blank']} path={master_path}"
    )


if __name__ == "__main__":
    main()
