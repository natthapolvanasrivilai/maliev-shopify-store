# PIMM Blender Master Asset System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one editable, assembly-aware Blender master for each PIMM machine, one shared physical-material library, and a non-destructive migration inventory from the authoritative 30G and 50G STEP files.

**Architecture:** A pinned external Python 3.11 CAD environment reads STEP through OpenCascade XCAF, records assembly/product occurrence provenance, and exports one interchange mesh per STEP solid. Blender 5.2 consumes the manifest, creates one object per solid inside assembly collections, assigns an explicit unassigned audit material, and saves editable master files. Validators fail closed on source drift, merged/missing solids, duplicate IDs, unauthorized material state, and legacy inventory omissions.

**Tech Stack:** Python 3.11, `cadquery-ocp==7.9.3.1.1`, OpenCascade XCAF, Blender 5.2 LTS Python API, glTF 2.0 intermediates, Node.js contract tests, Python `unittest`, JSON manifests.

## Global Constraints

- Authoritative 30G source: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\sources\PIMM-30G-authoritative-source.step`, 116,620,371 bytes, SHA-256 `F8AAA223A79B9FE3BB71470818C2E87591C0DECA9A7B0BC8E09AD4DDB0499295`.
- Authoritative 50G source: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\sources\PIMM-50G-authoritative-source.step`, 116,851,157 bytes, SHA-256 `55914B756354C3BDCC522ED439732C9F3F0FBE43F7038A1FFA6045C92ADC1E98`.
- Blender executable: `D:\Blender 5.2\blender.exe`.
- Never mutate either authoritative STEP file.
- Never use OBJ as a canonical machine source.
- Never join imported solids by material, connectivity, name, or proximity.
- Never guess or overwrite final manual material assignments.
- Never delete a legacy Blender project automatically.
- Storefront asset replacement, push, deployment, and production publication are out of scope.
- Preserve unrelated repository and M-drive work.

---

### Task 1: CAD Runtime and Assembly Manifest

**Files:**
- Create: `scripts/blender/master_assets/requirements-step.txt`
- Create: `scripts/blender/master_assets/pimm_step_manifest.py`
- Create: `scripts/blender/master_assets/tests/test_pimm_step_manifest.py`
- Create: `scripts/tests/pimm-master-assets-contract.test.mjs`
- Create externally: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\tools\pimm-cad-py311\`
- Create externally: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\manifests\PIMM-{30G,50G}-import-manifest.json`

**Interfaces:**
- Consumes: `build_manifest(step_path: Path, machine: str, output_dir: Path) -> dict[str, object]`.
- Produces: deterministic JSON containing `source`, `assemblies`, `occurrences`, `solids`, and `summary`; each solid has `stable_id`, `assembly_path`, `product_id`, `occurrence_id`, `solid_index`, `original_name`, `geometry_signature`, and `interchange_path`.

- [ ] **Step 1: Write failing unit and Node contract tests**

```python
def test_stable_id_is_deterministic():
    a = stable_solid_id("30G", "0:1/0:4", "PRODUCT_18", 3)
    b = stable_solid_id("30G", "0:1/0:4", "PRODUCT_18", 3)
    self.assertEqual(a, b)
    self.assertRegex(a, r"^30G-[0-9a-f]{16}$")

def test_source_identity_rejects_hash_drift():
    with self.assertRaisesRegex(ValueError, "source SHA-256 mismatch"):
        validate_source_identity(temp_step, expected_size=4, expected_sha256="0" * 64)
```

The Node contract must assert pinned OCP version, both exact source identities, XCAF APIs, per-solid export, deterministic IDs, and absence of OBJ canonical input.

- [ ] **Step 2: Run tests and record RED**

Run: `py -3.11 -m unittest scripts.blender.master_assets.tests.test_pimm_step_manifest -v`  
Run: `node --test scripts/tests/pimm-master-assets-contract.test.mjs`  
Expected: failure because the runtime contract and manifest module do not exist.

- [ ] **Step 3: Implement the minimal XCAF manifest pipeline**

