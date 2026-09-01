# PIMM Dedicated Collection Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dedicated, full-page 30G/50G collection comparison with model-specific Blender angle sequences, a sticky active-model dossier, and direct routing into the unified PIMM configurator.

**Architecture:** A dedicated alternate collection template renders one focused comparison section instead of the generic collection banner/grid. The section reads the canonical unified PIMM product through a Shopify product setting, validates its exact `Model = 30G, 50G` contract in Liquid, and exposes one JSON payload to a scoped custom-element controller. A separate Blender renderer/finalizer publishes three collection-only physical studio frames per model; the controller plays the five-state sequence `front → left → front → right → front` without duplicating an image across storefront locations.

**Tech Stack:** Shopify Online Store 2.0 Liquid/JSON templates, vanilla CSS, vanilla JavaScript custom elements, Node.js 20 test runner, Blender 5.2/Cycles, Python 3/Pillow, Shopify CLI Theme Check, Chrome DevTools Protocol browser validation.

**Spec:** `docs/superpowers/specs/2026-09-01-pimm-dedicated-collection-design.md`

## Global Constraints

- Keep `templates/collection.json` and all non-PIMM collection behavior unchanged.
- Resolve models by exact option values `30G` and `50G`; never use product ordering, titles, prices, or hardcoded variant IDs as identity.
- Read full machine price only from `variant.metafields.custom.full_machine_price.value` and lead time only from `variant.metafields.custom.lead_time_days.value`.
- Read technical facts only from the version-1 `variant.metafields.custom.pimm_specifications.value` contract.
- Route each CTA to the canonical unified product URL with Shopify's `?variant=<id>` parameter.
- Bind the alternate template to the current canonical development handle `pimm-pneumatic-injection-molding-machine-development`; production publication and handle migration remain separate operations.
- Use authoritative masters `PIMM-30G-MASTER.blend` and `PIMM-50G-MASTER.blend` with their currently locked SHA-256 values.
- Publish collection-only media; do not reuse homepage, catalogue, navigation, or product-story assets.
- Do not create fake perspective, mirrored frames, post-render floor composites, or artificial machine shadows.
- Preserve one `h1`, keyboard access, visible focus, 44px touch targets, Thai/English parity, reduced-motion behavior, and zero horizontal overflow.
- The header is transparent over the opening stage and becomes solid white after its overlay sentinel crosses the existing header threshold.
- Do not push, deploy, assign the template in production, alter Shopify merchant settings, or publish the draft unified product in this plan.

## File map

### Create

- `scripts/blender/pimm_production/blender_collection_card_render.py` — render front, left, and right physical studio frames from one opened authoritative master.
- `scripts/blender/pimm_production/finalize_collection_card_assets.py` — validate native outputs, create lossless WebPs, and write the hash-locked collection manifest.
- `scripts/blender/pimm_production/tests/test_collection_card_render.py` — renderer/finalizer contract tests that do not require a full production render.
- `scripts/tests/pimm-collection-card-assets.test.mjs` — repository-level asset provenance, uniqueness, dimensions, and usage tests.
- `scripts/tests/pimm-collection-page-contract.test.mjs` — Liquid/template/header/localization contract tests.
- `scripts/tests/pimm-collection-interaction.test.mjs` — custom-element state and animation tests using a deterministic VM DOM fixture.
- `scripts/tests/pimm-collection-responsive-browser.test.mjs` — opt-in CDP validation for geometry, interaction, routing, images, and header transition.
- `sections/maliev-pimm-collection.liquid` — canonical product validation, semantic card/dossier markup, JSON payload, schema, and structured data.
- `assets/maliev-pimm-collection.css` — dedicated desktop, tablet, mobile, focus, active, and reduced-motion presentation.
- `assets/maliev-pimm-collection.js` — scoped active-model and frame-sequence controller.
- `templates/collection.pimm-machines.json` — alternate collection template containing only the dedicated section.
- `assets/maliev-pimm-collection-assets.v1.json` — published collection render manifest.
- `assets/maliev-pimm-collection-20260901-r01-{30g,50g}-{front,left,right}.{png,webp}` — twelve native/storefront assets.

### Modify

- `sections/maliev-header.liquid` — enable the existing overlay header contract for `collection.pimm-machines`.
- `locales/en.default.json` — English comparison copy.
- `locales/th.json` — Thai comparison copy with information parity.
- `scripts/tests/pimm-unified-story-assets.test.mjs` — scope the unified-story family assertion so a separately manifested collection family is allowed.
- `package.json` — add the new non-browser collection tests to `verify:render-assets`.

---

### Task 1: Collection Blender renderer and publication contract

**Files:**
- Create: `scripts/blender/pimm_production/blender_collection_card_render.py`
- Create: `scripts/blender/pimm_production/finalize_collection_card_assets.py`
- Create: `scripts/blender/pimm_production/tests/test_collection_card_render.py`

