"""Fail-closed contract for one PIMM linked render scene."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Iterable, Mapping

from scripts.blender.pimm_production.campaign_contract import load_campaign, shot_policy

from scripts.blender.pimm_production.published_artwork import (
    PUBLISHED_ARTWORK_COUNT_PROPERTY,
    PUBLISHED_ARTWORK_SHA256_PROPERTY,
)


_FIELDS = {
    "schema_version",
    "scene_id",
    "machine",
    "purpose",
    "master_path",
    "master_sha256",
    "master_collection",
    "material_library_path",
    "material_library_sha256",
    "camera_name",
    "complete_product",
    "animation_contract",
    "output_contract",
}
_STATIC_PRODUCT_FIELDS = {"scene_path", "static_render_setup"}
_SCENE_ID = re.compile(r"^pimm-(?:(30g|50g)|(30g-50g))--[a-z0-9-]+(?:--[a-z0-9-]+)*$")
_SLUG = re.compile(r"^[a-z0-9-]+$")
_CAMERA = re.compile(r"^CAM_[A-Z0-9_]+$")
_SHA256 = re.compile(r"^[A-Fa-f0-9]{64}$")
_OUTPUT_FIELDS = {"width", "height", "alpha"}
_STATIC_RENDER_SETUP_FIELDS = {
    "camera",
    "color_management",
    "lighting",
    "physical_shadow",
    "world",
}
_STATIC_CAMERA_FIELDS = {
    "aperture_fstop",
    "clip_end",
    "clip_start",
    "focal_length_mm",
    "sensor_width_mm",
    "view",
}
_STATIC_COLOR_FIELDS = {"exposure", "gamma", "look", "view_transform"}
_STATIC_LIGHTING_FIELDS = {"lower_bounce_name", "required_light_names", "temperature_kelvin"}
_STATIC_WORLD_FIELDS = {"hdri_path", "hdri_sha256", "rotation_degrees", "strength"}
_STATIC_PHYSICAL_SHADOW_FIELDS = {"catcher_name", "gate"}
_STATIC_LIGHT_NAMES = ["KEY_SOFTBOX", "FILL_SOFTBOX", "BASE_BOUNCE", "STRIP_LEFT", "STRIP_RIGHT"]
_STATIC_HDRI_PATH = "assets/hdri/studio_kontrast_04_4k.exr"
_STATIC_HDRI_SHA256 = "9A982ADE8702402A895F3297BF3CB652CB6F9C8C9CCCA961D2C7603107094A06"
_CAMPAIGN_PATH = (
    Path(__file__).resolve().parent
    / "contracts"
    / "campaigns"
    / "pimm-responsive-product-photography-v1.json"
)
_LEGACY_STATIC_SCENE_IDS = {
    f"pimm-{machine}--{purpose}--{view}"
    for machine in ("30g", "50g")
    for purpose, view in (
        ("hero", "front"),
        ("overview", "three-quarter"),
        ("engineering", "controls"),
        ("tooling", "front-detail"),
    )
}
PUBLISHED_STABLE_ID_COUNT_PROPERTY = "pimm_published_stable_id_count"
PUBLISHED_STABLE_ID_SHA256_PROPERTY = "pimm_published_stable_id_sha256"


@dataclass(frozen=True)
class SceneContract:
    """Exact identity, ownership, camera, and output contract for a scene."""

    schema_version: int
    scene_id: str
    machine: str | None
    machines: tuple[str, ...] | None
    purpose: str
    master_path: str
    master_sha256: str
    master_collection: str
    material_library_path: str
    material_library_sha256: str
    camera_name: str
    complete_product: bool
    animation_contract: str | None
    output_contract: dict[str, object]
    scene_path: str | None = None
    static_render_setup: dict[str, object] | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "SceneContract":
        """Construct from an exact mapping without silently dropping fields."""

        fields = set(payload)
        required_without_scope = _FIELDS - {"machine"}
        has_single_machine = "machine" in fields
        has_shared_machines = "machines" in fields
        expected = required_without_scope | ({"machine"} if has_single_machine else {"machines"})
        allowed = expected | _STATIC_PRODUCT_FIELDS
        if (has_single_machine == has_shared_machines) or fields != expected and fields != allowed:
            missing = sorted(expected - fields)
            extra = sorted(fields - allowed)
            raise ValueError(
                "scene contract must contain exactly the required fields "
                f"(missing={missing}, extra={extra})"
            )
        output = payload["output_contract"]
        if not isinstance(output, Mapping):
            raise ValueError("scene contract output_contract must be an object")
        static_render_setup = payload.get("static_render_setup")
        if static_render_setup is not None and not isinstance(static_render_setup, Mapping):
            raise ValueError("scene contract static_render_setup must be an object")
        return cls(
            schema_version=payload["schema_version"],
            scene_id=payload["scene_id"],
            machine=payload.get("machine"),
            machines=(
                tuple(payload["machines"])
                if isinstance(payload.get("machines"), list)
                else None
            ),
            purpose=payload["purpose"],
            master_path=payload["master_path"],
            master_sha256=payload["master_sha256"],
            master_collection=payload["master_collection"],
            material_library_path=payload["material_library_path"],
            material_library_sha256=payload["material_library_sha256"],
            camera_name=payload["camera_name"],
            complete_product=payload["complete_product"],
            animation_contract=payload["animation_contract"],
            output_contract=dict(output),
            scene_path=payload.get("scene_path"),
            static_render_setup=(
                dict(static_render_setup) if isinstance(static_render_setup, Mapping) else None
            ),
        )

    @classmethod
    def from_json(cls, path: Path) -> "SceneContract":
        """Load an exact UTF-8 JSON scene contract."""

        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("scene contract JSON root must be an object")
        return cls.from_mapping(payload)

    def to_mapping(self) -> dict[str, object]:
        """Return the deterministic JSON-ready field mapping."""

        return {
            key: value
            for key, value in asdict(self).items()
            if key not in _STATIC_PRODUCT_FIELDS | {"machine", "machines"} or value is not None
        }


def canonical_scene_contract_json(contract: SceneContract) -> str:
    """Return the canonical payload embedded in a contracted render scene."""

    return json.dumps(
        contract.to_mapping(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def stable_id_evidence(stable_ids: Iterable[str]) -> tuple[int, str]:
    """Return deterministic unique stable-ID count and SHA-256 evidence."""

    identifiers = sorted(set(stable_ids))
    payload = ("\n".join(identifiers) + "\n").encode("utf-8")
    return len(identifiers), hashlib.sha256(payload).hexdigest().upper()


def _canonical_relative(value: object, expected: str) -> bool:
    if not isinstance(value, str) or value != expected:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in value


def _campaign_policy(scene_id: object):
    """Return a campaign policy for its IDs while leaving retired contracts readable."""

    if not isinstance(scene_id, str):
        return None
    campaign = load_campaign(_CAMPAIGN_PATH)
    try:
        return shot_policy(campaign, scene_id)
    except ValueError:
        return None


def _legacy_camera_policy(contract: SceneContract) -> tuple[str, float, float] | None:
    """Keep prior immutable stills valid until their governed replacements are authored."""

    if contract.scene_id not in _LEGACY_STATIC_SCENE_IDS:
        return None
    if contract.purpose == "engineering":
        return ("controls", 135.0, 8.0)
    if contract.purpose == "tooling":
        return ("front-detail", 135.0, 11.0)
    if contract.purpose == "overview":
        return ("three-quarter", 85.0, 11.0)
    return ("front", 85.0, 11.0)


def _validate_campaign_scene_policy(contract: SceneContract, errors: list[str]) -> None:
    """Bind campaign-owned scene identity, machine scope, and output to the manifest."""

    policy = _campaign_policy(contract.scene_id)
    if policy is None:
        return
    if contract.machines is not None:
        actual_machines = contract.machines
    elif contract.machine is not None:
        actual_machines = (contract.machine,)
    else:
        actual_machines = ()
    if actual_machines != policy.machines:
        errors.append("campaign scene machine scope must match the governed shot policy")
    if contract.purpose != policy.purpose:
        errors.append("campaign scene purpose must match the governed shot policy")
    if contract.output_contract != {
        "width": policy.width,
        "height": policy.height,
        "alpha": policy.alpha,
    }:
        errors.append("campaign scene output_contract must match the governed shot policy")


def _validate_static_render_setup(contract: SceneContract, errors: list[str]) -> None:
    if contract.scene_path is None or contract.static_render_setup is None:
        if (
            contract.scene_id in _LEGACY_STATIC_SCENE_IDS or _campaign_policy(contract.scene_id) is not None
            and contract.scene_path is None
            and contract.static_render_setup is None
        ):
            errors.append(
                "governed static product scene contracts require scene_path and "
                "static_render_setup"
            )
        elif contract.scene_path is not None or contract.static_render_setup is not None:
            errors.append("static product scene contracts require both scene_path and static_render_setup")
        return
    expected_scene_path = f"scenes/stills/{contract.scene_id}.blend"
    if not _canonical_relative(contract.scene_path, expected_scene_path):
        errors.append(f"static product scene_path must equal {expected_scene_path}")
    setup = contract.static_render_setup
    if set(setup) != _STATIC_RENDER_SETUP_FIELDS:
        errors.append("static product static_render_setup has unexpected fields")
        return
    camera = setup["camera"]
    color = setup["color_management"]
    lighting = setup["lighting"]
    physical_shadow = setup["physical_shadow"]
    world = setup["world"]
    if not isinstance(camera, Mapping) or set(camera) != _STATIC_CAMERA_FIELDS:
        errors.append("static product camera setup has unexpected fields")
    else:
        campaign_shot = _campaign_policy(contract.scene_id)
        expected_camera = (
            (camera["view"], campaign_shot.focal_length_mm, campaign_shot.aperture_fstop)
            if campaign_shot is not None
            else _legacy_camera_policy(contract)
        )
        if expected_camera is None:
            errors.append("static product scene_id must be one of the governed campaign shots")
        elif (
            camera["view"],
            camera["focal_length_mm"],
            camera["aperture_fstop"],
        ) != expected_camera:
            errors.append("static product camera must match the governed shot configuration")
        if camera["sensor_width_mm"] != 36.0:
            errors.append("static product camera sensor width must be 36mm")
        if camera["clip_start"] != 1.0:
            errors.append("static product camera near clip must equal 1 scene unit")
        if camera["clip_end"] != 10000.0:
            errors.append("static product camera far clip must equal 10000 scene units")
        if not isinstance(camera["view"], str) or not _SLUG.fullmatch(camera["view"]):
            errors.append("static product camera view must be a lowercase slug")
    if not isinstance(color, Mapping) or set(color) != _STATIC_COLOR_FIELDS:
        errors.append("static product color management has unexpected fields")
    elif (
        color["view_transform"] != "AgX"
        or color["look"] != "AgX - Medium High Contrast"
        or color["exposure"] != 0.0
        or color["gamma"] != 1.0
    ):
        errors.append("static product color management must use the approved AgX setup")
    if not isinstance(lighting, Mapping) or set(lighting) != _STATIC_LIGHTING_FIELDS:
        errors.append("static product lighting setup has unexpected fields")
    elif (
        lighting["temperature_kelvin"] != 5500.0
        or lighting["required_light_names"] != _STATIC_LIGHT_NAMES
        or lighting["lower_bounce_name"] != "BASE_BOUNCE"
    ):
        errors.append("static product lighting must use the approved 5500K lower-bounce rig")
    expected_shadow_gate = (
        "not-applicable" if contract.purpose == "engineering" else "required"
    )
    if (
        not isinstance(physical_shadow, Mapping)
        or set(physical_shadow) != _STATIC_PHYSICAL_SHADOW_FIELDS
    ):
        errors.append("static product physical shadow policy has unexpected fields")
    elif (
        physical_shadow["catcher_name"] != "PIMM_SCENE_SHADOW_CATCHER"
        or physical_shadow["gate"] != expected_shadow_gate
    ):
        errors.append(
            "static product physical shadow policy must match the governed shot class"
        )
    if not isinstance(world, Mapping) or set(world) != _STATIC_WORLD_FIELDS:
        errors.append("static product world setup has unexpected fields")
    elif (
        world["hdri_path"] != _STATIC_HDRI_PATH
        or world["hdri_sha256"] != _STATIC_HDRI_SHA256
        or world["strength"] != 0.5
        or world["rotation_degrees"] != 0.0
    ):
        errors.append("static product world must use the approved pinned HDRI setup")


def validate_scene_contract(contract: SceneContract) -> list[str]:
    """Return semantic errors; an empty list is the render-scene schema gate."""

    errors: list[str] = []
    if contract.schema_version != 1:
        errors.append("scene contract schema_version must be 1")
    if contract.machine is not None and contract.machine not in {"30G", "50G"}:
        errors.append("scene contract machine must be 30G or 50G")
    if contract.machine is None and contract.machines != ("30G", "50G"):
        errors.append("shared scene contract machines must equal 30G and 50G")
    match = _SCENE_ID.fullmatch(contract.scene_id) if isinstance(contract.scene_id, str) else None
    if match is None:
        errors.append("scene contract scene_id must match the canonical PIMM scene pattern")
    elif contract.machine in {"30G", "50G"} and match.group(1) != contract.machine.lower():
        errors.append("scene contract scene_id machine must match machine")
    elif contract.machines == ("30G", "50G") and match.group(2) != "30g-50g":
        errors.append("shared scene contract scene_id must identify both machines")
    if not isinstance(contract.purpose, str) or _SLUG.fullmatch(contract.purpose) is None:
        errors.append("scene contract purpose must be a lowercase slug")
    elif isinstance(contract.scene_id, str) and f"--{contract.purpose}" not in contract.scene_id:
        errors.append("scene contract purpose must be represented in scene_id")

    if contract.machine in {"30G", "50G"}:
        expected_master = f"masters/PIMM-{contract.machine}-MASTER.blend"
        if not _canonical_relative(contract.master_path, expected_master):
            errors.append(f"scene contract canonical master_path must equal {expected_master}")
    elif not isinstance(contract.master_path, str):
        errors.append("scene contract master_path must be a string")
    if (
        not isinstance(contract.master_sha256, str)
        or _SHA256.fullmatch(contract.master_sha256) is None
    ):
        errors.append("scene contract master_sha256 must be 64 hexadecimal characters")
    if contract.master_collection != "PIMM_PUBLISHED":
        errors.append("scene contract master_collection must equal PIMM_PUBLISHED")
    if not _canonical_relative(
        contract.material_library_path, "masters/PIMM-MATERIAL-LIBRARY.blend"
    ):
        errors.append(
            "scene contract canonical material_library_path must equal masters/PIMM-MATERIAL-LIBRARY.blend"
        )
    if (
        not isinstance(contract.material_library_sha256, str)
        or _SHA256.fullmatch(contract.material_library_sha256) is None
    ):
        errors.append(
            "scene contract material_library_sha256 must be 64 hexadecimal characters"
        )
    if not isinstance(contract.camera_name, str) or _CAMERA.fullmatch(contract.camera_name) is None:
        errors.append("scene contract camera_name must use the CAM_ managed name")
    if contract.complete_product is not True:
        errors.append("scene contract complete_product must be true")
    if contract.animation_contract is not None and (
        not isinstance(contract.animation_contract, str)
        or not contract.animation_contract.strip()
    ):
        errors.append("scene contract animation_contract must be null or a nonempty string")

    output = contract.output_contract
    if set(output) != _OUTPUT_FIELDS:
        errors.append("scene contract output_contract must contain exactly width, height, and alpha")
    width = output.get("width")
    height = output.get("height")
    alpha = output.get("alpha")
    if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
        errors.append("scene contract output_contract width must be a positive integer")
    if not isinstance(height, int) or isinstance(height, bool) or height <= 0:
        errors.append("scene contract output_contract height must be a positive integer")
    if not isinstance(alpha, bool):
        errors.append("scene contract output_contract alpha must be boolean")
    _validate_campaign_scene_policy(contract, errors)
    _validate_static_render_setup(contract, errors)
    return errors


def load_authoritative_product_ids(
    asset_root: Path, machine: str
) -> tuple[set[str], list[str]]:
    """Load exact solid IDs from the authoritative import manifest."""

    path = asset_root / "manifests" / f"PIMM-{machine}-import-manifest.json"
    if not path.is_file():
        return set(), [f"authoritative import manifest is missing: {path}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return set(), [f"authoritative import manifest cannot be read: {path}: {error}"]
    if not isinstance(payload, Mapping) or payload.get("schema_version") != 1:
        return set(), [f"authoritative import manifest schema_version must be 1: {path}"]
    solids = payload.get("solids")
    if not isinstance(solids, list) or not solids:
        return set(), [f"authoritative import manifest solids must be a nonempty list: {path}"]
    identifiers: list[str] = []
    errors: list[str] = []
    for index, solid in enumerate(solids):
        stable_id = solid.get("stable_id") if isinstance(solid, Mapping) else None
        if not isinstance(stable_id, str) or not stable_id.strip():
            errors.append(
                f"authoritative import manifest solids[{index}] lacks stable_id: {path}"
            )
        else:
            identifiers.append(stable_id)
    if len(set(identifiers)) != len(identifiers):
        errors.append(f"authoritative import manifest contains duplicate stable IDs: {path}")
    return set(identifiers), errors
