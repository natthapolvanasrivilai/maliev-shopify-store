# PIMM Blender Production Governance Design

**Date:** 2026-08-15

**Status:** Approved design

**Scope:** PIMM 30G and 50G Blender masters, linked render scenes, materials, animation, render approval, BlenderMCP operation, and legacy-asset cleanup

## Objective

Create a free-tools-only, reproducible Blender production system for the PIMM 30G and 50G machines. The system must improve realism without allowing AI or render tooling to alter authoritative product geometry, artwork, material semantics, controller values, or machine behavior.

The project will establish:

- one authoritative geometry and material master for each machine;
- one shared physical-material library;
- linked render scenes that contain no private product copies;
- a dedicated Blender-project `AGENTS.md` for human and AI operation;
- documented machine, controller, material, lighting, animation, and file-management rules;
- low-cost proof renders and owner contact-sheet approval before native rendering;
- deterministic release manifests and consumer paths;
- evidence-backed migration of obsolete projects and renders into an external pending-delete archive;
- BlenderMCP as the preferred interactive control surface, backed by repeatable checked-in scripts.

## Constraints

1. Only free tools may be used. Paid add-ons, subscriptions, cloud render enhancement, and paid or cloud AI services are prohibited.
2. Final product pixels may not be generatively repainted, upscaled, or materially altered by AI.
3. Authoritative STEP sources, product meshes, approved manual material assignments, decals, and machine semantics must remain unchanged by render automation.
4. No deprecated asset is permanently deleted during this implementation. Verified deprecated assets move first into a read-only, dated pending-delete archive outside the active workspace.
5. A native-resolution render may run only after its exact proof generation is approved by the owner.
6. Stale experiments, `.blend1` recovery files, temporary masks, and rejected proof generations may not remain in active consumer paths.
7. Render consumers may resolve only an explicit approved release manifest, never an ambiguous filename or latest-directory convention.

## Current State

The current authoritative masters are:

- `masters/PIMM-30G-MASTER.blend`;
- `masters/PIMM-50G-MASTER.blend`;
- `masters/PIMM-MATERIAL-LIBRARY.blend`.

Each machine master currently contains 478 independently selectable STEP solids and uses Metric/Millimeters with `scene.unit_settings.scale_length=0.001`. Imported product objects carry the documented `0.01` source-to-Blender scale and stable STEP provenance.

The active external workspace still contains numerous superseded `.blend`, `.blend1`, and render-generation directories. Its existing root README describes the obsolete OBJ/meters workflow and must be replaced. The last inventory accounts for 77 Blender projects, but its master hashes predate the latest STEP rebuild; it is evidence only and must be regenerated before migration.

The locally installed BlenderMCP connection is operational and can inspect the open Blender scene. Its local installation is free software. BlenderMCP is an interface to Blender, not a substitute for scripts, manifests, or saved-file validation.

## Tool Policy

### Approved baseline

- Blender 5.2 or the explicitly locked compatible version;
- Cycles;
- AgX color management;
- OpenImageDenoise;
- Blender compositor and render passes;
- Blender Python and Python standard library;
- OpenImageIO when supplied locally under a compatible free license;
- the locally installed free BlenderMCP implementation;
- locally authored procedural textures, studio light fields, and reflection cards;
- reference images owned by MALIEV or carrying a recorded compatible license.

Every external tool or asset used in production must appear in `manifests/free-tools-lock.json` with its version, source, license, and local checksum where applicable.

### Prohibited baseline

- paid Blender add-ons;
- paid texture or HDRI generators;
- subscription tools;
- cloud AI processing;
- cloud render enhancers;
- generative repainting of final product renders;
- AI-created controller digits, decals, labels, geometry, or machine parts;
- unlicensed textures, HDRIs, fonts, or artwork.

The AI tools listed in the supplied research are not adopted wholesale. Realism will come from physically meaningful materials, controlled reflection geometry, calibrated exposure, correct camera behavior, adequate sampling, and reference-based validation.

## Target Workspace Architecture

```text
blender-product-renders/
├── AGENTS.md
├── README.md
├── sources/
│   ├── cad/
│   ├── references/
│   └── artwork/
├── masters/
│   ├── PIMM-30G-MASTER.blend
│   ├── PIMM-50G-MASTER.blend
│   └── PIMM-MATERIAL-LIBRARY.blend
├── scenes/
│   ├── 30g/
│   ├── 50g/
│   └── shared-templates/
├── renders/
│   ├── proofs/<generation-id>/
│   ├── approved/<release-id>/
│   └── final/<release-id>/
├── manifests/
│   ├── sources/
│   ├── scenes/
│   ├── approvals/
│   └── releases/
├── scripts/
├── tools/
└── docs/
    ├── machine-operation-30g.md
    ├── machine-operation-50g.md
    ├── material-authoring.md
    ├── lighting-and-cameras.md
    ├── animation-rigging.md
    └── rendering-and-approval.md

blender-product-renders-archive/
└── pending-delete/<date>-<batch-id>/
```

