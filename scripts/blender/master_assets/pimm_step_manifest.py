"""Assembly-aware STEP manifest and per-solid interchange exporter for PIMM."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ASSET_ROOT = Path(r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders")
SOURCE_ROOT = ASSET_ROOT / "sources"
MANIFEST_ROOT = ASSET_ROOT / "manifests"
STAGING_ROOT = ASSET_ROOT / "imports" / "master-solids"

EXPECTED_SOURCES: dict[str, dict[str, Any]] = {
    "30G": {
        "path": SOURCE_ROOT / "PIMM-30G-authoritative-source.step",
        "size": 116_623_783,
        "sha256": "2EA1C86BD15386717BB53F02B61490ABB2F8DB45E7D70ED668AF29203A4E2205",
    },
    "50G": {
        "path": SOURCE_ROOT / "PIMM-50G-authoritative-source.step",
        "size": 116_854_560,
        "sha256": "A6CB2CAA65CA2002A3A18D9C341833506764D55F7ED840BC9095ED8AF7386FEF",
    },
}


def sha256_file(path: Path, chunk_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate_source_identity(
    path: Path, *, expected_size: int, expected_sha256: str
) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    stat = resolved.stat()
    if stat.st_size != expected_size:
        raise ValueError(
            f"source byte length mismatch: expected {expected_size}, got {stat.st_size}"
        )
    actual_hash = sha256_file(resolved)
    if actual_hash.upper() != expected_sha256.upper():
        raise ValueError(
            f"source SHA-256 mismatch: expected {expected_sha256.upper()}, got {actual_hash}"
        )
    return {
        "path": str(resolved),
        "size": stat.st_size,
        "sha256": actual_hash,
        "mtime_ns": stat.st_mtime_ns,
    }


def stable_solid_id(
    machine: str, occurrence_id: str, product_id: str, solid_index: int
) -> str:
    identity = f"{machine}|{occurrence_id}|{product_id}|{solid_index}".encode("utf-8")
    return f"{machine}-{hashlib.sha256(identity).hexdigest()[:16]}"


def safe_filename(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return normalized[:80] or "solid"


def validate_manifest_structure(manifest: dict[str, Any]) -> None:
    for key in (
        "source",
        "assemblies",
        "occurrences",
        "non_solid_products",
        "solids",
        "summary",
    ):
        if key not in manifest:
            raise ValueError(f"manifest is missing required field: {key}")

    solids = manifest["solids"]
    if manifest["summary"].get("solid_count") != len(solids):
        raise ValueError("manifest solid count does not match solids array")
    if manifest["summary"].get("non_solid_product_count") != len(
        manifest["non_solid_products"]
    ):
        raise ValueError(
            "manifest non-solid product count does not match non_solid_products array"
        )

    stable_ids: set[str] = set()
    required = {
        "stable_id",
        "assembly_path",
        "product_id",
        "occurrence_id",
        "solid_index",
        "original_name",
        "geometry_signature",
        "interchange_path",
    }
    for solid in solids:
        missing = sorted(required - solid.keys())
        if missing:
            raise ValueError(f"solid is missing required fields: {missing}")
        stable_id = solid["stable_id"]
        if stable_id in stable_ids:
            raise ValueError(f"duplicate stable solid ID: {stable_id}")
        stable_ids.add(stable_id)
        interchange = Path(solid["interchange_path"])
        if not interchange.is_file() or interchange.stat().st_size == 0:
            raise ValueError(f"interchange file is missing or empty: {interchange}")


def _geometry_signature(shape: Any, ocp: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    bbox = ocp["Bnd_Box"]()
    ocp["BRepBndLib"].Add_s(shape, bbox)
    bounds = [round(float(value), 9) for value in bbox.Get()]

    properties = ocp["GProp_GProps"]()
    ocp["BRepGProp"].VolumeProperties_s(shape, properties)
    center = properties.CentreOfMass()
    metrics = {
        "bounds": bounds,
        "volume": round(float(properties.Mass()), 9),
        "center_of_mass": [
            round(float(center.X()), 9),
            round(float(center.Y()), 9),
            round(float(center.Z()), 9),
        ],
        "vertices": _count_subshapes(shape, ocp["TopAbs_VERTEX"], ocp),
        "edges": _count_subshapes(shape, ocp["TopAbs_EDGE"], ocp),
        "faces": _count_subshapes(shape, ocp["TopAbs_FACE"], ocp),
    }
    encoded = json.dumps(metrics, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), metrics


def _count_subshapes(shape: Any, shape_type: Any, ocp: dict[str, Any]) -> int:
    explorer = ocp["TopExp_Explorer"](shape, shape_type)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def _load_ocp() -> dict[str, Any]:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Message import Message_ProgressRange
    from OCP.RWGltf import RWGltf_CafWriter
    from OCP.STEPCAFControl import STEPCAFControl_Reader
    from OCP.TCollection import TCollection_AsciiString, TCollection_ExtendedString
    from OCP.TColStd import TColStd_IndexedDataMapOfStringString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDF import TDF_Label, TDF_LabelSequence, TDF_Tool
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopAbs import (
        TopAbs_EDGE,
        TopAbs_FACE,
        TopAbs_SHELL,
        TopAbs_SOLID,
        TopAbs_VERTEX,
        TopAbs_WIRE,
    )
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    return locals()


def _label_entry(label: Any, ocp: dict[str, Any]) -> str:
    value = ocp["TCollection_AsciiString"]()
    ocp["TDF_Tool"].Entry_s(label, value)
    return value.ToCString()


def _label_name(label: Any, ocp: dict[str, Any]) -> str:
    attribute = ocp["TDataStd_Name"]()
    if label.FindAttribute(ocp["TDataStd_Name"].GetID_s(), attribute):
        return attribute.Get().ToExtString()
    return ""


def _export_solid(shape: Any, name: str, output_path: Path, ocp: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesher = ocp["BRepMesh_IncrementalMesh"](shape, 0.06, False, 0.30, True)
    mesher.Perform()
    if not mesher.IsDone():
        raise RuntimeError(f"solid tessellation failed: {name}")

    application = ocp["XCAFApp_Application"].GetApplication_s()
    document = ocp["TDocStd_Document"](ocp["TCollection_ExtendedString"]("PIMM-SOLID"))
    application.NewDocument(ocp["TCollection_ExtendedString"]("MDTV-XCAF"), document)
    shape_tool = ocp["XCAFDoc_DocumentTool"].ShapeTool_s(document.Main())
    label = shape_tool.AddShape(shape, False)
    ocp["TDataStd_Name"].Set_s(label, ocp["TCollection_ExtendedString"](name))

    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    writer = ocp["RWGltf_CafWriter"](
        ocp["TCollection_AsciiString"](str(temporary)), True
    )
    metadata = ocp["TColStd_IndexedDataMapOfStringString"]()
    if not writer.Perform(document, metadata, ocp["Message_ProgressRange"]()):
        raise RuntimeError(f"solid glTF export failed: {name}")
    if not temporary.is_file() or temporary.stat().st_size == 0:
        raise RuntimeError(f"solid glTF export produced no bytes: {name}")
    temporary.replace(output_path)


def build_manifest(
    step_path: Path, machine: str, output_dir: Path, *, export_meshes: bool = True
) -> dict[str, Any]:
    if machine not in EXPECTED_SOURCES:
        raise ValueError(f"unsupported machine: {machine}")
    expected = EXPECTED_SOURCES[machine]
    source_before = validate_source_identity(
        step_path,
        expected_size=expected["size"],
        expected_sha256=expected["sha256"],
    )
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if step_path.resolve() == output_dir or output_dir in step_path.resolve().parents:
        raise ValueError("output directory must not contain the authoritative source")

    ocp = _load_ocp()
    application = ocp["XCAFApp_Application"].GetApplication_s()
    document = ocp["TDocStd_Document"](ocp["TCollection_ExtendedString"]("PIMM"))
    application.NewDocument(ocp["TCollection_ExtendedString"]("MDTV-XCAF"), document)
    reader = ocp["STEPCAFControl_Reader"]()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.SetLayerMode(True)
    reader.SetPropsMode(True)
    if reader.ReadFile(str(step_path)) != ocp["IFSelect_RetDone"]:
        raise RuntimeError(f"unable to read STEP source: {step_path}")
    if not reader.Transfer(document):
        raise RuntimeError(f"unable to transfer STEP assembly: {step_path}")

    shape_tool = ocp["XCAFDoc_DocumentTool"].ShapeTool_s(document.Main())
    roots = ocp["TDF_LabelSequence"]()
    shape_tool.GetFreeShapes(roots)
    assemblies: list[dict[str, Any]] = []
    occurrences: list[dict[str, Any]] = []
    non_solid_products: list[dict[str, Any]] = []
    solids: list[dict[str, Any]] = []

    def visit_definition(
        definition: Any,
        assembly_path: list[str],
        occurrence_path: str,
        global_location: Any,
    ) -> None:
        components = ocp["TDF_LabelSequence"]()
        is_assembly = shape_tool.GetComponents_s(definition, components, False)
        definition_id = _label_entry(definition, ocp)
        definition_name = _label_name(definition, ocp) or definition_id
        if is_assembly:
            assemblies.append(
                {
                    "id": definition_id,
                    "name": definition_name,
                    "path": assembly_path,
                    "occurrence_path": occurrence_path,
                    "component_count": components.Length(),
                }
            )
            for component_index in range(1, components.Length() + 1):
                component = components.Value(component_index)
                referred = ocp["TDF_Label"]()
                if not shape_tool.GetReferredShape_s(component, referred):
                    raise RuntimeError(
                        f"assembly component has no referred shape: {_label_entry(component, ocp)}"
                    )
                occurrence_id = _label_entry(component, ocp)
                occurrence_name = _label_name(component, ocp) or occurrence_id
                product_id = _label_entry(referred, ocp)
                product_name = _label_name(referred, ocp) or product_id
                next_path = [*assembly_path, occurrence_name]
                next_occurrence_path = f"{occurrence_path}/{occurrence_id}"
                next_location = global_location.Multiplied(
                    shape_tool.GetLocation_s(component)
                )
                occurrences.append(
                    {
                        "id": occurrence_id,
                        "name": occurrence_name,
                        "product_id": product_id,
                        "product_name": product_name,
                        "assembly_path": next_path,
                        "occurrence_path": next_occurrence_path,
                    }
                )
                visit_definition(
                    referred, next_path, next_occurrence_path, next_location
                )
            return

        base_shape = shape_tool.GetShape_s(definition)
        if base_shape.IsNull():
            raise RuntimeError(f"product has no shape: {definition_id}")
        located_shape = base_shape.Moved(global_location)
        explorer = ocp["TopExp_Explorer"](located_shape, ocp["TopAbs_SOLID"])
        solid_index = 0
        while explorer.More():
            solid_index += 1
            solid_shape = explorer.Current()
            stable_id = stable_solid_id(
                machine, occurrence_path, definition_id, solid_index
            )
            original_name = definition_name
            interchange = output_dir / f"{stable_id}--{safe_filename(original_name)}.glb"
            signature, geometry = _geometry_signature(solid_shape, ocp)
            if export_meshes:
                _export_solid(solid_shape, stable_id, interchange, ocp)
            solids.append(
                {
                    "stable_id": stable_id,
                    "assembly_path": assembly_path,
                    "product_id": definition_id,
                    "occurrence_id": occurrence_path.rsplit("/", 1)[-1],
                    "occurrence_path": occurrence_path,
                    "solid_index": solid_index,
                    "original_name": original_name,
                    "geometry_signature": signature,
                    "geometry": geometry,
                    "interchange_path": str(interchange),
                }
            )
            explorer.Next()
        if solid_index == 0:
            non_solid_products.append(
                {
                    "product_id": definition_id,
                    "occurrence_id": occurrence_path.rsplit("/", 1)[-1],
                    "occurrence_path": occurrence_path,
                    "assembly_path": assembly_path,
                    "original_name": definition_name,
                    "topology": {
                        "solids": 0,
                        "shells": _count_subshapes(
                            located_shape, ocp["TopAbs_SHELL"], ocp
                        ),
                        "faces": _count_subshapes(
                            located_shape, ocp["TopAbs_FACE"], ocp
                        ),
                        "wires": _count_subshapes(
                            located_shape, ocp["TopAbs_WIRE"], ocp
                        ),
                        "edges": _count_subshapes(
                            located_shape, ocp["TopAbs_EDGE"], ocp
                        ),
                        "vertices": _count_subshapes(
                            located_shape, ocp["TopAbs_VERTEX"], ocp
                        ),
                    },
                }
            )

    for root_index in range(1, roots.Length() + 1):
        root = roots.Value(root_index)
        root_id = _label_entry(root, ocp)
        root_name = _label_name(root, ocp) or root_id
        visit_definition(
            root,
            [root_name],
            root_id,
            ocp["TopLoc_Location"](),
        )

    source_after = validate_source_identity(
        step_path,
        expected_size=expected["size"],
        expected_sha256=expected["sha256"],
    )
    if source_after != source_before:
        raise RuntimeError("authoritative STEP source changed during manifest build")

    manifest = {
        "schema_version": 1,
        "source": {"machine": machine, **source_before},
        "assemblies": assemblies,
        "occurrences": occurrences,
        "non_solid_products": non_solid_products,
        "solids": solids,
        "summary": {
            "root_count": roots.Length(),
            "assembly_count": len(assemblies),
            "occurrence_count": len(occurrences),
            "non_solid_product_count": len(non_solid_products),
            "solid_count": len(solids),
        },
    }
    if export_meshes:
        validate_manifest_structure(manifest)
    return manifest


def write_manifest(manifest: dict[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(destination)


def build_machine(machine: str, *, export_meshes: bool = True) -> dict[str, Any]:
    source = EXPECTED_SOURCES[machine]["path"]
    interchange_root = STAGING_ROOT / machine.lower()
    manifest = build_manifest(
        source, machine, interchange_root, export_meshes=export_meshes
    )
    destination = MANIFEST_ROOT / f"PIMM-{machine}-import-manifest.json"
    write_manifest(manifest, destination)
    print(
        "PIMM_STEP_MANIFEST "
        f"machine={machine} roots={manifest['summary']['root_count']} "
        f"assemblies={manifest['summary']['assembly_count']} "
        f"occurrences={manifest['summary']['occurrence_count']} "
        f"non_solids={manifest['summary']['non_solid_product_count']} "
        f"solids={manifest['summary']['solid_count']} path={destination}"
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--machine", choices=sorted(EXPECTED_SOURCES))
    parser.add_argument("--audit-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    machines = sorted(EXPECTED_SOURCES) if args.all else [args.machine]
    for machine in machines:
        build_machine(machine, export_meshes=not args.audit_only)


if __name__ == "__main__":
    main()
