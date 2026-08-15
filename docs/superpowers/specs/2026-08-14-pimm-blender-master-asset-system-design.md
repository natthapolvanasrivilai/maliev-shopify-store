# PIMM Blender Master Asset System Design

**Date:** 2026-08-14  
**Status:** Approved design  
**Scope:** 30G and 50G pneumatic injection molding machine CAD, Blender masters, materials, render dependencies, and legacy project consolidation

## Objective

Replace the current collection of inconsistent Blender projects with one authoritative master for each machine, one shared physical-material library, and a small set of linked render scenes. The system must preserve each STEP solid as an individually selectable Blender object so the owner can manually name parts and assign the correct materials without scripts guessing or overwriting those decisions.

The authoritative CAD inputs are:

- `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\sources\PIMM-30G-authoritative-source.step`
- `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\sources\PIMM-50G-authoritative-source.step`

These are verified copies of `Z:\30g.step` and `Z:\50g.step`:

- 30G: 116,901,306 bytes; SHA-256 `D1522BEB526BAF96C0A4707E0AC296F660BBC7339E60FE4A88931E1D5203E5CE`
- 50G: 117,113,211 bytes; SHA-256 `405534913F74ABB1E801577EABDA1BC1F7C8C5FFC37FEB84D2D2EF15DF2BF455`

These hashes and sizes must remain part of the import manifest.

Blender authoring units are Metric/Millimeters with `scene.unit_settings.scale_length=0.001`. Every imported STEP-solid object carries the fixed `0.01` source-to-Blender scale in its transform and `pimm_source_to_blender_scale` provenance property.

## Target Architecture

```text
blender-product-renders/
  sources/
    PIMM-30G-authoritative-source.step
    PIMM-50G-authoritative-source.step

  masters/
    PIMM-30G-MASTER.blend
    PIMM-50G-MASTER.blend
    PIMM-MATERIAL-LIBRARY.blend

  renders/
    scenes/
      30g/
      50g/
    output/
      30g/
      50g/
    archive/
      YYYY-MM-DD-pre-master-migration/

  manifests/
    PIMM-30G-import-manifest.json
    PIMM-50G-import-manifest.json
    blender-project-inventory.json
```

The two machine masters own product geometry and material assignments. The material library owns physically reusable materials. Render scenes own cameras, lighting, shadow catchers, animation, and output settings only.

## Authoritative Machine Masters

Each master contains:

- one Blender mesh object per STEP solid;
- collections representing the STEP assembly and product-occurrence hierarchy;
- stable source provenance on every object;
- the owner's human-readable part name;
- exactly one approved material assignment unless a documented multi-material part requires more;
- a dedicated material-audit scene and published product collection;
- no marketing cameras, page-specific lighting, or storefront animations.

The working collection remains editable. Render consumers link only the validated `PUBLISHED` collection. Publishing is an explicit validation step, not an automatic save side effect.

## Assembly-Aware STEP Import

The canonical import path must use an assembly-aware STEP/XCAF pipeline. OBJ is forbidden as a canonical machine source because it loses product occurrences, assembly ownership, stable CAD identity, and reliable solid boundaries.

For every STEP solid, the importer records:

- machine identifier (`30G` or `50G`);
- source STEP SHA-256 and byte length;
- STEP product and product-occurrence identifiers;
- assembly path;
- original CAD label or generated fallback label;
- solid index within its source representation;
- imported geometry signature;
- import timestamp and importer version.

Each solid becomes a separate mesh object even when adjacent solids share a material or touch geometrically. The importer must not join by material, connectivity, name, or proximity. STEP assembly nodes become Blender collections; occurrences remain traceable to their parent collections.

Initial Blender names use a deterministic pattern such as:

`30G__UpperAssembly__SOLID_0042`

The immutable original CAD name remains in a custom property. A separate `pimm_part_name` property stores the owner's descriptive name. Renaming a Blender object must never destroy source identity.

## Manual Material Authoring

All imported objects begin with a conspicuous `PIMM_UNASSIGNED` audit material. The importer may classify geometry for reporting, but it must not guess or apply final production materials.

The owner assigns materials manually from one of two locations:

1. Shared physical materials linked from `PIMM-MATERIAL-LIBRARY.blend`.
2. Machine-local materials stored in the corresponding master.

Shared materials include physically reusable finishes such as:

- CNC-milled aluminum;
- die-cast aluminum;
- brushed or satin sheet aluminum;
- polished stainless steel;
- nickel-plated shaft steel;
- black oxide steel;
- brass;
- powder-coated steel;
- rubber, tubing, and engineering plastics.

Machine-local materials include:

- MALIEV engraving and decals;
- AIRTAC and controller artwork;
- display digits and indicators;
- serial labels and machine-specific markings;
- genuinely unique finishes that should not propagate to the other machine.