**Interfaces:**
- Consumes: an opened authoritative machine master, `--machine`, `--expected-master-sha256`, `--output-dir`, `--samples`, and optional `--scale`.
- Produces: three 1200×1600 16-bit RGB PNG files per model named `maliev-pimm-collection-20260901-r01-<model>-<angle>.png`.
- Produces: `publish(render_dir: Path, asset_dir: Path, samples: int) -> dict[str, object]` in the finalizer.
- Angle contract: `ANGLE_DEGREES = {"front": 0.0, "left": -12.0, "right": 12.0}`.

- [ ] **Step 1: Write failing renderer/finalizer tests**

```python
class CollectionCardContractTests(unittest.TestCase):
    def test_angle_contract_is_small_symmetric_and_front_resting(self):
        self.assertEqual(renderer.ANGLE_DEGREES, {"front": 0.0, "left": -12.0, "right": 12.0})
        self.assertEqual(renderer.OUTPUT_DIMENSIONS, (1200, 1600))

    def test_finalizer_publishes_lossless_native_and_storefront_records(self):
        for model in ("30g", "50g"):
            for angle in ("front", "left", "right"):
                Image.new("RGB", (1200, 1600), (240, 241, 243)).save(
                    self.render_dir / f"{finalizer.RELEASE_ID}-{model}-{angle}.png"
                )
        manifest = finalizer.publish(self.render_dir, self.asset_dir, samples=256)
        self.assertEqual(len(manifest["assets"]), 6)
        self.assertEqual({record["angle_degrees"] for record in manifest["assets"]}, {0.0, -12.0, 12.0})
        self.assertEqual(len({record["storefront"]["filename"] for record in manifest["assets"]}), 6)

    def test_finalizer_rejects_wrong_dimensions(self):
        self._write_complete_fixture()
        Image.new("RGB", (1199, 1600)).save(
            self.render_dir / f"{finalizer.RELEASE_ID}-30g-front.png"
        )
        with self.assertRaisesRegex(ValueError, "unexpected collection render dimensions"):
            finalizer.publish(self.render_dir, self.asset_dir, samples=256)
```

- [ ] **Step 2: Run the tests and confirm the new modules are missing**

Run:

```powershell
py -3 -m unittest scripts.blender.pimm_production.tests.test_collection_card_render -v
```

Expected: FAIL because `blender_collection_card_render` and `finalize_collection_card_assets` do not exist.

- [ ] **Step 3: Implement the renderer contract**

Use these exact public constants and CLI fields:

```python
RELEASE_ID = "maliev-pimm-collection-20260901-r01"
RESULT_MARKER = "MALIEV_PIMM_COLLECTION_RENDER_JSON="
OUTPUT_DIMENSIONS = (1200, 1600)
ANGLE_DEGREES = {"front": 0.0, "left": -12.0, "right": 12.0}
MASTER_HASHES = {
    "30G": "98577604BB25033B5A7229A66A14D12703E6636DF6B064F877DF7EFC6E65CEFA",
    "50G": "CC26246CD01956B1145B1AA5744B968918F956B667B720205723E6B60A252D90",
}
```

The renderer must reuse the established master validation, world-bounds, physical cyclorama, and softbox patterns from `blender_master_storefront_render.py`, but it must own a collection-specific vertical camera and may not modify that existing renderer.

For each angle:

```python
stage.rotation_euler[2] = math.radians(ANGLE_DEGREES[angle])
scene.render.resolution_x, scene.render.resolution_y = OUTPUT_DIMENSIONS
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.image_settings.color_depth = "16"
scene.render.film_transparent = False
```

The physical floor/cyclorama must extend at least 30 machine extents laterally and toward the camera. It remains a visible diffuse receiver, not a shadow catcher. Camera, focal length, exposure, target, and light transforms remain identical across all three angles for a model.

- [ ] **Step 4: Implement the finalizer contract**

The finalizer must:

```python
def publish(render_dir: Path, asset_dir: Path, samples: int) -> dict[str, object]:
    # Require all six expected RGB PNGs at exactly 1200x1600.
    # Copy each native PNG into assets/.
    # Save a lossless WebP derivative with method=6.
    # Record SHA-256, dimensions, model, angle, and angle_degrees.
    # Write assets/maliev-pimm-collection-assets.v1.json.
```

