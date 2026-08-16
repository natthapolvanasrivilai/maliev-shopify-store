"""Fail-closed authorization and local QA boundary for native PIMM final renders."""

from __future__ import annotations

import json
import ntpath
import os
import re
import secrets
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

from .approval_manifest import (
    _canonical_component,
    _create_new_json,
    _lexically_within,
    _load_approval,
    _mapping,
    _reject_reparse_ancestors,
    _revision_entries,
    _sha,
    _unlink_owned,
    _validate_created_at_utc,
    _validate_roots,
    approval_head_lock,
    build_authorized_component_contract,
    canonical_absolute_path,
    canonical_json_sha256,
    compute_final_qa,
    held_evidence_authority,
    _stable_file,
    stable_file_record,
    stable_json,
    validate_approval,
    validate_evidence_records,
)
from .proof_contract import validate_authored_settings


_RELEASE_ID = re.compile(r"^release-[0-9]{4}-[0-9]{2}-[0-9]{2}-r[0-9]{2}$")
_DELIVERABLES = frozenset({"exr", "png", "webp"})
_FINAL_FIELDS = {
    "schema", "release_id", "shot_id", "generation_id", "authority_roots",
    "evidence", "inputs", "render_settings", "samples", "output_root",
    "deliverables", "asset_root", "scene_path",
}
_STATE_HASH_FIELDS = {
    "camera_sha256", "lights_sha256", "world_sha256", "compositor_sha256",
    "render_settings_sha256", "animation_sha256", "composition_sha256",
    "dependency_sha256",
}


@dataclass(frozen=True)
class FinalAuthorization:
    """A validated, approval-bound final-render execution envelope."""

    approval_path: Path
    final_contract_path: Path
    release_id: str
    shot_id: str
    generation_id: str
    output_root: PurePosixPath
    asset_root: Path
    scene_path: Path
    approval_sha256: str
    final_contract_sha256: str
    authorization_sha256: str
    approval_record: Mapping[str, object]
    final_contract_record: Mapping[str, object]


def _load_final(path: Path) -> tuple[Mapping[str, object], dict[str, Path], dict[str, object]]:
    absolute = canonical_absolute_path(str(Path(path)), "final contract path")
    drive_root = Path(absolute.anchor)
    payload, _ = stable_json(absolute, drive_root, "asset", "final contract")
    roots = _validate_roots(payload.get("authority_roots"))
    _lexically_within(absolute, roots["asset"], "final contract")
    payload, record = stable_json(absolute, roots["asset"], "asset", "final contract")
    return payload, roots, record


def _contract_errors(approval: Mapping[str, object], final: Mapping[str, object]) -> list[str]:
    errors: list[str] = []
    if set(final) != _FINAL_FIELDS:
        errors.append("final contract fields are incomplete or contain unknown values")
    if final.get("schema") != "pimm-final-render-contract/v1":
        errors.append("final contract schema is invalid")
    release_id = final.get("release_id")
    if not isinstance(release_id, str) or _RELEASE_ID.fullmatch(release_id) is None:
        errors.append("final release ID is invalid")
    if final.get("shot_id") != approval.get("shot_id"):
        errors.append("shot ID drift")
    if final.get("generation_id") != approval.get("proof_generation_id"):
        errors.append("proof generation drift")
    for field, label in (
        ("authority_roots", "authority roots"),
        ("evidence", "evidence"),
        ("inputs", "approved input SHA-256"),
    ):
        if final.get(field) != approval.get(field):
            errors.append(f"{label} drift")
    approved_settings = approval.get("render_settings")
    final_settings = final.get("render_settings")
    if not isinstance(approved_settings, Mapping) or not isinstance(final_settings, Mapping):
        errors.append("final render settings are required")
    else:
        expected_fields = _STATE_HASH_FIELDS | {
            "base_dimensions", "effective_proof_dimensions", "output_dimensions",
            "alpha_mode", "proof_samples",
        }
        if set(approved_settings) != expected_fields or set(final_settings) != expected_fields:
            errors.append("final render settings fields are invalid")
        labels = {
            "camera_sha256": "camera SHA-256 drift",
            "lights_sha256": "lights SHA-256 drift",
            "world_sha256": "world SHA-256 drift",
            "compositor_sha256": "compositor SHA-256 drift",
            "render_settings_sha256": "render settings SHA-256 drift",
            "animation_sha256": "animation SHA-256 drift",
            "dependency_sha256": "dependency SHA-256 drift",
            "composition_sha256": "composition SHA-256 drift",
            "output_dimensions": "output dimensions drift",
            "base_dimensions": "base dimensions drift",
            "effective_proof_dimensions": "effective proof dimensions drift",
            "alpha_mode": "alpha mode drift",
            "proof_samples": "proof samples drift",
        }
        for key, message in labels.items():
            if final_settings.get(key) != approved_settings.get(key):
                errors.append(message)
        for key in _STATE_HASH_FIELDS:
            try:
                _sha(final_settings.get(key), f"final {key}")
            except ValueError as error:
                errors.append(str(error))
        if final_settings.get("output_dimensions") != final_settings.get("base_dimensions"):
            errors.append("final output dimensions must retain original resolution")
    samples = final.get("samples")
    proof_samples = approved_settings.get("proof_samples") if isinstance(approved_settings, Mapping) else None
    if (
        not isinstance(samples, int)
        or isinstance(samples, bool)
        or not isinstance(proof_samples, int)
        or isinstance(proof_samples, bool)
        or samples <= proof_samples
    ):
        errors.append("final render requires an explicit sampling increase")
    output_root = final.get("output_root")
    if not isinstance(release_id, str) or output_root != f"renders/final/{release_id}":
        errors.append("final output root must be a new immutable renders/final/<release-id> directory")
    deliverables = final.get("deliverables")
    if (
        not isinstance(deliverables, list)
        or set(deliverables) != _DELIVERABLES
        or len(deliverables) != len(_DELIVERABLES)
    ):
        errors.append("final deliverables must contain exactly float EXR, transparent PNG, and transparent WebP")
    return errors


