"""Deterministic, non-optical composition policy for the governed PIMM campaign.

The campaign contract remains the sole authority for shot identity, machine scope,
camera optics, output dimensions, and render policy.  This module owns only the
spatial decisions needed to author one scene for each contracted shot.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .campaign_contract import (
    RenderCampaign,
    camera_view,
    load_campaign,
    validate_campaign,
)


CAMPAIGN_PATH = (
    Path(__file__).resolve().parent
    / "contracts"
    / "campaigns"
    / "pimm-responsive-product-photography-v1.json"
)
COMPLETE_PRODUCT_BOUNDS = "complete-product-bounds"
STABLE_ID_GROUPS = "stable-id-groups"
STUDIO_PROFILES = frozenset(
    {"transparent", "bright", "dark", "detail", "comparison", "workshop"}
)
MANAGED_REFLECTION_CARD_NAMES = (
    "PIMM_REFLECTION_CARD_LEFT",
    "PIMM_REFLECTION_CARD_RIGHT",
    "PIMM_REFLECTION_CARD_TOP",
)


@dataclass(frozen=True)
class NormalizedRect:
    """One normalized protected region, measured from the image's top-left."""

    left: float
    top: float
    right: float
    bottom: float

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x <= self.right and self.top <= y <= self.bottom


@dataclass(frozen=True)
class SubjectPlacement:
    """Normalized subject center plus its minimum image-edge clearances."""

    center_x: float
    center_y: float
    clearance_left: float
    clearance_right: float
    clearance_top: float
    clearance_bottom: float


@dataclass(frozen=True)
class MachinePlacement:
    """Scene-owned transform for one immutable linked machine collection."""

    machine: str
    offset_x: float
    offset_y: float
    ground_z: float = 0.0
    scale: float = 1.0


@dataclass(frozen=True)
class ShotComposition:
    """Shot-specific spatial policy, deliberately excluding campaign optics."""

    shot_id: str
    camera_view: str
    target_mode: str
    target_groups: Mapping[str, tuple[str, ...]]
    subject_placement: SubjectPlacement
    protected_copy_rect: NormalizedRect | None
    minimum_working_distance_heights: float
    studio_profile: str
    camera_azimuth_degrees: float
    camera_elevation_degrees: float
    machine_placements: tuple[MachinePlacement, ...] = ()

    @property
    def target_stable_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted({identifier for values in self.target_groups.values() for identifier in values})
        )


