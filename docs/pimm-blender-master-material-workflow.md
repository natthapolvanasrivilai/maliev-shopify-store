# PIMM Blender Master Material Workflow

This workflow is for manually correcting the 30G and 50G machine materials while preserving every authoritative STEP solid and its CAD provenance.

## Master files

- `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-30G-MASTER.blend`
- `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-50G-MASTER.blend`
- Shared materials: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-MATERIAL-LIBRARY.blend`

Each master contains 478 separate, selectable STEP-solid objects. They are intentionally magenta because every object begins with the linked `PIMM_UNASSIGNED` material. Each object's initial `pimm_part_name` is the exact `pimm_original_cad_name`; you can replace that label with a clearer name at any time. Both masters use Metric/Millimeters scene units (`scale_length=0.001`) and retain a documented `0.01` object scale. During import, the builder temporarily uses the matching `0.01` scene scale so Blender's glTF unit conversion does not make the physical CAD ten times too large. The CAD-to-Blender `-90° X` conversion is baked into mesh data, so each object opens with zero rotation in the Transform panel.

## Select and identify a part

1. Open one machine master.
2. Switch to the `PIMM_<machine>_MATERIAL_AUDIT` scene.
3. In the Outliner, expand `PIMM_WORKING`. Nested collections mirror the STEP assembly occurrences.
4. Select a body in the viewport. Use `/` on the numeric keypad for Local View when neighboring bodies obscure it.
5. Open Object Properties → Custom Properties. Do not change `pimm_stable_id`, `pimm_product_id`, `pimm_occurrence_id`, `pimm_solid_index`, `pimm_geometry_signature`, or `pimm_original_cad_name`.
6. Replace `pimm_part_name` with your descriptive part name if desired. It starts as the original CAD name. Renaming the visible Blender object is optional because the stable source identity is stored separately.

## Assign a shared physical material

1. In the Material properties, remove `PIMM_UNASSIGNED` only after identifying the body.
2. Link the required material from `PIMM-MATERIAL-LIBRARY.blend`; do not append or duplicate it.
3. Choose the physically correct family from the shared library: CNC milled aluminum, die-cast aluminum, satin sheet aluminum, polished stainless, nickel-plated shaft, black oxide steel, brass, black powder coat, rubber, blue pneumatic tube, engineering plastic, stainless brushed hairline, aluminum satin extrusion, pink powder-coat steel, nylon PA6, PEEK, ASA 3D print (0.2 mm layer), white textile cable, steel braided cable, stainless steel fasteners, steel satin, heat-oxidized blue-black steel, clear acrylic, red illuminated numeric, red illuminated transparent, or red transparent power switch.
4. Set the object custom property `pimm_material_state` to `approved`.
5. Save the machine master.

Editing the shared material in the library updates both machine masters and future linked render scenes. Do not make a shared material local inside a machine master.

## Create a machine-local material

Branding, controller displays, decals, serial labels, and machine-specific artwork stay local to the machine master.

1. Create the material inside the machine master.
2. Add custom property `pimm_material_id` with a stable uppercase identifier, such as `MALIEV_FRONT_ENGRAVING`.
3. Add custom property `pimm_material_scope` with value `machine-local`.
4. Add custom property `pimm_machine` with value `30G` or `50G`.
5. Assign it and set the object `pimm_material_state` to `approved`.

Never place branded or controller-specific materials in the shared library.

## Multiple material slots

The default contract is one material per STEP solid. If a true single CAD solid requires more than one material slot:

1. Assign the required slots manually.
2. Add object custom property `pimm_multi_material_exception`.
3. Describe why the source solid genuinely requires multiple finishes and identify the affected faces.

An undocumented multi-material object blocks publication.

## Geometry exceptions

The audit checks for disconnected mesh components after merging coincident vertices in a temporary in-memory copy. It never modifies the master mesh. If a CAD solid legitimately contains disconnected tessellated regions:

1. Inspect the object against the STEP source and its neighbors.
2. Confirm that it is one authoritative `TopAbs_SOLID`, not two merged CAD bodies.
3. Add `pimm_geometry_exception` explaining the source condition.

Do not split or join master objects merely to silence the audit.

## Run the audit

Working audit permits unassigned objects but fails provenance, material-library, geometry, or master-integrity errors:

```powershell
& 'D:\Blender 5.2\blender.exe' -b '<master.blend>' --python-exit-code 1 -P 'B:\maliev\maliev-shopify-store\.worktrees\pimm-blender-master-assets\scripts\blender\master_assets\pimm_master_audit.py' -- --mode working
```

Publish audit additionally rejects every remaining unassigned or unexplained disconnected object:

```powershell
& 'D:\Blender 5.2\blender.exe' -b '<master.blend>' --python-exit-code 1 -P 'B:\maliev\maliev-shopify-store\.worktrees\pimm-blender-master-assets\scripts\blender\master_assets\pimm_master_audit.py' -- --mode publish
```

Reports are written to the `manifests` folder. Auditing is read-only and verifies the master and authoritative STEP hashes before and after the run.

## Publishing boundary

`PIMM_PUBLISHED` remains empty until the publish audit passes and the owner approves the material work. Render-scene migration and storefront asset replacement must wait for that approval. Legacy Blender projects remain untouched and recoverable during this manual phase.

As of the read-only Task 9 handoff on 2026-08-17, both masters remain `blocked_manual_material_approval`: fresh working audits account for 554 solids per master, preserve source/master identity, report zero integrity or disconnected-geometry errors, and find 10 unassigned solids in each machine. Both audits return `publishable=false`, and the production linked template remains absent. Task 5 proof and Task 6 native-final/release evidence is fixture-only and proves the gates rather than approving real output. The sibling-governance archive plan remains an unapplied zero-item proposal; it is not permission to move or delete any product asset.

## Initial validated handoff

The initial 2026-08-14 handoff is intentionally ready for manual assignment, not publication:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `PIMM-30G-MASTER.blend` | 104,980,950 | `2176F34E2FFD36FE52F1BFF34F71E47AE1B1D87FAC0F0A528601908D8D8FBB18` |
| `PIMM-50G-MASTER.blend` | 106,148,542 | `B5CF3BC3B94B62D6F2302F2BFBAB2794F73A3B95F6DA3E2966C477C813B4AD6B` |
| `PIMM-MATERIAL-LIBRARY.blend` | 358,194 | `F5DD5A1739A3479CE1202AFFFA9C91A56E34551B39B0943F6060CC0724A44EFC` |

Both masters contain 478 unique occurrence-solid objects, four explicitly accounted empty CAD placeholders, zero unexplained disconnected objects, and 478 `PIMM_UNASSIGNED` material states. Their working audits contain zero integrity errors and correctly report `publishable=false`.

The legacy inventory covers 77 Blender projects totaling 13,498,586,358 bytes. Proposed dispositions are 3 `keep-authoritative`, 15 `migrate-scene`, 23 `archive-after-validation`, and 36 `review`. These are recommendations only; the inventory performed no moves or deletions.
