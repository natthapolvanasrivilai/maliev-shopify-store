# PIMM Blender Production Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a free-tools-only, fail-closed Blender production workflow with authoritative machine semantics, safe BlenderMCP operation, linked render scenes, low-resolution contact-sheet approval, immutable final releases, and reversible archival of deprecated PIMM assets.

**Architecture:** The Shopify repository owns canonical governance documents, machine/tool contracts, Blender Python validators, proof/release tooling, and archive logic. The external Blender workspace receives hash-verified copies of its `AGENTS.md` and README, while machine masters retain geometry/material authority and render scenes link only approved `PIMM_PUBLISHED` collections. Proof, approval, final-render, release, consumer, and archive manifests form an immutable chain; any source or scene drift fails closed.

**Design specification:** [`docs/superpowers/specs/2026-08-15-pimm-blender-production-governance-design.md`](../specs/2026-08-15-pimm-blender-production-governance-design.md)

**Tech Stack:** Blender 5.2 using the installed production executable, Cycles, AgX, OpenImageDenoise, Blender Python API, local LGPL BlenderMCP, Python 3.11, Pillow 12.2.0 for contact sheets, Python `unittest`, Node.js contract tests, JSON manifests, SHA-256.

## Global Constraints

- Active Blender root: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders`.
- Pending-delete archive root: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders-archive\pending-delete`.
- Authoritative 30G master: `masters\PIMM-30G-MASTER.blend`.
- Authoritative 50G master: `masters\PIMM-50G-MASTER.blend`.
- Shared material library: `masters\PIMM-MATERIAL-LIBRARY.blend`.
- Blender executable: `D:\Blender 5.2\blender.exe`.
- 30G controllers show physical seven-segment `300/300`; 50G controllers show physical seven-segment `350/350`.
- Only free tools and compatibly licensed local assets may enter the workflow.
- Paid add-ons, subscriptions, cloud AI, cloud render enhancement, AI upscaling, and generative repainting of final product pixels are prohibited.
- Never mutate authoritative STEP sources through render, audit, proof, inventory, or archive commands.
- Never overwrite an approved manual material assignment.
- Never embed a private machine copy or localize linked product materials in a render scene.
- Never render native finals without a current owner approval manifest.
- Never let storefront consumers reference proof, rejected, temporary, archived, or mixed-generation assets.
- Move deprecated files only after exact consumer and unique-content validation; preserve paths, hashes, sizes, and timestamps.
- Do not permanently delete any file in this implementation.
- Preserve unrelated repository changes and the user’s active Blender process.
- Render-scene migration and native proof production remain blocked until the applicable master passes publish audit and the owner approves its manual material assignments.

## File Map

### Canonical documents and contracts

- Create: `docs/pimm-blender-governance/AGENTS.md` — AI/human operating authority and prohibited actions.
- Create: `docs/pimm-blender-governance/README.md` — current workspace entry point.
- Create: `docs/pimm-blender-governance/machine-operation-30g.md` — 30G semantics and explicit animation block state.
- Create: `docs/pimm-blender-governance/machine-operation-50g.md` — 50G semantics and explicit animation block state.
- Create: `docs/pimm-blender-governance/material-authoring.md` — shared/local material workflow and realism checks.
- Create: `docs/pimm-blender-governance/lighting-and-cameras.md` — studio, reflection, alpha, and framing rules.
- Create: `docs/pimm-blender-governance/animation-rigging.md` — named-control and endpoint rules.
- Create: `docs/pimm-blender-governance/rendering-and-approval.md` — proof/contact-sheet/final/release lifecycle.
- Create: `scripts/blender/pimm_production/contracts/machines/30g.json`.
- Create: `scripts/blender/pimm_production/contracts/machines/50g.json`.
- Create: `scripts/blender/pimm_production/requirements-production.txt`.

### Production Python package

- Create: `scripts/blender/pimm_production/__init__.py`.
- Create: `scripts/blender/pimm_production/paths.py` — canonical roots and path-boundary guards.
- Create: `scripts/blender/pimm_production/io_contract.py` — hashing and atomic JSON/text operations.
- Create: `scripts/blender/pimm_production/workspace_docs.py` — external documentation installation/parity.
- Create: `scripts/blender/pimm_production/tool_policy.py` — free-tool discovery and lock validation.
- Create: `scripts/blender/pimm_production/machine_contract.py` — machine/controller contract schema.
- Create: `scripts/blender/pimm_production/blender_session_preflight.py` — MCP/CLI scene inspection.
- Create: `scripts/blender/pimm_production/scene_contract.py` — linked render-scene schema.
- Create: `scripts/blender/pimm_production/blender_scene_validator.py` — open-scene ownership validation.
- Create: `scripts/blender/pimm_production/blender_scene_template.py` — linked-scene template builder.
- Create: `scripts/blender/pimm_production/proof_contract.py` — proof settings and manifest schema.
- Create: `scripts/blender/pimm_production/blender_proof_render.py` — low-resolution render runner.
- Create: `scripts/blender/pimm_production/contact_sheet.py` — labelled proof contact sheets.
- Create: `scripts/blender/pimm_production/approval_manifest.py` — owner decision and invalidation.
- Create: `scripts/blender/pimm_production/blender_final_render.py` — approval-gated native render.
- Create: `scripts/blender/pimm_production/release_manifest.py` — atomic immutable release manifest.
- Modify: `scripts/blender/master_assets/pimm_legacy_inventory.py` — schema-v2 dependency inventory.
- Create: `scripts/blender/pimm_production/archive_plan.py` — reversible move planning and application.

### Tests