_TARGETS = {
    "30G": {
        "controls": {
            "controller_segments": ("30G-e68df40302de070b", "30G-4062c23b788f0249"),
            "enclosure": ("30G-d49b1cfe3bdb231d", "30G-b76c8e63056742ec"),
        },
        "pneumatics": {
            "regulator": (
                "30G-17d7471e4d56f8a8",
                "30G-7e1fa62c25dc41d3",
                "30G-d697fcbb01970757",
                "30G-7a672ac61a2269f6",
                "30G-8d6b4ac61bedd0d9",
                "30G-459d43d35b7ebb65",
                "30G-4c786960f95f54f5",
                "30G-06e5f34a7bf68df0",
                "30G-e56e53bc84d7efc5",
            ),
            "gauge": ("30G-2ec9c84d99cac9e7", "30G-d3ba4a09051c2160", "30G-623a1bfb6905b6f3"),
            "valve_fittings_tubing": (
                "30G-663ad7c8ef8b894f",
                "30G-f0a9409677fbdb7b",
                "30G-e86b01298131cb24",
                "30G-0cd746d4874417b8",
            ),
            "gauge_decal": ("30G-2ec9c84d99cac9e7",),
            "airtac_artwork": ("30G-663ad7c8ef8b894f",),
        },
        "tooling": {
            "nozzle": ("30G-d15912a35de6e11f",),
            "platen": ("30G-bfa12d3b2a10cf6f",),
            "fixture_grid": ("30G-bfa12d3b2a10cf6f",),
        },
        "base-feet": {
            "base_plate": ("30G-bfa12d3b2a10cf6f",),
            "springs": (
                "30G-1822215575476862",
                "30G-58918b6cff8c3cd0",
                "30G-b683194a8f60f583",
                "30G-ecf57b9f0835c7ab",
            ),
            "posts": (
                "30G-e1e1410e3118c432",
                "30G-52f82919acc88598",
                "30G-e34481d6e76ed5d2",
                "30G-6717aa8a16a9dc04",
                "30G-1eac7e5d22177e6c",
                "30G-60bc7e096622b3a3",
                "30G-ed60f19a48f43e82",
                "30G-61df6af3f68ca2e1",
            ),
            "foot_contacts": (
                "30G-d81608e985bd200f",
                "30G-1a7f1009f15a7ee4",
                "30G-64039c77f719dbec",
                "30G-7419ee7fe262373b",
            ),
        },
    },
    "50G": {
        "controls": {
            "controller_segments": ("50G-18519915f076fefe", "50G-e354bb882fc8b7a2"),
            "enclosure": ("50G-de39a2df56bb26ce", "50G-09ae1d029ca4dc6f"),
        },
        "pneumatics": {
            "regulator": (
                "50G-8f9c7d4319d9a1ec",
                "50G-2b2a97a424a4a7dd",
                "50G-489637c262b10095",
                "50G-8ad3b6458037bc61",
                "50G-3aea9e6cc20300b1",
                "50G-ac196f0347140e27",
                "50G-e716f0c3bb1cac3d",
                "50G-350bd5334d1c1164",
                "50G-748ed96cc513ec49",
            ),
            "gauge": ("50G-b440522795fc66c6", "50G-4200746e27e10004", "50G-f96d2ac185f73212"),
            "valve_fittings_tubing": (
                "50G-a7f1dbd423430c1d",
                "50G-00e6f87753e44aff",
                "50G-d654365a3fc7ebec",
                "50G-490837dee8473eb6",
            ),
            "gauge_decal": ("50G-b440522795fc66c6",),
            "airtac_artwork": ("50G-a7f1dbd423430c1d",),
        },
        "tooling": {
            "nozzle": ("50G-ad493c932ab49712",),
            "platen": ("50G-af58918a3a92d1f4",),
            "fixture_grid": ("50G-af58918a3a92d1f4",),
        },
        "base-feet": {
            "base_plate": ("50G-af58918a3a92d1f4",),
            "springs": (
                "50G-f5914579d4851da3",
                "50G-a791a55ded7a8f30",
                "50G-de1116a543de5253",
                "50G-a8f09983a9501f32",
            ),
            "posts": (
                "50G-679df482b0286819",
                "50G-a684404439f221da",
                "50G-5a8fba2bfb997850",
                "50G-16be4a2449593463",
                "50G-5451c65920a49bb5",
                "50G-537fb705e8c18c1d",
                "50G-234447d6e47a74c4",
                "50G-c93d50080174a861",
            ),
            "foot_contacts": (
                "50G-4513ee4e5dd3ae2c",
                "50G-128eb11d742a1eb0",
                "50G-4ba184a5ab1f9699",
                "50G-52ed17bc40830918",
            ),
        },
    },
}


def _placement(center_x: float, center_y: float, clearance: float = 0.08) -> SubjectPlacement:
    return SubjectPlacement(center_x, center_y, clearance, clearance, clearance, clearance)


