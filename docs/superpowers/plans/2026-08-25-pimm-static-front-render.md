# PIMM Static Front Render Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Govern and render dedicated straight-on static hero proofs for the PIMM 30G and 50G without starting animation work or changing the storefront.

**Architecture:** Canonical repository documentation controls the external Blender workspace. A checked-in Blender authoring module creates one linked still-shot scene per machine from the published masters, with deterministic camera and studio-light configuration; immutable proof contracts then render review evidence.

**Tech Stack:** Blender 5.2 Python API, Cycles, Python `unittest`, repository PIMM proof and scene contracts.

**Spec:** `docs/superpowers/specs/2026-08-25-pimm-static-front-render-design.md`

## Global Constraints

- Do not create or modify animation rigs, actions, drivers, controller-value animation, or operating sequences.
- Do not modify published master geometry, approved material assignments, labels, displays, or stable identities.
- Do not render native finals or replace, upload, deploy, push, or merge storefront assets.
- Proofs must use the same authored camera, lights, world, and compositor intended for finals.
- Preserve unrelated work and the untracked `.material-library-candidate/` directory.

---

### Task 1: Canonical Blender workspace guidance

**Files:**
- Modify: `docs/pimm-blender-governance/AGENTS.md`
- Modify: `scripts/blender/pimm_production/tests/test_workspace_docs.py`

**Interfaces:**
- Consumes: `install_workspace_docs(repo_root, workspace_root)` and canonical documentation mapping.
- Produces: an external `AGENTS.md` with hash parity and explicit static/animation ownership boundaries.

- [ ] Write assertions for the required `scenes/stills`, `scenes/animations`, `rigs`, proof/final ownership, and animation-blocking language.
- [ ] Run the focused test and confirm it fails because the new guidance is absent.
- [ ] Add the smallest complete ownership and naming rules to canonical `AGENTS.md`.
- [ ] Run the focused workspace-document tests and confirm they pass.
- [ ] Install the canonical documents into the external workspace and verify hash parity.
- [ ] Commit the guidance slice with only its repository files.

### Task 2: Deterministic front static-scene authoring

**Files:**
- Create: `scripts/blender/pimm_production/blender_static_hero_scene.py`
- Create: `scripts/blender/pimm_production/tests/test_static_hero_scene.py`

**Interfaces:**
- Consumes: a source linked scene, machine code, scene ID, destination path, and verified product bounds.
- Produces: `author_front_scene(bpy, machine, source_path, destination_path) -> dict[str, object]` and a saved linked `.blend` with `CAM_HERO` plus deterministic studio lights.

- [ ] Write tests for the machine configuration, exact front-axis camera rule, pitch ceiling, managed scene identity, and lighting-energy hierarchy.
- [ ] Run the focused tests and confirm they fail because the authoring module is absent.
- [ ] Implement the pure configuration and geometry calculations, then the Blender authoring entrypoint.
- [ ] Run focused tests and confirm they pass.
- [ ] Run syntax and diff checks.
- [ ] Commit the scene-authoring slice.

### Task 3: Build and validate dedicated still scenes

**Files:**
- Create externally: `scenes/stills/pimm-30g--hero--front.blend`
- Create externally: `scenes/stills/pimm-50g--hero--front.blend`
- Create externally: `scenes/contracts/pimm-30g--hero--front.json`
- Create externally: `scenes/contracts/pimm-50g--hero--front.json`

**Interfaces:**
- Consumes: published 30G/50G masters, shared material library, and Task 2 authoring entrypoint.
- Produces: two reopenable linked static scenes and matching scene contracts.

- [ ] Back up any pre-existing exact destination files before mutation.
- [ ] Run Blender authoring for 30G and 50G.
- [ ] Reopen each saved scene and inspect camera, lights, links, render settings, and product bounds.
- [ ] Generate scene contracts with current master, material-library, and scene hashes.
- [ ] Run the scene validator against both contracts and require zero errors.

### Task 4: Render immutable static proofs

**Files:**
- Create externally: `renders/proofs/<30g-proof-id>/`
- Create externally: `renders/proofs/<50g-proof-id>/`

**Interfaces:**
- Consumes: validated Task 3 scene files and contracts.
- Produces: pass-labelled contact sheets and manifests with unchanged fingerprints.

- [ ] Create unique composition proof contracts at 12.5 percent resolution, 16 samples, denoising enabled, and white/checker/dark backgrounds.
- [ ] Render both proof contracts through the governed Blender proof runner.
- [ ] Verify both manifests report `status=pass` and `fingerprints_unchanged=true`.
- [ ] Inspect both contact sheets for straight-on alignment, complete framing, black-part separation, controller visibility, and balanced exposure.
- [ ] Remove temporary proof-contract helpers and report exact proof IDs, hashes, paths, and any remaining gate.