The source-controlled Shopify repository owns the canonical instructions, validators, and Blender Python scripts. The canonical workspace documents live at `docs/pimm-blender-governance/AGENTS.md` and `docs/pimm-blender-governance/README.md`. An installation/check command places them at `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\AGENTS.md` and `README.md`, then verifies their hashes. This prevents the external documentation from silently drifting away from the tested workflow.

## Ownership Boundaries

### Machine masters

Machine masters own:

- authoritative imported geometry;
- assembly collections and stable object identity;
- owner-maintained `pimm_part_name` values;
- approved product material assignments;
- machine-local artwork, decals, display materials, and labels;
- documented neutral transforms;
- the validated `PIMM_PUBLISHED` collection.

Machine masters do not own marketing cameras, shot-specific lights, shadow catchers, or storefront animation timelines.

### Shared material library

`PIMM-MATERIAL-LIBRARY.blend` owns reusable physical finishes. Linked shared materials must not be made local in a machine master or render scene. Machine-specific branding, serial labels, and controller artwork remain local to the applicable machine master.

Manual material assignments are authoritative. AI may inspect, report, or suggest, but it may not overwrite an approved assignment.

### Render scenes

Render scenes link the applicable master’s `PIMM_PUBLISHED` collection. They may own:

- cameras and framing;
- physical lights and reflection cards;
- physical shadow catchers and compositor nodes;
- approved animation controls and scene-local rigs;
- render layers, passes, output formats, and output paths.

A render scene fails validation if it embeds a private machine mesh, makes a linked product material local, overrides an approved product material, or links an unapproved master revision.

## Dedicated AGENTS.md Contract

The Blender-project `AGENTS.md` establishes this authority order:

1. immutable STEP sources and import manifests;
2. owner-approved machine and material documentation;
3. published 30G or 50G master;
4. shared material library;
5. scene contract and approval manifest;
6. checked-in render scripts;
7. ad-hoc AI instructions.

When two sources conflict, the higher authority wins. Missing or ambiguous machine behavior blocks work rather than authorizing a guess.

The file will contain explicit instructions for:

- opening and inspecting master and render files;
- identifying objects through stable IDs and CAD provenance;
- assigning shared and machine-local materials;
- configuring controller displays;
- creating and validating linked scenes;
- using BlenderMCP safely;
- running proof, approval, final, and release workflows;
- moving deprecated files through the pending-delete archive;
- preserving the active user session and unrelated Blender processes;
- reporting validation evidence before completion.

## Machine and Controller Semantics

Separate operation documents define the 30G and 50G machines. Each document records:

- product specifications relevant to rendering;
- neutral machine pose;
- named movable assemblies;
- permitted axes, limits, and endpoint transforms;
- operating sequence and frame-state expectations;
- mold, platen, injection, pneumatic, and controller relationships;
- hose and cable behavior;
- prohibited impossible motion;
- owner-approved reference images or diagrams.

Unknown mechanics remain explicitly blocked until the owner supplies or approves the missing information.

Controller rules are fail-closed:

- the 30G renders physical seven-segment values `300/300`;
- the 50G renders physical seven-segment values `350/350`;
- illuminated segments use the appropriate green or red emissive material;
- inactive segment geometry remains physically present;
- flat text, font objects, composited text, or image overlays may not replace the controller geometry;
- digit arrangement, perspective, occlusion, and controller housing geometry must remain authentic.

## Material Realism Standard

Material validation distinguishes at least:

- CNC-milled aluminum;
- die-cast aluminum;
- satin aluminum extrusion;
- brushed stainless hairline;
- polished and nickel-plated shafts;
- satin and stainless fasteners;
- steel, black oxide, and heat-oxidized steel;
- powder-coated steel, including pink powder coat;
- brass;
- rubber and pneumatic tubing;
- nylon PA6, PEEK, and 0.2 mm-layer ASA;
- white textile and steel-braided cables;
- transparent and emissive controls.

Procedural microstructure must be physically plausible at product scale. Materials are evaluated under a neutral audit rig and in the approved studio rig. The tests must detect broad clipped highlights, crushed shadows, missing roughness separation, black shaft troughs, flat cast surfaces, over-matte CNC faces, and inappropriate identical treatment of distinct materials.

