# PIMM Editorial Product Photography Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce four governed, preview-resolution PIMM product-photography concepts with visibly different sets, lighting, shadows, cameras, and supporting assets for owner selection.

**Architecture:** Keep the existing 22-shot storefront campaign immutable and introduce a separate four-shot editorial-concept campaign that cannot authorize finals or publish storefront media. Link the published 30G/50G masters read-only, own all cameras/lights/sets/props in the concept scenes, admit external assets only through exact CC0 provenance records, and publish previews atomically with a labelled contact sheet.

**Tech Stack:** Blender 5.2 LTS, Cycles, Blender Python API, Python 3.13, Pillow, unittest, JSON contracts, PowerShell, Poly Haven public API/assets.

**Spec:** `docs/superpowers/specs/2026-08-30-pimm-editorial-product-photography-expansion-design.md`

## Global Constraints

- The first delivery contains exactly four preview concepts and does not authorize finals, storefront publication, production deployment, or animation.
- `PIMM-30G-MASTER.blend`, `PIMM-50G-MASTER.blend`, and `PIMM-MATERIAL-LIBRARY.blend` are immutable linked inputs.
- All four machine feet must resolve to one contact plane; no machine may float.
- Use Cycles and AgX; record exposure, samples, denoising, bounce limits, camera, lights, scene hash, and asset provenance.
- Cameras are full-frame equivalent: 85 mm architectural/workshop, 135 mm dark engineering, and 135–200 mm process still life.
- Pinterest images are composition references only and are never downloaded or copied into scenes.
- External assets require a public source URL, `CC0-1.0`, exact version identifier, safe local path, SHA-256, intended shot IDs, and `machine_master_modified: false`.
- External or procedural props remain scene-local and must not intersect, obscure, or appear to be supplied parts of either machine.
- Previous proof generations, rejected scenes, and archived revisions remain byte-immutable.

---

### Task 1: Freeze the separate editorial-concept campaign

**Files:**
- Create: `scripts/blender/pimm_production/contracts/campaigns/pimm-editorial-concepts-v1.json`
- Create: `scripts/blender/pimm_production/editorial_concept_contract.py`
- Create: `scripts/blender/pimm_production/tests/test_editorial_concept_contract.py`

**Interfaces:**
- Consumes: the four approved concepts and master paths from the design specification.
- Produces: `EDITORIAL_CAMPAIGN_PATH`, `EditorialConceptShot`, `EditorialConceptCampaign`, `load_editorial_campaign(path: Path)`, and `validate_editorial_campaign(campaign: EditorialConceptCampaign) -> list[str]`.

- [ ] **Step 1: Write failing exact-policy tests**

Require these shot IDs and no others:

```python
EXPECTED = {
    "pimm-30g--concept-architectural-daylight": ("30G", 1280, 720, 85.0),
    "pimm-50g--concept-dark-engineering": ("50G", 1280, 720, 135.0),
    "pimm-50g--concept-modern-workshop": ("50G", 1280, 720, 85.0),
    "pimm-30g--concept-process-still-life": ("30G", 900, 1125, 180.0),
}
```

Tests must reject a changed machine, dimensions, focal length, final-authorized flag, missing contact gate, non-Cycles engine, or duplicated shot ID.

- [ ] **Step 2: Run the tests and confirm the contract is absent**

Run:

```powershell
python -m unittest scripts.blender.pimm_production.tests.test_editorial_concept_contract -v
```

Expected: failure because `editorial_concept_contract` does not exist.

- [ ] **Step 3: Implement the strict contract loader and JSON**

Each JSON shot contains exactly:

```json
{
  "shot_id": "pimm-30g--concept-architectural-daylight",
  "machine": "30G",
  "concept": "architectural-daylight",
  "width": 1280,
  "height": 720,
  "focal_length_mm": 85.0,
  "aperture_fstop": 11.0,
  "render_engine": "CYCLES",
  "color_management": "AgX - Medium High Contrast",
  "preview_samples": 32,
  "denoise": true,
  "contact_gate": "four-feet-common-plane",
  "final_authorized": false
}
```

Use exact field-set validation, duplicate-key rejection through the existing campaign JSON loader pattern, and immutable dataclasses.

