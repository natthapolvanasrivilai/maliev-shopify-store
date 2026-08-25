# PIMM Published Artwork Contract Design

**Date:** 2026-08-25

**Status:** Pending owner review

**Scope:** Carry the existing pressure-gauge and AirTAC decals from the governed 30G and 50G masters into every linked render scene without changing artwork pixels, UVs, transforms, product geometry, or approved physical-material assignments.

## Problem and root cause

Both governed masters already contain the correct decal objects, materials, packed images, UV mapping, and attachment metadata:

| Machine | Pressure-gauge object | AirTAC object |
| --- | --- | --- |
| 30G | `PIMM30_MASTER_Pressure_Gauge_Face` | `PIMM30_MASTER_AirTAC_Decal` |
| 50G | `PIMM50_MASTER_Pressure_Gauge_Face` | `PIMM50_MASTER_AirTAC_Decal` |

The four objects are render-enabled and belong only to `PIMM_SURFACE_DECALS`. That collection is a sibling of `PIMM_PUBLISHED`, not a child. Static render scenes link only `PIMM_PUBLISHED`, so Blender does not load the decal objects, their two local materials, or their packed image dependencies.

The omission cannot be corrected safely by linking the collection alone. The current `PIMM_PUBLISHED` contract classifies every published mesh as an authoritative STEP-imported mesh with a `pimm_stable_id`, and its evidence must exactly equal the authoritative import manifest. The decals are intentionally machine-local artwork rather than STEP geometry. They have artwork metadata but no STEP stable IDs, and their two local materials do not yet carry governed `pimm_material_id` values. A direct collection link would therefore fail the master-publication and scene-validation gates.

This is a publication-contract gap: master-local artwork is an approved master responsibility, but the published-collection contract currently models only imported geometry.

## Considered approaches

### 1. Separate governed artwork evidence inside `PIMM_PUBLISHED` — selected

Keep the existing STEP stable-ID evidence unchanged and introduce a second evidence class for machine-local artwork. `PIMM_PUBLISHED` contains both imported product meshes and exact approved artwork meshes, while validators classify and verify them independently.

This preserves the authority boundary: STEP IDs remain derived only from the import manifest, and artwork remains owned by the machine master. Every linked consumer receives the complete machine through the existing single-collection interface.

### 2. Give decals synthetic STEP stable IDs — rejected

Adding the decals to the import-manifest identity set would make the current validators easier to satisfy, but it would falsely describe authored artwork as imported CAD geometry. It would also couple artwork revisions to immutable STEP provenance.

### 3. Link `PIMM_SURFACE_DECALS` separately in each render scene — rejected

This would require every still, animation, audit, and future consumer to remember a second master collection. Missing artwork could recur silently, and the scene contract would no longer represent one complete published product. It also weakens the existing rule that renders consume exactly one governed `PIMM_PUBLISHED` collection.

## Authority model

`PIMM_PUBLISHED` remains the only product collection that render scenes consume. Its meshes are divided into two disjoint classes:

1. **Imported product meshes** carry a non-empty `pimm_stable_id`. Their count and canonical digest continue to match the authoritative STEP import manifest exactly.
2. **Published artwork meshes** carry no `pimm_stable_id`. They must satisfy the exact machine-local artwork schema below and must be reachable through `PIMM_PUBLISHED`.

An unclassified mesh, a mesh that satisfies both classes, an unexpected artwork role, or a duplicate identity fails publication and rendering.

The existing collection properties remain geometry-only:

- `pimm_published_stable_id_count`
- `pimm_published_stable_id_sha256`

Two new collection properties govern artwork:

- `pimm_published_artwork_count`
- `pimm_published_artwork_sha256`

The artwork digest is SHA-256 over canonical sorted JSON records. It does not replace the master-file hash; it provides an explicit semantic boundary that validators can independently recalculate.

## Exact artwork contract

Each machine must publish exactly two artwork records:

| Role | Shared asset key | Material ID | Image |
| --- | --- | --- | --- |
| `pressure_gauge_face` | `PIMM_SHARED_PRESSURE_GAUGE_FACE` | `MACHINE_ARTWORK_PRESSURE_GAUGE_FACE` | `assets/pressure-gauge-decal-no-needle.png` |
| `pneumatic_switch_decal` | `PIMM_SHARED_PNEUMATIC_SWITCH_DECAL` | `MACHINE_ARTWORK_AIRTAC_DECAL` | `assets/decal.png` |

Pinned source artwork:

- `pressure-gauge-decal-no-needle.png`: `D1E02A1C703D0C854CA0C610D0EDBBA07E225C51735BB900506C0F2DB779EA39`
- `decal.png`: `30973D1EB16ADBBFC4CBD9C868E1ADB4D8EC96F280B0EDDDAFF7D941DD3E6D15`

Each canonical artwork record includes:

- machine;
- object name;
- object role;
- shared asset key;
- target-parent identity from `pimm_attached_parent`;
- surface-attachment flag;
- mesh datablock name and mesh-content fingerprint;
- material name and exact `pimm_material_id`;
- image name, canonical managed path, source-file SHA-256, packed state, and packed-content fingerprint;
- UV-layer names and active-render UV fingerprint;
- render visibility.

Validators require the existing object and image metadata to agree with this record. The migration may add governance properties and material IDs, but it may not modify object transforms, mesh vertices, polygons, UV coordinates, image pixels, image packing, target attachment metadata, or existing physical product material assignments.