- Create: `scripts/blender/pimm_production/tests/__init__.py`.
- Create: `scripts/blender/pimm_production/tests/test_workspace_docs.py`.
- Create: `scripts/blender/pimm_production/tests/test_tool_policy.py`.
- Create: `scripts/blender/pimm_production/tests/test_machine_contract.py`.
- Create: `scripts/blender/pimm_production/tests/test_scene_contract.py`.
- Create: `scripts/blender/pimm_production/tests/test_proof_contract.py`.
- Create: `scripts/blender/pimm_production/tests/test_approval_release.py`.
- Create: `scripts/blender/pimm_production/tests/test_archive_plan.py`.
- Create: `scripts/blender/pimm_production/tests/test_consumer_graph.py`.
- Modify: `scripts/blender/master_assets/tests/test_pimm_legacy_inventory.py`.
- Create: `scripts/tests/pimm-blender-production-governance.test.mjs`.
- Modify: `.gitignore` — ignore Python caches without deleting unrelated user data.

---

### Task 1: Canonical Governance Documents and External Parity

**Files:**
- Create: `docs/pimm-blender-governance/AGENTS.md`
- Create: `docs/pimm-blender-governance/README.md`
- Create: `docs/pimm-blender-governance/material-authoring.md`
- Create: `docs/pimm-blender-governance/lighting-and-cameras.md`
- Create: `docs/pimm-blender-governance/animation-rigging.md`
- Create: `docs/pimm-blender-governance/rendering-and-approval.md`
- Create: `scripts/blender/pimm_production/__init__.py`
- Create: `scripts/blender/pimm_production/paths.py`
- Create: `scripts/blender/pimm_production/io_contract.py`
- Create: `scripts/blender/pimm_production/workspace_docs.py`
- Create: `scripts/blender/pimm_production/tests/__init__.py`
- Create: `scripts/blender/pimm_production/tests/test_workspace_docs.py`
- Create: `scripts/tests/pimm-blender-production-governance.test.mjs`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `sha256_file(path: Path) -> str`.
- Produces: `atomic_write_json(path: Path, payload: Mapping[str, object]) -> None`.
- Produces: `canonical_workspace_docs(repo_root: Path) -> dict[Path, Path]` mapping canonical source to external destination.
- Produces: `install_workspace_docs(repo_root: Path, workspace_root: Path) -> list[dict[str, object]]`.
- Produces: `verify_workspace_docs(repo_root: Path, workspace_root: Path) -> list[str]`; empty means parity.

- [ ] **Step 1: Write failing parity and content tests**

```python
def test_workspace_docs_define_free_tool_and_render_gates(self):
    agents = (DOC_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    self.assertIn("Paid add-ons, subscriptions, and cloud AI are prohibited", agents)
    self.assertIn("BlenderMCP defaults to read-only inspection", agents)
    self.assertIn("30G", agents)
    self.assertIn("300/300", agents)
    self.assertIn("50G", agents)
    self.assertIn("350/350", agents)
    self.assertIn("native-resolution rendering requires owner approval", agents)

def test_verify_workspace_docs_rejects_drift(self):
    with TemporaryDirectory() as root:
        destination = Path(root) / "AGENTS.md"
        destination.write_text("stale", encoding="utf-8")
        errors = verify_workspace_docs(REPO_ROOT, Path(root))
        self.assertRegex("\n".join(errors), "AGENTS.md SHA-256 drift")
```

The Node contract must require the exact canonical/external paths and reject references to paid/cloud enhancers in allowed-tool sections.

- [ ] **Step 2: Run tests and record RED**

Run:

```powershell
python -m unittest scripts.blender.pimm_production.tests.test_workspace_docs -v
node --test scripts/tests/pimm-blender-production-governance.test.mjs
```

Expected: imports or file reads fail because the governance package and canonical documents do not exist.

- [ ] **Step 3: Implement path and atomic-I/O boundaries**

```python
REPO_ROOT = Path(__file__).resolve().parents[3]
ASSET_ROOT = Path(r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders")
ARCHIVE_ROOT = Path(r"M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders-archive\pending-delete")
DOC_ROOT = REPO_ROOT / "docs" / "pimm-blender-governance"

def require_within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    resolved.relative_to(root.resolve())
    return resolved

def atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
```

The path guard must reject the drive root, repository root, asset root itself, unresolved environment variables, and destinations outside the expected root.

- [ ] **Step 4: Write the canonical documents**

Copy every approved requirement from the design specification into focused documents. `AGENTS.md` must establish authority order, read-before-write BlenderMCP behavior, no paid/cloud tools, no invented machine behavior, proof approval before finals, no permanent deletion, and validation reporting. Replace the obsolete OBJ/meters instructions in the canonical README with STEP masters, `0.01` object scale, Metric/Millimeters, linked scenes, and current commands.

- [ ] **Step 5: Implement external install/check commands**

CLI contract:

```powershell
python scripts/blender/pimm_production/workspace_docs.py --check
python scripts/blender/pimm_production/workspace_docs.py --install
```

`--check` is read-only and fails on missing/drifted external files. `--install` writes only `AGENTS.md`, `README.md`, and `docs/*.md` beneath the exact external root using temporary files and `os.replace`; it emits source/destination hashes.

- [ ] **Step 6: Add Python cache exclusions and run GREEN tests**

Add exactly:

```gitignore
__pycache__/
*.py[cod]
```

Run the Task 1 tests plus `git diff --check`. Expected: all pass; existing cache directories become ignored without deleting them.

- [ ] **Step 7: Install the approved docs and verify readback**

Run `--install`, then a separate `--check`. Read the external `AGENTS.md` and README from disk and compare hashes to canonical sources. Do not move or render assets.

- [ ] **Step 8: Commit**

Stage only Task 1 files and commit: `Establish PIMM Blender workspace governance`.

---

### Task 2: Free-Tool Lock and BlenderMCP Preflight