def _revision_head_errors(
    approval_path: Path, approval: Mapping[str, object], asset_root: Path
) -> list[str]:
    """Require the supplied approval to be the one unbroken immutable chain head."""

    try:
        entries = _revision_entries(approval_path.parent)
    except (OSError, ValueError) as error:
        return [str(error)]
    if not entries or entries[-1] != approval_path:
        return ["latest approval revision is required"]
    prior: Path | None = None
    for revision, path in enumerate(entries, start=1):
        try:
            payload, record = stable_json(path, asset_root, "asset", "approval revision")
        except ValueError as error:
            return [f"approval revision chain is unreadable: {error}"]
        if payload.get("revision") != revision:
            return ["approval revision chain is broken"]
        try:
            _validate_created_at_utc(payload.get("created_at_utc"))
        except ValueError as error:
            return [str(error)]
        if prior is None:
            if payload.get("prior_approval_sha256") is not None or payload.get("prior_approval_path") is not None:
                return ["approval revision chain is broken"]
        else:
            prior_record = stable_file_record(prior, asset_root, "asset", "prior approval revision")
            if (
                payload.get("prior_approval_sha256") != prior_record["sha256"]
                or payload.get("prior_approval_path") != str(prior)
            ):
                return ["approval revision chain is broken"]
        # Revalidate the current revision identity after all dependent reads.
        stable_file_record(path, asset_root, "asset", "approval revision", record)
        prior = path
    return []


def _authorization_payload(
    approval_path: Path,
    approval_record: Mapping[str, object],
    final_path: Path,
    final_record: Mapping[str, object],
    final: Mapping[str, object],
) -> dict[str, object]:
    return {
        "approval_path": str(approval_path),
        "approval_sha256": approval_record["sha256"],
        "final_contract_path": str(final_path),
        "final_contract_sha256": final_record["sha256"],
        "release_id": final["release_id"],
        "shot_id": final["shot_id"],
        "generation_id": final["generation_id"],
        "authority_roots": final["authority_roots"],
        "evidence": final["evidence"],
        "inputs": final["inputs"],
        "render_settings": final["render_settings"],
        "samples": final["samples"],
        "output_root": final["output_root"],
        "deliverables": final["deliverables"],
    }