- [ ] **Step 4: Run focused tests**

Run the command from Step 2. Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add -- scripts/blender/pimm_production/contracts/campaigns/pimm-editorial-concepts-v1.json scripts/blender/pimm_production/editorial_concept_contract.py scripts/blender/pimm_production/tests/test_editorial_concept_contract.py
git commit -m "Define PIMM editorial concept previews"
```

### Task 2: Add exact CC0 download and provenance support

**Files:**
- Modify: `scripts/blender/pimm_production/external_asset_manifest.py`
- Create: `scripts/blender/pimm_production/polyhaven_assets.py`
- Modify: `scripts/blender/pimm_production/tests/test_external_asset_manifest.py`
- Create: `scripts/blender/pimm_production/tests/test_polyhaven_assets.py`
- Modify external: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\manifests\external-assets-v1.json`
- Create external: files under `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\assets\external\polyhaven\`

**Interfaces:**
- Consumes: Poly Haven asset IDs `university_workshop`, `tool_cart`, and `metal_toolbox` from public source pages.
- Produces: `PolyHavenAssetSpec`, `resolve_public_download(spec)`, `download_asset_once(spec, destination)`, and provenance records accepted by `validate_external_assets`.

- [ ] **Step 1: Write failing provenance and network-boundary tests**

Tests require:

```python
APPROVED_POLYHAVEN = {
    "university_workshop": {"kind": "hdris", "resolution": "4k", "format": "exr"},
    "tool_cart": {"kind": "models", "resolution": "1k", "format": "blend"},
    "metal_toolbox": {"kind": "models", "resolution": "1k", "format": "blend"},
}
```

Reject redirects to another host, missing checksums, account gates, non-CC0 licenses, archive traversal, existing destination files, or intended shot IDs outside the concept campaign. Network tests mock responses and never download real bytes.

- [ ] **Step 2: Run focused tests and confirm failure**

```powershell
python -m unittest scripts.blender.pimm_production.tests.test_external_asset_manifest scripts.blender.pimm_production.tests.test_polyhaven_assets -v
```

- [ ] **Step 3: Implement deterministic public-asset acquisition**

Resolve file metadata from `https://api.polyhaven.com/files/<asset-id>`, select only the exact declared resolution/format, stream to an exclusive temporary file, hash during download, validate archive members before extraction, and atomically rename into the governed asset folder. Record the public source pages:

```text
https://polyhaven.com/a/university_workshop
https://polyhaven.com/a/tool_cart
https://polyhaven.com/a/metal_toolbox
```

The workshop HDRI and models are authorized only for `pimm-50g--concept-modern-workshop`; the toolbox is additionally authorized for `pimm-30g--concept-process-still-life`.

- [ ] **Step 4: Download and record exact assets**

Run:

```powershell
python -m scripts.blender.pimm_production.polyhaven_assets --asset-root "M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders" --asset-id university_workshop --asset-id tool_cart --asset-id metal_toolbox
```

Expected: three created asset records, three SHA-256 values, no master/material changes, and an atomically updated `external-assets-v1.json`.

- [ ] **Step 5: Re-run focused tests and provenance readback**

Run the Step 2 tests and:

```powershell
python -c "import json; from pathlib import Path; from scripts.blender.pimm_production.external_asset_manifest import validate_external_assets; p=Path(r'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\manifests\external-assets-v1.json'); d=json.loads(p.read_text(encoding='utf-8')); print(validate_external_assets(d, {'pimm-50g--concept-modern-workshop','pimm-30g--concept-process-still-life'}))"
```

Expected: `[]`.

- [ ] **Step 6: Commit repository code**

```powershell
git add -- scripts/blender/pimm_production/external_asset_manifest.py scripts/blender/pimm_production/polyhaven_assets.py scripts/blender/pimm_production/tests/test_external_asset_manifest.py scripts/blender/pimm_production/tests/test_polyhaven_assets.py
git commit -m "Govern CC0 assets for PIMM editorial scenes"
```

### Task 3: Build four distinct procedural sets and light rigs

**Files:**
- Create: `scripts/blender/pimm_production/editorial_sets.py`
- Create: `scripts/blender/pimm_production/tests/test_editorial_sets.py`

