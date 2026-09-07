"""Governed evidence for non-STEP artwork published with PIMM masters."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping


PUBLISHED_ARTWORK_COUNT_PROPERTY = "pimm_published_artwork_count"
PUBLISHED_ARTWORK_SHA256_PROPERTY = "pimm_published_artwork_sha256"


@dataclass(frozen=True)
class PublishedArtworkSpec:
    """Exact identity contract for one master-owned artwork surface."""

    role: str
    object_name: str
    asset_key: str
    attached_parent: str
    material_name: str
    material_id: str
    image_relative_path: str
    image_sha256: str


_AIRTAC_IMAGE_SHA256 = "30973D1EB16ADBBFC4CBD9C868E1ADB4D8EC96F280B0EDDDAFF7D941DD3E6D15"
_GAUGE_IMAGE_SHA256 = "D1E02A1C703D0C854CA0C610D0EDBBA07E225C51735BB900506C0F2DB779EA39"


ARTWORK_SPECS_BY_MACHINE: dict[str, tuple[PublishedArtworkSpec, ...]] = {
    "30G": (
        PublishedArtworkSpec(
            role="pneumatic_switch_decal",
            object_name="PIMM30_MASTER_AirTAC_Decal",
            asset_key="PIMM_SHARED_PNEUMATIC_SWITCH_DECAL",
            attached_parent="30G__white-powdercoat-aluminum__fdabf8545f224107",
            material_name="MAT_AirTAC_Decal",
            material_id="MACHINE_ARTWORK_AIRTAC_DECAL",
            image_relative_path="assets/decal.png",
            image_sha256=_AIRTAC_IMAGE_SHA256,
        ),
        PublishedArtworkSpec(
            role="pressure_gauge_face",
            object_name="PIMM30_MASTER_Pressure_Gauge_Face",
            asset_key="PIMM_SHARED_PRESSURE_GAUGE_FACE",
            attached_parent="30G__MSPGN1__a7d370380a06c044",
            material_name="MAT_Pressure_Gauge_Decal",
            material_id="MACHINE_ARTWORK_PRESSURE_GAUGE_FACE",
            image_relative_path="assets/pressure-gauge-decal-no-needle.png",
            image_sha256=_GAUGE_IMAGE_SHA256,
        ),
    ),
    "50G": (
        PublishedArtworkSpec(
            role="pneumatic_switch_decal",
            object_name="PIMM50_MASTER_AirTAC_Decal",
            asset_key="PIMM_SHARED_PNEUMATIC_SWITCH_DECAL",
            attached_parent="50G__white-powdercoat-aluminum__a7f1dbd423430c1d",
            material_name="MAT_AirTAC_Decal",
            material_id="MACHINE_ARTWORK_AIRTAC_DECAL",
            image_relative_path="assets/decal.png",
            image_sha256=_AIRTAC_IMAGE_SHA256,
        ),
        PublishedArtworkSpec(
            role="pressure_gauge_face",
            object_name="PIMM50_MASTER_Pressure_Gauge_Face",
            asset_key="PIMM_SHARED_PRESSURE_GAUGE_FACE",
            attached_parent="50G__MSPGN1__3aea9e6cc20300b1",
            material_name="MAT_Pressure_Gauge_Decal",
            material_id="MACHINE_ARTWORK_PRESSURE_GAUGE_FACE",
            image_relative_path="assets/pressure-gauge-decal-no-needle.png",
            image_sha256=_GAUGE_IMAGE_SHA256,
        ),
    ),
}


_EVIDENCE_FIELDS = (
    "machine",
    "object_name",
    "role",
    "asset_key",
    "attached_parent",
    "material_id",
    "image_relative_path",
    "image_sha256",
    "mesh_sha256",
    "uv_sha256",
    "transform_sha256",
    "packed_sha256",
    "render_visible",
)


def canonical_artwork_evidence(
    records: Iterable[Mapping[str, object]],
) -> tuple[int, str]:
    """Return deterministic count and SHA-256 for exact artwork records."""

    normalized = [
        {field: record.get(field) for field in _EVIDENCE_FIELDS}
        for record in records
    ]
    normalized.sort(key=lambda row: (str(row["machine"]), str(row["role"])))
    payload = json.dumps(
        normalized,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return len(normalized), hashlib.sha256(payload).hexdigest().upper()


def protected_artwork_evidence(
    records: Iterable[Mapping[str, object]],
) -> tuple[int, str]:
    """Fingerprint fields that a governance-only migration must not change."""

    protected_fields = tuple(
        field for field in _EVIDENCE_FIELDS if field != "material_id"
    )
    normalized = [
        {field: record.get(field) for field in protected_fields}
        for record in records
    ]
    normalized.sort(key=lambda row: (str(row["machine"]), str(row["role"])))
    return len(normalized), _sha256_json(normalized)


def _sha256_json(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def _mesh_fingerprint(mesh: object) -> str:
    return _sha256_json(
        {
            "vertices": [
                [float(value) for value in vertex.co]
                for vertex in getattr(mesh, "vertices", ())
            ],
            "edges": [list(edge.vertices) for edge in getattr(mesh, "edges", ())],
            "polygons": [
                list(polygon.vertices) for polygon in getattr(mesh, "polygons", ())
            ],
        }
    )


def _uv_fingerprint(mesh: object) -> str:
    return _sha256_json(
        [
            {
                "name": str(getattr(layer, "name", "")),
                "uv": [
                    [float(value) for value in datum.uv]
                    for datum in getattr(layer, "data", ())
                ],
            }
            for layer in getattr(mesh, "uv_layers", ())
        ]
    )


def _transform_fingerprint(obj: object) -> str:
    return _sha256_json(
        [[float(value) for value in row] for row in getattr(obj, "matrix_world", ())]
    )


def _packed_image_sha256(image: object) -> str | None:
    if getattr(image, "packed_file", None) is None:
        return None
    source = Path(str(getattr(image, "filepath", "")))
    if not source.is_file():
        return None
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def capture_published_artwork(
    published: object, machine: str
) -> tuple[list[dict[str, object]], list[str]]:
    """Capture exact Blender artwork evidence without mutating the open file."""

    specs = ARTWORK_SPECS_BY_MACHINE.get(machine, ())
    expected_names = {spec.object_name for spec in specs}
    expected_roles = {spec.role for spec in specs}
    expected_keys = {spec.asset_key for spec in specs}
    candidates = [
        obj
        for obj in getattr(published, "all_objects", ())
        if getattr(obj, "type", None) == "MESH"
        and (
            str(getattr(obj, "name", "")) in expected_names
            or obj.get("pimm_asset_role") in expected_roles
            or obj.get("pimm_identical_asset_key") in expected_keys
        )
    ]
    records: list[dict[str, object]] = []
    errors: list[str] = []
    for obj in candidates:
        mesh = getattr(obj, "data", None)
        materials = [material for material in getattr(mesh, "materials", ()) if material]
        if len(materials) != 1:
            errors.append(
                f"artwork object requires exactly one material: {getattr(obj, 'name', '')}"
            )
            continue
        material = materials[0]
        image_nodes = [
            node
            for node in getattr(getattr(material, "node_tree", None), "nodes", ())
            if getattr(node, "bl_idname", "") == "ShaderNodeTexImage"
            and getattr(node, "image", None) is not None
        ]
        images = {node.image for node in image_nodes}
        if len(images) != 1:
            errors.append(
                f"artwork material requires exactly one image: {getattr(obj, 'name', '')}"
            )
            continue
        image = next(iter(images))
        packed_sha256 = _packed_image_sha256(image)
        image_name = str(obj.get("pimm_asset_image", getattr(image, "name", "")))
        records.append(
            {
                "machine": obj.get("pimm_machine"),
                "object_name": str(getattr(obj, "name", "")),
                "role": obj.get("pimm_asset_role"),
                "asset_key": obj.get("pimm_identical_asset_key"),
                "attached_parent": obj.get("pimm_attached_parent"),
                "material_id": material.get("pimm_material_id"),
                "image_relative_path": f"assets/{image_name}",
                "image_sha256": packed_sha256,
                "mesh_sha256": _mesh_fingerprint(mesh),
                "uv_sha256": _uv_fingerprint(mesh),
                "transform_sha256": _transform_fingerprint(obj),
                "packed_sha256": packed_sha256,
                "render_visible": getattr(obj, "hide_render", None) is False,
                "stable_id": obj.get("pimm_stable_id"),
            }
        )
    return records, errors


def validate_published_artwork(
    published: object, machine: str
) -> tuple[list[dict[str, object]], list[str]]:
    """Validate artwork objects and their embedded collection evidence."""

    records, errors = capture_published_artwork(published, machine)
    errors.extend(validate_artwork_records(machine, records))
    count, digest = canonical_artwork_evidence(records)
    if published.get(PUBLISHED_ARTWORK_COUNT_PROPERTY) != count:
        errors.append("PIMM_PUBLISHED embedded artwork count does not match its contents")
    if published.get(PUBLISHED_ARTWORK_SHA256_PROPERTY) != digest:
        errors.append("PIMM_PUBLISHED embedded artwork SHA-256 does not match its contents")

    record_names = {str(record["object_name"]) for record in records}
    for obj in getattr(published, "all_objects", ()):
        if getattr(obj, "type", None) != "MESH":
            continue
        is_geometry = bool(obj.get("pimm_stable_id"))
        is_artwork = str(getattr(obj, "name", "")) in record_names
        if is_geometry and is_artwork:
            errors.append(f"published mesh is dual-classified: {getattr(obj, 'name', '')}")
        elif not is_geometry and not is_artwork:
            errors.append(f"published mesh is unclassified: {getattr(obj, 'name', '')}")
    return records, errors


def validate_artwork_records(
    machine: str,
    records: Iterable[Mapping[str, object]],
) -> list[str]:
    """Validate captured artwork against the exact machine specification."""

    specs = ARTWORK_SPECS_BY_MACHINE.get(machine)
    if specs is None:
        return [f"unsupported artwork machine: {machine}"]

    rows = list(records)
    errors: list[str] = []
    expected_by_role = {spec.role: spec for spec in specs}
    roles = [str(row.get("role", "")) for row in rows]
    duplicates = sorted({role for role in roles if roles.count(role) > 1})
    if duplicates:
        errors.append(f"duplicate artwork roles: {duplicates}")
    missing = sorted(set(expected_by_role) - set(roles))
    if missing:
        errors.append(f"missing artwork roles: {missing}")
    unexpected = sorted(set(roles) - set(expected_by_role))
    if unexpected:
        errors.append(f"unexpected artwork roles: {unexpected}")

    for row in rows:
        role = str(row.get("role", ""))
        spec = expected_by_role.get(role)
        if spec is None:
            continue
        if row.get("stable_id") not in (None, ""):
            errors.append(f"artwork role {role} must not carry a STEP stable_id")
        expected = asdict(spec)
        for key in (
            "object_name",
            "asset_key",
            "attached_parent",
            "material_id",
            "image_relative_path",
            "image_sha256",
        ):
            if row.get(key) != expected[key]:
                errors.append(
                    f"artwork role {role} {key} mismatch: "
                    f"expected {expected[key]!r}, got {row.get(key)!r}"
                )
        if row.get("machine") != machine:
            errors.append(f"artwork role {role} machine mismatch")
        if row.get("packed_sha256") != spec.image_sha256:
            errors.append(f"artwork role {role} packed_sha256 mismatch")
        for fingerprint in ("mesh_sha256", "uv_sha256", "transform_sha256"):
            value = row.get(fingerprint)
            if not isinstance(value, str) or len(value) != 64:
                errors.append(f"artwork role {role} {fingerprint} is invalid")
        if row.get("render_visible") is not True:
            errors.append(f"artwork role {role} is hidden from render")
    return errors
