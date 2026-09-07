# PIMM Rendering System Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every active PIMM 30G/50G Blender storefront render with proof-approved, KeyShot-quality transparent studio media that has realistic metals, balanced exposure, and complete physical ground shadows.

**Architecture:** A shared Blender Python module owns calibrated material families, bright/dark studio rigs, Cycles/color settings, physical shadow catching, and render validation. Product-specific builders preserve immutable machine sources, cameras, mechanisms, and animation timing while consuming that shared system. A manifest-driven promotion script converts only approved high-bit-depth masters into the 22 active 30G and ten active 50G storefront files.

**Tech Stack:** Blender 5.2 Python API, Cycles/OptiX with deterministic CPU fallback, OpenImageIO/Pillow image inspection, FFmpeg 8 VP9 alpha encoding, Node.js 20+ test runner, PowerShell 7, Shopify Liquid/JSON templates, Shopify Theme Check, Chromium/CDP responsive tests.

## Global Constraints

- Original KeyShot references, CAD files, and immutable source `.blend` files are read-only and must retain SHA-256, byte length, and modification time.
- The PIMM 30G landing startup is the only dark-studio output; all other 30G media and every 50G output use the bright studio.
- No PIMM 50G output may use the retired red/dark keynote treatment, including the next-model media embedded on the 30G page.
- Geometry, object transforms, camera intent, animation timing, controller values, decals, labels, and mechanisms remain unchanged unless the approved proof exposes an existing source defect.
- Every ground-bearing master is transparent RGBA with a complete physical Cycles contact/ambient shadow and no opaque floor, rectangular plane edge, radial fake shadow, or CSS-style feather baked into the image.
- Master stills and animation frames are high-bit-depth lossless outputs; WebP/WebM storefront files are derivatives, never the rendering source.
- Static posters and matching animation endpoints must have identical camera, scale, materials, lighting, exposure, and alpha bounds.
- Published media must keep the filenames and dimensions required by existing Liquid/template contracts, except the four active red-stage next-model files, which receive new bright-studio names and matching 30G template reference updates.
- Legacy unreferenced `v2`, `v4`, `v10`, red-stage, and keynote exports are not rerendered.
- No push or deployment is authorized.

## File structure and ownership

- Create `scripts/blender/pimm_rendering_system.py`: shared material, lighting, reflection-card, color-management, shadow-catcher, and validation API.
- Create `scripts/blender/pimm_active_render_manifest.json`: immutable source hashes, versioned targets, proof scenes, active output mapping, dimensions, poster frames, and encoding parameters.
- Create `scripts/blender/create_pimm30_calibrated_studio.py`: idempotent owner of versioned 30G bright scenes and the 30G dark-startup variant.
- Modify `scripts/blender/create_pimm30_direct_operation_toggle.py`: consume the shared material/studio API while retaining the approved actuator/plunger animation.
- Modify `scripts/blender/create_pimm50_light_studio.py`: replace local studio/material/shadow logic with the shared API and build the versioned bright 50G target.
- Create `scripts/render/promote_pimm_calibrated_media.ps1`: manifest-driven master validation, WebP/WebM encoding, endpoint extraction, and atomic storefront promotion.
- Create `scripts/tests/pimm-rendering-system-contract.test.mjs`: shared-module and manifest contract tests.
- Create `scripts/tests/pimm30-calibrated-blender.test.mjs`: 30G source/scene/material/animation contract tests.
- Create `scripts/tests/pimm-calibrated-proof-quality.test.mjs`: alpha, shadow, exposure, material-separation, temporal, and proof-composite tests.
- Modify `scripts/tests/pimm50-light-studio-blender.test.mjs`: shared-module and versioned-target assertions.
- Modify `scripts/tests/pimm50-light-studio-assets.test.mjs`: approved v2 master and quality-contract assertions.
- Modify `scripts/tests/pimm30-presentation-regressions.test.mjs`: promoted-media parity, dimensions, duration, alpha, and poster endpoint assertions.
- Regenerate only the active files named in `scripts/blender/pimm_active_render_manifest.json` under `assets/`.

---

### Task 1: Freeze the active source and output manifest