**Files:**
- Create: `scripts/blender/pimm_production/requirements-production.txt`
- Create: `scripts/blender/pimm_production/tool_policy.py`
- Create: `scripts/blender/pimm_production/blender_session_preflight.py`
- Create: `scripts/blender/pimm_production/tests/test_tool_policy.py`
- Modify: `scripts/tests/pimm-blender-production-governance.test.mjs`
- Create externally: `manifests/free-tools-lock.json`

**Interfaces:**
- Produces: `ToolRecord(id: str, version: str, license: str, path: str, sha256: str | None)`.
- Produces: `discover_free_tools() -> list[ToolRecord]`.
- Produces: `validate_tool_lock(payload: Mapping[str, object]) -> list[str]`.
- Produces inside Blender: `inspect_open_session(bpy) -> dict[str, object]`.

- [ ] **Step 1: Write failing license and preflight tests**

```python
def test_paid_or_cloud_tool_is_rejected(self):
    payload = {"tools": [{"id": "cloud-enhancer", "license": "commercial", "execution": "cloud"}]}
    self.assertRegex("\n".join(validate_tool_lock(payload)), "paid or cloud tool")

def test_allowed_local_tools_require_version_and_license(self):
    payload = {"tools": [{"id": "blender", "version": "5.2.0", "license": "GPL-3.0-or-later", "execution": "local", "path": r"D:\Blender 5.2\blender.exe"}]}
    self.assertEqual(validate_tool_lock(payload), [])
```

Add a Node assertion that the lock schema contains Blender, BlenderMCP, Python, and Pillow and contains no `subscription`, `paid`, `cloud`, or remote API endpoint.

- [ ] **Step 2: Run tests and record RED**

Run the focused Python and Node tests. Expected: missing module/functions and missing external lock.

- [ ] **Step 3: Pin the free production environment**

Create `requirements-production.txt` with:

```text
Pillow==12.2.0
```

Create external venv `tools\pimm-render-py311` with Python 3.11, install the exact requirement, and record executable/package hashes. Do not install Blender add-ons.

- [ ] **Step 4: Implement local tool discovery and policy**

Probe:

- `D:\Blender 5.2\blender.exe --version`;
- `git -C C:\Users\natth\blender_mcp rev-parse HEAD`;
- the first BlenderMCP `LICENSE*` file and its SHA;
- Python version/executable;
- Pillow version and distribution metadata.

Reject missing license/version/path, network execution, unknown commercial license, or a path outside the configured local tool roots. Write the lock atomically under `manifests`.

- [ ] **Step 5: Implement Blender session preflight**

```python
def inspect_open_session(bpy) -> dict[str, object]:
    scene = bpy.context.scene
    return {
        "filepath": bpy.data.filepath,
        "dirty": bpy.data.is_dirty,
        "scene": scene.name,
        "view_layer": bpy.context.view_layer.name,
        "unit_system": scene.unit_settings.system,
        "length_unit": scene.unit_settings.length_unit,
        "scale_length": scene.unit_settings.scale_length,
        "selected_objects": sorted(obj.name for obj in bpy.context.selected_objects),
        "active_object": bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else None,
        "libraries": sorted(library.filepath for library in bpy.data.libraries),
    }
```

CLI/MCP output must be JSON serializable. The script is read-only, never saves, and rejects mutation flags.

- [ ] **Step 6: Exercise the preflight through BlenderMCP**

Call the connected BlenderMCP with the checked-in preflight function, not ad-hoc scene mutation. Expected current evidence includes exact file path, dirty state, scene, Metric/Millimeters, `scale_length≈0.001`, active selection, and library list. Repeat through background Blender on each master.

- [ ] **Step 7: Run GREEN tests and commit**

Run focused Python/Node tests, validate the external lock, and run `git diff --check`. Commit: `Lock free PIMM Blender production tools`.

---

### Task 3: Machine Operation and Controller Contracts

**Files:**
- Create: `docs/pimm-blender-governance/machine-operation-30g.md`
- Create: `docs/pimm-blender-governance/machine-operation-50g.md`
- Create: `scripts/blender/pimm_production/contracts/machines/30g.json`
- Create: `scripts/blender/pimm_production/contracts/machines/50g.json`
- Create: `scripts/blender/pimm_production/machine_contract.py`
- Create: `scripts/blender/pimm_production/tests/test_machine_contract.py`
- Modify: `scripts/tests/pimm-blender-production-governance.test.mjs`

**Interfaces:**
- Produces: `load_machine_contract(machine: Literal["30G", "50G"]) -> dict[str, object]`.
- Produces: `validate_machine_contract(payload: Mapping[str, object]) -> list[str]`.
- Produces: `discover_controller_candidates(objects: Iterable[object]) -> list[dict[str, object]]` using stable IDs and CAD names.
- Produces: `validate_controller_scene(bpy, contract: Mapping[str, object]) -> list[str]`.
- Produces: `animation_is_authorized(payload: Mapping[str, object]) -> bool`.

- [ ] **Step 1: Write failing semantic tests**

```python
def test_controller_values_are_machine_specific(self):
    self.assertEqual(load_machine_contract("30G")["controller"]["display_values"], ["300", "300"])
    self.assertEqual(load_machine_contract("50G")["controller"]["display_values"], ["350", "350"])

def test_motion_is_blocked_without_owner_approved_map(self):
    payload = {
        "schema_version": 1,
        "machine": "30G",
        "controller": {
            "display_values": ["300", "300"],
            "geometry_mode": "physical-seven-segment-mesh",
            "allow_font": False,
            "allow_image_overlay": False,
            "inactive_segments_required": True,
        },
        "animation": {
            "status": "blocked_pending_owner_motion_map",
            "allowed_controls": [],
        },
    }
    self.assertEqual(validate_machine_contract(payload), [])
    self.assertFalse(animation_is_authorized(payload))
```

