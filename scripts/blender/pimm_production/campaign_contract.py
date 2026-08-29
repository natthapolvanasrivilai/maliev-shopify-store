"""Fail-closed policy for the owner-approved PIMM photography campaign."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping


CAMPAIGN_SCHEMA = "maliev.pimm-render-campaign/v1"
CAMPAIGN_ID = "pimm-responsive-product-photography-v1"
_CAMPAIGN_FIELDS = {"schema", "campaign_id", "shots"}
_SHOT_FIELDS = {
    "shot_id", "machines", "purpose", "width", "height", "alpha",
    "focal_length_mm", "aperture_fstop", "product_safe_margin",
    "shadow_safe_margin", "storefront_roles", "scene_contract_path",
    "scene_path", "background_class", "animation_contract", "sensor_width_mm",
    "color_management", "hdri_path", "hdri_sha256", "hdri_strength",
    "hdri_rotation_degrees", "required_light_names",
}
_EXPECTED_LIGHTS = ["KEY_SOFTBOX", "FILL_SOFTBOX", "BASE_BOUNCE", "STRIP_LEFT", "STRIP_RIGHT"]
_EXPECTED_HDRI_SHA256 = "9A982ADE8702402A895F3297BF3CB652CB6F9C8C9CCCA961D2C7603107094A06"


@dataclass(frozen=True)
class CampaignShot:
    """Immutable storefront-facing camera and output policy for one campaign shot."""

    shot_id: str
    machines: tuple[str, ...]
    purpose: str
    width: int
    height: int
    alpha: bool
    focal_length_mm: float
    aperture_fstop: float
    product_safe_margin: float
    shadow_safe_margin: float
    storefront_roles: tuple[str, ...]


@dataclass(frozen=True)
class _ShotMetadata:
    """Non-camera immutable campaign metadata retained for semantic validation."""

    scene_contract_path: object
    scene_path: object
    background_class: object
    animation_contract: object
    sensor_width_mm: object
    color_management: object
    hdri_path: object
    hdri_sha256: object
    hdri_strength: object
    hdri_rotation_degrees: object
    required_light_names: object


@dataclass(frozen=True)
class RenderCampaign:
    """Loaded immutable campaign and its strict metadata index."""

    schema: object
    campaign_id: object
    shots: tuple[CampaignShot, ...]
    metadata_by_shot_id: Mapping[str, _ShotMetadata]

    @property
    def by_shot_id(self) -> Mapping[str, CampaignShot]:
        return {shot.shot_id: shot for shot in self.shots}


def _exact_object(payload: object, expected: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be an object")
    actual = set(payload)
    if actual != expected:
        raise ValueError(
            f"{label} has unexpected fields "
            f"(missing={sorted(expected - actual)}, extra={sorted(actual - expected)})"
        )
    return payload


def _tuple(value: object) -> tuple[object, ...]:
    return tuple(value) if isinstance(value, list) else ()


def load_campaign(path: Path) -> RenderCampaign:
    """Load one exact campaign JSON object without silently accepting extra shape."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"campaign JSON is invalid: {error}") from error
    root = _exact_object(payload, _CAMPAIGN_FIELDS, "campaign root")
    shots_payload = root["shots"]
    if not isinstance(shots_payload, list):
        raise ValueError("campaign shots must be a list")
    shots: list[CampaignShot] = []
    metadata: dict[str, _ShotMetadata] = {}
    for index, item in enumerate(shots_payload):
        shot = _exact_object(item, _SHOT_FIELDS, f"campaign shots[{index}]")
        shot_id = shot["shot_id"]
        if not isinstance(shot_id, str):
            raise ValueError(f"campaign shots[{index}] shot_id must be a string")
        if shot_id in metadata:
            raise ValueError(f"campaign shot_id is duplicated: {shot_id}")
        shots.append(
            CampaignShot(
                shot_id=shot_id,
                machines=tuple(_tuple(shot["machines"])),
                purpose=shot["purpose"],
                width=shot["width"],
                height=shot["height"],
                alpha=shot["alpha"],
                focal_length_mm=shot["focal_length_mm"],
                aperture_fstop=shot["aperture_fstop"],
                product_safe_margin=shot["product_safe_margin"],
                shadow_safe_margin=shot["shadow_safe_margin"],
                storefront_roles=tuple(_tuple(shot["storefront_roles"])),
            )
        )
        metadata[shot_id] = _ShotMetadata(
            scene_contract_path=shot["scene_contract_path"],
            scene_path=shot["scene_path"],
            background_class=shot["background_class"],
            animation_contract=shot["animation_contract"],
            sensor_width_mm=shot["sensor_width_mm"],
            color_management=shot["color_management"],
            hdri_path=shot["hdri_path"],
            hdri_sha256=shot["hdri_sha256"],
            hdri_strength=shot["hdri_strength"],
            hdri_rotation_degrees=shot["hdri_rotation_degrees"],
            required_light_names=shot["required_light_names"],
        )
    return RenderCampaign(root["schema"], root["campaign_id"], tuple(shots), metadata)


