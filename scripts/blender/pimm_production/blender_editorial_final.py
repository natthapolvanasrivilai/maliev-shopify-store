"""Render and atomically publish one approval-bound editorial native release."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Mapping, Sequence
import uuid

from PIL import Image, ImageDraw, ImageFont

try:
    from . import blender_editorial_scene
    from .blender_editorial_preview import (
        _CAMPAIGN, _authority_worker_record, _load_completion_authority,
        _validate_blender_authority, _validate_rendered_png_dimensions,
    )
    from .editorial_final_contract import (
        ALLOWED_SCENE_MUTATIONS, FINAL_CONTRACT_NAME, RELEASE_ID,
        validate_editorial_final_contract,
    )
    from .io_contract import sha256_file
    from .paths import require_within
except ImportError:  # Blender executes this checked-in file outside package mode.
    repository_root = Path(__file__).resolve().parents[3]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))
    from scripts.blender.pimm_production import blender_editorial_scene
    from scripts.blender.pimm_production.blender_editorial_preview import (
        _CAMPAIGN, _authority_worker_record, _load_completion_authority,
        _validate_blender_authority, _validate_rendered_png_dimensions,
    )
    from scripts.blender.pimm_production.editorial_final_contract import (
        ALLOWED_SCENE_MUTATIONS, FINAL_CONTRACT_NAME, RELEASE_ID,
        validate_editorial_final_contract,
    )
    from scripts.blender.pimm_production.io_contract import sha256_file
    from scripts.blender.pimm_production.paths import require_within


WORKER_MARKER = "PIMM_EDITORIAL_FINAL_JSON="
REPORT_NAME = "native-report.json"
CONTACT_SHEET_NAME = "sheet-editorial-finals.png"
DISPOSITION_NAME = "actual-pixel-disposition.json"
RELEASE_MANIFEST_NAME = "release-manifest.json"
FINAL_LIBRARY = "editorial-concepts-v1"
WORKER_TIMEOUT_SECONDS = 3600
_PASS_FIELDS = ("pixel_review", "grounding", "clipping", "props", "exposure", "detail", "decals")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json_bytes(payload: Mapping[str, object]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _exclusive_json(path: Path, payload: Mapping[str, object]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(_json_bytes(payload))
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _validate_ephemeral_render_delta(
    baseline: Mapping[str, object],
    final: Mapping[str, object],
    contract: Mapping[str, object],
) -> None:
    """Reject every in-memory scene mutation not explicitly authorized by contract."""

    if set(baseline) != set(final):
        raise ValueError("final render state fields drift")
    allowed = contract.get("allowed_scene_mutations")
    if allowed != ALLOWED_SCENE_MUTATIONS:
        raise ValueError("final render allowed mutation policy drift")
    for field in baseline:
        if field not in ALLOWED_SCENE_MUTATIONS and baseline[field] != final[field]:
            raise ValueError(f"unauthorized final render {field} drift")


def _state_record(bpy: Any) -> dict[str, object]:
    scene = bpy.context.scene
    return {
        "camera": str(scene.camera.name if scene.camera else ""),
        "lights": blender_editorial_scene._scene_light_signature(bpy),
        "world": str(getattr(scene.world, "name", "")),
        "compositor": blender_editorial_scene._node_tree_signature_record(
            bpy, getattr(scene, "node_tree", None)
        ),
        "resolution_x": int(scene.render.resolution_x),
        "resolution_y": int(scene.render.resolution_y),
        "resolution_percentage": int(scene.render.resolution_percentage),
        "cycles.samples": int(scene.cycles.samples),
        "cycles.use_denoising": bool(scene.cycles.use_denoising),
        "render.filepath": str(scene.render.filepath),
        "image_settings.file_format": str(scene.render.image_settings.file_format),
        "image_settings.color_mode": str(scene.render.image_settings.color_mode),
        "image_settings.color_depth": str(scene.render.image_settings.color_depth),
    }


def _shot_dimensions(contract: Mapping[str, object], approved_shot: Mapping[str, object]) -> tuple[int, int]:
    source = approved_shot.get("dimensions")
    if not isinstance(source, list) or len(source) != 2:
        raise ValueError("approved shot dimensions are invalid")
    target = contract["landscape_dimensions"] if int(source[0]) > int(source[1]) else contract["portrait_dimensions"]
    width, height = int(target[0]), int(target[1])
    if int(source[0]) * height != int(source[1]) * width:
        raise ValueError("native final aspect ratio drift")
    return width, height


def _render_worker(
    bpy: Any,
    *,
    asset_root: Path,
    contract_path: Path,
    staging_root: Path,
    shot_id: str,
) -> dict[str, object]:
    contract = validate_editorial_final_contract(contract_path, asset_root)
    approved = next((item for item in contract["shots"] if item["shot_id"] == shot_id), None)
    if approved is None:
        raise ValueError("final shot is not approval-authorized")
    campaign_shot = _CAMPAIGN.by_shot_id[shot_id]
    authority = _load_completion_authority(asset_root, campaign_shot)
    expected_authority = dict(approved["authority"])
    expected_authority.pop("checked_at", None)
    expected_authority.pop("blender_scene_validation", None)
    if expected_authority != _authority_worker_record(authority):
        raise ValueError("final shot current completion authority drift")
    if Path(str(bpy.data.filepath)).resolve() != authority.scene_path:
        raise ValueError("fresh Blender process opened the wrong editorial scene")
    snapshot, collection_errors = blender_editorial_scene._collect_runtime_snapshot(bpy, authority.contract)
    errors = [
        *collection_errors,
        *blender_editorial_scene._validate_editorial_runtime_snapshot(snapshot, authority.contract),
    ]
    if errors:
        raise ValueError("fresh native final scene authority failed: " + "; ".join(errors))

    width, height = _shot_dimensions(contract, approved)
    png = require_within(staging_root / f"{shot_id}.png", staging_root)
    exr = require_within(staging_root / f"{shot_id}.exr", staging_root)
    if png.exists() or exr.exists():
        raise ValueError("native final worker output already exists")
    baseline = _state_record(bpy)
    scene = bpy.context.scene
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.cycles.samples = int(contract["samples"])
    scene.cycles.use_denoising = bool(contract["denoise"])
    scene.render.filepath = str(png)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "16"
    mutated = _state_record(bpy)
    _validate_ephemeral_render_delta(baseline, mutated, contract)
    started_at = _utc_now()
    started = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    seconds = time.perf_counter() - started
    _validate_rendered_png_dimensions(png, width, height)
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "32"
    bpy.data.images["Render Result"].save_render(filepath=str(exr), scene=scene)
    if not exr.is_file() or exr.stat().st_size <= 0:
        raise ValueError("native archive EXR was not produced")
    final_state = _state_record(bpy)
    _validate_ephemeral_render_delta(baseline, final_state, contract)
    validate_editorial_final_contract(contract_path, asset_root)
    return {
        "shot_id": shot_id,
        "process_id": os.getpid(),
        "scene_sha256": authority.scene_sha256,
        "contract_sha256": authority.contract_sha256,
        "completion_marker_sha256": authority.completion_marker_sha256,
        "png": png.name,
        "png_sha256": sha256_file(png),
        "exr": exr.name,
        "exr_sha256": sha256_file(exr),
        "dimensions": [width, height],
        "samples": int(contract["samples"]),
        "denoise": bool(contract["denoise"]),
        "film_transparent": bool(scene.render.film_transparent),
        "started_at": started_at,
        "finished_at": _utc_now(),
        "seconds": round(seconds, 6),
        "authority_status": "pass",
        "actual_pixel_review": "pending",
    }


def _worker_command(
    blender: Path, scene: Path, asset_root: Path, contract: Path, staging: Path, shot_id: str
) -> list[str]:
    return [
        str(blender), "--background", str(scene), "--python", str(Path(__file__).resolve()), "--",
        "--render-shot", "--asset-root", str(asset_root), "--contract", str(contract),
        "--staging-root", str(staging), "--shot-id", shot_id,
    ]


def _parse_worker(completed: subprocess.CompletedProcess[str], shot_id: str) -> dict[str, object]:
    if completed.returncode != 0:
        raise ValueError(f"native final Blender worker failed for {shot_id}: {completed.stderr[-2000:]}")
    lines = [line for line in completed.stdout.splitlines() if line.startswith(WORKER_MARKER)]
    if len(lines) != 1:
        raise ValueError(f"native final Blender worker result is missing for {shot_id}")
    payload = json.loads(lines[0][len(WORKER_MARKER):])
    if payload.get("shot_id") != shot_id:
        raise ValueError("native final Blender worker shot identity drift")
    return payload


def _build_contact_sheet(staging: Path, shots: Sequence[Mapping[str, object]]) -> Path:
    output = staging / CONTACT_SHEET_NAME
    canvas = Image.new("RGB", (2560, 1800), (238, 238, 236))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=24)
    for index, shot in enumerate(shots):
        x = (index % 2) * 1280
        y = (index // 2) * 900
        with Image.open(staging / str(shot["png"])) as source:
            image = source.convert("RGB")
            image.thumbnail((1240, 820), Image.Resampling.LANCZOS)
            px = x + (1280 - image.width) // 2
            py = y + 38 + (820 - image.height) // 2
            canvas.paste(image, (px, py))
        draw.text((x + 20, y + 10), str(shot["shot_id"]), fill=(18, 18, 18), font=font)
    canvas.save(output, format="PNG", compress_level=6)
    return output


def _preserve_failure(staging: Path, asset_root: Path, release_id: str, error: Exception) -> Path | None:
    if not staging.exists():
        return None
    failure_parent = asset_root / "renders" / "final-failures" / FINAL_LIBRARY
    failure_parent.mkdir(parents=True, exist_ok=True)
    rejected = failure_parent / f"{release_id}-{uuid.uuid4().hex[:8]}"
    try:
        (staging / "failure.json").write_bytes(_json_bytes({
            "release_id": release_id, "failed_at": _utc_now(),
            "error_type": type(error).__name__, "error": str(error),
        }))
        os.rename(staging, rejected)
        return rejected
    except OSError:
        return None


def render_editorial_native_finals(asset_root: Path, blender: Path, contract_path: Path) -> Path:
    """Render four fresh native pairs into one exclusively claimed hidden staging root."""

    asset_root = Path(asset_root).resolve()
    blender = Path(blender).resolve()
    contract_path = Path(contract_path).resolve()
    contract = validate_editorial_final_contract(contract_path, asset_root)
    _validate_blender_authority(asset_root, blender)
    parent = asset_root / "renders" / "final" / FINAL_LIBRARY
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / str(contract["release_id"])
    if target.exists():
        raise ValueError("editorial native final release already exists")
    staging = parent / f".{contract['release_id']}.pending-{uuid.uuid4().hex}"
    staging.mkdir(exist_ok=False)
    try:
        records = []
        for shot in contract["shots"]:
            validate_editorial_final_contract(contract_path, asset_root)
            scene = Path(str(shot["authority"]["scene_path"]))
            completed = subprocess.run(
                _worker_command(blender, scene, asset_root, contract_path, staging, str(shot["shot_id"])),
                capture_output=True, text=True, timeout=WORKER_TIMEOUT_SECONDS, check=False,
            )
            records.append(_parse_worker(completed, str(shot["shot_id"])))
            validate_editorial_final_contract(contract_path, asset_root)
        if len({record["process_id"] for record in records}) != 4:
            raise ValueError("native final campaign did not use four fresh Blender processes")
        contact = _build_contact_sheet(staging, records)
        report = {
            "schema": "maliev.pimm-editorial-native-report/v1",
            "release_id": contract["release_id"],
            "generation_id": contract["generation_id"],
            "contract_path": str(contract_path),
            "contract_sha256": sha256_file(contract_path),
            "rendered_at": _utc_now(),
            "fresh_blender_processes": 4,
            "samples": 256,
            "shots": records,
            "contact_sheet": {"path": contact.name, "sha256": sha256_file(contact), "dimensions": [2560, 1800]},
            "status": "pending-actual-pixel-review",
        }
        _exclusive_json(staging / REPORT_NAME, report)
        validate_editorial_final_contract(contract_path, asset_root)
        return staging
    except Exception as error:
        rejected = _preserve_failure(staging, asset_root, str(contract["release_id"]), error)
        suffix = f"; evidence={rejected}" if rejected else ""
        raise RuntimeError(f"editorial native final render failed: {error}{suffix}") from error


def _validate_staging(staging: Path, contract: Mapping[str, object]) -> tuple[dict[str, object], set[str]]:
    report_path = staging / REPORT_NAME
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("release_id") != contract["release_id"] or report.get("contract_sha256") != sha256_file(Path(str(report["contract_path"]))):
        raise ValueError("native report contract binding drift")
    records = report.get("shots")
    if not isinstance(records, list) or [item.get("shot_id") for item in records] != [item["shot_id"] for item in contract["shots"]]:
        raise ValueError("native report exact four-shot set drift")
    expected = {REPORT_NAME, CONTACT_SHEET_NAME}
    for approved, record in zip(contract["shots"], records, strict=True):
        width, height = _shot_dimensions(contract, approved)
        if record.get("dimensions") != [width, height]:
            raise ValueError("native final dimensions drift")
        for field in ("png", "exr"):
            relative = record.get(field)
            if not isinstance(relative, str) or Path(relative).name != relative:
                raise ValueError("native final output path is invalid")
            path = require_within(staging / relative, staging)
            if not path.is_file() or sha256_file(path) != record.get(f"{field}_sha256"):
                raise ValueError(f"native final {field} hash drift")
            expected.add(relative)
        with Image.open(staging / str(record["png"])) as image:
            if image.format != "PNG" or image.size != (width, height):
                raise ValueError("native final PNG dimensions or format drift")
    sheet = staging / CONTACT_SHEET_NAME
    if report.get("contact_sheet", {}).get("sha256") != sha256_file(sheet):
        raise ValueError("native final contact-sheet hash drift")
    observed = {path.name for path in staging.iterdir()}
    if observed != expected or any(path.is_dir() for path in staging.iterdir()):
        raise ValueError("native final staging contains extra or missing files")
    return report, expected


def publish_editorial_native_release(
    staging: Path, contract_path: Path, disposition: Mapping[str, object]
) -> Path:
    """Publish only a complete, hash-bound actual-pixel acceptance; marker last."""

    staging = Path(staging).resolve()
    contract_path = Path(contract_path).resolve()
    asset_root = contract_path.parents[3]
    contract = validate_editorial_final_contract(contract_path, asset_root)
    parent = asset_root / "renders" / "final" / FINAL_LIBRARY
    require_within(staging, parent)
    if not staging.name.startswith(f".{contract['release_id']}") or ".pending" not in staging.name:
        raise ValueError("native final staging claim is invalid")
    report, expected = _validate_staging(staging, contract)
    if disposition.get("decision") != "accept" or not str(disposition.get("reviewer", "")).strip():
        raise ValueError("actual-pixel disposition is not an identified acceptance")
    reviewed_at = disposition.get("reviewed_at")
    if not isinstance(reviewed_at, str) or not reviewed_at.endswith("Z"):
        raise ValueError("actual-pixel disposition UTC timestamp is invalid")
    sheet_review = disposition.get("contact_sheet")
    if not isinstance(sheet_review, Mapping) or sheet_review.get("pixel_review") != "pass" or sheet_review.get("sha256") != report["contact_sheet"]["sha256"]:
        raise ValueError("contact-sheet actual-pixel disposition is incomplete or hash drifted")
    reviews = disposition.get("shots")
    if not isinstance(reviews, list) or len(reviews) != 4:
        raise ValueError("exactly four actual-pixel shot dispositions are required")
    for record, review in zip(report["shots"], reviews, strict=True):
        if not isinstance(review, Mapping) or review.get("shot_id") != record["shot_id"]:
            raise ValueError("actual-pixel shot disposition identity drift")
        if review.get("png_sha256") != record["png_sha256"] or review.get("exr_sha256") != record["exr_sha256"]:
            raise ValueError("actual-pixel shot disposition hash drift")
        if any(review.get(field) != "pass" for field in _PASS_FIELDS) or not str(review.get("notes", "")).strip():
            raise ValueError("actual-pixel shot disposition requires every field to pass")
    # Web derivatives are intentionally created only after the acceptance above is complete.
    for record in report["shots"]:
        webp = staging / f"{record['shot_id']}.webp"
        with Image.open(staging / str(record["png"])) as image:
            image.save(webp, format="WEBP", quality=92, method=6)
        record["webp"] = webp.name
        record["webp_sha256"] = sha256_file(webp)
        expected.add(webp.name)
    disposition_path = staging / DISPOSITION_NAME
    _exclusive_json(disposition_path, dict(disposition))
    expected.add(DISPOSITION_NAME)
    # Bind the accepted review and derivatives into the report before marker-last publication.
    report["status"] = "accepted"
    report["accepted_at"] = _utc_now()
    report["actual_pixel_disposition"] = {"path": DISPOSITION_NAME, "sha256": sha256_file(disposition_path)}
    report["shots"] = report["shots"]
    report_path = staging / REPORT_NAME
    report_path.chmod(0o644)
    report_path.write_bytes(_json_bytes(report))
    report_path.chmod(0o444)
    validate_editorial_final_contract(contract_path, asset_root)
    expected.add(REPORT_NAME)
    manifest = {
        "schema": "maliev.pimm-editorial-native-release/v1",
        "release_id": contract["release_id"],
        "generation_id": contract["generation_id"],
        "approval": contract["approval"],
        "contract": {"path": str(contract_path), "sha256": sha256_file(contract_path)},
        "report": {"path": REPORT_NAME, "sha256": sha256_file(report_path)},
        "contact_sheet": report["contact_sheet"],
        "actual_pixel_disposition": report["actual_pixel_disposition"],
        "shots": report["shots"],
        "published_at": _utc_now(),
        "status": "accepted",
    }
    marker = staging / RELEASE_MANIFEST_NAME
    _exclusive_json(marker, manifest)  # marker written last
    expected.add(RELEASE_MANIFEST_NAME)
    observed = {path.name for path in staging.iterdir()}
    if observed != expected or any(path.is_dir() for path in staging.iterdir()):
        marker.unlink(missing_ok=True)
        raise ValueError("native final release tree contains extra or missing files")
    validate_editorial_final_contract(contract_path, asset_root)
    target = parent / str(contract["release_id"])
    if target.exists():
        marker.unlink(missing_ok=True)
        raise ValueError("native final release replay or competing publication")
    os.rename(staging, target)
    return target


def _arguments(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-shot", action="store_true")
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--staging-root", type=Path)
    parser.add_argument("--shot-id")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _arguments(
        list(argv) if argv is not None else sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    )
    if not arguments.render_shot or None in (arguments.asset_root, arguments.contract, arguments.staging_root, arguments.shot_id):
        raise ValueError("native final worker requires render-shot, asset-root, contract, staging-root, and shot-id")
    import bpy
    result = _render_worker(
        bpy,
        asset_root=arguments.asset_root.resolve(),
        contract_path=arguments.contract.resolve(),
        staging_root=arguments.staging_root.resolve(),
        shot_id=str(arguments.shot_id),
    )
    print(WORKER_MARKER + json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