Create `requirements-step.txt` with exactly:

```text
cadquery-ocp==7.9.3.1.1
```

Implement source hashing, XCAF assembly traversal, occurrence paths, explicit `TopAbs_SOLID` enumeration, deterministic stable IDs, geometry signatures from mass properties/bounds/topology counts, and one `.glb` interchange file per occurrence solid. Refuse duplicate IDs, empty solids, source drift, or an output outside the configured staging directory.

- [ ] **Step 4: Create the isolated CAD runtime and generate both manifests**

Run:

```powershell
py -3.11 -m venv 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\tools\pimm-cad-py311'
& 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\tools\pimm-cad-py311\Scripts\python.exe' -m pip install -r scripts\blender\master_assets\requirements-step.txt
& 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\tools\pimm-cad-py311\Scripts\python.exe' scripts\blender\master_assets\pimm_step_manifest.py --all
```

Expected: both manifests and their per-solid interchange directories are created; source hash/size/mtime readback is unchanged.

- [ ] **Step 5: Run GREEN tests and commit**

Run the Python and Node tests above. Inspect summaries for nonzero assemblies, occurrences, and solids; assert every solid has a unique stable ID and existing interchange file.

Commit only Task 1 files with message: `Build assembly-aware PIMM STEP manifest pipeline`.

---

### Task 2: Shared Physical-Material Library

**Files:**
- Create: `scripts/blender/master_assets/pimm_material_library.py`
- Create: `scripts/blender/master_assets/tests/test_pimm_material_library.py`
- Create externally: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-MATERIAL-LIBRARY.blend`
- Create externally: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\manifests\PIMM-material-library.json`

**Interfaces:**
- Produces: `build_material_library(output_blend: Path, output_manifest: Path) -> dict[str, object]`.
- Material custom properties: `pimm_material_id`, `pimm_material_scope="shared"`, `pimm_material_revision=1`, and `pimm_manual_assignment_allowed=True`.

- [ ] **Step 1: Write failing catalog tests**

Require these exact stable IDs: `UNASSIGNED`, `CNC_MILLED_ALUMINUM`, `DIE_CAST_ALUMINUM`, `SATIN_SHEET_ALUMINUM`, `POLISHED_STAINLESS`, `NICKEL_PLATED_SHAFT`, `BLACK_OXIDE_STEEL`, `BRASS`, `BLACK_POWDERCOAT`, `RUBBER_BLACK`, `PNEUMATIC_TUBE_BLUE`, and `ENGINEERING_PLASTIC`.

Tests assert distinct node groups and physically different roughness/metallic/anisotropy values for CNC, cast, satin sheet, and polished shaft families. `UNASSIGNED` must be magenta, nonmetallic, and unmistakable.

- [ ] **Step 2: Run tests and record RED**

Run: `& 'D:\Blender 5.2\blender.exe' -b --factory-startup -P scripts\blender\master_assets\pimm_material_library.py -- --validate-only`  
Expected: failure because the builder is absent.

- [ ] **Step 3: Implement and save the library**

Create only reusable physical materials. Do not add decals, displays, logos, serial labels, or machine-specific finishes. Add a neutral material-swatch scene for manual review and save the library atomically through a temporary `.blend` followed by verified move.

- [ ] **Step 4: Validate and commit**

Run Blender validate-only, create the external library, reopen it in a fresh Blender process, verify all IDs/properties/node topology, and compare manifest SHA against the saved file.

Commit Task 2 files with message: `Create shared PIMM physical material library`.

---

### Task 3: Editable Machine Master Builder

**Files:**
- Create: `scripts/blender/master_assets/pimm_master_builder.py`
- Create: `scripts/blender/master_assets/tests/test_pimm_master_builder.py`
- Create externally: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-30G-MASTER.blend`
- Create externally: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-50G-MASTER.blend`

