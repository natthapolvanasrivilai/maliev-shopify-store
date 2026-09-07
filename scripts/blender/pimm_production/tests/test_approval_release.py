"""Fixture-only contract tests for PIMM owner approval and immutable releases."""

from __future__ import annotations

import copy
import contextlib
import dataclasses
import hashlib
import io
import json
import os
import struct
import subprocess
import textwrap
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from PIL import Image, ImageDraw

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
APPROVED_COMPONENT_MACHINE_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "approved-30g-component-machine.json"
)


class CampaignProofApprovalBoundaryTests(unittest.TestCase):
    def test_preview_campaign_does_not_authorize_native_finals(self):
        source = Path(proof_fixtures.PROOF_RUNNER).read_text(encoding="utf-8")
        self.assertIn('"--render-campaign"', source)
        self.assertNotIn("run_authorized_final(", source)


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


_SEGMENT_LABELS = ("a", "b", "c", "d", "e", "f", "g")
_DIGIT_SEGMENTS = {
    "0": "1110111",
    "1": "0010010",
    "2": "1011101",
    "3": "1011011",
    "4": "0111010",
    "5": "1101011",
    "6": "1101111",
    "7": "1010010",
    "8": "1111111",
    "9": "1111011",
}


def _approved_component_machine_contract() -> dict[str, object]:
    """Return a schema-compatible approved physical 30G segment map."""

    values = ["300", "300"]
    patterns = [_DIGIT_SEGMENTS[digit] for value in values for digit in value]
    segments = []
    for digit_index, pattern in enumerate(patterns):
        for segment_index, (label, bit) in enumerate(zip(_SEGMENT_LABELS, pattern)):
            active = bit == "1"
            segments.append(
                {
                    "stable_object_id": f"30G-display-d{digit_index}-{label}",
                    "material_id": "CONTROLLER_ACTIVE" if active else "CONTROLLER_INACTIVE",
                    "object_type": "MESH",
                    "active": active,
                }
            )
    return {
        "schema_version": 1,
        "machine": "30G",
        "controller": {
            "display_values": values,
            "geometry_mode": "physical-seven-segment-mesh",
            "allow_font": False,
            "allow_image_overlay": False,
            "inactive_segments_required": True,
            "approved_machine_local_material_ids": [
                "CONTROLLER_ACTIVE",
                "CONTROLLER_INACTIVE",
            ],
            "approved_segments": segments,
        },
        "animation": {
            "status": "blocked_pending_owner_motion_map",
            "allowed_controls": [],
        },
    }


def _install_approved_components_in_render_metadata(metadata: dict[str, object]) -> None:
    """Install complete proof-schema records for the approved fixture components."""

    authored = metadata["authored_settings"]["before"]
    material_specs = (
        (
            "PIMM_BLACK_POWDERCOAT",
            "PIMM-MAT-BLACK-POWDERCOAT",
            "BLACK_POWDERCOAT",
        ),
        ("DISPLAY_LIT_RED", None, "CONTROLLER_ACTIVE"),
        ("DISPLAY_UNLIT_RED", None, "CONTROLLER_INACTIVE"),
    )
    material_identities: dict[str, dict[str, object]] = {}
    materials = []
    for name, stable_id, material_id in material_specs:
        material = proof_fixtures._valid_dependency_material()
        identity: dict[str, object] = {
            "name": name,
            "type": "Material",
            "library": None,
            "pimm_material_id": material_id,
        }
        if stable_id:
            identity["pimm_stable_id"] = stable_id
        material["identity"] = identity
        material["node_tree"] = None
        material_identities[material_id] = identity
        materials.append(material)

    objects = [proof_fixtures._valid_camera_dependency_object()]

    def component_object(name: str, stable_id: str, material_name: str) -> dict[str, object]:
        obj = proof_fixtures._valid_dependency_object(name)
        obj["identity"]["pimm_stable_id"] = stable_id
        obj["material_slots"] = [
            {
                "index": 0,
                "name": material_name,
                "link": "DATA",
                "material": material_identities[material_name],
            }
        ]
        return obj

    objects.append(
        component_object(
            "PIMM_30G_MATERIAL_BODY", "30G-material-body", "BLACK_POWDERCOAT"
        )
    )
    machine = _approved_component_machine_contract()
    for segment in machine["controller"]["approved_segments"]:
        objects.append(
            component_object(
                str(segment["stable_object_id"]),
                str(segment["stable_object_id"]),
                str(segment["material_id"]),
            )
        )
    objects.sort(key=lambda obj: json.dumps(obj["identity"], sort_keys=True, separators=(",", ":")))
    materials.sort(key=lambda item: json.dumps(item["identity"], sort_keys=True, separators=(",", ":")))
    authored["objects"] = objects
    authored["materials"] = materials
    authored["collection_tree"]["objects"] = [obj["identity"] for obj in objects]
    authored["collection_tree"]["objects"].sort(
        key=lambda identity: json.dumps(identity, sort_keys=True, separators=(",", ":"))
    )
    proof_fixtures._recompute_dependency_digest(authored)
    metadata["authored_settings"]["after"] = copy.deepcopy(authored)


def _approved_component_authored_state() -> dict[str, object]:
    """Model the exact approved scene object/material identities used by masks."""

    machine = _approved_component_machine_contract()
    segments = machine["controller"]["approved_segments"]
    material_identity = {
        "name": "PIMM_BLACK_POWDERCOAT",
        "type": "Material",
        "library": None,
        "pimm_stable_id": "PIMM-MAT-BLACK-POWDERCOAT",
        "pimm_material_id": "BLACK_POWDERCOAT",
    }
    active_identity = {
        "name": "DISPLAY_LIT_RED",
        "type": "Material",
        "library": None,
        "pimm_material_id": "CONTROLLER_ACTIVE",
    }
    inactive_identity = {
        "name": "DISPLAY_UNLIT_RED",
        "type": "Material",
        "library": None,
        "pimm_material_id": "CONTROLLER_INACTIVE",
    }
    material_identities = {
        "BLACK_POWDERCOAT": material_identity,
        "CONTROLLER_ACTIVE": active_identity,
        "CONTROLLER_INACTIVE": inactive_identity,
    }
    objects: list[dict[str, object]] = [
        {
            "identity": {
                "name": "PIMM_30G_MATERIAL_BODY",
                "type": "Object",
                "library": None,
                "pimm_stable_id": "30G-material-body",
            },
            "object_type": "MESH",
            "data": {
                "identity": {
                    "name": "PIMM_30G_MATERIAL_BODY_MESH",
                    "type": "Mesh",
                    "library": None,
                }
            },
            "hide_render": False,
            "material_slots": [{"material": material_identity}],
            "modifiers": [],
        }
    ]
    for segment in segments:
        objects.append(
            {
                "identity": {
                    "name": segment["stable_object_id"],
                    "type": "Object",
                    "library": None,
                    "pimm_stable_id": segment["stable_object_id"],
                },
                "object_type": "MESH",
                "data": {
                    "identity": {
                        "name": f"{segment['stable_object_id']}_MESH",
                        "type": "Mesh",
                        "library": None,
                    }
                },
                "hide_render": False,
                "material_slots": [
                    {
                        "material": material_identities[str(segment["material_id"])]
                    }
                ],
                "modifiers": [],
            }
        )
    return {
        "library_authorities": [],
        "objects": objects,
        "materials": [
            {"identity": identity, "properties": {}, "node_tree": None}
            for identity in material_identities.values()
        ],
        "images": [],
    }