The pressure-gauge artwork must remain the no-needle variant so the physical needle geometry remains visible above it. The AirTAC artwork must retain its existing `ports_right_clockwise` orientation metadata.

## Publication migration

A checked-in Blender mutation script performs a fail-closed migration for each master:

1. Verify the exact input master, artwork file hashes, object names, roles, asset keys, attachment metadata, materials, images, packed state, render visibility, transforms, mesh fingerprints, and UV fingerprints.
2. Verify that neither decal is already reachable through `PIMM_PUBLISHED` and that both are members of `PIMM_SURFACE_DECALS`.
3. Add only the two machine-local material IDs and required published-artwork metadata.
4. Link the existing `PIMM_SURFACE_DECALS` collection beneath `PIMM_PUBLISHED`; do not duplicate or recreate objects or datablocks.
5. Calculate and store the artwork count and canonical digest while retaining the existing STEP stable-ID evidence unchanged.
6. Save a new master, reopen it independently, and run the complete master-publication audit before it replaces the canonical path.

The migration emits structured before/after evidence for every changed property and verifies that protected transforms, mesh fingerprints, UV fingerprints, and image hashes remain identical.

## Validator and contract changes

The master publication audit and render-scene validator will share one artwork-record implementation so producer and consumer cannot drift.

The master audit will:

- require exact STEP stable-ID parity as today;
- require exactly two valid published artwork records;
- require both existing decal objects to be reachable through `PIMM_PUBLISHED`;
- reject artwork remaining outside the published closure, extra artwork, unknown roles, invalid materials, changed image hashes, missing packed data, or changed attachment semantics.

The render-scene validator will:

- classify published meshes as imported geometry or approved artwork;
- continue rejecting scene-local product meshes and materials;
- accept artwork objects, meshes, materials, and images only when they originate from the contracted master and match its exact artwork evidence;
- require machine-local decal materials to carry their exact material IDs;
- reject a render scene that links a master revision where either decal is missing or ungoverned.

Scene contracts continue to reference only `PIMM_PUBLISHED`. Their master SHA-256 values change after the governed master migration; no new consumer collection or optional artwork flag is introduced.

## Test strategy

Tests are written and observed failing before production changes.

Focused pure tests cover:

- canonical artwork-record ordering and digest stability;
- exact role, asset-key, material-ID, image-path, and image-hash requirements;
- rejection of duplicate, missing, extra, ambiguous, or dual-classified meshes.

Blender fixture tests cover:

- a complete master with imported geometry plus two governed artwork meshes passes;
- artwork outside `PIMM_PUBLISHED` fails;
- an unclassified published mesh fails;
- wrong material origin or ID fails;
- wrong image, changed pixels, missing packed content, changed UVs, or changed attachment metadata fails;
- a linked render scene contains both decal objects and both image dependencies;
- linked artwork remains master-owned and cannot be localized or overridden.

Migration tests prove idempotence and assert that only approved governance metadata, collection reachability, and material IDs change. Existing STEP geometry, material assignments, decal geometry, UVs, transforms, and pixels must have identical before/after fingerprints.

The existing static-scene, master-publication, scene-contract, proof-contract, and full relevant test suites run after the focused tests.

## Rendering and review

After both masters pass reopen validation:

1. Archive the superseded masters, still scenes, and their prior hashes with a reversible manifest. Nothing is permanently deleted.
2. Update the 30G and 50G static-scene contracts to the new exact master hashes.
3. Re-author both straight-on still scenes from their governed templates.
4. Reopen and validate each scene.
5. Render targeted high-resolution close-up checks of the pressure regulator and AirTAC face for both machines.
6. Render quick full-machine Cycles checks to ensure the decals do not introduce framing, exposure, or reflection regressions.
7. Publish new immutable white/checker/dark governed proof packages and contact sheets.
8. Verify unchanged protected fingerprints and inspect the published images.

Proof approval does not authorize native finals, storefront derivatives, uploads, pushes, or deployment.

## Rollback and failure handling

Before any canonical `.blend` is replaced, its exact path, SHA-256, byte length, and timestamp are recorded and the file is moved into a dated recoverable archive beneath the governed workspace. The migration stops before canonical replacement if any preflight, saved-file reopen, master audit, scene validation, image check, or protected-fingerprint comparison fails.

If a later scene or proof gate fails, the newly authored assets remain unapproved and the prior masters/scenes can be restored from the archive manifest. No failed output is promoted to finals or storefront consumers.

## Acceptance criteria

- Both existing decal objects—not recreated substitutes—are reachable through each master’s `PIMM_PUBLISHED` collection.
- STEP stable-ID evidence remains exactly equal to the immutable import manifests.
- Each master has exactly two validated artwork records with the pinned source images and material IDs.
- Decal mesh, UV, transform, attachment, packing, and pixel fingerprints are unchanged by migration.
- Fresh 30G and 50G render scenes contain the two linked decals and no private product copies.
- High-resolution close-ups visibly show the pressure-gauge face and AirTAC label in both machines.
- Both new governed proof manifests pass with protected fingerprints unchanged.
- All focused and relevant regression tests pass.
- Superseded files remain recoverable from a hash-recorded archive.
- No native final, storefront replacement, push, or deployment occurs.