No automation may overwrite an approved manual assignment. Shared materials remain linked so one physical-material correction can propagate consistently. Machine-local branding and display materials remain isolated.

## Material Audit Workspace

Each machine master includes a dedicated audit scene optimized for manual work. It supports:

- isolation by assembly collection;
- searching by original CAD name, stable source ID, or owner-assigned name;
- filtering unassigned objects;
- identifying objects with multiple material slots;
- identifying disconnected geometry inside one imported solid;
- showing neighboring parts without making them selectable;
- neutral lighting that reveals roughness, reflectivity, and material boundaries;
- a validation panel or report summarizing assigned, unassigned, and exceptional objects.

The audit workflow must make the selected body and its provenance obvious. Material assignment remains a normal Blender operation, not a custom opaque database.

## Render Scene Dependencies

Render scenes link the appropriate `PUBLISHED` machine collection from its master. They must not embed private copies of product geometry or product materials.

Render scenes may own:

- cameras and framing;
- lights and reflection cards;
- physical shadow catchers and compositor setup;
- animation rigs and approved transform controls;
- render layers, output formats, and file paths.

Library overrides are permitted only when required for transforms, animation controls, or visibility. Product materials cannot be overridden locally. Any unauthorized local product material or copied product mesh blocks validation.

Every render scene records the master path, published revision, source STEP hash, and material-library revision it was validated against. Missing or mismatched dependencies fail closed.

## Reimport and Revision Handling

A revised STEP file is never imported directly over an approved master. It is imported into a staging Blender file and compared with the current master using source identifiers and geometry signatures.

The migration report classifies solids as:

- unchanged;
- renamed or moved within the assembly;
- geometry changed;
- added;
- removed;
- ambiguous and requiring manual review.

Approved names and materials may transfer only for deterministic matches. Ambiguous matches remain `PIMM_UNASSIGNED`. The owner reviews and approves the staged result before it replaces the published master.

## Validation and Publishing Gates

A machine master cannot publish unless validation confirms:

- STEP source hash, size, and provenance match the manifest;
- imported solid count matches the assembly-aware import report;
- every source solid maps to exactly one selectable Blender object;
- no duplicate source identifiers exist;
- no unexplained merged bodies exist;
- every product object has an approved material;
- documented multi-material exceptions are explicit;
- shared materials remain linked to the material library;
- branded and machine-specific materials remain local;
- the published collection contains only validated product objects;
- existing render consumers resolve to the expected master revision.

Render validation confirms:

- no locally copied product meshes;
- no unauthorized local product-material replacements;
- dependency paths and revision hashes match;
- source STEP files and machine masters are not mutated during rendering;
- required cameras, lights, animations, and outputs remain scene-local.

A failed audit blocks publication but does not alter or discard the working master.

## Legacy Project Migration and Archive

The current Blender inventory is audited before any destructive action. For each legacy `.blend`, record:

- file path, size, modified time, and hash;
- whether it contains unique product geometry;
- whether it contains a useful camera, lighting setup, or animation;
- known scripts and storefront/render consumers;
- migration destination or archival reason.

Useful cameras, lighting, and animation migrate into linked render scenes. Product geometry and materials are replaced by links to the approved masters. Exact duplicates, backups, failed experiments, and superseded generated targets move into a dated read-only archive only after their consumers and unique content are verified.

Nothing is automatically deleted. Archived files remain recoverable, but they are no longer authoritative or valid render dependencies.

## Initial Deliverables

Implementation produces these independently validated slices:

1. Import and audit tooling with fail-closed separate-solid/provenance tests.
2. Shared physical-material library with an explicit catalog and ownership rules.
3. `PIMM-30G-MASTER.blend` imported from the authoritative 30G STEP and ready for manual material assignment.
4. `PIMM-50G-MASTER.blend` imported from the authoritative 50G STEP and ready for manual material assignment.
5. Material-audit reports and owner workflow documentation.
6. Legacy Blender inventory and migration map.
7. Migration of approved render scenes to linked masters after manual material assignment is complete.
8. Read-only archival of verified superseded projects.

Render migration and storefront asset replacement must not begin until the owner completes or approves the manual material assignments in both masters.

## Out of Scope

- Automatic material guessing as the final authority.
- Destructive deletion of legacy projects.
- Replacing storefront assets before masters and render scenes pass validation.
- Changing CAD geometry, machine specifications, or controller semantics.
- Pushing, deploying, or publishing storefront changes.

## Acceptance Criteria

The implemented system is accepted when:

- the owner can open one master per machine and select every STEP solid independently;
- source identity survives object renaming;
- all unassigned materials are immediately visible and auditable;
- manual assignments cannot be silently replaced by import or render scripts;
- every render scene links one published machine master rather than embedding a private machine copy;
- the material library provides consistent reusable physical finishes;
- legacy Blender projects have an evidence-backed migration or archive disposition;
- all validations pass without mutating the authoritative STEP inputs.