## Lighting, Camera, and Alpha Standard

The standard product presentation is a clean white studio with controlled, physically meaningful reflections. It uses:

- broad area lights and studio-card gradients;
- reflection cards that shape polished cylinders without washing broad aluminum faces;
- calibrated world contribution;
- AgX highlight rolloff;
- an effectively infinite physical Cycles shadow catcher;
- transparent RGBA output with a soft, complete, light ground shadow;
- camera contracts that preserve full-product and intended-feature framing.

Image-space painted shadows, radial fake masks, clipped finite catcher planes, and arbitrary exposure compensation are prohibited. White, checker, and dark composites must show no catcher boundary, cropped shadow tail, dark contact bar, or lost product silhouette.

## BlenderMCP Operating Rules

Before modifying a connected Blender session, an agent must inspect:

- file path;
- dirty state;
- active scene and view layer;
- unit settings;
- library links;
- current selection and active object;
- relevant object, material, and collection identities.

BlenderMCP defaults to read-only inspection. It may be used for scene exploration, object selection, structured diagnostics, screenshots, and controlled execution of checked-in scripts.

It must not:

- overwrite a master without explicit authorization;
- publish a collection automatically;
- delete datablocks or files without the approved cleanup manifest;
- terminate unrelated Blender processes;
- assume names, materials, transforms, or values without inspection;
- treat a successful save call as validation.

Repeatable mutations belong in checked-in Blender Python. Every saved `.blend` is reopened and validated independently. Structured results identify changed datablocks, stable object IDs, material IDs, output files, and before/after source hashes.

## Render and Approval Pipeline

### Gate 0: preflight

Preflight verifies:

- STEP and master identity;
- material-library revision;
- scene dependencies;
- linked geometry and materials;
- units and scale;
- controller values;
- animation endpoint contracts;
- output path and generation ID;
- absence of forbidden paid or cloud dependencies.

Any failure blocks rendering.

### Gate 1: composition proof

The first proof uses:

- 12.5–25% contracted output resolution;
- 16–32 Cycles samples;
- denoising;
- white, checker, and dark composites.

It validates framing, crop intent, alpha clearance, ground-shadow containment, camera angle, major reflections, and broad exposure.

### Gate 2: material and lighting proof

The material proof normally uses:

- 25% resolution;
- 32–64 Cycles samples;
- object and material masks;
- targeted detail crops;
- quantitative highlight, shadow, shaft, material-separation, and alpha tests.

The output is a labelled contact sheet. Individual shots can be approved, rejected, or annotated within the batch.

### Gate 3: owner approval

Approval records:

- proof and contact-sheet hashes;
- source STEP hash;
- master and material-library revisions;
- scene and script revisions;
- render settings;
- decision, notes, owner, and timestamp.

Changing geometry, material, camera, light, world, compositor, animation, output size, or render settings invalidates the approval.

### Gate 4: native final render

Only an approved shot may render at contracted native resolution. The default final setup is:

- Cycles adaptive sampling;
- 128–256 maximum samples unless a tested shot contract requires otherwise;
- float EXR master;
- transparent PNG, WebP, or video deliverables as required;
- exact approved composition and material state.

AI upscaling, cloud enhancement, generative texture replacement, and post-render product repainting remain prohibited.

### Gate 5: release QA

Release validation includes:

- original-resolution visual inspection;
- white, checker, and dark composites;
- controller-value verification;
- exact output dimensions and alpha mode;
- shadow containment and edge continuity;
- static/poster/animation endpoint parity;
- output and provenance hashes;
- storefront consumer filename and format checks.

Only a complete approved release may enter the final consumer directory.

## Naming and Generation Rules

Stable scene filename:

`pimm-30g--hero--three-quarter.blend`

Proof generation:

`proof-20260815T153000Z-a1b2c3d/`

Proof outputs:

- `pimm-30g--hero--three-quarter--white.png`;
- `pimm-30g--hero--three-quarter--checker.png`;
- `pimm-30g--hero--three-quarter--dark.png`.

Final release:

`release-2026-08-15-r01/`

Animation frame:

`pimm-50g--operation-cycle--desktop--frame-0001.exr`

Names such as `final-final`, `new`, `fixed`, `copy`, or an unexplained version suffix are prohibited. Revisions live in source control and manifests. Output directories are immutable after approval.

## Consumer Boundary

Storefront code and downstream render consumers resolve only a release manifest. The manifest maps a stable logical asset ID to an exact immutable file, hash, dimensions, alpha contract, and release ID.