def _composition_for_policy(campaign: RenderCampaign, shot_id: str) -> ShotComposition:
    policy = campaign.by_shot_id[shot_id]
    view = camera_view(campaign, shot_id)
    machine = policy.machines[0] if len(policy.machines) == 1 else None
    target_mode = STABLE_ID_GROUPS if policy.purpose == "detail" else COMPLETE_PRODUCT_BOUNDS
    groups: Mapping[str, tuple[str, ...]] = {}
    protected: NormalizedRect | None = None
    placement = _placement(0.5, 0.5)
    azimuth = -18.0
    elevation = 0.0
    minimum_distance = 3.0
    profile = policy.purpose
    machine_placements: tuple[MachinePlacement, ...] = ()

    if policy.purpose == "hero":
        profile = "transparent"
        if shot_id.endswith("--desktop"):
            placement = SubjectPlacement(0.72, 0.50, 0.50, 0.08, 0.08, 0.12)
            protected = NormalizedRect(0.0, 0.05, 0.42, 0.95)
        elif shot_id.endswith("--tablet"):
            placement = _placement(0.50, 0.50, 0.10)
        else:
            placement = SubjectPlacement(0.50, 0.36, 0.10, 0.10, 0.08, 0.40)
            protected = NormalizedRect(0.0, 0.66, 1.0, 1.0)
    elif policy.purpose == "editorial":
        if "--editorial-bright--" in shot_id:
            profile = "bright"
            azimuth = -28.0
        else:
            profile = "dark"
            azimuth = 28.0
        placement = _placement(0.50, 0.50, 0.09)
    elif policy.purpose == "detail":
        if machine is None:
            raise ValueError(f"detail shot lacks one machine: {shot_id}")
        detail = shot_id.split("--")[1]
        groups = _TARGETS[machine][detail]
        profile = "detail"
        minimum_distance = 1.0
        azimuth = -12.0 if detail in {"controls", "pneumatics"} else 0.0
        placement = _placement(0.50, 0.50, 0.06)
    elif policy.purpose == "comparison":
        profile = "comparison"
        machine_placements = (
            MachinePlacement("30G", -250.0, 0.0),
            MachinePlacement("50G", 250.0, 0.0),
        )
        placement = _placement(0.50, 0.50, 0.08)
    elif policy.purpose == "workshop":
        profile = "workshop"
        placement = SubjectPlacement(0.38, 0.52, 0.08, 0.40, 0.08, 0.10)
        protected = NormalizedRect(0.62, 0.08, 0.96, 0.92)

    return ShotComposition(
        shot_id=shot_id,
        camera_view=view,
        target_mode=target_mode,
        target_groups=groups,
        subject_placement=placement,
        protected_copy_rect=protected,
        minimum_working_distance_heights=minimum_distance,
        studio_profile=profile,
        camera_azimuth_degrees=azimuth,
        camera_elevation_degrees=elevation,
        machine_placements=machine_placements,
    )


_CAMPAIGN = load_campaign(CAMPAIGN_PATH)
_CAMPAIGN_ERRORS = validate_campaign(_CAMPAIGN)
if _CAMPAIGN_ERRORS:
    raise ValueError("campaign validation failed: " + "; ".join(_CAMPAIGN_ERRORS))

SHOT_COMPOSITIONS = {
    shot.shot_id: _composition_for_policy(_CAMPAIGN, shot.shot_id)
    for shot in _CAMPAIGN.shots
}


def composition_for(shot_id: str) -> ShotComposition:
    """Return one exact composition or fail closed for an uncontracted shot."""

    try:
        return SHOT_COMPOSITIONS[shot_id]
    except KeyError as error:
        raise ValueError(f"uncontracted shot composition: {shot_id}") from error


def _normalized_rect(rect: NormalizedRect) -> bool:
    return (
        0.0 <= rect.left < rect.right <= 1.0
        and 0.0 <= rect.top < rect.bottom <= 1.0
    )


def validate_compositions(
    campaign: RenderCampaign,
    compositions: Mapping[str, ShotComposition] = SHOT_COMPOSITIONS,
) -> list[str]:
    """Return every campaign coverage and deterministic spatial-policy error."""

    errors = list(validate_campaign(campaign))
    if set(compositions) != set(campaign.by_shot_id):
        errors.append("composition shot IDs must equal the exact campaign shot IDs")
    for shot_id, composition in compositions.items():
        policy = campaign.by_shot_id.get(shot_id)
        if policy is None:
            continue
        if composition.shot_id != shot_id:
            errors.append(f"{shot_id} composition identity must match its registry key")
        if composition.camera_view != camera_view(campaign, shot_id):
            errors.append(f"{shot_id} camera view must match campaign authority")
        placement = composition.subject_placement
        values = (
            placement.center_x,
            placement.center_y,
            placement.clearance_left,
            placement.clearance_right,
            placement.clearance_top,
            placement.clearance_bottom,
        )
        if not all(isinstance(value, (int, float)) and 0.0 <= value <= 1.0 for value in values):
            errors.append(f"{shot_id} normalized subject placement is invalid")
        if composition.protected_copy_rect is not None and not _normalized_rect(
            composition.protected_copy_rect
        ):
            errors.append(f"{shot_id} protected-copy rectangle is invalid")
        if composition.minimum_working_distance_heights <= 0.0:
            errors.append(f"{shot_id} working-distance minimum must be positive")
        if policy.purpose != "detail" and composition.minimum_working_distance_heights < 3.0:
            errors.append(f"{shot_id} full-machine working distance must be at least three heights")
        if composition.studio_profile not in STUDIO_PROFILES:
            errors.append(f"{shot_id} studio profile is not governed")
        if policy.purpose == "detail":
            if composition.target_mode != STABLE_ID_GROUPS or not composition.target_groups:
                errors.append(f"{shot_id} detail target membership is absent")
            if not all(
                values and all(identifier.startswith(policy.machines[0]) for identifier in values)
                for values in composition.target_groups.values()
            ):
                errors.append(f"{shot_id} detail target stable IDs do not match machine scope")
        elif composition.target_mode != COMPLETE_PRODUCT_BOUNDS or composition.target_groups:
            errors.append(f"{shot_id} full-machine target must use complete-product bounds")
        if policy.purpose == "comparison":
            placements = composition.machine_placements
            if (
                tuple(item.machine for item in placements) != policy.machines
                or len({item.machine for item in placements}) != 2
                or len({item.ground_z for item in placements}) != 1
                or any(item.scale != 1.0 for item in placements)
            ):
                errors.append(f"{shot_id} comparison placement must preserve two machines on one floor")
        elif composition.machine_placements:
            errors.append(f"{shot_id} non-comparison shot cannot have machine transforms")
    return errors