def _set_component_library_authorities(
    authored: dict[str, object], master: Path, material_library: Path
) -> None:
    """Model a master-linked component with a nested shared material library."""

    master_text = str(master.resolve())
    material_text = str(material_library.resolve())
    authored["library_authorities"] = [
        {
            "raw_filepath": str(master),
            "lexical_path": str(master),
            "canonical_path": master_text,
            "parent_canonical_path": None,
        },
        {
            "raw_filepath": str(material_library),
            "lexical_path": str(material_library),
            "canonical_path": material_text,
            "parent_canonical_path": master_text,
        },
    ]
    authored["library_authorities"].sort(
        key=lambda item: json.dumps(
            [
                item["canonical_path"],
                item["lexical_path"],
                item["raw_filepath"],
            ],
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    materials_by_id = {
        str(record["identity"]["pimm_material_id"]): record["identity"]
        for record in authored["materials"]
    }
    for record in authored["materials"]:
        identity = record["identity"]
        identity["library"] = (
            material_text
            if identity["pimm_material_id"] == "BLACK_POWDERCOAT"
            else master_text
        )
    for obj in authored["objects"]:
        if obj.get("object_type") != "MESH":
            continue
        obj["identity"]["library"] = master_text
        obj["data"]["identity"]["library"] = master_text
        for slot in obj["material_slots"]:
            material_id = slot["material"]["pimm_material_id"]
            slot["material"] = materials_by_id[material_id]
    authored["materials"].sort(
        key=lambda item: json.dumps(
            item["identity"], sort_keys=True, separators=(",", ":")
        )
    )
    authored["objects"].sort(
        key=lambda item: json.dumps(
            [
                item["identity"]["name"],
                item["object_type"],
                item["identity"]["library"],
            ],
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    if "collection_tree" in authored:
        authored["collection_tree"]["objects"].sort(
            key=lambda identity: json.dumps(
                identity, sort_keys=True, separators=(",", ":")
            )
        )


def _add_governed_auxiliary_materials(
    authored: dict[str, object], master: Path
) -> None:
    """Add the two master artworks and scene catcher captured by static scenes."""

    master_text = str(master.resolve())
    specs = (
        (
            "MACHINE_ARTWORK_AIRTAC_DECAL",
            "MAT_AirTAC_Decal",
            "PIMM30_MASTER_AirTAC_Decal",
            master_text,
        ),
        (
            "MACHINE_ARTWORK_PRESSURE_GAUGE_FACE",
            "MAT_Pressure_Gauge_Decal",
            "PIMM30_MASTER_Pressure_Gauge_Face",
            master_text,
        ),
        (
            "SCENE_SHADOW_CATCHER",
            "PIMM_SCENE_SHADOW_CATCHER_MATERIAL",
            "PIMM_SCENE_SHADOW_CATCHER",
            None,
        ),
    )
    for material_id, material_name, object_name, library in specs:
        material = {
            "name": material_name,
            "type": "Material",
            "library": library,
            "pimm_material_id": material_id,
        }
        authored["materials"].append(
            {"identity": material, "properties": {}, "node_tree": None}
        )
        authored["objects"].append(
            {
                "identity": {
                    "name": object_name,
                    "type": "Object",
                    "library": library,
                },
                "object_type": "MESH",
                "data": {
                    "identity": {
                        "name": f"{object_name}_MESH",
                        "type": "Mesh",
                        "library": library,
                    }
                },
                "hide_render": False,
                "material_slots": [{"material": material}],
                "modifiers": [],
            }
        )


def _add_governed_hdri_dependency(
    authored: dict[str, object], root: Path, evidence: dict[str, dict[str, object]]
) -> None:
    """Add the exact proof-bound external studio HDRI captured by static scenes."""

    hdri = root / "assets" / "hdri" / "studio_kontrast_04_4k.exr"
    hdri.parent.mkdir(parents=True)
    hdri.write_bytes(b"governed studio HDRI fixture")
    record = approval_module.stable_file_record(hdri, root, "asset", "hdri")
    evidence["hdri"] = record
    authored["images"].append(
        {
            "name": "studio_kontrast_04_4k.exr",
            "type": "Image",
            "library": None,
            "source": "FILE",
            "filepath": str(hdri.resolve()),
            "file_format": "OPEN_EXR",
            "external_files": [
                {
                    key: record[key]
                    for key in (
                        "path", "sha256", "bytes", "mtime_ns", "ctime_ns",
                        "device", "inode", "links",
                    )
                }
                | {"resolved_path": record["path"]}
            ],
        }
    )


def _component_authority_fixture(
    root: Path,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, str],
    dict[str, dict[str, object]],
    Path,
    Path,
]:
    """Return approved component state tied only to pinned master/material files."""

    master = root / "inputs" / "PIMM-30G-MASTER.blend"
    material_library = root / "inputs" / "PIMM-MATERIAL-LIBRARY.blend"
    scene = root / "inputs" / "scene.blend"
    master.parent.mkdir(parents=True)
    master.write_bytes(b"pinned component master")
    material_library.write_bytes(b"pinned component material library")
    scene.write_bytes(b"pinned component scene")
    authored = _approved_component_authored_state()
    _set_component_library_authorities(authored, master, material_library)
    component_contract = approval_module.build_component_contract(
        _approved_component_machine_contract(), authored
    )
    roots = {
        "asset": str(root.resolve()),
        "repository": str(REPO_ROOT.resolve()),
        "tool": str((root / "tools").resolve()),
    }
    evidence = {
        "master": approval_module.stable_file_record(
            master, root, "asset", "master"
        ),
        "material_library": approval_module.stable_file_record(
            material_library, root, "asset", "material library"
        ),
        "scene": approval_module.stable_file_record(
            scene, root, "asset", "scene"
        ),
    }
    return (
        authored,
        component_contract,
        roots,
        evidence,
        master,
        material_library,
    )


def _rewrite_proof_authored_settings(
    proof_path: Path, mutation: Callable[[dict[str, object]], None]
) -> None:
    """Apply one schema-valid authored-state mutation to both Task 5 copies."""

    metadata_path = proof_path.parent / "render-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    before = copy.deepcopy(metadata["authored_settings"]["before"])
    mutation(before)
    proof_fixtures._recompute_dependency_digest(before)
    metadata["authored_settings"] = {
        "before": before,
        "after": copy.deepcopy(before),
    }
    _write_json(metadata_path, metadata)
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["render"] = metadata
    _write_json(proof_path, proof)


def _png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _structured_component_pixels(
    *, invert_segment_states: bool = False
) -> tuple[bytes, dict[str, bytes]]:
    """Depict an irregular material body and six physical seven-segment digits."""

    machine = _approved_component_machine_contract()
    segments = machine["controller"]["approved_segments"]
    image = Image.new("RGBA", (64, 48), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    material_mask = Image.new("L", image.size, 0)
    material_draw = ImageDraw.Draw(material_mask)
    material_shape = [(4, 9), (28, 7), (34, 15), (32, 38), (10, 41), (3, 28)]
    material_draw.polygon(material_shape, fill=255)
    for y in range(image.height):
        for x in range(image.width):
            if material_mask.getpixel((x, y)):
                image.putpixel((x, y), (45 + x * 2, 65 + y, 90 + (x + y) % 55, 220))
    draw.rectangle((36, 9, 63, 21), fill=(18, 20, 24, 255))

    masks: dict[str, bytes] = {"material": _png_bytes(material_mask)}
    digit_x = (38, 42, 46, 51, 55, 59)
    segment_pixels = {
        "a": lambda x: [(x + 1, 11)],
        "b": lambda x: [(x, 12), (x, 13)],
        "c": lambda x: [(x + 2, 12), (x + 2, 13)],
        "d": lambda x: [(x + 1, 14)],
        "e": lambda x: [(x, 15), (x, 16)],
        "f": lambda x: [(x + 2, 15), (x + 2, 16)],
        "g": lambda x: [(x + 1, 17)],
    }
    for index, segment in enumerate(segments):
        digit_index, label_index = divmod(index, len(_SEGMENT_LABELS))
        label = _SEGMENT_LABELS[label_index]
        mask = Image.new("L", image.size, 0)
        for coordinate in segment_pixels[label](digit_x[digit_index]):
            mask.putpixel(coordinate, 255)
        active = bool(segment["active"]) ^ invert_segment_states
        color = (245, 70, 25, 255) if active else (24, 8, 6, 255)
        for coordinate in segment_pixels[label](digit_x[digit_index]):
            image.putpixel(coordinate, color)
        masks[str(segment["stable_object_id"])] = _png_bytes(mask)
    return _png_bytes(image), masks


def _fixture_final_qa(
    png: Path,
    approval: dict[str, object],
    endpoints: dict[str, Path],
    component_contract: dict[str, object],
    component_masks: dict[str, Path],
) -> dict[str, object]:
    """Build fixture QA from persisted pixels, masks, and approved authorities."""

    evidence = approval["evidence"]
    assert isinstance(evidence, dict)
    machine_path = Path(evidence["machine_contract"]["path"])
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    scene_contract = json.loads(Path(evidence["scene_contract"]["path"]).read_text(encoding="utf-8"))
    return approval_module.compute_final_qa(
        png.read_bytes(),
        {label: path.read_bytes() for label, path in endpoints.items()},
        [64, 48],
        machine,
        scene_contract,
        component_contract=component_contract,
        component_mask_bytes={
            mask_id: path.read_bytes() for mask_id, path in component_masks.items()
        },
        material_library_sha256=approval["inputs"]["material_library_sha256"],
        scene_contract_sha256=evidence["scene_contract"]["sha256"],
        machine_contract_sha256=evidence["machine_contract"]["sha256"],
    )


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
    if not master.exists():
        master.write_bytes(b"authoritative master")
    if not material.exists():
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
    if not native_scene:
        _install_approved_components_in_render_metadata(metadata)
        authored = metadata["authored_settings"]["before"]
        _set_component_library_authorities(authored, master, material)
        proof_fixtures._recompute_dependency_digest(authored)
        metadata["authored_settings"]["after"] = copy.deepcopy(authored)
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
        if result.returncode or not capture_path.is_file():
            raise AssertionError(result.stdout + result.stderr)
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
    with patch.object(
        approval_module,
        "_machine_contract_path",
        return_value=APPROVED_COMPONENT_MACHINE_FIXTURE,
        create=True,
    ):
        approval_path = record_decision(
            proof_path, SHOT_ID, decision, "natth", "fixture review"
        )
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
    """Write the semantically structured material/body and physical display fixture."""

    png, _ = _structured_component_pixels()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def _write_native_component_mask_fixture(family: Path) -> None:
    """Write the exact canonical mask family expected from the mocked Blender call."""

    _, masks = _structured_component_pixels()
    segments = _approved_component_machine_contract()["controller"]["approved_segments"]
    ordinals = {
        str(segment["stable_object_id"]): ordinal
        for ordinal, segment in enumerate(segments)
    }
    for mask_id, data in masks.items():
        filename = (
            f"{SHOT_ID}--material-objects-mask.png"
            if mask_id == "material"
            else f"{SHOT_ID}--controller-segment-{ordinals[mask_id]:02d}-mask.png"
        )
        (family / filename).write_bytes(data)


def write_release_output_fixture(root: Path, generation_id: str) -> Path:
    """Write one complete final-output manifest with a transparent delivery family."""

    approval_path, final_contract_path = write_approval_fixture(
        root, "approved", "a" * 64, generation_id=generation_id
    )
    authorization = authorize_final_render(approval_path, final_contract_path)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    evidence = approval["evidence"]
    machine = json.loads(Path(evidence["machine_contract"]["path"]).read_text(encoding="utf-8"))
    metadata = json.loads(Path(evidence["render_metadata"]["path"]).read_text(encoding="utf-8"))
    component_contract = approval_module.build_component_contract(
        machine, metadata["authored_settings"]["before"]
    )
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
    _, mask_bytes = _structured_component_pixels()
    component_masks: dict[str, Path] = {}
    component_entries: list[dict[str, object]] = []
    for mask_id, data in mask_bytes.items():
        if mask_id == "material":
            filename = f"{SHOT_ID}--material-objects-mask.png"
        else:
            segment = next(
                item for item in component_contract["segments"]
                if item["stable_object_id"] == mask_id
            )
            filename = f"{SHOT_ID}--controller-segment-{segment['ordinal']:02d}-mask.png"
        path = output_root / filename
        path.write_bytes(data)
        component_masks[mask_id] = path
        component_entries.append(
            {
                "mask_id": mask_id,
                "path": filename,
                "sha256": _sha256(path),
                "dimensions": [64, 48],
                "mime_type": "image/png",
            }
        )
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
            png, approval, endpoints, component_contract, component_masks
        ),
        "qa_evidence": qa_evidence,
        "component_evidence": {
            "schema": "pimm-final-component-evidence/v1",
            "contract": component_contract,
            "masks": sorted(component_entries, key=lambda item: str(item["mask_id"])),
        },
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
    component = payload["component_evidence"]
    component_masks = {
        record["mask_id"]: family / record["path"] for record in component["masks"]
    }
    for record in component["masks"]:
        record["sha256"] = _sha256(family / record["path"])
    old_section = copy.deepcopy(payload["qa"].get(preserve_qa_section)) if preserve_qa_section else None
    approval = json.loads(Path(payload["approval_path"]).read_text(encoding="utf-8"))
    payload["qa"] = _fixture_final_qa(
        family / f"{SHOT_ID}--transparent.png",
        approval,
        endpoints,
        component["contract"],
        component_masks,
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


def _zip_shuffle(raw: bytes) -> bytes:
    return raw[0::2] + raw[1::2]


def _zip_unshuffle(raw: bytes) -> bytes:
    split = (len(raw) + 1) // 2
    decoded = bytearray(len(raw))
    decoded[0::2] = raw[:split]
    decoded[1::2] = raw[split:]
    return bytes(decoded)


def _zip_predict(raw: bytes) -> bytes:
    predicted = bytearray(raw)
    for index in range(1, len(raw)):
        predicted[index] = (raw[index] - raw[index - 1] + 128) & 0xFF
    return bytes(predicted)


def _zip_inverse_predict(raw: bytes) -> bytes:
    decoded = bytearray(raw)
    for index in range(1, len(decoded)):
        decoded[index] = (decoded[index - 1] + decoded[index] - 128) & 0xFF
    return bytes(decoded)


def _wrong_exr_decoder_collision(raw: bytes) -> bytes:
    """Return different channel bytes that collide under the former decode order."""

    return _zip_unshuffle(_zip_inverse_predict(_zip_shuffle(_zip_predict(raw))))


def _former_wrong_zip_decode(raw: bytes) -> bytes:
    """Model the former unshuffle-before-inverse-predict decoder for regression proof."""

    return _zip_inverse_predict(_zip_unshuffle(_zip_predict(_zip_shuffle(raw))))


def _float_exr_bytes(
    width: int,
    height: int,
    *,
    pixel_value: float = 0.5,
    compression: int = 0,
    vary_pixels: bool = False,
    raw_transform: Callable[[bytes], bytes] | None = None,
    raw_fallback: bool = False,
) -> bytes:
    """Build a minimal valid uncompressed scanline float-RGBA OpenEXR fixture."""

    def attribute(name: str, kind: str, value: bytes) -> bytes:
        return name.encode("ascii") + b"\0" + kind.encode("ascii") + b"\0" + struct.pack("<I", len(value)) + value

    channels = b""
    for name in ("A", "B", "G", "R"):
        channels += name.encode("ascii") + b"\0" + struct.pack("<I", 2) + b"\0\0\0\0" + struct.pack("<II", 1, 1)
    channels += b"\0"
    window = struct.pack("<iiii", 0, 0, width - 1, height - 1)
    header = b"v/1\x01" + struct.pack("<I", 2)
    header += attribute("channels", "chlist", channels)
    header += attribute("compression", "compression", bytes([compression]))
    header += attribute("dataWindow", "box2i", window)
    header += attribute("displayWindow", "box2i", window)
    header += attribute("lineOrder", "lineOrder", b"\0")
    header += attribute("pixelAspectRatio", "float", struct.pack("<f", 1.0))
    header += attribute("screenWindowCenter", "v2f", struct.pack("<ff", 0.0, 0.0))
    header += attribute("screenWindowWidth", "float", struct.pack("<f", 1.0))
    header += b"\0"
    chunks: list[bytes] = []
    for y in range(height):
        if vary_pixels:
            scanline_data = b"".join(
                struct.pack("<f", pixel_value + ((y * width * 4 + index) % 23) / 32.0)
                for index in range(width * 4)
            )
        else:
            scanline_data = struct.pack("<f", pixel_value) * (width * 4)
        if raw_transform is not None:
            scanline_data = raw_transform(scanline_data)
        if compression == 0 or raw_fallback:
            payload = scanline_data
        elif compression == 2:
            payload = zlib.compress(_zip_predict(_zip_shuffle(scanline_data)))
        else:
            raise AssertionError("fixture supports only uncompressed and ZIPS EXR")
        chunks.append(struct.pack("<iI", y, len(payload)) + payload)
    cursor = len(header) + height * 8
    offsets: list[int] = []
    for chunk in chunks:
        offsets.append(cursor)
        cursor += len(chunk)
    return header + struct.pack(f"<{height}Q", *offsets) + b"".join(chunks)


def _write_float_exr(
    path: Path,
    width: int,
    height: int,
    *,
    pixel_value: float = 0.5,
    compression: int = 0,
    vary_pixels: bool = False,
    raw_transform: Callable[[bytes], bytes] | None = None,
    raw_fallback: bool = False,
) -> None:
    """Write a minimal valid uncompressed scanline float-RGBA OpenEXR fixture."""

    path.write_bytes(
        _float_exr_bytes(
            width,
            height,
            pixel_value=pixel_value,
            compression=compression,
            vary_pixels=vary_pixels,
            raw_transform=raw_transform,
            raw_fallback=raw_fallback,
        )
    )


def _replace_only_exr_payload(
    data: bytes, transform: Callable[[bytes], bytes]
) -> bytes:
    """Replace the single scanline chunk payload in a one-row EXR fixture."""

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
    chunk_offset = struct.unpack_from("<Q", data, cursor)[0]
    y, size = struct.unpack_from("<iI", data, chunk_offset)
    payload = data[chunk_offset + 8 : chunk_offset + 8 + size]
    replacement = transform(payload)
    return (
        data[:chunk_offset]
        + struct.pack("<iI", y, len(replacement))
        + replacement
    )


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
    def test_native_dependency_state_ignores_only_factory_startup_addon_metadata(self) -> None:
        """Catches addon caches masking any real dependency or provenance drift."""

        expected = _approved_component_authored_state()
        expected.update({
            "scene_identity": {"name": "Scene", "type": "Scene", "library": None},
            "collection_tree": {"identity": "root", "children": []},
            "view_layers": [{"name": "ViewLayer", "properties": {}}],
        })
        for obj in expected["objects"]:
            obj.setdefault("properties", {})
            obj.setdefault("transform", {"location": [0.0, 0.0, 0.0]})
        expected["materials"][0]["node_tree"] = {"nodes": [{"value": 0.5}]}
        live = copy.deepcopy(expected)
        for obj in expected["objects"]:
            obj["properties"]["poliigon"] = ""
            obj["properties"]["poliigon_lod"] = ""
        for material in expected["materials"]:
            material["properties"]["poliigon"] = ""

        self.assertEqual(
            final_module._dependency_state_sha256(expected),
            final_module._dependency_state_sha256(live),
        )

        mutations = []
        object_transform = copy.deepcopy(live)
        object_transform["objects"][0]["transform"]["location"][0] = 1.0
        mutations.append(object_transform)
        object_property = copy.deepcopy(live)
        object_property["objects"][0]["properties"]["unexpected"] = True
        mutations.append(object_property)
        material_node = copy.deepcopy(live)
        material_node["materials"][0]["node_tree"]["nodes"][0]["value"] = 0.75
        mutations.append(material_node)
        material_property = copy.deepcopy(live)
        material_property["materials"][0]["properties"]["unexpected"] = True
        mutations.append(material_property)
        image = copy.deepcopy(live)
        image["images"].append({"name": "unexpected", "sha256": "A" * 64})
        mutations.append(image)
        library = copy.deepcopy(live)
        library["library_authorities"].append({"canonical_path": "M:/unexpected.blend"})
        mutations.append(library)
        for mutated in mutations:
            with self.subTest(mutated=mutations.index(mutated)):
                self.assertNotEqual(
                    final_module._dependency_state_sha256(expected),
                    final_module._dependency_state_sha256(mutated),
                )

    def test_independent_release_dependency_check_reuses_only_governed_normalization(self) -> None:
        """Keeps release regeneration aligned with the narrow native dependency gate."""

        approved = _approved_component_authored_state()
        approved.update({
            "scene_identity": {"name": "Scene", "type": "Scene", "library": None},
            "collection_tree": {"identity": "root", "children": []},
            "view_layers": [{"name": "ViewLayer", "properties": {}}],
        })
        for obj in approved["objects"]:
            obj.setdefault("properties", {})
            obj.setdefault("transform", {"location": [0.0, 0.0, 0.0]})
            obj["properties"]["poliigon"] = ""
            obj["properties"]["poliigon_lod"] = ""
        approved["materials"][0]["node_tree"] = {"nodes": [{"value": 0.5}]}
        for material in approved["materials"]:
            material["properties"]["poliigon"] = ""

        normalized = copy.deepcopy(approved)
        for obj in normalized["objects"]:
            obj["properties"].pop("poliigon")
            obj["properties"].pop("poliigon_lod")
        for material in normalized["materials"]:
            material["properties"].pop("poliigon")
        release_module._validate_independent_dependency_state(approved, normalized)

        mutations = []
        object_transform = copy.deepcopy(normalized)
        object_transform["objects"][0]["transform"]["location"][0] = 1.0
        mutations.append(object_transform)
        object_property = copy.deepcopy(normalized)
        object_property["objects"][0]["properties"]["unexpected"] = True
        mutations.append(object_property)
        material_node = copy.deepcopy(normalized)
        material_node["materials"][0]["node_tree"]["nodes"][0]["value"] = 0.75
        mutations.append(material_node)
        material_property = copy.deepcopy(normalized)
        material_property["materials"][0]["properties"]["unexpected"] = True
        mutations.append(material_property)
        image = copy.deepcopy(normalized)
        image["images"].append({"name": "unexpected", "sha256": "A" * 64})
        mutations.append(image)
        library = copy.deepcopy(normalized)
        library["library_authorities"].append({"canonical_path": "M:/unexpected.blend"})
        mutations.append(library)
        for index, mutated in enumerate(mutations):
            with self.subTest(mutation=index), self.assertRaisesRegex(
                ValueError, "release independent linked dependency state drift"
            ):
                release_module._validate_independent_dependency_state(approved, mutated)

    def test_native_animation_state_ignores_only_factory_startup_addon_metadata(self) -> None:
        """Catches harmless Poliigon normalization hiding any real object-state drift."""

        expected = _approved_component_authored_state()
        for obj in expected["objects"]:
            obj.setdefault("properties", {})
        expected["objects"][0]["transform"] = {"location": [0.0, 0.0, 0.0]}
        live = copy.deepcopy(expected)
        for obj in expected["objects"]:
            obj["properties"]["poliigon"] = "addon-runtime"
            obj["properties"]["poliigon_lod"] = "LOD0"

        self.assertEqual(
            final_module._animation_state_sha256(expected, None),
            final_module._animation_state_sha256(live, None),
        )

        transform_drift = copy.deepcopy(live)
        transform_drift["objects"][0]["transform"]["location"][0] += 1.0
        self.assertNotEqual(
            final_module._animation_state_sha256(expected, None),
            final_module._animation_state_sha256(transform_drift, None),
        )

        property_drift = copy.deepcopy(live)
        property_drift["objects"][0].setdefault("properties", {})["unexpected"] = True
        self.assertNotEqual(
            final_module._animation_state_sha256(expected, None),
            final_module._animation_state_sha256(property_drift, None),
        )

    def test_static_scene_hdri_external_dependency_requires_exact_evidence(self) -> None:
        """Catches any external image except the one proof-bound governed studio HDRI."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            authored, _, roots, evidence, _, _ = _component_authority_fixture(root)
            _add_governed_hdri_dependency(authored, root, evidence)
            machine = _approved_component_machine_contract()

            with patch.object(
                approval_module, "_GOVERNED_HDRI_SHA256", evidence["hdri"]["sha256"]
            ):
                approval_module.build_authorized_component_contract(
                    machine, authored, roots, evidence
                )

            cases: dict[str, Callable[[dict[str, object], dict[str, object]], None]] = {
                "missing evidence": lambda candidate, records: records.pop("hdri"),
                "wrong path": lambda candidate, records: candidate["images"][-1].__setitem__(
                    "filepath", str(root / "assets" / "hdri" / "wrong.exr")
                ),
                "wrong filename": lambda candidate, records: candidate["images"][-1].__setitem__(
                    "name", "wrong.exr"
                ),
                "wrong bytes hash": lambda candidate, records: candidate["images"][-1][
                    "external_files"
                ][0].__setitem__("sha256", "A" * 64),
                "wrong dependency role": lambda candidate, records: candidate["images"][-1].__setitem__(
                    "type", "Material"
                ),
                "wrong library": lambda candidate, records: candidate["images"][-1].__setitem__(
                    "library", records["master"]["path"]
                ),
                "wrong source": lambda candidate, records: candidate["images"][-1].__setitem__(
                    "source", "GENERATED"
                ),
                "unrelated external image": lambda candidate, records: candidate["images"].append(
                    copy.deepcopy(candidate["images"][-1])
                ),
            }
            for label, mutate in cases.items():
                with self.subTest(mutation=label):
                    candidate = copy.deepcopy(authored)
                    records = copy.deepcopy(evidence)
                    mutate(candidate, records)
                    with patch.object(
                        approval_module,
                        "_GOVERNED_HDRI_SHA256",
                        evidence["hdri"]["sha256"],
                    ), self.assertRaisesRegex(ValueError, "HDRI|external image|hdri"):
                        approval_module.build_authorized_component_contract(
                            machine, candidate, roots, records
                        )

    def test_static_scene_auxiliary_materials_require_exact_roles_and_owners(self) -> None:
        """Catches final authorization rejecting or weakening the three governed auxiliaries."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            authored, _, roots, evidence, master, _ = _component_authority_fixture(root)
            _add_governed_auxiliary_materials(authored, master)
            machine = _approved_component_machine_contract()

            approval_module.build_authorized_component_contract(
                machine, authored, roots, evidence
            )

            for index in (-3, -2, -1):
                material_id = authored["materials"][index]["identity"]["pimm_material_id"]
                expected_library = authored["materials"][index]["identity"]["library"]
                mutations: dict[str, Callable[[dict[str, object]], None]] = {
                    "wrong stable ID": lambda candidate, i=index: candidate["materials"][i][
                        "identity"
                    ].__setitem__("pimm_material_id", f"{material_id}_WRONG"),
                    "wrong material name": lambda candidate, i=index: candidate["materials"][i][
                        "identity"
                    ].__setitem__("name", "WRONG_AUXILIARY_MATERIAL"),
                    "wrong provenance": lambda candidate, i=index, expected=expected_library: candidate[
                        "materials"
                    ][i]["identity"].__setitem__(
                        "library", None if expected is not None else str(master.resolve())
                    ),
                    "wrong owner": lambda candidate, i=index: candidate["objects"][i][
                        "identity"
                    ].__setitem__("name", "WRONG_AUXILIARY_OWNER"),
                }
                for label, mutate in mutations.items():
                    with self.subTest(material_id=material_id, mutation=label):
                        candidate = copy.deepcopy(authored)
                        mutate(candidate)
                        with self.assertRaisesRegex(ValueError, "auxiliary|pimm_material_id"):
                            approval_module.build_authorized_component_contract(
                                machine, candidate, roots, evidence
                            )

            unknown = copy.deepcopy(authored)
            unknown_material = copy.deepcopy(unknown["materials"][-1])
            unknown_material["identity"]["pimm_material_id"] = "UNKNOWN_AUXILIARY"
            unknown_material["identity"]["name"] = "UNKNOWN_AUXILIARY"
            unknown["materials"].append(unknown_material)
            with self.assertRaisesRegex(ValueError, "pimm_material_id"):
                approval_module.build_authorized_component_contract(
                    machine, unknown, roots, evidence
                )

    def test_mapped_drive_authority_accepts_only_its_exact_resolved_unc_target(self) -> None:
        """Keeps mapped SMB proofs usable without permitting arbitrary UNC authority."""

        matcher = getattr(approval_module, "_match_drive_authority_path", None)
        self.assertTrue(callable(matcher))
        lexical = Path(r"M:\asset\masters\PIMM-30G-MASTER.blend")
        resolved = Path(r"\\maliev\maliev\asset\masters\PIMM-30G-MASTER.blend")
        with patch.object(type(lexical), "resolve", return_value=resolved):
            self.assertEqual(
                matcher(str(resolved), (lexical,), "mapped authority"),
                lexical,
            )
            with self.assertRaisesRegex(ValueError, "exact mapped-drive authority"):
                matcher(
                    r"\\other\share\asset\masters\PIMM-30G-MASTER.blend",
                    (lexical,),
                    "mapped authority",
                )

    def test_published_json_identity_tolerates_smb_timestamp_settling_only(self) -> None:
        """Accepts post-rename SMB times while retaining exact object identity."""

        created = {
            "device": 7, "inode": 11, "links": 1, "bytes": 42,
            "mtime_ns": 100, "ctime_ns": 200,
        }
        published = {
            **created,
            "mtime_ns": 101,
            "ctime_ns": 201,
            "change_time_ns": 300,
            "authority": "asset",
            "path": r"M:\asset\approval.json",
            "sha256": "A" * 64,
        }
        self.assertTrue(approval_module._published_identity_matches(created, published))
        for field in ("device", "inode", "links", "bytes"):
            with self.subTest(field=field):
                changed = dict(published)
                changed[field] = int(changed[field]) + 1
                self.assertFalse(
                    approval_module._published_identity_matches(created, changed)
                )

    def test_release_publication_tolerates_only_smb_timestamp_settling(self) -> None:
        """Keeps the release marker's final readback exact except for SMB times."""

        destination = Path(r"M:\asset\release-2026-08-27-r16\release-manifest.json")
        payload = {
            "schema": "pimm-final-release-manifest/v1",
            "tree_authority": {
                "schema": "pimm-release-tree-authority/v1",
                "entries": [],
                "sha256": _canonical_fixture_sha([]),
            },
        }
        encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        created = {
            "device": 7,
            "inode": 11,
            "links": 1,
            "bytes": len(encoded),
            "mtime_ns": 100,
            "ctime_ns": 200,
        }
        published = {
            **created,
            "mtime_ns": 101,
            "ctime_ns": 201,
            "change_time_ns": 300,
            "authority": "asset",
            "path": str(destination),
            "sha256": hashlib.sha256(encoded).hexdigest().upper(),
        }
        self.assertTrue(
            release_module._release_publication_matches(
                destination, payload, payload, created, published
            )
        )

        for field in ("path", "device", "inode", "links", "bytes", "sha256"):
            with self.subTest(field=field):
                changed = copy.deepcopy(published)
                changed[field] = (
                    str(destination.parent / "other.json")
                    if field == "path"
                    else "F" * 64 if field == "sha256"
                    else int(changed[field]) + 1
                )
                self.assertFalse(
                    release_module._release_publication_matches(
                        destination, payload, payload, created, changed
                    )
                )

        changed_payload = copy.deepcopy(payload)
        changed_payload["schema"] = "counterfeit"
        self.assertFalse(
            release_module._release_publication_matches(
                destination, payload, changed_payload, created, published
            )
        )
        changed_tree = copy.deepcopy(payload)
        changed_tree["tree_authority"]["sha256"] = "F" * 64
        self.assertFalse(
            release_module._release_publication_matches(
                destination, payload, changed_tree, created, published
            )
        )

    def setUp(self) -> None:
        self._machine_contract_patch = patch.object(
            approval_module,
            "_machine_contract_path",
            return_value=APPROVED_COMPONENT_MACHINE_FIXTURE,
        )
        self._machine_contract_patch.start()
        native_regenerator = release_module._regenerate_component_evidence

        def regenerate_fixture_masks(
            scene_path: Path,
            blender_binary: Path,
            dimensions: list[object],
            shot_id: str,
            component_contract: dict[str, object],
            samples: int,
            *,
            repository_root: Path,
            approved_authored_settings: dict[str, object],
        ) -> tuple[bytes, bytes, dict[str, bytes]]:
            if blender_binary.resolve() == BLENDER.resolve():
                return native_regenerator(
                    scene_path,
                    blender_binary,
                    dimensions,
                    shot_id,
                    component_contract,
                    samples,
                    repository_root=repository_root,
                    approved_authored_settings=approved_authored_settings,
                )
            png, masks = _structured_component_pixels()
            return (
                png,
                _float_exr_bytes(int(dimensions[0]), int(dimensions[1])),
                masks,
            )

        self._component_regeneration_patch = patch.object(
            release_module,
            "_regenerate_component_evidence",
            side_effect=regenerate_fixture_masks,
        )
        self._component_regeneration_patch.start()

    def tearDown(self) -> None:
        self._component_regeneration_patch.stop()
        self._machine_contract_patch.stop()

    def test_native_final_runner_is_an_explicit_authorized_operation(self) -> None:
        """Catches a final gate that authorizes data but cannot render native evidence."""

        self.assertTrue(callable(run_authorized_final))

    def test_static_native_script_audits_preview_state_then_renders_cycles_once(self) -> None:
        """Keeps Eevee authoring valid while avoiding four identical static Cycles renders."""

        script = final_module._blender_render_script(
            Path(r"M:\asset\stage"),
            Path(r"M:\asset\stage\audit.json"),
            REPO_ROOT,
            [1800, 2200],
            256,
            SHOT_ID,
            approval_module.build_component_contract(
                _approved_component_machine_contract(),
                _approved_component_authored_state(),
            ),
        )
        self.assertLess(
            script.index("_capture_authored_settings(bpy)"),
            script.index("scene.render.engine = 'CYCLES'"),
        )
        self.assertNotIn("must retain CYCLES", script)
        self.assertEqual(script.count("bpy.ops.render.render(write_still=True)"), 1)
        self.assertIn("save_render", script)

    def test_component_dependencies_accept_only_pinned_master_or_material_library(self) -> None:
        """Catches linked object/data/material/node/image bytes outside approval authority."""

        validator = getattr(
            approval_module, "build_authorized_component_contract", None
        )
        self.assertTrue(
            callable(validator),
            "Task 6 requires a component builder that resolves linked libraries to pinned evidence",
        )
        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            (
                authored,
                expected_contract,
                roots,
                evidence,
                master,
                material_library,
            ) = _component_authority_fixture(root)
            self.assertEqual(
                validator(
                    _approved_component_machine_contract(), authored, roots, evidence
                ),
                expected_contract,
            )

            same_name = root / "other" / master.name
            same_name.parent.mkdir()
            same_name.write_bytes(master.read_bytes())
            sidecar = root / "other" / "linked-components.blend"
            sidecar.write_bytes(b"unapproved linked dependency")

            def object_library(candidate: dict[str, object]) -> None:
                candidate["objects"][0]["identity"]["library"] = str(sidecar.resolve())

            def mesh_library(candidate: dict[str, object]) -> None:
                candidate["objects"][0]["data"]["identity"]["library"] = str(
                    sidecar.resolve()
                )

            def same_name_library(candidate: dict[str, object]) -> None:
                candidate["objects"][0]["identity"]["library"] = str(
                    same_name.resolve()
                )

            def linked_material_library(candidate: dict[str, object]) -> None:
                identity = candidate["materials"][0]["identity"]
                identity["library"] = str(sidecar.resolve())
                candidate["objects"][0]["material_slots"][0]["material"] = identity

            def localized_shared_material(candidate: dict[str, object]) -> None:
                identity = candidate["materials"][0]["identity"]
                identity["library"] = None
                candidate["objects"][0]["material_slots"][0]["material"] = identity

            def localized_machine_material(candidate: dict[str, object]) -> None:
                identity = next(
                    material["identity"]
                    for material in candidate["materials"]
                    if material["identity"]["pimm_material_id"]
                    == "CONTROLLER_ACTIVE"
                )
                identity["library"] = None
                for obj in candidate["objects"]:
                    for slot in obj["material_slots"]:
                        if (
                            slot["material"]["pimm_material_id"]
                            == "CONTROLLER_ACTIVE"
                        ):
                            slot["material"] = identity

            def node_library(candidate: dict[str, object]) -> None:
                candidate["materials"][0]["node_tree"] = {
                    "identity": {
                        "name": "UNPINNED_NESTED_GROUP",
                        "type": "ShaderNodeTree",
                        "library": str(sidecar.resolve()),
                    },
                    "nodes": [],
                    "links": [],
                }

            def image_library(candidate: dict[str, object]) -> None:
                candidate["materials"][0]["node_tree"] = {
                    "identity": {
                        "name": "SCENE_LOCAL_TREE",
                        "type": "ShaderNodeTree",
                        "library": None,
                    },
                    "nodes": [
                        {
                            "data": {
                                "image": {
                                    "name": "UNPINNED_IMAGE",
                                    "type": "Image",
                                    "library": str(sidecar.resolve()),
                                    "source": "GENERATED",
                                    "external_files": [],
                                }
                            }
                        }
                    ],
                    "links": [],
                }

            mutations = {
                "object": object_library,
                "mesh": mesh_library,
                "same-name path": same_name_library,
                "material": linked_material_library,
                "localized shared material": localized_shared_material,
                "localized machine material": localized_machine_material,
                "nested node group": node_library,
                "nested image": image_library,
            }
            for label, mutate in mutations.items():
                with self.subTest(dependency=label):
                    candidate = copy.deepcopy(authored)
                    mutate(candidate)
                    with self.assertRaisesRegex(
                        ValueError, "linked Blender library|pinned master|material-library"
                    ):
                        validator(
                            _approved_component_machine_contract(),
                            candidate,
                            roots,
                            evidence,
                        )

            master.write_bytes(b"mutated master with stable datablock names and IDs")
            with self.assertRaisesRegex(ValueError, "master.*(drift|identity|SHA-256)"):
                validator(
                    _approved_component_machine_contract(), authored, roots, evidence
                )
            (
                material_authored,
                _,
                material_roots,
                material_evidence,
                _,
                material_library,
            ) = _component_authority_fixture(root / "material-byte-drift")
            material_library.write_bytes(
                b"mutated material library with stable material and node names"
            )
            with self.assertRaisesRegex(
                ValueError, "material library.*(drift|identity|SHA-256)"
            ):
                validator(
                    _approved_component_machine_contract(),
                    material_authored,
                    material_roots,
                    material_evidence,
                )

    def test_component_validation_rehashes_each_unique_library_at_fixed_gates(self) -> None:
        """Prevents approval time from scaling with every linked Blender identity."""

        with TemporaryDirectory() as root_text:
            (
                authored,
                _,
                roots,
                evidence,
                master,
                material_library,
            ) = _component_authority_fixture(Path(root_text))
            original = approval_module.stable_file_record
            calls: list[Path] = []

            def track(path: Path, *args: object, **kwargs: object) -> dict[str, object]:
                calls.append(Path(path))
                return original(path, *args, **kwargs)

            with patch.object(approval_module, "stable_file_record", side_effect=track):
                approval_module._validate_component_library_paths(
                    authored,
                    roots,
                    evidence,
                    frozenset({"CONTROLLER_ACTIVE", "CONTROLLER_INACTIVE"}),
                )
            self.assertEqual(calls.count(master), 2)
            self.assertEqual(calls.count(material_library), 2)

    def test_component_contract_requires_exact_unique_pimm_material_ids(self) -> None:
        """Catches fallback, wrong, swapped, or duplicate material authority."""

        machine = _approved_component_machine_contract()
        valid = _approved_component_authored_state()

        def rewrite_all(
            candidate: dict[str, object], old: str, new: str | None
        ) -> None:
            def visit(value: object) -> None:
                if isinstance(value, dict):
                    if (
                        value.get("type") == "Material"
                        and value.get("pimm_material_id") == old
                    ):
                        if new is None:
                            value.pop("pimm_material_id", None)
                        else:
                            value["pimm_material_id"] = new
                    for nested in value.values():
                        visit(nested)
                elif isinstance(value, list):
                    for nested in value:
                        visit(nested)

            visit(candidate)

        mutations: dict[str, Callable[[dict[str, object]], None]] = {
            "missing": lambda candidate: rewrite_all(
                candidate, "BLACK_POWDERCOAT", None
            ),
            "blank": lambda candidate: rewrite_all(
                candidate, "BLACK_POWDERCOAT", ""
            ),
            "wrong": lambda candidate: rewrite_all(
                candidate, "BLACK_POWDERCOAT", "WRONG_SHARED_MATERIAL"
            ),
        }

        def swap(candidate: dict[str, object]) -> None:
            rewrite_all(candidate, "CONTROLLER_ACTIVE", "__SWAP__")
            rewrite_all(candidate, "CONTROLLER_INACTIVE", "CONTROLLER_ACTIVE")
            rewrite_all(candidate, "__SWAP__", "CONTROLLER_INACTIVE")

        def duplicate(candidate: dict[str, object]) -> None:
            duplicate_identity = {
                "name": "PIMM_BLACK_POWDERCOAT_COPY",
                "type": "Material",
                "library": None,
                "pimm_material_id": "BLACK_POWDERCOAT",
            }
            candidate["materials"].append(
                {"identity": duplicate_identity, "properties": {}, "node_tree": None}
            )
            candidate["objects"][0]["material_slots"].append(
                {"material": duplicate_identity}
            )

        def coordinated_wrong_shared_id(candidate: dict[str, object]) -> None:
            rewrite_all(candidate, "BLACK_POWDERCOAT", "NOT_IN_SHARED_CATALOG")

            def rename(value: object) -> None:
                if isinstance(value, dict):
                    if (
                        value.get("type") == "Material"
                        and value.get("pimm_material_id")
                        == "NOT_IN_SHARED_CATALOG"
                    ):
                        value["name"] = "PIMM_NOT_IN_SHARED_CATALOG"
                    for nested in value.values():
                        rename(nested)
                elif isinstance(value, list):
                    for nested in value:
                        rename(nested)

            rename(candidate)

        def add_unassigned_material(candidate: dict[str, object]) -> None:
            unassigned = {
                "name": "PIMM_UNASSIGNED",
                "type": "Material",
                "library": None,
                "pimm_material_id": "UNASSIGNED",
            }
            candidate["materials"].append(
                {"identity": unassigned, "properties": {}, "node_tree": None}
            )
            candidate["objects"].append(
                {
                    "identity": {
                        "name": "PIMM_UNASSIGNED_BODY",
                        "type": "Object",
                        "library": None,
                        "pimm_stable_id": "30G-unassigned-body",
                    },
                    "object_type": "MESH",
                    "data": {
                        "identity": {
                            "name": "PIMM_UNASSIGNED_BODY_MESH",
                            "type": "Mesh",
                            "library": None,
                        }
                    },
                    "hide_render": False,
                    "material_slots": [{"material": unassigned}],
                    "modifiers": [],
                }
            )

        mutations["swapped"] = swap
        mutations["duplicate"] = duplicate
        mutations["coordinated wrong shared ID"] = coordinated_wrong_shared_id
        mutations["unassigned"] = add_unassigned_material
        for label, mutate in mutations.items():
            with self.subTest(material_id=label):
                candidate = copy.deepcopy(valid)
                mutate(candidate)
                with self.assertRaisesRegex(
                    ValueError, "pimm_material_id|material.*(mismatch|unique|duplicate)"
                ):
                    approval_module.build_component_contract(machine, candidate)

    def test_fully_rehashed_proof_cannot_reclassify_shared_material_as_master_local(
        self,
    ) -> None:
        """Catches a coordinated Task 5 proof/machine role-classification bypass."""

        with TemporaryDirectory() as root_text, TemporaryDirectory(
            dir=REPO_ROOT
        ) as machine_root_text:
            root = Path(root_text)
            proof = _proof_manifest(root, "a" * 64)
            master = (root / "inputs" / "PIMM-30G-MASTER.blend").resolve()

            def move_shared_material_to_master(authored: dict[str, object]) -> None:
                def visit(value: object) -> None:
                    if isinstance(value, dict):
                        if (
                            value.get("type") == "Material"
                            and value.get("pimm_material_id") == "BLACK_POWDERCOAT"
                        ):
                            value["library"] = str(master)
                        for nested in value.values():
                            visit(nested)
                    elif isinstance(value, list):
                        for nested in value:
                            visit(nested)

                visit(authored)

            _rewrite_proof_authored_settings(proof, move_shared_material_to_master)
            machine = json.loads(
                APPROVED_COMPONENT_MACHINE_FIXTURE.read_text(encoding="utf-8")
            )
            machine["controller"]["approved_machine_local_material_ids"].append(
                "BLACK_POWDERCOAT"
            )
            machine_path = _write_json(
                Path(machine_root_text) / "coordinated-machine-contract.json", machine
            )

            with patch.object(
                approval_module,
                "_machine_contract_path",
                return_value=machine_path,
            ):
                with self.assertRaisesRegex(
                    ValueError, "shared material catalog|machine contract"
                ):
                    record_decision(
                        proof,
                        SHOT_ID,
                        "approved",
                        "natth",
                        "coordinated material-role mutation",
                    )

            self.assertFalse((proof.parent / "approvals").exists())
            self.assertFalse((root / "renders" / "final").exists())

    def test_component_authority_rejects_lexical_library_aliases_and_missing_topology(
        self,
    ) -> None:
        """Catches canonical targets hiding the lexical path Blender will open."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            (
                authored,
                _,
                roots,
                evidence,
                master,
                material_library,
            ) = _component_authority_fixture(root)
            machine = _approved_component_machine_contract()
            validator = approval_module.build_authorized_component_contract

            relative = copy.deepcopy(authored)
            material_record = next(
                record
                for record in relative["library_authorities"]
                if record["canonical_path"] == str(material_library.resolve())
            )
            material_record["raw_filepath"] = f"//{material_library.name}"
            self.assertEqual(
                validator(machine, relative, roots, evidence)["schema"],
                "pimm-final-component-contract/v1",
            )

            missing = copy.deepcopy(authored)
            missing["library_authorities"] = []
            with self.assertRaisesRegex(ValueError, "lexical|library authorit|topology"):
                validator(machine, missing, roots, evidence)

            alias_root = root / "library-alias"
            os.symlink(master.parent, alias_root, target_is_directory=True)
            aliased = copy.deepcopy(authored)
            master_record = next(
                record
                for record in aliased["library_authorities"]
                if record["canonical_path"] == str(master.resolve())
            )
            master_record["raw_filepath"] = f"//../library-alias/{master.name}"
            master_record["lexical_path"] = str(alias_root / master.name)
            with self.assertRaisesRegex(ValueError, "alias|reparse|junction|symlink"):
                validator(machine, aliased, roots, evidence)

            nested_alias = copy.deepcopy(authored)
            nested_record = next(
                record
                for record in nested_alias["library_authorities"]
                if record["canonical_path"] == str(material_library.resolve())
            )
            nested_record["raw_filepath"] = f"//{material_library.name}"
            nested_record["lexical_path"] = str(alias_root / material_library.name)
            nested_record["parent_canonical_path"] = str(master.resolve())
            with self.assertRaisesRegex(ValueError, "alias|reparse|junction|symlink"):
                validator(machine, nested_alias, roots, evidence)

    def test_component_authority_resolves_indirect_relative_library_from_scene(
        self,
    ) -> None:
        """Catches approval rebasing Blender's scene-relative library path to its parent."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            (
                authored,
                _,
                roots,
                evidence,
                _,
                material_library,
            ) = _component_authority_fixture(root)
            scene = root / "scenes" / "fixtures" / "scene.blend"
            scene.parent.mkdir(parents=True)
            scene.write_bytes(b"nested scene evidence")
            evidence["scene"] = approval_module.stable_file_record(
                scene, root, "asset", "scene"
            )
            material_record = next(
                record
                for record in authored["library_authorities"]
                if record["canonical_path"] == str(material_library.resolve())
            )
            material_record["raw_filepath"] = (
                f"//../../inputs/{material_library.name}"
            )

            result = approval_module.build_authorized_component_contract(
                _approved_component_machine_contract(), authored, roots, evidence
            )

            self.assertEqual(result["schema"], "pimm-final-component-contract/v1")

    def test_owner_approval_rejects_fully_rehashed_lexical_library_alias(
        self,
    ) -> None:
        """Catches Task 5 proof rehashing after canonicalization erased an alias."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            proof = _proof_manifest(root, "a" * 64)
            inputs = root / "inputs"
            alias_root = root / "approved-library-alias"
            os.symlink(inputs, alias_root, target_is_directory=True)

            def install_alias(authored: dict[str, object]) -> None:
                master = inputs / "PIMM-30G-MASTER.blend"
                record = next(
                    item
                    for item in authored["library_authorities"]
                    if item["canonical_path"] == str(master.resolve())
                )
                record["raw_filepath"] = f"//../approved-library-alias/{master.name}"
                record["lexical_path"] = str(alias_root / master.name)

            _rewrite_proof_authored_settings(proof, install_alias)
            with patch.object(
                approval_module,
                "_machine_contract_path",
                return_value=APPROVED_COMPONENT_MACHINE_FIXTURE,
                create=True,
            ):
                with self.assertRaisesRegex(
                    ValueError, "alias|reparse|junction|symlink"
                ):
                    record_decision(
                        proof,
                        SHOT_ID,
                        "approved",
                        "natth",
                        "lexical alias must remain visible",
                    )
            self.assertFalse((proof.parent / "approvals").exists())

    def test_owner_approval_rejects_same_name_unpinned_component_library(self) -> None:
        """Catches genuine Task 5 evidence approving a same-name sidecar library."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            proof = _proof_manifest(root, "a" * 64)
            sidecar = root / "sidecar" / "PIMM-30G-MASTER.blend"
            sidecar.parent.mkdir()
            sidecar.write_bytes(b"unapproved master bytes with familiar datablock names")

            def mutate(authored: dict[str, object]) -> None:
                for obj in authored["objects"]:
                    if obj["identity"].get("pimm_stable_id") != "30G-material-body":
                        continue
                    obj["identity"]["library"] = str(sidecar.resolve())
                    obj["data"]["identity"]["library"] = str(sidecar.resolve())
                    replacement = obj["identity"]
                    for identity in authored["collection_tree"]["objects"]:
                        if identity.get("pimm_stable_id") == "30G-material-body":
                            identity.clear()
                            identity.update(replacement)
                authored["collection_tree"]["objects"].sort(
                    key=lambda identity: json.dumps(
                        identity, sort_keys=True, separators=(",", ":")
                    )
                )

            _rewrite_proof_authored_settings(proof, mutate)
            with self.assertRaisesRegex(
                ValueError, "linked Blender library|pinned master|material-library"
            ):
                record_decision(
                    proof, SHOT_ID, "approved", "natth", "must remain pinned"
                )
            self.assertFalse((proof.parent / "approvals").exists())

    def test_linked_library_drift_after_authorization_blocks_before_native_blender(
        self,
    ) -> None:
        """Catches a master/material race between authorization and native reopen."""

        for evidence_name in ("master", "material_library"):
            with self.subTest(evidence=evidence_name), TemporaryDirectory() as root_text:
                root = Path(root_text)
                approval, final_contract = write_approval_fixture(
                    root, "approved", "a" * 64
                )
                final_payload = json.loads(final_contract.read_text(encoding="utf-8"))
                dependency = Path(final_payload["evidence"][evidence_name]["path"])
                native_builder = final_module.build_authorized_component_contract
                injected = False

                def inject_after_component_authorization(
                    *args: object, **kwargs: object
                ) -> dict[str, object]:
                    nonlocal injected
                    contract = native_builder(*args, **kwargs)
                    if not injected:
                        injected = True
                        dependency.write_bytes(
                            b"mutated linked library with retained names and stable IDs"
                        )
                    return contract

                with (
                    patch.object(
                        final_module,
                        "build_authorized_component_contract",
                        side_effect=inject_after_component_authorization,
                    ),
                    patch.object(final_module.subprocess, "run") as blender_run,
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        rf"{evidence_name.replace('_', '[ _]')}.*drift|evidence drift",
                    ):
                        run_authorized_final(approval, final_contract)

                self.assertTrue(injected)
                blender_run.assert_not_called()
                release_parent = root / "renders" / "final"
                self.assertFalse((release_parent / RELEASE_ID).exists())
                self.assertEqual(
                    list(release_parent.glob(f".{RELEASE_ID}-*.stage")), []
                )

    @unittest.skipUnless(os.name == "nt", "Windows sharing authority is required")
    def test_native_blender_holds_linked_library_bytes_against_in_process_swap(
        self,
    ) -> None:
        """Catches a same-path library rewrite while Blender is resolving links."""

        for evidence_name in ("master", "material_library"):
            with self.subTest(evidence=evidence_name), TemporaryDirectory() as root_text:
                root = Path(root_text)
                approval, final_contract = write_approval_fixture(
                    root, "approved", "a" * 64
                )
                final_payload = json.loads(final_contract.read_text(encoding="utf-8"))
                dependency = Path(final_payload["evidence"][evidence_name]["path"])
                original = dependency.read_bytes()
                attempted = False

                def inject_while_blender_has_authority(
                    *args: object, **kwargs: object
                ) -> SimpleNamespace:
                    nonlocal attempted
                    del args, kwargs
                    attempted = True
                    dependency.write_bytes(
                        b"same stable IDs and names, different linked-library bytes"
                    )
                    return SimpleNamespace(returncode=0, stderr="", stdout="")

                with patch.object(
                    final_module.subprocess,
                    "run",
                    side_effect=inject_while_blender_has_authority,
                ):
                    with self.assertRaisesRegex(
                        ValueError, "evidence drift|held-authority"
                    ):
                        run_authorized_final(approval, final_contract)

                self.assertTrue(attempted)
                self.assertEqual(dependency.read_bytes(), original)
                release_parent = root / "renders" / "final"
                self.assertFalse((release_parent / RELEASE_ID).exists())
                self.assertEqual(
                    list(release_parent.glob(f".{RELEASE_ID}-*.stage")), []
                )

    @unittest.skipUnless(os.name == "nt", "Windows reparse authority is required")
    def test_native_load_blocks_library_directory_retarget_and_restore_race(
        self,
    ) -> None:
        """Catches a lexical library directory becoming an attacker symlink at open."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            approval, final_contract = write_approval_fixture(
                root, "approved", "a" * 64
            )
            approved_directory = root / "inputs"
            parked_directory = root / "inputs-approved"
            attacker_directory = root / "attacker-library-target"
            attacker_directory.mkdir()
            attacker_master = attacker_directory / "PIMM-30G-MASTER.blend"
            attacker_material = attacker_directory / "PIMM-MATERIAL-LIBRARY.blend"
            attacker_master.write_bytes(b"attacker master survives")
            attacker_material.write_bytes(b"attacker material survives")
            probe = root / "symlink-capability-probe"
            try:
                os.symlink(attacker_directory, probe, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"directory symlink unavailable: {error}")
            else:
                probe.unlink()
            attempted = False

            def retarget_restore_before_capture(
                *args: object, **kwargs: object
            ) -> SimpleNamespace:
                nonlocal attempted
                del args, kwargs
                attempted = True
                approved_directory.rename(parked_directory)
                try:
                    os.symlink(
                        attacker_directory,
                        approved_directory,
                        target_is_directory=True,
                    )
                    self.assertEqual(
                        (approved_directory / attacker_master.name).read_bytes(),
                        b"attacker master survives",
                    )
                finally:
                    if approved_directory.is_symlink():
                        approved_directory.unlink()
                    parked_directory.rename(approved_directory)
                return SimpleNamespace(returncode=0, stderr="", stdout="")

            with patch.object(
                final_module.subprocess,
                "run",
                side_effect=retarget_restore_before_capture,
            ):
                with self.assertRaisesRegex(ValueError, "held-authority|write/delete race"):
                    run_authorized_final(approval, final_contract)

            self.assertTrue(attempted)
            self.assertTrue(approved_directory.is_dir())
            self.assertFalse(parked_directory.exists())
            self.assertEqual(attacker_master.read_bytes(), b"attacker master survives")
            self.assertEqual(attacker_material.read_bytes(), b"attacker material survives")
            release_parent = root / "renders" / "final"
            self.assertFalse((release_parent / RELEASE_ID).exists())
            self.assertEqual(list(release_parent.glob(f".{RELEASE_ID}-*.stage")), [])

    @unittest.skipUnless(os.name == "nt", "Windows reparse authority is required")
    def test_release_regeneration_blocks_library_retarget_restore_before_marker(
        self,
    ) -> None:
        """Catches a restored lexical alias hiding bytes opened by release Blender."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            output = write_release_output_fixture(
                root, "proof-20260815T153000Z-a1b2c3d"
            )
            approved_directory = root / "inputs"
            parked_directory = root / "inputs-approved"
            attacker_directory = root / "attacker-library-target"
            attacker_directory.mkdir()
            attacker_master = attacker_directory / "PIMM-30G-MASTER.blend"
            attacker_material = attacker_directory / "PIMM-MATERIAL-LIBRARY.blend"
            attacker_master.write_bytes(b"attacker master survives")
            attacker_material.write_bytes(b"attacker material survives")
            probe = root / "symlink-capability-probe"
            try:
                os.symlink(attacker_directory, probe, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"directory symlink unavailable: {error}")
            else:
                probe.unlink()
            attempted = False

            def retarget_restore_during_regeneration(
                *args: object, **kwargs: object
            ) -> tuple[bytes, bytes, dict[str, bytes]]:
                nonlocal attempted
                del kwargs
                attempted = True
                approved_directory.rename(parked_directory)
                try:
                    os.symlink(
                        attacker_directory,
                        approved_directory,
                        target_is_directory=True,
                    )
                    self.assertEqual(
                        (approved_directory / attacker_material.name).read_bytes(),
                        b"attacker material survives",
                    )
                finally:
                    if approved_directory.is_symlink():
                        approved_directory.unlink()
                    parked_directory.rename(approved_directory)
                dimensions = args[2]
                png, masks = _structured_component_pixels()
                return (
                    png,
                    _float_exr_bytes(int(dimensions[0]), int(dimensions[1])),
                    masks,
                )

            with patch.object(
                release_module,
                "_regenerate_component_evidence",
                side_effect=retarget_restore_during_regeneration,
            ):
                with self.assertRaisesRegex(ValueError, "held-authority|write/delete race"):
                    build_release_manifest(RELEASE_ID, [output])

            self.assertTrue(attempted)
            self.assertTrue(approved_directory.is_dir())
            self.assertFalse(parked_directory.exists())
            self.assertEqual(attacker_master.read_bytes(), b"attacker master survives")
            self.assertEqual(attacker_material.read_bytes(), b"attacker material survives")
            self.assertTrue(output.is_file())
            self.assertFalse((output.parents[1] / "release-manifest.json").exists())

    def test_linked_library_drift_blocks_before_and_during_release_regeneration(
        self,
    ) -> None:
        """Catches independent regeneration consuming raced master/material bytes."""

        for evidence_name in ("master", "material_library"):
            with self.subTest(phase="before", evidence=evidence_name), TemporaryDirectory() as root_text:
                output = write_release_output_fixture(
                    Path(root_text), "proof-20260815T153000Z-a1b2c3d"
                )
                payload = json.loads(output.read_text(encoding="utf-8"))
                final_payload = json.loads(
                    Path(payload["authorized_final_contract_path"]).read_text(
                        encoding="utf-8"
                    )
                )
                dependency = Path(final_payload["evidence"][evidence_name]["path"])
                native_builder = release_module.build_authorized_component_contract
                injected = False

                def inject_before_regeneration(
                    *args: object, **kwargs: object
                ) -> dict[str, object]:
                    nonlocal injected
                    contract = native_builder(*args, **kwargs)
                    if not injected:
                        injected = True
                        dependency.write_bytes(b"raced before independent regeneration")
                    return contract

                release_module._regenerate_component_evidence.reset_mock()
                with patch.object(
                    release_module,
                    "build_authorized_component_contract",
                    side_effect=inject_before_regeneration,
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        rf"{evidence_name.replace('_', '[ _]')}.*drift|evidence drift",
                    ):
                        build_release_manifest(RELEASE_ID, [output])
                self.assertTrue(injected)
                release_module._regenerate_component_evidence.assert_not_called()
                self.assertFalse((output.parents[1] / "release-manifest.json").exists())

            with self.subTest(phase="during", evidence=evidence_name), TemporaryDirectory() as root_text:
                output = write_release_output_fixture(
                    Path(root_text), "proof-20260815T153000Z-a1b2c3d"
                )
                payload = json.loads(output.read_text(encoding="utf-8"))
                final_payload = json.loads(
                    Path(payload["authorized_final_contract_path"]).read_text(
                        encoding="utf-8"
                    )
                )
                dependency = Path(final_payload["evidence"][evidence_name]["path"])

                def inject_during_regeneration(
                    *args: object, **kwargs: object
                ) -> tuple[bytes, bytes, dict[str, bytes]]:
                    del args, kwargs
                    dependency.write_bytes(b"raced during independent regeneration")
                    png, masks = _structured_component_pixels()
                    return png, _float_exr_bytes(64, 48), masks

                with patch.object(
                    release_module,
                    "_regenerate_component_evidence",
                    side_effect=inject_during_regeneration,
                ) as regenerator:
                    with self.assertRaisesRegex(
                        ValueError,
                        rf"{evidence_name.replace('_', '[ _]')}.*drift|evidence drift",
                    ):
                        build_release_manifest(RELEASE_ID, [output])
                regenerator.assert_called_once()
                self.assertFalse((output.parents[1] / "release-manifest.json").exists())

    def test_final_qa_binds_approved_component_identities_to_exact_masked_pixels(self) -> None:
        """Catches whole-frame regions or copied claims without approved object masks."""

        machine = _approved_component_machine_contract()
        authored = _approved_component_authored_state()
        component_contract = approval_module.build_component_contract(machine, authored)
        png, masks = _structured_component_pixels()
        qa = approval_module.compute_final_qa(
            png,
            {"start": png, "end": png},
            [64, 48],
            machine,
            {"animation_contract": None},
            component_contract=component_contract,
            component_mask_bytes=masks,
            material_library_sha256="A" * 64,
            scene_contract_sha256="B" * 64,
            machine_contract_sha256="C" * 64,
        )
        self.assertEqual(qa["material"]["stable_object_ids"], ["30G-material-body"])
        self.assertGreater(qa["material"]["visible_overlap_pixels"], 0)
        self.assertEqual(qa["controller"]["display_values"], ["300", "300"])
        self.assertEqual(
            qa["controller"]["observed_digit_patterns"],
            [_DIGIT_SEGMENTS[digit] for value in ("300", "300") for digit in value],
        )
        self.assertGreater(qa["controller"]["active_segment_count"], 0)
        self.assertGreater(qa["controller"]["inactive_segment_count"], 0)

    def test_static_final_qa_keeps_unapproved_controller_motion_map_explicitly_blocked(self) -> None:
        """Allows still publication without inventing future animation segment identities."""

        machine = _approved_component_machine_contract()
        machine["animation"] = {
            "status": "blocked_pending_owner_motion_map",
            "allowed_controls": [],
        }
        machine["controller"].pop("approved_segments")
        machine["controller"].pop("approved_machine_local_material_ids")
        authored = _approved_component_authored_state()
        authored["objects"] = [authored["objects"][0]]
        authored["materials"] = [authored["materials"][0]]
        component_contract = approval_module.build_component_contract(machine, authored)
        self.assertEqual(component_contract["segments"], [])
        png, masks = _structured_component_pixels()
        qa = approval_module.compute_final_qa(
            png,
            {"start": png, "end": png},
            [64, 48],
            machine,
            {"animation_contract": None},
            component_contract=component_contract,
            component_mask_bytes={"material": masks["material"]},
            material_library_sha256="A" * 64,
            scene_contract_sha256="B" * 64,
            machine_contract_sha256="C" * 64,
        )
        self.assertEqual(
            qa["controller"]["verification_status"],
            "blocked_pending_owner_motion_map",
        )
        self.assertEqual(qa["controller"]["segments"], [])

    def test_final_qa_rejects_rehashed_nonuniform_wrong_component_pattern(self) -> None:
        """Catches a nonuniform counterfeit whose hashes match pixels but digits are wrong."""

        machine = _approved_component_machine_contract()
        component_contract = approval_module.build_component_contract(
            machine, _approved_component_authored_state()
        )
        png, masks = _structured_component_pixels(invert_segment_states=True)
        with self.assertRaisesRegex(ValueError, "controller.*pattern|segment.*state"):
            approval_module.compute_final_qa(
                png,
                {"start": png, "end": png},
                [64, 48],
                machine,
                {"animation_contract": None},
                component_contract=component_contract,
                component_mask_bytes=masks,
                material_library_sha256="A" * 64,
                scene_contract_sha256="B" * 64,
                machine_contract_sha256="C" * 64,
            )

    def test_final_qa_rejects_incomplete_swapped_and_unrelated_component_evidence(self) -> None:
        """Catches mask-set drift, swapped identities, all-one states, and arbitrary gradients."""

        machine = _approved_component_machine_contract()
        component_contract = approval_module.build_component_contract(
            machine, _approved_component_authored_state()
        )
        png, masks = _structured_component_pixels()

        def compute(candidate_png: bytes, candidate_masks: dict[str, bytes]) -> None:
            approval_module.compute_final_qa(
                candidate_png,
                {"start": candidate_png, "end": candidate_png},
                [64, 48],
                machine,
                {"animation_contract": None},
                component_contract=component_contract,
                component_mask_bytes=candidate_masks,
                material_library_sha256="A" * 64,
                scene_contract_sha256="B" * 64,
                machine_contract_sha256="C" * 64,
            )

        first_id = str(component_contract["segments"][0]["stable_object_id"])
        second_id = str(component_contract["segments"][1]["stable_object_id"])
        mutations: list[tuple[str, bytes, dict[str, bytes], str]] = []
        missing = dict(masks)
        del missing[first_id]
        mutations.append(("missing", png, missing, "missing|extra"))
        extra = dict(masks)
        extra["unapproved-segment"] = masks[first_id]
        mutations.append(("extra", png, extra, "missing|extra"))
        swapped = dict(masks)
        swapped[first_id], swapped[second_id] = swapped[second_id], swapped[first_id]
        mutations.append(("swapped", png, swapped, "layout|swapped|pattern|state"))

        for state_name, color in (
            ("all active", (245, 70, 25, 255)),
            ("all inactive", (24, 8, 6, 255)),
        ):
            with Image.open(io.BytesIO(png)) as source:
                recolored = source.convert("RGBA")
            for segment in component_contract["segments"]:
                stable_id = str(segment["stable_object_id"])
                with Image.open(io.BytesIO(masks[stable_id])) as raw_mask:
                    segment_mask = raw_mask.convert("L")
                for y in range(segment_mask.height):
                    for x in range(segment_mask.width):
                        if segment_mask.getpixel((x, y)):
                            recolored.putpixel((x, y), color)
            mutations.append(
                (state_name, _png_bytes(recolored), dict(masks), "active/inactive|pattern|state")
            )

        gradient = Image.new("RGBA", (64, 48), (0, 0, 0, 255))
        for y in range(gradient.height):
            for x in range(gradient.width):
                gradient.putpixel((x, y), (x * 3, y * 4, (x + y) * 2, 255))
        mutations.append(
            ("unrelated gradient", _png_bytes(gradient), dict(masks), "active/inactive|pattern|state")
        )

        for label, candidate_png, candidate_masks, expected in mutations:
            with self.subTest(mutation=label), self.assertRaisesRegex(ValueError, expected):
                compute(candidate_png, candidate_masks)

    @unittest.skipUnless(BLENDER.is_file(), "fixture Blender runtime unavailable")
    def test_native_final_runner_emits_real_exr_png_webp_and_manifest(self) -> None:
        """Catches native evidence claims that fail on approved linked components."""

        with TemporaryDirectory() as root_text:
            root = Path(root_text)
            scene_path = root / "inputs" / "scene.blend"
            scene_path.parent.mkdir(parents=True)
            setup = textwrap.dedent(
                f"""
                import bpy

                material_library_path = {str(root / 'inputs' / 'PIMM-MATERIAL-LIBRARY.blend')!r}
                master_path = {str(root / 'inputs' / 'PIMM-30G-MASTER.blend')!r}
                bpy.ops.wm.read_factory_settings(use_empty=True)

                def component_material(name, color, stable_id=None, material_id=None):
                    material = bpy.data.materials.new(name)
                    material.use_nodes = True
                    material.use_fake_user = True
                    if stable_id is not None:
                        material['pimm_stable_id'] = stable_id
                    if material_id is not None:
                        material['pimm_material_id'] = material_id
                    material.node_tree['pimm_stable_id'] = f'{{name}}-node-tree'
                    principled = material.node_tree.nodes.get('Principled BSDF')
                    principled.inputs['Base Color'].default_value = (*color, 1.0)
                    principled.inputs['Roughness'].default_value = 0.45
                    return material

                body_material = component_material(
                    'PIMM_BLACK_POWDERCOAT', (0.08, 0.18, 0.35),
                    'PIMM-MAT-BLACK-POWDERCOAT', 'BLACK_POWDERCOAT'
                )
                bpy.ops.wm.save_as_mainfile(filepath=material_library_path)

                bpy.ops.wm.read_factory_settings(use_empty=True)
                with bpy.data.libraries.load(material_library_path, link=True) as (data_from, data_to):
                    data_to.materials = ['PIMM_BLACK_POWDERCOAT']
                body_material = data_to.materials[0]
                active_material = component_material(
                    'DISPLAY_LIT_RED', (1.0, 0.05, 0.01),
                    material_id='CONTROLLER_ACTIVE'
                )
                inactive_material = component_material(
                    'DISPLAY_UNLIT_RED', (0.02, 0.002, 0.001),
                    material_id='CONTROLLER_INACTIVE'
                )
                published = bpy.data.collections.new('PIMM_PUBLISHED')
                bpy.context.scene.collection.children.link(published)

                def move_to_published(obj):
                    for collection in list(obj.users_collection):
                        collection.objects.unlink(obj)
                    published.objects.link(obj)

                bpy.ops.mesh.primitive_cube_add(location=(-1.6, 0.0, 0.0), scale=(1.15, 1.55, 0.18))
                body = bpy.context.object
                body.name = 'PIMM_30G_MATERIAL_BODY'
                body['pimm_stable_id'] = '30G-material-body'
                body.data.materials.append(body_material)
                move_to_published(body)

                labels = ('a', 'b', 'c', 'd', 'e', 'f', 'g')
                patterns = ('1011011', '1110111', '1110111', '1011011', '1110111', '1110111')
                segments = [
                    {{'stable_object_id': f'30G-display-d{{digit}}-{{label}}', 'active': bit == '1'}}
                    for digit, pattern in enumerate(patterns)
                    for label, bit in zip(labels, pattern)
                ]
                digit_x = (0.25, 0.70, 1.15, 1.75, 2.20, 2.65)
                positions = {{
                    'a': (0.0, 0.38, 0.14, 0.06),
                    'b': (-0.17, 0.20, 0.07, 0.11),
                    'c': (0.17, 0.20, 0.07, 0.11),
                    'd': (0.0, 0.0, 0.14, 0.06),
                    'e': (-0.17, -0.20, 0.07, 0.11),
                    'f': (0.17, -0.20, 0.07, 0.11),
                    'g': (0.0, -0.38, 0.14, 0.06),
                }}
                for index, segment in enumerate(segments):
                    digit_index, label_index = divmod(index, 7)
                    label = labels[label_index]
                    offset_x, offset_y, scale_x, scale_y = positions[label]
                    bpy.ops.mesh.primitive_cube_add(
                        location=(digit_x[digit_index] + offset_x, offset_y, 0.0),
                        scale=(scale_x, scale_y, 0.05),
                    )
                    obj = bpy.context.object
                    obj.name = segment['stable_object_id']
                    obj['pimm_stable_id'] = segment['stable_object_id']
                    obj.data.materials.append(active_material if segment['active'] else inactive_material)
                    move_to_published(obj)

                bpy.ops.wm.save_as_mainfile(filepath=master_path)
                bpy.ops.wm.read_factory_settings(use_empty=True)
                with bpy.data.libraries.load(master_path, link=True) as (data_from, data_to):
                    data_to.collections = ['PIMM_PUBLISHED']
                bpy.context.scene.collection.children.link(data_to.collections[0])

                bpy.ops.object.camera_add(location=(0, 0, 10))
                camera = bpy.context.object
                camera.name = 'CAM_HERO'
                camera.data.type = 'ORTHO'
                camera.data.ortho_scale = 6.5
                bpy.context.scene.camera = camera
                bpy.ops.object.light_add(type='AREA', location=(0, 0, 8))
                light = bpy.context.object
                light.name = 'PIMM_FIXTURE_KEY'
                light.data.energy = 1200
                light.data.shape = 'DISK'
                light.data.size = 6
                scene = bpy.context.scene
                scene.world = None
                scene.render.engine = 'CYCLES'
                scene.cycles.samples = 1
                scene.render.film_transparent = True
                scene.render.resolution_x = 64
                scene.render.resolution_y = 48
                scene.render.resolution_percentage = 100
                bpy.ops.wm.save_as_mainfile(filepath={str(scene_path)!r})
                """
            )
            result = subprocess.run(
                [str(BLENDER), "--factory-startup", "-b", "--python-expr", setup],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(scene_path.is_file(), result.stdout + result.stderr)
            approval_path, final_contract_path = write_approval_fixture(root, "approved", "a" * 64)
            approval_payload = json.loads(approval_path.read_text(encoding="utf-8"))
            self.assertEqual(
                Path(approval_payload["evidence"]["blender_binary"]["path"]),
                BLENDER.resolve(),
            )
            render_metadata = json.loads(
                Path(approval_payload["evidence"]["render_metadata"]["path"]).read_text(
                    encoding="utf-8"
                )
            )
            authored_before = render_metadata["authored_settings"]["before"]
            expected_master = Path(
                approval_payload["evidence"]["master"]["path"]
            )
            expected_material_library = Path(
                approval_payload["evidence"]["material_library"]["path"]
            )
            linked_segments = [
                obj for obj in authored_before["objects"]
                if str(obj["identity"].get("pimm_stable_id", "")).startswith("30G-display-")
            ]
            self.assertEqual(len(linked_segments), 42)
            self.assertEqual(
                {Path(obj["identity"]["library"]) for obj in linked_segments},
                {expected_master},
            )
            self.assertEqual(
                {Path(obj["data"]["identity"]["library"]) for obj in linked_segments},
                {expected_master},
            )
            material_by_id = {
                material["identity"].get("pimm_material_id"): material["identity"]
                for material in authored_before["materials"]
            }
            self.assertEqual(
                material_by_id["BLACK_POWDERCOAT"]["library"],
                str(expected_material_library),
            )
            self.assertEqual(
                material_by_id["CONTROLLER_ACTIVE"]["library"],
                str(expected_master),
            )
            self.assertEqual(
                material_by_id["CONTROLLER_INACTIVE"]["library"],
                str(expected_master),
            )
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
            component = manifest["component_evidence"]
            self.assertEqual(component["schema"], "pimm-final-component-evidence/v1")
            self.assertEqual(len(component["masks"]), 43)
            for record in component["masks"]:
                self.assertEqual(_sha256(manifest_path.parent / record["path"]), record["sha256"])
            self.assertEqual(
                manifest["qa"]["controller"]["observed_digit_patterns"],
                [_DIGIT_SEGMENTS[digit] for value in ("300", "300") for digit in value],
            )
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
            "dependency_sha256": "dependency SHA-256 drift",
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
                    _mutate_fixture_region_family(output, 39, 11, (0, 255, 0, 255))
                    _refresh_final_fixture_manifest(
                        output, payload, preserve_qa_section="controller"
                    )
                    expected = "controller|final pixels"
                elif mutation == "changed material pixels":
                    _mutate_fixture_region_family(output, 10, 20, (255, 255, 0, 255))
                    _refresh_final_fixture_manifest(
                        output, payload, preserve_qa_section="material"
                    )
                    expected = "material|final pixels"
                else:
                    _write_uniform_fixture_family(output)
                    expected = "uniform|material|controller|dedicated"
                    with self.assertRaisesRegex(ValueError, expected):
                        _refresh_final_fixture_manifest(output, payload)
                    self.assertFalse((output.parents[1] / "release-manifest.json").exists())
                    continue
                with self.assertRaisesRegex(ValueError, expected):
                    build_release_manifest(RELEASE_ID, [output])
                self.assertFalse((output.parents[1] / "release-manifest.json").exists())

    def test_release_rejects_fully_rehashed_component_identity_counterfeit(self) -> None:
        """Catches wrong physical mask identities even when every hash and QA is refreshed."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            component = payload["component_evidence"]
            contract = component["contract"]
            first = contract["segments"][0]
            other = contract["segments"][7]
            first_id = first["stable_object_id"]
            other_id = other["stable_object_id"]
            for field in (
                "stable_object_id",
                "object_identity_sha256",
                "material_identity_sha256",
            ):
                first[field], other[field] = other[field], first[field]
            records = {record["mask_id"]: record for record in component["masks"]}
            records[first_id]["mask_id"] = other_id
            records[other_id]["mask_id"] = first_id
            unsigned = {key: value for key, value in contract.items() if key != "sha256"}
            contract["sha256"] = _canonical_fixture_sha(unsigned)
            _refresh_final_fixture_manifest(output, payload)

            refreshed = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(refreshed["qa"]["controller"]["observed_digit_patterns"], [
                _DIGIT_SEGMENTS[digit] for value in ("300", "300") for digit in value
            ])
            with self.assertRaisesRegex(ValueError, "component.*contract|identity|mask"):
                build_release_manifest(RELEASE_ID, [output])

    def test_release_rejects_fully_rehashed_fabricated_component_regions(self) -> None:
        """Catches fabricated masks/pixels that retain the exact approved contract."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            original_contract = copy.deepcopy(payload["component_evidence"]["contract"])
            family = output.parent
            translated_paths = [
                family / f"{SHOT_ID}--transparent.png",
                family / f"{SHOT_ID}--animation-start.png",
                family / f"{SHOT_ID}--animation-end.png",
            ]
            for path in translated_paths:
                with Image.open(path) as source:
                    translated = Image.new("RGBA", source.size, (0, 0, 0, 0))
                    translated.alpha_composite(source.convert("RGBA"), (0, 3))
                translated.save(path, format="PNG")
            with Image.open(translated_paths[0]) as source:
                source.save(
                    family / f"{SHOT_ID}--transparent.webp",
                    format="WEBP",
                    lossless=True,
                )
            for record in payload["component_evidence"]["masks"]:
                path = family / record["path"]
                with Image.open(path) as source:
                    translated = Image.new("L", source.size, 0)
                    translated.paste(source.convert("L"), (0, 3))
                translated.save(path, format="PNG")
            _refresh_final_fixture_manifest(output, payload)
            refreshed = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                refreshed["component_evidence"]["contract"], original_contract
            )
            with self.assertRaisesRegex(
                ValueError, "component mask.*approved|regenerated|Blender object"
            ):
                build_release_manifest(RELEASE_ID, [output])

    def test_release_rejects_repainted_pixels_under_authentic_component_masks(self) -> None:
        """Catches semantic repainting that retains every authentic object mask."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            family = output.parent
            final_png = family / f"{SHOT_ID}--transparent.png"
            with Image.open(final_png) as source:
                repainted = source.convert("RGBA")
            mask_records = {
                record["mask_id"]: family / record["path"]
                for record in payload["component_evidence"]["masks"]
            }
            with Image.open(mask_records["material"]) as source:
                material_mask = source.convert("L")
            for y in range(material_mask.height):
                for x in range(material_mask.width):
                    if material_mask.getpixel((x, y)):
                        repainted.putpixel(
                            (x, y),
                            (210 if (x + y) % 2 else 25, 180 if x % 2 else 35, 75, 220),
                        )
            for segment in payload["component_evidence"]["contract"]["segments"]:
                stable_id = str(segment["stable_object_id"])
                color = (
                    (30, 245, 40, 255)
                    if segment["expected_active"] else (5, 9, 12, 255)
                )
                with Image.open(mask_records[stable_id]) as source:
                    segment_mask = source.convert("L")
                for y in range(segment_mask.height):
                    for x in range(segment_mask.width):
                        if segment_mask.getpixel((x, y)):
                            repainted.putpixel((x, y), color)
            for path in (
                final_png,
                family / f"{SHOT_ID}--animation-start.png",
                family / f"{SHOT_ID}--animation-end.png",
            ):
                repainted.save(path, format="PNG")
            repainted.save(
                family / f"{SHOT_ID}--transparent.webp", format="WEBP", lossless=True
            )
            _refresh_final_fixture_manifest(output, payload)
            with self.assertRaisesRegex(
                ValueError, "final pixels.*approved|regenerated.*pixels|Blender render"
            ):
                build_release_manifest(RELEASE_ID, [output])
            self.assertFalse((output.parents[1] / "release-manifest.json").exists())

    def test_release_rejects_fully_rehashed_webp_only_counterfeit(self) -> None:
        """Catches a storefront WebP that no longer depicts the approved render."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            family = output.parent
            webp = family / f"{SHOT_ID}--transparent.webp"
            counterfeit = Image.new("RGBA", (64, 48), (0, 0, 0, 0))
            for y in range(8, 40):
                for x in range(5, 59):
                    counterfeit.putpixel(
                        (x, y),
                        ((x * 17 + y * 3) % 256, (x * 5) % 256, (y * 11) % 256, 255),
                    )
            counterfeit.save(webp, format="WEBP", lossless=True)
            webp_record = next(
                item for item in payload["outputs"] if item["mime_type"] == "image/webp"
            )
            webp_record["sha256"] = _sha256(webp)
            _write_json(output, payload)

            with self.assertRaisesRegex(
                ValueError, "WebP.*approved|approved.*WebP|deliverable pixels"
            ):
                build_release_manifest(RELEASE_ID, [output])
            self.assertFalse((output.parents[1] / "release-manifest.json").exists())

    def test_release_rejects_fully_rehashed_exr_only_counterfeit(self) -> None:
        """Catches a valid float EXR whose channels no longer match the approved render."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            family = output.parent
            exr = family / f"{SHOT_ID}--transparent.exr"
            _write_float_exr(exr, 64, 48, pixel_value=0.25)
            exr_record = next(
                item for item in payload["outputs"] if item["mime_type"] == "image/x-exr"
            )
            exr_record["sha256"] = _sha256(exr)
            _write_json(output, payload)

            with self.assertRaisesRegex(
                ValueError, "EXR.*approved|approved.*EXR|deliverable pixels"
            ):
                build_release_manifest(RELEASE_ID, [output])
            self.assertFalse((output.parents[1] / "release-manifest.json").exists())

    def test_release_rejects_cross_encoding_exr_digest_collision(self) -> None:
        """Catches a ZIPS counterfeit colliding with approved uncompressed channels."""

        approved_scanline = struct.pack("<f", 0.5) * (64 * 4)
        malicious_scanline = _wrong_exr_decoder_collision(approved_scanline)
        self.assertNotEqual(malicious_scanline, approved_scanline)
        self.assertEqual(
            _former_wrong_zip_decode(malicious_scanline), approved_scanline
        )
        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            exr = output.parent / f"{SHOT_ID}--transparent.exr"
            _write_float_exr(
                exr,
                64,
                48,
                compression=2,
                raw_transform=_wrong_exr_decoder_collision,
            )
            exr_record = next(
                item for item in payload["outputs"] if item["mime_type"] == "image/x-exr"
            )
            exr_record["sha256"] = _sha256(exr)
            _write_json(output, payload)

            with self.assertRaisesRegex(
                ValueError, "EXR.*approved|approved.*EXR|deliverable pixels"
            ):
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

    @unittest.skipUnless(os.name == "nt", "Windows handle deletion is required")
    def test_atomic_json_pending_cleanup_deletes_only_its_creation_handle(self) -> None:
        """Catches pending cleanup unlinking a replacement after identity verification."""

        with TemporaryDirectory() as root_text:
            destination = Path(root_text) / "decision.json"
            parked = destination.parent / "owned-pending.json"
            competitor = b'{"competitor":true}\n'
            pending: Path | None = None
            swapped = False
            original_delete = getattr(approval_module, "_delete_owned_handle", None)
            original_create_owned = approval_module._create_owned_file
            created_descriptor: int | None = None

            def capture_creation_handle(path: Path, **kwargs: object) -> int:
                nonlocal created_descriptor
                created_descriptor = original_create_owned(path, **kwargs)
                return created_descriptor

            def fail_before_commit(path: Path) -> None:
                nonlocal pending
                pending = path
                raise OSError("injected pending publication failure")

            def replace_after_owned_verification(descriptor: int, label: str) -> None:
                nonlocal swapped
                self.assertIsNotNone(original_delete)
                self.assertIsNotNone(pending)
                self.assertEqual(descriptor, created_descriptor)
                assert pending is not None
                pending.rename(parked)
                pending.write_bytes(competitor)
                swapped = True
                original_delete(descriptor, label)

            with (
                patch.object(
                    approval_module,
                    "_create_owned_file",
                    side_effect=capture_creation_handle,
                ),
                patch.object(
                    approval_module,
                    "_delete_owned_handle",
                    create=True,
                    side_effect=replace_after_owned_verification,
                ),
            ):
                with self.assertRaisesRegex(
                    OSError, "injected pending publication failure"
                ):
                    approval_module._create_new_json(
                        destination,
                        {"complete": True},
                        before_commit=fail_before_commit,
                    )

            self.assertTrue(swapped)
            assert pending is not None
            self.assertEqual(pending.read_bytes(), competitor)
            self.assertFalse(parked.exists())
            self.assertFalse(destination.exists())

    def test_atomic_json_postcommit_requires_exact_handle_delete_support(self) -> None:
        """Catches non-Windows release publication that cannot revoke its marker exactly."""

        with TemporaryDirectory() as root_text:
            destination = Path(root_text) / "release-manifest.json"
            with patch.object(
                approval_module, "_WINDOWS_HANDLE_DELETE", False, create=True
            ):
                with self.assertRaisesRegex(OSError, "exact.*handle.*delet"):
                    approval_module._create_new_json(
                        destination,
                        {"complete": True},
                        after_commit=lambda *_: None,
                    )

            self.assertFalse(destination.exists())
            self.assertEqual(
                list(destination.parent.glob(".release-manifest.json.*.pending")), []
            )

    def test_atomic_json_non_windows_pending_cleanup_fails_closed(self) -> None:
        """Catches a pathname-unlink fallback deleting an unowned pending replacement."""

        with TemporaryDirectory() as root_text:
            destination = Path(root_text) / "decision.json"
            pending: Path | None = None

            def fail_before_commit(path: Path) -> None:
                nonlocal pending
                pending = path
                raise OSError("injected pending publication failure")

            with patch.object(
                approval_module, "_WINDOWS_HANDLE_DELETE", False, create=True
            ):
                with self.assertRaisesRegex(
                    OSError, "injected pending publication failure"
                ) as raised:
                    approval_module._create_new_json(
                        destination,
                        {"complete": True},
                        before_commit=fail_before_commit,
                    )

            self.assertIsNotNone(pending)
            assert pending is not None
            self.assertTrue(pending.exists())
            self.assertRegex(
                "\n".join(getattr(raised.exception, "__notes__", [])),
                "exact-owned cleanup.*unavailable",
            )
            self.assertFalse(destination.exists())

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
                "dependency_sha256",
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
            _write_float_exr(path, 64, 1)
            _declare_fake_zip_compression(path)
            path.write_bytes(
                _replace_only_exr_payload(
                    path.read_bytes(), lambda payload: payload[:-1]
                )
            )
            with self.assertRaisesRegex(ValueError, "EXR.*(compressed|payload|ZIP)"):
                release_module._validate_float_exr(path.read_bytes(), [64, 1])

    def test_exr_pixel_evidence_matches_uncompressed_and_zips_pixels(self) -> None:
        """Catches inverse predictor/unshuffle operations applied in the wrong order."""

        uncompressed = _float_exr_bytes(64, 1, vary_pixels=True)
        zips = _float_exr_bytes(64, 1, compression=2, vary_pixels=True)
        expected = release_module._validate_float_exr(uncompressed, [64, 1])
        actual = release_module._validate_float_exr(zips, [64, 1])
        self.assertEqual(
            actual["decoded_channels_sha256"], expected["decoded_channels_sha256"]
        )

    def test_exr_parser_accepts_and_authenticates_zips_raw_fallback(self) -> None:
        """Catches rejecting OpenEXR's equal-size uncompressed ZIP fallback chunks."""

        uncompressed = _float_exr_bytes(64, 1, vary_pixels=True)
        raw_fallback = _float_exr_bytes(
            64, 1, compression=2, vary_pixels=True, raw_fallback=True
        )
        expected = release_module._validate_float_exr(uncompressed, [64, 1])
        actual = release_module._validate_float_exr(raw_fallback, [64, 1])
        self.assertEqual(
            actual["decoded_channels_sha256"], expected["decoded_channels_sha256"]
        )

    def test_exr_parser_does_not_inflate_equal_size_zip_payload(self) -> None:
        """Catches treating a raw-fallback chunk as a zlib prefix with ignored padding."""

        zips = _float_exr_bytes(64, 1, compression=2, vary_pixels=True)
        expected_size = 64 * 4 * 4
        padded = _replace_only_exr_payload(
            zips,
            lambda payload: payload + b"\0" * (expected_size - len(payload)),
        )
        genuine = release_module._validate_float_exr(zips, [64, 1])
        raw_fallback = release_module._validate_float_exr(padded, [64, 1])
        self.assertNotEqual(
            raw_fallback["decoded_channels_sha256"],
            genuine["decoded_channels_sha256"],
        )

    def test_exr_parser_rejects_unconsumed_zlib_tail(self) -> None:
        """Catches accepting bytes after an otherwise complete compressed stream."""

        zips = _float_exr_bytes(64, 1, compression=2, vary_pixels=True)
        tailed = _replace_only_exr_payload(zips, lambda payload: payload + b"X")
        with self.assertRaisesRegex(ValueError, "EXR.*(ZIP|trailing|compressed|payload)"):
            release_module._validate_float_exr(tailed, [64, 1])

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
            payload["qa"]["alpha"]["minimum"] = 1
            payload["qa"]["alpha"]["maximum"] = 254
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
                _write_native_component_mask_fixture(family)
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
                _write_native_component_mask_fixture(family)
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

    def test_release_commit_revalidates_linked_library_identity_before_marker(
        self,
    ) -> None:
        """Catches restored master/material bytes raced at the marker commit point."""

        for evidence_name in ("master", "material_library"):
            with self.subTest(evidence=evidence_name), TemporaryDirectory() as root_text:
                output = write_release_output_fixture(
                    Path(root_text), "proof-20260815T153000Z-a1b2c3d"
                )
                payload = json.loads(output.read_text(encoding="utf-8"))
                approval_payload = json.loads(
                    Path(payload["approval_path"]).read_text(encoding="utf-8")
                )
                dependency = Path(
                    approval_payload["evidence"][evidence_name]["path"]
                )
                original = dependency.read_bytes()
                original_stat = dependency.stat()
                injected = False
                original_create = release_module._create_new_json

                def inject_transient_drift(
                    path: Path, manifest: dict[str, object], **kwargs: object
                ) -> dict[str, object]:
                    nonlocal injected
                    injected = True
                    dependency.write_bytes(b"transient linked-library attacker bytes")
                    dependency.write_bytes(original)
                    os.utime(
                        dependency,
                        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
                    )
                    return original_create(path, manifest, **kwargs)

                with patch.object(
                    release_module,
                    "_create_new_json",
                    side_effect=inject_transient_drift,
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        rf"{evidence_name.replace('_', '[ _]')}.*drift|evidence drift|identity",
                    ):
                        build_release_manifest(RELEASE_ID, [output])

                self.assertTrue(injected)
                self.assertEqual(dependency.read_bytes(), original)
                self.assertFalse((output.parents[1] / "release-manifest.json").exists())

    def test_release_removes_owned_marker_when_held_topology_exit_fails(
        self,
    ) -> None:
        """Catches topology-manifest drift after marker creation escaping cleanup."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            final = json.loads(
                Path(payload["authorized_final_contract_path"]).read_text(
                    encoding="utf-8"
                )
            )
            metadata = Path(final["evidence"]["render_metadata"]["path"])
            original = metadata.read_bytes()
            original_stat = metadata.stat()
            attempted = False
            original_create = release_module._create_new_json

            def drift_after_owned_marker(
                path: Path, marker: dict[str, object], **kwargs: object
            ) -> dict[str, object]:
                nonlocal attempted
                created = original_create(path, marker, **kwargs)
                attempted = True
                metadata.write_bytes(b"transient topology-manifest drift")
                metadata.write_bytes(original)
                os.utime(
                    metadata,
                    ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
                )
                return created

            with patch.object(
                release_module,
                "_create_new_json",
                side_effect=drift_after_owned_marker,
            ):
                with self.assertRaisesRegex(
                    ValueError, "held-authority|evidence drift|identity"
                ):
                    build_release_manifest(RELEASE_ID, [output])

            self.assertTrue(attempted)
            self.assertEqual(metadata.read_bytes(), original)
            self.assertFalse((output.parents[1] / "release-manifest.json").exists())

    def test_release_context_exit_never_removes_postcommit_competitor_marker(
        self,
    ) -> None:
        """Catches cleanup deleting a competitor swapped at the delete boundary."""

        with TemporaryDirectory() as root_text:
            output = write_release_output_fixture(
                Path(root_text), "proof-20260815T153000Z-a1b2c3d"
            )
            original_held = release_module.held_evidence_authority
            competitor = b'{"competitor":true}\n'
            marker = output.parents[1] / "release-manifest.json"
            parked = output.parents[1] / "owned-release-manifest.json"
            swapped = False
            original_delete = getattr(approval_module, "_delete_owned_handle", None)
            original_create_owned = approval_module._create_owned_file
            marker_descriptor: int | None = None

            def capture_marker_handle(path: Path, **kwargs: object) -> int:
                nonlocal marker_descriptor
                descriptor = original_create_owned(path, **kwargs)
                if path.name.startswith(".release-manifest.json."):
                    marker_descriptor = descriptor
                return descriptor

            def replace_after_owned_verification(
                descriptor: int, label: str
            ) -> None:
                nonlocal swapped
                self.assertIsNotNone(original_delete)
                if label != "release marker failed held-authority exit":
                    original_delete(descriptor, label)
                    return
                self.assertEqual(descriptor, marker_descriptor)
                marker.rename(parked)
                marker.write_bytes(competitor)
                swapped = True
                original_delete(descriptor, label)

            @contextlib.contextmanager
            def fail_after_held_exit(
                *args: object, **kwargs: object
            ) -> object:
                with original_held(*args, **kwargs) as authority:
                    yield authority
                if (output.parents[1] / "release-manifest.json").exists():
                    raise ValueError("forced held-authority context exit failure")

            with (
                patch.object(
                    approval_module,
                    "_create_owned_file",
                    side_effect=capture_marker_handle,
                ),
                patch.object(
                    approval_module,
                    "_delete_owned_handle",
                    create=True,
                    side_effect=replace_after_owned_verification,
                ),
                patch.object(
                    release_module,
                    "held_evidence_authority",
                    side_effect=fail_after_held_exit,
                ),
            ):
                with self.assertRaisesRegex(ValueError, "context exit failure"):
                    build_release_manifest(RELEASE_ID, [output])

            self.assertTrue(swapped)
            self.assertEqual(marker.read_bytes(), competitor)
            self.assertFalse(parked.exists())

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