The manifest includes `schema_version: 1`, both locked master records, renderer/finalizer paths, `shadow_source: "Blender Cycles physical studio floor; no post-render shadow compositing"`, and six asset records.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
py -3 -m unittest scripts.blender.pimm_production.tests.test_collection_card_render -v
```

Expected: all tests PASS.

- [ ] **Step 6: Run static validation**

Run:

```powershell
py -3 -m py_compile scripts\blender\pimm_production\blender_collection_card_render.py scripts\blender\pimm_production\finalize_collection_card_assets.py
git diff --check
```

Expected: both commands exit 0.

- [ ] **Step 7: Commit the render pipeline**

```powershell
git add -- scripts/blender/pimm_production/blender_collection_card_render.py scripts/blender/pimm_production/finalize_collection_card_assets.py scripts/blender/pimm_production/tests/test_collection_card_render.py
git commit -m "Add PIMM collection render pipeline"
```

---

### Task 2: Render and publish the six dedicated collection views

**Files:**
- Create: `assets/maliev-pimm-collection-assets.v1.json`
- Create: `assets/maliev-pimm-collection-20260901-r01-30g-{front,left,right}.{png,webp}`
- Create: `assets/maliev-pimm-collection-20260901-r01-50g-{front,left,right}.{png,webp}`
- Create: `scripts/tests/pimm-collection-card-assets.test.mjs`
- Modify: `scripts/tests/pimm-unified-story-assets.test.mjs`
- Modify: `package.json`

**Interfaces:**
- Consumes: Task 1's renderer, finalizer, exact release ID, filenames, and manifest schema.
- Produces: twelve repository assets and a manifest whose six storefront records are consumed by `maliev-pimm-collection.liquid`.

- [ ] **Step 1: Write the failing repository asset test**

```javascript
test('collection cards use six unique purpose-rendered Blender views', async () => {
  const manifest = JSON.parse(await readFile(new URL('../../assets/maliev-pimm-collection-assets.v1.json', import.meta.url)));
  assert.equal(manifest.release_id, 'maliev-pimm-collection-20260901-r01');
  assert.equal(manifest.assets.length, 6);
  assert.deepEqual(
    manifest.assets.map(({ model, angle }) => `${model}:${angle}`).toSorted(),
    ['30g:front', '30g:left', '30g:right', '50g:front', '50g:left', '50g:right'],
  );
  assert.equal(new Set(manifest.assets.map(({ storefront }) => storefront.filename)).size, 6);
  assert.equal(manifest.shadow_source, 'Blender Cycles physical studio floor; no post-render shadow compositing');
});
```

Also verify every native and storefront hash, exact 1200×1600 dimensions, RGB mode, master hashes, no filename collision with other PIMM manifests, and that the six WebPs are referenced exactly once by the dedicated section.

- [ ] **Step 2: Run the asset test and confirm the manifest is absent**

Run:

```powershell
node --test scripts/tests/pimm-collection-card-assets.test.mjs
```

Expected: FAIL with `ENOENT` for `assets/maliev-pimm-collection-assets.v1.json`.

- [ ] **Step 3: Render the 30G frames from its authoritative master**

```powershell
& 'D:\Blender 5.2\blender.exe' --background 'M:\30_Products\PIMM\blender-product-renders\masters\PIMM-30G-MASTER.blend' --python 'scripts\blender\pimm_production\blender_collection_card_render.py' -- --machine 30G --expected-master-sha256 98577604BB25033B5A7229A66A14D12703E6636DF6B064F877DF7EFC6E65CEFA --output-dir '.codex-tmp\pimm-collection-20260901-r01' --samples 256
```

Expected: marker `MALIEV_PIMM_COLLECTION_RENDER_JSON=` followed by records for `front`, `left`, and `right`.

- [ ] **Step 4: Render the 50G frames from its authoritative master**

```powershell
& 'D:\Blender 5.2\blender.exe' --background 'M:\30_Products\PIMM\blender-product-renders\masters\PIMM-50G-MASTER.blend' --python 'scripts\blender\pimm_production\blender_collection_card_render.py' -- --machine 50G --expected-master-sha256 CC26246CD01956B1145B1AA5744B968918F956B667B720205723E6B60A252D90 --output-dir '.codex-tmp\pimm-collection-20260901-r01' --samples 256
```

Expected: marker `MALIEV_PIMM_COLLECTION_RENDER_JSON=` followed by records for `front`, `left`, and `right`.

- [ ] **Step 5: Publish lossless derivatives and the manifest**

```powershell
py -3 scripts\blender\pimm_production\finalize_collection_card_assets.py --render-dir '.codex-tmp\pimm-collection-20260901-r01' --asset-dir assets --samples 256
```

Expected: twelve image files plus `assets/maliev-pimm-collection-assets.v1.json`.

- [ ] **Step 6: Inspect all six angles before accepting the render**

Create one local contact sheet from the six native PNGs using Pillow for inspection only. Confirm:

- both machines are fully visible and do not intersect the frame;
- the 30G and 50G frames have matching scale/camera behavior within their own sequences;
- the top copy-safe region remains clear;
- the physical floor has no visible edge, band, hard clipping, or artificial compositing;
- metal remains bright and realistic;
- the left/right views are true physical rotations, not mirrored images.

If any check fails, adjust only the new collection renderer and repeat Tasks 1 and 2 validation before publication.

- [ ] **Step 7: Update manifest-family tests and the package verification list**

Change `pimm-unified-story-assets.test.mjs` so its exclusivity assertion filters only `pimm-master-20260901-r05-*` media. Keep its exact placement and no-reuse checks unchanged.

Add to `package.json`:

```json
"verify:render-assets": "node --test scripts/tests/pimm-unified-story-assets.test.mjs scripts/tests/pimm-homepage-assets.test.mjs scripts/tests/pimm-collection-card-assets.test.mjs scripts/tests/product-card-presentation.test.mjs"
```

- [ ] **Step 8: Run asset and regression tests**

```powershell
node --test scripts/tests/pimm-collection-card-assets.test.mjs scripts/tests/pimm-unified-story-assets.test.mjs scripts/tests/pimm-homepage-assets.test.mjs
npm run verify:render-assets
git diff --check
```

Expected: all tests PASS and no whitespace errors.

- [ ] **Step 9: Commit the dedicated render release**

```powershell
git add -- assets/maliev-pimm-collection-assets.v1.json assets/maliev-pimm-collection-20260901-r01-30g-front.png assets/maliev-pimm-collection-20260901-r01-30g-front.webp assets/maliev-pimm-collection-20260901-r01-30g-left.png assets/maliev-pimm-collection-20260901-r01-30g-left.webp assets/maliev-pimm-collection-20260901-r01-30g-right.png assets/maliev-pimm-collection-20260901-r01-30g-right.webp assets/maliev-pimm-collection-20260901-r01-50g-front.png assets/maliev-pimm-collection-20260901-r01-50g-front.webp assets/maliev-pimm-collection-20260901-r01-50g-left.png assets/maliev-pimm-collection-20260901-r01-50g-left.webp assets/maliev-pimm-collection-20260901-r01-50g-right.png assets/maliev-pimm-collection-20260901-r01-50g-right.webp scripts/tests/pimm-collection-card-assets.test.mjs scripts/tests/pimm-unified-story-assets.test.mjs package.json
git commit -m "Publish dedicated PIMM collection renders"
```

---

### Task 3: Server-rendered dedicated collection contract

**Files:**
- Create: `sections/maliev-pimm-collection.liquid`
- Create: `templates/collection.pimm-machines.json`
- Create: `scripts/tests/pimm-collection-page-contract.test.mjs`
- Modify: `locales/en.default.json`
- Modify: `locales/th.json`
- Modify: `package.json`

**Interfaces:**
- Consumes: Task 2's six WebP names and manifest release ID.
- Consumes: `section.settings.pimm_product`, whose exact two variants are identified through `variant.option1` values.
- Produces: `<pimm-collection-comparison data-pimm-collection-comparison>` and `[data-pimm-collection-models]` JSON.
- JSON record shape: `{ id: number, model: "30G"|"50G", url: string, fullPrice: string, available: boolean, leadTime: string, specifications: { shotCapacityG: number, maxMeltTemperatureC: number, moldEnvelopeMm: { width: number, height: number, depth: number }, maxAirPressureMpa: number } }`.

- [ ] **Step 1: Write failing page-contract tests**

The test must assert:

```javascript
assert.deepEqual(template.order, ['main']);
assert.equal(template.sections.main.type, 'maliev-pimm-collection');
assert.match(section, /section\.settings\.pimm_product/);
assert.match(section, /product\.options\.size == 1/);
assert.match(section, /product\.options\.first == 'Model'/);
assert.match(section, /variant\.metafields\.custom\.full_machine_price\.value/);
assert.match(section, /variant\.metafields\.custom\.pimm_specifications\.value/);
assert.match(section, /variant\.metafields\.custom\.lead_time_days\.value/);
assert.match(section, /\?variant=/);
assert.doesNotMatch(section, /120[,.]000|170[,.]000|variant\.price \| times/);
assert.equal((section.match(/maliev-pimm-collection-20260901-r01-[^'"\s]+\.webp/g) ?? []).length, 6);
```

Parse both locale files and assert identical key paths beneath `products.pimm_collection`.

- [ ] **Step 2: Run the contract test and confirm the template/section are absent**

```powershell
node --test scripts/tests/pimm-collection-page-contract.test.mjs
```

Expected: FAIL with `ENOENT` for the new template or section.

- [ ] **Step 3: Add exact Thai and English locale structures**

Create matching keys under `products.pimm_collection`:

```json
{
  "title": "Choose the machine for your workshop",
  "intro": "Compare the compact 30G and extended-capacity 50G before opening the full machine configurator.",
  "best_for": "Best for",
  "price": "Full machine price",
  "lead_time": "Lead time",
  "shot_capacity": "Shot capacity",
  "mold_envelope": "Mold envelope (W × H × D)",
  "melt_temperature": "Maximum melt temperature",
  "air_pressure": "Maximum air pressure",
  "compare_with": "Compared with {{ model }}",
  "configure": "View {{ model }} machine",
  "select_model": "Compare {{ model }}",
  "configuration_error": "Machine comparison is not configured.",
  "updated_announcement": "Now comparing {{ model }}"
}
```

Use these Thai values with identical interpolation variables:

```json
{
  "title": "เลือกเครื่องที่เหมาะกับเวิร์กช็อปของคุณ",
  "intro": "เปรียบเทียบรุ่น 30G ขนาดกะทัดรัดกับรุ่น 50G ที่รองรับปริมาณมากขึ้น ก่อนเปิดหน้าตั้งค่าเครื่องฉีดพลาสติก",
  "best_for": "เหมาะสำหรับ",
  "price": "ราคาเครื่องเต็มจำนวน",
  "lead_time": "ระยะเวลาผลิต",
  "shot_capacity": "ความจุการฉีด",
  "mold_envelope": "ขนาดพื้นที่แม่พิมพ์ (ก × ส × ล)",
  "melt_temperature": "อุณหภูมิหลอมสูงสุด",
  "air_pressure": "แรงดันลมสูงสุด",
  "compare_with": "เปรียบเทียบกับ {{ model }}",
  "configure": "ดูเครื่องรุ่น {{ model }}",
  "select_model": "เปรียบเทียบรุ่น {{ model }}",
  "configuration_error": "ยังไม่ได้ตั้งค่าการเปรียบเทียบเครื่อง",
  "updated_announcement": "กำลังเปรียบเทียบรุ่น {{ model }}"
}
```

- [ ] **Step 4: Implement fail-closed Liquid contract resolution**

Resolve exactly one 30G and one 50G variant and validate every required field before setting `contract_valid = true`:

```liquid
assign pimm_product = section.settings.pimm_product
assign model_30g = nil
assign model_50g = nil
if pimm_product.options.size == 1 and pimm_product.options.first == 'Model' and pimm_product.variants.size == 2
  for variant in pimm_product.variants
    case variant.option1 | strip
      when '30G'
        assign model_30g = variant
      when '50G'
        assign model_50g = variant
    endcase
  endfor
endif
```

Validate schema version, model identity, positive technical values, full price, and lead time for both models. When invalid, render the localized configuration error and no price/specification values.

- [ ] **Step 5: Implement semantic card and dossier markup**

The section root must include:

```liquid
<pimm-collection-comparison
  class="pimm-collection"
  data-pimm-collection-comparison
  data-header-overlay-sentinel
  data-header-overlay-tone="bright"
>
```

Render one `h1`, two article cards, a desktop dossier aside, a mobile inline dossier, an `aria-live="polite"` committed-state announcement, and one JSON payload. Each card contains three layered `<img>` elements with only the front frame exposed initially. Left/right transition frames use `alt=""` and the front frame carries the model-specific alt text.

The primary link is computed from `pimm_product.url` plus `?variant={{ variant.id }}`.

- [ ] **Step 6: Add the dedicated alternate template and section schema**

`templates/collection.pimm-machines.json` contains only:

```json
{
  "sections": {
    "main": {
      "type": "maliev-pimm-collection",
      "settings": {
        "pimm_product": "pimm-pneumatic-injection-molding-machine-development",
        "support_url": "",
        "factory_visit_url": ""
      }
    }
  },
  "order": ["main"]
}
```

The section schema includes a required `product` picker named `pimm_product` and optional URL fields `support_url` and `factory_visit_url`.

- [ ] **Step 7: Add crawlable structured data**

Emit one `CollectionPage` with an `ItemList` containing two `ListItem` entries. Each entry uses the model-specific canonical variant URL, name, and position. Do not serialize an invalid contract.

- [ ] **Step 8: Register the contract test in package verification and run it**

Append `scripts/tests/pimm-collection-page-contract.test.mjs` to `verify:render-assets`, then run:

```powershell
node --test scripts/tests/pimm-collection-page-contract.test.mjs scripts/tests/pimm-unified-product-page-contract.test.mjs
npm run verify:theme
git diff --check
```

Expected: all Node tests PASS, Theme Check reports zero errors, and diff check exits 0.

- [ ] **Step 9: Commit the server-rendered collection**

```powershell
git add -- sections/maliev-pimm-collection.liquid templates/collection.pimm-machines.json locales/en.default.json locales/th.json scripts/tests/pimm-collection-page-contract.test.mjs package.json
git commit -m "Build dedicated PIMM comparison collection"
```

---

### Task 4: Precision layout and transparent header transition

**Files:**
- Create: `assets/maliev-pimm-collection.css`
- Modify: `sections/maliev-pimm-collection.liquid`
- Modify: `sections/maliev-header.liquid`
- Modify: `scripts/tests/pimm-collection-page-contract.test.mjs`

**Interfaces:**
- Consumes: Task 3's classes and `data-header-overlay-sentinel` root.
- Produces: desktop `minmax(0, 1.9fr) minmax(28rem, 1fr)` page grid, two-card left grid, sticky dossier, and inline tablet/mobile dossier.
- Produces: `.mc-header--overlay` on only product PIMM templates and `collection.pimm-machines`.

- [ ] **Step 1: Extend the page-contract test with failing presentation assertions**

```javascript
assert.match(header, /request\.page_type == 'collection'[\s\S]*template\.suffix == 'pimm-machines'[\s\S]*assign header_has_overlay = true/);
assert.match(css, /grid-template-columns:\s*minmax\(0,\s*1\.9fr\)\s+minmax\(28rem,\s*1fr\)/);
assert.match(css, /position:\s*sticky/);
assert.match(css, /@media[^{}]*max-width:\s*989px[\s\S]*position:\s*static/);
assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
assert.doesNotMatch(css, /overflow-x:\s*(?:scroll|auto)/);
```

- [ ] **Step 2: Run the focused test and confirm it fails**

```powershell
node --test scripts/tests/pimm-collection-page-contract.test.mjs
```

Expected: FAIL because the CSS and collection header condition do not exist.

- [ ] **Step 3: Add the stylesheet include and page tokens**

At the top of the section:

```liquid
{{ 'maliev-pimm-collection.css' | asset_url | stylesheet_tag }}
```

Define section-scoped tokens:

```css
.pimm-collection {
  --pimm-collection-accent: #0879c9;
  --pimm-collection-canvas: #eef1f4;
  --pimm-collection-ink: #111315;
  --pimm-collection-ease: cubic-bezier(0.22, 1, 0.36, 1);
  background: var(--pimm-collection-canvas);
  color: var(--pimm-collection-ink);
  min-height: 100svh;
}
```

- [ ] **Step 4: Implement desktop composition**

Use a full-width shell with fluid gutters, two side-by-side tall cards, a sticky dossier offset by `var(--maliev-header-h)`, and image media that fills its stage with `object-fit: cover`. Text overlays must use explicit copy-safe grid areas rather than absolute positioning over machine controls.

Card hover/focus-within behavior is limited to:

```css
.pimm-collection__card:is(:hover, :focus-within) {
  border-color: color-mix(in srgb, var(--pimm-collection-accent) 55%, transparent);
  box-shadow: 0 1.8rem 4.8rem rgba(17, 19, 21, 0.14);
  transform: translateY(-0.6rem);
}
```

- [ ] **Step 5: Implement tablet/mobile flow and reduced motion**

At `max-width: 989px`, remove sticky positioning and use the inline dossier. At `max-width: 749px`, stack introduction, 30G, 50G, dossier, and final actions. Enforce `min-width: 0`, `max-width: 100%`, and 44px controls.

```css
@media (prefers-reduced-motion: reduce) {
  .pimm-collection__card,
  .pimm-collection__frame,
  .pimm-collection__dossier-value {
    transition: none !important;
  }
  .pimm-collection__card:is(:hover, :focus-within) { transform: none; }
}
```

- [ ] **Step 6: Extend the existing header overlay condition**

In `maliev-header.liquid`, retain current product behavior and add:

```liquid
if request.page_type == 'collection' and template.suffix == 'pimm-machines'
  assign header_has_overlay = true
endif
```

Do not modify `maliev-header.js`; its existing sentinel and eased `.mc-header--overlay` contract already provides the required transition.

- [ ] **Step 7: Validate layout contracts**

```powershell
node --test scripts/tests/pimm-collection-page-contract.test.mjs scripts/tests/pimm-homepage-assets.test.mjs
npm run verify:theme
git diff --check
```

Expected: tests PASS and Theme Check reports zero errors.

- [ ] **Step 8: Commit presentation and header behavior**

```powershell
git add -- assets/maliev-pimm-collection.css sections/maliev-pimm-collection.liquid sections/maliev-header.liquid scripts/tests/pimm-collection-page-contract.test.mjs
git commit -m "Style PIMM collection comparison stage"
```

---

### Task 5: Active-model dossier and physical frame playback

**Files:**
- Create: `assets/maliev-pimm-collection.js`
- Create: `scripts/tests/pimm-collection-interaction.test.mjs`
- Modify: `sections/maliev-pimm-collection.liquid`
- Modify: `package.json`

**Interfaces:**
- Consumes: Task 3's JSON record shape and Task 4's card/frame selectors.
- Produces: custom element `pimm-collection-comparison`.
- Public instance methods: `commitModel(model, announce = true)`, `previewModel(model)`, `restoreCommittedModel()`, `playSequence(card)`, `stopSequence(card, reset = true)`.
- Playback indexes: `["front", "left", "front", "right", "front"]` at `[0, 180, 360, 540, 720]` milliseconds.

- [ ] **Step 1: Write failing VM controller tests**

Cover these exact behaviors:

```javascript
test('30G is committed initially and a preview does not overwrite the committed model', () => {
  const comparison = createComparison(Controller);
  comparison.connectedCallback();
  assert.equal(comparison.committedModel, '30G');
  comparison.previewModel('50G');
  assert.equal(comparison.activeModel, '50G');
  assert.equal(comparison.committedModel, '30G');
  comparison.restoreCommittedModel();
  assert.equal(comparison.activeModel, '30G');
});

test('committing 50G updates aria state, dossier values, and announcement once', () => {
  const comparison = createComparison(Controller);
  comparison.connectedCallback();
  comparison.commitModel('50G');
  assert.equal(comparison.committedModel, '50G');
  assert.equal(card50.getAttribute('aria-current'), 'true');
  assert.equal(announcement.textContent, 'Now comparing 50G');
});

test('reduced motion never schedules angle playback', () => {
  const { comparison, timers } = createComparison(Controller, { reducedMotion: true });
  comparison.playSequence(card30);
  assert.equal(timers.length, 0);
  assert.equal(visibleFrame(card30), 'front');
});

test('disconnect clears timers and aborts all listeners', () => {
  comparison.connectedCallback();
  comparison.playSequence(card30);
  comparison.disconnectedCallback();
  assert.equal(activeTimerCount(), 0);
  assert.equal(comparison.controller.signal.aborted, true);
});
```

- [ ] **Step 2: Run the interaction test and confirm the controller is absent**

```powershell
node --test scripts/tests/pimm-collection-interaction.test.mjs
```

Expected: FAIL with `ENOENT` for `assets/maliev-pimm-collection.js`.

- [ ] **Step 3: Implement safe initialization and payload validation**

```javascript
const MODELS = ['30G', '50G'];
const FRAME_SEQUENCE = ['front', 'left', 'front', 'right', 'front'];
const FRAME_DELAYS = [0, 180, 360, 540, 720];

connectedCallback() {
  if (this.controller) this.controller.abort();
  this.controller = new AbortController();
  this.reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  this.records = this.parseRecords();
  if (!this.hasExactRecordContract(this.records)) return;
  this.committedModel = '30G';
  this.applyModel('30G', false);
  this.bindCards();
  this.preloadDeferredFrames();
}
```

Invalid JSON or records leave server-rendered 30G content functional and do not attach playback listeners.

- [ ] **Step 4: Implement preview and commit semantics**

- `pointerenter` and `focusin` call `previewModel`.
- `pointerleave` and focus leaving the card call `restoreCommittedModel`.
- click/touch activation calls `commitModel`.
- only committed changes update the polite live region.
- both desktop and mobile dossier instances are updated from the same record.
- card active state uses class plus `aria-current`, never color alone.

- [ ] **Step 5: Implement deterministic frame playback**

Use one timer set per card. Starting playback clears that card's existing timers. Each scheduled callback exposes exactly one frame through `hidden` and `aria-hidden`. The final callback restores `front`.

Do not loop. Do not play with reduced motion. Do not alter `<img>` transforms.

- [ ] **Step 6: Implement cleanup and Shopify editor resilience**

```javascript
disconnectedCallback() {
  this.controller?.abort();
  this.controller = null;
  for (const card of this.querySelectorAll('[data-pimm-collection-card]')) {
    this.stopSequence(card, true);
  }
}
```

Register only when undefined:

```javascript
if (!customElements.get('pimm-collection-comparison')) {
  customElements.define('pimm-collection-comparison', PimmCollectionComparison);
}
```

- [ ] **Step 7: Include the deferred module and register its test**

In the section:

```liquid
<script src="{{ 'maliev-pimm-collection.js' | asset_url }}" defer="defer"></script>
```

Append `scripts/tests/pimm-collection-interaction.test.mjs` to `verify:render-assets`.

- [ ] **Step 8: Run focused and relevant tests**

```powershell
node --test scripts/tests/pimm-collection-interaction.test.mjs scripts/tests/pimm-collection-page-contract.test.mjs scripts/tests/pimm-precision-reveal.test.mjs
npm run verify:theme
git diff --check
```

Expected: all tests PASS and Theme Check reports zero errors.

- [ ] **Step 9: Commit the interaction controller**

```powershell
git add -- assets/maliev-pimm-collection.js sections/maliev-pimm-collection.liquid scripts/tests/pimm-collection-interaction.test.mjs package.json
git commit -m "Add PIMM collection comparison interaction"
```

---

### Task 6: Responsive browser proof and final repository verification

**Files:**
- Create: `scripts/tests/pimm-collection-responsive-browser.test.mjs`
- Modify when browser evidence reveals a defect: only files created or modified in Tasks 1-5.

**Interfaces:**
- Consumes: environment variable `PIMM_COLLECTION_PREVIEW_URL`, pointing to the local collection preview with `view=pimm-machines`; the alternate template binds the canonical development product handle.
- Produces: screenshots under `.codex-tmp/pimm-collection/browser-evidence/` and a passing responsive browser test.

- [ ] **Step 1: Write the opt-in CDP browser test**

Adapt the existing CDP harness from `pimm-unified-responsive-browser.test.mjs`, but target `[data-pimm-collection-comparison]`.

Use viewports:

```javascript
const viewports = [[1536, 1024], [1280, 800], [1024, 768], [390, 844], [360, 800]];
```

For each viewport assert:

```javascript
assert.equal(probe.h1Count, 1);
assert.equal(probe.cardCount, 2);
assert.equal(probe.imagesReady, true);
assert.equal(probe.horizontalOverflow, false);
assert.equal(probe.machineImagesTransformed, false);
assert.equal(probe.frontFramesDistinct, true);
assert.equal(probe.controlsAtLeast44px, true);
```

At desktop widths also assert cards are side by side and the dossier is to their right. At mobile widths assert 30G precedes 50G and the inline dossier follows both.

- [ ] **Step 2: Add interaction, URL, and header probes**

The browser test must:

1. Confirm 30G is initially active.
2. Hover/focus 50G and verify preview without commitment.
3. Click 50G and verify committed dossier values and one announcement.
4. Verify the 50G primary link has a numeric `variant` query value different from the 30G link.
5. Verify angle playback returns to the front frame and never applies an image transform.
6. Verify the header background is transparent at scroll position 0.
7. Scroll past the sentinel and verify `.mc-header--overlay.is-solid` with a white background.
8. Emulate reduced motion and verify only the front frame changes are suppressed.
9. Navigate to a `/th/` preview URL and verify Thai dossier labels are present.

- [ ] **Step 3: Run the browser test against the local preview**

With `npm run dev` already serving the development theme and its preview URL available:

```powershell
$env:PIMM_COLLECTION_PREVIEW_URL='http://127.0.0.1:9494/collections/%E0%B9%80%E0%B8%84%E0%B8%A3%E0%B8%B7%E0%B9%88%E0%B8%AD%E0%B8%87%E0%B8%89%E0%B8%B5%E0%B8%94%E0%B8%9E%E0%B8%A5%E0%B8%B2%E0%B8%AA%E0%B8%95%E0%B8%B4%E0%B8%81?view=pimm-machines'
node --test scripts/tests/pimm-collection-responsive-browser.test.mjs
```

Expected: all five viewport cases and both locales PASS; screenshots are written for manual review.

- [ ] **Step 4: Inspect browser evidence against the approved design**

Inspect desktop and mobile screenshots and verify:

- machines fill their media fields without clipping;
- copy never fades into or covers the machines;
- both model scenes are visibly distinct;
- card elevation is restrained;
- the sticky dossier remains fully reachable;
- the transparent header has sufficient contrast and becomes solid without a flash;
- the page does not resemble a generic Shopify collection grid.

Fix only observed defects, add an assertion for every regression fixed, then rerun the focused browser test.

- [ ] **Step 5: Run the complete repository verification**

```powershell
npm run verify
node --test scripts/tests/*.test.mjs
py -3 -m unittest scripts.blender.pimm_production.tests.test_collection_card_render -v
git diff --check
git status --short
```

Expected:

- Theme Check: zero errors.
- Render/contract/interaction tests: all PASS.
- Full Node suite: all PASS except no opt-in browser suite is silently skipped when its required URL is intentionally absent; the explicit browser command in Step 3 must already have passed.
- Python collection renderer tests: all PASS.
- Diff check: exit 0.
- Status: only the browser-test file and any narrowly required regression fixes are present.

- [ ] **Step 6: Commit the browser proof and final fixes**

```powershell
git add -- scripts/tests/pimm-collection-responsive-browser.test.mjs assets/maliev-pimm-collection.css assets/maliev-pimm-collection.js sections/maliev-pimm-collection.liquid sections/maliev-header.liquid locales/en.default.json locales/th.json
git diff --cached --quiet; if ($LASTEXITCODE -ne 0) { git commit -m "Verify responsive PIMM collection experience" }
```

- [ ] **Step 7: Record final handoff evidence**

Report:

- the dedicated preview URL used;
- Blender and storefront manifest release ID;
- exact test/build commands and pass counts;
- screenshot paths for desktop and mobile;
- commit hashes for Tasks 1-6;
- that production template assignment, unified-product publication, push, and deployment remain deliberately excluded.