**Interfaces:**
- Consumes: `EditorialConceptShot` and Blender `bpy`.
- Produces: `build_editorial_set(bpy, shot) -> EditorialSetEvidence` and immutable set/light records.

- [ ] **Step 1: Write failing set-signature tests**

Require four distinct signatures:

```python
EXPECTED_LIGHTS = {
    "architectural-daylight": {"SUN_Gobo", "FILL_WALL", "EDGE_STRIP"},
    "dark-engineering": {"KEY_SLASH", "RIM_LEFT", "RIM_RIGHT", "BASE_LIFT", "BLUE_ACCENT"},
    "modern-workshop": {"WORKSHOP_HDRI", "WINDOW_KEY", "MACHINE_FILL", "PRACTICAL_WARM"},
    "process-still-life": {"KEY_TOP_SIDE", "EDGE_CARD", "FOREGROUND_KICK", "BASE_LIFT"},
}
```

Tests also require unique set-geometry signatures, zero product-like support ownership, and concept-specific shadow intent.

- [ ] **Step 2: Run tests and confirm failure**

```powershell
python -m unittest scripts.blender.pimm_production.tests.test_editorial_sets -v
```

- [ ] **Step 3: Implement minimal concept builders**

Implement:

- `architectural-daylight`: warm-grey wall/floor, procedural window gobo outside frame, upright accent slab behind the machine, directional hard key and broad fill.
- `dark-engineering`: graphite floor/back wall, two black flags, rim strips, low base fill, controlled blue accent, elongated diagonal shadow.
- `modern-workshop`: Poly Haven workshop HDRI, linked scene-local tool cart, procedural steel workbench, translucent pellet jars, mold blocks, drawings, and warm practical light.
- `process-still-life`: linked scene-local metal toolbox, procedural mold halves, PEEK/black/neutral pellets, molded sample parts, caliper-like inspection prop, technical drawing, and layered foreground blocks.

Tag every scene-owned object with `pimm_scene_support_role`, every external object with the exact provenance fields, and every light with `pimm_editorial_light_role`.

- [ ] **Step 4: Run focused tests**

Run the Step 2 command. Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add -- scripts/blender/pimm_production/editorial_sets.py scripts/blender/pimm_production/tests/test_editorial_sets.py
git commit -m "Build distinct PIMM editorial sets"
```

### Task 4: Author governed one-shot Blender scenes

**Files:**
- Create: `scripts/blender/pimm_production/blender_editorial_scene.py`
- Create: `scripts/blender/pimm_production/tests/test_blender_editorial_scene.py`
- Create external: four contracts under `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\scenes\contracts\editorial-concepts-v1\`
- Create external: four `.blend` files under `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\scenes\editorial-concepts-v1\`

**Interfaces:**
- Consumes: editorial campaign, set builder, exact external-asset manifest, published masters, and current foot-contact authority.
- Produces: `prepare_editorial_contract(shot)`, `author_editorial_scene(bpy, shot, contract)`, and `validate_open_editorial_scene(bpy, contract) -> list[str]`.

- [ ] **Step 1: Write failing authoring tests**

Tests reject local product copies, a changed linked master, a changed material library, wrong focal length, non-level architectural verticals, missing four-foot evidence, prop intersections with machine bounds, missing set signatures, missing provenance, or a scene that sets `final_authorized` true.

- [ ] **Step 2: Run focused tests and confirm failure**

```powershell
python -m unittest scripts.blender.pimm_production.tests.test_blender_editorial_scene -v
```

- [ ] **Step 3: Implement authoring and fresh-process validation**

Use the existing stable-ID, library-path, contact-plane, atomic-save, and fresh-Blender reopen helpers. Camera height targets the machine midline, verticals remain upright, and the camera distance is solved from complete product bounds plus each concept's prop-safe framing rectangle.

- [ ] **Step 4: Hash protected inputs and author all four scenes**

Run one `--prepare-contract`, `--author-scene`, and fresh `--validate-scene` sequence per shot. Stop at the first failure. Preserve failed candidates under `scenes/rejected/editorial-concepts-v1/<timestamp>/`; never overwrite them.

- [ ] **Step 5: Verify protected bytes and run focused tests**

Rehash both masters and the material library and require exact equality with pre-author hashes. Run the Step 2 test command. Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add -- scripts/blender/pimm_production/blender_editorial_scene.py scripts/blender/pimm_production/tests/test_blender_editorial_scene.py
git commit -m "Author governed PIMM editorial scenes"
```