def _authorize_final_render(
    approval_path: Path, final_contract_path: Path, *, head_locked: bool
) -> FinalAuthorization:
    approval_path = canonical_absolute_path(str(Path(approval_path)), "approval path")
    approval, approval_roots = _load_approval(approval_path)
    asset_root = approval_roots["asset"]

    def validate_locked() -> FinalAuthorization:
        locked_approval, locked_roots = _load_approval(approval_path)
        if locked_approval != approval or locked_roots != approval_roots:
            raise ValueError("approval identity raced before chain-head authorization")
        if (
            approval.get("decision") != "approved"
            or not isinstance(approval.get("owner"), str)
            or not str(approval["owner"]).strip()
        ):
            raise ValueError("owner approval required")
        errors = _revision_head_errors(approval_path, approval, asset_root)
        errors += validate_approval(approval_path, {})
        final, final_roots, final_record = _load_final(Path(final_contract_path))
        errors += _contract_errors(approval, final)
        try:
            _, current_evidence = validate_evidence_records(
                final.get("authority_roots"), final.get("evidence")
            )
            if current_evidence != final.get("evidence"):
                errors.append("final current evidence drift")
        except (OSError, ValueError) as error:
            errors.append(str(error))
        if final_roots != approval_roots:
            errors.append("final authority roots drift")
        try:
            final_asset = canonical_absolute_path(final.get("asset_root"), "final asset root")
            final_scene = canonical_absolute_path(final.get("scene_path"), "final scene path")
            if final_asset != asset_root:
                errors.append("final asset root drift")
            scene_record = _mapping(final.get("evidence"), "final evidence").get("scene")
            if not isinstance(scene_record, Mapping) or final_scene != Path(str(scene_record.get("path"))):
                errors.append("final scene path drift")
        except ValueError as error:
            errors.append(str(error))
            final_asset = asset_root
            final_scene = asset_root
        if errors:
            raise ValueError("final render authorization failed: " + "; ".join(errors))
        approval_record = stable_file_record(
            approval_path, asset_root, "asset", "latest approval"
        )
        final_path = canonical_absolute_path(str(Path(final_contract_path)), "final contract path")
        final_record = stable_file_record(
            final_path, asset_root, "asset", "final contract", final_record
        )
        authorization_hash = canonical_json_sha256(
            _authorization_payload(approval_path, approval_record, final_path, final_record, final)
        )
        return FinalAuthorization(
            approval_path=approval_path,
            final_contract_path=final_path,
            release_id=str(final["release_id"]),
            shot_id=str(final["shot_id"]),
            generation_id=str(final["generation_id"]),
            output_root=PurePosixPath(str(final["output_root"])),
            asset_root=final_asset,
            scene_path=final_scene,
            approval_sha256=str(approval_record["sha256"]),
            final_contract_sha256=str(final_record["sha256"]),
            authorization_sha256=authorization_hash,
            approval_record=approval_record,
            final_contract_record=final_record,
        )

    if head_locked:
        return validate_locked()
    with approval_head_lock(approval_path.parent):
        return validate_locked()


def authorize_final_render(approval_path: Path, final_contract_path: Path) -> FinalAuthorization:
    """Authorize only an explicit sample increase over a current approved proof."""

    return _authorize_final_render(approval_path, final_contract_path, head_locked=False)


def _validate_rgba(path: Path, dimensions: list[object]) -> tuple[int, int]:
    from PIL import Image

    with Image.open(path) as image:
        image.load()
        if list(image.size) != dimensions or image.mode != "RGBA":
            raise ValueError("final image dimensions or RGBA alpha drift")
        alpha = image.getchannel("A").getextrema()
        if alpha[1] == 0:
            raise ValueError("final image alpha has no visible product")
        return int(alpha[0]), int(alpha[1])


def _blender_render_script(
    output_root: Path,
    audit_path: Path,
    repository_root: Path,
    dimensions: list[object],
    samples: int,
    shot_id: str,
    component_contract: Mapping[str, object],
) -> str:
    """Return a native Blender script that audits current state before its only mutation."""

    component_specs = _component_mask_specs(component_contract, shot_id)

    return "\n".join((
        "import bpy, json, pathlib, sys",
        f"sys.path.insert(0, {str(repository_root)!r})",
        "from scripts.blender.pimm_production.blender_proof_render import _capture_authored_settings",
        f"pathlib.Path({str(audit_path)!r}).write_text(json.dumps(_capture_authored_settings(bpy), sort_keys=True), encoding='utf-8')",
        "scene = bpy.context.scene",
        "if scene.render.engine != 'CYCLES': raise RuntimeError('authorized final scene must retain CYCLES')",
        "original_frame = scene.frame_current",
        f"scene.cycles.samples = {samples}",
        "scene.render.film_transparent = True",
        f"scene.render.resolution_x = {int(dimensions[0])}",
        f"scene.render.resolution_y = {int(dimensions[1])}",
        "scene.render.resolution_percentage = 100",
        "scene.render.image_settings.color_mode = 'RGBA'",
        "scene.render.image_settings.file_format = 'PNG'",
        "scene.render.image_settings.color_depth = '8'",
        "scene.frame_set(scene.frame_start)",
        f"scene.render.filepath = {str(output_root / f'{shot_id}--animation-start.png')!r}",
        "bpy.ops.render.render(write_still=True)",
        "scene.frame_set(scene.frame_end)",
        f"scene.render.filepath = {str(output_root / f'{shot_id}--animation-end.png')!r}",
        "bpy.ops.render.render(write_still=True)",
        "scene.frame_set(original_frame)",
        "scene.render.image_settings.file_format = 'OPEN_EXR'",
        "scene.render.image_settings.color_depth = '32'",
        f"scene.render.filepath = {str(output_root / f'{shot_id}--transparent.exr')!r}",
        "bpy.ops.render.render(write_still=True)",
        "scene.render.image_settings.file_format = 'PNG'",
        "scene.render.image_settings.color_depth = '8'",
        f"scene.render.filepath = {str(output_root / f'{shot_id}--transparent.png')!r}",
        "bpy.ops.render.render(write_still=True)",
        *_component_mask_script_lines(output_root, component_specs),
    ))