**Interfaces:**
- Consumes: Task 1 import manifests and Task 2 material library.
- Produces: `build_master(machine: str, manifest_path: Path, material_library: Path, output_blend: Path) -> dict[str, object]`.
- Object properties: `pimm_stable_id`, `pimm_machine`, `pimm_step_sha256`, `pimm_product_id`, `pimm_occurrence_id`, `pimm_assembly_path`, `pimm_solid_index`, `pimm_original_cad_name`, `pimm_geometry_signature`, `pimm_part_name`, and `pimm_material_state="unassigned"`.

- [ ] **Step 1: Write failing Blender integration tests**

Tests must mutate fixtures to prove rejection of duplicate IDs, two solids joined into one object, missing source properties, a product object without `PIMM_UNASSIGNED`, a render camera in the master, and a material falsely marked approved.

- [ ] **Step 2: Run tests and record RED**

Run: `& 'D:\Blender 5.2\blender.exe' -b --factory-startup -P scripts\blender\master_assets\pimm_master_builder.py -- --validate-only`  
Expected: failure because the builder is absent.

- [ ] **Step 3: Build collection hierarchy and import individual solids**

For each manifest assembly path, create nested `CAD_ASSEMBLY` collections. Import each solid interchange independently, require exactly one mesh result, rename it deterministically, attach all provenance, remove temporary interchange materials, and assign linked `PIMM_UNASSIGNED`. Never call Blender join or merge operators.

- [ ] **Step 4: Add manual-authoring and publishing structure**

Create `WORKING`, `PUBLISHED`, and `AUDIT` collections. `WORKING` contains all imported solids. `PUBLISHED` remains empty and marked blocked while unassigned objects exist. Add a neutral audit scene, object color/status properties, and text-block instructions for searching, renaming through `pimm_part_name`, assigning linked materials, and running validation.

- [ ] **Step 5: Generate both masters and validate immutable sources**

Run the builder separately for 30G and 50G. Reopen each result in a new Blender process and verify object count equals manifest occurrence-solid count, stable IDs are unique, every object is selectable, all start unassigned, no camera/light exists, and source hash/size/mtime are unchanged.

- [ ] **Step 6: Commit**

Commit Task 3 files with message: `Build editable PIMM machine masters from STEP solids`.

---

### Task 4: Master Audit and Manual Material Workflow