def validate_workshop_support_assets(
    composition: ShotComposition,
    local_supports: Sequence[Mapping[str, object]],
    provenance_by_asset_id: Mapping[str, Mapping[str, object]],
) -> list[str]:
    """Validate scene-local workshop props against already-approved provenance."""

    errors: list[str] = []
    if composition.studio_profile != "workshop" and local_supports:
        return [f"{composition.shot_id} does not permit workshop support assets"]
    expected_asset_ids = {
        asset_id
        for asset_id, provenance in provenance_by_asset_id.items()
        if composition.shot_id in provenance.get("intended_shot_ids", ())
    }
    support_groups: dict[str, list[Mapping[str, object]]] = {}
    for support in local_supports:
        if not isinstance(support, Mapping):
            continue
        asset_id = support.get("asset_version_id")
        if isinstance(asset_id, str):
            support_groups.setdefault(asset_id, []).append(support)
    if set(support_groups) != expected_asset_ids:
        errors.append(
            f"{composition.shot_id} workshop supports must equal the exact expected asset set"
        )
    required = {
        "name",
        "ownership",
        "asset_version_id",
        "local_relative_path",
        "sha256",
        "member_count",
        "member_names",
    }
    for index, support in enumerate(local_supports):
        prefix = f"workshop support[{index}]"
        if set(support) != required:
            errors.append(f"{prefix} has unexpected fields")
            continue
        if support["ownership"] != "scene-support":
            errors.append(f"{prefix} ownership must equal scene-support")
        asset_id = support["asset_version_id"]
        provenance = provenance_by_asset_id.get(asset_id) if isinstance(asset_id, str) else None
        if provenance is None:
            errors.append(f"{prefix} has no provenance record")
            continue
        if composition.shot_id not in provenance.get("intended_shot_ids", ()):
            errors.append(f"{prefix} provenance does not authorize this workshop shot")
        for field in ("asset_version_id", "local_relative_path", "sha256"):
            if support[field] != provenance.get(field):
                errors.append(f"{prefix} {field} does not match provenance")
    for asset_id in sorted(expected_asset_ids):
        members = support_groups.get(asset_id, [])
        if not members:
            continue
        expected_names_values = [member.get("member_names") for member in members]
        expected_counts = [member.get("member_count") for member in members]
        first_names = expected_names_values[0]
        valid_names = (
            isinstance(first_names, list)
            and bool(first_names)
            and all(isinstance(name, str) and name for name in first_names)
            and len(first_names) == len(set(first_names))
            and all(value == first_names for value in expected_names_values)
        )
        valid_count = (
            all(isinstance(value, int) and not isinstance(value, bool) for value in expected_counts)
            and len(set(expected_counts)) == 1
            and valid_names
            and expected_counts[0] == len(first_names)
        )
        actual_names = [member.get("name") for member in members]
        if (
            not valid_names
            or not valid_count
            or len(actual_names) != len(first_names)
            or set(actual_names) != set(first_names)
        ):
            errors.append(
                f"workshop support asset {asset_id} member set does not match its authored container"
            )
    return errors


_COMPOSITION_ERRORS = validate_compositions(_CAMPAIGN)
if _COMPOSITION_ERRORS:
    raise ValueError("shot composition validation failed: " + "; ".join(_COMPOSITION_ERRORS))