def _component_mask_script_lines(
    output_root: Path, component_specs: list[dict[str, object]]
) -> tuple[str, ...]:
    """Render exact visible Object Index masks without saving the opened scene."""

    return (
        f"component_specs = json.loads({json.dumps(component_specs, sort_keys=True)!r})",
        "expected_ids = {stable_id for spec in component_specs for stable_id in spec['stable_object_ids']}",
        "objects_by_id = {}",
        "for obj in scene.objects:",
        "    stable_id = obj.get('pimm_stable_id') if hasattr(obj, 'get') else None",
        "    if stable_id in expected_ids:",
        "        objects_by_id.setdefault(str(stable_id), []).append(obj)",
        "if set(objects_by_id) != expected_ids or any(len(items) != 1 for items in objects_by_id.values()):",
        "    raise RuntimeError('approved component object identities are missing or ambiguous in native scene')",
        "if any(items[0].type != 'MESH' or items[0].hide_render for items in objects_by_id.values()):",
        "    raise RuntimeError('approved component object identities are not visible physical meshes')",
        "view_layer = bpy.context.view_layer",
        "original_pass_indices = {obj: obj.pass_index for obj in scene.objects}",
        "original_object_index_pass = view_layer.use_pass_object_index",
        "original_mask_samples = scene.cycles.samples",
        "original_compositor = scene.compositing_node_group",
        "mask_compositor = None",
        "try:",
        "    for obj in scene.objects:",
        "        obj.pass_index = 0",
        "    for spec in component_specs:",
        "        for stable_id in spec['stable_object_ids']:",
        "            objects_by_id[stable_id][0].pass_index = spec['pass_index']",
        "    view_layer.use_pass_object_index = True",
        "    view_layer.update_render_passes()",
        "    scene.cycles.samples = 1",
        "    mask_compositor = bpy.data.node_groups.new('PIMM_COMPONENT_MASKS', 'CompositorNodeTree')",
        "    scene.compositing_node_group = mask_compositor",
        "    render_layers = mask_compositor.nodes.new('CompositorNodeRLayers')",
        "    object_index_output = render_layers.outputs.get('Object Index') or render_layers.outputs.get('IndexOB')",
        "    if object_index_output is None:",
        "        raise RuntimeError('native component object-index compositor pass is absent')",
        "    for spec in component_specs:",
        "        id_mask = mask_compositor.nodes.new('CompositorNodeIDMask')",
        "        id_mask.inputs['Index'].default_value = spec['pass_index']",
        "        file_output = mask_compositor.nodes.new('CompositorNodeOutputFile')",
        "        file_output.directory = " + repr(str(output_root)),
        "        spec['temporary_prefix'] = '.pimm-component-' + str(spec['pass_index']) + '-'",
        "        file_output.file_name = spec['temporary_prefix']",
        "        output_item = file_output.file_output_items.new('FLOAT', 'Mask')",
        "        output_item.override_node_format = True",
        "        output_item.format.file_format = 'OPEN_EXR'",
        "        output_item.format.color_mode = 'BW'",
        "        output_item.format.color_depth = '32'",
        "        mask_compositor.links.new(object_index_output, id_mask.inputs['ID value'])",
        "        mask_compositor.links.new(id_mask.outputs['Alpha'], file_output.inputs['Mask'])",
        "    bpy.ops.render.render()",
        "    scene.render.image_settings.file_format = 'PNG'",
        "    scene.render.image_settings.color_mode = 'BW'",
        "    scene.render.image_settings.color_depth = '8'",
        "    for spec in component_specs:",
        "        matches = list(pathlib.Path(" + repr(str(output_root)) + ").glob(spec['temporary_prefix'] + '*.exr'))",
        "        if len(matches) != 1:",
        "            raise RuntimeError('native component compositor mask output is missing or ambiguous: ' + spec['mask_id'])",
        "        mask_image = bpy.data.images.load(str(matches[0]), check_existing=False)",
        "        try:",
        "            mask_image.save_render(str(pathlib.Path(" + repr(str(output_root)) + ") / spec['path']), scene=scene)",
        "        finally:",
        "            bpy.data.images.remove(mask_image)",
        "            matches[0].unlink()",
        "    scene.render.image_settings.color_mode = 'RGBA'",
        "finally:",
        "    for obj, pass_index in original_pass_indices.items():",
        "        obj.pass_index = pass_index",
        "    view_layer.use_pass_object_index = original_object_index_pass",
        "    scene.cycles.samples = original_mask_samples",
        "    scene.compositing_node_group = original_compositor",
        "    if mask_compositor is not None:",
        "        bpy.data.node_groups.remove(mask_compositor)",
    )