Mutation fixtures must reject `350/350` for 30G, `300/300` for 50G, FONT/image overlay digits, missing inactive segments, unknown animated objects, and an animation marked enabled with an empty approved control map.

- [ ] **Step 2: Run tests and record RED**

Expected: contracts and validation functions do not exist.

- [ ] **Step 3: Define exact machine contracts**

Each JSON must contain:

```json
{
  "schema_version": 1,
  "machine": "30G",
  "controller": {
    "display_values": ["300", "300"],
    "geometry_mode": "physical-seven-segment-mesh",
    "allow_font": false,
    "allow_image_overlay": false,
    "inactive_segments_required": true
  },
  "animation": {
    "status": "blocked_pending_owner_motion_map",
    "allowed_controls": []
  }
}
```

The 50G contract differs only where machine facts differ and must set `display_values` to `350/350`. It is not acceptable to copy temperature values between machines.

- [ ] **Step 4: Add read-only controller discovery**

Use BlenderMCP/background Blender to emit stable ID, CAD name, object type, material IDs, bounds, and collection path for controller/display candidates. Save candidate reports under `manifests/machine-contract-candidates/`; never alter meshes or materials. Require owner approval before stable IDs are promoted into machine contracts.

- [ ] **Step 5: Write operation documents without inventing motion**

Document known controller facts and current neutral-pose authority. State explicitly that animation remains blocked until the owner approves the named control/axis/limit map. Include the exact approval table columns: stable object ID, human part name, control ID, axis, minimum, maximum, neutral, start, operating, final, hose/cable dependency, collision note.

- [ ] **Step 6: Validate approved controller mappings in Blender**

After owner approval of candidate stable IDs, update the JSON contracts with exact IDs and run mutation-backed validation. Require physical MESH segments, correct emissive material IDs, present inactive segments, and absence of FONT/image replacement.

- [ ] **Step 7: Run GREEN tests and commit**

Commit docs/contracts/validators only after both machines pass controller semantics or remain explicitly animation-blocked with no unauthorized action. Commit: `Define PIMM machine and controller contracts`.

---

### Task 4: Linked Render-Scene Contract and Template

**Files:**
- Create: `scripts/blender/pimm_production/scene_contract.py`
- Create: `scripts/blender/pimm_production/blender_scene_validator.py`
- Create: `scripts/blender/pimm_production/blender_scene_template.py`
- Create: `scripts/blender/pimm_production/tests/test_scene_contract.py`
- Modify: `scripts/tests/pimm-blender-production-governance.test.mjs`
- Create externally after publish approval: `scenes/shared-templates/pimm-linked-studio-template.blend`

**Interfaces:**
- Produces: `SceneContract.from_mapping(payload: Mapping[str, object]) -> SceneContract`.
- Produces: `SceneContract.from_json(path: Path) -> SceneContract`.
- Produces: `validate_scene_contract(contract: SceneContract) -> list[str]`.
- Produces inside Blender: `validate_open_render_scene(bpy, contract: SceneContract) -> list[str]`.
- Produces: `build_linked_scene(contract_path: Path, output_blend: Path) -> dict[str, object]`.
- Test-only helper: `build_scene_fixture(kind: str, root: Path) -> tuple[Path, SceneContract]` creates one deterministic Blender fixture and its contract.
- Test-only helper: `run_scene_fixture_validation(path: Path, contract: SceneContract) -> list[str]` opens the fixture in background Blender and returns its reported errors.

- [ ] **Step 1: Write failing scene ownership tests**

```python
def test_scene_contract_requires_published_master_collection(self):
    payload = {
        "schema_version": 1,
        "scene_id": "pimm-30g--hero--three-quarter",
        "machine": "30G",
        "purpose": "hero",
        "master_path": "masters/PIMM-30G-MASTER.blend",
        "master_sha256": "a" * 64,
        "master_collection": "PIMM_WORKING",
        "material_library_path": "masters/PIMM-MATERIAL-LIBRARY.blend",
        "material_library_sha256": "b" * 64,
        "camera_name": "CAM_HERO",
        "complete_product": True,
        "animation_contract": None,
        "output_contract": {"width": 1200, "height": 1200, "alpha": True},
    }
    errors = validate_scene_contract(SceneContract.from_mapping(payload))
    self.assertRegex("\n".join(errors), "PIMM_PUBLISHED")

def test_private_mesh_and_localized_product_material_fail(self):
    with TemporaryDirectory() as root:
        path, contract = build_scene_fixture("private-product-copy", Path(root))
        self.assertIn("private machine mesh", "\n".join(run_scene_fixture_validation(path, contract)))
        path, contract = build_scene_fixture("localized-shared-material", Path(root))
        self.assertIn("linked product material made local", "\n".join(run_scene_fixture_validation(path, contract)))
```

Mutations also cover wrong master SHA, wrong material-library SHA, missing camera, output outside managed roots, a scene-local product mesh, and a locally overridden product material.

- [ ] **Step 2: Run tests and record RED**

Expected: modules and fixture builder do not exist.

- [ ] **Step 3: Implement the scene schema**

Required fields:

```python
@dataclass(frozen=True)
class SceneContract:
    schema_version: int
    scene_id: str
    machine: str
    purpose: str
    master_path: str
    master_sha256: str
    master_collection: str
    material_library_path: str
    material_library_sha256: str
    camera_name: str
    complete_product: bool
    animation_contract: str | None
    output_contract: dict[str, object]
```

`scene_id` must match `^pimm-(30g|50g)--[a-z0-9-]+(?:--[a-z0-9-]+)*$`. Master collection must equal `PIMM_PUBLISHED`.

- [ ] **Step 4: Implement Blender ownership validation**

Inspect `bpy.data.libraries`, linked collections, object libraries, mesh datablock libraries, and material libraries. Product objects must come from the expected master library; shared product materials must resolve to the expected material library; machine-local materials must resolve through the master. Reject library overrides that change product materials.

