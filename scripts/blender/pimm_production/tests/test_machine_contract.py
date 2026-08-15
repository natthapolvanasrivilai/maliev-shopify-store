"""Regression coverage for the PIMM machine/controller safety contract."""

from __future__ import annotations

from copy import deepcopy
import unittest

from scripts.blender.pimm_production.machine_contract import (
    animation_is_authorized,
    discover_controller_candidates,
    load_machine_contract,
    validate_controller_scene,
    validate_machine_contract,
)


class _Material:
    def __init__(self, name: str, material_id: str | None = None) -> None:
        self.name = name
        self._material_id = material_id

    def get(self, key: str, default: object = None) -> object:
        if key == "pimm_material_id" and self._material_id is not None:
            return self._material_id
        return default


class _MaterialSlot:
    def __init__(self, material: _Material | None) -> None:
        self.material = material


class _Collection:
    def __init__(self, name: str) -> None:
        self.name = name


class _KeyframePoint:
    def __init__(self, frame: float, value: float) -> None:
        self.co = (frame, value)


class _Fcurve:
    def __init__(self, data_path: str, array_index: int, keyframes: tuple[tuple[float, float], ...]) -> None:
        self.data_path = data_path
        self.array_index = array_index
        self.keyframe_points = tuple(_KeyframePoint(frame, value) for frame, value in keyframes)


class _Action:
    def __init__(self, fcurves: tuple[_Fcurve, ...]) -> None:
        self.fcurves = fcurves


class _AnimationData:
    def __init__(self, fcurves: tuple[_Fcurve, ...]) -> None:
        self.action = _Action(fcurves)
        self.drivers: tuple[object, ...] = ()


class _Object:
    def __init__(
        self,
        name: str,
        object_type: str,
        *,
        stable_id: str | None = None,
        cad_name: str | None = None,
        materials: tuple[str, ...] = (),
        collections: tuple[str, ...] = (),
        animated: bool = False,
        fcurves: tuple[_Fcurve, ...] = (),
        image_empty: bool = False,
    ) -> None:
        self.name = name
        self.type = object_type
        self.dimensions = (10.0, 20.0, 2.0)
        self.bound_box = tuple((float(x), float(y), float(z)) for x in (0, 1) for y in (0, 1) for z in (0, 1))
        self.users_collection = tuple(_Collection(value) for value in collections)
        self.material_slots = tuple(_MaterialSlot(_Material(value)) for value in materials)
        self.animation_data = _AnimationData(fcurves) if fcurves else (object() if animated else None)
        self.empty_display_type = "IMAGE" if image_empty else "PLAIN_AXES"
        self._properties = {
            "pimm_stable_id": stable_id,
            "pimm_cad_name": cad_name,
            "pimm_collection_path": list(collections),
        }

    def get(self, key: str, default: object = None) -> object:
        value = self._properties.get(key, default)
        return default if value is None else value


class _Data:
    def __init__(self, objects: list[_Object]) -> None:
        self.objects = objects


class _Bpy:
    def __init__(self, objects: list[_Object]) -> None:
        self.data = _Data(objects)


