"""Fail-closed Cycles proof renderer and pinned-Pillow finalizer."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))

from scripts.blender.pimm_production import blender_scene_validator
from scripts.blender.pimm_production import proof_contract as proof_module
from scripts.blender.pimm_production.contact_sheet import build_contact_sheet
from scripts.blender.pimm_production.io_contract import atomic_write_json, sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT as CANONICAL_ASSET_ROOT
from scripts.blender.pimm_production.paths import require_within
from scripts.blender.pimm_production.proof_contract import (
    ProofContract,
    analyze_mask_metrics,
    validate_proof_contract,
    write_proof_manifest,
)
from scripts.blender.pimm_production.scene_contract import SceneContract
from scripts.blender.pimm_production.tool_policy import validate_tool_lock


RESULT_MARKER = "PIMM_PROOF_RENDER_JSON="


def _fingerprint(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256_file(path),
    }


def _protected_paths(asset_root: Path, scene: SceneContract, scene_path: Path) -> dict[str, Path]:
    return {
        "source": asset_root / "sources" / f"PIMM-{scene.machine}-authoritative-source.step",
        "master": asset_root / Path(*PurePosixPath(scene.master_path).parts),
        "material_library": asset_root / Path(*PurePosixPath(scene.material_library_path).parts),
        "scene": scene_path,
    }


def _snapshot(paths: Mapping[str, Path]) -> dict[str, object]:
    missing = [f"{name}: {path}" for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ValueError("protected proof inputs are missing: " + "; ".join(missing))
    return {name: _fingerprint(path) for name, path in paths.items()}


def _validate_tools(lock_path: Path) -> tuple[dict[str, object], Path]:
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("free tool lock root must be an object")
    errors = validate_tool_lock(payload)
    tools = payload.get("tools")
    records = {
        str(item.get("id")): item
        for item in tools
        if isinstance(tools, list) and isinstance(item, Mapping)
    }
    for tool_id in ("blender", "python", "pillow"):
        record = records.get(tool_id)
        if not isinstance(record, Mapping):
            continue
        path = Path(str(record.get("path", "")))
        if not path.is_file():
            errors.append(f"{tool_id}: locked file is missing")
        elif sha256_file(path) != str(record.get("sha256", "")).upper():
            errors.append(f"{tool_id}: locked file SHA-256 mismatch")
    evidence = payload.get("license_evidence")
    mcp_evidence = evidence.get("blender-mcp") if isinstance(evidence, Mapping) else None
    if isinstance(mcp_evidence, Mapping):
        evidence_path = Path(str(mcp_evidence.get("path", "")))
        if not evidence_path.is_file():
            errors.append("blender-mcp: locked license evidence is missing")
        elif sha256_file(evidence_path) != str(mcp_evidence.get("sha256", "")).upper():
            errors.append("blender-mcp: locked license evidence SHA-256 mismatch")
    if errors:
        raise ValueError("free tool lock validation failed: " + "; ".join(errors))
    python_record = records["python"]
    return dict(payload), Path(str(python_record["path"])).resolve()


def _fixture_asset_root(path: Path) -> Path:
    import tempfile

    resolved = path.resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if resolved == temporary_root:
        raise ValueError("fixture asset root cannot equal the system temporary root")
    try:
        resolved.relative_to(temporary_root)
    except ValueError as error:
        raise ValueError("fixture asset root must be beneath the system temporary root") from error
    return resolved


def _project_named_shafts(bpy: Any, camera: object) -> dict[str, list[float]]:
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    scene = bpy.context.scene
    regions: dict[str, list[float]] = {}
    for obj in bpy.data.objects:
        if getattr(obj, "type", None) != "MESH" or "shaft" not in obj.name.lower():
            continue
        points = [
            world_to_camera_view(scene, camera, obj.matrix_world @ Vector(corner))
            for corner in obj.bound_box
        ]
        visible = [point for point in points if point.z > 0]
        if not visible:
            continue
        left = max(0.0, min(point.x for point in visible))
        right = min(1.0, max(point.x for point in visible))
        bottom = max(0.0, min(point.y for point in visible))
        top = min(1.0, max(point.y for point in visible))
        if right > left and top > bottom:
            regions[obj.name] = [left, 1.0 - top, right, 1.0 - bottom]
    return regions


def _proof_environment_errors(bpy: Any) -> list[str]:
    """Authorize only exact, named, temporary proof-environment meshes."""

    errors: list[str] = []
    allowed = {"shadow-catcher": "PIMM_ENV_SHADOW_CATCHER"}
    for obj in bpy.data.objects:
        if getattr(obj, "type", None) != "MESH" or getattr(obj, "library", None) is not None:
            continue
        role = obj.get("pimm_proof_environment_role")
        expected_name = allowed.get(role)
        mesh = getattr(obj, "data", None)
        if expected_name is None or obj.name != expected_name:
            errors.append(f"unauthorized local proof environment mesh object: {obj.name}")
            continue
        if mesh is None or mesh.name != expected_name or mesh.get("pimm_proof_environment_role") != role:
            errors.append(f"proof environment mesh role mismatch: {obj.name}")
        if obj.get("pimm_stable_id") is not None:
            errors.append(f"proof environment mesh cannot carry product identity: {obj.name}")
        if role == "shadow-catcher" and getattr(obj, "is_shadow_catcher", False) is not True:
            errors.append(f"proof shadow catcher role lacks Cycles shadow-catcher state: {obj.name}")
        for material in getattr(mesh, "materials", ()):
            if material is None:
                continue
            if (
                material.name != "PIMM_ENV_SHADOW_CATCHER_MATERIAL"
                or material.get("pimm_proof_environment_role") != role
                or material.get("pimm_material_scope") is not None
            ):
                errors.append(f"unauthorized proof environment material: {material.name}")
    return errors


def _frame_fixture_scene(bpy: Any, camera: object) -> tuple[list[object], list[object]]:
    from mathutils import Vector

    meshes = [obj for obj in bpy.data.objects if getattr(obj, "type", None) == "MESH"]
    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    if not points:
        raise ValueError("proof scene has no product mesh bounds")
    minimum = Vector(
        (
            min(point.x for point in points),
            min(point.y for point in points),
            min(point.z for point in points),
        )
    )
    maximum = Vector(
        (
            max(point.x for point in points),
            max(point.y for point in points),
            max(point.z for point in points),
        )
    )
    target = (minimum + maximum) * 0.5
    extent = max((maximum - minimum).length, 1.0)
    camera.location = target + Vector((2.6 * extent, -3.8 * extent, 3.2 * extent))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 52

    lights: list[object] = []
    for name, offset, energy, size in (
        ("PIMM_PROOF_KEY", (2.0, -2.5, 4.0), 900.0, 4.0),
        ("PIMM_PROOF_FILL", (-3.0, -1.0, 2.0), 500.0, 3.0),
    ):
        data = bpy.data.lights.new(name, type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(light)
        light.location = target + Vector(offset) * extent
        light.rotation_euler = (target - light.location).to_track_quat("-Z", "Y").to_euler()
        lights.append(light)
    catcher_mesh = bpy.data.meshes.new("PIMM_ENV_SHADOW_CATCHER")
    catcher_mesh["pimm_proof_environment_role"] = "shadow-catcher"
    size = extent * 5.0
    z = minimum.z - extent * 0.15
    catcher_mesh.from_pydata(
        [(-size, -size, z), (size, -size, z), (size, size, z), (-size, size, z)],
        [],
        [(0, 1, 2, 3)],
    )
    catcher_material = bpy.data.materials.new("PIMM_ENV_SHADOW_CATCHER_MATERIAL")
    catcher_material["pimm_proof_environment_role"] = "shadow-catcher"
    catcher_material.diffuse_color = (0.5, 0.5, 0.5, 1.0)
    catcher_mesh.materials.append(catcher_material)
    catcher = bpy.data.objects.new("PIMM_ENV_SHADOW_CATCHER", catcher_mesh)
    catcher["pimm_proof_environment_role"] = "shadow-catcher"
    catcher.is_shadow_catcher = True
    bpy.context.scene.collection.objects.link(catcher)
    environment_errors = _proof_environment_errors(bpy)
    if environment_errors:
        raise ValueError("; ".join(environment_errors))
    return lights, [catcher]


def _render_rgba(
    bpy: Any,
    contract: ProofContract,
    destination: Path,
) -> tuple[dict[str, object], list[object], list[object], Path | None]:
    scene = bpy.context.scene
    camera = scene.camera
    if camera is None:
        raise ValueError("proof scene has no active camera")
    lights, environment = _frame_fixture_scene(bpy, camera)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = contract.samples
    scene.cycles.use_denoising = contract.denoise
    scene.render.resolution_percentage = round(float(contract.resolution_percentage))
    if float(contract.resolution_percentage) == 12.5:
        # Blender's integer setting cannot represent 12.5%; preserve exact output dimensions.
        scene.render.resolution_percentage = 100
        scene.render.resolution_x = round(int(scene.render.resolution_x) * 0.125)
        scene.render.resolution_y = round(int(scene.render.resolution_y) * 0.125)
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.filepath = str(destination)
    scene.render.use_file_extension = True
    scene.view_settings.view_transform = "AgX"
    available_looks = {
        item.identifier
        for item in scene.view_settings.bl_rna.properties["look"].enum_items
    }
    for look in ("AgX - Medium High Contrast", "Medium High Contrast", "None"):
        if look in available_looks:
            scene.view_settings.look = look
            break
    started = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    elapsed = time.perf_counter() - started
    actual = destination if destination.is_file() else destination.with_suffix(".png")
    if actual != destination and actual.is_file():
        os.replace(actual, destination)
    if not destination.is_file():
        raise ValueError(f"Cycles did not create the contracted RGBA proof: {destination}")
    actual_dimensions = [
        round(scene.render.resolution_x * scene.render.resolution_percentage / 100),
        round(scene.render.resolution_y * scene.render.resolution_percentage / 100),
    ]
    product_rgba = destination.with_name(f".{destination.stem}.product-only.png")
    for obj in environment:
        obj.hide_render = True
    scene.render.filepath = str(product_rgba)
    bpy.ops.render.render(write_still=True)
    if not product_rgba.is_file():
        raise ValueError("Cycles did not create the product-only mask source")
    metadata = {
        "schema": "pimm-proof-render-metadata/v1",
        "engine": scene.render.engine,
        "device": scene.cycles.device,
        "samples": contract.samples,
        "resolution_percentage": contract.resolution_percentage,
        "actual_dimensions": actual_dimensions,
        "denoise": scene.cycles.use_denoising,
        "cycles": {
            "device": scene.cycles.device,
            "samples": scene.cycles.samples,
            "use_denoising": scene.cycles.use_denoising,
            "max_bounces": scene.cycles.max_bounces,
            "transparent_max_bounces": scene.cycles.transparent_max_bounces,
        },
        "agx": {
            "view_transform": scene.view_settings.view_transform,
            "look": scene.view_settings.look,
            "exposure": scene.view_settings.exposure,
            "gamma": scene.view_settings.gamma,
        },
        "blender_version": bpy.app.version_string,
        "render_seconds": round(elapsed, 6),
        "named_shaft_regions": _project_named_shafts(bpy, camera),
        "shadow_pass_available": True,
    }
    return metadata, lights, environment, product_rgba


def _save_png_once(image: object, path: Path, *, mode: str | None = None) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        target = image.convert(mode) if mode else image
        target.save(temporary, format="PNG")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def finalize_proof(
    proof_contract_path: Path,
    output_root: Path,
    rgba_path: Path,
    asset_root: Path,
    product_rgba_path: Path | None = None,
) -> dict[str, object]:
    """Create lossless composites/masks, quantitative manifest, and contact sheet."""

    from PIL import Image, ImageDraw

    proof_module.ASSET_ROOT = asset_root.resolve()
    contract = ProofContract.from_json(proof_contract_path)
    expected_root = (
        asset_root / Path(*PurePosixPath(contract.output_root).parts)
    ).resolve()
    if output_root.resolve() != expected_root:
        raise ValueError("finalizer output root does not match proof contract")
    with Image.open(rgba_path) as loaded:
        source = loaded.convert("RGBA")
        source.load()
    if source.getchannel("A").getextrema()[1] == 0:
        raise ValueError("proof RGBA contains no visible subject pixels")

    shot_id = SceneContract.from_json(output_root / "scene-contract.json").scene_id
    outputs = [rgba_path]
    for background in contract.backgrounds:
        if background == "white":
            backdrop = Image.new("RGBA", source.size, (255, 255, 255, 255))
        elif background == "dark":
            backdrop = Image.new("RGBA", source.size, (24, 26, 30, 255))
        else:
            backdrop = Image.new("RGBA", source.size, (224, 224, 224, 255))
            draw = ImageDraw.Draw(backdrop)
            tile = max(8, min(source.size) // 12)
            for top in range(0, source.height, tile):
                for left in range(0, source.width, tile):
                    if (left // tile + top // tile) % 2:
                        draw.rectangle(
                            (left, top, min(left + tile - 1, source.width - 1), min(top + tile - 1, source.height - 1)),
                            fill=(174, 177, 182, 255),
                        )
        composite = Image.alpha_composite(backdrop, source)
        destination = output_root / f"{shot_id}--{background}.png"
        _save_png_once(composite, destination)
        outputs.append(destination)
    if product_rgba_path is None or not product_rgba_path.is_file():
        raise ValueError("proof QA requires a product-only Cycles render")
    with Image.open(product_rgba_path) as loaded_product:
        product_alpha = loaded_product.convert("RGBA").getchannel("A")
        product_alpha.load()
    from PIL import ImageChops

    shadow_alpha = ImageChops.subtract(source.getchannel("A"), product_alpha).point(
        lambda value: value if value >= 16 else 0
    )
    metadata_path = output_root / "render-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["intended_subject_metrics"] = analyze_mask_metrics(product_alpha)
    metadata["physical_shadow_metrics"] = analyze_mask_metrics(shadow_alpha)
    atomic_write_json(metadata_path, metadata)
    if contract.object_masks:
        masks = {
            "object-mask": product_alpha,
            "material-mask": product_alpha,
            "shadow-mask": shadow_alpha,
        }
        for name, mask in masks.items():
            destination = output_root / f"{shot_id}--{name}.png"
            _save_png_once(mask, destination, mode="L")
            outputs.append(destination)
    product_rgba_path.unlink()

    manifest_path = write_proof_manifest(contract, outputs)
    contact_path = build_contact_sheet(manifest_path, output_root / "contact-sheet.png")
    return {
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "contact_sheet_path": str(contact_path),
        "contact_sheet_sha256": sha256_file(contact_path),
        "outputs": [str(path) for path in outputs],
    }


def _run_one(
    bpy: Any,
    proof_path: Path,
    asset_root: Path,
    tool_lock: Path,
) -> dict[str, object]:
    try:
        lock, pillow_python = _validate_tools(tool_lock)
        contract_bytes = proof_path.read_bytes()
        contract = ProofContract.from_mapping(json.loads(contract_bytes.decode("utf-8")))
        scene_contract_path = (
            asset_root / Path(*PurePosixPath(contract.scene_contract_path).parts)
        ).resolve()
        scene = SceneContract.from_json(scene_contract_path)
        proof_module.ASSET_ROOT = asset_root
        blender_scene_validator.ASSET_ROOT = asset_root
        contract_errors = validate_proof_contract(contract, scene)
        scene_errors = blender_scene_validator.validate_open_render_scene(
            bpy,
            scene,
            contract_snapshot_sha256=sha256_file(scene_contract_path),
        )
        if contract_errors or scene_errors:
            return {
                "status": "blocked_contract",
                "generation_id": contract.generation_id,
                "errors": contract_errors + scene_errors,
            }
        scene_path = Path(str(bpy.data.filepath)).resolve()
        if sha256_file(scene_path) != contract.scene_sha256.upper():
            return {
                "status": "blocked_scene_drift",
                "generation_id": contract.generation_id,
                "errors": ["open scene SHA-256 drifted from proof contract"],
            }
        paths = _protected_paths(asset_root, scene, scene_path)
        before = _snapshot(paths)
        output_root = (
            asset_root / Path(*PurePosixPath(contract.output_root).parts)
        ).resolve()
        require_within(output_root, asset_root / "renders" / "proofs")
        output_root.mkdir(parents=True, exist_ok=False)
        proof_snapshot = output_root / "proof-contract.json"
        scene_snapshot = output_root / "scene-contract.json"
        proof_snapshot.write_bytes(contract_bytes)
        scene_snapshot.write_bytes(scene_contract_path.read_bytes())

        scene_context = bpy.context.scene
        camera = scene_context.camera
        camera_location = camera.location.copy()
        camera_rotation = camera.rotation_euler.copy()
        camera_lens = camera.data.lens
        saved = {
            "engine": scene_context.render.engine,
            "resolution_x": scene_context.render.resolution_x,
            "resolution_y": scene_context.render.resolution_y,
            "resolution_percentage": scene_context.render.resolution_percentage,
            "film_transparent": scene_context.render.film_transparent,
            "filepath": scene_context.render.filepath,
            "file_format": scene_context.render.image_settings.file_format,
            "color_mode": scene_context.render.image_settings.color_mode,
            "color_depth": scene_context.render.image_settings.color_depth,
            "view_transform": scene_context.view_settings.view_transform,
            "look": scene_context.view_settings.look,
        }
        lights: list[object] = []
        environment: list[object] = []
        product_rgba_path: Path | None = None
        try:
            rgba_path = output_root / f"{scene.scene_id}--rgba.png"
            metadata, lights, environment, product_rgba_path = _render_rgba(
                bpy, contract, rgba_path
            )
        finally:
            for obj in environment:
                mesh = obj.data
                materials = list(mesh.materials)
                bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.meshes.remove(mesh)
                for material in materials:
                    if material.users == 0:
                        bpy.data.materials.remove(material)
            for light in lights:
                data = light.data
                bpy.data.objects.remove(light, do_unlink=True)
                bpy.data.lights.remove(data)
            camera.location = camera_location
            camera.rotation_euler = camera_rotation
            camera.data.lens = camera_lens
            scene_context.render.engine = saved["engine"]
            scene_context.render.resolution_x = saved["resolution_x"]
            scene_context.render.resolution_y = saved["resolution_y"]
            scene_context.render.resolution_percentage = saved["resolution_percentage"]
            scene_context.render.film_transparent = saved["film_transparent"]
            scene_context.render.filepath = saved["filepath"]
            scene_context.render.image_settings.file_format = saved["file_format"]
            scene_context.render.image_settings.color_mode = saved["color_mode"]
            scene_context.render.image_settings.color_depth = saved["color_depth"]
            scene_context.view_settings.view_transform = saved["view_transform"]
            scene_context.view_settings.look = saved["look"]
        after_render = _snapshot(paths)
        if before != after_render:
            return {
                "status": "blocked_fingerprint_drift",
                "generation_id": contract.generation_id,
                "errors": ["source/master/material/scene fingerprints changed during render"],
            }
        metadata.update(
            {
                "proof_contract_sha256": sha256_file(proof_snapshot),
                "scene_contract_sha256": sha256_file(scene_snapshot),
                "tool_lock_sha256": sha256_file(tool_lock),
                "tool_lock": lock,
                "fingerprints": {"before": before, "after": after_render},
            }
        )
        atomic_write_json(output_root / "render-metadata.json", metadata)
        finalizer = subprocess.run(
            [
                str(pillow_python),
                "-m",
                "scripts.blender.pimm_production.blender_proof_render",
                "--finalize",
                "--proof-contract",
                str(proof_snapshot),
                "--asset-root",
                str(asset_root),
                "--output-root",
                str(output_root),
                "--rgba",
                str(rgba_path),
                *(
                    ["--product-rgba", str(product_rgba_path)]
                    if product_rgba_path is not None
                    else []
                ),
            ],
            cwd=Path(__file__).resolve().parents[3],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if finalizer.returncode:
            return {
                "status": "failed_finalize",
                "generation_id": contract.generation_id,
                "errors": [finalizer.stderr.strip() or finalizer.stdout.strip()],
            }
        after_finalize = _snapshot(paths)
        if before != after_finalize:
            return {
                "status": "blocked_fingerprint_drift",
                "generation_id": contract.generation_id,
                "errors": ["source/master/material/scene fingerprints changed during proof finalization"],
            }
        manifest_path = output_root / "manifest.json"
        contact_path = output_root / "contact-sheet.png"
        return {
            "status": "pass",
            "generation_id": contract.generation_id,
            "output_root": str(output_root),
            "manifest_sha256": sha256_file(manifest_path),
            "contact_sheet_sha256": sha256_file(contact_path),
            "fingerprints_unchanged": True,
        }
    except Exception as error:  # Fail closed and stop the batch after one emitted result.
        return {
            "status": "failed",
            "generation_id": getattr(locals().get("contract"), "generation_id", None),
            "errors": [f"{type(error).__name__}: {error}"],
        }


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--proof-contract", type=Path, action="append", required=True)
    parser.add_argument("--fixture-asset-root", type=Path)
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument("--tool-lock", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--rgba", type=Path)
    parser.add_argument("--product-rgba", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(
        list(argv)
        if argv is not None
        else sys.argv[sys.argv.index("--") + 1 :]
        if "--" in sys.argv
        else sys.argv[1:]
    )
    if arguments.finalize:
        if len(arguments.proof_contract) != 1 or not all(
            (arguments.asset_root, arguments.output_root, arguments.rgba)
        ):
            raise ValueError("finalizer requires one contract, asset root, output root, and RGBA")
        result = finalize_proof(
            arguments.proof_contract[0],
            arguments.output_root,
            arguments.rgba,
            arguments.asset_root,
            arguments.product_rgba,
        )
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0

    import bpy

    if arguments.fixture_asset_root is not None:
        asset_root = _fixture_asset_root(arguments.fixture_asset_root)
    else:
        asset_root = CANONICAL_ASSET_ROOT.resolve()
    tool_lock = arguments.tool_lock or asset_root / "manifests" / "free-tools-lock.json"
    exit_code = 0
    for proof_path in arguments.proof_contract:
        result = _run_one(bpy, proof_path.resolve(), asset_root, tool_lock.resolve())
        print(RESULT_MARKER + json.dumps(result, sort_keys=True), flush=True)
        if result["status"] != "pass":
            exit_code = 1
            break
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