def _component_mask_specs(
    component_contract: Mapping[str, object], shot_id: str
) -> list[dict[str, object]]:
    """Return canonical mask names and render-pass identities for one component contract."""

    material_objects = component_contract.get("material_objects")
    segments = component_contract.get("segments")
    if not isinstance(material_objects, list) or not isinstance(segments, list):
        raise ValueError("final component contract object identities are invalid")
    specs: list[dict[str, object]] = [
        {
            "mask_id": "material",
            "path": f"{shot_id}--material-objects-mask.png",
            "pass_index": 1,
            "stable_object_ids": [
                str(_mapping(item, "approved material component")["stable_object_id"])
                for item in material_objects
            ],
        }
    ]
    for ordinal, raw_segment in enumerate(segments):
        segment = _mapping(raw_segment, f"approved controller segment {ordinal}")
        if segment.get("ordinal") != ordinal:
            raise ValueError("final component contract segment order drift")
        specs.append(
            {
                "mask_id": str(segment["stable_object_id"]),
                "path": f"{shot_id}--controller-segment-{ordinal:02d}-mask.png",
                "pass_index": ordinal + 2,
                "stable_object_ids": [str(segment["stable_object_id"])],
            }
        )
    return specs


def _blender_component_mask_script(
    output_root: Path,
    audit_path: Path,
    repository_root: Path,
    dimensions: list[object],
    shot_id: str,
    component_contract: Mapping[str, object],
    samples: int,
    combined_filename: str,
    combined_exr_filename: str,
) -> str:
    """Return a standalone Blender script for independent media/mask regeneration."""

    specs = _component_mask_specs(component_contract, shot_id)
    return "\n".join(
        (
            "import bpy, json, pathlib, sys",
            f"sys.path.insert(0, {str(repository_root)!r})",
            "from scripts.blender.pimm_production.blender_proof_render import _capture_authored_settings",
            f"pathlib.Path({str(audit_path)!r}).write_text(json.dumps(_capture_authored_settings(bpy), sort_keys=True), encoding='utf-8')",
            "scene = bpy.context.scene",
            "if scene.render.engine != 'CYCLES': raise RuntimeError('authorized final scene must retain CYCLES')",
            "scene.render.film_transparent = True",
            f"scene.render.resolution_x = {int(dimensions[0])}",
            f"scene.render.resolution_y = {int(dimensions[1])}",
            "scene.render.resolution_percentage = 100",
            f"scene.cycles.samples = {samples}",
            "scene.render.image_settings.file_format = 'OPEN_EXR'",
            "scene.render.image_settings.color_mode = 'RGBA'",
            "scene.render.image_settings.color_depth = '32'",
            f"scene.render.filepath = {str(output_root / combined_exr_filename)!r}",
            "bpy.ops.render.render(write_still=True)",
            "scene.render.image_settings.file_format = 'PNG'",
            "scene.render.image_settings.color_mode = 'RGBA'",
            "scene.render.image_settings.color_depth = '8'",
            f"scene.render.filepath = {str(output_root / combined_filename)!r}",
            "bpy.ops.render.render(write_still=True)",
            *_component_mask_script_lines(output_root, specs),
        )
    )