class MachineContractTests(unittest.TestCase):
    def _enabled_contract(self) -> dict[str, object]:
        contract = load_machine_contract("30G")
        contract["controller"]["approved_machine_local_material_ids"] = [
            "CONTROLLER_GREEN_EMISSIVE",
            "CONTROLLER_OFF",
        ]
        contract["controller"]["approved_segments"] = [
            {
                "stable_object_id": "30G-segment-active",
                "material_id": "CONTROLLER_GREEN_EMISSIVE",
                "object_type": "MESH",
                "active": True,
            },
            {
                "stable_object_id": "30G-segment-inactive",
                "material_id": "CONTROLLER_OFF",
                "object_type": "MESH",
                "active": False,
            },
        ]
        contract["animation"] = {
            "status": "enabled_owner_approved",
            "allowed_controls": [
                {
                    "stable_object_id": "30G-approved-control",
                    "human_part_name": "Approved part",
                    "control_id": "approved-control",
                    "transform_channel": "location",
                    "axis": "Z",
                    "minimum": 0.0,
                    "maximum": 10.0,
                    "neutral": 0.0,
                    "start": 0.0,
                    "operating": 5.0,
                    "final": 10.0,
                    "hose_cable_dependency": "Owner reviewed",
                    "collision_note": "Owner reviewed",
                }
            ],
        }
        return contract

    def _approved_segments(self) -> list[_Object]:
        return [
            _Object(
                "Active display segment",
                "MESH",
                stable_id="30G-segment-active",
                cad_name="Display",
                materials=("CONTROLLER_GREEN_EMISSIVE",),
            ),
            _Object(
                "Inactive display segment",
                "MESH",
                stable_id="30G-segment-inactive",
                cad_name="Display",
                materials=("CONTROLLER_OFF",),
            ),
        ]

    def test_controller_values_are_machine_specific(self) -> None:
        """Catches a copied display temperature between the two master contracts."""

        self.assertEqual(load_machine_contract("30G")["controller"]["display_values"], ["300", "300"])
        self.assertEqual(load_machine_contract("50G")["controller"]["display_values"], ["350", "350"])

    def test_motion_is_blocked_without_owner_approved_map(self) -> None:
        """Catches a contract that treats a neutral master as animation-ready."""

        payload = {
            "schema_version": 1,
            "machine": "30G",
            "controller": {
                "display_values": ["300", "300"],
                "geometry_mode": "physical-seven-segment-mesh",
                "allow_font": False,
                "allow_image_overlay": False,
                "inactive_segments_required": True,
            },
            "animation": {
                "status": "blocked_pending_owner_motion_map",
                "allowed_controls": [],
            },
        }

        self.assertEqual(validate_machine_contract(payload), [])
        self.assertFalse(animation_is_authorized(payload))

    def test_semantic_mutations_are_rejected(self) -> None:
        """Catches copied values and substitutions that remove physical display evidence."""

        fixtures = [
            ("30G", ["350", "350"], "30G controller display_values must be ['300', '300']"),
            ("50G", ["300", "300"], "50G controller display_values must be ['350', '350']"),
        ]
        for machine, values, expected in fixtures:
            with self.subTest(machine=machine, values=values):
                payload = load_machine_contract(machine)
                payload["controller"]["display_values"] = values
                self.assertIn(expected, validate_machine_contract(payload))

        payload = load_machine_contract("30G")
        payload["controller"]["geometry_mode"] = "FONT"
        self.assertIn("controller geometry_mode must be physical-seven-segment-mesh", validate_machine_contract(payload))

        payload = load_machine_contract("30G")
        payload["controller"]["allow_image_overlay"] = True
        self.assertIn("controller allow_image_overlay must be false", validate_machine_contract(payload))

        payload = load_machine_contract("30G")
        payload["controller"]["inactive_segments_required"] = False
        self.assertIn("controller inactive_segments_required must be true", validate_machine_contract(payload))

    def test_enabled_motion_requires_a_nonempty_owner_approved_map(self) -> None:
        """Catches an enabled status that can animate without a named approved control."""

        payload = load_machine_contract("30G")
        payload["animation"] = {"status": "enabled_owner_approved", "allowed_controls": []}
        errors = validate_machine_contract(payload)

        self.assertIn("enabled_owner_approved animation requires a nonempty allowed_controls map", errors)
        self.assertFalse(animation_is_authorized(payload))

    def test_enabled_motion_requires_a_complete_physical_segment_and_material_map(self) -> None:
        """Catches enabled motion that lacks physical active/inactive display evidence."""

        missing_segments = self._enabled_contract()
        del missing_segments["controller"]["approved_segments"]
        del missing_segments["controller"]["approved_machine_local_material_ids"]
        self.assertIn(
            "enabled_owner_approved animation requires a nonempty controller approved_segments map",
            validate_machine_contract(missing_segments),
        )
        self.assertFalse(animation_is_authorized(missing_segments))

        missing_inactive = self._enabled_contract()
        missing_inactive["controller"]["approved_segments"][1]["active"] = True
        self.assertIn(
            "approved controller segment map requires at least one inactive segment",
            validate_machine_contract(missing_inactive),
        )
        self.assertFalse(animation_is_authorized(missing_inactive))

        unassigned = self._enabled_contract()
        unassigned["controller"]["approved_segments"][0]["material_id"] = "UNASSIGNED"
        self.assertIn(
            "controller approved_segments[0] material_id cannot be UNASSIGNED",
            validate_machine_contract(unassigned),
        )
        self.assertFalse(animation_is_authorized(unassigned))

        non_approved = self._enabled_contract()
        non_approved["controller"]["approved_segments"][0]["material_id"] = "OTHER_MACHINE_MATERIAL"
        self.assertIn(
            "controller approved_segments[0] material_id is not in approved_machine_local_material_ids",
            validate_machine_contract(non_approved),
        )
        self.assertFalse(animation_is_authorized(non_approved))

    def test_discovery_reports_stable_identity_and_cad_context_without_mutating_objects(self) -> None:
        """Catches discovery that loses the identity needed for later owner review."""

        controller = _Object(
            "Controller segment",
            "MESH",
            stable_id="30G-controller-segment-a",
            cad_name="Display - PV (Process Value)",
            materials=("MALIEV_Controller_Green_Emissive",),
            collections=("PIMM_PUBLISHED", "Electronic Box", "Controller"),
        )

        candidates = discover_controller_candidates([controller, _Object("Frame", "MESH")])

        self.assertEqual(
            candidates,
            [
                {
                    "stable_object_id": "30G-controller-segment-a",
                    "cad_name": "Display - PV (Process Value)",
                    "object_name": "Controller segment",
                    "object_type": "MESH",
                    "material_ids": ["MALIEV_Controller_Green_Emissive"],
                    "bounds": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
                    "collection_path": ["PIMM_PUBLISHED", "Electronic Box", "Controller"],
                }
            ],
        )
        self.assertEqual(controller.name, "Controller segment")
        self.assertEqual(controller.type, "MESH")

    def test_discovery_uses_the_master_provenance_cad_name(self) -> None:
        """Catches a report that ignores the CAD-name field written into PIMM masters."""

        controller = _Object("30G-deadbeef", "MESH", stable_id="30G-deadbeef")
        controller._properties["pimm_original_cad_name"] = "Display - SV (Set Value)"

        candidates = discover_controller_candidates([controller])

        self.assertEqual(candidates[0]["stable_object_id"], "30G-deadbeef")
        self.assertEqual(candidates[0]["cad_name"], "Display - SV (Set Value)")

    def test_discovery_uses_the_master_assembly_provenance(self) -> None:
        """Catches controller parts omitted because their solid CAD name is generic."""

        controller = _Object("30G-cafebabe", "MESH", stable_id="30G-cafebabe", cad_name="Panel")
        controller._properties["pimm_assembly_path"] = '["Assembly", "Electronic Box", "REX-C100"]'

        candidates = discover_controller_candidates([controller])

        self.assertEqual(candidates[0]["stable_object_id"], "30G-cafebabe")
        self.assertEqual(candidates[0]["collection_path"], ["Assembly", "Electronic Box", "REX-C100"])

    def test_discovery_reports_stable_material_ids_not_display_names(self) -> None:
        """Catches a candidate report that cannot join an approved material-ID mapping."""

        controller = _Object(
            "Controller segment",
            "MESH",
            stable_id="30G-segment",
            cad_name="Display",
            materials=("PIMM_ControllerGreen",),
        )
        controller.material_slots = (_MaterialSlot(_Material("PIMM_ControllerGreen", "CONTROLLER_GREEN_EMISSIVE")),)

        candidates = discover_controller_candidates([controller])

        self.assertEqual(candidates[0]["material_ids"], ["CONTROLLER_GREEN_EMISSIVE"])

    def test_scene_rejects_unknown_animation_and_nonphysical_display_replacements(self) -> None:
        """Catches an animation or display replacement entering a blocked master scene."""

        contract = load_machine_contract("30G")
        scene = _Bpy(
            [
                _Object("Mold travel", "MESH", animated=True),
                _Object("Display font", "FONT", stable_id="font", cad_name="Display"),
                _Object("Display image", "EMPTY", stable_id="image", cad_name="Display", image_empty=True),
            ]
        )

        errors = validate_controller_scene(scene, contract)

        self.assertIn("animation is blocked but scene object is animated: Mold travel", errors)
        self.assertIn("controller/display candidate must be a physical MESH: Display font", errors)
        self.assertIn("controller/display candidate cannot be an image overlay: Display image", errors)

    def test_scene_allows_only_the_exact_owner_approved_animated_object(self) -> None:
        """Catches an approved motion map that admits a different object or channel."""

        contract = self._enabled_contract()
        approved = _Object(
            "Approved part",
            "MESH",
            stable_id="30G-approved-control",
            fcurves=(_Fcurve("location", 2, ((1.0, 0.0), (2.0, 5.0), (3.0, 10.0))),),
        )
        unknown = _Object("Unknown part", "MESH", stable_id="30G-unknown-control", animated=True)

        self.assertTrue(animation_is_authorized(contract))
        self.assertEqual(validate_controller_scene(_Bpy([*self._approved_segments(), approved]), contract), [])
        self.assertIn(
            "animated scene object is not owner-approved: Unknown part",
            validate_controller_scene(_Bpy([*self._approved_segments(), approved, unknown]), contract),
        )

    def test_scene_rejects_unapproved_animation_channels_axis_limits_and_poses(self) -> None:
        """Catches f-curves that depart from the exact owner-approved motion record."""

        contract = self._enabled_contract()
        fixtures = [
            (
                _Object(
                    "Approved part",
                    "MESH",
                    stable_id="30G-approved-control",
                    fcurves=(_Fcurve("location", 0, ((1.0, 0.0), (2.0, 5.0), (3.0, 10.0))),),
                ),
                "approved animation axis mismatch: Approved part",
            ),
            (
                _Object(
                    "Approved part",
                    "MESH",
                    stable_id="30G-approved-control",
                    fcurves=(
                        _Fcurve("location", 2, ((1.0, 0.0), (2.0, 5.0), (3.0, 10.0))),
                        _Fcurve("rotation_euler", 2, ((1.0, 0.0),)),
                    ),
                ),
                "approved animation has unexpected transform channel: Approved part",
            ),
            (
                _Object(
                    "Approved part",
                    "MESH",
                    stable_id="30G-approved-control",
                    fcurves=(_Fcurve("location", 2, ((1.0, 0.0), (2.0, 12.0), (3.0, 10.0))),),
                ),
                "approved animation key value is outside limits: Approved part",
            ),
            (
                _Object(
                    "Approved part",
                    "MESH",
                    stable_id="30G-approved-control",
                    fcurves=(_Fcurve("location", 2, ((1.0, 0.0), (2.0, 6.0), (3.0, 10.0))),),
                ),
                "approved animation key poses do not match start/operating/final: Approved part",
            ),
        ]
        for object_value, expected in fixtures:
            with self.subTest(expected=expected):
                self.assertIn(
                    expected,
                    validate_controller_scene(_Bpy([*self._approved_segments(), object_value]), contract),
                )

    def test_owner_mapped_segments_require_mesh_material_and_an_inactive_segment(self) -> None:
        """Catches approved display maps that cannot prove physical active and inactive segments."""

        contract = load_machine_contract("30G")
        contract["controller"]["approved_machine_local_material_ids"] = ["Controller Green"]
        contract["controller"]["approved_segments"] = [
            {"stable_object_id": "segment-a", "material_id": "Controller Green", "object_type": "MESH", "active": True},
            {"stable_object_id": "segment-b", "material_id": "Controller Green", "object_type": "MESH", "active": False},
        ]
        scene = _Bpy(
            [
                _Object("Segment A", "MESH", stable_id="segment-a", cad_name="Display", materials=("Controller Green",)),
                _Object("Segment B", "FONT", stable_id="segment-b", cad_name="Display"),
            ]
        )
        errors = validate_controller_scene(scene, contract)
        self.assertIn("approved controller segment must be a MESH: segment-b", errors)
        self.assertIn("approved controller segment material mismatch: segment-b", errors)

        no_inactive = deepcopy(contract)
        no_inactive["controller"]["approved_segments"][1]["active"] = True
        self.assertIn(
            "approved controller segment map requires at least one inactive segment",
            validate_machine_contract(no_inactive),
        )


if __name__ == "__main__":
    unittest.main()