- [ ] **Step 5: Build fixture scenes and validate mutations**

Generate tiny fixture `.blend` files under a temporary test directory, not the M-drive scenes directory. Prove the validator detects private mesh copies, missing link, localized material, output escape, and wrong hash.

- [ ] **Step 6: Enforce the manual-material publication boundary**

Run publish audit on each actual master. If `PIMM_PUBLISHED` is empty or material audit reports unassigned objects, the template builder must emit `status=blocked_manual_material_approval` and not create a production scene. This is expected until the owner completes materials.

- [ ] **Step 7: Create the real shared template only after approval**

Once the owner approves a publish-audit-green master, build the linked studio template, reopen it in a fresh Blender process, and validate links, units, camera/light-only local ownership, and no private product mesh.

- [ ] **Step 8: Run GREEN tests and commit**

Commit: `Enforce linked PIMM render scene ownership`.

---

### Task 5: Proof Rendering, Quantitative QA, and Contact Sheets

**Files:**
- Create: `scripts/blender/pimm_production/proof_contract.py`
- Create: `scripts/blender/pimm_production/blender_proof_render.py`
- Create: `scripts/blender/pimm_production/contact_sheet.py`
- Create: `scripts/blender/pimm_production/tests/test_proof_contract.py`
- Modify: `scripts/blender/pimm_production/requirements-production.txt`
- Modify: `scripts/tests/pimm-blender-production-governance.test.mjs`

**Interfaces:**
- Produces: `ProofContract.from_mapping(payload: Mapping[str, object]) -> ProofContract`.
- Produces: `ProofContract.from_json(path: Path) -> ProofContract`.
- Produces: `validate_proof_contract(contract: ProofContract, scene: SceneContract) -> list[str]`.
- Produces: `write_proof_manifest(contract: ProofContract, outputs: Sequence[Path]) -> Path`.
- Produces: `build_contact_sheet(manifest_path: Path, output_path: Path) -> Path`.
- Test-only helper: `scene_contract_fixture() -> SceneContract` returns the exact valid scene payload shown in Task 4 with `master_collection="PIMM_PUBLISHED"`.
- Test-only helper: `composition_contract() -> ProofContract` returns stage `composition`, generation `proof-20260815T153000Z-a1b2c3d`, 25%, 32 samples, denoise enabled, and white/checker/dark backgrounds.
- Test-only helper: `material_contract(backgrounds: Sequence[str], object_masks: bool) -> ProofContract` returns stage `material-lighting`, 25%, 64 samples, and the supplied background/mask values.

- [ ] **Step 1: Write failing proof-stage tests**

```python
def test_composition_proof_is_low_cost(self):
    contract = composition_contract()
    self.assertLessEqual(contract.resolution_percentage, 25)
    self.assertGreaterEqual(contract.resolution_percentage, 12.5)
    self.assertLessEqual(contract.samples, 32)

def test_material_proof_requires_all_backgrounds_and_masks(self):
    contract = material_contract(backgrounds=["white"], object_masks=False)
    errors = validate_proof_contract(contract, scene_contract_fixture())
    self.assertIn("white/checker/dark", "\n".join(errors))
    self.assertIn("object/material masks", "\n".join(errors))
```

Reject output outside `renders/proofs/<generation-id>`, reused generation IDs, native resolution, samples above the proof ceiling, missing denoising, missing backgrounds, missing masks, or master/scene hash drift.

- [ ] **Step 2: Run tests and record RED**

Expected: proof modules and contract types do not exist.

- [ ] **Step 3: Implement immutable proof contracts**

```python
@dataclass(frozen=True)
class ProofContract:
    schema_version: int
    generation_id: str
    stage: Literal["composition", "material-lighting"]
    scene_contract_path: str
    scene_sha256: str
    master_sha256: str
    material_library_sha256: str
    resolution_percentage: float
    samples: int
    denoise: bool
    backgrounds: tuple[str, ...]
    object_masks: bool
    output_root: str
```

Generation IDs must match `^proof-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{7}$`. The output directory must not preexist.

- [ ] **Step 4: Implement Blender proof rendering**

The Blender runner:

1. revalidates tool, machine, scene, and proof contracts;
2. snapshots source/master/material hashes;
3. sets contracted percentage and samples;
4. renders RGBA proof and required passes;
5. creates white/checker/dark composites without changing product pixels;
6. records render device, Cycles settings, AgX settings, hashes, timing, and Blender version;
7. verifies source/master/material hashes are unchanged.

It must stop after the first failed proof and never continue a batch with mixed settings.

- [ ] **Step 5: Implement quantitative QA hooks**

Record full-product or intended-subject bounds, edge alpha, partial-alpha attachment, physical-shadow extent, background continuity, near-white/clipped fraction, dark fraction, luma percentiles, material-mask metrics, and named-shaft reflection metrics. Reuse proven PIMM renderer formulas where possible, but move shared logic into focused functions rather than copying an entire legacy builder.

- [ ] **Step 6: Implement labelled contact sheets with Pillow**

```python
def build_contact_sheet(manifest_path: Path, output_path: Path) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = sorted(manifest["outputs"], key=lambda item: (item["shot_id"], item["background"]))
    # Open immutable proof images, fit them into fixed cells without resampling
    # the source files in place, draw shot/settings/hash labels, and save once.
```

The sheet header includes generation ID, scene/master/material short hashes, resolution percentage, samples, and status. Every cell includes shot ID, background, dimensions, and output short hash. Write `contact-sheet.json` alongside the image so decisions do not depend on OCR.

- [ ] **Step 7: Run fixture proof and GREEN tests**

Render a small fixture scene at 12.5%/16 samples and material proof at 25%/32 samples. Verify exact files, backgrounds, masks, manifest, contact sheet, and immutable inputs. Do not render a real machine until its master is publish-approved.