def _live_state_hashes(
    authored: Mapping[str, object], animation_contract: object
) -> dict[str, str]:
    return {
        "camera_sha256": canonical_json_sha256(authored.get("camera")),
        "lights_sha256": canonical_json_sha256(authored.get("lights")),
        "world_sha256": canonical_json_sha256(authored.get("world")),
        "compositor_sha256": canonical_json_sha256(authored.get("compositor")),
        "render_settings_sha256": canonical_json_sha256({
            "render": authored.get("render"),
            "cycles": authored.get("cycles"),
            "color_management": authored.get("color_management"),
            "view_layers": authored.get("view_layers"),
        }),
        "animation_sha256": canonical_json_sha256({
            "animation_contract": animation_contract,
            "objects": authored.get("objects"),
        }),
        "dependency_sha256": _sha(
            authored.get("dependency_sha256"), "native dependency SHA-256"
        ),
    }


def _owned_identity(path: Path) -> dict[str, object]:
    status = os.stat(path, follow_symlinks=False)
    return {
        "device": int(status.st_dev), "inode": int(status.st_ino),
        "links": int(status.st_nlink), "bytes": int(status.st_size),
        "mtime_ns": int(status.st_mtime_ns), "ctime_ns": int(status.st_ctime_ns),
    }


def _directory_claim(path: Path) -> tuple[int, int, int]:
    _reject_reparse_ancestors(path, "owned final stage")
    status = os.stat(path, follow_symlinks=False)
    if not stat.S_ISDIR(status.st_mode):
        raise ValueError("owned final stage is no longer a directory")
    return int(status.st_dev), int(status.st_ino), int(status.st_nlink)


def _cleanup_stage(stage: Path, expected_files: set[Path]) -> None:
    """Delete only known files inside the exclusively-owned stage."""

    if not stage.exists():
        return
    actual_files = {path for path in stage.rglob("*") if path.is_file() and not path.is_symlink()}
    if not actual_files <= expected_files:
        return
    for path in sorted(actual_files, key=lambda item: len(item.parts), reverse=True):
        _unlink_owned(path, _owned_identity(path), "owned final stage artifact")
    directories = sorted(
        (path for path in stage.rglob("*") if path.is_dir() and not path.is_symlink()),
        key=lambda item: len(item.parts),
        reverse=True,
    )
    for directory in directories:
        directory.rmdir()
    stage.rmdir()


