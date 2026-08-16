"""Fixture-only contract tests for PIMM owner approval and immutable releases."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import os
import struct
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image

from scripts.blender.pimm_production.approval_manifest import (
    record_decision,
    validate_approval,
    validate_approval_payload,
)
import scripts.blender.pimm_production.approval_manifest as approval_module
import scripts.blender.pimm_production.blender_final_render as final_module
from scripts.blender.pimm_production.blender_final_render import authorize_final_render, run_authorized_final
from scripts.blender.pimm_production.io_contract import sha256_file
import scripts.blender.pimm_production.proof_contract as proof_module
from scripts.blender.pimm_production.release_manifest import build_release_manifest
import scripts.blender.pimm_production.release_manifest as release_module
from scripts.blender.pimm_production.tests import test_proof_contract as proof_fixtures


SHOT_ID = "pimm-30g--hero--three-quarter"
RELEASE_ID = "release-2026-08-15-r01"
BLENDER = Path(r"D:\Blender 5.2\blender.exe")
REPO_ROOT = Path(__file__).resolve().parents[4]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _fingerprint(path: Path) -> dict[str, object]:
    stat_result = path.stat()
    return {
        "path": str(path.resolve()),
        "bytes": stat_result.st_size,
        "mtime_ns": stat_result.st_mtime_ns,
        "sha256": _sha256(path),
    }


def _canonical_fixture_sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest().upper()


def _fixture_region_metrics(
    pixels: list[tuple[int, int, int, int]], width: int, box: list[int]
) -> dict[str, object]:
    """Independently derive exact pixel/mask evidence for one fixture region."""

    left, top, right, bottom = box
    region = [
        pixels[y * width + x]
        for y in range(top, bottom + 1)
        for x in range(left, right + 1)
    ]
    visible = [pixel for pixel in region if pixel[3] > 0]
    rgba_bytes = bytes(channel for pixel in region for channel in pixel)
    mask_bytes = bytes(255 if pixel[3] > 0 else 0 for pixel in region)
    visible_rgb_bytes = bytes(channel for pixel in visible for channel in pixel[:3])
    return {
        "region": box,
        "rgba_sha256": hashlib.sha256(rgba_bytes).hexdigest().upper(),
        "product_mask_sha256": hashlib.sha256(mask_bytes).hexdigest().upper(),
        "visible_rgb_sha256": hashlib.sha256(visible_rgb_bytes).hexdigest().upper(),
        "visible_pixels": len(visible),
        "unique_rgb_values": len({pixel[:3] for pixel in visible}),
    }


def _fixture_controller_patterns(
    pixels: list[tuple[int, int, int, int]],
    width: int,
    box: list[int],
    digit_count: int,
) -> list[str]:
    """Sample seven physical regions per controller digit from real fixture pixels."""

    left, top, right, bottom = box
    visible_luma = [
        sum(pixels[y * width + x][:3])
        for y in range(top, bottom + 1)
        for x in range(left, right + 1)
        if pixels[y * width + x][3] > 0
    ]
    threshold = (min(visible_luma) + max(visible_luma)) / 2
    samples = ((0.5, 0.1), (0.2, 0.3), (0.8, 0.3), (0.5, 0.5),
               (0.2, 0.7), (0.8, 0.7), (0.5, 0.9))
    region_width = right - left + 1
    region_height = bottom - top + 1
    patterns: list[str] = []
    for digit in range(digit_count):
        digit_left = left + digit * region_width / digit_count
        digit_right = left + (digit + 1) * region_width / digit_count - 1
        bits = []
        for x_fraction, y_fraction in samples:
            x = round(digit_left + max(0, digit_right - digit_left) * x_fraction)
            y = round(top + max(0, region_height - 1) * y_fraction)
            pixel = pixels[y * width + min(right, max(left, x))]
            bits.append("1" if pixel[3] > 0 and sum(pixel[:3]) > threshold else "0")
        patterns.append("".join(bits))
    return patterns


def _fixture_png_evidence(path: Path) -> tuple[int, int, list[tuple[int, int, int, int]], dict[str, object]]:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        pixels = list(rgba.get_flattened_data())
    visible = [pixel for pixel in pixels if pixel[3] > 0]
    visible_indices = [index for index, pixel in enumerate(pixels) if pixel[3] > 0]
    xs = [index % width for index in visible_indices]
    ys = [index // width for index in visible_indices]
    rgba_bytes = bytes(channel for pixel in pixels for channel in pixel)
    mask_bytes = bytes(255 if pixel[3] > 0 else 0 for pixel in pixels)
    return width, height, pixels, {
        "file_sha256": _sha256(path),
        "rgba_sha256": hashlib.sha256(rgba_bytes).hexdigest().upper(),
        "product_mask_sha256": hashlib.sha256(mask_bytes).hexdigest().upper(),
        "subject_bounds": [min(xs), min(ys), max(xs), max(ys)],
        "visible_pixels": len(visible),
        "visible_fraction": round(len(visible) / len(pixels), 8),
    }


def _fixture_final_qa(
    png: Path,
    approval: dict[str, object],
    endpoints: dict[str, Path],
) -> dict[str, object]:
    """Hand-derived Task 6 QA fixture, independent of the production builder."""

    width, height, pixels, product = _fixture_png_evidence(png)
    bounds = product["subject_bounds"]
    assert isinstance(bounds, list)
    left, top, right, bottom = bounds
    split = left + max(1, ((right - left + 1) * 2) // 3)
    material_box = [left, top, split - 1, bottom]
    controller_box = [split, top, right, bottom]
    material = _fixture_region_metrics(pixels, width, material_box)
    controller = _fixture_region_metrics(pixels, width, controller_box)
    alpha_bytes = bytes(pixel[3] for pixel in pixels)
    machine_path = (
        REPO_ROOT / "scripts" / "blender" / "pimm_production" / "contracts" / "machines" / "30g.json"
    )
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    evidence = approval["evidence"]
    assert isinstance(evidence, dict)
    scene_contract = json.loads(Path(evidence["scene_contract"]["path"]).read_text(encoding="utf-8"))
    digit_count = sum(len(value) for value in machine["controller"]["display_values"])
    patterns = _fixture_controller_patterns(pixels, width, controller_box, digit_count)
    endpoint_records = []
    for label in ("start", "end"):
        endpoint_width, endpoint_height, _, endpoint = _fixture_png_evidence(endpoints[label])
        assert (endpoint_width, endpoint_height) == (width, height)
        endpoint_records.append({"label": label, **endpoint})
    return {
        "schema": "pimm-final-qa/v1",
        "dimensions": [width, height],
        "product": {key: value for key, value in product.items() if key != "file_sha256"},
        "material": {
            "material_library_sha256": approval["inputs"]["material_library_sha256"],
            "scene_contract_sha256": evidence["scene_contract"]["sha256"],
            **material,
        },
        "alpha": {
            "channel_sha256": hashlib.sha256(alpha_bytes).hexdigest().upper(),
            "minimum": min(alpha_bytes),
            "maximum": max(alpha_bytes),
            "nonzero_pixels": sum(value > 0 for value in alpha_bytes),
            "partial_pixels": sum(0 < value < 255 for value in alpha_bytes),
        },
        "controller": {
            "machine_contract_sha256": _sha256(machine_path),
            "controller_contract_sha256": _canonical_fixture_sha(machine["controller"]),
            **controller,
            "digit_patterns": patterns,
            "active_segment_count": sum(pattern.count("1") for pattern in patterns),
            "segment_mask_sha256": hashlib.sha256("".join(patterns).encode("ascii")).hexdigest().upper(),
        },
        "animation": {
            "contract_sha256": _canonical_fixture_sha(
                {"machine": machine["animation"], "scene": scene_contract["animation_contract"]}
            ),
            "status": machine["animation"]["status"],
            "endpoints": endpoint_records,
            "identical": True,
        },
    }


def _proof_manifest(
    root: Path,
    scene_sha256: str,
    generation_id: str = "proof-20260815T153000Z-a1b2c3d",
) -> Path:
    """Write a genuine Task 5 proof manifest and all on-disk authorities."""

    del scene_sha256  # the fixture derives all pins from real bytes
    root.mkdir(parents=True, exist_ok=True)
    inputs = root / "inputs"
    inputs.mkdir(exist_ok=True)
    source = inputs / "source.step"
    master = inputs / "PIMM-30G-MASTER.blend"
    material = inputs / "PIMM-MATERIAL-LIBRARY.blend"
    scene_path = inputs / "scene.blend"
    native_scene = scene_path.exists()
    source.write_bytes(b"authoritative STEP")
    master.write_bytes(b"authoritative master")
    material.write_bytes(b"authoritative material library")
    if not scene_path.exists():
        scene_path.write_bytes(b"authoritative fixture scene")

    base_contract = proof_fixtures.composition_contract()
    contract = dataclasses.replace(
        base_contract,
        generation_id=generation_id,
        scene_sha256=_sha256(scene_path),
        master_sha256=_sha256(master),
        material_library_sha256=_sha256(material),
        output_root=f"renders/proofs/{generation_id}",
    )
    base_scene = proof_fixtures.scene_contract_fixture()
    scene = dataclasses.replace(
        base_scene,
        master_sha256=contract.master_sha256,
        material_library_sha256=contract.material_library_sha256,
        output_contract={"width": 64, "height": 48, "alpha": True},
    )
    proof_fixtures._write_scene_contract(root, scene, contract.scene_contract_path)
    proof_root = root / "renders" / "proofs" / generation_id
    proof_root.mkdir(parents=True)
    metadata = proof_fixtures._valid_render_metadata(contract, actual_dimensions=[16, 12])
    metadata["base_dimensions"] = [64, 48]
    tool_binary = BLENDER if native_scene else root / "tools" / "blender.exe"
    if tool_binary != BLENDER:
        tool_binary.parent.mkdir(parents=True)
        tool_binary.write_bytes(b"fixture Blender binary")
    metadata["blender"] = {
        "binary_path": str(tool_binary.resolve()),
        "binary_sha256": _sha256(tool_binary),
        "version": "5.2.0",
    }
    records = {
        "source": _fingerprint(source),
        "master": _fingerprint(master),
        "material_library": _fingerprint(material),
        "scene": _fingerprint(scene_path),
    }
    metadata["fingerprints"] = {"before": copy.deepcopy(records), "after": copy.deepcopy(records)}

    if tool_binary == BLENDER:
        capture_path = root / "captured-authored-settings.json"
        expression = "\n".join(
            (
                "import json, pathlib, sys",
                f"sys.path.insert(0, {str(REPO_ROOT)!r})",
                "from scripts.blender.pimm_production.blender_proof_render import _capture_authored_settings",
                f"pathlib.Path({str(capture_path)!r}).write_text(json.dumps(_capture_authored_settings(__import__('bpy')), sort_keys=True), encoding='utf-8')",
            )
        )
        result = subprocess.run(
            [str(BLENDER), "--factory-startup", "-b", str(scene_path), "--python-expr", expression],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise AssertionError(result.stderr)
        authored = json.loads(capture_path.read_text(encoding="utf-8"))
        metadata["authored_settings"] = {"before": authored, "after": copy.deepcopy(authored)}

    proof_fixtures._write_manifest_evidence(root, proof_root, contract, scene, metadata)
    outputs: list[Path] = []
    for background, color in (
        ("rgba", (30, 40, 50, 160)),
        ("white", (230, 230, 230, 255)),
        ("checker", (120, 130, 140, 255)),
        ("dark", (20, 25, 30, 255)),
    ):
        output = proof_root / f"{SHOT_ID}--{background}.png"
        Image.new("RGBA", (16, 12), color).save(output)
        outputs.append(output)
    with patch.object(proof_module, "ASSET_ROOT", root.resolve()):
        proof = proof_module.write_proof_manifest(contract, outputs)
    Image.new("RGBA", (64, 48), (255, 255, 255, 255)).save(proof_root / "contact-sheet.png")
    return proof


def write_approval_fixture(
    root: Path,
    decision: str,
    scene_sha256: str,
    *,
    generation_id: str = "proof-20260815T153000Z-a1b2c3d",
) -> tuple[Path, Path]:
    """Write a complete approval and matching final contract for fixture tests."""

    proof_path = _proof_manifest(root, scene_sha256, generation_id)
    approval_path = record_decision(proof_path, SHOT_ID, decision, "natth", "fixture review")
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    final = {
        "schema": "pimm-final-render-contract/v1",
        "release_id": RELEASE_ID,
        "shot_id": SHOT_ID,
        "generation_id": approval["proof_generation_id"],
        "authority_roots": approval["authority_roots"],
        "evidence": approval["evidence"],
        "inputs": approval["inputs"],
        "render_settings": approval["render_settings"],
        "samples": 128,
        "output_root": f"renders/final/{RELEASE_ID}",
        "deliverables": ["exr", "png", "webp"],
        "asset_root": approval["authority_roots"]["asset"],
        "scene_path": approval["evidence"]["scene"]["path"],
    }
    final_path = _write_json(root / "contracts" / "final.json", final)
    return approval_path, final_path


def _write_nonuniform_final_fixture(path: Path) -> None:
    """Write explicit material and controller pixel regions without production helpers."""

    pixels: list[tuple[int, int, int, int]] = []
    for y in range(48):
        for x in range(64):
            if x < 42:
                pixels.append((40 + (x * 3) % 90, 70 + (y * 5) % 80, 120 + (x + y) % 80, 160))
            else:
                bright = (x + 2 * y) % 7 in {0, 1, 4}
                pixels.append((220, 45 + y % 20, 20, 220) if bright else (15, 20, 25 + x % 12, 180))
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.frombytes("RGBA", (64, 48), bytes(channel for pixel in pixels for channel in pixel)).save(path)


def write_release_output_fixture(root: Path, generation_id: str) -> Path:
    """Write one complete final-output manifest with a transparent delivery family."""

    approval_path, final_contract_path = write_approval_fixture(
        root, "approved", "a" * 64, generation_id=generation_id
    )
    authorization = authorize_final_render(approval_path, final_contract_path)
    output_root = root / "renders" / "final" / RELEASE_ID / SHOT_ID
    output_root.mkdir(parents=True, exist_ok=True)
    outputs: list[dict[str, object]] = []
    png = output_root / f"{SHOT_ID}--transparent.png"
    _write_nonuniform_final_fixture(png)
    for extension, mime in (("png", "image/png"), ("webp", "image/webp")):
        path = output_root / f"{SHOT_ID}--transparent.{extension}"
        if extension == "webp":
            with Image.open(png) as image:
                image.save(path, format="WEBP", lossless=True)
        outputs.append(
            {
                "logical_asset_id": f"{SHOT_ID}--transparent-{extension}",
                "path": path.name,
                "sha256": _sha256(path),
                "dimensions": [64, 48],
                "alpha": True,
                "mime_type": mime,
            }
        )
    endpoints = {
        label: output_root / f"{SHOT_ID}--animation-{label}.png"
        for label in ("start", "end")
    }
    for path in endpoints.values():
        path.write_bytes(png.read_bytes())
    qa_evidence = [
        {
            "role": f"animation-{label}",
            "path": endpoints[label].name,
            "sha256": _sha256(endpoints[label]),
            "dimensions": [64, 48],
            "mime_type": "image/png",
        }
        for label in ("start", "end")
    ]
    exr = output_root / f"{SHOT_ID}--transparent.exr"
    _write_float_exr(exr, 64, 48)
    outputs.append(
        {
            "logical_asset_id": f"{SHOT_ID}--transparent-exr",
            "path": exr.name,
            "sha256": _sha256(exr),
            "dimensions": [64, 48],
            "alpha": True,
            "mime_type": "image/x-exr",
        }
    )
    manifest = {
        "schema": "pimm-final-output-manifest/v1",
        "release_id": RELEASE_ID,
        "generation_id": generation_id,
        "shot_id": SHOT_ID,
        "approval_path": str(authorization.approval_path),
        "approval_sha256": authorization.approval_sha256,
        "authorized_final_contract_path": str(authorization.final_contract_path),
        "authorized_final_contract_sha256": authorization.final_contract_sha256,
        "final_authorization_sha256": authorization.authorization_sha256,
        "output_root": f"renders/final/{RELEASE_ID}",
        "required_deliverables": ["exr", "png", "webp"],
        "qa": _fixture_final_qa(
            png,
            json.loads(approval_path.read_text(encoding="utf-8")),
            endpoints,
        ),
        "qa_evidence": qa_evidence,
        "outputs": outputs,
    }
    return _write_json(output_root / "final-output-manifest.json", manifest)


def _refresh_final_fixture_manifest(
    output: Path,
    payload: dict[str, object],
    *,
    preserve_qa_section: str | None = None,
) -> None:
    """Refresh fixture hashes/QA independently after an intentional pixel mutation."""

    family = output.parent
    for record in payload["outputs"]:
        record["sha256"] = _sha256(family / record["path"])
    endpoints = {
        record["role"].removeprefix("animation-"): family / record["path"]
        for record in payload["qa_evidence"]
    }
    for record in payload["qa_evidence"]:
        record["sha256"] = _sha256(family / record["path"])
    old_section = copy.deepcopy(payload["qa"].get(preserve_qa_section)) if preserve_qa_section else None
    approval = json.loads(Path(payload["approval_path"]).read_text(encoding="utf-8"))
    payload["qa"] = _fixture_final_qa(
        family / f"{SHOT_ID}--transparent.png",
        approval,
        endpoints,
    )
    if preserve_qa_section:
        payload["qa"][preserve_qa_section] = old_section
    _write_json(output, payload)


def _mutate_fixture_region_family(
    output: Path,
    x: int,
    y: int,
    color: tuple[int, int, int, int],
) -> None:
    """Apply one real pixel mutation to final and both contracted endpoints."""

    family = output.parent
    png_paths = [
        family / f"{SHOT_ID}--transparent.png",
        family / f"{SHOT_ID}--animation-start.png",
        family / f"{SHOT_ID}--animation-end.png",
    ]
    for path in png_paths:
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
        rgba.putpixel((x, y), color)
        rgba.save(path, format="PNG")
    with Image.open(png_paths[0]) as image:
        image.save(family / f"{SHOT_ID}--transparent.webp", format="WEBP", lossless=True)


def _write_uniform_fixture_family(output: Path) -> None:
    family = output.parent
    uniform = Image.new("RGBA", (64, 48), (30, 40, 50, 160))
    uniform.save(family / f"{SHOT_ID}--transparent.png", format="PNG")
    uniform.save(family / f"{SHOT_ID}--transparent.webp", format="WEBP", lossless=True)
    uniform.save(family / f"{SHOT_ID}--animation-start.png", format="PNG")
    uniform.save(family / f"{SHOT_ID}--animation-end.png", format="PNG")


def _write_float_exr(path: Path, width: int, height: int) -> None:
    """Write a minimal valid uncompressed scanline float-RGBA OpenEXR fixture."""

    def attribute(name: str, kind: str, value: bytes) -> bytes:
        return name.encode("ascii") + b"\0" + kind.encode("ascii") + b"\0" + struct.pack("<I", len(value)) + value

    channels = b""
    for name in ("A", "B", "G", "R"):
        channels += name.encode("ascii") + b"\0" + struct.pack("<I", 2) + b"\0\0\0\0" + struct.pack("<II", 1, 1)
    channels += b"\0"
    window = struct.pack("<iiii", 0, 0, width - 1, height - 1)
    header = b"v/1\x01" + struct.pack("<I", 2)
    header += attribute("channels", "chlist", channels)
    header += attribute("compression", "compression", b"\0")
    header += attribute("dataWindow", "box2i", window)
    header += attribute("displayWindow", "box2i", window)
    header += attribute("lineOrder", "lineOrder", b"\0")
    header += attribute("pixelAspectRatio", "float", struct.pack("<f", 1.0))
    header += attribute("screenWindowCenter", "v2f", struct.pack("<ff", 0.0, 0.0))
    header += attribute("screenWindowWidth", "float", struct.pack("<f", 1.0))
    header += b"\0"
    scanline_data = struct.pack("<f", 0.5) * (width * 4)
    chunks = [struct.pack("<iI", y, len(scanline_data)) + scanline_data for y in range(height)]
    cursor = len(header) + height * 8
    offsets: list[int] = []
    for chunk in chunks:
        offsets.append(cursor)
        cursor += len(chunk)
    path.write_bytes(header + struct.pack(f"<{height}Q", *offsets) + b"".join(chunks))


def _write_repeated_empty_chunk_exr(path: Path, width: int, height: int) -> None:
    """Write EXR-like bytes whose table repeats one empty scanline chunk."""

    _write_float_exr(path, width, height)
    data = bytearray(path.read_bytes())
    cursor = 8
    while True:
        name_end = data.index(0, cursor)
        if name_end == cursor:
            cursor += 1
            break
        cursor = name_end + 1
        kind_end = data.index(0, cursor)
        cursor = kind_end + 1
        size = struct.unpack_from("<I", data, cursor)[0]
        cursor += 4 + size
    first_chunk = struct.unpack_from("<Q", data, cursor)[0]
    for index in range(height):
        struct.pack_into("<Q", data, cursor + index * 8, first_chunk)
    struct.pack_into("<I", data, first_chunk + 4, 0)
    path.write_bytes(data)


def _swap_first_exr_scanline_offsets(path: Path) -> None:
    """Keep complete unique chunks but map the first table entries out of order."""

    data = bytearray(path.read_bytes())
    cursor = 8
    while True:
        name_end = data.index(0, cursor)
        if name_end == cursor:
            cursor += 1
            break
        cursor = name_end + 1
        kind_end = data.index(0, cursor)
        cursor = kind_end + 1
        size = struct.unpack_from("<I", data, cursor)[0]
        cursor += 4 + size
    first, second = struct.unpack_from("<QQ", data, cursor)
    struct.pack_into("<QQ", data, cursor, second, first)
    path.write_bytes(data)


def _declare_fake_zip_compression(path: Path) -> None:
    """Relabel uncompressed chunks as ZIPS without changing their payload bytes."""

    data = bytearray(path.read_bytes())
    marker = b"compression\0compression\0" + struct.pack("<I", 1)
    offset = data.index(marker) + len(marker)
    data[offset] = 2
    path.write_bytes(data)


class ApprovalReleaseTests(unittest.TestCase):
    def test_native_final_runner_is_an_explicit_authorized_operation(self) -> None:
        """Catches a final gate that authorizes data but cannot render native evidence."""

        self.assertTrue(callable(run_authorized_final))

    @unittest.skipUnless(BLENDER.is_file(), "fixture Blender runtime unavailable")
    def test_native_final_runner_emits_real_exr_png_webp_and_manifest(self) -> None:
        """Catches a final runner that claims release evidence without native media."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene_path = root / "inputs" / "scene.blend"
            scene_path.parent.mkdir(parents=True)
            setup = "\n".join((
                "import bpy",
                "bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))",
                "bpy.ops.object.camera_add(location=(0, -6, 0))",
                "camera = bpy.context.object",
                "camera.rotation_euler = (1.5708, 0, 0)",
                "bpy.context.scene.camera = camera",
                "bpy.context.scene.world = None",
                "bpy.context.scene.render.engine = 'CYCLES'",
                "bpy.ops.wm.save_as_mainfile(filepath=" + repr(str(scene_path)) + ")",
            ))
            result = subprocess.run(
                [str(BLENDER), "--factory-startup", "-b", "--python-expr", setup],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            approval_path, final_contract_path = write_approval_fixture(root, "approved", "a" * 64)
            manifest_path = run_authorized_final(approval_path, final_contract_path)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual({item["mime_type"] for item in manifest["outputs"]}, {"image/x-exr", "image/png", "image/webp"})
            self.assertTrue((manifest_path.parent / f"{SHOT_ID}--transparent.exr").read_bytes().startswith(b"v/1\x01"))
            with Image.open(manifest_path.parent / f"{SHOT_ID}--transparent.png") as png:
                self.assertEqual(png.mode, "RGBA")
                self.assertEqual(png.size, (64, 48))
            self.assertEqual(manifest["qa"]["dimensions"], [64, 48])
            self.assertEqual(
                [endpoint["label"] for endpoint in manifest["qa"]["animation"]["endpoints"]],
                ["start", "end"],
            )
            self.assertEqual(
                [record["role"] for record in manifest["qa_evidence"]],
                ["animation-start", "animation-end"],
            )
            for record in manifest["qa_evidence"]:
                self.assertEqual(_sha256(manifest_path.parent / record["path"]), record["sha256"])
            release_path = build_release_manifest(RELEASE_ID, [manifest_path])
            self.assertTrue(release_path.is_file())
            release_module._validate_release_tree_authority(release_path)

    def test_final_authorization_binds_native_and_effective_proof_dimensions_separately(self) -> None:
        """Catches a final contract that promotes reduced proof pixels to final resolution."""

        with TemporaryDirectory() as root_text:
            approval_path, final_contract_path = write_approval_fixture(
                Path(root_text), "approved", "a" * 64
            )
            authorization = authorize_final_render(approval_path, final_contract_path)
            final = json.loads(authorization.final_contract_path.read_text(encoding="utf-8"))
            self.assertIn("base_dimensions", final["render_settings"])
            self.assertIn("effective_proof_dimensions", final["render_settings"])
            self.assertEqual(final["render_settings"]["base_dimensions"], [64, 48])
            self.assertEqual(final["render_settings"]["effective_proof_dimensions"], [16, 12])
            self.assertEqual(final["render_settings"]["output_dimensions"], [64, 48])

            final["render_settings"]["output_dimensions"] = [16, 12]
            _write_json(final_contract_path, final)
            with self.assertRaisesRegex(ValueError, "output dimensions drift|original resolution"):
                authorize_final_render(approval_path, final_contract_path)

    def test_any_scene_drift_invalidates_approval(self) -> None:
        approval = {
            "schema_version": 1,
            "decision": "approved",
            "owner": "natth",
            "inputs": {"scene_sha256": "a" * 64},
        }
        errors = validate_approval_payload(approval, {"scene_sha256": "b" * 64})
        self.assertIn("scene SHA-256 drift", "\n".join(errors))

    def test_recorded_approval_is_hash_bound_revisioned_and_not_overwritten(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            proof = _proof_manifest(root, "a" * 64)
            first = record_decision(proof, SHOT_ID, "approved", "natth", "approved")
            second = record_decision(proof, SHOT_ID, "rejected", "natth", "amended")
            first_payload = json.loads(first.read_text(encoding="utf-8"))
            second_payload = json.loads(second.read_text(encoding="utf-8"))
            self.assertNotEqual(first, second)
            self.assertEqual(first_payload["revision"], 1)
            self.assertEqual(second_payload["revision"], 2)
            self.assertEqual(second_payload["prior_approval_sha256"], _sha256(first))
            self.assertEqual(validate_approval(first, first_payload["inputs"]), [])

    def test_later_rejection_revokes_an_older_approved_revision(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            proof = _proof_manifest(root, "a" * 64)
            approved = record_decision(proof, SHOT_ID, "approved", "natth", "approved")
            record_decision(proof, SHOT_ID, "rejected", "natth", "rejected later")
            _, final_contract = write_approval_fixture(root / "final", "approved", "a" * 64)
            with self.assertRaisesRegex(ValueError, "latest approval revision"):
                authorize_final_render(approved, final_contract)

    def test_proof_pixel_mutation_invalidates_recorded_approval(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval_path, _ = write_approval_fixture(root, "approved", "a" * 64)
            proof_pixel = root / "renders" / "proofs" / "proof-20260815T153000Z-a1b2c3d" / f"{SHOT_ID}--rgba.png"
            Image.new("RGBA", (16, 12), (1, 2, 3, 255)).save(proof_pixel)
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            self.assertIn("proof pixel SHA-256 drift", "\n".join(validate_approval(approval_path, approval["inputs"])))

    def test_source_file_mutation_invalidates_approval_on_disk(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval, _ = write_approval_fixture(root, "approved", "a" * 64)
            payload = json.loads(approval.read_text(encoding="utf-8"))
            source = Path(payload["evidence"]["source"]["path"])
            source.write_bytes(b"changed source")
            self.assertIn("proof evidence cannot be read", "\n".join(validate_approval(approval, {})))

    def test_validate_approval_returns_errors_for_unreadable_proof_evidence(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval_path, _ = write_approval_fixture(root, "approved", "a" * 64)
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            Path(approval["proof_manifest_path"]).write_text("{", encoding="utf-8")
            errors = validate_approval(approval_path, approval["inputs"])
            self.assertIn("proof evidence cannot be read", "\n".join(errors))

    def test_final_render_requires_approved_decision(self) -> None:
        with TemporaryDirectory() as root_text:
            approval_path, final_contract_path = write_approval_fixture(Path(root_text), "rejected", "a" * 64)
            with self.assertRaisesRegex(ValueError, "owner approval required"):
                authorize_final_render(approval_path, final_contract_path)

    def test_final_render_fails_closed_on_settings_and_dimension_drift(self) -> None:
        with TemporaryDirectory() as root_text:
            approval_path, final_contract_path = write_approval_fixture(Path(root_text), "approved", "a" * 64)
            payload = json.loads(final_contract_path.read_text(encoding="utf-8"))
            payload["render_settings"]["camera_sha256"] = "f" * 64
            payload["render_settings"]["output_dimensions"] = [65, 48]
            _write_json(final_contract_path, payload)
            with self.assertRaisesRegex(ValueError, "final render authorization failed") as error:
                authorize_final_render(approval_path, final_contract_path)
            self.assertIn("camera SHA-256 drift", str(error.exception))
            self.assertIn("output dimensions drift", str(error.exception))

    def test_final_render_rejects_each_approved_render_state_mutation(self) -> None:
        mutations = {
            "camera_sha256": "camera SHA-256 drift",
            "lights_sha256": "lights SHA-256 drift",
            "world_sha256": "world SHA-256 drift",
            "compositor_sha256": "compositor SHA-256 drift",
            "render_settings_sha256": "render settings SHA-256 drift",
            "composition_sha256": "composition SHA-256 drift",
        }
        for field, expected_error in mutations.items():
            with self.subTest(field=field), TemporaryDirectory() as root_text:
                approval_path, final_contract_path = write_approval_fixture(Path(root_text), "approved", "a" * 64)
                payload = json.loads(final_contract_path.read_text(encoding="utf-8"))
                payload["render_settings"][field] = "f" * 64
                _write_json(final_contract_path, payload)
                with self.assertRaisesRegex(ValueError, expected_error):
                    authorize_final_render(approval_path, final_contract_path)

    def test_owner_and_shot_are_required_for_an_approval(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            proof = _proof_manifest(root, "a" * 64)
            with self.assertRaisesRegex(ValueError, "shot_id is not present"):
                record_decision(proof, "pimm-30g--unknown", "approved", "natth", "review")
            approval_path, final_contract_path = write_approval_fixture(root / "missing-owner", "approved", "a" * 64)
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            approval["owner"] = ""
            _write_json(approval_path, approval)
            with self.assertRaisesRegex(ValueError, "owner approval required"):
                authorize_final_render(approval_path, final_contract_path)

    def test_final_render_allows_only_explicit_sampling_increase(self) -> None:
        with TemporaryDirectory() as root_text:
            approval_path, final_contract_path = write_approval_fixture(Path(root_text), "approved", "a" * 64)
            authorization = authorize_final_render(approval_path, final_contract_path)
            self.assertEqual(authorization.output_root.as_posix(), f"renders/final/{RELEASE_ID}")
            payload = json.loads(final_contract_path.read_text(encoding="utf-8"))
            payload["samples"] = payload["render_settings"]["proof_samples"]
            _write_json(final_contract_path, payload)
            with self.assertRaisesRegex(ValueError, "sampling increase"):
                authorize_final_render(approval_path, final_contract_path)

    def test_release_rejects_mixed_generations(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            outputs = [
                write_release_output_fixture(root / "one", "proof-20260815T153000Z-a1b2c3d"),
                write_release_output_fixture(root / "two", "proof-20260815T160000Z-d4e5f6a"),
            ]
            with self.assertRaisesRegex(ValueError, "mixed proof generations"):
                build_release_manifest(RELEASE_ID, outputs)

    def test_release_rejects_outputs_from_separate_immutable_roots(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            outputs = [
                write_release_output_fixture(root / "one", "proof-20260815T153000Z-a1b2c3d"),
                write_release_output_fixture(root / "two", "proof-20260815T153000Z-a1b2c3d"),
            ]
            with self.assertRaisesRegex(ValueError, "release output roots"):
                build_release_manifest(RELEASE_ID, outputs)

    def test_release_rejects_duplicate_assets_missing_exr_and_proof_paths(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            output = write_release_output_fixture(root, "proof-20260815T153000Z-a1b2c3d")
            payload = json.loads(output.read_text(encoding="utf-8"))
            duplicate = copy.deepcopy(payload["outputs"][0])
            payload["outputs"].append(duplicate)
            _write_json(output, payload)
            with self.assertRaisesRegex(ValueError, "duplicate logical asset ID"):
                build_release_manifest(RELEASE_ID, [output])

            output = write_release_output_fixture(root / "missing", "proof-20260815T153000Z-a1b2c3d")
            payload = json.loads(output.read_text(encoding="utf-8"))
            payload["outputs"] = [item for item in payload["outputs"] if item["mime_type"] != "image/x-exr"]
            _write_json(output, payload)
            with self.assertRaisesRegex(ValueError, "absent EXR"):
                build_release_manifest(RELEASE_ID, [output])

            output = write_release_output_fixture(root / "unsafe", "proof-20260815T153000Z-a1b2c3d")
            payload = json.loads(output.read_text(encoding="utf-8"))
            payload["output_root"] = "renders/proofs/proof-20260815T153000Z-a1b2c3d"
            _write_json(output, payload)
            with self.assertRaisesRegex(ValueError, "proof/archive/mutable"):
                build_release_manifest(RELEASE_ID, [output])

    def test_release_rejects_noncanonical_logical_asset_and_extra_family_member(self) -> None:
        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(Path(root_text), "proof-20260815T153000Z-a1b2c3d")
            payload = json.loads(output.read_text(encoding="utf-8"))
            payload["outputs"][0]["logical_asset_id"] = "counterfeit"
            _write_json(output, payload)
            with self.assertRaisesRegex(ValueError, "logical asset ID"):
                build_release_manifest(RELEASE_ID, [output])

    def test_approved_fixture_creates_atomic_release_manifest_last(self) -> None:
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            output = write_release_output_fixture(root, "proof-20260815T153000Z-a1b2c3d")
            release_path = build_release_manifest(RELEASE_ID, [output])
            release = json.loads(release_path.read_text(encoding="utf-8"))
            self.assertEqual(release["release_id"], RELEASE_ID)
            self.assertEqual(release["generation_id"], "proof-20260815T153000Z-a1b2c3d")
            self.assertEqual(len(release["assets"]), 3)
            self.assertEqual(release_path.name, "release-manifest.json")
            self.assertFalse(release_path.with_suffix(".json.tmp").exists())

    def test_release_recomputes_controller_and_animation_qa_from_pixels_and_contracts(self) -> None:
        """Catches caller-selected state hashes or mutable controller/endpoint metrics."""

        mutations = (
            ("controller", "active_segment_count", 99, "controller QA drift"),
            ("animation", "contract_sha256", "F" * 64, "animation QA drift"),
            ("product", "visible_pixels", 1, "product QA drift"),
        )
        for section, field, value, expected in mutations:
            with self.subTest(section=section, field=field), TemporaryDirectory() as root_text:
                output = write_release_output_fixture(
                    Path(root_text), "proof-20260815T153000Z-a1b2c3d"
                )
                payload = json.loads(output.read_text(encoding="utf-8"))
                payload["qa"][section][field] = value
                _write_json(output, payload)
                with self.assertRaisesRegex(ValueError, expected):
                    build_release_manifest(RELEASE_ID, [output])

    def test_release_independently_authenticates_distinct_animation_endpoint_files(self) -> None:
        """Catches missing, substituted, swapped, or changed endpoint pixel evidence."""

        for mutation in ("missing", "final-as-both", "swapped", "changed"):
            with self.subTest(mutation=mutation), TemporaryDirectory() as root_text:
                output = write_release_output_fixture(
                    Path(root_text), "proof-20260815T153000Z-a1b2c3d"
                )
                payload = json.loads(output.read_text(encoding="utf-8"))
                evidence = payload["qa_evidence"]
                start = output.parent / evidence[0]["path"]
                if mutation == "missing":
                    start.unlink()
                elif mutation == "final-as-both":
                    final_png = output.parent / f"{SHOT_ID}--transparent.png"
                    for record in evidence:
                        record["path"] = final_png.name
                        record["sha256"] = _sha256(final_png)
                    _write_json(output, payload)
                elif mutation == "swapped":
                    evidence[0]["path"], evidence[1]["path"] = (
                        evidence[1]["path"], evidence[0]["path"]
                    )
                    _write_json(output, payload)
                else:
                    with Image.open(start) as image:
                        changed = image.convert("RGBA")
                    changed.putpixel((5, 5), (255, 0, 255, 255))
                    changed.save(start, format="PNG")
                    evidence[0]["sha256"] = _sha256(start)
                    _write_json(output, payload)
                with self.assertRaisesRegex(ValueError, "endpoint|animation"):
                    build_release_manifest(RELEASE_ID, [output])
                self.assertFalse((output.parents[1] / "release-manifest.json").exists())

    def test_release_derives_material_and_controller_qa_from_dedicated_regions(self) -> None:
        """Catches copied controller claims, region drift, and uniform-frame counterfeits."""

        for mutation in (
            "false controller segments",
            "changed controller pixels",
            "changed material pixels",
            "uniform whole frame",
        ):
            with self.subTest(mutation=mutation), TemporaryDirectory() as root_text:
                output = write_release_output_fixture(
                    Path(root_text), "proof-20260815T153000Z-a1b2c3d"
                )
                payload = json.loads(output.read_text(encoding="utf-8"))
                if mutation == "false controller segments":
                    payload["qa"]["controller"]["digit_patterns"] = ["1111111"] * 6
                    payload["qa"]["controller"]["active_segment_count"] = 42
                    _write_json(output, payload)
                    expected = "controller"
                elif mutation == "changed controller pixels":
                    _mutate_fixture_region_family(output, 50, 20, (0, 255, 0, 255))
                    _refresh_final_fixture_manifest(
                        output, payload, preserve_qa_section="controller"
                    )
                    expected = "controller"
                elif mutation == "changed material pixels":
                    _mutate_fixture_region_family(output, 10, 20, (255, 255, 0, 255))
                    _refresh_final_fixture_manifest(
                        output, payload, preserve_qa_section="material"
                    )
                    expected = "material"
                else:
                    _write_uniform_fixture_family(output)
                    _refresh_final_fixture_manifest(output, payload)
                    expected = "uniform|material|controller|dedicated"
                with self.assertRaisesRegex(ValueError, expected):
                    build_release_manifest(RELEASE_ID, [output])
                self.assertFalse((output.parents[1] / "release-manifest.json").exists())

    def test_atomic_json_never_exposes_a_partial_final_path(self) -> None:
        """Catches writing directly into the authoritative JSON filename."""

        with TemporaryDirectory() as root_text:
            destination = Path(root_text) / "decision.json"
            observed_final_existence: list[bool] = []

            def fail_after_flush(descriptor: int) -> None:
                del descriptor
                observed_final_existence.append(destination.exists())
                raise OSError("injected fsync failure")

            with patch.object(approval_module.os, "fsync", side_effect=fail_after_flush):
                with self.assertRaisesRegex(OSError, "injected fsync failure"):
                    approval_module._create_new_json(destination, {"complete": True})
            self.assertEqual(observed_final_existence, [False])
            self.assertFalse(destination.exists())
            self.assertEqual(list(destination.parent.glob(".decision.json.*.pending")), [])

    def test_atomic_json_competitor_survives_pending_to_final_race(self) -> None:
        """Catches an atomic publisher that overwrites or deletes the competing final."""

        with TemporaryDirectory() as root_text:
            destination = Path(root_text) / "decision.json"
            competitor = b'{"competitor":true}\n'
            original_rename = approval_module.os.rename

            def inject_competitor(source: object, target: object) -> None:
                destination.write_bytes(competitor)
                original_rename(source, target)

            with patch.object(approval_module.os, "rename", side_effect=inject_competitor):
                with self.assertRaises((FileExistsError, ValueError)):
                    approval_module._create_new_json(destination, {"complete": True})
            self.assertEqual(destination.read_bytes(), competitor)
            self.assertEqual(list(destination.parent.glob(".decision.json.*.pending")), [])

    def test_final_contract_rehashes_every_authoritative_artifact_and_state(self) -> None:
        """Catches authorization that trusts approval/final JSON instead of current bytes."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            _, final_contract_path = write_approval_fixture(root, "approved", "a" * 64)
            evidence_names = tuple(
                json.loads(final_contract_path.read_text(encoding="utf-8"))["evidence"]
            )

        for name in evidence_names:
            with self.subTest(artifact=name), TemporaryDirectory() as root_text:
                root = Path(root_text)
                approval_path, final_contract_path = write_approval_fixture(
                    root, "approved", "a" * 64
                )
                final = json.loads(final_contract_path.read_text(encoding="utf-8"))
                record = final["evidence"][name]
                path = Path(str(record["path"]))
                if name in {"proof_runner", "final_runner", "machine_contract"}:
                    changed = copy.deepcopy(final)
                    changed["evidence"][name]["sha256"] = "f" * 64
                    _write_json(final_contract_path, changed)
                    with self.assertRaisesRegex(ValueError, rf"{name}.*drift|drift.*{name}"):
                        authorize_final_render(approval_path, final_contract_path)
                    _write_json(final_contract_path, final)
                    continue
                original = path.read_bytes()
                original_stat = path.stat()
                path.write_bytes(original + b" drift")
                with self.assertRaisesRegex(ValueError, rf"{name}.*drift|drift.*{name}"):
                    authorize_final_render(approval_path, final_contract_path)
                path.write_bytes(original)
                os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval_path, final_contract_path = write_approval_fixture(root, "approved", "a" * 64)
            final = json.loads(final_contract_path.read_text(encoding="utf-8"))
            for field in (
                "camera_sha256",
                "lights_sha256",
                "world_sha256",
                "compositor_sha256",
                "render_settings_sha256",
                "animation_sha256",
            ):
                with self.subTest(state=field):
                    changed = copy.deepcopy(final)
                    changed["render_settings"][field] = "f" * 64
                    _write_json(final_contract_path, changed)
                    with self.assertRaisesRegex(ValueError, field.replace("_sha256", "").replace("_", "[ _]")):
                        authorize_final_render(approval_path, final_contract_path)
            _write_json(final_contract_path, final)

    def test_approval_rejects_windows_path_aliases_without_touching_external_bytes(self) -> None:
        """Catches a PurePosix suffix check accepting Windows traversal/absolute aliases."""

        attacks = (r"..\outside.png", r"C:\outside.png", r"\\server\share\outside.png")
        for attack in attacks:
            with self.subTest(attack=attack), TemporaryDirectory() as root_text:
                root = Path(root_text)
                external = root / "outside.png"
                external.write_bytes(b"external sentinel")
                proof = _proof_manifest(root / "asset", "a" * 64)
                payload = json.loads(proof.read_text(encoding="utf-8"))
                payload["outputs"][0]["path"] = attack
                payload["outputs"][0]["sha256"] = _sha256(external)
                _write_json(proof, payload)
                with self.assertRaisesRegex(ValueError, "canonical"):
                    record_decision(proof, SHOT_ID, "approved", "natth", "reviewed")
                self.assertEqual(external.read_bytes(), b"external sentinel")

    @unittest.skipUnless(BLENDER.is_file(), "fixture Blender runtime unavailable")
    def test_native_final_rejects_a_preexisting_release_root_without_deleting_it(self) -> None:
        """Catches a runner that claims a family below somebody else's release root."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval_path, final_contract_path = write_approval_fixture(root, "approved", "a" * 64)
            release_root = root / "renders" / "final" / RELEASE_ID
            release_root.mkdir(parents=True)
            sentinel = release_root / "competing-owner.txt"
            sentinel.write_bytes(b"competitor")
            with self.assertRaisesRegex(ValueError, "release root already exists"):
                run_authorized_final(approval_path, final_contract_path)
            self.assertEqual(sentinel.read_bytes(), b"competitor")

    def test_release_requires_real_current_approval_and_final_authorization(self) -> None:
        """Catches a release manifest that accepts suffix-only approval hashes."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            payload["approval_sha256"] = "0" * 64
            _write_json(output, payload)
            with self.assertRaisesRegex(ValueError, "approval|authorization"):
                build_release_manifest(RELEASE_ID, [output])

    def test_release_rejects_a_magic_only_exr_without_float_rgba_channels(self) -> None:
        """Catches EXR validation that checks only the four-byte magic suffix."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            exr_record = next(item for item in payload["outputs"] if item["mime_type"] == "image/x-exr")
            exr = output.parent / exr_record["path"]
            exr.write_bytes(b"v/1\x01not-an-exr-header")
            exr_record["sha256"] = _sha256(exr)
            _write_json(output, payload)
            with self.assertRaisesRegex(ValueError, "EXR"):
                build_release_manifest(RELEASE_ID, [output])

    def test_exr_parser_rejects_repeated_empty_scanline_chunks(self) -> None:
        """Catches an EXR parser that checks offsets exist without coverage or payloads."""

        with TemporaryDirectory() as root_text:
            path = Path(root_text) / "repeated-empty.exr"
            _write_repeated_empty_chunk_exr(path, 64, 48)
            with self.assertRaisesRegex(ValueError, "EXR.*(unique|empty|coverage|chunk)"):
                release_module._validate_float_exr(path.read_bytes(), [64, 48])

    def test_exr_parser_rejects_scanline_offset_table_order_drift(self) -> None:
        """Catches unique complete chunks assigned to the wrong scanline table entry."""

        with TemporaryDirectory() as root_text:
            path = Path(root_text) / "swapped-offsets.exr"
            _write_float_exr(path, 64, 48)
            _swap_first_exr_scanline_offsets(path)
            with self.assertRaisesRegex(ValueError, "EXR.*(order|coordinate)"):
                release_module._validate_float_exr(path.read_bytes(), [64, 48])

    def test_exr_parser_rejects_invalid_compressed_payload_lengths(self) -> None:
        """Catches non-OpenEXR bytes hidden behind a supported compression label."""

        with TemporaryDirectory() as root_text:
            path = Path(root_text) / "fake-zip.exr"
            _write_float_exr(path, 64, 48)
            _declare_fake_zip_compression(path)
            with self.assertRaisesRegex(ValueError, "EXR.*(compressed|payload|ZIP)"):
                release_module._validate_float_exr(path.read_bytes(), [64, 48])

    def test_release_rejects_unmanifested_files_before_publishing_marker(self) -> None:
        """Catches a pass marker that ignores extra mutable release contents."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            extra = output.parents[1] / "unmanifested.tmp"
            extra.write_bytes(b"not approved")
            with self.assertRaisesRegex(ValueError, "extra|unmanifested"):
                build_release_manifest(RELEASE_ID, [output])
            self.assertFalse((output.parents[1] / "release-manifest.json").exists())

    def test_release_rejects_extra_family_directories_and_false_alpha_qa(self) -> None:
        """Catches incomplete entry scans and self-declared alpha evidence."""

        with self.subTest(mutation="extra directory"), TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            (output.parent / "mutable-cache").mkdir()
            with self.assertRaisesRegex(ValueError, "extra|unmanifested"):
                build_release_manifest(RELEASE_ID, [output])
            self.assertFalse((output.parents[1] / "release-manifest.json").exists())

        with self.subTest(mutation="false alpha QA"), TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            payload["qa"]["alpha"]["minimum"] = 0
            payload["qa"]["alpha"]["maximum"] = 255
            _write_json(output, payload)
            with self.assertRaisesRegex(ValueError, "alpha QA|alpha.*drift"):
                build_release_manifest(RELEASE_ID, [output])
            self.assertFalse((output.parents[1] / "release-manifest.json").exists())

    def test_competing_approval_revision_is_not_deleted_and_head_lock_is_released(self) -> None:
        """Catches revision selection without an exclusive chain-head claim."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            proof = _proof_manifest(root, "a" * 64)
            original_create = approval_module._create_new_json
            competitor = b'{"competitor":true}\n'

            def inject_revision(path: Path, payload: dict[str, object]) -> dict[str, object]:
                self.assertTrue((path.parent / ".approval-head.lock").is_file())
                path.write_bytes(competitor)
                return original_create(path, payload)

            with patch.object(approval_module, "_create_new_json", side_effect=inject_revision):
                with self.assertRaises(FileExistsError):
                    record_decision(proof, SHOT_ID, "approved", "natth", "reviewed")
            approval_dir = proof.parent / "approvals" / SHOT_ID
            self.assertEqual((approval_dir / "approval-r01.json").read_bytes(), competitor)
            self.assertFalse((approval_dir / ".approval-head.lock").exists())

    def test_competing_release_root_race_keeps_competitor_and_removes_only_stage(self) -> None:
        """Catches a final publisher overwriting a root that appears after QA."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval_path, final_contract_path = write_approval_fixture(root, "approved", "a" * 64)
            final = json.loads(final_contract_path.read_text(encoding="utf-8"))
            proof_manifest = Path(final["evidence"]["proof_manifest"]["path"])
            proof = json.loads(proof_manifest.read_text(encoding="utf-8"))
            authored = proof["render"]["authored_settings"]["before"]
            dimensions = tuple(final["render_settings"]["output_dimensions"])

            def fake_blender(*args: object, **kwargs: object) -> SimpleNamespace:
                del args, kwargs
                stage = next((root / "renders" / "final").glob(f".{RELEASE_ID}-*.stage"))
                family = stage / SHOT_ID
                _write_json(family / ".native-state.json", authored)
                png = family / f"{SHOT_ID}--transparent.png"
                _write_nonuniform_final_fixture(png)
                (family / f"{SHOT_ID}--animation-start.png").write_bytes(png.read_bytes())
                (family / f"{SHOT_ID}--animation-end.png").write_bytes(png.read_bytes())
                _write_float_exr(
                    family / f"{SHOT_ID}--transparent.exr", dimensions[0], dimensions[1]
                )
                return SimpleNamespace(returncode=0, stderr="", stdout="fixture Blender")

            original_rename = final_module.os.rename
            competitor_root = root / "renders" / "final" / RELEASE_ID

            def inject_root(source: object, destination: object) -> None:
                if Path(destination) != competitor_root:
                    original_rename(source, destination)
                    return
                self.assertNotEqual(Path(source), competitor_root)
                competitor_root.mkdir()
                (competitor_root / "competing-owner.txt").write_bytes(b"competitor")
                original_rename(source, destination)

            with (
                patch.object(final_module.subprocess, "run", side_effect=fake_blender),
                patch.object(final_module.os, "rename", side_effect=inject_root),
            ):
                with self.assertRaisesRegex(ValueError, "competing publication"):
                    run_authorized_final(approval_path, final_contract_path)
            self.assertEqual((competitor_root / "competing-owner.txt").read_bytes(), b"competitor")
            self.assertEqual(list((root / "renders" / "final").glob(f".{RELEASE_ID}-*.stage")), [])

    def test_native_final_rejects_nonidentical_static_animation_endpoint_pixels(self) -> None:
        """Catches animation QA that hashes authored claims instead of real endpoint renders."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval_path, final_contract_path = write_approval_fixture(root, "approved", "a" * 64)
            final = json.loads(final_contract_path.read_text(encoding="utf-8"))
            proof = json.loads(Path(final["evidence"]["proof_manifest"]["path"]).read_text(encoding="utf-8"))
            authored = proof["render"]["authored_settings"]["before"]
            dimensions = tuple(final["render_settings"]["output_dimensions"])

            def fake_blender(*args: object, **kwargs: object) -> SimpleNamespace:
                del args, kwargs
                stage = next((root / "renders" / "final").glob(f".{RELEASE_ID}-*.stage"))
                family = stage / SHOT_ID
                _write_json(family / ".native-state.json", authored)
                png = family / f"{SHOT_ID}--transparent.png"
                _write_nonuniform_final_fixture(png)
                _write_float_exr(
                    family / f"{SHOT_ID}--transparent.exr", dimensions[0], dimensions[1]
                )
                start = family / f"{SHOT_ID}--animation-start.png"
                end = family / f"{SHOT_ID}--animation-end.png"
                start.write_bytes(png.read_bytes())
                end.write_bytes(png.read_bytes())
                with Image.open(end) as image:
                    changed = image.convert("RGBA")
                changed.putpixel((5, 5), (200, 1, 2, 160))
                changed.save(end, format="PNG")
                return SimpleNamespace(returncode=0, stderr="", stdout="fixture Blender")

            with patch.object(final_module.subprocess, "run", side_effect=fake_blender):
                with self.assertRaisesRegex(ValueError, "animation endpoint|endpoint parity"):
                    run_authorized_final(approval_path, final_contract_path)
            self.assertFalse((root / "renders" / "final" / RELEASE_ID).exists())

    def test_competing_release_marker_is_not_overwritten_or_deleted(self) -> None:
        """Catches a marker race between validation and immutable publication."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            original_create = release_module._create_new_json
            competitor = b'{"competitor":true}\n'

            def inject_marker(
                path: Path, payload: dict[str, object], **kwargs: object
            ) -> dict[str, object]:
                path.write_bytes(competitor)
                return original_create(path, payload, **kwargs)

            with patch.object(release_module, "_create_new_json", side_effect=inject_marker):
                with self.assertRaisesRegex(ValueError, "already exists"):
                    build_release_manifest(RELEASE_ID, [output])
            marker = output.parents[1] / "release-manifest.json"
            self.assertEqual(marker.read_bytes(), competitor)
            self.assertTrue(output.is_file())

    def test_release_holds_approval_head_authority_through_marker_commit(self) -> None:
        """Catches a rejection landing after authorization but before the pass marker."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            approval = Path(payload["approval_path"])
            proof = Path(json.loads(approval.read_text(encoding="utf-8"))["proof_manifest_path"])
            attempted = False
            original_create = release_module._create_new_json

            def inject_rejection(path: Path, manifest: dict[str, object], **kwargs: object) -> dict[str, object]:
                nonlocal attempted
                attempted = True
                record_decision(proof, SHOT_ID, "rejected", "natth", "injected before marker")
                return original_create(path, manifest, **kwargs)

            with patch.object(release_module, "_create_new_json", side_effect=inject_rejection):
                with self.assertRaises((FileExistsError, ValueError)):
                    build_release_manifest(RELEASE_ID, [output])
            self.assertTrue(attempted)
            self.assertFalse((output.parents[1] / "release-manifest.json").exists())
            self.assertFalse((approval.parent / "approval-r02.json").exists())
            record_decision(proof, SHOT_ID, "rejected", "natth", "after lock release")

    def test_release_commit_rejects_transient_source_mutate_restore(self) -> None:
        """Catches a commit point that sees restored bytes but loses change identity."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            approval_payload = json.loads(Path(payload["approval_path"]).read_text(encoding="utf-8"))
            source = Path(approval_payload["evidence"]["source"]["path"])
            original = source.read_bytes()
            original_stat = source.stat()
            injected = False
            original_create = release_module._create_new_json

            def inject_transient_drift(
                path: Path, manifest: dict[str, object], **kwargs: object
            ) -> dict[str, object]:
                nonlocal injected
                injected = True
                source.write_bytes(b"transient attacker bytes")
                source.write_bytes(original)
                os.utime(source, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
                return original_create(path, manifest, **kwargs)

            with patch.object(release_module, "_create_new_json", side_effect=inject_transient_drift):
                with self.assertRaisesRegex(ValueError, "source.*drift|evidence drift|identity"):
                    build_release_manifest(RELEASE_ID, [output])
            self.assertTrue(injected)
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse((output.parents[1] / "release-manifest.json").exists())

    def test_release_commit_rescan_rejects_late_file_and_directory(self) -> None:
        """Catches a release tree rescan performed only before marker staging."""

        for kind in ("file", "directory"):
            with self.subTest(kind=kind), TemporaryDirectory() as root_text:
                output = write_release_output_fixture(
                    Path(root_text), "proof-20260815T153000Z-a1b2c3d"
                )
                release_root = output.parents[1]
                injected = False
                original_create = release_module._create_new_json

                def inject_entry(
                    path: Path, manifest: dict[str, object], **kwargs: object
                ) -> dict[str, object]:
                    nonlocal injected
                    injected = True
                    late = release_root / f"late-{kind}"
                    late.write_bytes(b"late") if kind == "file" else late.mkdir()
                    return original_create(path, manifest, **kwargs)

                with patch.object(release_module, "_create_new_json", side_effect=inject_entry):
                    with self.assertRaisesRegex(ValueError, "extra|rescan|release tree"):
                        build_release_manifest(RELEASE_ID, [output])
                self.assertTrue(injected)
                self.assertFalse((release_root / "release-manifest.json").exists())

    def test_release_marker_rename_boundary_never_certifies_injected_tree_entries(self) -> None:
        """Catches additions after the precommit rescan but inside marker rename."""

        variants = (
            ("root file", lambda output: output.parents[1] / "rename-race-extra.txt", False),
            ("family file", lambda output: output.parent / "rename-race-extra.txt", False),
            ("family directory", lambda output: output.parent / "rename-race-extra", True),
        )
        for label, target_for, is_directory in variants:
            with self.subTest(mutation=label), TemporaryDirectory() as root_text:
                output = write_release_output_fixture(
                    Path(root_text), "proof-20260815T153000Z-a1b2c3d"
                )
                release_root = output.parents[1]
                marker = release_root / "release-manifest.json"
                injected = target_for(output)
                original_rename = approval_module.os.rename
                validity_during_rename: list[bool] = []

                def inject_at_marker_rename(source: object, destination: object) -> None:
                    if Path(destination) != marker:
                        original_rename(source, destination)
                        return
                    if is_directory:
                        injected.mkdir()
                    else:
                        injected.write_bytes(b"rename-boundary competitor")
                    original_rename(source, destination)
                    validator = getattr(release_module, "_validate_release_tree_authority", None)
                    if validator is None:
                        validity_during_rename.append(True)
                    else:
                        try:
                            validator(marker)
                        except ValueError:
                            validity_during_rename.append(False)
                        else:
                            validity_during_rename.append(True)

                with patch.object(approval_module.os, "rename", side_effect=inject_at_marker_rename):
                    with self.assertRaisesRegex(ValueError, "tree|rescan|rename-boundary"):
                        build_release_manifest(RELEASE_ID, [output])
                self.assertEqual(validity_during_rename, [False])
                self.assertTrue(injected.exists())
                self.assertFalse(marker.exists())
                self.assertEqual(list(release_root.glob(".release-manifest.json.*.pending")), [])

    def test_release_rejects_windows_alias_reserved_and_ads_output_names(self) -> None:
        """Catches cross-platform aliases before any external path can be opened."""

        attacks = (
            "../outside.exr",
            r"..\outside.exr",
            r"C:\outside.exr",
            r"\\server\share\outside.exr",
            "CON.exr",
            f"{SHOT_ID}--transparent.exr.",
            f"{SHOT_ID}--transparent.exr ",
            f"{SHOT_ID}--transparent.exr:stream",
        )
        for attack in attacks:
            with self.subTest(attack=attack), TemporaryDirectory() as root_text:
                output = write_release_output_fixture(
                    Path(root_text), "proof-20260815T153000Z-a1b2c3d"
                )
                payload = json.loads(output.read_text(encoding="utf-8"))
                payload["outputs"][2]["path"] = attack
                _write_json(output, payload)
                with self.assertRaisesRegex(ValueError, "canonical|reserved"):
                    build_release_manifest(RELEASE_ID, [output])

    def test_release_revalidates_latest_approval_revision(self) -> None:
        """Catches release publication from an approval superseded by a rejection."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            approval = Path(payload["approval_path"])
            approval_payload = json.loads(approval.read_text(encoding="utf-8"))
            record_decision(
                Path(approval_payload["proof_manifest_path"]),
                SHOT_ID,
                "rejected",
                "natth",
                "superseded",
            )
            with self.assertRaisesRegex(ValueError, "latest approval revision"):
                build_release_manifest(RELEASE_ID, [output])

    def test_approval_timestamp_requires_canonical_utc_z_in_payload_and_chain(self) -> None:
        """Catches empty, offset, fractional, impossible, or noncanonical approval times."""

        invalid = (
            "",
            "2026-08-16T12:34:56+07:00",
            "2026-08-16T12:34:56.000Z",
            "2026-02-30T12:34:56Z",
            "2026-8-16T12:34:56Z",
        )
        for value in invalid:
            with self.subTest(value=value), TemporaryDirectory() as root_text:
                approval_path, final_contract_path = write_approval_fixture(
                    Path(root_text), "approved", "a" * 64
                )
                payload = json.loads(approval_path.read_text(encoding="utf-8"))
                payload["created_at_utc"] = value
                errors = validate_approval_payload(payload, {})
                self.assertIn("created_at_utc", "\n".join(errors))
                _write_json(approval_path, payload)
                with self.assertRaisesRegex(ValueError, "created_at_utc"):
                    authorize_final_render(approval_path, final_contract_path)

    def test_final_authority_rejects_hardlinks_and_reparse_ancestors(self) -> None:
        """Catches physical aliases even when their target bytes still match."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval_path, final_contract_path = write_approval_fixture(root, "approved", "a" * 64)
            final = json.loads(final_contract_path.read_text(encoding="utf-8"))
            source = Path(final["evidence"]["source"]["path"])
            hardlink = source.with_name("source-hardlink.step")
            os.link(source, hardlink)
            with self.assertRaisesRegex(ValueError, "single-link|evidence drift"):
                authorize_final_render(approval_path, final_contract_path)
            hardlink.unlink()

            alias = root / "inputs-alias"
            try:
                os.symlink(source.parent, alias, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"directory symlink unavailable: {error}")
            changed = copy.deepcopy(final)
            changed["evidence"]["source"]["path"] = str(alias / source.name)
            _write_json(final_contract_path, changed)
            with self.assertRaisesRegex(ValueError, "symlink|junction|reparse"):
                authorize_final_render(approval_path, final_contract_path)
            self.assertEqual(source.read_bytes(), b"authoritative STEP")


if __name__ == "__main__":
    unittest.main()