def validate_campaign(campaign: RenderCampaign) -> list[str]:
    """Return every semantic error in a loaded campaign without failing open."""

    errors: list[str] = []
    if campaign.schema != CAMPAIGN_SCHEMA:
        errors.append(f"campaign schema must equal {CAMPAIGN_SCHEMA}")
    if campaign.campaign_id != CAMPAIGN_ID:
        errors.append(f"campaign_id must equal {CAMPAIGN_ID}")
    if len(campaign.shots) != 22:
        errors.append("campaign must contain exactly 22 shots")
    if len(campaign.by_shot_id) != len(campaign.shots):
        errors.append("campaign shot_id values must be unique")

    allowed_backgrounds = {
        "hero": "transparent", "editorial": "studio", "detail": "studio",
        "comparison": "studio", "workshop": "workshop",
    }
    for shot in campaign.shots:
        metadata = campaign.metadata_by_shot_id[shot.shot_id]
        prefix = shot.shot_id
        if shot.purpose not in allowed_backgrounds:
            errors.append(f"{prefix} purpose is not governed")
        if shot.machines not in {("30G",), ("50G",), ("30G", "50G")}:
            errors.append(f"{prefix} machines must be 30G, 50G, or the exact shared pair")
        if len(shot.machines) != len(set(shot.machines)):
            errors.append(f"{prefix} machines must not contain duplicates")
        if not isinstance(shot.width, int) or isinstance(shot.width, bool) or shot.width <= 0:
            errors.append(f"{prefix} width must be a positive integer")
        if not isinstance(shot.height, int) or isinstance(shot.height, bool) or shot.height <= 0:
            errors.append(f"{prefix} height must be a positive integer")
        if not isinstance(shot.alpha, bool):
            errors.append(f"{prefix} alpha must be boolean")
        if shot.focal_length_mm not in {85.0, 135.0, 200.0}:
            errors.append(f"{prefix} focal_length_mm must be one of 85, 135, 200")
        if shot.aperture_fstop not in {8.0, 11.0, 16.0}:
            errors.append(f"{prefix} aperture_fstop must be one of 8, 11, 16")
        if not isinstance(shot.storefront_roles, tuple) or not shot.storefront_roles:
            errors.append(f"{prefix} storefront_roles must be a nonempty list")
        if metadata.scene_contract_path != f"scenes/contracts/{prefix}.json":
            errors.append(f"{prefix} scene_contract_path must match shot_id")
        if metadata.scene_path != f"scenes/stills/{prefix}.blend":
            errors.append(f"{prefix} scene_path must match shot_id")
        if metadata.background_class != allowed_backgrounds.get(shot.purpose):
            errors.append(f"{prefix} background_class must match purpose")
        if metadata.animation_contract is not None:
            errors.append(f"{prefix} animation_contract must be null")
        if metadata.sensor_width_mm != 36.0:
            errors.append(f"{prefix} sensor_width_mm must equal 36")
        if metadata.color_management != "AgX - Medium High Contrast":
            errors.append(f"{prefix} color_management must equal AgX - Medium High Contrast")
        if metadata.hdri_path != "assets/hdri/studio_kontrast_04_4k.exr":
            errors.append(f"{prefix} hdri_path must equal the pinned studio HDRI")
        if metadata.hdri_sha256 != _EXPECTED_HDRI_SHA256:
            errors.append(f"{prefix} hdri_sha256 must equal the pinned studio HDRI hash")
        if metadata.hdri_strength != 0.5 or metadata.hdri_rotation_degrees != 0.0:
            errors.append(f"{prefix} HDRI strength and rotation must equal 0.5 and 0")
        if metadata.required_light_names != _EXPECTED_LIGHTS:
            errors.append(f"{prefix} required_light_names must equal the managed light rig")
        if shot.purpose == "hero":
            if (shot.product_safe_margin, shot.shadow_safe_margin) != (0.08, 0.12):
                errors.append(f"{prefix} hero safe margins must equal product 0.08 and shadow 0.12")
            if not shot.alpha:
                errors.append(f"{prefix} hero alpha must be true")
        elif (shot.product_safe_margin, shot.shadow_safe_margin) != (0.0, 0.0):
            errors.append(f"{prefix} non-hero safe margins must equal zero")
        if shot.purpose in {"editorial", "detail"} and (shot.width, shot.height) != (1800, 2250):
            errors.append(f"{prefix} editorial and detail dimensions must equal 1800x2250")
        if shot.purpose == "comparison" and shot.machines != ("30G", "50G"):
            errors.append(f"{prefix} comparison shots must declare both 30G and 50G")
    return errors


def shot_policy(campaign: RenderCampaign, shot_id: str) -> CampaignShot:
    """Return one immutable approved shot policy or fail closed for unknown shots."""

    try:
        return campaign.by_shot_id[shot_id]
    except KeyError as error:
        raise ValueError(f"uncontracted shot: {shot_id}") from error
