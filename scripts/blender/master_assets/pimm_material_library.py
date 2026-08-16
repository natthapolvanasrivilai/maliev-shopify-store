"""Build the shared, physically reusable PIMM Blender material library."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping


ASSET_ROOT = Path(r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders")
DEFAULT_OUTPUT = ASSET_ROOT / "masters" / "PIMM-MATERIAL-LIBRARY.blend"
DEFAULT_MANIFEST = ASSET_ROOT / "manifests" / "PIMM-material-library.json"

# The owner-approved ASA surface direction is the visible vertical ribbing
# shown in the reference. The coarse pitch is intentionally visual rather
# than literal 0.2 mm FDM layer height so it survives product-scale renders.
ASA_LAYER_LINE_SCALE = 0.12
ASA_LAYER_LINE_DIRECTION = "X"


@dataclass(frozen=True)
class MaterialSpec:
    base_color: tuple[float, float, float, float]
    metallic: float
    roughness: float
    anisotropy: float = 0.0
    coat_weight: float = 0.0
    microstructure: str = "none"
    emission_color: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    emission_strength: float = 0.0
    transmission: float = 0.0
    alpha: float = 1.0


MATERIAL_SPECS: dict[str, MaterialSpec] = {
    "UNASSIGNED": MaterialSpec((1.0, 0.0, 0.65, 1.0), 0.0, 0.50),
    "CNC_MILLED_ALUMINUM": MaterialSpec(
        (0.56, 0.58, 0.61, 1.0), 1.0, 0.22, 0.42, 0.08, "machined_fine"
    ),
    "DIE_CAST_ALUMINUM": MaterialSpec(
        (0.34, 0.35, 0.37, 1.0), 1.0, 0.38, 0.08, 0.02, "cast_grain"
    ),
    "SATIN_SHEET_ALUMINUM": MaterialSpec(
        (0.52, 0.54, 0.57, 1.0), 1.0, 0.29, 0.58, 0.04, "brushed_linear"
    ),
    "POLISHED_STAINLESS": MaterialSpec(
        (0.64, 0.67, 0.70, 1.0), 1.0, 0.11, 0.25, 0.18, "polished"
    ),
    "NICKEL_PLATED_SHAFT": MaterialSpec(
        (0.62, 0.65, 0.69, 1.0), 1.0, 0.16, 0.32, 0.14, "polished"
    ),
    "BLACK_OXIDE_STEEL": MaterialSpec(
        (0.025, 0.030, 0.035, 1.0), 0.78, 0.31, 0.12, 0.0, "fine_grain"
    ),
    "BRASS": MaterialSpec(
        (0.58, 0.34, 0.08, 1.0), 1.0, 0.21, 0.16, 0.08, "machined_fine"
    ),
    "BLACK_POWDERCOAT": MaterialSpec(
        (0.018, 0.020, 0.024, 1.0), 0.08, 0.46, 0.0, 0.0, "powder_grain"
    ),
    "RUBBER_BLACK": MaterialSpec(
        (0.012, 0.014, 0.016, 1.0), 0.0, 0.63, 0.0, 0.0, "rubber"
    ),
    "PNEUMATIC_TUBE_BLUE": MaterialSpec(
        (0.015, 0.31, 0.62, 1.0), 0.0, 0.30, 0.0, 0.18, "polymer"
    ),
    "ENGINEERING_PLASTIC": MaterialSpec(
        (0.055, 0.060, 0.068, 1.0), 0.0, 0.38, 0.0, 0.05, "polymer"
    ),
    "STAINLESS_BRUSHED_HAIRLINE": MaterialSpec(
        (0.60, 0.63, 0.67, 1.0), 1.0, 0.24, 0.78, 0.14, "brushed_linear"
    ),
    "ALUMINUM_SATIN_EXTRUSION": MaterialSpec(
        (0.48, 0.51, 0.55, 1.0), 1.0, 0.30, 0.64, 0.05, "brushed_linear"
    ),
    "PINK_POWDERCOAT_STEEL": MaterialSpec(
        (0.42, 0.035, 0.10, 1.0), 0.12, 0.46, 0.0, 0.02, "powder_grain"
    ),
    "NYLON_PA6": MaterialSpec(
        (0.72, 0.68, 0.58, 1.0), 0.0, 0.42, 0.0, 0.02, "polymer"
    ),
    "PEEK": MaterialSpec(
        (0.31, 0.18, 0.045, 1.0), 0.0, 0.34, 0.0, 0.03, "polymer"
    ),
    "ASA_3D_PRINT_0_2MM": MaterialSpec(
        (0.006, 0.007, 0.010, 1.0), 0.0, 0.52, 0.0, 0.02, "layer_lines"
    ),
    "WHITE_TEXTILE_CABLE": MaterialSpec(
        (0.82, 0.82, 0.78, 1.0), 0.0, 0.70, 0.0, 0.0, "textile"
    ),
    "STEEL_BRAIDED_CABLE": MaterialSpec(
        (0.28, 0.30, 0.33, 1.0), 0.86, 0.38, 0.22, 0.03, "braided"
    ),
    "STAINLESS_STEEL_FASTENERS": MaterialSpec(
        (0.58, 0.61, 0.65, 1.0), 1.0, 0.18, 0.26, 0.12, "machined_fine"
    ),
    "STEEL_SATIN": MaterialSpec(
        (0.39, 0.41, 0.44, 1.0), 0.95, 0.32, 0.45, 0.05, "brushed_linear"
    ),
    "STEEL_HEAT_OXIDIZED_BLUEBLACK": MaterialSpec(
        (0.018, 0.028, 0.050, 1.0), 0.88, 0.34, 0.16, 0.0, "fine_grain"
    ),
    "GREEN_ILLUMINATED_NUMERIC": MaterialSpec(
        (0.008, 0.028, 0.010, 1.0), 0.0, 0.24, 0.0, 0.0, "none",
        (0.03, 1.0, 0.08, 1.0), 5.0
    ),
    "RED_ILLUMINATED_NUMERIC": MaterialSpec(
        (0.030, 0.006, 0.005, 1.0), 0.0, 0.24, 0.0, 0.0, "none",
        (1.0, 0.025, 0.012, 1.0), 5.0
    ),
    "RED_ILLUMINATED_TRANSPARENT": MaterialSpec(
        (0.30, 0.008, 0.004, 1.0), 0.0, 0.20, 0.0, 0.04, "none",
        (1.0, 0.012, 0.006, 1.0), 1.8, 0.38, 0.78
    ),
    # The white powder-coat profile already exists in the published library;
    # keep it declared here so a rebuild cannot silently drop it.
    "WHITE_POWDERCOAT_STEEL": MaterialSpec(
        (0.72, 0.74, 0.77, 1.0), 0.0, 0.46, 0.0, 0.02, "powder_grain"
    ),
    # Generic controller-surface finishes. These are reusable physical
    # profiles only; machine artwork, labels, logos, and display assignments
    # remain local to each machine master.
    "BLACK_GLOSS_GLASS": MaterialSpec(
        (0.006, 0.008, 0.010, 1.0), 0.05, 0.12, 0.0, 0.24, "none",
        (0.0, 0.0, 0.0, 1.0), 0.0, 0.08, 1.0
    ),
    "INACTIVE_NUMERIC_SEGMENT": MaterialSpec(
        (0.16, 0.17, 0.18, 1.0), 0.10, 0.34, 0.05, 0.08, "fine_grain"
    ),
    "CHARCOAL_TEXTURED_POLYMER": MaterialSpec(
        (0.035, 0.038, 0.042, 1.0), 0.0, 0.42, 0.0, 0.08, "powder_grain"
    ),
    "CONTROL_PANEL_SATIN_GRAY": MaterialSpec(
        (0.36, 0.36, 0.34, 1.0), 0.08, 0.42, 0.04, 0.06, "fine_grain"
    ),
    "BLUE_ACCENT_POLYMER": MaterialSpec(
        (0.018, 0.035, 0.21, 1.0), 0.05, 0.32, 0.0, 0.08, "polymer"
    ),
    "GREEN_ILLUMINATED_TRANSPARENT": MaterialSpec(
        (0.006, 0.28, 0.012, 1.0), 0.0, 0.20, 0.0, 0.04, "none",
        (0.04, 1.0, 0.08, 1.0), 1.8, 0.38, 0.78
    ),
    "RED_SIGNAL_POLYMER": MaterialSpec(
        (0.32, 0.015, 0.012, 1.0), 0.05, 0.34, 0.0, 0.04, "polymer"
    ),
    "GREEN_SIGNAL_POLYMER": MaterialSpec(
        (0.18, 0.56, 0.20, 1.0), 0.05, 0.34, 0.0, 0.04, "polymer"
    ),
    "WARM_WHITE_MARKING": MaterialSpec(
        (0.72, 0.62, 0.40, 1.0), 0.05, 0.33, 0.0, 0.04, "none"
    ),
    "SINTERED_BRONZE_POROUS": MaterialSpec(
        (0.42, 0.20, 0.045, 1.0), 0.72, 0.44, 0.12, 0.04, "sintered_porous"
    ),
}


FORBIDDEN_SHARED_TOKENS = (
    "MALIEV",
    "DECAL",
    "DISPLAY",
    "CONTROLLER",
    "SERIAL",
    "AIRTAC",
    "LOGO",
)


def validate_material_specs(specs: Mapping[str, MaterialSpec]) -> None:
    if set(specs) != set(MATERIAL_SPECS):
        additions = sorted(set(specs) - set(MATERIAL_SPECS))
        if any(token in material_id for material_id in additions for token in FORBIDDEN_SHARED_TOKENS):
            raise ValueError(f"machine-local material cannot enter shared library: {additions}")
        raise ValueError(f"shared material catalog drifted: {sorted(specs)}")
    for material_id, spec in specs.items():
        for value_name in ("metallic", "roughness", "anisotropy", "coat_weight"):
            value = getattr(spec, value_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{material_id} {value_name} is outside 0..1")
    if len({MATERIAL_SPECS[key].roughness for key in (
        "CNC_MILLED_ALUMINUM",
        "DIE_CAST_ALUMINUM",
        "SATIN_SHEET_ALUMINUM",
        "NICKEL_PLATED_SHAFT",
    )}) != 4:
        raise ValueError("metal finish roughness profiles must remain distinct")


def _set_principled_input(node, names: tuple[str, ...], value) -> None:
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None:
            socket.default_value = value
            return


def _add_microstructure(material, principled, spec: MaterialSpec) -> None:
    if spec.microstructure in {"none", "polished", "polymer", "rubber"}:
        return
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    if spec.microstructure == "layer_lines":
        # Scene units are millimetres, so a wave scale of 5.0 gives one
        # repeat every 0.2 mm. Object coordinates keep that spacing physical
        # instead of compressing it into a generated 0..1 texture range.
        coordinates = nodes.new("ShaderNodeTexCoord")
        coordinates.name = "PIMM_LAYER_LINE_COORDINATES"
        wave = nodes.new("ShaderNodeTexWave")
        wave.name = "PIMM_LAYER_LINES_0_2MM"
        wave.wave_type = "BANDS"
        wave.bands_direction = ASA_LAYER_LINE_DIRECTION
        wave.inputs["Scale"].default_value = ASA_LAYER_LINE_SCALE
        wave.inputs["Distortion"].default_value = 0.0
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.name = "PIMM_LAYER_LINE_PROFILE"
        ramp.color_ramp.elements[0].position = 0.35
        ramp.color_ramp.elements[1].position = 0.65
        links.new(coordinates.outputs["Object"], wave.inputs["Vector"])
        links.new(wave.outputs["Color"], ramp.inputs["Fac"])
        bump = nodes.new("ShaderNodeBump")
        bump.name = "PIMM_LAYER_LINE_BUMP"
        bump.inputs["Strength"].default_value = 0.20
        bump.inputs["Distance"].default_value = 0.025
        links.new(ramp.outputs["Color"], bump.inputs["Height"])
        normal = principled.inputs.get("Normal")
        if normal is not None:
            links.new(bump.outputs["Normal"], normal)
        return
    if spec.microstructure == "sintered_porous":
        # The silencer face needs visible, coarse sintered pores rather than
        # a fine machining grain. A low-frequency noise field drives both a
        # dark pore-color ramp and a deeper bump, while the threaded body can
        # continue using the separate brass profile.
        texture = nodes.new("ShaderNodeTexNoise")
        texture.name = "PIMM_SINTERED_POROUS_CELLS"
        texture.noise_dimensions = "3D"
        texture.inputs["Scale"].default_value = 92.0
        texture.inputs["Detail"].default_value = 3.0
        texture.inputs["Roughness"].default_value = 0.72
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.name = "PIMM_SINTERED_POROUS_COLOR"
        ramp.color_ramp.elements[0].position = 0.34
        ramp.color_ramp.elements[0].color = (
            spec.base_color[0] * 0.18,
            spec.base_color[1] * 0.18,
            spec.base_color[2] * 0.18,
            1.0,
        )
        ramp.color_ramp.elements[1].position = 0.58
        ramp.color_ramp.elements[1].color = spec.base_color
        links.new(texture.outputs["Fac"], ramp.inputs["Fac"])
        base_color = principled.inputs.get("Base Color")
        if base_color is not None:
            links.new(ramp.outputs["Color"], base_color)
        bump = nodes.new("ShaderNodeBump")
        bump.name = "PIMM_SINTERED_POROUS_BUMP"
        bump.inputs["Strength"].default_value = 0.24
        bump.inputs["Distance"].default_value = 0.028
        links.new(texture.outputs["Fac"], bump.inputs["Height"])
        normal = principled.inputs.get("Normal")
        if normal is not None:
            links.new(bump.outputs["Normal"], normal)
        return
    texture = nodes.new("ShaderNodeTexNoise")
    texture.name = f"PIMM_{spec.microstructure.upper()}"
    texture.noise_dimensions = "3D"
    scale = {
        "cast_grain": 145.0,
        "powder_grain": 110.0,
        "fine_grain": 260.0,
        "machined_fine": 420.0,
        "brushed_linear": 310.0,
        "textile": 240.0,
        "braided": 180.0,
        "layer_lines": 700.0,
        "sintered_porous": 260.0,
    }[spec.microstructure]
    texture.inputs["Scale"].default_value = scale
    texture.inputs["Detail"].default_value = 2.0
    texture.inputs["Roughness"].default_value = 0.46
    bump = nodes.new("ShaderNodeBump")
    bump.name = "PIMM_MICRO_BUMP"
    bump.inputs["Strength"].default_value = {
        "cast_grain": 0.075,
        "powder_grain": 0.055,
        "fine_grain": 0.025,
        "machined_fine": 0.018,
        "brushed_linear": 0.022,
        "textile": 0.035,
        "braided": 0.040,
        "layer_lines": 0.012,
        "sintered_porous": 0.095,
    }[spec.microstructure]
    bump.inputs["Distance"].default_value = 0.018
    links.new(texture.outputs["Fac"], bump.inputs["Height"])
    normal = principled.inputs.get("Normal")
    if normal is not None:
        links.new(bump.outputs["Normal"], normal)


def create_material(bpy, material_id: str, spec: MaterialSpec):
    material = bpy.data.materials.new(name=f"PIMM_{material_id}")
    material.use_nodes = True
    material.diffuse_color = spec.base_color
    material["pimm_material_id"] = material_id
    material["pimm_material_scope"] = "shared"
    material["pimm_material_revision"] = 1
    material["pimm_manual_assignment_allowed"] = True
    material["pimm_material_profile_json"] = json.dumps(asdict(spec), sort_keys=True)
    principled = next(
        node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"
    )
    principled.name = "PIMM_PHYSICAL_SURFACE"
    _set_principled_input(principled, ("Base Color",), spec.base_color)
    _set_principled_input(principled, ("Metallic",), spec.metallic)
    _set_principled_input(principled, ("Roughness",), spec.roughness)
    _set_principled_input(
        principled, ("Anisotropic IOR Level", "Anisotropic"), spec.anisotropy
    )
    _set_principled_input(
        principled, ("Coat Weight", "Clearcoat"), spec.coat_weight
    )
    _set_principled_input(
        principled, ("Emission Color", "Emission"), spec.emission_color
    )
    _set_principled_input(principled, ("Emission Strength",), spec.emission_strength)
    _set_principled_input(
        principled, ("Transmission Weight", "Transmission"), spec.transmission
    )
    _set_principled_input(principled, ("Alpha",), spec.alpha)
    if spec.alpha < 1.0:
        try:
            material.surface_render_method = "DITHERED"
        except (AttributeError, TypeError):
            pass
    _add_microstructure(material, principled, spec)
    try:
        material.asset_mark()
        material.asset_data.description = f"PIMM shared physical material: {material_id}"
    except (AttributeError, RuntimeError):
        pass
    return material


def _clear_scene(bpy) -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in list(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)


def build_material_library(output_blend: Path | None, output_manifest: Path | None) -> dict:
    import bpy

    validate_material_specs(MATERIAL_SPECS)
    _clear_scene(bpy)
    scene = bpy.context.scene
    scene.name = "PIMM_MATERIAL_AUDIT"
    scene["pimm_library_type"] = "shared-physical-materials"
    scene["pimm_material_revision"] = 1
    scene.render.engine = "BLENDER_EEVEE"

    materials = {
        material_id: create_material(bpy, material_id, spec)
        for material_id, spec in MATERIAL_SPECS.items()
    }

    swatches = bpy.data.collections.new("PIMM_MATERIAL_SWATCHES")
    scene.collection.children.link(swatches)
    for index, material_id in enumerate(MATERIAL_SPECS):
        row, column = divmod(index, 4)
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=48,
            ring_count=24,
            radius=0.42,
            location=(column * 1.35 - 2.0, -row * 1.35 + 1.35, 0.5),
        )
        swatch = bpy.context.object
        swatch.name = f"SWATCH_{material_id}"
        swatch.data.materials.append(materials[material_id])
        for collection in list(swatch.users_collection):
            collection.objects.unlink(swatch)
        swatches.objects.link(swatch)

    bpy.ops.object.light_add(type="AREA", location=(1.5, -2.0, 5.0))
    key = bpy.context.object
    key.name = "AUDIT_KEY"
    key.data.energy = 900.0
    key.data.shape = "DISK"
    key.data.size = 4.0
    bpy.ops.object.light_add(type="AREA", location=(-4.0, 1.0, 2.5))
    fill = bpy.context.object
    fill.name = "AUDIT_FILL"
    fill.data.energy = 450.0
    fill.data.size = 3.0

    manifest = {
        "schema_version": 1,
        "revision": 1,
        "materials": {
            material_id: asdict(spec) for material_id, spec in MATERIAL_SPECS.items()
        },
    }
    validate_blender_library(bpy)

    if output_blend is not None:
        output_blend.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_blend.with_name(output_blend.stem + ".tmp.blend")
        if temporary.exists():
            temporary.unlink()
        bpy.ops.wm.save_as_mainfile(filepath=str(temporary), check_existing=False)
        os.replace(temporary, output_blend)
        digest = hashlib.sha256(output_blend.read_bytes()).hexdigest().upper()
        manifest["blend"] = {
            "path": str(output_blend.resolve()),
            "size": output_blend.stat().st_size,
            "sha256": digest,
        }
    if output_manifest is not None:
        output_manifest.parent.mkdir(parents=True, exist_ok=True)
        temporary_manifest = output_manifest.with_suffix(".json.tmp")
        temporary_manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary_manifest, output_manifest)
    return manifest


def validate_blender_library(bpy) -> None:
    expected_names = {f"PIMM_{material_id}" for material_id in MATERIAL_SPECS}
    actual = {material.name for material in bpy.data.materials if material.name in expected_names}
    if actual != expected_names:
        raise RuntimeError(f"shared material set drifted: {sorted(actual)}")
    for material_id in MATERIAL_SPECS:
        material = bpy.data.materials[f"PIMM_{material_id}"]
        if material.get("pimm_material_id") != material_id:
            raise RuntimeError(f"material ID drifted: {material.name}")
        if material.get("pimm_material_scope") != "shared":
            raise RuntimeError(f"material scope drifted: {material.name}")
        if not material.get("pimm_manual_assignment_allowed"):
            raise RuntimeError(f"material cannot be manually assigned: {material.name}")
        if not any(node.type == "BSDF_PRINCIPLED" for node in material.node_tree.nodes):
            raise RuntimeError(f"material has no physical surface: {material.name}")


def blender_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    return parser.parse_args(blender_args())


def main() -> None:
    args = parse_args()
    manifest = build_material_library(
        None if args.validate_only else args.output,
        None if args.validate_only else args.manifest,
    )
    print(
        f"PIMM_MATERIAL_LIBRARY materials={len(manifest['materials'])} "
        f"saved={not args.validate_only}"
    )


if __name__ == "__main__":
    main()
