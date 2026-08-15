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
    effective_dimensions,
    validate_proof_contract,
    write_proof_manifest,
)
from scripts.blender.pimm_production.scene_contract import SceneContract
from scripts.blender.pimm_production.tool_policy import validate_tool_lock


RESULT_MARKER = "PIMM_PROOF_RENDER_JSON="
_PENDING_TO_PUBLISHED = {
    ".contact-sheet.pending.png": "contact-sheet.png",
    ".contact-sheet.pending.json": "contact-sheet.json",
    ".manifest.pending.json": "manifest.json",
}


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


def _validate_executing_blender(
    bpy: Any, lock: Mapping[str, object]
) -> dict[str, str]:
    """Prove the process itself is the exact Blender executable in the lock."""

    tools = lock.get("tools")
    records = [
        item
        for item in (tools if isinstance(tools, list) else [])
        if isinstance(item, Mapping)
        and item.get("id") == "blender"
    ]
    if len(records) != 1:
        raise ValueError("free tool lock must contain exactly one Blender record")
    record = records[0]
    locked = Path(str(record.get("path", ""))).resolve()
    executing = Path(str(bpy.app.binary_path)).resolve()
    if executing != locked:
        raise ValueError(
            f"executing Blender path does not match lock: {executing} != {locked}"
        )
    locked_hash = str(record.get("sha256", "")).upper()
    actual_hash = sha256_file(executing)
    if actual_hash != locked_hash:
        raise ValueError("executing Blender SHA-256 does not match lock")
    version = str(record.get("version", ""))
    if not version or not str(bpy.app.version_string).startswith(version):
        raise ValueError("executing Blender version does not match lock")
    return {
        "binary_path": str(executing),
        "binary_sha256": actual_hash,
        "version": version,
    }


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


def _prepare_render_environment(
    bpy: Any, camera: object, *, fixture_mode: bool
) -> tuple[list[object], list[object]]:
    """Add synthetic framing and environment only in explicit fixture mode."""

    if fixture_mode:
        return _frame_fixture_scene(bpy, camera)
    fixture_roles = [
        obj.name
        for obj in bpy.data.objects
        if getattr(obj, "library", None) is None
        and getattr(obj, "type", None) == "MESH"
        and obj.get("pimm_proof_environment_role") is not None
    ]
    if fixture_roles:
        raise ValueError(
            "canonical proof contains fixture-only environment roles: "
            + ", ".join(sorted(fixture_roles))
        )
    return [], []


def _capture_authored_settings(bpy: Any) -> dict[str, object]:
    """Capture authored camera, lights, world, and compositor without mutation."""

    scene = bpy.context.scene
    camera = scene.camera
    camera_record: dict[str, object] | None = None
    if camera is not None:
        camera_record = {
            "name": camera.name,
            "location": [float(value) for value in camera.location],
            "rotation_euler": [float(value) for value in camera.rotation_euler],
            "lens": float(camera.data.lens),
        }
    lights = sorted(
        (
            {
                "name": obj.name,
                "type": obj.data.type,
                "energy": float(obj.data.energy),
                "location": [float(value) for value in obj.location],
                "rotation_euler": [float(value) for value in obj.rotation_euler],
            }
            for obj in bpy.data.objects
            if getattr(obj, "type", None) == "LIGHT"
        ),
        key=lambda item: str(item["name"]),
    )
    world = scene.world
    world_record = None
    if world is not None:
        world_record = {
            "name": world.name,
            "use_nodes": bool(world.use_nodes),
            "color": [float(value) for value in world.color],
        }
    tree = getattr(scene, "node_tree", None) if scene.use_nodes else None
    compositor = {
        "use_nodes": bool(scene.use_nodes),
        "nodes": sorted(node.name for node in tree.nodes) if tree else [],
        "links": sorted(
            f"{link.from_node.name}:{link.from_socket.name}->{link.to_node.name}:{link.to_socket.name}"
            for link in tree.links
        )
        if tree
        else [],
    }
    return {
        "camera": camera_record,
        "lights": lights,
        "world": world_record,
        "compositor": compositor,
    }


def _expected_product_rgba_path(output_root: Path, shot_id: str) -> Path:
    return output_root / f".{shot_id}--product-only.tmp.png"


