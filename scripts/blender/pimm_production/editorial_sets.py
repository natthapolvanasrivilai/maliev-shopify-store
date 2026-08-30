"""Scene-local procedural sets and materially distinct lights for editorial previews.

This module deliberately accepts ``bpy`` as an argument.  Importing it in ordinary
Python therefore does not require Blender, while the same records drive real scene
construction inside Blender.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from .editorial_concept_contract import EDITORIAL_CAMPAIGN_PATH, EditorialConceptShot, load_editorial_campaign
from .external_asset_manifest import validate_external_assets
from .paths import ASSET_ROOT, require_within


_CAMPAIGN = load_editorial_campaign(EDITORIAL_CAMPAIGN_PATH)
_APPROVED_SHOTS = _CAMPAIGN.by_shot_id
_PRODUCT_PROPERTIES = (
    "pimm_stable_id",
    "pimm_artwork_id",
    "pimm_machine",
    "pimm_asset_role",
    "pimm_product_material_override",
)
_EXTERNAL_BY_CONCEPT = {
    "architectural-daylight": (),
    "dark-engineering": (),
    "modern-workshop": ("university_workshop", "tool_cart"),
    "process-still-life": ("metal_toolbox",),
}


@dataclass(frozen=True)
class EditorialSetGeometry:
    """One scene-owned procedural support at millimetre product-photography scale."""

    name: str
    role: str
    primitive: str
    center_mm: tuple[float, float, float]
    dimensions_mm: tuple[float, float, float]
    rotation_euler: tuple[float, float, float]
    base_color: tuple[float, float, float, float]
    roughness: float
    metallic: float = 0.0
    transmission: float = 0.0

    @property
    def maximum_dimension_mm(self) -> float:
        return max(self.dimensions_mm)


@dataclass(frozen=True)
class EditorialLight:
    """One immutable light role in an editorial concept rig."""

    role: str
    light_type: str
    energy: float
    color: tuple[float, float, float]
    location_mm: tuple[float, float, float]
    rotation_euler: tuple[float, float, float]
    size_mm: float = 0.0
    size_y_mm: float = 0.0
    angle_radians: float = 0.0


@dataclass(frozen=True)
class EditorialExternalAsset:
    """Exact manifest provenance for one scene-local external support instance."""

    asset_id: str
    source_url: str
    asset_version_id: str
    license: str
    local_relative_path: str
    sha256: str
    intended_shot_ids: tuple[str, ...]
    machine_master_modified: bool
    path: Path


@dataclass(frozen=True)
class EditorialSetEvidence:
    """Immutable evidence returned after one editorial set is constructed."""

    shot_id: str
    concept: str
    geometry: tuple[EditorialSetGeometry, ...]
    lights: tuple[EditorialLight, ...]
    shadow_intent: str
    geometry_signature: str
    external_assets: tuple[EditorialExternalAsset, ...]


@dataclass(frozen=True)
class _EditorialSetSpec:
    concept: str
    geometry: tuple[EditorialSetGeometry, ...]
    lights: tuple[EditorialLight, ...]
    shadow_intent: str


def _geometry(
    name: str,
    role: str,
    primitive: str,
    center: tuple[float, float, float],
    dimensions: tuple[float, float, float],
    color: tuple[float, float, float, float],
    roughness: float,
    *,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    metallic: float = 0.0,
    transmission: float = 0.0,
) -> EditorialSetGeometry:
    return EditorialSetGeometry(
        f"PIMM_SCENE_SUPPORT_{name}", role, primitive, center, dimensions,
        rotation, color, roughness, metallic, transmission,
    )


def _light(
    role: str,
    light_type: str,
    energy: float,
    color: tuple[float, float, float],
    location: tuple[float, float, float],
    rotation: tuple[float, float, float],
    *,
    size: float = 0.0,
    size_y: float = 0.0,
    angle: float = 0.0,
) -> EditorialLight:
    return EditorialLight(role, light_type, energy, color, location, rotation, size, size_y, angle)


_WARM_GREY = (0.46, 0.43, 0.39, 1.0)
_GRAPHITE = (0.028, 0.032, 0.038, 1.0)
_BLACK = (0.006, 0.007, 0.009, 1.0)
_STEEL = (0.31, 0.34, 0.37, 1.0)
_PAPER = (0.80, 0.79, 0.74, 1.0)


_SETS = {
    "architectural-daylight": _EditorialSetSpec(
        "architectural-daylight",
        (
            _geometry("ARCH_FLOOR", "warm-grey-floor", "box", (0, 0, -40), (7000, 6000, 80), _WARM_GREY, 0.82),
            _geometry("ARCH_WALL", "warm-grey-wall", "box", (0, 2650, 2000), (7000, 120, 4000), (0.50, 0.47, 0.43, 1), 0.88),
            _geometry("ARCH_GOBO_VERTICAL", "window-gobo", "box", (-3150, -1350, 2300), (90, 120, 3100), _BLACK, 1.0),
            _geometry("ARCH_GOBO_HORIZONTAL", "window-gobo", "box", (-3150, -1350, 2300), (1800, 120, 90), _BLACK, 1.0),
            _geometry("ARCH_ACCENT_SLAB", "accent-slab", "box", (1450, 1900, 1450), (850, 180, 2900), (0.30, 0.28, 0.25, 1), 0.72),
        ),
        (
            _light("SUN_Gobo", "SUN", 4.0, (1.0, 0.82, 0.64), (-3600, -3000, 4800), (math.radians(28), 0, math.radians(-38)), angle=math.radians(1.3)),
            _light("FILL_WALL", "AREA", 950.0, (1.0, 0.91, 0.80), (3000, 500, 2200), (math.radians(76), 0, math.radians(115)), size=2600, size_y=1800),
            _light("EDGE_STRIP", "AREA", 1200.0, (1.0, 0.94, 0.85), (-2100, 1300, 2300), (math.radians(90), 0, math.radians(-65)), size=1700, size_y=180),
        ),
        "crisp-window-grid-clear-of-product-evidence",
    ),
    "dark-engineering": _EditorialSetSpec(
        "dark-engineering",
        (
            _geometry("DARK_FLOOR", "graphite-floor", "box", (0, 0, -45), (7200, 6200, 90), _GRAPHITE, 0.46),
            _geometry("DARK_WALL", "graphite-wall", "box", (0, 2800, 1900), (7200, 140, 3800), (0.016, 0.019, 0.025, 1), 0.58),
            _geometry("DARK_FLAG_LEFT", "black-flag-left", "box", (-2550, -250, 1850), (45, 1600, 3000), _BLACK, 0.98, rotation=(0, 0, math.radians(-11))),
            _geometry("DARK_FLAG_RIGHT", "black-flag-right", "box", (2500, 300, 1700), (45, 1400, 2800), _BLACK, 0.98, rotation=(0, 0, math.radians(14))),
        ),
        (
            _light("KEY_SLASH", "AREA", 2100.0, (1.0, 0.86, 0.70), (-2900, -2500, 4100), (math.radians(42), 0, math.radians(-38)), size=1100, size_y=180),
            _light("RIM_LEFT", "AREA", 1500.0, (0.84, 0.91, 1.0), (-2300, 1500, 2300), (math.radians(90), 0, math.radians(-72)), size=2100, size_y=130),
            _light("RIM_RIGHT", "AREA", 1350.0, (0.91, 0.95, 1.0), (2400, 1700, 2100), (math.radians(90), 0, math.radians(70)), size=1900, size_y=120),
            _light("BASE_LIFT", "AREA", 420.0, (0.76, 0.82, 0.90), (0, -1100, 450), (math.radians(18), 0, math.radians(180)), size=1900, size_y=700),
            _light("BLUE_ACCENT", "AREA", 560.0, (0.035, 0.20, 0.82), (1350, 900, 1650), (math.radians(85), 0, math.radians(120)), size=900, size_y=90),
        ),
        "elongated-diagonal-readable-underside",
    ),
    "modern-workshop": _EditorialSetSpec(
        "modern-workshop",
        (
            _geometry("WORKBENCH_TOP", "steel-workbench", "box", (-2250, 1150, 900), (1800, 760, 90), _STEEL, 0.31, metallic=0.78),
            _geometry("WORKBENCH_LEG_A", "steel-workbench", "box", (-2950, 1150, 440), (90, 650, 880), _STEEL, 0.38, metallic=0.68),
            _geometry("WORKBENCH_LEG_B", "steel-workbench", "box", (-1550, 1150, 440), (90, 650, 880), _STEEL, 0.38, metallic=0.68),
            _geometry("PELLET_JAR_CLEAR_A", "pellet-jar", "cylinder", (-2650, 1040, 1190), (230, 230, 480), (0.82, 0.91, 0.94, 0.34), 0.12, transmission=0.82),
            _geometry("PELLET_JAR_CLEAR_B", "pellet-jar", "cylinder", (-2320, 1040, 1150), (210, 210, 400), (0.80, 0.88, 0.91, 0.34), 0.12, transmission=0.82),
            _geometry("WORKSHOP_MOLD_A", "mold-block", "box", (-1980, 1050, 1035), (380, 300, 180), (0.27, 0.30, 0.32, 1), 0.24, metallic=0.88),
            _geometry("WORKSHOP_MOLD_B", "mold-block", "box", (-1580, 1050, 1035), (320, 280, 180), (0.22, 0.24, 0.26, 1), 0.22, metallic=0.90),
            _geometry("WORKSHOP_DRAWING", "technical-drawing", "box", (-2250, 650, 970), (720, 470, 8), _PAPER, 0.72, rotation=(math.radians(4), 0, math.radians(-8))),
        ),
        (
            _light("WORKSHOP_HDRI", "WORLD", 0.42, (1.0, 1.0, 1.0), (0, 0, 0), (0, 0, 0)),
            _light("WINDOW_KEY", "AREA", 1700.0, (0.82, 0.91, 1.0), (-3200, -1700, 3600), (math.radians(48), 0, math.radians(-48)), size=2400, size_y=1400),
            _light("MACHINE_FILL", "AREA", 780.0, (0.93, 0.96, 1.0), (2200, -800, 1500), (math.radians(72), 0, math.radians(118)), size=1800, size_y=1000),
            _light("PRACTICAL_WARM", "POINT", 520.0, (1.0, 0.54, 0.24), (-1700, 1650, 2600), (0, 0, 0), size=180),
        ),
        "soft-window-cast-with-contact-depth",
    ),
    "process-still-life": _EditorialSetSpec(
        "process-still-life",
        (
            _geometry("PROCESS_MOLD_HALF_A", "mold-half", "box", (-1250, -650, 220), (620, 430, 260), (0.24, 0.26, 0.28, 1), 0.20, rotation=(0, 0, math.radians(-14)), metallic=0.92),
            _geometry("PROCESS_MOLD_HALF_B", "mold-half", "box", (-570, -780, 185), (560, 420, 220), (0.19, 0.21, 0.23, 1), 0.18, rotation=(0, 0, math.radians(10)), metallic=0.94),
            _geometry("PROCESS_PEEK_PELLETS", "peek-pellets", "cylinder", (720, -980, 90), (500, 500, 180), (0.72, 0.55, 0.30, 1), 0.44),
            _geometry("PROCESS_BLACK_PELLETS", "black-pellets", "cylinder", (1270, -760, 80), (420, 420, 160), (0.012, 0.014, 0.018, 1), 0.50),
            _geometry("PROCESS_NEUTRAL_PELLETS", "neutral-pellets", "cylinder", (1120, -1320, 70), (380, 380, 140), (0.62, 0.60, 0.55, 1), 0.48),
            _geometry("PROCESS_SAMPLE_A", "molded-sample", "cylinder", (320, -1180, 110), (260, 260, 220), (0.025, 0.030, 0.038, 1), 0.32, rotation=(math.radians(90), 0, 0)),
            _geometry("PROCESS_SAMPLE_B", "molded-sample", "box", (50, -980, 105), (360, 190, 210), (0.08, 0.18, 0.34, 1), 0.28, rotation=(0, 0, math.radians(-18))),
            _geometry("PROCESS_CALIPER_BAR", "inspection-caliper", "box", (-250, -1420, 42), (950, 55, 32), (0.48, 0.50, 0.52, 1), 0.18, rotation=(0, 0, math.radians(12)), metallic=0.92),
            _geometry("PROCESS_CALIPER_JAW_A", "inspection-caliper", "box", (-650, -1320, 105), (45, 300, 130), (0.48, 0.50, 0.52, 1), 0.18, rotation=(0, 0, math.radians(12)), metallic=0.92),
            _geometry("PROCESS_CALIPER_JAW_B", "inspection-caliper", "box", (120, -1505, 105), (45, 300, 130), (0.48, 0.50, 0.52, 1), 0.18, rotation=(0, 0, math.radians(12)), metallic=0.92),
            _geometry("PROCESS_DRAWING", "technical-drawing", "box", (-1250, 450, 18), (1050, 780, 10), _PAPER, 0.76, rotation=(0, 0, math.radians(-7))),
            _geometry("PROCESS_FOREGROUND_LOW", "foreground-block", "box", (-1650, -1650, 160), (720, 600, 320), (0.12, 0.13, 0.15, 1), 0.58),
            _geometry("PROCESS_FOREGROUND_HIGH", "foreground-block", "box", (1580, -1650, 310), (620, 580, 620), (0.28, 0.27, 0.24, 1), 0.62),
            _geometry("PROCESS_FOREGROUND_STEP", "foreground-block", "box", (1850, -900, 135), (500, 420, 270), (0.42, 0.39, 0.34, 1), 0.66),
        ),
        (
            _light("KEY_TOP_SIDE", "AREA", 1900.0, (1.0, 0.86, 0.69), (-2200, -1700, 3900), (math.radians(32), 0, math.radians(-35)), size=1500, size_y=900),
            _light("EDGE_CARD", "AREA", 1050.0, (0.82, 0.90, 1.0), (2100, 400, 2200), (math.radians(88), 0, math.radians(72)), size=1700, size_y=160),
            _light("FOREGROUND_KICK", "AREA", 720.0, (1.0, 0.66, 0.39), (-900, -2500, 700), (math.radians(68), 0, math.radians(-12)), size=950, size_y=260),
            _light("BASE_LIFT", "AREA", 500.0, (0.78, 0.84, 0.92), (600, -900, 500), (math.radians(28), 0, math.radians(160)), size=1500, size_y=650),
        ),
        "layered-foreground-edge-defined",
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _asset_id(record: Mapping[str, object]) -> str:
    source = str(record["source_url"])
    return source.rstrip("/").rsplit("/", 1)[-1]


def _external_records(shot: EditorialConceptShot) -> tuple[EditorialExternalAsset, ...]:
    required = _EXTERNAL_BY_CONCEPT[shot.concept]
    if not required:
        return ()
    manifest_path = require_within(
        ASSET_ROOT / "manifests" / "external-assets-v1.json",
        ASSET_ROOT / "manifests",
    )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"editorial external asset manifest cannot be read: {manifest_path}: {error}") from error
    errors = validate_external_assets(payload, set(_CAMPAIGN.by_shot_id))
    if errors:
        raise ValueError("editorial external asset manifest is invalid: " + "; ".join(errors))
    selected: dict[str, EditorialExternalAsset] = {}
    for raw in payload["assets"]:
        asset_id = _asset_id(raw)
        if asset_id not in required or shot.shot_id not in raw["intended_shot_ids"]:
            continue
        if asset_id in selected:
            raise ValueError(f"editorial external asset is duplicated: {asset_id}")
        relative = str(raw["local_relative_path"])
        path = require_within(ASSET_ROOT / Path(relative), ASSET_ROOT / "assets")
        if not path.is_file():
            raise FileNotFoundError(f"editorial external asset is missing: {path}")
        expected_hash = str(raw["sha256"]).upper()
        actual_hash = _sha256(path)
        if actual_hash != expected_hash:
            raise ValueError(
                f"editorial external asset SHA-256 mismatch: expected {expected_hash}, "
                f"found {actual_hash}: {path}"
            )
        selected[asset_id] = EditorialExternalAsset(
            asset_id=asset_id,
            source_url=str(raw["source_url"]),
            asset_version_id=str(raw["asset_version_id"]),
            license=str(raw["license"]),
            local_relative_path=relative,
            sha256=expected_hash,
            intended_shot_ids=tuple(str(value) for value in raw["intended_shot_ids"]),
            machine_master_modified=bool(raw["machine_master_modified"]),
            path=path,
        )
    missing = [asset_id for asset_id in required if asset_id not in selected]
    if missing:
        raise ValueError(f"editorial external assets are missing for {shot.shot_id}: {', '.join(missing)}")
    return tuple(selected[asset_id] for asset_id in required)


def _box_mesh(spec: EditorialSetGeometry) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    half_x, half_y, half_z = (value / 2.0 for value in spec.dimensions_mm)
    vertices = [
        (x, y, z)
        for x in (-half_x, half_x)
        for y in (-half_y, half_y)
        for z in (-half_z, half_z)
    ]
    faces = [
        (0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
        (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3),
    ]
    return vertices, faces


def _cylinder_mesh(spec: EditorialSetGeometry) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    segments = 24
    radius_x = spec.dimensions_mm[0] / 2.0
    radius_y = spec.dimensions_mm[1] / 2.0
    half_z = spec.dimensions_mm[2] / 2.0
    vertices = [
        (radius_x * math.cos(2 * math.pi * index / segments), radius_y * math.sin(2 * math.pi * index / segments), z)
        for z in (-half_z, half_z)
        for index in range(segments)
    ]
    faces: list[tuple[int, ...]] = [
        tuple(range(segments - 1, -1, -1)),
        tuple(range(segments, segments * 2)),
    ]
    faces.extend(
        (index, (index + 1) % segments, segments + (index + 1) % segments, segments + index)
        for index in range(segments)
    )
    return vertices, faces


def _set_principled_input(material: Any, name: str, value: object) -> None:
    principled = material.node_tree.nodes.get("Principled BSDF")
    if principled is not None and name in principled.inputs:
        principled.inputs[name].default_value = value


def _install_geometry(bpy: Any, spec: EditorialSetGeometry) -> Any:
    mesh = bpy.data.meshes.new(f"{spec.name}_MESH")
    vertices, faces = _cylinder_mesh(spec) if spec.primitive == "cylinder" else _box_mesh(spec)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    material = bpy.data.materials.new(f"{spec.name}_MATERIAL")
    material.use_nodes = True
    material.diffuse_color = spec.base_color
    _set_principled_input(material, "Base Color", spec.base_color)
    _set_principled_input(material, "Roughness", spec.roughness)
    _set_principled_input(material, "Metallic", spec.metallic)
    _set_principled_input(material, "Transmission Weight", spec.transmission)
    _set_principled_input(material, "Alpha", spec.base_color[3])
    if spec.transmission > 0.0 or spec.base_color[3] < 1.0:
        if hasattr(material, "surface_render_method"):
            material.surface_render_method = "DITHERED"
        else:
            material.blend_method = "BLEND"
    for datablock in (mesh, material):
        datablock["pimm_scene_support_ownership"] = "scene-support"
        datablock["pimm_scene_support_role"] = spec.role
    mesh.materials.append(material)
    obj = bpy.data.objects.new(spec.name, mesh)
    obj.location = spec.center_mm
    obj.rotation_euler = spec.rotation_euler
    obj["pimm_scene_support_ownership"] = "scene-support"
    obj["pimm_scene_support_role"] = spec.role
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _install_light(bpy: Any, spec: EditorialLight) -> Any | None:
    if spec.light_type == "WORLD":
        return None
    light_data = bpy.data.lights.new(f"PIMM_EDITORIAL_{spec.role}", spec.light_type)
    light_data.energy = spec.energy
    light_data.color = spec.color
    light_data["pimm_editorial_light_role"] = spec.role
    if spec.light_type == "AREA":
        light_data.shape = "RECTANGLE"
        light_data.size = spec.size_mm
        light_data.size_y = spec.size_y_mm
    elif spec.light_type == "SUN":
        light_data.angle = spec.angle_radians
    elif spec.light_type == "POINT":
        light_data.shadow_soft_size = spec.size_mm
    obj = bpy.data.objects.new(f"PIMM_EDITORIAL_{spec.role}", light_data)
    obj.location = spec.location_mm
    obj.rotation_euler = spec.rotation_euler
    obj["pimm_editorial_light_role"] = spec.role
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _tag_provenance(datablock: Any, record: EditorialExternalAsset) -> None:
    datablock["pimm_external_source_url"] = record.source_url
    datablock["pimm_external_asset_version_id"] = record.asset_version_id
    datablock["pimm_external_license"] = record.license
    datablock["pimm_external_local_relative_path"] = record.local_relative_path
    datablock["pimm_external_sha256"] = record.sha256
    datablock["pimm_external_intended_shot_ids"] = json.dumps(
        record.intended_shot_ids, separators=(",", ":")
    )
    datablock["pimm_external_machine_master_modified"] = record.machine_master_modified


def _scene_world(bpy: Any) -> Any:
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("PIMM_EDITORIAL_WORKSHOP_WORLD")
        bpy.context.scene.world = world
    world.use_nodes = True
    return world


def _install_hdri(bpy: Any, record: EditorialExternalAsset, strength: float) -> Any:
    world = _scene_world(bpy)
    nodes = world.node_tree.nodes
    background = nodes.get("Background")
    if background is None:
        background = nodes.new("ShaderNodeBackground")
    environment = nodes.new("ShaderNodeTexEnvironment")
    environment.image = bpy.data.images.load(str(record.path), check_existing=False)
    background.inputs["Strength"].default_value = strength
    world.node_tree.links.new(environment.outputs["Color"], background.inputs["Color"])
    world["pimm_editorial_light_role"] = "WORKSHOP_HDRI"
    world["pimm_scene_support_ownership"] = "scene-support"
    world["pimm_scene_support_role"] = "workshop-environment"
    _tag_provenance(world, record)
    proxy = bpy.data.objects.new("PIMM_SCENE_SUPPORT_WORKSHOP_HDRI_ENVIRONMENT", None)
    proxy["pimm_scene_support_ownership"] = "scene-support"
    proxy["pimm_scene_support_role"] = "workshop-environment"
    _tag_provenance(proxy, record)
    bpy.context.scene.collection.objects.link(proxy)
    return proxy


def _product_like_external_object(obj: Any) -> bool:
    if any(obj.get(name) is not None for name in _PRODUCT_PROPERTIES):
        return True
    mesh = getattr(obj, "data", None)
    for material in getattr(mesh, "materials", ()) if mesh is not None else ():
        if material.get("pimm_material_id") is not None or material.get("pimm_material_scope") in {"shared", "machine-local"}:
            return True
    return False


def _install_linked_model(bpy: Any, record: EditorialExternalAsset, shot: EditorialConceptShot) -> Any:
    with bpy.data.libraries.load(str(record.path), link=True, relative=False) as (available, requested):
        if not available.collections:
            raise ValueError(f"editorial external model has no collection: {record.path}")
        requested.collections = [available.collections[0]]
    loaded = [collection for collection in requested.collections if collection is not None]
    if len(loaded) != 1:
        raise ValueError(f"editorial external model did not resolve one collection: {record.path}")
    if any(_product_like_external_object(obj) for obj in getattr(loaded[0], "all_objects", ())):
        raise ValueError(f"product-like external scene support is forbidden: {record.asset_id}")
    instance = bpy.data.objects.new(f"PIMM_SCENE_SUPPORT_EXTERNAL_{record.asset_id.upper()}", None)
    instance.instance_type = "COLLECTION"
    instance.instance_collection = loaded[0]
    instance.location = {
        "tool_cart": (2550.0, 1250.0, 0.0),
        "metal_toolbox": (-1850.0, 900.0, 720.0),
    }[record.asset_id]
    instance["pimm_scene_support_ownership"] = "scene-support"
    instance["pimm_scene_support_role"] = f"external-{record.asset_id.replace('_', '-')}"
    instance["pimm_editorial_shot_id"] = shot.shot_id
    _tag_provenance(instance, record)
    bpy.context.scene.collection.objects.link(instance)
    return instance


def _geometry_signature(items: tuple[EditorialSetGeometry, ...]) -> str:
    payload = [
        [item.name, item.role, item.primitive, item.center_mm, item.dimensions_mm, item.rotation_euler]
        for item in items
    ]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode("utf-8")).hexdigest().upper()


def _validate_shot(shot: EditorialConceptShot) -> None:
    expected = _APPROVED_SHOTS.get(shot.shot_id)
    if expected is None or expected != shot:
        raise ValueError(f"shot is not an exact approved editorial shot: {shot.shot_id}")


def build_editorial_set(bpy: Any, shot: EditorialConceptShot) -> EditorialSetEvidence:
    """Build one concept-specific scene-owned set and return immutable evidence.

    The function never saves a Blender file and never edits or parents anything into
    linked PIMM machine data.  External Blend files are linked and represented by a
    scene-local collection instance; the workshop HDRI is represented by a tagged
    scene-local proxy as well as a tagged World.
    """

    _validate_shot(shot)
    spec = _SETS[shot.concept]
    external = _external_records(shot)
    for item in spec.geometry:
        _install_geometry(bpy, item)
    for item in spec.lights:
        _install_light(bpy, item)
    for record in external:
        if record.asset_id == "university_workshop":
            world_light = next(light for light in spec.lights if light.role == "WORKSHOP_HDRI")
            _install_hdri(bpy, record, world_light.energy)
        else:
            _install_linked_model(bpy, record, shot)
    return EditorialSetEvidence(
        shot_id=shot.shot_id,
        concept=shot.concept,
        geometry=spec.geometry,
        lights=spec.lights,
        shadow_intent=spec.shadow_intent,
        geometry_signature=_geometry_signature(spec.geometry),
        external_assets=external,
    )