def run_authorized_final(approval_path: Path, final_contract_path: Path) -> Path:
    """Stage, audit, render, QA, and exclusively publish one immutable final root."""

    raw_approval = canonical_absolute_path(str(Path(approval_path)), "approval path")
    with approval_head_lock(raw_approval.parent):
        authorization = _authorize_final_render(
            raw_approval, final_contract_path, head_locked=True
        )
        final, roots, _ = _load_final(Path(final_contract_path))
        dimensions = _mapping(final.get("render_settings"), "final render settings").get("output_dimensions")
        if (
            not isinstance(dimensions, list)
            or len(dimensions) != 2
            or not all(isinstance(value, int) and not isinstance(value, bool) and value > 0 for value in dimensions)
        ):
            raise ValueError("native final output dimensions are invalid")
        final_evidence = _mapping(final.get("evidence"), "final evidence")
        machine_contract_record = _mapping(
            final_evidence.get("machine_contract"), "machine contract evidence"
        )
        machine_contract_path = Path(str(machine_contract_record.get("path")))
        approved_machine_contract, _ = stable_json(
            machine_contract_path,
            roots["repository"],
            "repository",
            "approved machine contract",
            machine_contract_record,
        )
        render_metadata_record = _mapping(
            final_evidence.get("render_metadata"), "render metadata evidence"
        )
        approved_render_metadata, _ = stable_json(
            Path(str(render_metadata_record.get("path"))),
            roots["asset"],
            "asset",
            "approved render metadata",
            render_metadata_record,
        )
        approved_authored_settings = _mapping(
            approved_render_metadata.get("authored_settings"),
            "approved authored settings evidence",
        )
        approved_component_contract = build_authorized_component_contract(
            approved_machine_contract,
            _mapping(
                approved_authored_settings.get("before"),
                "approved authored settings before",
            ),
            final.get("authority_roots"),
            final_evidence,
        )
        release_parent = authorization.asset_root / "renders" / "final"
        _lexically_within(release_parent, authorization.asset_root, "final release parent")
        _reject_reparse_ancestors(release_parent, "final release parent")
        release_parent.mkdir(parents=True, exist_ok=True)
        _reject_reparse_ancestors(release_parent, "final release parent")
        release_root = release_parent / authorization.release_id
        if release_root.exists():
            raise ValueError("final release root already exists; immutable output required")
        stage = release_parent / f".{authorization.release_id}-{secrets.token_hex(8)}.stage"
        os.mkdir(stage)
        stage_claim = _directory_claim(stage)
        family = stage / authorization.shot_id
        os.mkdir(family)
        script = family / ".native-final.py"
        audit = family / ".native-state.json"
        endpoint_start = family / f"{authorization.shot_id}--animation-start.png"
        endpoint_end = family / f"{authorization.shot_id}--animation-end.png"
        exr = family / f"{authorization.shot_id}--transparent.exr"
        png = family / f"{authorization.shot_id}--transparent.png"
        webp = family / f"{authorization.shot_id}--transparent.webp"
        manifest = family / "final-output-manifest.json"
        component_specs = _component_mask_specs(
            approved_component_contract, authorization.shot_id
        )
        component_paths = {
            str(spec["mask_id"]): family / str(spec["path"])
            for spec in component_specs
        }
        expected_stage_files = {
            script, audit, endpoint_start, endpoint_end, exr, png, webp, manifest,
            *component_paths.values(),
        }
        try:
            repository_root = roots["repository"]
            script.write_text(
                _blender_render_script(
                    family, audit, repository_root, dimensions,
                    int(final["samples"]), authorization.shot_id,
                    approved_component_contract,
                ),
                encoding="utf-8",
            )
            script_identity = _owned_identity(script)
            blender_record = _mapping(final.get("evidence"), "final evidence").get("blender_binary")
            blender = Path(str(_mapping(blender_record, "Blender evidence").get("path")))
            # Hold the exact scene/master/material authority from its last
            # rehash until Blender exits.  This denies same-path byte swaps and
            # rename/delete replacement while linked datablocks are resolving.
            with held_evidence_authority(
                final.get("authority_roots"), final.get("evidence")
            ):
                result = subprocess.run(
                    [str(blender), "--factory-startup", "-b", str(authorization.scene_path), "-P", str(script)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            if result.returncode:
                raise ValueError("native Blender final render failed: " + result.stderr[-1000:])
            if not all(
                path.is_file()
                for path in (
                    audit, endpoint_start, endpoint_end, exr, png,
                    *component_paths.values(),
                )
            ):
                raise ValueError(
                    "native final did not produce audited media and component-mask outputs "
                    f"(files={sorted(child.name for child in family.iterdir())}, "
                    f"stdout={result.stdout[-1000:]}, stderr={result.stderr[-2000:]})"
                )
            authored, _ = stable_json(audit, stage, "asset", "native authored state")
            authored = validate_authored_settings(
                authored, "native authored state"
            )
            scene_contract_record = _mapping(final.get("evidence"), "final evidence").get("scene_contract")
            scene_contract_path = Path(str(_mapping(scene_contract_record, "scene contract evidence").get("path")))
            scene_contract, _ = stable_json(
                scene_contract_path, roots["asset"], "asset", "current scene contract",
                _mapping(scene_contract_record, "scene contract evidence"),
            )
            machine_contract, _ = stable_json(
                machine_contract_path,
                roots["repository"],
                "repository",
                "current machine contract",
                machine_contract_record,
            )
            live_component_contract = build_authorized_component_contract(
                machine_contract,
                authored,
                final.get("authority_roots"),
                final_evidence,
            )
            if live_component_contract != approved_component_contract:
                raise ValueError("native component identities drifted from approved scene/machine")
            live_hashes = _live_state_hashes(authored, scene_contract.get("animation_contract"))
            expected_settings = _mapping(final.get("render_settings"), "final render settings")
            for field, actual in live_hashes.items():
                if expected_settings.get(field) != actual:
                    raise ValueError(f"native current {field.replace('_sha256', '')} state drift")
            _validate_rgba(png, dimensions)
            from PIL import Image
            with Image.open(png) as image:
                image.save(webp, format="WEBP", lossless=True)
            _validate_rgba(webp, dimensions)
            if exr.read_bytes()[:4] != b"v/1\x01":
                raise ValueError("native final did not produce a genuine EXR")
            png_record, png_bytes = _stable_file(
                str(png), str(stage), "asset", "native final PNG", capture=True
            )
            start_record, start_bytes = _stable_file(
                str(endpoint_start), str(stage), "asset", "animation start endpoint", capture=True
            )
            end_record, end_bytes = _stable_file(
                str(endpoint_end), str(stage), "asset", "animation end endpoint", capture=True
            )
            component_mask_bytes: dict[str, bytes] = {}
            component_mask_records: list[dict[str, object]] = []
            component_publication_records: list[tuple[Path, dict[str, object]]] = []
            for spec in component_specs:
                mask_id = str(spec["mask_id"])
                path = component_paths[mask_id]
                record, data = _stable_file(
                    str(path), str(stage), "asset",
                    f"native component mask {mask_id}", capture=True,
                )
                component_mask_bytes[mask_id] = data or b""
                component_publication_records.append((path, record))
                component_mask_records.append({
                    "mask_id": mask_id,
                    "path": path.name,
                    "sha256": record["sha256"],
                    "dimensions": dimensions,
                    "mime_type": "image/png",
                })
            qa = compute_final_qa(
                png_bytes or b"",
                {"start": start_bytes or b"", "end": end_bytes or b""},
                dimensions,
                machine_contract,
                scene_contract,
                component_contract=approved_component_contract,
                component_mask_bytes=component_mask_bytes,
                material_library_sha256=str(_mapping(final.get("inputs"), "final inputs")["material_library_sha256"]),
                scene_contract_sha256=str(_mapping(scene_contract_record, "scene contract evidence")["sha256"]),
                machine_contract_sha256=str(_mapping(machine_contract_record, "machine contract evidence")["sha256"]),
            )
            _unlink_owned(script, script_identity, "native final script")
            _unlink_owned(audit, _owned_identity(audit), "native state audit")

            # Revalidate all authorities and both authorization records immediately
            # before hashing output and publishing evidence.
            validate_evidence_records(final.get("authority_roots"), final.get("evidence"))
            stable_file_record(
                authorization.approval_path, authorization.asset_root, "asset",
                "latest approval", authorization.approval_record,
            )
            stable_file_record(
                authorization.final_contract_path, authorization.asset_root, "asset",
                "final contract", authorization.final_contract_record,
            )
            outputs: list[dict[str, object]] = []
            qa_evidence: list[dict[str, object]] = []
            published_records: list[tuple[Path, dict[str, object]]] = [
                (endpoint_start, start_record), (endpoint_end, end_record),
                *component_publication_records,
            ]
            for label, path, record in (
                ("start", endpoint_start, start_record),
                ("end", endpoint_end, end_record),
            ):
                stable_file_record(
                    path, stage, "asset", f"animation {label} endpoint", record
                )
                qa_evidence.append({
                    "role": f"animation-{label}",
                    "path": path.name,
                    "sha256": record["sha256"],
                    "dimensions": dimensions,
                    "mime_type": "image/png",
                })
            for path, mime in ((exr, "image/x-exr"), (png, "image/png"), (webp, "image/webp")):
                record = stable_file_record(path, stage, "asset", f"final {path.suffix}")
                published_records.append((path, record))
                extension = path.suffix[1:]
                outputs.append({
                    "logical_asset_id": f"{authorization.shot_id}--transparent-{extension}",
                    "path": path.name,
                    "sha256": record["sha256"],
                    "dimensions": dimensions,
                    "alpha": True,
                    "mime_type": mime,
                })
            _create_new_json(manifest, {
                "schema": "pimm-final-output-manifest/v1",
                "release_id": authorization.release_id,
                "generation_id": authorization.generation_id,
                "shot_id": authorization.shot_id,
                "approval_path": str(authorization.approval_path),
                "approval_sha256": authorization.approval_sha256,
                "authorized_final_contract_path": str(authorization.final_contract_path),
                "authorized_final_contract_sha256": authorization.final_contract_sha256,
                "final_authorization_sha256": authorization.authorization_sha256,
                "output_root": f"renders/final/{authorization.release_id}",
                "required_deliverables": ["exr", "png", "webp"],
                "qa": qa,
                "qa_evidence": qa_evidence,
                "component_evidence": {
                    "schema": "pimm-final-component-evidence/v1",
                    "contract": approved_component_contract,
                    "masks": component_mask_records,
                },
                "outputs": outputs,
            })
            manifest_record = stable_file_record(
                manifest, stage, "asset", "final output manifest"
            )
            published_records.append((manifest, manifest_record))
            for path, record in published_records:
                stable_file_record(path, stage, "asset", "staged final publication", record)
            if _directory_claim(stage) != stage_claim:
                raise ValueError("owned final stage identity changed before publication")
            if release_root.exists():
                raise ValueError("final release root already exists; competing publication detected")
            try:
                os.rename(stage, release_root)
            except FileExistsError as error:
                raise ValueError(
                    "final release root already exists; competing publication detected"
                ) from error
            return release_root / authorization.shot_id / manifest.name
        except BaseException:
            _cleanup_stage(stage, expected_stage_files)
            raise