def _validate_product_rgba_path(
    output_root: Path, shot_id: str, product_rgba_path: Path
) -> Path:
    """Allow cleanup of only the exact hidden file created for this generation."""

    output_root = Path(output_root)
    supplied = Path(product_rgba_path)
    expected = _expected_product_rgba_path(output_root, shot_id)
    contracted = {
        output_root / "manifest.json",
        output_root / "contact-sheet.png",
        output_root / "contact-sheet.json",
        output_root / "render-metadata.json",
        output_root / "proof-contract.json",
        output_root / "scene-contract.json",
    }
    if (
        not supplied.is_absolute()
        or supplied != expected
        or expected in contracted
        or output_root.is_symlink()
        or supplied.is_symlink()
    ):
        raise ValueError("product-only temporary path is not the exact contained generation file")
    try:
        resolved_root = output_root.resolve(strict=True)
        resolved = supplied.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, ValueError) as error:
        raise ValueError("product-only temporary path is not a readable contained file") from error
    if (
        resolved != expected.resolve()
        or not resolved.is_file()
        or resolved.stat().st_nlink != 1
    ):
        raise ValueError("product-only temporary path is not the exact readable generation file")
    return resolved


def _render_rgba(
    bpy: Any,
    contract: ProofContract,
    destination: Path,
    *,
    fixture_mode: bool,
) -> tuple[dict[str, object], list[object], list[object], Path | None]:
    scene = bpy.context.scene
    camera = scene.camera
    if camera is None:
        raise ValueError("proof scene has no active camera")
    lights, environment = _prepare_render_environment(
        bpy, camera, fixture_mode=fixture_mode
    )
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = contract.samples
    scene.cycles.use_denoising = contract.denoise
    width, height = effective_dimensions(
        SceneContract.from_json(destination.parent / "scene-contract.json"),
        contract.resolution_percentage,
    )
    scene.render.resolution_percentage = 100
    scene.render.resolution_x = width
    scene.render.resolution_y = height
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
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    started = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    elapsed = time.perf_counter() - started
    actual = destination if destination.is_file() else destination.with_suffix(".png")
    if actual != destination and actual.is_file():
        os.replace(actual, destination)
    if not destination.is_file():
        raise ValueError(f"Cycles did not create the contracted RGBA proof: {destination}")
    actual_dimensions = [width, height]
    product_rgba = None
    if fixture_mode:
        product_rgba = _expected_product_rgba_path(destination.parent, destination.stem.removesuffix("--rgba"))
        for obj in environment:
            obj.hide_render = True
        scene.render.filepath = str(product_rgba)
        bpy.ops.render.render(write_still=True)
        if not product_rgba.is_file():
            raise ValueError("Cycles did not create the product-only mask source")
    elif contract.object_masks:
        raise ValueError("canonical object masks require authored passes; fixture-only product render is forbidden")
    metadata = {
        "schema": "pimm-proof-render-metadata/v1",
        "engine": scene.render.engine,
        "device": scene.cycles.device,
        "samples": contract.samples,
        "resolution_percentage": contract.resolution_percentage,
        "base_dimensions": [
            SceneContract.from_json(destination.parent / "scene-contract.json").output_contract["width"],
            SceneContract.from_json(destination.parent / "scene-contract.json").output_contract["height"],
        ],
        "actual_dimensions": actual_dimensions,
        "image_settings": {
            "film_transparent": scene.render.film_transparent,
            "file_format": scene.render.image_settings.file_format,
            "color_mode": scene.render.image_settings.color_mode,
            "color_depth": scene.render.image_settings.color_depth,
            "use_file_extension": scene.render.use_file_extension,
        },
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
        "render_seconds": round(elapsed, 6),
        "named_shaft_regions": _project_named_shafts(bpy, camera),
        "shadow_pass_available": fixture_mode,
        "fixture_mode": fixture_mode,
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
    scene_contract = SceneContract.from_json(output_root / "scene-contract.json")
    shot_id = scene_contract.scene_id
    expected_rgba = output_root / f"{shot_id}--rgba.png"
    if not rgba_path.is_absolute() or rgba_path != expected_rgba or rgba_path.is_symlink():
        raise ValueError("RGBA path is not the exact contracted generation output")
    metadata_path = output_root / "render-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    fixture_mode = metadata.get("fixture_mode") is True
    validated_product = None
    if product_rgba_path is not None:
        if not fixture_mode:
            raise ValueError("product-only temporary path is fixture-only")
        validated_product = _validate_product_rgba_path(
            output_root, shot_id, product_rgba_path
        )
    elif fixture_mode:
        raise ValueError("fixture proof QA requires the exact product-only temporary path")
    with Image.open(rgba_path) as loaded:
        source = loaded.convert("RGBA")
        source.load()
    if source.getchannel("A").getextrema()[1] == 0:
        raise ValueError("proof RGBA contains no visible subject pixels")

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
    if validated_product is not None:
        with Image.open(validated_product) as loaded_product:
            product_alpha = loaded_product.convert("RGBA").getchannel("A")
            product_alpha.load()
        from PIL import ImageChops

        shadow_alpha = ImageChops.subtract(source.getchannel("A"), product_alpha).point(
            lambda value: value if value >= 16 else 0
        )
    else:
        product_alpha = source.getchannel("A")
        shadow_alpha = Image.new("L", source.size, 0)
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
    if validated_product is not None:
        validated_product.unlink()

    manifest_path = write_proof_manifest(
        contract, outputs, destination=output_root / ".manifest.pending.json"
    )
    contact_path = build_contact_sheet(
        manifest_path,
        output_root / ".contact-sheet.pending.png",
        evidence_path=output_root / ".contact-sheet.pending.json",
        published_manifest_name="manifest.json",
        published_output_name="contact-sheet.png",
    )
    return {
        "manifest_pending_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "contact_sheet_pending_path": str(contact_path),
        "contact_sheet_sha256": sha256_file(contact_path),
        "outputs": [str(path) for path in outputs],
    }


def _pending_artifact_paths(output_root: Path) -> dict[Path, Path]:
    return {
        output_root / pending: output_root / published
        for pending, published in _PENDING_TO_PUBLISHED.items()
    }


def _cleanup_pending_artifacts(output_root: Path) -> None:
    for pending in _pending_artifact_paths(output_root):
        if pending.exists() and pending.is_file() and not pending.is_symlink():
            pending.unlink()


def _publish_pending_artifacts(output_root: Path) -> None:
    paths = _pending_artifact_paths(output_root)
    for pending, published in paths.items():
        if (
            not pending.is_file()
            or pending.is_symlink()
            or pending.parent.resolve() != output_root.resolve()
            or published.exists()
        ):
            raise ValueError("pending proof artifact set is incomplete or unsafe")
    published_now: list[Path] = []
    try:
        # The manifest is the pass marker and is deliberately published last.
        order = (
            output_root / ".contact-sheet.pending.png",
            output_root / ".contact-sheet.pending.json",
            output_root / ".manifest.pending.json",
        )
        for pending in order:
            published = paths[pending]
            os.replace(pending, published)
            published_now.append(published)
    except Exception:
        for path in published_now:
            if path.is_file() and not path.is_symlink():
                path.unlink()
        _cleanup_pending_artifacts(output_root)
        raise


def _run_pillow_finalizer(
    pillow_python: Path,
    proof_snapshot: Path,
    asset_root: Path,
    output_root: Path,
    rgba_path: Path,
    product_rgba_path: Path | None,
) -> dict[str, object]:
    command = [
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
    ]
    if product_rgba_path is not None:
        command.extend(["--product-rgba", str(product_rgba_path)])
    result = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[3],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip())
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as error:
        raise ValueError("Pillow finalizer did not return one JSON result") from error
    if not isinstance(payload, Mapping):
        raise ValueError("Pillow finalizer result must be an object")
    return dict(payload)


