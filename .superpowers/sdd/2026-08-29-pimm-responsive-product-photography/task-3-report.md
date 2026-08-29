# Task 3 report: generalized one-shot scene authoring

## Status

Implemented and committed the repository-owned Task 3 authoring slice in
`d434bb4` (`Author responsive PIMM scenes from campaign contracts`). No external
Blender scenes were created, and no master, material-library, proof, final,
release, storefront, production, push, or deployment state was changed.

## Implemented scope

- Replaced the legacy static-shot registry with exact campaign-derived
  configurations for all 22 governed shots. Camera optics, output dimensions,
  alpha policy, machine scope, purpose, and view continue to come only from
  `campaign_contract.py`.
- Added deterministic non-optical composition records for desktop, tablet,
  mobile, editorial, component-detail, comparison, and workshop shots. The
  records bind complete-product or exact stable-ID targets, normalized subject
  placement, protected-copy rectangles, minimum working distance, camera
  orbit, and studio profile.
- Added responsive camera framing, eye-level full-machine orbits, campaign
  focal lengths, exact managed output paths, and composition evidence.
- Added profile-governed broad lights, three named reflection cards, and a
  finite physical shadow catcher sized beyond the managed camera frustum.
- Added a deterministic two-master comparison link plan: each approved
  `PIMM_PUBLISHED` collection has one unique scene-owned identity-scale
  transform, and both source contact planes resolve to one common floor.
- Added workshop scene-support validation against the approved external-asset
  provenance manifest. Local product-like meshes or materials and unrecorded
  support assets fail closed.
- Extended fresh-reopen validation for exact campaign scope, one managed
  camera, exact lights/cards, no animation, exact Cycles/output/color state,
  exact output path, multiple-master authority, private mesh/material rejection,
  and scene-support ownership.
- Preserved the Task 2 live-foot-contact and published-pixel safety APIs and
  their regression coverage.

## Test-first evidence

- Added `test_shot_compositions.py` first; the initial run failed with
  `ModuleNotFoundError` before `shot_compositions.py` existed.
- Added campaign registry/camera/rig assertions before implementation; the
  legacy six-shot registry failed the new exact-22 expectations.
- Added comparison-link and runtime reopen assertions before their APIs; those
  tests failed until the link-plan and campaign runtime validators existed.

## Validation performed

- `python -m unittest scripts.blender.pimm_production.tests.test_static_product_scene scripts.blender.pimm_production.tests.test_shot_compositions scripts.blender.pimm_production.tests.test_scene_contract -v`
  - PASS: 79 tests in 105.557 seconds.
- `python -m unittest discover -s scripts\blender\pimm_production\tests -v`
  - PARTIAL: 364 tests ran in 534.525 seconds; all Task 3 tests and all
    non-approval modules passed. The existing Task 5 approval/release fixture
    produced 8 failures and 86 errors because its temporary
    `pimm-30g--hero--three-quarter` scene contract differs from the current
    external M-drive contract at the same governed path. The failure path is in
    unchanged `proof_contract.py`, `approval_manifest.py`, and
    `test_approval_release.py`, outside this Task 3 slice.
- `python -m py_compile scripts/blender/pimm_production/blender_static_product_scene.py scripts/blender/pimm_production/blender_scene_template.py scripts/blender/pimm_production/blender_scene_validator.py scripts/blender/pimm_production/shot_compositions.py`
  - PASS.
- `node --test scripts/tests/pimm-blender-production-governance.test.mjs`
  - PARTIAL: 12 passed, 4 failed. Two failures reproduce the same external
    Task 5 scene-contract drift; the others are existing external tool-lock and
    handoff-report hash drift. No failed assertion targets a Task 3 file.
- `npm run verify`
  - PASS: Theme Check completed with only three dependency-template warnings;
    render-asset tests passed 3 with 2 expected environment skips.
- `git diff --check` and `git diff --cached --check`
  - PASS.

## Boundaries inspected

- Exact 22-shot campaign manifest and `campaign_contract.py` producer.
- `SceneContract` single-machine/shared-machine scope and fresh reopen consumer.
- Master collection, material-library, stable-ID, foot-contact, alpha-safety,
  render-state, and external-asset provenance authorities.
- Existing proof/approval governance failures were inspected only; their files
  were not changed because proofs, finals, and release work are outside Task 3.

## Remaining concern

The complete repository governance suite cannot be reported all-green while
the external M-drive hero scene contract and checked-in Task 5 approval fixture
represent different contracts. Task 4 must create and validate the 22 external
`.blend` plus JSON pairs before any proof work; this task deliberately did not
create them.