Rejected, proof, archived, temporary, and unmanifested outputs are invalid consumers. A release is atomic: consumers cannot mix outputs from different generations.

## Cleanup and Pending-Delete Archive

Cleanup begins with a fresh inventory because the existing 77-project report contains obsolete master fingerprints.

For every `.blend`, `.blend1`, render directory, script, texture, image, and video, the inventory records:

- absolute and relative path;
- SHA-256, byte length, and modification time;
- project/scenes and unique content summary;
- source, master, material, image, and script dependencies;
- known storefront and render consumers;
- replacement or migration target;
- disposition and rationale.

The allowed dispositions are:

- authoritative;
- active-linked-scene;
- migrate;
- pending-archive;
- unresolved.

Before moving a deprecated item:

1. prove it is not authoritative;
2. prove it is not an active consumer dependency;
3. migrate and validate any unique camera, rig, animation, light, or compositor content;
4. compare replacement proof output where visual equivalence matters;
5. create the archive manifest and restore mapping;
6. obtain owner approval for the move batch.

Approved items move to a sibling archive outside the active workspace:

`M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders-archive\pending-delete\<date>-<batch-id>\`

The move preserves relative paths, hashes, sizes, and timestamps. After the move, dependency scans, scene validation, proof contracts, and storefront-consumer tests rerun. The archive is read-only and excluded from all active searches and consumers.

No item is permanently deleted in this implementation phase. Deletion requires a later explicit owner-approved batch.

`.blend1`, temporary masks, failed proofs, and abandoned generations may exist during work but must leave active consumer paths before release. Recoverable copies follow the same archive procedure.

## Error Handling and Fail-Closed Behavior

The system stops before mutation or rendering when it encounters:

- changed source hash;
- missing or stale master link;
- local product copy;
- unauthorized material override;
- unapproved material state;
- wrong controller value;
- unknown animation transform;
- missing artwork or license provenance;
- unmanaged output path;
- stale approval;
- active consumer of an archive candidate;
- incomplete archive manifest;
- paid or cloud dependency.

A failure report identifies the exact file, object, stable ID, material, scene, frame, consumer, or manifest field. Validation never silently repairs product data.

## Validation Strategy

The implementation will add focused tests for:

- external `AGENTS.md` and README parity with their source-controlled canonical files;
- free-tools lock and prohibited dependency detection;
- machine/controller semantic contracts;
- linked master/material ownership;
- scene naming and output lifecycle;
- proof settings and contact-sheet generation;
- approval invalidation;
- final-render authorization;
- release atomicity and consumer mappings;
- full inventory accounting;
- archive manifest completeness and reversible moves;
- no active dependency on archived or rejected assets;
- BlenderMCP read-before-write and saved-file reopen validation.

Tests must fail against the current unmanaged state before the production workflow is changed.

## Implementation Slices

1. Canonical governance documents, external `AGENTS.md`/README installer, and parity tests.
2. Machine-operation, material, lighting, animation, and approval manuals.
3. Free-tools lock and BlenderMCP preflight/structured-inspection scripts.
4. Linked render-scene templates and dependency validators.
5. Proof render, quantitative QA, contact-sheet, and approval-manifest pipeline.
6. Native final render and atomic release-manifest pipeline.
7. Fresh complete legacy inventory and consumer graph.
8. Owner-reviewed migration and first move-only pending-delete archive batch.
9. Storefront consumers migrated only to a fully approved release.

Each slice is independently validated and committed. Native rendering, file movement, and storefront changes remain separately authorized boundaries.

## Out of Scope

- permanent deletion of archived files;
- paid or cloud tooling;
- automatic final material assignment;
- modification of authoritative STEP geometry;
- invented machine behavior;
- deployment or publication of storefront changes;
- generative modification of final product pixels.

## Acceptance Criteria

The production-governance implementation is accepted when:

- the external Blender workspace contains the validated dedicated `AGENTS.md` and current README;
- only the two machine masters and shared material library own product geometry/material authority;
- render scenes link masters and contain no private machine copies;
- free-tool and license rules are machine-verifiable;
- 30G and 50G controller and operation semantics are documented and tested;
- every proof generation is isolated and produces owner-review contact sheets;
- native rendering is impossible without a matching approval record;
- every final output belongs to one atomic release manifest;
- consumers cannot resolve proof, rejected, stale, or archived outputs;
- the fresh inventory accounts for every legacy project and render generation;
- the first approved deprecated batch is moved reversibly into the external pending-delete archive;
- no file is permanently deleted;
- all repository, Blender, manifest, audit, and consumer tests pass.