### Task 5: Render four atomic previews and contact sheet

**Files:**
- Create: `scripts/blender/pimm_production/blender_editorial_preview.py`
- Create: `scripts/blender/pimm_production/editorial_contact_sheet.py`
- Create: `scripts/blender/pimm_production/tests/test_editorial_preview.py`
- Create external: immutable preview generation under `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\proofs\editorial-concepts-v1\<generation-id>\`

**Interfaces:**
- Consumes: four fresh Blender scenes and their contracts.
- Produces: `render_editorial_preview_campaign(asset_root, blender) -> EditorialPreviewResult`, per-shot PNGs, `campaign-manifest.json`, `campaign-report.json`, and `sheet-editorial-concepts.png`.

- [ ] **Step 1: Write failing atomic-preview tests**

Require exactly four fresh renders, no cache reuse, complete scene/master/material hashes, recorded render settings, exact external assets, four contact passes, no clipped machine or intentional shadow, and no partial final directory after any shot failure.

- [ ] **Step 2: Run focused tests and confirm failure**

```powershell
python -m unittest scripts.blender.pimm_production.tests.test_editorial_preview -v
```

- [ ] **Step 3: Implement the renderer and contact sheet**

Render with 32 Cycles samples and denoising at the contracted preview dimensions. The contact sheet uses 2 × 2 equal cells and labels each image with shot ID, machine, lens, f-stop, set signature, scene hash prefix, contact state, master-fingerprint state, and asset-provenance state.

- [ ] **Step 4: Render the preview generation**

```powershell
python -m scripts.blender.pimm_production.blender_editorial_preview --render-campaign --asset-root "M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders" --blender "D:\Blender 5.2\blender.exe"
```

Expected: one new immutable generation with four passing shots and one contact sheet.

- [ ] **Step 5: Inspect actual pixels**

Inspect every preview and the contact sheet at 100 percent. Reject the generation if any foot floats, any prop intersects the product, a product or designed shadow clips, white metal washes out, dark metal crushes, decals become unreadable where visible, or two concepts collapse to the same lighting signature.

- [ ] **Step 6: Run focused and integration checks**

```powershell
python -m unittest scripts.blender.pimm_production.tests.test_editorial_concept_contract scripts.blender.pimm_production.tests.test_external_asset_manifest scripts.blender.pimm_production.tests.test_polyhaven_assets scripts.blender.pimm_production.tests.test_editorial_sets scripts.blender.pimm_production.tests.test_blender_editorial_scene scripts.blender.pimm_production.tests.test_editorial_preview -v
node --test scripts/tests/pimm-blender-production-governance.test.mjs
git diff --check
```

Record known unrelated baseline failures separately; no new failure in the six focused modules is acceptable.

- [ ] **Step 7: Commit**

```powershell
git add -- scripts/blender/pimm_production/blender_editorial_preview.py scripts/blender/pimm_production/editorial_contact_sheet.py scripts/blender/pimm_production/tests/test_editorial_preview.py
git commit -m "Render PIMM editorial concept previews"
```

### Task 6: Owner preview checkpoint

**Files:**
- Modify ignored task ledger only: `.superpowers/sdd/2026-08-30-pimm-editorial-product-photography-expansion/progress.md`

**Interfaces:**
- Consumes: immutable preview generation and its report.
- Produces: owner-facing review evidence only; no final authorization.

- [ ] **Step 1: Present the exact generation**

Provide the generation ID, absolute contact-sheet path, four individual preview paths, report SHA-256, scene hashes, master/material fingerprint results, foot-contact results, clipping results, and asset-provenance results.

- [ ] **Step 2: Stop before finals or storefront work**

Do not render native finals, replace Shopify assets, edit the landing page, deploy, or push. Owner approval must identify the exact preview generation and selected concepts.
