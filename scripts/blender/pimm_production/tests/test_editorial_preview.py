"""Atomic rendering coverage for the four editorial-concept previews."""

from __future__ import annotations

from copy import deepcopy
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from scripts.blender.pimm_production.editorial_concept_contract import (
    EDITORIAL_CAMPAIGN_PATH,
    load_editorial_campaign,
)
from scripts.blender.pimm_production.editorial_contact_sheet import (
    build_editorial_contact_sheet,
)
from scripts.blender.pimm_production import editorial_contact_sheet as contact_sheet_module
from scripts.blender.pimm_production import blender_editorial_preview as preview_module
from scripts.blender.pimm_production.blender_editorial_preview import (
    EditorialPreviewFailure,
    render_editorial_preview_campaign,
)
from scripts.blender.pimm_production.io_contract import sha256_file


CAMPAIGN = load_editorial_campaign(EDITORIAL_CAMPAIGN_PATH)


def _json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _arg(command: list[str], name: str) -> str:
    return command[command.index(name) + 1]


class EditorialPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.asset_root = Path(self.temporary.name).resolve()
        self.blender = self.asset_root / "tools" / "blender.exe"
        self.blender.parent.mkdir(parents=True)
        self.blender.write_bytes(b"fixture Blender 5.2")
        self.master_hashes: dict[str, str] = {}
        for machine in ("30G", "50G"):
            path = self.asset_root / "masters" / f"PIMM-{machine}-MASTER.blend"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"{machine} immutable master".encode())
            self.master_hashes[machine] = sha256_file(path)
        self.material_path = self.asset_root / "masters" / "PIMM-MATERIAL-LIBRARY.blend"
        self.material_path.write_bytes(b"immutable material library")
        self.material_hash = sha256_file(self.material_path)
        self.external_records = self._write_external_assets()
        self.contracts: dict[str, dict[str, object]] = {}
        self.paths: dict[str, dict[str, Path]] = {}
        self._write_completion_authorities()
        self.worker_calls: list[str] = []

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_external_assets(self) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        definitions = (
            (
                "university_workshop",
                "university_workshop:hdris:4k:exr:fixture",
                "university_workshop_4k.exr",
                ["pimm-50g--concept-modern-workshop"],
            ),
            (
                "tool_cart",
                "tool_cart:models:1k:blend:fixture",
                "tool_cart_1k.blend",
                ["pimm-50g--concept-modern-workshop"],
            ),
            (
                "metal_toolbox",
                "metal_toolbox:models:1k:blend:fixture",
                "metal_toolbox_1k.blend",
                [
                    "pimm-50g--concept-modern-workshop",
                    "pimm-30g--concept-process-still-life",
                ],
            ),
        )
        for asset_id, version, filename, intended in definitions:
            relative = f"assets/external/polyhaven/{asset_id}/{filename}"
            path = self.asset_root / Path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"{asset_id} governed bytes".encode())
            records.append(
                {
                    "source_url": f"https://polyhaven.com/a/{asset_id}",
                    "asset_version_id": version,
                    "license": "CC0-1.0",
                    "local_relative_path": relative,
                    "sha256": sha256_file(path),
                    "intended_shot_ids": intended,
                    "machine_master_modified": False,
                }
            )
        _json(
            self.asset_root / "manifests" / "external-assets-v1.json",
            {"schema": "maliev.pimm-external-assets/v1", "assets": records},
        )
        return records

    def _contract_external_assets(self, shot_id: str) -> list[dict[str, object]]:
        required = {
            "pimm-30g--concept-architectural-daylight": (),
            "pimm-50g--concept-dark-engineering": (),
            "pimm-50g--concept-modern-workshop": (
                "university_workshop",
                "tool_cart",
            ),
            "pimm-30g--concept-process-still-life": ("metal_toolbox",),
        }[shot_id]
        result = []
        for record in self.external_records:
            asset_id = str(record["source_url"]).rsplit("/", 1)[-1]
            if asset_id not in required:
                continue
            asset = dict(record)
            asset["asset_id"] = asset_id
            result.append(asset)
        return result

    def _write_completion_authorities(self) -> None:
        for index, shot in enumerate(CAMPAIGN.shots, start=1):
            scene_relative = f"scenes/editorial-concepts-v1/{shot.shot_id}.blend"
            contract_relative = f"scenes/contracts/editorial-concepts-v1/{shot.shot_id}.json"
            marker_relative = (
                f"scenes/contracts/editorial-concepts-v1/{shot.shot_id}.complete.json"
            )
            scene_path = self.asset_root / Path(scene_relative)
            contract_path = self.asset_root / Path(contract_relative)
            marker_path = self.asset_root / Path(marker_relative)
            scene_path.parent.mkdir(parents=True, exist_ok=True)
            scene_path.write_bytes(f"fresh scene {shot.shot_id}".encode())
            contract: dict[str, object] = {
                "schema": "maliev.pimm-editorial-scene/v1",
                "campaign_id": CAMPAIGN.campaign_id,
                "scene_id": shot.shot_id,
                "machine": shot.machine,
                "concept": shot.concept,
                "scene_path": scene_relative,
                "master": {
                    "path": f"masters/PIMM-{shot.machine}-MASTER.blend",
                    "sha256": self.master_hashes[shot.machine],
                },
                "material_library": {
                    "path": "masters/PIMM-MATERIAL-LIBRARY.blend",
                    "sha256": self.material_hash,
                },
                "contact": {
                    "gate": "four-feet-common-plane",
                    "tolerance": 0.0002,
                },
                "camera": {
                    "name": "CAM_EDITORIAL",
                    "focal_length_mm": shot.focal_length_mm,
                    "aperture_fstop": shot.aperture_fstop,
                },
                "render": {
                    "engine": "CYCLES",
                    "width": shot.width,
                    "height": shot.height,
                    "resolution_percentage": 100,
                    "preview_samples": 32,
                    "denoise": True,
                    "view_transform": "AgX",
                    "look": "AgX - Medium High Contrast",
                    "alpha": False,
                },
                "set": {
                    "geometry_signature": f"{index:064X}",
                    "light_signature": f"{index + 10:064X}",
                    "scene_geometry_signature": f"{index + 20:064X}",
                    "scene_light_signature": f"{index + 30:064X}",
                    "shadow_intent": f"distinct-shadow-{index}",
                },
                "external_assets": self._contract_external_assets(shot.shot_id),
                "input_policy": "link-only-immutable",
                "preview_only": True,
                "final_authorized": False,
                "publication": {
                    "schema": "maliev.pimm-editorial-publication/v1",
                    "authority": "marker-last-sha256-pair",
                    "transaction_id": f"{index:032x}",
                    "completion_marker_path": marker_relative,
                },
            }
            _json(contract_path, contract)
            marker = {
                "schema": "maliev.pimm-editorial-publication/v1",
                "status": "complete",
                "scene_id": shot.shot_id,
                "transaction_id": f"{index:032x}",
                "scene_sha256": sha256_file(scene_path),
                "contract_sha256": sha256_file(contract_path),
                "paths": {
                    "scene_published": str(scene_path),
                    "contract_published": str(contract_path),
                    "completion_marker": str(marker_path),
                },
            }
            _json(marker_path, marker)
            self.contracts[shot.shot_id] = contract
            self.paths[shot.shot_id] = {
                "scene": scene_path,
                "contract": contract_path,
                "marker": marker_path,
            }

    def _worker_result(self, command: list[str], call_index: int) -> dict[str, object]:
        shot_id = _arg(command, "--shot-id")
        output_path = Path(_arg(command, "--output"))
        contract = json.loads(Path(_arg(command, "--contract")).read_text(encoding="utf-8"))
        marker_path = Path(_arg(command, "--completion-marker"))
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        render = contract["render"]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        colors = ((222, 214, 202), (24, 29, 38), (168, 174, 168), (80, 69, 58))
        image = Image.new("RGB", (render["width"], render["height"]), colors[call_index % 4])
        draw = ImageDraw.Draw(image)
        inset_x = max(32, render["width"] // 5)
        inset_y = max(32, render["height"] // 5)
        draw.rounded_rectangle(
            (inset_x, inset_y, render["width"] - inset_x, render["height"] - inset_y),
            radius=24,
            fill=(110 + call_index * 8, 120, 132),
            outline=(235, 238, 241),
            width=8,
        )
        image.save(output_path, format="PNG")
        external = []
        for record in contract["external_assets"]:
            external.append(
                {
                    **record,
                    "actual_sha256": sha256_file(
                        self.asset_root / Path(record["local_relative_path"])
                    ),
                    "status": "pass",
                }
            )
        contact = {
            "stable_ids": [f"foot-{number}" for number in range(4)],
            "pad_bottoms": [0.0, 0.00001, -0.00001, 0.0],
            "contact_z": 0.0,
            "spread": 0.00002,
            "tolerance": 0.0002,
            "outlier_stable_ids": [],
            "feet": [
                {"stable_id": f"foot-{number}", "bottom_z": 0.0, "delta_to_plane": 0.0}
                for number in range(4)
            ],
        }
        return {
            "schema": "maliev.pimm-editorial-preview-shot/v1",
            "status": "technical-pass",
            "shot_id": shot_id,
            "process_id": 1000 + call_index,
            "cache_reuse": False,
            "output_path": str(output_path),
            "output_sha256": sha256_file(output_path),
            "output_width": render["width"],
            "output_height": render["height"],
            "render": {
                "engine": "CYCLES",
                "samples": 32,
                "denoise": True,
                "width": render["width"],
                "height": render["height"],
                "resolution_percentage": 100,
                "view_transform": "AgX",
                "look": "AgX - Medium High Contrast",
                "exposure": 0.0,
                "gamma": 1.0,
                "film_transparent": False,
                "file_format": "PNG",
                "color_mode": "RGB",
                "color_depth": "8",
                "use_persistent_data": False,
                "bounce_limits": {
                    "max_bounces": 12,
                    "diffuse_bounces": 4,
                    "glossy_bounces": 4,
                    "transmission_bounces": 12,
                    "volume_bounces": 0,
                    "transparent_max_bounces": 8,
                },
                "blender_version": "5.2.0",
                "started_at": "2026-08-30T08:00:00Z",
                "finished_at": "2026-08-30T08:00:01Z",
                "seconds": 1.0,
                "dimension_evidence": {
                    "dimension_authority": "written-png-ihdr",
                    "png_dimensions": [render["width"], render["height"]],
                    "render_result_size": [0, 0],
                },
            },
            "authority": {
                "checked_at": "2026-08-30T07:59:59Z",
                "scene_path": str(self.paths[shot_id]["scene"]),
                "scene_sha256": marker["scene_sha256"],
                "contract_path": str(self.paths[shot_id]["contract"]),
                "contract_sha256": marker["contract_sha256"],
                "completion_marker_path": str(marker_path),
                "completion_marker_sha256": sha256_file(marker_path),
                "transaction_id": marker["transaction_id"],
                "blender_scene_validation": "pass",
                "master": {
                    "path": str(self.asset_root / Path(contract["master"]["path"])),
                    "sha256": contract["master"]["sha256"],
                    "status": "pass",
                },
                "material_library": {
                    "path": str(
                        self.asset_root / Path(contract["material_library"]["path"])
                    ),
                    "sha256": contract["material_library"]["sha256"],
                    "status": "pass",
                },
                "external_assets": external,
            },
            "contact": {"status": "pass", "measurements": contact},
            "framing": {
                "status": "pass",
                "complete_machine_framed": True,
                "support_rectangle_framed": True,
                "machine_frame_width_ratio": 0.3,
                "machine_frame_height_ratio": 0.8,
                "machine_frame_area_ratio": 0.24,
                "safe_margin_minimum": 0.05,
            },
            "clipping": {
                "status": "pending-visual-review",
                "machine": "pass",
                "designed_shadow": "pending-visual-review",
                "props": "pass",
                "support_intersections": [],
                "hidden_foot_stable_ids": [],
            },
            "set": {
                "geometry_signature": contract["set"]["scene_geometry_signature"],
                "light_signature": contract["set"]["scene_light_signature"],
                "shadow_intent": contract["set"]["shadow_intent"],
            },
            "asset_provenance_status": "pass",
            "master_fingerprint_status": "pass",
            "fingerprints_unchanged": True,
        }

    def _successful_worker(self, command: list[str], **_: object) -> CompletedProcess[str]:
        call_index = len(self.worker_calls)
        shot_id = _arg(command, "--shot-id")
        self.worker_calls.append(shot_id)
        payload = self._worker_result(command, call_index)
        return CompletedProcess(
            command,
            0,
            stdout=preview_module.RESULT_MARKER + json.dumps(payload) + "\n",
            stderr="",
        )

    def _render(self):
        blender_authority = {
            "status": "pass",
            "path": str(self.blender),
            "sha256": sha256_file(self.blender),
            "version": "5.2.0",
            "lock_path": str(self.asset_root / "manifests" / "free-tools-lock.json"),
            "lock_sha256": "A" * 64,
        }
        with patch.object(
            preview_module,
            "_validate_blender_authority",
            return_value=blender_authority,
        ), patch.object(preview_module.subprocess, "run", side_effect=self._successful_worker):
            return render_editorial_preview_campaign(self.asset_root, self.blender)

    def _visual_decision(
        self,
        result: object,
        *,
        decision: str = "accept",
        failures: dict[tuple[str, str], str] | None = None,
    ) -> dict[str, object]:
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        report = json.loads(result.report_path.read_text(encoding="utf-8"))
        failures = failures or {}
        shots = []
        for record in manifest["shots"]:
            shot_id = record["shot_id"]
            review = {
                field: failures.get((shot_id, field), "pass")
                for field in (
                    "machine",
                    "props",
                    "designed_shadow",
                    "grounding",
                    "exposure",
                    "detail",
                    "pixel_review",
                )
            }
            shots.append(
                {
                    "shot_id": shot_id,
                    "output_sha256": record["output_sha256"],
                    "dimensions": [record["output_width"], record["output_height"]],
                    **review,
                    "notes": "fixture 100 percent actual-pixel review",
                }
            )
        return {
            "schema": "maliev.pimm-editorial-visual-disposition/v1",
            "generation_id": result.generation_id,
            "decision": decision,
            "reviewer": "fixture-reviewer",
            "reviewed_at": "2026-08-30T09:00:00Z",
            "campaign_manifest_sha256": sha256_file(result.manifest_path),
            "campaign_report_sha256": sha256_file(result.report_path),
            "contact_sheet": {
                "path": result.contact_sheet_path.name,
                "sha256": report["contact_sheet_sha256"],
                "dimensions": report["contact_sheet_dimensions"],
                "pixel_review": "pass",
            },
            "shots": shots,
        }

    def test_technical_success_stays_pending_review_and_is_not_a_consumer_generation(self) -> None:
        """Catches technical success becoming observable at the canonical final path."""

        result = self._render()

        self.assertEqual(result.status, "pending-review")
        self.assertEqual(self.worker_calls, [shot.shot_id for shot in CAMPAIGN.shots])
        self.assertEqual(result.shot_count, 4)
        self.assertTrue(result.output_root.is_dir())
        self.assertEqual(result.output_root.parent.name, "pending-review")
        canonical = result.output_root.parent.parent / result.generation_id
        self.assertFalse(canonical.exists())
        self.assertFalse(any(result.output_root.parent.parent.glob(".*.pending")))
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        report = json.loads(result.report_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "pending-review")
        self.assertEqual(report["status"], "pending-review")
        self.assertEqual(manifest["manual_visual_inspection"]["status"], "pending")
        self.assertEqual(manifest["cache_reuse"], False)
        self.assertEqual(manifest["fresh_blender_processes"], 4)
        self.assertEqual(manifest["contact_passes"], 4)
        self.assertEqual(manifest["framing_passes"], 4)
        self.assertEqual(len(manifest["shots"]), 4)
        self.assertEqual(len({shot["process_id"] for shot in manifest["shots"]}), 4)
        for shot, record in zip(CAMPAIGN.shots, manifest["shots"], strict=True):
            self.assertEqual(record["status"], "pending-review")
            self.assertEqual(record["clipping"]["designed_shadow"], "pending-visual-review")
            self.assertEqual(record["shot_id"], shot.shot_id)
            self.assertEqual(record["render"]["samples"], 32)
            self.assertIs(record["render"]["denoise"], True)
            self.assertEqual(
                (record["output_width"], record["output_height"]),
                (shot.width, shot.height),
            )
            self.assertEqual(record["render_source"], "fresh-blender")
            self.assertEqual(record["authority"]["scene_sha256"], sha256_file(self.paths[shot.shot_id]["scene"]))
            self.assertEqual(record["authority"]["master"]["sha256"], self.master_hashes[shot.machine])
            self.assertEqual(record["authority"]["material_library"]["sha256"], self.material_hash)
            self.assertTrue((result.output_root / record["output_relative_path"]).is_file())

    def test_accept_with_complete_all_pass_visual_decision_promotes_atomically(self) -> None:
        """Catches canonical publication without a complete hash-bound all-pass review."""

        pending = self._render()
        decision = self._visual_decision(pending)

        accepted = preview_module.accept_editorial_preview_generation(
            self.asset_root,
            pending.generation_id,
            decision,
        )

        self.assertEqual(accepted.status, "accepted")
        self.assertEqual(accepted.output_root.parent.name, "editorial-concepts-v1")
        self.assertFalse(pending.output_root.exists())
        self.assertTrue((accepted.output_root / "visual-disposition.json").is_file())
        manifest = json.loads(accepted.manifest_path.read_text(encoding="utf-8"))
        report = json.loads(accepted.report_path.read_text(encoding="utf-8"))
        disposition = json.loads(
            (accepted.output_root / "visual-disposition.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "accepted")
        self.assertEqual(report["status"], "accepted")
        self.assertEqual(disposition["decision"], "accept")
        self.assertTrue(all(record["status"] == "accepted" for record in manifest["shots"]))
        self.assertTrue(
            all(record["clipping"]["designed_shadow"] == "pass" for record in manifest["shots"])
        )

    def test_reject_with_complete_visual_decision_moves_atomically_to_rejected(self) -> None:
        """Catches rejected pixels remaining pending or appearing at the canonical path."""

        pending = self._render()
        failed_shot = CAMPAIGN.shots[1].shot_id
        decision = self._visual_decision(
            pending,
            decision="reject",
            failures={(failed_shot, "exposure"): "fail"},
        )

        rejected = preview_module.reject_editorial_preview_generation(
            self.asset_root,
            pending.generation_id,
            decision,
        )

        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(rejected.output_root.parent.name, "rejected")
        self.assertFalse(pending.output_root.exists())
        self.assertFalse((rejected.output_root.parent.parent / rejected.generation_id).exists())
        disposition_path = rejected.output_root / "visual-disposition.json"
        disposition_hash = sha256_file(disposition_path)
        with self.assertRaisesRegex(ValueError, "pending-review"):
            preview_module.reject_editorial_preview_generation(
                self.asset_root,
                pending.generation_id,
                decision,
            )
        self.assertEqual(sha256_file(disposition_path), disposition_hash)

    def test_accept_rejects_incomplete_or_hash_tampered_visual_decision(self) -> None:
        """Catches a partial review or a decision bound to different pixels being accepted."""

        for mutation in ("missing-grounding", "wrong-image-hash", "failed-accept"):
            with self.subTest(mutation=mutation):
                pending = self._render()
                decision = self._visual_decision(pending)
                if mutation == "missing-grounding":
                    del decision["shots"][0]["grounding"]
                elif mutation == "wrong-image-hash":
                    decision["shots"][0]["output_sha256"] = "0" * 64
                else:
                    decision["shots"][0]["detail"] = "fail"

                with self.assertRaises(ValueError):
                    preview_module.accept_editorial_preview_generation(
                        self.asset_root,
                        pending.generation_id,
                        decision,
                    )

                self.assertTrue(pending.output_root.is_dir())
                self.assertFalse(
                    (pending.output_root.parent.parent / pending.generation_id).exists()
                )

    def test_png_mutation_after_sheet_before_disposition_blocks_acceptance(self) -> None:
        """Catches a reviewer decision being applied to bytes changed after sheet creation."""

        pending = self._render()
        decision = self._visual_decision(pending)
        first = pending.output_root / CAMPAIGN.shots[0].shot_id
        first = first.with_suffix(".png")
        Image.new("RGB", (1280, 720), (255, 0, 255)).save(first, format="PNG")

        with self.assertRaisesRegex(ValueError, "PNG bytes"):
            preview_module.accept_editorial_preview_generation(
                self.asset_root,
                pending.generation_id,
                decision,
            )

        self.assertTrue(pending.output_root.is_dir())
        self.assertFalse(
            (pending.output_root.parent.parent / pending.generation_id).exists()
        )
        self.assertFalse((pending.output_root / "visual-disposition.json").exists())

    def test_png_or_disposition_mutation_before_final_move_blocks_publication(self) -> None:
        """Catches a post-decision race between verification and canonical promotion."""

        for mutation in ("png", "disposition"):
            with self.subTest(mutation=mutation):
                pending = self._render()
                decision = self._visual_decision(pending)
                real_validate = preview_module._validate_generation_artifacts
                validation_calls = 0

                def mutate_before_final_validation(
                    generation_root: Path,
                    *,
                    expected_status: str,
                    require_disposition: bool,
                ) -> object:
                    nonlocal validation_calls
                    validation_calls += 1
                    if validation_calls == 2:
                        if mutation == "png":
                            image_path = generation_root / f"{CAMPAIGN.shots[0].shot_id}.png"
                            Image.new("RGB", (1280, 720), (0, 255, 255)).save(
                                image_path,
                                format="PNG",
                            )
                        else:
                            (generation_root / "visual-disposition.json").write_text(
                                "{}\n",
                                encoding="utf-8",
                            )
                    return real_validate(
                        generation_root,
                        expected_status=expected_status,
                        require_disposition=require_disposition,
                    )

                with patch.object(
                    preview_module,
                    "_validate_generation_artifacts",
                    side_effect=mutate_before_final_validation,
                ):
                    with self.assertRaises(ValueError):
                        preview_module.accept_editorial_preview_generation(
                            self.asset_root,
                            pending.generation_id,
                            decision,
                        )

                self.assertEqual(validation_calls, 2)
                self.assertTrue(pending.output_root.is_dir())
                self.assertFalse(
                    (pending.output_root.parent.parent / pending.generation_id).exists()
                )

    def test_cli_accept_and_reject_require_visual_decision_files(self) -> None:
        """Catches disposition APIs existing without controller-usable CLI operations."""

        for operation in ("accept", "reject"):
            with self.subTest(operation=operation):
                pending = self._render()
                failures = (
                    {}
                    if operation == "accept"
                    else {(CAMPAIGN.shots[0].shot_id, "detail"): "fail"}
                )
                decision = self._visual_decision(
                    pending,
                    decision=operation,
                    failures=failures,
                )
                decision_path = self.asset_root / f"{operation}-decision.json"
                _json(decision_path, decision)
                stdout = StringIO()

                with redirect_stdout(stdout):
                    exit_code = preview_module.main(
                        [
                            f"--{operation}-generation",
                            "--asset-root",
                            str(self.asset_root),
                            "--generation-id",
                            pending.generation_id,
                            "--visual-decision",
                            str(decision_path),
                        ]
                    )

                self.assertEqual(exit_code, 0)
                emitted = stdout.getvalue().strip()
                self.assertTrue(emitted.startswith(preview_module.RESULT_MARKER))
                payload = json.loads(emitted.removeprefix(preview_module.RESULT_MARKER))
                self.assertEqual(
                    payload["status"],
                    "accepted" if operation == "accept" else "rejected",
                )

    def test_any_worker_failure_preserves_staging_under_rejected_and_leaves_no_final(self) -> None:
        """Catches deletion of failed evidence or a partially published final generation."""

        def fail_third(command: list[str], **kwargs: object) -> CompletedProcess[str]:
            if len(self.worker_calls) == 2:
                shot_id = _arg(command, "--shot-id")
                self.worker_calls.append(shot_id)
                return CompletedProcess(command, 1, stdout="", stderr="fixture render failure")
            return self._successful_worker(command, **kwargs)

        with patch.object(
            preview_module,
            "_validate_blender_authority",
            return_value={
                "status": "pass",
                "path": str(self.blender),
                "sha256": sha256_file(self.blender),
                "version": "5.2.0",
                "lock_path": "fixture",
                "lock_sha256": "A" * 64,
            },
        ), patch.object(preview_module.subprocess, "run", side_effect=fail_third):
            with self.assertRaises(EditorialPreviewFailure) as caught:
                render_editorial_preview_campaign(self.asset_root, self.blender)

        error = caught.exception
        self.assertIsNotNone(error.rejected_root)
        assert error.rejected_root is not None
        self.assertTrue(error.rejected_root.is_dir())
        self.assertTrue((error.rejected_root / "campaign-failure.json").is_file())
        generation_parent = self.asset_root / "renders" / "proofs" / "editorial-concepts-v1"
        self.assertFalse((generation_parent / error.generation_id).exists())
        self.assertFalse(any(generation_parent.glob(".*.pending")))
        self.assertEqual(len(list(error.rejected_root.glob("*.png"))), 2)

    def test_blender_worker_timeout_is_bounded_and_preserved_fail_closed(self) -> None:
        """Catches an unbounded render hang or a timeout with no durable failure evidence."""

        def time_out(command: list[str], **kwargs: object) -> CompletedProcess[str]:
            self.assertEqual(kwargs["timeout"], 900)
            raise TimeoutExpired(
                command,
                kwargs["timeout"],
                output="fixture partial Blender stdout",
                stderr="fixture Blender timeout stderr",
            )

        with patch.object(
            preview_module,
            "_validate_blender_authority",
            return_value={
                "status": "pass",
                "path": str(self.blender),
                "sha256": sha256_file(self.blender),
                "version": "5.2.0",
                "lock_path": "fixture",
                "lock_sha256": "A" * 64,
            },
        ), patch.object(preview_module.subprocess, "run", side_effect=time_out):
            with self.assertRaises(EditorialPreviewFailure) as caught:
                render_editorial_preview_campaign(self.asset_root, self.blender)

        rejected = caught.exception.rejected_root
        self.assertIsNotNone(rejected)
        assert rejected is not None
        failure = json.loads((rejected / "campaign-failure.json").read_text(encoding="utf-8"))
        self.assertIs(failure["timed_out"], True)
        self.assertEqual(failure["timeout_seconds"], 900)
        self.assertIn("partial Blender stdout", failure["stdout_tail"])
        self.assertIn("timeout stderr", failure["stderr_tail"])
        self.assertFalse(
            (
                rejected.parent.parent
                / preview_module.PENDING_REVIEW_DIRECTORY
                / caught.exception.generation_id
            ).exists()
        )
        self.assertFalse((rejected.parent.parent / caught.exception.generation_id).exists())

    def test_failure_preservation_records_secondary_errors_without_masking_primary(self) -> None:
        """Catches swallowed evidence-write errors or replacement of the render failure."""

        real_atomic_write = preview_module.atomic_write_json
        failure_writes = 0

        def fail_first_failure_write(path: Path, payload: object) -> None:
            nonlocal failure_writes
            if Path(path).name == "campaign-failure.json":
                failure_writes += 1
                if failure_writes == 1:
                    raise OSError("fixture failure evidence write blocked")
            real_atomic_write(path, payload)

        def fail_worker(command: list[str], **_: object) -> CompletedProcess[str]:
            return CompletedProcess(
                command,
                1,
                stdout="fixture primary stdout",
                stderr="fixture primary render failure",
            )

        with patch.object(
            preview_module,
            "_validate_blender_authority",
            return_value={
                "status": "pass",
                "path": str(self.blender),
                "sha256": sha256_file(self.blender),
                "version": "5.2.0",
                "lock_path": "fixture",
                "lock_sha256": "A" * 64,
            },
        ), patch.object(preview_module.subprocess, "run", side_effect=fail_worker), patch.object(
            preview_module,
            "atomic_write_json",
            side_effect=fail_first_failure_write,
        ):
            with self.assertRaises(EditorialPreviewFailure) as caught:
                render_editorial_preview_campaign(self.asset_root, self.blender)

        self.assertIn("fixture primary render failure", str(caught.exception))
        self.assertTrue(caught.exception.preservation_errors)
        rejected = caught.exception.rejected_root
        self.assertIsNotNone(rejected)
        assert rejected is not None
        failure = json.loads((rejected / "campaign-failure.json").read_text(encoding="utf-8"))
        self.assertEqual(failure["secondary_errors"], list(caught.exception.preservation_errors))
        self.assertIn("fixture failure evidence write blocked", failure["secondary_errors"][0])

    def test_authority_hash_drift_before_a_shot_blocks_that_blender_process(self) -> None:
        """Catches a renderer that trusts Task 4 hashes captured only at campaign start."""

        second_marker = self.paths[CAMPAIGN.shots[1].shot_id]["marker"]

        def drift_after_first(command: list[str], **kwargs: object) -> CompletedProcess[str]:
            completed = self._successful_worker(command, **kwargs)
            if len(self.worker_calls) == 1:
                second_marker.write_text("{}\n", encoding="utf-8")
            return completed

        with patch.object(
            preview_module,
            "_validate_blender_authority",
            return_value={
                "status": "pass",
                "path": str(self.blender),
                "sha256": sha256_file(self.blender),
                "version": "5.2.0",
                "lock_path": "fixture",
                "lock_sha256": "A" * 64,
            },
        ), patch.object(preview_module.subprocess, "run", side_effect=drift_after_first):
            with self.assertRaises(EditorialPreviewFailure):
                render_editorial_preview_campaign(self.asset_root, self.blender)

        self.assertEqual(self.worker_calls, [CAMPAIGN.shots[0].shot_id])

    def test_completion_authority_enforces_exact_concept_required_external_assets(self) -> None:
        """Catches treating the provenance intended-shot list as the required scene asset set."""

        expected = {
            "pimm-30g--concept-architectural-daylight": [],
            "pimm-50g--concept-dark-engineering": [],
            "pimm-50g--concept-modern-workshop": ["university_workshop", "tool_cart"],
            "pimm-30g--concept-process-still-life": ["metal_toolbox"],
        }
        for shot in CAMPAIGN.shots:
            authority = preview_module._load_completion_authority(self.asset_root, shot)
            self.assertEqual(
                [record["asset_id"] for record in authority.external_assets],
                expected[shot.shot_id],
            )

        modern = CAMPAIGN.by_shot_id["pimm-50g--concept-modern-workshop"]
        contract_path = self.paths[modern.shot_id]["contract"]
        marker_path = self.paths[modern.shot_id]["marker"]
        original_contract = contract_path.read_bytes()
        original_marker = marker_path.read_bytes()
        mutations = {
            "missing tool cart": [self.contracts[modern.shot_id]["external_assets"][0]],
            "authorized but not required metal toolbox": [
                *self.contracts[modern.shot_id]["external_assets"],
                {
                    **next(
                        record
                        for record in self.external_records
                        if str(record["source_url"]).endswith("/metal_toolbox")
                    ),
                    "asset_id": "metal_toolbox",
                },
            ],
        }
        for label, external_assets in mutations.items():
            with self.subTest(label=label):
                contract = deepcopy(self.contracts[modern.shot_id])
                contract["external_assets"] = external_assets
                _json(contract_path, contract)
                marker = json.loads(original_marker)
                marker["contract_sha256"] = sha256_file(contract_path)
                _json(marker_path, marker)
                try:
                    with self.assertRaisesRegex(ValueError, "required external asset IDs"):
                        preview_module._load_completion_authority(self.asset_root, modern)
                finally:
                    contract_path.write_bytes(original_contract)
                    marker_path.write_bytes(original_marker)

    def test_final_authority_recheck_blocks_publication_after_last_render_drift(self) -> None:
        """Catches a renderer that publishes after a protected scene changes mid-campaign."""

        first_scene = self.paths[CAMPAIGN.shots[0].shot_id]["scene"]

        def drift_after_last(command: list[str], **kwargs: object) -> CompletedProcess[str]:
            completed = self._successful_worker(command, **kwargs)
            if len(self.worker_calls) == 4:
                first_scene.write_bytes(b"scene changed after its render")
            return completed

        with patch.object(
            preview_module,
            "_validate_blender_authority",
            return_value={
                "status": "pass",
                "path": str(self.blender),
                "sha256": sha256_file(self.blender),
                "version": "5.2.0",
                "lock_path": "fixture",
                "lock_sha256": "A" * 64,
            },
        ), patch.object(preview_module.subprocess, "run", side_effect=drift_after_last):
            with self.assertRaises(EditorialPreviewFailure) as caught:
                render_editorial_preview_campaign(self.asset_root, self.blender)

        generation_parent = self.asset_root / "renders" / "proofs" / "editorial-concepts-v1"
        self.assertFalse((generation_parent / caught.exception.generation_id).exists())

    def test_worker_result_rejects_missing_hash_settings_contact_framing_or_clipping_evidence(self) -> None:
        """Catches an automated pass marker that omits one of the acceptance authorities."""

        shot = CAMPAIGN.shots[0]
        authority = preview_module._load_completion_authority(self.asset_root, shot)
        output = self.asset_root / "fixture-output.png"
        command = [
            str(self.blender), "--shot-id", shot.shot_id,
            "--output", str(output),
            "--contract", str(self.paths[shot.shot_id]["contract"]),
            "--completion-marker", str(self.paths[shot.shot_id]["marker"]),
        ]
        baseline = self._worker_result(command, 0)
        mutations = {
            "scene hash": lambda item: item["authority"].__setitem__("scene_sha256", "0" * 64),
            "samples": lambda item: item["render"].__setitem__("samples", 16),
            "contact": lambda item: item["contact"].__setitem__("status", "fail"),
            "framing": lambda item: item["framing"].__setitem__("complete_machine_framed", False),
            "shadow clipping": lambda item: item["clipping"].__setitem__("designed_shadow", "pass"),
            "provenance": lambda item: item.__setitem__("asset_provenance_status", "fail"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                payload = deepcopy(baseline)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, label):
                    preview_module._validate_worker_result(shot, authority, payload, output)

    def test_worker_requires_designed_shadow_to_remain_pending_visual_review(self) -> None:
        """Catches fresh Blender hardcoding an aesthetic shadow pass before pixel review."""

        shot = CAMPAIGN.shots[0]
        authority = preview_module._load_completion_authority(self.asset_root, shot)
        output = self.asset_root / "pending-shadow-output.png"
        command = [
            str(self.blender), "--shot-id", shot.shot_id,
            "--output", str(output),
            "--contract", str(self.paths[shot.shot_id]["contract"]),
            "--completion-marker", str(self.paths[shot.shot_id]["marker"]),
        ]
        pending = self._worker_result(command, 0)

        preview_module._validate_worker_result(shot, authority, pending, output)
        pending["clipping"]["designed_shadow"] = "pass"

        with self.assertRaisesRegex(ValueError, "shadow clipping"):
            preview_module._validate_worker_result(shot, authority, pending, output)

    def test_nonfinite_numeric_evidence_is_rejected_at_json_and_worker_boundaries(self) -> None:
        """Catches NaN/Inf bypassing comparisons in contact, framing, or render evidence."""

        nonfinite_json = self.asset_root / "nonfinite.json"
        nonfinite_json.write_text('{"value": NaN}\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            preview_module._load_json_bytes(nonfinite_json, "fixture evidence")
        for token in ("Infinity", "1e400"):
            with self.subTest(contact_sheet_token=token):
                nonfinite_sheet_manifest = (
                    self.asset_root / f"nonfinite-sheet-manifest-{token}.json"
                )
                nonfinite_sheet_manifest.write_text(
                    '{"schema":"maliev.pimm-editorial-preview-campaign/v1",'
                    f'"shots":[],"value":{token}}}\n',
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "nonfinite"):
                    contact_sheet_module._load_manifest(nonfinite_sheet_manifest)

        shot = CAMPAIGN.shots[0]
        authority = preview_module._load_completion_authority(self.asset_root, shot)
        output = self.asset_root / "nonfinite-worker-output.png"
        command = [
            str(self.blender), "--shot-id", shot.shot_id,
            "--output", str(output),
            "--contract", str(self.paths[shot.shot_id]["contract"]),
            "--completion-marker", str(self.paths[shot.shot_id]["marker"]),
        ]
        baseline = self._worker_result(command, 0)
        mutations = {
            "render seconds NaN": lambda item: item["render"].__setitem__("seconds", float("nan")),
            "contact spread NaN": lambda item: item["contact"]["measurements"].__setitem__(
                "spread", float("nan")
            ),
            "foot delta NaN": lambda item: item["contact"]["measurements"]["feet"][0].__setitem__(
                "delta_to_plane", float("nan")
            ),
            "framing margin NaN": lambda item: item["framing"].__setitem__(
                "safe_margin_minimum", float("nan")
            ),
            "framing ratio Inf": lambda item: item["framing"].__setitem__(
                "machine_frame_area_ratio", float("inf")
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                payload = deepcopy(baseline)
                mutate(payload)
                with self.assertRaisesRegex(ValueError, "nonfinite"):
                    preview_module._validate_worker_result(shot, authority, payload, output)

    def test_wrong_output_dimensions_are_rejected_before_manifest_publication(self) -> None:
        """Catches a worker that reports the contract size while writing another raster size."""

        def wrong_dimensions(command: list[str], **kwargs: object) -> CompletedProcess[str]:
            completed = self._successful_worker(command, **kwargs)
            output = Path(_arg(command, "--output"))
            Image.new("RGB", (64, 64), (20, 30, 40)).save(output, format="PNG")
            payload = json.loads(completed.stdout.removeprefix(preview_module.RESULT_MARKER))
            payload["output_sha256"] = sha256_file(output)
            return CompletedProcess(
                command,
                0,
                stdout=preview_module.RESULT_MARKER + json.dumps(payload) + "\n",
                stderr="",
            )

        with patch.object(
            preview_module,
            "_validate_blender_authority",
            return_value={
                "status": "pass",
                "path": str(self.blender),
                "sha256": sha256_file(self.blender),
                "version": "5.2.0",
                "lock_path": "fixture",
                "lock_sha256": "A" * 64,
            },
        ), patch.object(preview_module.subprocess, "run", side_effect=wrong_dimensions):
            with self.assertRaises(EditorialPreviewFailure):
                render_editorial_preview_campaign(self.asset_root, self.blender)

    def test_written_png_is_dimension_authority_when_headless_render_result_is_zero(self) -> None:
        """Catches rejection of valid Blender 5.2 background renders whose image API says 0x0."""

        output = self.asset_root / "headless-render-result.png"
        Image.new("RGB", (1280, 720), (32, 48, 64)).save(output, format="PNG")

        evidence = preview_module._validate_rendered_png_dimensions(
            output,
            1280,
            720,
            render_result_size=(0, 0),
        )

        self.assertEqual(evidence["png_dimensions"], [1280, 720])
        self.assertEqual(evidence["render_result_size"], [0, 0])
        self.assertEqual(evidence["dimension_authority"], "written-png-ihdr")

    def test_contact_sheet_is_two_by_two_equal_cells_with_all_required_labels(self) -> None:
        """Catches missing decision fields or a layout that is not four equal review cells."""

        result = self._render()
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        report = json.loads(result.report_path.read_text(encoding="utf-8"))
        cells = report["contact_sheet_cells"]

        self.assertEqual(report["contact_sheet_dimensions"], [2560, 1800])
        self.assertEqual(len(cells), 4)
        self.assertEqual(
            {(cell["width"], cell["height"]) for cell in cells},
            {(1280, 900)},
        )
        required = {
            "shot_id", "machine", "lens", "f_stop", "render_engine",
            "set_signature", "scene_hash_prefix", "contact_state",
            "master_fingerprint_state", "asset_provenance_state",
        }
        for cell, shot in zip(cells, manifest["shots"], strict=True):
            self.assertEqual(set(cell["labels"]), required)
            self.assertEqual(cell["labels"]["shot_id"], shot["shot_id"])
            self.assertEqual(
                cell["source_dimensions"],
                [shot["output_width"], shot["output_height"]],
            )
        with Image.open(result.contact_sheet_path) as image:
            self.assertEqual(image.size, (2560, 1800))

    def test_contact_sheet_refuses_an_existing_output_instead_of_reusing_it(self) -> None:
        """Catches contact-sheet cache reuse or overwrite inside an immutable generation."""

        result = self._render()

        with self.assertRaisesRegex(ValueError, "already exists"):
            build_editorial_contact_sheet(result.manifest_path, result.contact_sheet_path)

    def test_contact_sheet_rejects_alternate_write_inside_any_authoritative_generation(self) -> None:
        """Catches adding an unbound sheet to pending, accepted, or rejected evidence."""

        pending = self._render()
        accepted_pending = self._render()
        accepted = preview_module.accept_editorial_preview_generation(
            self.asset_root,
            accepted_pending.generation_id,
            self._visual_decision(accepted_pending),
        )
        rejected_pending = self._render()
        rejected = preview_module.reject_editorial_preview_generation(
            self.asset_root,
            rejected_pending.generation_id,
            self._visual_decision(
                rejected_pending,
                decision="reject",
                failures={(CAMPAIGN.shots[0].shot_id, "detail"): "fail"},
            ),
        )

        for result in (pending, accepted, rejected):
            with self.subTest(status=result.status):
                alternate = result.output_root / "alternate-review-sheet.png"
                with self.assertRaisesRegex(ValueError, "canonical|generation authority"):
                    build_editorial_contact_sheet(result.manifest_path, alternate)
                self.assertFalse(alternate.exists())


if __name__ == "__main__":
    unittest.main()