- [ ] **Step 8: Commit**

Commit: `Add gated PIMM proof and contact sheet pipeline`.

---

### Task 6: Owner Approval, Native Render Authorization, and Atomic Releases

**Files:**
- Create: `scripts/blender/pimm_production/approval_manifest.py`
- Create: `scripts/blender/pimm_production/blender_final_render.py`
- Create: `scripts/blender/pimm_production/release_manifest.py`
- Create: `scripts/blender/pimm_production/tests/test_approval_release.py`
- Modify: `scripts/tests/pimm-blender-production-governance.test.mjs`

**Interfaces:**
- Produces: `record_decision(proof_manifest: Path, shot_id: str, decision: Literal["approved", "rejected"], owner: str, notes: str) -> Path`.
- Produces: `validate_approval_payload(payload: Mapping[str, object], current_inputs: Mapping[str, str]) -> list[str]`.
- Produces: `validate_approval(approval_path: Path, current_inputs: Mapping[str, str]) -> list[str]`.
- Produces: `authorize_final_render(approval_path: Path, final_contract_path: Path) -> FinalAuthorization`.
- Produces: `build_release_manifest(release_id: str, approved_outputs: Sequence[Path]) -> Path`.
- Test-only helper: `write_approval_fixture(root: Path, decision: str, scene_sha256: str) -> tuple[Path, Path]` writes a complete approval and matching final contract.
- Test-only helper: `write_release_output_fixture(root: Path, generation_id: str) -> Path` writes one hashed final-output manifest entry.

- [ ] **Step 1: Write failing approval and release tests**

```python
def test_any_scene_drift_invalidates_approval(self):
    approval = {
        "schema_version": 1,
        "decision": "approved",
        "owner": "natth",
        "inputs": {"scene_sha256": "a" * 64},
    }
    errors = validate_approval_payload(approval, {"scene_sha256": "b" * 64})
    self.assertIn("scene SHA-256 drift", "\n".join(errors))

def test_final_render_requires_approved_decision(self):
    with TemporaryDirectory() as root:
        approval_path, final_contract_path = write_approval_fixture(Path(root), "rejected", "a" * 64)
        with self.assertRaisesRegex(ValueError, "owner approval required"):
            authorize_final_render(approval_path, final_contract_path)

def test_release_rejects_mixed_generations(self):
    with TemporaryDirectory() as root:
        outputs = [
            write_release_output_fixture(Path(root), "proof-20260815T153000Z-a1b2c3d"),
            write_release_output_fixture(Path(root), "proof-20260815T160000Z-d4e5f6a"),
        ]
        with self.assertRaisesRegex(ValueError, "mixed proof generations"):
            build_release_manifest("release-2026-08-15-r01", outputs)
```

Mutations cover camera/light/world/compositor/render-settings drift, modified proof pixels, rejected shot, missing owner, duplicate logical asset ID, changed dimensions, absent EXR, and proof/archived path as a release output.

- [ ] **Step 2: Run tests and record RED**

Expected: approval/final/release modules do not exist.

- [ ] **Step 3: Implement immutable owner decisions**

Approval schema contains exact proof/contact-sheet hashes, source/master/material/scene/script hashes, render settings, shot decision, notes, owner, and UTC timestamp. Refuse to overwrite an existing decision; amendments create a new approval revision linked to the prior hash.

CLI example:

```powershell
python scripts/blender/pimm_production/approval_manifest.py record --proof-manifest <path> --shot-id pimm-30g--hero--three-quarter --decision approved --owner natth --notes "materials and framing approved"
```

- [ ] **Step 4: Implement final-render authorization**

Require the final contract to match approved geometry, materials, camera, lights, world, compositor, animation, output dimensions, alpha mode, and composition. Permit only the documented final-sampling increase. Final output root must be a new `renders/final/<release-id>` directory.

- [ ] **Step 5: Implement native render and release QA**

The Blender runner writes float EXR and contracted transparent deliverables, then validates original-resolution product/material/alpha/controller metrics and animation endpoint parity. System Python verifies PNG/WebP/video dimensions and hashes. No generated output is copied into storefront assets during this task.

- [ ] **Step 6: Implement atomic release manifests**

Release IDs match `^release-[0-9]{4}-[0-9]{2}-[0-9]{2}-r[0-9]{2}$`. The manifest maps stable logical asset IDs to exact immutable path, SHA, dimensions, alpha, MIME type, generation, approval, and release ID. Reject mixed generation, partial shot families, duplicate logical IDs, mutable output directories, and proof/archive paths.

- [ ] **Step 7: Run fixture GREEN tests and commit**

Use fixture outputs to prove rejected/stale approvals block finals and an approved fixture creates an atomic release. Commit: `Gate PIMM final renders behind owner approval`.

---

### Task 7: Fresh Legacy Inventory and Consumer Graph

**Files:**
- Modify: `scripts/blender/master_assets/pimm_legacy_inventory.py`
- Modify: `scripts/blender/master_assets/tests/test_pimm_legacy_inventory.py`
- Create: `scripts/blender/pimm_production/consumer_graph.py`
- Create: `scripts/blender/pimm_production/tests/test_consumer_graph.py`
- Modify: `scripts/tests/pimm-blender-production-governance.test.mjs`
- Rewrite externally: `manifests/blender-project-inventory.json`
- Create externally: `manifests/render-generation-inventory.json`
- Create externally: `manifests/consumer-graph.json`