def _run_one(
    bpy: Any,
    proof_path: Path,
    asset_root: Path,
    tool_lock: Path,
    *,
    fixture_mode: bool,
) -> dict[str, object]:
    output_root: Path | None = None
    try:
        lock, pillow_python = _validate_tools(tool_lock)
        blender_identity = _validate_executing_blender(bpy, lock)
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
        tool_snapshot = output_root / "tool-lock.json"
        proof_snapshot.write_bytes(contract_bytes)
        scene_snapshot.write_bytes(scene_contract_path.read_bytes())
        tool_snapshot.write_bytes(tool_lock.read_bytes())

        scene_context = bpy.context.scene
        camera = scene_context.camera
        if camera is None:
            raise ValueError("proof scene has no active camera")
        authored_before = _capture_authored_settings(bpy)
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
            "use_file_extension": scene_context.render.use_file_extension,
            "view_transform": scene_context.view_settings.view_transform,
            "look": scene_context.view_settings.look,
            "exposure": scene_context.view_settings.exposure,
            "gamma": scene_context.view_settings.gamma,
            "cycles_device": scene_context.cycles.device,
            "cycles_samples": scene_context.cycles.samples,
            "cycles_use_denoising": scene_context.cycles.use_denoising,
        }
        lights: list[object] = []
        environment: list[object] = []
        product_rgba_path: Path | None = None
        try:
            rgba_path = output_root / f"{scene.scene_id}--rgba.png"
            metadata, lights, environment, product_rgba_path = _render_rgba(
                bpy, contract, rgba_path, fixture_mode=fixture_mode
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
            scene_context.render.use_file_extension = saved["use_file_extension"]
            scene_context.view_settings.view_transform = saved["view_transform"]
            scene_context.view_settings.look = saved["look"]
            scene_context.view_settings.exposure = saved["exposure"]
            scene_context.view_settings.gamma = saved["gamma"]
            scene_context.cycles.device = saved["cycles_device"]
            scene_context.cycles.samples = saved["cycles_samples"]
            scene_context.cycles.use_denoising = saved["cycles_use_denoising"]
        after_render = _snapshot(paths)
        authored_after = _capture_authored_settings(bpy)
        if before != after_render:
            return {
                "status": "blocked_fingerprint_drift",
                "generation_id": contract.generation_id,
                "errors": ["source/master/material/scene fingerprints changed during render"],
            }
        if authored_before != authored_after:
            return {
                "status": "blocked_settings_drift",
                "generation_id": contract.generation_id,
                "errors": ["authored camera/light/world/compositor settings changed during render"],
            }
        metadata.update(
            {
                "blender": blender_identity,
                "proof_contract_sha256": sha256_file(proof_snapshot),
                "scene_contract_sha256": sha256_file(scene_snapshot),
                "tool_lock_sha256": sha256_file(tool_snapshot),
                "fingerprints": {"before": before, "after": after_render},
                "authored_settings": {
                    "before": authored_before,
                    "after": authored_after,
                },
                "intended_subject_metrics": {},
                "physical_shadow_metrics": {},
            }
        )
        atomic_write_json(output_root / "render-metadata.json", metadata)
        try:
            _run_pillow_finalizer(
                pillow_python,
                proof_snapshot,
                asset_root,
                output_root,
                rgba_path,
                product_rgba_path,
            )
        except Exception as error:
            _cleanup_pending_artifacts(output_root)
            return {
                "status": "failed_finalize",
                "generation_id": contract.generation_id,
                "errors": [f"{type(error).__name__}: {error}"],
            }
        # This is the final gate. No pass-labelled artifact exists before it.
        after_prepare = _snapshot(paths)
        authored_after_prepare = _capture_authored_settings(bpy)
        if before != after_prepare:
            _cleanup_pending_artifacts(output_root)
            return {
                "status": "blocked_fingerprint_drift",
                "generation_id": contract.generation_id,
                "errors": ["source/master/material/scene fingerprints changed during proof finalization"],
            }
        if authored_before != authored_after_prepare:
            _cleanup_pending_artifacts(output_root)
            return {
                "status": "blocked_settings_drift",
                "generation_id": contract.generation_id,
                "errors": ["authored camera/light/world/compositor settings changed during proof finalization"],
            }
        _publish_pending_artifacts(output_root)
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
        if output_root is not None:
            _cleanup_pending_artifacts(output_root)
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
        result = _run_one(
            bpy,
            proof_path.resolve(),
            asset_root,
            tool_lock.resolve(),
            fixture_mode=arguments.fixture_asset_root is not None,
        )
        print(RESULT_MARKER + json.dumps(result, sort_keys=True), flush=True)
        if result["status"] != "pass":
            exit_code = 1
            break
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