**Files:**
- Create: `scripts/blender/master_assets/pimm_master_audit.py`
- Create: `scripts/blender/master_assets/tests/test_pimm_master_audit.py`
- Create: `docs/pimm-blender-master-material-workflow.md`
- Create externally: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\manifests\PIMM-{30G,50G}-material-audit.json`

**Interfaces:**
- Produces: `audit_master(master_path: Path, mode: Literal["working", "publish"]) -> AuditResult`.
- `AuditResult` fields: `source_ok`, `object_count`, `unique_id_count`, `unassigned_ids`, `multi_material_exceptions`, `disconnected_geometry`, `linked_shared_materials`, `local_machine_materials`, `publishable`, and `errors`.

- [ ] **Step 1: Write failing audit tests**

Fixtures prove working mode permits and reports unassigned materials, while publish mode rejects them. Reject shared-material copies made local, branding marked shared, undocumented multiple slots, duplicate source IDs, and unexplained disconnected components.

- [ ] **Step 2: Run RED tests**

Run Python tests and Blender fixture validation; expected failure because audit functions do not exist.

- [ ] **Step 3: Implement audit and owner documentation**

Document exact Blender operations for isolate/search, renaming via `pimm_part_name`, linking shared materials, creating local branded materials, marking a documented multi-material exception, saving, and running working/publish audits. The audit may report geometry anomalies but must never rewrite an assignment.

- [ ] **Step 4: Generate initial reports and validate**

Generate reports for both masters. Expected initial state: source/object/provenance checks pass, all solids appear in `unassigned_ids`, and `publishable` is false. This is a successful handoff state for manual correction, not a failure.

- [ ] **Step 5: Commit**

Commit Task 4 files with message: `Add manual material audit workflow for PIMM masters`.

---

### Task 5: Legacy Blender Inventory and Migration Map

**Files:**
- Create: `scripts/blender/master_assets/pimm_legacy_inventory.py`
- Create: `scripts/blender/master_assets/tests/test_pimm_legacy_inventory.py`
- Create externally: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\manifests\blender-project-inventory.json`
- Create externally: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\manifests\blender-project-migration-report.md`

**Interfaces:**
- Produces: `inventory_projects(root: Path) -> list[ProjectRecord]`.
- `ProjectRecord` contains path, size, mtime, SHA-256, Blender version, scene names, product-object count, camera/light/animation counts, linked libraries, referenced images, likely consumers, duplicate group, and proposed disposition.

- [ ] **Step 1: Write failing classification tests**

Tests require `.blend1` and byte-identical hashes to classify as backup/duplicate; require generated/current consumers to remain `review`; forbid `delete`; and allow only `keep-authoritative`, `migrate-scene`, `archive-after-validation`, or `review` dispositions.

- [ ] **Step 2: Run RED tests**

Run: `py -3.11 -m unittest scripts.blender.master_assets.tests.test_pimm_legacy_inventory -v`  
Expected: failure because inventory code is absent.

- [ ] **Step 3: Implement read-only inventory**

Use filesystem metadata and background Blender inspection without saving source projects. Search repository and M-drive scripts for exact filename consumers. Hash files for duplicate groups. Do not move, rename, chmod, or delete any legacy file.

- [ ] **Step 4: Generate and inspect migration report**

Require every discovered `.blend`/`.blend1` to appear exactly once. Explicitly mark the new masters and material library authoritative; keep every consumer-bearing or unique legacy file in review until render migration occurs after manual material approval.

- [ ] **Step 5: Commit**

Commit Task 5 files with message: `Inventory legacy PIMM Blender projects for migration`.

---

### Task 6: End-to-End Validation and Handoff

**Files:**
- Modify: `scripts/tests/pimm-master-assets-contract.test.mjs`
- Modify: `docs/pimm-blender-master-material-workflow.md`
- Modify: `docs/superpowers/plans/2026-08-14-pimm-blender-master-asset-system.md`

**Interfaces:**
- Consumes every task output.
- Produces a read-only handoff with exact master/library paths, source hashes, object/solid counts, audit status, and legacy inventory summary.

- [ ] **Step 1: Add end-to-end fail-closed assertions**

Assert exact source identity, manifest-to-master object parity, unique stable IDs, separate selectable objects, linked shared-library identity, no cameras/lights in masters, expected initial unassigned state, publish blocking, complete legacy inventory, and zero source/master mutation during audit.

- [ ] **Step 2: Run complete validation**

Run:

```powershell
py -3.11 -m unittest discover -s scripts\blender\master_assets\tests -v
node --test scripts\tests\pimm-master-assets-contract.test.mjs
& 'D:\Blender 5.2\blender.exe' -b 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-30G-MASTER.blend' -P scripts\blender\master_assets\pimm_master_audit.py -- --mode working
& 'D:\Blender 5.2\blender.exe' -b 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-50G-MASTER.blend' -P scripts\blender\master_assets\pimm_master_audit.py -- --mode working
npm run verify
git diff --check
```

Expected: code/tests/theme validation pass; both working audits pass source/provenance/object checks and report `publishable=false` solely because manual material assignments are intentionally incomplete.

- [ ] **Step 3: Visual Blender handoff inspection**

Open each master and verify collection hierarchy, individual object selection, audit material visibility, model completeness, scale/orientation, audit scene usability, and absence of cameras/lights. Confirm the shared material library opens with all catalog swatches.

- [ ] **Step 4: Commit the final validation slice**

Stage only owned plan/test/document changes and commit with message: `Validate PIMM Blender master authoring handoff`.

- [ ] **Step 5: Report the manual handoff boundary**

Report the master paths, exact counts and hashes, commits, validations, and that no legacy file was moved/deleted and no storefront asset was replaced. State clearly that render-scene migration remains intentionally blocked until the owner completes or approves manual material assignments.