**Interfaces:**
- Produces: `AssetRecord(path: str, size: int, mtime_ns: int, sha256: str, kind: str, unique_content: bool, consumers: tuple[str, ...], dependencies: tuple[str, ...], proposed_disposition: str)`.
- Produces: `InventoryManifest(records: tuple[AssetRecord, ...], discovered_paths: tuple[str, ...])`.
- Produces: `ConsumerGraph(consumers: Mapping[str, tuple[str, ...]], producers: Mapping[str, tuple[str, ...]])`.
- Produces: `inventory_workspace(root: Path) -> InventoryManifest`.
- Produces: `build_consumer_graph(repo_root: Path, asset_root: Path, records: Sequence[AssetRecord]) -> ConsumerGraph`.
- Produces: `classify_record(record: AssetRecord, graph: ConsumerGraph) -> Literal["authoritative", "active-linked-scene", "migrate", "pending-archive", "unresolved"]`.

- [ ] **Step 1: Write failing complete-inventory tests**

```python
def test_every_blend_and_render_file_is_accounted_once(self):
    record = AssetRecord(
        path="PIMM-old.blend1",
        size=100,
        mtime_ns=1,
        sha256="a" * 64,
        kind="blend-recovery",
        unique_content=False,
        consumers=(),
        dependencies=(),
        proposed_disposition="pending-archive",
    )
    inventory = InventoryManifest(records=(record,), discovered_paths=(record.path,))
    paths = [record.path for record in inventory.records]
    self.assertEqual(len(paths), len(set(paths)))
    self.assertEqual(set(paths), set(inventory.discovered_paths))

def test_active_consumer_prevents_archive(self):
    record = AssetRecord(path="PIMM-product-render-master.blend", unique_content=True)
    graph = ConsumerGraph(consumers={record.path: ["scripts/render.py"]})
    self.assertEqual(classify_record(record, graph), "migrate")
```

Reject stale authoritative hashes, omitted `.blend1`, missing render directories, unresolved exact filename consumers, and any `delete` disposition.

- [ ] **Step 2: Run tests and record RED**

Expected: schema-v2 inventory and consumer graph functions are missing.

- [ ] **Step 3: Expand inventory scope**

Record every `.blend`, `.blend1`, render image/video, mask/pass, script, texture, artwork, and manifest under the active root. Record path, size, mtime, SHA-256, Blender inspection summary, unique content, dependencies, generation/release membership, and proposed disposition. Ignore only the external pending-delete archive and tool virtual-environment internals.

- [ ] **Step 4: Build exact consumer graph**

Scan repository Liquid/JSON/CSS/JS/Python/PowerShell/batch files and external Blender/scripts/manifests. For `.blend`, use background Blender to inspect linked libraries, images, fonts, sounds, caches, and output paths without saving. Store producer and consumer edges with source line or datablock evidence.

- [ ] **Step 5: Regenerate inventory against current masters**

Run read-only inventory after hashing current 30G/50G masters and material library. Expected: all current 478-object master fingerprints match; the obsolete prior inventory is replaced atomically; every discovered item appears exactly once.

- [ ] **Step 6: Review unresolved and migration records**

Do not auto-classify unique-content or consumer-bearing files as pending archive. Produce a human-readable migration report listing cameras, rigs, animations, lights, compositor nodes, and consumers that must move to linked scenes after material publication.

- [ ] **Step 7: Run GREEN tests and commit**

Commit source/test changes and the source-controlled schema, not large external inventories. Commit: `Refresh PIMM Blender asset and consumer inventory`.

---

### Task 8: Reversible Pending-Delete Archive and First Move Batch

**Files:**
- Create: `scripts/blender/pimm_production/archive_plan.py`
- Create: `scripts/blender/pimm_production/tests/test_archive_plan.py`
- Modify: `scripts/tests/pimm-blender-production-governance.test.mjs`
- Create externally at the sibling governance authority root: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders-governance\manifests\archive-plans\<batch-id>.json`. Archive plans must never be published beneath the governed `blender-product-renders` active root because doing so would invalidate the Task 7 publication they bind.
- Create externally after explicit batch approval: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders-archive\pending-delete\<date>-<batch-id>\archive-manifest.json`

**Interfaces:**
- Produces: `build_archive_plan(inventory: InventoryManifest, graph: ConsumerGraph, batch_id: str) -> ArchivePlan`.
- Produces: `validate_archive_plan(plan: ArchivePlan, inventory: InventoryManifest, graph: ConsumerGraph) -> list[str]`.
- Produces: `apply_archive_plan(plan_path: Path, approval_path: Path) -> ArchiveResult`.
- Produces: `restore_archive_batch(manifest_path: Path) -> ArchiveResult`.
- Test-only fixture: `ArchiveTestFixture(plan: ArchivePlan, inventory: InventoryManifest, graph: ConsumerGraph, plan_path: Path, stale_approval_path: Path, manifest_path: Path, original_sha256: str)` exposes every path and digest consumed by the archive tests.
- Test-only helper: `archive_test_fixture(root: Path, consumers: tuple[str, ...], unique_content: bool) -> ArchiveTestFixture` creates exact source/destination files, a stale approval, and restore manifests under temporary roots.

- [ ] **Step 1: Write failing archive safety tests**

```python
def test_consumer_or_unique_content_blocks_move(self):
    with TemporaryDirectory() as root:
        fixture = archive_test_fixture(Path(root), ("theme.liquid",), True)
        errors = validate_archive_plan(fixture.plan, fixture.inventory, fixture.graph)
        self.assertIn("active consumer", "\n".join(errors))
        self.assertIn("unique content not migrated", "\n".join(errors))

def test_apply_requires_exact_owner_approved_plan_hash(self):
    with TemporaryDirectory() as root:
        fixture = archive_test_fixture(Path(root), (), False)
        with self.assertRaisesRegex(ValueError, "approved archive-plan SHA-256"):
            apply_archive_plan(fixture.plan_path, fixture.stale_approval_path)

def test_restore_recreates_original_path_and_hash(self):
    with TemporaryDirectory() as root:
        fixture = archive_test_fixture(Path(root), (), False)
        result = restore_archive_batch(fixture.manifest_path)
        self.assertEqual(result.restored[0].sha256, fixture.original_sha256)
```

