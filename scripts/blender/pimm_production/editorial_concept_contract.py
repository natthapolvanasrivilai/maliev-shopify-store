"""Fail-closed contract for the separate preview-only editorial concepts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping


EDITORIAL_CAMPAIGN_PATH = (
    Path(__file__).resolve().parent
    / "contracts"
    / "campaigns"
    / "pimm-editorial-concepts-v1.json"
)
EDITORIAL_CAMPAIGN_SCHEMA = "maliev.pimm-editorial-concept-campaign/v1"
EDITORIAL_CAMPAIGN_ID = "pimm-editorial-concepts-v1"
_CAMPAIGN_FIELDS = {"schema", "campaign_id", "shots"}
_SHOT_FIELDS = {
    "shot_id", "machine", "concept", "width", "height", "focal_length_mm",
    "aperture_fstop", "render_engine", "color_management", "preview_samples",
    "denoise", "contact_gate", "final_authorized",
}
_EXPECTED = {
    "pimm-30g--concept-architectural-daylight": ("30G", "architectural-daylight", 1280, 720, 85.0),
    "pimm-50g--concept-dark-engineering": ("50G", "dark-engineering", 1280, 720, 135.0),
    "pimm-50g--concept-modern-workshop": ("50G", "modern-workshop", 1280, 720, 85.0),
    "pimm-30g--concept-process-still-life": ("30G", "process-still-life", 900, 1125, 180.0),
}


@dataclass(frozen=True)
class EditorialConceptShot:
    """Immutable preview policy for one editorial concept shot."""

    shot_id: str
    machine: str
    concept: str
    width: int
    height: int
    focal_length_mm: float
    aperture_fstop: float
    render_engine: str
    color_management: str
    preview_samples: int
    denoise: bool
    contact_gate: str
    final_authorized: bool


@dataclass(frozen=True)
class EditorialConceptCampaign:
    """Loaded immutable editorial campaign."""

    schema: object
    campaign_id: object
    shots: tuple[EditorialConceptShot, ...]

    @property
    def by_shot_id(self) -> Mapping[str, EditorialConceptShot]:
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


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_editorial_campaign(path: Path) -> EditorialConceptCampaign:
    """Load an exact editorial campaign JSON object."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as error:
        raise ValueError(f"editorial campaign JSON is invalid: {error}") from error
    root = _exact_object(payload, _CAMPAIGN_FIELDS, "editorial campaign root")
    shots_payload = root["shots"]
    if not isinstance(shots_payload, list):
        raise ValueError("editorial campaign shots must be a list")
    shots: list[EditorialConceptShot] = []
    seen: set[str] = set()
    for index, item in enumerate(shots_payload):
        shot = _exact_object(item, _SHOT_FIELDS, f"editorial campaign shots[{index}]")
        shot_id = shot["shot_id"]
        if not isinstance(shot_id, str):
            raise ValueError(f"editorial campaign shots[{index}] shot_id must be a string")
        if shot_id in seen:
            raise ValueError(f"editorial campaign shot_id is duplicated: {shot_id}")
        seen.add(shot_id)
        shots.append(EditorialConceptShot(**shot))
    return EditorialConceptCampaign(root["schema"], root["campaign_id"], tuple(shots))


def validate_editorial_campaign(campaign: EditorialConceptCampaign) -> list[str]:
    """Return all semantic policy violations in an editorial campaign."""

    errors: list[str] = []
    if campaign.schema != EDITORIAL_CAMPAIGN_SCHEMA:
        errors.append(f"campaign schema must equal {EDITORIAL_CAMPAIGN_SCHEMA}")
    if campaign.campaign_id != EDITORIAL_CAMPAIGN_ID:
        errors.append(f"campaign_id must equal {EDITORIAL_CAMPAIGN_ID}")
    if len(campaign.shots) != 4:
        errors.append("campaign must contain exactly 4 shots")
    if len(campaign.by_shot_id) != len(campaign.shots):
        errors.append("campaign shot_id values must be unique")
    if set(campaign.by_shot_id) != set(_EXPECTED):
        errors.append("campaign shot IDs must equal the exact approved four-shot editorial library")
    for shot in campaign.shots:
        prefix = shot.shot_id
        expected = _EXPECTED.get(prefix)
        if expected is None:
            errors.append(f"{prefix} is not an approved editorial concept shot")
        else:
            machine, concept, width, height, focal = expected
            if shot.machine != machine:
                errors.append(f"{prefix} machine must equal {machine}")
            if shot.concept != concept:
                errors.append(f"{prefix} concept must equal {concept}")
            if (shot.width, shot.height) != (width, height):
                errors.append(f"{prefix} dimensions must equal {width}x{height}")
            if shot.focal_length_mm != focal:
                errors.append(f"{prefix} focal_length_mm must equal {focal}")
        if shot.aperture_fstop != 11.0:
            errors.append(f"{prefix} aperture_fstop must equal 11.0")
        if shot.render_engine != "CYCLES":
            errors.append(f"{prefix} render_engine must equal CYCLES")
        if shot.color_management != "AgX - Medium High Contrast":
            errors.append(f"{prefix} color_management must equal AgX - Medium High Contrast")
        if shot.preview_samples != 32:
            errors.append(f"{prefix} preview_samples must equal 32")
        if shot.denoise is not True:
            errors.append(f"{prefix} denoise must equal true")
        if shot.contact_gate != "four-feet-common-plane":
            errors.append(f"{prefix} contact_gate must equal four-feet-common-plane")
        if shot.final_authorized is not False:
            errors.append(f"{prefix} final_authorized must equal false")
    return errors
