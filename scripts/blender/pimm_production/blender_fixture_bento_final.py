"""Resumably render the owner-approved 8:11 fixture-mounting animation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.blender.pimm_production.blender_bento_final import checked_file
from scripts.blender.pimm_production.blender_bento_r22_native import save_float_master
from scripts.blender.pimm_production.io_contract import sha256_file
from scripts.blender.pimm_production.paths import ASSET_ROOT, REPO_ROOT, require_within


APPROVAL = REPO_ROOT / "docs/pimm-blender-governance/fixture-bento-portrait-approval.json"
GENERATION = "fixture-mounting-20260904-portrait-final-01"
OUTPUT = ASSET_ROOT / "renders/final" / GENERATION
EXPECTED_PROOF_SCHEMA = "maliev.pimm-fixture-bento-portrait-proof/v1"
EXPECTED_APPROVAL_SCHEMA = "maliev.pimm-fixture-bento-portrait-approval/v1"


def approved_contract() -> tuple[dict, dict]:
    approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
    if (
        approval.get("schema") != EXPECTED_APPROVAL_SCHEMA
        or approval.get("decision") != "approved"
        or approval.get("owner") != "store owner"
    ):
        raise ValueError("Exact fixture portrait owner approval required")

    proof_path = require_within(
        Path(approval["proof_manifest_path"]), ASSET_ROOT / "renders/proofs"
    )
    checked_file(proof_path, approval["proof_manifest_sha256"])
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    checked_file(
        require_within(Path(approval["proof_video_path"]), proof_path.parent),
        approval["proof_video_sha256"],
    )
    checked_file(
        require_within(Path(approval["scene_path"]), proof_path.parent),
        approval["scene_sha256"],
    )
    if proof.get("schema") != EXPECTED_PROOF_SCHEMA:
        raise ValueError("Wrong fixture portrait proof schema")
    if proof.get("scene", {}).get("sha256", "").upper() != approval["scene_sha256"]:
        raise ValueError("Approved fixture portrait scene drifted")

    proof_contract = proof.get("contract", {})
    final_contract = approval.get("final_contract", {})
    invariant_fields = (
        "aspect_ratio",
        "fps",
        "frames",
        "duration_seconds",
        "camera",
        "camera_lens_mm",
        "camera_sensor_fit",
        "camera_shift_y",
    )
    if any(proof_contract.get(field) != final_contract.get(field) for field in invariant_fields):
        raise ValueError("Approved final changed proof camera or timing")
    if final_contract.get("resolution") != [800, 1100] or final_contract.get("samples") != 48:
        raise ValueError("Wrong approved fixture portrait delivery settings")
    return approval, proof


def frame_path(index: int) -> Path:
    if type(index) is not int or not 1 <= index <= 912:
        raise ValueError("Invalid fixture portrait frame")
    return require_within(OUTPUT / "frames" / f"frame-{index:04d}.png", ASSET_ROOT / "renders/final")


def validate_png(path: Path, size: list[int]) -> None:
    with path.open("rb") as stream:
        header = stream.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or list(struct.unpack(">II", header[16:24])) != size:
        raise ValueError(f"Wrong native PNG size: {path}")


def validate_frame(record: dict, output: Path, authority: dict, index: int) -> None:
    if record.get("index") != index or record.get("authority") != authority:
        raise ValueError("Fixture portrait frame authority changed")
    if not os.path.samefile(record["path"], output):
        raise ValueError("Wrong fixture portrait frame path")
    checked_file(output, record["sha256"])
    validate_png(output, [800, 1100])
    exr = output.with_suffix(".exr")
    if not os.path.samefile(record["exr_path"], exr):
        raise ValueError("Wrong fixture portrait EXR path")
    checked_file(exr, record["exr_sha256"])
    with exr.open("rb") as stream:
        if stream.read(4) != b"\x76\x2f\x31\x01":
            raise ValueError("Expected native float EXR master")


def configure_gpu() -> None:
    import bpy

    preferences = bpy.context.preferences.addons["cycles"].preferences
    preferences.refresh_devices()
    preferences.compute_device_type = "OPTIX"
    for device in preferences.devices:
        device.use = device.type == "OPTIX"
    if not any(device.use for device in preferences.devices):
        raise RuntimeError("Approved OptiX GPU unavailable")


def main() -> None:
    import bpy

    approval, _proof = approved_contract()
    authority = {
        "approval_sha256": sha256_file(APPROVAL),
        "proof_manifest_sha256": approval["proof_manifest_sha256"],
        "proof_video_sha256": approval["proof_video_sha256"],
        "scene_sha256": approval["scene_sha256"],
        "worker_sha256": sha256_file(Path(__file__)),
    }
    bpy.ops.wm.open_mainfile(filepath=approval["scene_path"])
    scene = bpy.context.scene
    contract = approval["final_contract"]
    if scene.camera is None or scene.camera.name != contract["camera"]:
        raise ValueError("Approved fixture portrait camera unavailable")
    if (
        scene.frame_start != 1
        or scene.frame_end != contract["frames"]
        or scene.render.fps != contract["fps"]
        or scene.render.fps_base != 1
        or scene.camera.data.lens != contract["camera_lens_mm"]
        or scene.camera.data.sensor_fit != contract["camera_sensor_fit"]
        or scene.camera.data.shift_y != contract["camera_shift_y"]
    ):
        raise ValueError("Approved fixture portrait scene camera or timing changed")

    if scene.render.engine != "CYCLES":
        raise ValueError("Approved fixture portrait render engine changed")
    scene.render.resolution_x, scene.render.resolution_y = contract["resolution"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.render.use_persistent_data = True
    scene.render.image_settings.compression = 25
    scene.render.fps = contract["fps"]
    scene.cycles.samples = contract["samples"]
    scene.cycles.use_denoising = True
    configure_gpu()

    print("FIXTURE_FINAL_START=800x1100:24fps:912 frames", flush=True)
    records = []
    for index in range(1, contract["frames"] + 1):
        output = frame_path(index)
        receipt = output.with_suffix(".json")
        if receipt.exists():
            record = json.loads(receipt.read_text(encoding="utf-8"))
            validate_frame(record, output, authority, index)
        else:
            exr = output.with_suffix(".exr")
            if output.exists() or exr.exists():
                raise FileExistsError("Unreceipted fixture output preserved for investigation")
            output.parent.mkdir(parents=True, exist_ok=True)
            scene.frame_set(index)
            scene.render.filepath = str(output)
            started = time.perf_counter()
            bpy.ops.render.render(write_still=True)
            save_float_master(scene, exr)
            record = {
                "index": index,
                "path": str(output),
                "sha256": sha256_file(output),
                "exr_path": str(exr),
                "exr_sha256": sha256_file(exr),
                "authority": authority,
                "render_seconds": time.perf_counter() - started,
            }
            validate_frame(record, output, authority, index)
            receipt.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            print(f"FIXTURE_FINAL_FRAME={index}/912 seconds={record['render_seconds']:.2f}", flush=True)
        records.append(record)

    checked_file(APPROVAL, authority["approval_sha256"])
    checked_file(Path(approval["scene_path"]), authority["scene_sha256"])
    result = {
        "schema": "maliev.pimm-fixture-bento-portrait-final/v1",
        "generation": GENERATION,
        "contract": contract,
        "authority": authority,
        "frames": records,
    }
    manifest = OUTPUT / "final.json"
    if manifest.exists() and json.loads(manifest.read_text(encoding="utf-8")) != result:
        raise ValueError("Immutable fixture portrait final manifest differs")
    if not manifest.exists():
        manifest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("FIXTURE_FINAL_READY=" + str(manifest), flush=True)


if __name__ == "__main__":
    main()
    os._exit(0)