Mutations cover archive destination inside active root, destination collision, source hash drift, partial directory inventory, cross-volume partial copy, missing timestamp, and a plan containing `delete`.

- [ ] **Step 2: Run tests and record RED**

Expected: archive planning and application functions do not exist.

- [ ] **Step 3: Implement plan-only mode**

CLI:

```powershell
python scripts/blender/pimm_production/archive_plan.py plan --batch-id legacy-recovery-files-01
```

The plan contains source/destination paths, hashes, sizes, mtimes, reason, replacement, consumer evidence, unique-content/migration evidence, and restore mapping. Default command is read-only and never moves files.

- [ ] **Step 4: Generate the first conservative move proposal**

Select only records classified `pending-archive` with zero consumers and no unique content, initially prioritizing `.blend1` recovery copies and rejected proof generations whose full contents are inventoried. Do not include any `migrate`, `unresolved`, active calibrated proof, approved release, source, master, material, artwork, or script.

- [ ] **Step 5: Obtain exact owner batch approval**

Present the plan summary, item count, total bytes, highest-risk items, destination, and plan SHA-256. Record the owner’s approval in a separate immutable approval JSON that includes the exact plan hash. General cleanup approval does not substitute for this exact batch approval.

- [ ] **Step 6: Implement and execute reversible moves**

Before each move, verify source hash/size/mtime and destination absence. Write `archive-manifest.json.tmp` before mutation. On the same volume use atomic rename where possible; otherwise copy, verify destination hash, then remove only the exact verified source file. Preserve timestamps. On failure, stop, restore completed moves, and report the first error.

- [ ] **Step 7: Revalidate after the move**

Regenerate inventory and consumer graph; reopen affected Blender consumers; run proof/release/storefront contracts; prove active root no longer resolves archived paths; verify every archived item and restore mapping. Do not delete the archive.

- [ ] **Step 8: Run GREEN tests and commit**

Commit tooling/tests and a small source-controlled batch summary; keep large external manifests external. Commit: `Add reversible PIMM pending-delete archive workflow`.

---

### Task 9: End-to-End Governance Gate and Handoff

**Files:**
- Modify: `scripts/tests/pimm-blender-production-governance.test.mjs`
- Modify: `docs/pimm-blender-governance/README.md`
- Modify: `docs/pimm-blender-governance/rendering-and-approval.md`
- Modify: `docs/pimm-blender-master-material-workflow.md`
- Modify: `docs/superpowers/plans/2026-08-15-pimm-blender-production-governance.md`

**Interfaces:**
- Consumes every prior contract and external manifest.
- Produces: one read-only governance report containing doc parity, tool policy, machine semantics, master publication status, scene/proof/release status, consumer graph status, and archive batch status.

- [ ] **Step 1: Add end-to-end fail-closed assertions**

Node/Python tests must assert:

- external `AGENTS.md`/README hashes equal canonical files;
- tool lock contains only approved local free tools;
- 30G is `300/300` and 50G is `350/350`;
- animation remains blocked unless an approved motion map exists;
- actual render scenes cannot use private product meshes/materials;
- proof paths/settings are isolated and low resolution;
- native finals require current owner approval;
- release manifests are atomic and immutable;
- consumers cannot reference proof/rejected/archive paths;
- inventory accounts for every active item;
- archive manifests are complete and reversible;
- no permanent deletion action exists.

- [ ] **Step 2: Run the complete repository suite**

```powershell
python -m unittest discover -s scripts\blender\master_assets\tests -v
python -m unittest discover -s scripts\blender\pimm_production\tests -v
node --test scripts\tests\pimm-master-assets-contract.test.mjs scripts\tests\pimm-blender-production-governance.test.mjs
npm run verify
git diff --check
```

Expected: all repository tests pass; Theme Check reports zero repository errors. Existing dependency-template warnings may be reported but cannot be described as repository failures.

- [ ] **Step 3: Run Blender validations**

```powershell
& 'D:\Blender 5.2\blender.exe' -b 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-30G-MASTER.blend' --python-exit-code 1 -P scripts\blender\master_assets\pimm_master_audit.py -- --mode working
& 'D:\Blender 5.2\blender.exe' -b 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-50G-MASTER.blend' --python-exit-code 1 -P scripts\blender\master_assets\pimm_master_audit.py -- --mode working
& 'D:\Blender 5.2\blender.exe' -b --factory-startup --python-exit-code 1 -P scripts\blender\pimm_production\blender_session_preflight.py
```

Expected: source/unit/scale/provenance checks pass. Publication and real render-scene creation remain blocked if manual material assignments are incomplete; report that state as an intentional gate, not success.

- [ ] **Step 4: Exercise BlenderMCP read-only governance**

With the user’s active Blender session open, call the checked-in preflight and relevant read-only validators through BlenderMCP. Confirm no dirty-state change, no selection mutation unless explicitly requested, no save, and no process termination.

- [ ] **Step 5: Verify external lifecycle state**

Run documentation parity, tool lock, inventory, consumer graph, and archive-batch verification. Confirm no file was permanently deleted. Confirm active consumers resolve only active paths. If the first move batch has not received exact owner approval, report it as planned but unapplied.

- [ ] **Step 6: Commit final handoff documentation**

Stage only Task 9 documentation/test changes and commit: `Validate PIMM Blender production governance`.

- [ ] **Step 7: Report boundaries and next manual action**

Report commits, tests, BlenderMCP evidence, external docs, tool lock, machine contracts, publication state, proof/final/release readiness, inventory totals, archive batch status, and that no permanent deletion occurred. If masters remain unassigned, state that the next action is owner material assignment followed by publish audit; do not render or migrate storefront assets prematurely.
