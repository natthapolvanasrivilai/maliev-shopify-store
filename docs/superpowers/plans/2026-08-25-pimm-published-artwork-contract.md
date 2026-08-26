# PIMM Published Artwork Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the existing pressure-gauge and AirTAC artwork from both governed PIMM masters into their linked render scenes, then produce verified static renders in which that artwork is present.

**Architecture:** Preserve the current geometry-only stable-ID contract and add a parallel, deterministic artwork evidence contract. The master migration classifies and fingerprints the four existing decal objects without rebuilding them, assigns governed local material IDs, makes `PIMM_SURFACE_DECALS` reachable below `PIMM_PUBLISHED`, and records the artwork count and digest. Scene authoring and validation accept only the exact governed artwork set in addition to authoritative STEP geometry.

**Tech Stack:** Python 3, Blender Python API, `unittest`, PowerShell, Cycles, Git.

**Spec:** `docs/superpowers/specs/2026-08-25-pimm-published-artwork-contract-design.md`

## Global Constraints

- Preserve the existing decal pixels, packed images, UVs, meshes, transforms, attachment identities, and physical-material assignments.
- Add exactly two governed artwork roles per machine: pressure-gauge face and AirTAC label.
- Archive each master and render scene with hashes before replacement; never delete the only prior copy.
- Fail closed on missing, duplicate, ambiguous, dual-classified, or fingerprint-mismatched artwork.
- Do not touch `.material-library-candidate/`, deploy, push, publish to Shopify, or render animation sequences.

---

## Task 1: Add deterministic published-artwork evidence

**Files:**
- Create: `scripts/blender/pimm_production/published_artwork.py`
- Create: `scripts/blender/pimm_production/tests/test_published_artwork.py`
- Modify: `scripts/blender/pimm_production/scene_contract.py`

- [ ] Write failing unit tests for the exact 30G/50G role-to-object, asset-key, parent, material-ID, image-path, and image-SHA contract.
- [ ] Write failing tests for canonical evidence ordering and SHA-256 stability, plus rejection of missing, duplicate, unexpected, and dual-classified records.
- [ ] Run `python -m unittest scripts.blender.pimm_production.tests.test_published_artwork -v`; expect failures because the module and constants do not exist.
- [ ] Implement the pure-Python artwork specifications, property constants, canonical record normalization, evidence digest, and classification validation.
- [ ] Re-run the focused test; expect all tests to pass.
- [ ] Run `python -m unittest scripts.blender.pimm_production.tests.test_scene_contract -v`; expect no regression.

## Task 2: Integrate artwork into master and scene validation

**Files:**
- Modify: `scripts/blender/pimm_production/published_artwork.py`
- Modify: `scripts/blender/pimm_production/blender_scene_template.py`
- Modify: `scripts/blender/pimm_production/blender_scene_validator.py`
- Modify: `scripts/blender/master_assets/pimm_master_audit.py`
- Modify: `scripts/blender/pimm_production/tests/test_scene_contract.py`
- Modify: `scripts/blender/pimm_production/tests/test_published_artwork.py`

- [ ] Add failing Blender fixture tests proving that an artwork mesh without a STEP stable ID is accepted only when all governed artwork metadata and fingerprints match.
- [ ] Add failing tests proving unclassified meshes, missing artwork, duplicate roles, wrong parent identities, wrong image bytes, and stale artwork evidence are rejected.
- [ ] Run the focused Blender-backed scene-contract tests and capture the expected failures.
- [ ] Implement Blender capture helpers for mesh, UV, material, image, packing, attachment, visibility, and collection reachability fingerprints.
- [ ] Extend master audit and render-scene validation to compare geometry and artwork as disjoint evidence sets.
- [ ] Re-run focused tests and the complete `scripts/blender/pimm_production/tests` suite; expect all tests to pass.

## Task 3: Add an idempotent master-artwork migration

**Files:**
- Create: `scripts/blender/master_assets/blender_publish_master_artwork.py`
- Modify: `scripts/blender/pimm_production/tests/test_published_artwork.py`

- [ ] Add a failing fixture test for an unpublished but otherwise valid existing artwork collection.
- [ ] Assert migration preserves protected before/after fingerprints while adding only governance properties, the two material IDs, collection reachability, and collection evidence.
- [ ] Implement a CLI migration that validates the expected source hash, exact machine contract, packed asset bytes, and attachment identities before saving to a requested output path.
- [ ] Make the migration idempotent and fail closed if any protected field changes.
- [ ] Re-run focused tests and lint/compile checks.
- [ ] Commit the validated contract and migration code as `Govern published artwork in PIMM master links`.

## Task 4: Archive and migrate both governed masters

**External files:**
- Archive and replace: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-30G-MASTER.blend`
- Archive and replace: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-50G-MASTER.blend`
- Preserve dependency: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-MATERIAL-LIBRARY.blend`

- [ ] Create a timestamped archive with original paths, sizes, UTC timestamps, and SHA-256 hashes; verify the archived bytes before replacement.
- [ ] Migrate 30G and 50G from the archived originals to canonical master paths.
- [ ] Reopen each canonical master in Blender and run the master publication audit.
- [ ] Verify exactly 554 authoritative geometry objects plus exactly two governed artwork objects per machine, with unchanged geometry stable-ID evidence.
- [ ] Verify the two packed image hashes and protected artwork fingerprints match the archived masters.

## Task 5: Rebuild linked render scenes and render visual verification

**External files:**
- Archive and replace the governed 30G and 50G static-front `.blend` scenes and scene-contract JSON master hashes.
- Create verification renders under each scene's governed proof/output area.

- [ ] Archive current render scenes and record their hashes.
- [ ] Update only the expected master hashes in each external scene contract.
- [ ] Re-author both scenes from their templates so `PIMM_PUBLISHED` links the artwork transitively.
- [ ] Validate both reopened scenes against the extended geometry and artwork contract.
- [ ] Render four high-resolution crops from the linked production scenes: 30G/50G pressure gauge and 30G/50G AirTAC label.
- [ ] Render one quick full-frame static hero per machine using the approved 85 mm camera, HDRI strength 0.5/rotation 0, and existing light rig.
- [ ] Visually inspect the crops for legibility, correct orientation, and attachment, and inspect full frames for lighting/framing regressions.

## Task 6: Publish governed local proof bundles

**External outputs:**
- New immutable proof bundle for 30G.
- New immutable proof bundle for 50G.

- [ ] Run the governed proof renderer for each rebuilt scene.
- [ ] Verify each proof manifest, image hashes, source/master/material-library hashes, pre/post scene fingerprints, and contact sheet.
- [ ] Confirm the proof manifest records both governed artwork roles and packed image fingerprints.
- [ ] Run final repository tests and `git diff --check`.
- [ ] Commit any remaining repository documentation or contract fixture updates in a coherent validated commit.
- [ ] Report hashes, render paths, proof paths, commands/results, and explicitly confirm that no production deployment or push occurred.