**Files:**
- Create: `scripts/blender/pimm_active_render_manifest.json`
- Create: `scripts/tests/pimm-rendering-system-contract.test.mjs`
- Read: `templates/product.injection-molding-machine.json`
- Read: `sections/maliev-pimm-50g-launch.liquid`

**Interfaces:**
- Produces: manifest schema `{ version, sources, targets, proofs, outputs }` consumed by both Blender builders and the promotion script; each output includes its owning `consumer` contract (`pimm30-template` or `pimm50-section`).
- Produces: `sources[*].sha256`, `byteLength`, `path`, and `target` immutability contracts.
- Produces: exactly 22 unique `pimm30` output names and ten unique `pimm50` output names: six on the dedicated 50G page plus four newly named bright next-model files referenced by the 30G template.

- [ ] **Step 1: Write the failing manifest contract test**

```js
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../', import.meta.url);

test('active PIMM render manifest freezes immutable sources and storefront outputs', async () => {
  const manifest = JSON.parse(await readFile(new URL('../blender/pimm_active_render_manifest.json', import.meta.url)));
  assert.equal(manifest.version, 1);
  assert.equal(new Set(manifest.outputs.filter((x) => x.family === 'pimm30').map((x) => x.asset)).size, 22);
  assert.equal(new Set(manifest.outputs.filter((x) => x.family === 'pimm50').map((x) => x.asset)).size, 10);
  assert.equal(manifest.studios.pimm30Startup, 'dark');
  assert.equal(manifest.studios.pimm30Presentation, 'bright');
  assert.equal(manifest.studios.pimm50, 'bright');
  for (const source of manifest.sources) {
    assert.match(source.sha256, /^[A-F0-9]{64}$/);
    assert.ok(source.byteLength > 0);
    assert.notEqual(source.path, source.target);
  }
  const template = await readFile(new URL('../../templates/product.injection-molding-machine.json', import.meta.url), 'utf8');
  const section = await readFile(new URL('../../sections/maliev-pimm-50g-launch.liquid', import.meta.url), 'utf8');
  for (const output of manifest.outputs) {
    const consumerSource = output.consumer === 'pimm30-template' ? template : section;
    const reference = output.replaces ?? output.asset;
    assert.ok(consumerSource.includes(reference), `${output.consumer}: ${reference}`);
  }
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `node --test scripts/tests/pimm-rendering-system-contract.test.mjs`

Expected: FAIL with `ENOENT` for `pimm_active_render_manifest.json`.

- [ ] **Step 3: Write the exact manifest**

Use these immutable source records:

```json
{
  "version": 1,
  "studios": {
    "pimm30Startup": "dark",
    "pimm30Presentation": "bright",
    "pimm50": "bright"
  },
  "sources": [
    {
      "id": "pimm30-story",
      "path": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-30g-product-story-v10-safe-framing.blend",
      "sha256": "83A42DF08EA42837044E054C12D066009633441BF72F5F73CD8FC2E2BA8A9201",
      "byteLength": 199354059,
      "target": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-30g-calibrated-studio-v1.blend"
    },
    {
      "id": "pimm30-capacity-scale",
      "path": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-30g-capacity-scale.blend",
      "sha256": "E7D36EE305E9CB0386AD920DE9FD0A59A5007AA24BED7EE6DF7153441E486006",
      "byteLength": 314779,
      "target": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-30g-capacity-scale-calibrated-v1.blend"
    },
    {
      "id": "pimm30-temperature",
      "path": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-30g-temperature-sequence-closeup-v3.blend",
      "sha256": "2A71EA61DB5D6D651115FF5565BDDAD86F1D3117D08A8C8F1DD572D046B78895",
      "byteLength": 100871991,
      "target": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-30g-temperature-calibrated-v1.blend"
    },
    {
      "id": "pimm30-cylinder",
      "path": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-30g-product-story-v11-cylinder-framing.blend",
      "sha256": "9231A7CB1E123531A1F392BB213749837A0B7263553E39B5DADC2591BDDD6D8D",
      "byteLength": 199081058,
      "target": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-30g-cylinder-calibrated-v1.blend"
    },
    {
      "id": "pimm30-operation",
      "path": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-30g-direct-operation-toggle-v1.blend",
      "sha256": "835D998205C29B35B05756183BFB8D622E06BC05F4667B21D74FAA70F958377D",
      "byteLength": 101211488,
      "target": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-30g-direct-operation-calibrated-v1.blend"
    },
    {
      "id": "pimm30-pressure",
      "path": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-30g-product-story-v14-pressure-framing.blend",
      "sha256": "C9560075DA9323CD09612CEF59E25FACE535B7134879C086594EE04E893C3F1D",
      "byteLength": 199077982,
      "target": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-30g-pressure-calibrated-v1.blend"
    },
    {
      "id": "pimm30-configuration",
      "path": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-30g-configuration-turntable.blend",
      "sha256": "F09F60B5BA3AD6F35C5FEB7F7270142C35DFB8E3B181695DC34764AEB7250D7F",
      "byteLength": 100891724,
      "target": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-30g-configuration-calibrated-v1.blend"
    },
    {
      "id": "pimm50",
      "path": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-50g-keynote-reveal-v2-regulator-materials.blend",
      "sha256": "C19DDA7902BE63A2B28A77D3EF349D17555642399A9589B9A06EFCC05EAB882A",
      "byteLength": 198333166,
      "target": "M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\PIMM-50g-calibrated-studio-v2.blend"
    }
  ]
}
```

Add the 22 exact 30G output names from `templates/product.injection-molding-machine.json`, the six exact 50G names from `sections/maliev-pimm-50g-launch.liquid`, and four new `pimm50-next-model-bright-*` desktop/mobile animation/poster names whose `consumer` is the 30G template. Record required dimensions, source scene, poster frame, fps, duration, alpha codec, master glob, and proof output name. Do not include an unreferenced asset. The manifest contract must allow the four new names to be absent from the pre-change template and require the promotion step to introduce those exact references atomically.

- [ ] **Step 4: Run focused GREEN**

Run: `node --test scripts/tests/pimm-rendering-system-contract.test.mjs`

Expected: PASS.

- [ ] **Step 5: Commit the frozen contract**

```powershell
git add -- scripts/blender/pimm_active_render_manifest.json scripts/tests/pimm-rendering-system-contract.test.mjs
git commit -m "Freeze active PIMM render contracts"
```

---

### Task 2: Build the shared calibrated material and studio module

**Files:**
- Create: `scripts/blender/pimm_rendering_system.py`
- Modify: `scripts/tests/pimm-rendering-system-contract.test.mjs`

**Interfaces:**
- Produces: `MaterialProfile`, `StudioProfile`, `configure_cycles(scene, profile)`, `build_material_library(prefix)`, `assign_material_families(collection, rules, library)`, `build_bright_studio(scene, collection, target)`, `build_dark_startup_studio(scene, collection, target)`, `build_physical_shadow_catcher(scene, collection, bounds)`, and `validate_render_contract(scene, collection, contract)`.
- Consumes: manifest source/output contracts from Task 1.

- [ ] **Step 1: Add failing shared-system assertions**

```js
test('shared rendering system owns physical materials studios and shadow catching', async () => {
  const source = await readFile(new URL('../blender/pimm_rendering_system.py', import.meta.url), 'utf8');
  for (const symbol of [
    'MaterialProfile', 'StudioProfile', 'configure_cycles', 'build_material_library',
    'assign_material_families', 'build_bright_studio', 'build_dark_startup_studio',
    'build_physical_shadow_catcher', 'validate_render_contract'
  ]) assert.match(source, new RegExp(`(?:class|def) ${symbol}\\b`));
  assert.match(source, /shadow_catcher\s*=\s*True/);
  assert.match(source, /film_transparent\s*=\s*True/);
  assert.match(source, /color_depth\s*=\s*["']16["']/);
  assert.doesNotMatch(source, /ShaderNodeMapRange[\s\S]{0,900}SHADOW_ALPHA_FADE/);
});
```

- [ ] **Step 2: Run RED**

Run: `node --test scripts/tests/pimm-rendering-system-contract.test.mjs`

Expected: FAIL because `pimm_rendering_system.py` does not exist.

- [ ] **Step 3: Implement the material profiles**

Implement immutable profiles with Principled BSDF parameters and bounded procedural microstructure:

```python
MATERIAL_PROFILES = {
    "cnc_milled_aluminum": MaterialProfile(base=(0.78, 0.80, 0.82, 1), metallic=1.0, roughness=0.20, anisotropic=0.24, texture_scale=950.0, texture_strength=0.025),
    "cast_aluminum": MaterialProfile(base=(0.67, 0.69, 0.71, 1), metallic=1.0, roughness=0.31, anisotropic=0.04, texture_scale=145.0, texture_strength=0.035),
    "polished_shaft": MaterialProfile(base=(0.86, 0.88, 0.90, 1), metallic=1.0, roughness=0.075, anisotropic=0.08, texture_scale=0.0, texture_strength=0.0),
    "brushed_sheet": MaterialProfile(base=(0.69, 0.71, 0.73, 1), metallic=1.0, roughness=0.24, anisotropic=0.38, texture_scale=720.0, texture_strength=0.018),
}
```

Keep tubing, rubber, plastics, glass, displays, springs, labels, and decals as dielectric or emissive families. Reuse verified image textures and never synthesize branding with text overlays.

- [ ] **Step 4: Implement the two studio profiles**

The bright profile uses four large area sources and explicit white/dark reflection cards. Start from this bounded ratio and tune only during proof review:

```python
BRIGHT_STUDIO = StudioProfile(
    world_strength=0.22,
    exposure=0.0,
    key_energy=520.0,
    fill_energy=390.0,
    rim_energy=310.0,
    top_energy=240.0,
    look="AgX - Medium High Contrast",
)
DARK_STARTUP_STUDIO = StudioProfile(
    world_strength=0.008,
    exposure=-0.35,
    key_energy=90.0,
    fill_energy=65.0,
    rim_energy=220.0,
    top_energy=45.0,
    look="AgX - Medium High Contrast",
)
```

Use reflection cards that are visible to glossy rays but hidden from camera rays. Cards may shape shaft highlights but may not occlude the product or become visible in alpha.

- [ ] **Step 5: Implement physical shadow catching and render settings**

Create a plane larger than the computed product and shadow bounds, set `is_shadow_catcher = True`, enable transparent film and transparent-glass support, and keep the catcher outside the camera-visible alpha except for its physical shadow contribution. Configure 16-bit RGBA PNG masters, 256 final samples, adaptive threshold `0.01`, and denoising with normal/albedo passes. Proof renders may use 64 samples but may not be promoted.

- [ ] **Step 6: Run compile and focused GREEN**

Run:

```powershell
python -m py_compile scripts/blender/pimm_rendering_system.py
node --test scripts/tests/pimm-rendering-system-contract.test.mjs
```

Expected: both PASS.

- [ ] **Step 7: Commit the shared system**

```powershell
git add -- scripts/blender/pimm_rendering_system.py scripts/tests/pimm-rendering-system-contract.test.mjs
git commit -m "Build calibrated PIMM studio system"
```

---

### Task 3: Build and render the PIMM 30G proof package

**Files:**
- Create: `scripts/blender/create_pimm30_calibrated_studio.py`
- Create: `scripts/tests/pimm30-calibrated-blender.test.mjs`
- Modify: `scripts/blender/create_pimm30_direct_operation_toggle.py`
- Test: `scripts/tests/pimm30-presentation-regressions.test.mjs`

**Interfaces:**
- Consumes: shared API and manifest from Tasks 1–2.
- Produces: versioned 30G calibrated target blends and proof directory `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\pimm30-calibrated-v1\proofs`.
- Produces: `pimm30-bright-hero.exr/png`, `pimm30-material-closeup.exr/png`, and dark-startup frames `0001`, illumination midpoint, bright-transition endpoint.

- [ ] **Step 1: Write failing 30G builder tests**

Assert source hashes, target names, `PIMM30_CAL_` ownership prefix, bright and dark scene names, shared-module import, source immutability, physical shadow catcher, exact controller/decal preservation, 30G operation frame range, and poster/animation parity. Reject writes to any source path.

- [ ] **Step 2: Run RED**

Run: `node --test scripts/tests/pimm30-calibrated-blender.test.mjs`

Expected: FAIL because the builder does not exist and the operation builder does not consume the shared system.

- [ ] **Step 3: Implement idempotent 30G scene ownership**

Clone only source-owned product collections into `PIMM30_CAL_*` scenes. Build:

- `PIMM30_CAL_BRIGHT_HERO_PROOF`
- `PIMM30_CAL_MATERIAL_CLOSEUP_PROOF`
- `PIMM30_CAL_DARK_STARTUP_PROOF`
- Production scenes for overview, capacity, temperature, cylinder, operation, regulator, fixture, scale, and configuration.

Map verified cylinder caps to `cast_aluminum`, plates/blocks to `cnc_milled_aluminum`, rods/shafts/fasteners to `polished_shaft`, and controller/enclosure panels to `brushed_sheet`. Require an explicit mapping report; fail if a product metal remains assigned to an unclassified fallback.

- [ ] **Step 4: Integrate the operation animation without changing mechanics**

Replace inherited/local lighting and output setup in `create_pimm30_direct_operation_toggle.py` with the shared system. Keep the exact handle pivot, tilt-only movement, 200 mm plunger travel, controller digits, AIRTAC decal, frame timing, and source immutability contracts already covered by `pimm30-presentation-regressions.test.mjs`.

- [ ] **Step 5: Run compile and contract GREEN**

```powershell
python -m py_compile scripts/blender/pimm_rendering_system.py scripts/blender/create_pimm30_calibrated_studio.py scripts/blender/create_pimm30_direct_operation_toggle.py
node --test scripts/tests/pimm30-calibrated-blender.test.mjs scripts/tests/pimm30-presentation-regressions.test.mjs
```

Expected: PASS before rendering.

- [ ] **Step 6: Render the representative proof package**

Run Blender 5.2 from its verified installation:

```powershell
& 'D:\Blender 5.2\blender.exe' -b 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\PIMM-30g-product-story-v10-safe-framing.blend' -P 'scripts\blender\create_pimm30_calibrated_studio.py' -- --render-proofs
```

Expected: source hash/mtime unchanged, versioned targets saved, high-bit-depth masters and four-background composites emitted, summary marker printed.

- [ ] **Step 7: Inspect the 30G proofs at native resolution**

Inspect the hero, material close-up, darkest startup, illumination midpoint, and bright endpoint. Record in the task report:

- CNC/cast/polished/brushed separation.
- No clipped broad highlights.
- Readable shadow-side detail.
- Continuous shaft gradients.
- Complete contact/ambient shadow.
- No alpha halo or plane edge on four backgrounds.
- Exact dark-startup-to-bright endpoint framing.

- [ ] **Step 8: Stop for explicit proof approval**

Present the composited proofs to the user. Do not render the remaining 30G production assets until the user accepts the material, exposure, reflection, and shadow standard.

- [ ] **Step 9: Apply only approved bounded tuning and rerender proofs**

If rejected, adjust only shared profiles/reflection-card positions or explicit material mappings. Rerun Steps 5–8 until approved. Never compensate using post-render masks or per-image exposure patches.

- [ ] **Step 10: Commit the approved 30G pipeline**

```powershell
git add -- scripts/blender/create_pimm30_calibrated_studio.py scripts/blender/create_pimm30_direct_operation_toggle.py scripts/tests/pimm30-calibrated-blender.test.mjs scripts/tests/pimm30-presentation-regressions.test.mjs
git commit -m "Calibrate PIMM 30G product rendering"
```

---

### Task 4: Build and render the PIMM 50G proof package

**Files:**
- Modify: `scripts/blender/create_pimm50_light_studio.py`
- Modify: `scripts/tests/pimm50-light-studio-blender.test.mjs`
- Modify: `scripts/tests/pimm50-light-studio-assets.test.mjs`

**Interfaces:**
- Consumes: the proof-approved shared system from Tasks 2–3.
- Produces: `PIMM-50g-calibrated-studio-v2.blend` and proof directory `renders\pimm50-calibrated-v2\proofs`.
- Produces: bright hero, material close-up, hero animation endpoints, heating animation endpoints, and bright desktop/mobile next-model animation endpoints plus matching posters.

- [ ] **Step 1: Change the 50G tests to require the shared calibrated system**

Assert target `PIMM-50g-calibrated-studio-v2.blend`, shared-module import, bright-only scenes, physical shadow catching, 16-bit masters, 256 final samples, all six dedicated-page production scenes, bright desktop/mobile next-model scenes, hero/heating/next-model animations, poster isolation, comprehensive endpoint parity, and unchanged source hash.

- [ ] **Step 2: Run RED**

Run:

```powershell
node --test scripts/tests/pimm50-light-studio-blender.test.mjs scripts/tests/pimm50-light-studio-assets.test.mjs
```

Expected: FAIL because the builder still owns its local 48-sample, negative-exposure, synthetic-shadow system and v1 target.

- [ ] **Step 3: Refactor the 50G builder onto the shared system**

Remove local `create_world`, `create_lighting`, `create_shadow_catcher`, and `create_shadow_material`. Import the shared API, map the verified 50G material families, retain all six dedicated-page camera specifications and hero/heating mechanics, add bright desktop/mobile next-model cameras and animation outputs, and add `PIMM50_CAL_MATERIAL_CLOSEUP_PROOF`. All 50G scenes must request `BRIGHT_STUDIO`; reject a dark-studio selection in `assert_scene_contract`.

- [ ] **Step 4: Run compile and contract GREEN**

```powershell
python -m py_compile scripts/blender/pimm_rendering_system.py scripts/blender/create_pimm50_light_studio.py
node --test scripts/tests/pimm50-light-studio-blender.test.mjs
```

Expected: PASS.

- [ ] **Step 5: Render the 50G proof package**

```powershell
& 'D:\Blender 5.2\blender.exe' -b 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\PIMM-50g-keynote-reveal-v2-regulator-materials.blend' -P 'scripts\blender\create_pimm50_light_studio.py' -- --render-proofs
```

Expected: fourteen or more RGBA proofs including full-machine, material close-up, hero endpoints, heating endpoints, desktop/mobile next-model endpoints, source immutability summary, and persisted-target reopen parity.

- [ ] **Step 6: Inspect native-resolution 50G proofs**

Verify the same material/exposure/reflection/shadow criteria as 30G, plus 350°C controller legibility and bright-only lighting across every endpoint.

- [ ] **Step 7: Stop for explicit 50G proof approval**

Present the proof composites. Do not promote any 50G storefront asset before acceptance.

- [ ] **Step 8: Apply approved bounded tuning and rerender**

Keep the already approved shared material values stable unless the same physical finish demonstrably differs between machines. Scene-specific changes may adjust reflection-card placement or verified material assignments, not global tone matching by eye.

- [ ] **Step 9: Commit the approved 50G pipeline**

```powershell
git add -- scripts/blender/create_pimm50_light_studio.py scripts/tests/pimm50-light-studio-blender.test.mjs scripts/tests/pimm50-light-studio-assets.test.mjs
git commit -m "Calibrate PIMM 50G product rendering"
```

---

### Task 5: Add objective proof-quality and temporal validation

**Files:**
- Create: `scripts/tests/pimm-calibrated-proof-quality.test.mjs`
- Modify: `scripts/blender/pimm_rendering_system.py`

**Interfaces:**
- Consumes: approved proof roots and proof-derived threshold records from Tasks 3–4.
- Produces: reusable `proof-quality.json` summaries for each scene and animation frame.

- [ ] **Step 1: Write failing image-quality tests**

Use Pillow/OpenImageIO through a Python probe launched from Node. For every approved proof, assert:

```js
assert.equal(result.mode, 'RGBA');
assert.ok(result.alphaBounds);
assert.ok(result.clearance.left >= result.requiredClearancePx);
assert.ok(result.clearance.right >= result.requiredClearancePx);
assert.ok(result.clearance.bottom >= result.requiredShadowClearancePx);
assert.ok(result.highlightClipRatio <= 0.003);
assert.ok(result.shadowCrushRatio <= 0.015);
assert.ok(result.shadowAlphaHasSoftTail);
assert.equal(result.shadowHasRectangularBoundary, false);
assert.ok(result.materialMedianLuma.polished_shaft > result.materialMedianLuma.cast_aluminum);
assert.ok(result.temporalP95Delta <= result.approvedTemporalLimit);
```

Derive the numerical luma/temporal thresholds from accepted proofs and store them in the manifest; do not invent a threshold after production rendering.

- [ ] **Step 2: Run RED against the old proofs**

Run: `node --test scripts/tests/pimm-calibrated-proof-quality.test.mjs`

Expected: FAIL on missing summaries and at least the old 50G shadow/exposure/material checks.

- [ ] **Step 3: Implement proof statistics and four-background composites**

Add reusable Blender/Python helpers that calculate alpha bounds, soft-shadow falloff, bright/dark pixel ratios, material mask statistics from Cryptomatte/material-index passes, and frame-to-frame reflection stability. Generate white, `#f3f5f6`, `#202428`, and checkerboard composites without modifying master pixels.

- [ ] **Step 4: Run GREEN on approved 30G and 50G proofs**

Run: `node --test scripts/tests/pimm-calibrated-proof-quality.test.mjs`

Expected: PASS with a JSON summary for every required proof/frame.

- [ ] **Step 5: Commit the quality gate**

```powershell
git add -- scripts/blender/pimm_rendering_system.py scripts/tests/pimm-calibrated-proof-quality.test.mjs scripts/blender/pimm_active_render_manifest.json
git commit -m "Verify PIMM render quality objectively"
```

---

### Task 6: Batch-render active masters and create storefront derivatives

**Files:**
- Create: `scripts/render/promote_pimm_calibrated_media.ps1`
- Modify: `scripts/tests/pimm-rendering-system-contract.test.mjs`
- Generate: versioned master/proof directories on `M:`
- Generate: only manifest-listed files under `assets/`

**Interfaces:**
- Consumes: approved builders, target blends, manifest, and quality thresholds.
- Produces: atomic 32-file storefront promotion set plus endpoint thumbnails, media metadata report, and the four corresponding next-model reference updates in the 30G template.

- [ ] **Step 1: Write the failing promotion contract**

Assert the PowerShell script:

- Reads the JSON manifest.
- Refuses missing/unapproved quality summaries.
- Refuses source/storefront filename drift.
- Uses `ffmpeg` VP9 `yuva420p` alpha for WebM.
- Uses lossless WebP for approved still promotion unless the manifest explicitly permits quality compression.
- Writes to a temporary staging directory and atomically replaces only after all 32 files validate.
- Has `-ValidateOnly`, `-Family pimm30|pimm50|all`, and `-NoPromote` switches.

- [ ] **Step 2: Run RED**

Run: `node --test scripts/tests/pimm-rendering-system-contract.test.mjs`

Expected: FAIL because the promotion script does not exist.

- [ ] **Step 3: Implement manifest-driven staging and encoding**

For WebM use manifest dimensions/fps and an alpha-preserving command equivalent to:

```powershell
ffmpeg -framerate $fps -i $frameGlob -c:v libvpx-vp9 -pix_fmt yuva420p -auto-alt-ref 0 -lossless 1 -metadata:s:v:0 alpha_mode=1 $stagedOutput
```

For WebP use Pillow lossless RGBA conversion from the approved poster master. Validate dimensions, alpha bounds, media duration, frame count, and endpoint pixel parity before promotion.

- [ ] **Step 4: Run validate-only GREEN**

```powershell
pwsh ./scripts/render/promote_pimm_calibrated_media.ps1 -Family all -ValidateOnly -NoPromote
```

Expected: PASS and report exactly 22 30G plus ten 50G outputs.

- [ ] **Step 5: Run full high-quality production rendering**

Run each manifest source through its builder with `--render-production`. Capture actual GPU/CPU backend, time, samples, frame count, and output list. Do not parallelize multiple Cycles jobs onto the same GPU.

- [ ] **Step 6: Re-run proof-quality validation on production masters**

```powershell
node --test scripts/tests/pimm-calibrated-proof-quality.test.mjs
```

Expected: PASS for all promoted sources and animation endpoints.

- [ ] **Step 7: Promote the staged derivatives**

```powershell
pwsh ./scripts/render/promote_pimm_calibrated_media.ps1 -Family all
```

Expected: 32 validated atomic replacements, no unreferenced legacy file modifications, and only the four manifest-declared bright next-model reference changes in the 30G template.

- [ ] **Step 8: Run focused asset tests**

```powershell
node --test scripts/tests/pimm30-presentation-regressions.test.mjs scripts/tests/pimm50-light-studio-assets.test.mjs scripts/tests/pimm-calibrated-proof-quality.test.mjs
```

Expected: PASS.

- [ ] **Step 9: Commit the generated assets and promotion tooling**

Stage only the script, tests, manifest adjustments, 32 manifest-listed assets, and the four next-model template reference changes. Verify `git diff --cached --name-only` contains no legacy unreferenced media.

```powershell
git commit -m "Regenerate calibrated PIMM storefront media"
```

---

### Task 7: Validate storefront behavior across both products

**Files:**
- Modify only if validation exposes an asset-contract defect: `templates/product.injection-molding-machine.json`, `sections/maliev-pimm-50g-launch.liquid`, or PIMM CSS/JS.
- Test: all `scripts/tests/pimm30-*.test.mjs` and `scripts/tests/pimm50-*.test.mjs`.

**Interfaces:**
- Consumes: promoted media from Task 6.
- Produces: final responsive, reduced-motion, commerce, focus, and media-integrity evidence.

- [ ] **Step 1: Run all focused PIMM tests**

```powershell
node --test scripts/tests/pimm30-*.test.mjs scripts/tests/pimm50-*.test.mjs scripts/tests/pimm-rendering-system-contract.test.mjs scripts/tests/pimm-calibrated-proof-quality.test.mjs
```

Expected: all PASS.

- [ ] **Step 2: Run Shopify static validation**

```powershell
npm run verify
git diff --check
```

Expected: Theme Check has zero errors and `git diff --check` is clean.

- [ ] **Step 3: Run the existing live responsive matrix**

With `npm run dev` already serving the preview, run:

```powershell
node --test scripts/tests/pimm50-responsive-browser.test.mjs
```

Run the existing 30G browser/geometry validation command identified in `scripts/tests/pimm30-presentation-regressions.test.mjs` and its companion harness. Required widths/heights include 320×568, 384×824, 390×844, 430×932, 540×720, 720×540, 768×1024, 820×1180, 1024×768, 1440×900, and 3840×2160.

- [ ] **Step 4: Visually inspect live 30G and 50G routes**

At desktop, tablet portrait, phone portrait, and short landscape verify:

- No machine or shadow clipping.
- Poster/video transition does not flash, resize, or shift.
- 30G startup is dark and all later 30G assets are bright.
- Every 50G asset is bright studio, including the next-model media embedded on the 30G route.
- Alpha media works over its real page background without white boxes or halos.
- Machine materials remain consistent between chapters.
- Reduced motion shows the approved matching poster.
- Existing content, commerce controls, and focus treatment remain functional.

- [ ] **Step 5: Fix only proven asset-contract regressions with TDD**

If a validation failure requires CSS/Liquid/JS changes, first add a focused failing assertion to the relevant existing test, make the minimal correction, rerun the focused test and full PIMM suite, and commit separately as:

```powershell
git commit -m "Harden PIMM calibrated media presentation"
```

Do not use CSS masks or clipping to hide render defects; correct the master render instead.

- [ ] **Step 6: Produce the completion report**

Report actual proof/render commands, render device, sample counts, render duration, 32 promoted filenames, test totals, Theme Check result, browser matrix, native-resolution inspection, commits, and any residual external Shopify/browser errors. State explicitly that no push or deployment occurred.

---

### Task 8: Final review and branch completion decision

**Files:**
- Read: all commits and validation reports produced by Tasks 1–7.

**Interfaces:**
- Consumes: fully validated branch.
- Produces: user-reviewed final state with no deployment.

- [ ] **Step 1: Invoke `superpowers:requesting-code-review`**

Request a scope/contract review covering immutable sources, material/studio consistency, proof quality, animation parity, manifest-only promotion, and storefront regression evidence.

- [ ] **Step 2: Resolve every Critical or Important finding**

Use `superpowers:receiving-code-review`, reproduce each finding, add a failing regression where applicable, implement the minimal correction, and rerun the affected and full suites.

- [ ] **Step 3: Invoke `superpowers:verification-before-completion`**

Rerun the complete final gate from a clean process state. Do not rely on earlier task output.

- [ ] **Step 4: Use `superpowers:finishing-a-development-branch`**

Present the validated branch options. Because this request does not authorize pushing or deployment, do not push, create a PR, merge, or deploy without a new explicit instruction.
