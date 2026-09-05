# PIMM Responsive Product Photography Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mixed-generation PIMM storefront media and collision-prone landing page with one governed 22-shot Blender campaign, responsive alpha heroes, a photo-led buyer journey, and verified layouts across every required device class.

**Architecture:** Extend the existing fail-closed Blender governance modules rather than adding an independent render pipeline. A versioned campaign manifest defines every one-shot scene and its web role; the existing scene, proof, approval, final-render, and immutable-release layers gain campaign-aware validation. The Shopify theme consumes one repository lineage manifest whose model-specific responsive media descriptors are serialized by Liquid and switched in place by the existing custom element. Native finals remain blocked until the owner approves the exact proof generation.

**Tech Stack:** Blender 5.2 Cycles, Blender Python API, Python 3.11 `unittest`, Pillow 12.2.0, immutable JSON/SHA-256 contracts, Shopify Liquid/Online Store 2.0, vanilla JavaScript custom elements, CSS Grid, Node.js test runner, Shopify Theme Check, Chrome DevTools Protocol browser tests.

**Spec:** `docs/superpowers/specs/2026-08-29-pimm-responsive-product-photography-design.md`

## Global Constraints

- [ ] Work only in `B:\maliev\maliev-shopify-store\.worktrees\pimm-unified-configurator` and `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders`.
- [ ] Do not mutate `masters/PIMM-30G-MASTER.blend`, `masters/PIMM-50G-MASTER.blend`, `masters/PIMM-MATERIAL-LIBRARY.blend`, linked product geometry, product materials, decals, controller displays, or animation state.
- [ ] Treat the current passing four-foot contact-plane result as an invariant. Re-run it before proofs and before finals; never compensate with a tilted floor or product transform.
- [ ] Keep one `.blend` and one JSON contract per logical shot. Scene files may own only cameras, lights, reflection cards, world, shadow catcher, compositor, render layers, output settings, and explicitly governed contextual props.
- [ ] Keep all 22 shots in one proof generation and one final release. Reject partial and mixed-generation publication.
- [ ] Do not begin native final rendering until the user approves the exact proof contact sheets and their immutable proof generation ID.
- [ ] Do not mention or render a deposit, payment, checkout, or purchase action. `Book a demo session` is the only conversion CTA.
- [ ] Do not fetch both models' complete media libraries on initial page load.
- [ ] Do not push, deploy, publish products, modify the live theme, or modify Shopify production state.
- [ ] Preserve unrelated dirty files. Commit each independently validated repository slice; external Blender artifacts are governed by hashes and manifests, not copied into Git.

---

## Task 1: Freeze the 22-shot campaign contract

**Files:**

- Create: `scripts/blender/pimm_production/campaign_contract.py`
- Create: `scripts/blender/pimm_production/contracts/campaigns/pimm-responsive-product-photography-v1.json`
- Create: `scripts/blender/pimm_production/tests/test_campaign_contract.py`
- Modify: `scripts/blender/pimm_production/scene_contract.py`
- Modify: `scripts/blender/pimm_production/tests/test_scene_contract.py`

- [ ] Write `test_campaign_contract.py` first. Assert the manifest has schema `maliev.pimm-render-campaign/v1`, campaign ID `pimm-responsive-product-photography-v1`, exactly 22 unique shot IDs, the six required responsive heroes, the four editorial studies, eight model details, two comparison shots, and two workshop shots.
- [ ] Assert every scene contract maps to `scenes/contracts/{shot-id}.json`, every scene maps to `scenes/stills/{shot-id}.blend`, and every output dimension, machine scope, purpose, focal length, f-stop, alpha mode, background class, safe margin, and storefront role matches the approved specification.
- [ ] Assert the shared comparison shots declare both `30G` and `50G`; update `SceneContract` to represent `machines: ["30G", "50G"]` only for shared shots while retaining the existing singular `machine` field for single-model shots. Reject any other ambiguity.
- [ ] Replace `_STATIC_SHOT_CAMERAS` in `scene_contract.py` with campaign-derived shot policy. Keep the exact 36mm sensor, AgX Medium High Contrast, pinned HDRI hash, 0.5 strength, 0-degree rotation, and managed light-name requirements.
- [ ] Add exact validation for hero safe margins (`product: 0.08`, `shadow: 0.12`), editorial/detail dimensions, permitted focal lengths (`85`, `135`, `200`), permitted f-stops (`8`, `11`, `16`), and `animation_contract: null`.

Run first, expecting failure because the campaign module and manifest do not exist:

```powershell
python -m unittest scripts.blender.pimm_production.tests.test_campaign_contract scripts.blender.pimm_production.tests.test_scene_contract -v
```

Implement the central immutable `CampaignShot` record with these fields:

```python
@dataclass(frozen=True)
class CampaignShot:
    shot_id: str
    machines: tuple[str, ...]
    purpose: str
    width: int
    height: int
    alpha: bool
    focal_length_mm: float
    aperture_fstop: float
    product_safe_margin: float
    shadow_safe_margin: float
    storefront_roles: tuple[str, ...]
```

Expose `load_campaign(path: Path) -> RenderCampaign`, `validate_campaign(campaign: RenderCampaign) -> list[str]`, and `shot_policy(campaign: RenderCampaign, shot_id: str) -> CampaignShot`. `load_campaign` must reject non-object JSON and unexpected fields; `validate_campaign` returns every semantic error; `shot_policy` raises `ValueError` for an uncontracted ID.

- [ ] Re-run the focused tests and expect all campaign and scene-contract cases to pass.
- [ ] Run the entire Python governance suite:

```powershell
python -m unittest discover -s scripts\blender\pimm_production\tests -v
```

- [ ] Commit only the campaign contract slice:

```powershell
git add -- scripts/blender/pimm_production/campaign_contract.py scripts/blender/pimm_production/contracts/campaigns/pimm-responsive-product-photography-v1.json scripts/blender/pimm_production/tests/test_campaign_contract.py scripts/blender/pimm_production/scene_contract.py scripts/blender/pimm_production/tests/test_scene_contract.py
git commit -m "Define governed PIMM photography campaign"
```

## Task 2: Add alpha, contact, and provenance gates

**Files:**

- Create: `scripts/blender/pimm_production/image_safety.py`
- Create: `scripts/blender/pimm_production/external_asset_manifest.py`
- Create: `scripts/blender/pimm_production/tests/test_image_safety.py`
- Create: `scripts/blender/pimm_production/tests/test_external_asset_manifest.py`
- Modify: `scripts/blender/pimm_production/proof_contract.py`
- Modify: `scripts/blender/pimm_production/tests/test_proof_contract.py`
- Modify external: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\manifests\free-tools-lock.json`
- Create external when required: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\manifests\external-assets-v1.json`

- [ ] Add failing pixel-fixture tests for a clean interior product/shadow, product alpha touching an edge, shadow alpha touching an edge, insufficient 8% product clearance, insufficient 12% hero-shadow clearance, visible catcher RGB, missing product pixels, and a fully opaque image.
- [ ] Define `AlphaSafetyEvidence` with canvas size, product bounds, shadow bounds, per-edge fractions, alpha extrema, catcher visibility, and pass/fail reasons. Compute it from independent product and shadow passes, never from visual guesswork.
- [ ] Add proof-contract fields that bind the alpha-safety result and the current four-foot contact evidence for each complete-machine shot. Detail shots may mark full-machine contact `not-applicable`; base/feet details must still bind the contact-plane report.
- [ ] Add an external-asset schema requiring source URL, asset/version ID, `CC0-1.0`, local relative path, SHA-256, intended shot IDs, and `machine_master_modified: false`. Empty assets are valid; incomplete or account-gated records fail.
- [ ] Keep the pinned HDRI in the existing free-tool/provenance authority. If no new CC0 prop materially improves a workshop proof, commit an empty `assets` list rather than downloading decoration.

Run first, expecting the new tests to fail:

```powershell
python -m unittest scripts.blender.pimm_production.tests.test_image_safety scripts.blender.pimm_production.tests.test_external_asset_manifest scripts.blender.pimm_production.tests.test_proof_contract -v
```

Implement `analyze_alpha_safety(product_rgba, shadow_rgba, product_margin, shadow_margin)` to return `AlphaSafetyEvidence`, and `validate_external_assets(manifest, campaign_shot_ids)` to return every validation error. Keep both functions pure so fixture tests do not require Blender.

- [ ] Re-run focused tests, then the full Python governance suite.
- [ ] Commit the repository code and the repository-owned lock expectation. Record the external manifest hash in the commit message body; do not commit the M-drive file itself.

```powershell
git add -- scripts/blender/pimm_production/image_safety.py scripts/blender/pimm_production/external_asset_manifest.py scripts/blender/pimm_production/tests/test_image_safety.py scripts/blender/pimm_production/tests/test_external_asset_manifest.py scripts/blender/pimm_production/proof_contract.py scripts/blender/pimm_production/tests/test_proof_contract.py
git commit -m "Gate PIMM renders on alpha and asset provenance"
```

## Task 3: Generalize one-shot scene authoring

**Files:**

- Modify: `scripts/blender/pimm_production/blender_static_product_scene.py`
- Modify: `scripts/blender/pimm_production/blender_scene_template.py`
- Modify: `scripts/blender/pimm_production/blender_scene_validator.py`
- Modify: `scripts/blender/pimm_production/tests/test_static_product_scene.py`
- Modify: `scripts/blender/pimm_production/tests/test_scene_contract.py`
- Create: `scripts/blender/pimm_production/shot_compositions.py`
- Create: `scripts/blender/pimm_production/tests/test_shot_compositions.py`

- [ ] Replace the eight-entry `SHOT_CONFIGS`/allowed-focal-length assumptions with campaign-driven one-shot configurations for all 22 shots.
- [ ] Write failing tests for desktop left-copy safe area, centered tablet composition, mobile lower-control clearance, bright/dark three-quarter camera azimuth, detail target membership, aligned dual-machine ground plane, and workshop prop isolation.
- [ ] Add deterministic composition records with camera view, target stable IDs or complete-product bounds, normalized subject placement, protected-copy rectangle, working-distance minimum, and studio profile.
- [ ] Keep full-machine cameras eye-level and at least three machine heights away where the external studio permits. Use 85mm for desktop full-machine, 135mm for tablet/mobile/editorial, and 135–200mm for details.
- [ ] Create broad key, fill, rim, lower-bounce, and reflection-card geometry per studio profile. Keep `PIMM_SCENE_SHADOW_CATCHER` finite geometry outside the camera frustum so no catcher edge can appear.
- [ ] For comparison scenes, link each approved master collection once under separate scene-owned transforms; validate both contact planes resolve to one common floor without changing either linked collection.
- [ ] For workshop scenes, load only provenance-approved scene-local props. Reject any local mesh/material whose ownership is not `scene-support` or whose record is absent.
- [ ] Extend reopen validation to prove there is no private product mesh, no localized product material, no animation, one managed camera, exact light/card names, exact render engine/color settings, and exact output path.

Run first, expecting composition tests to fail:

```powershell
python -m unittest scripts.blender.pimm_production.tests.test_static_product_scene scripts.blender.pimm_production.tests.test_shot_compositions scripts.blender.pimm_production.tests.test_scene_contract -v
```

- [ ] Re-run focused tests and the complete Python governance suite after implementation.
- [ ] Commit the generalized authoring slice:

```powershell
git add -- scripts/blender/pimm_production/blender_static_product_scene.py scripts/blender/pimm_production/blender_scene_template.py scripts/blender/pimm_production/blender_scene_validator.py scripts/blender/pimm_production/shot_compositions.py scripts/blender/pimm_production/tests/test_static_product_scene.py scripts/blender/pimm_production/tests/test_shot_compositions.py scripts/blender/pimm_production/tests/test_scene_contract.py
git commit -m "Author responsive PIMM scenes from campaign contracts"
```

## Task 4: Build and reopen all 22 scene files

**Files:**

- Create external: all 22 manifest-named JSON files under `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\scenes\contracts\`
- Create external: all 22 manifest-named `.blend` files under `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\scenes\stills\`
- Modify external: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\manifests\PIMM-static-shot-targets-v1.json`

- [ ] Hash both masters and the material library before any build. Save the values in the campaign build report.
- [ ] Run the master foot-contact gate before scene creation:

```powershell
& 'D:\Blender 5.2\blender.exe' -b 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-30G-MASTER.blend' --python 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\scripts\verify_foot_contact_plane.py'
& 'D:\Blender 5.2\blender.exe' -b 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\masters\PIMM-50G-MASTER.blend' --python 'M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\scripts\verify_foot_contact_plane.py'
```

Expected: both reports identify four distinct feet, a common plane within `0.0002`, and status `pass`.

- [ ] For each campaign shot, run `--prepare-contract`, build the one-shot `.blend`, run `--author-scene`, then reopen it in a fresh Blender process with the scene validator. Stop the batch at the first failure.
- [ ] Rehash both masters and material library after the batch; require byte-identical hashes.
- [ ] Produce `renders/proofs/unapproved/pimm-responsive-product-photography-v1/scene-build-report.json` containing all 22 contract/scene hashes, reopen results, master hashes, target evidence, contact evidence, and external-asset hashes.
- [ ] Run `python -m unittest discover -s scripts\blender\pimm_production\tests -v` and `node --test scripts/tests/pimm-blender-production-governance.test.mjs`.
- [ ] Do not commit generated `.blend` files to the Shopify repo. Commit only repository code changes if validation exposed and required a code fix; otherwise record the exact external report path and SHA-256 in the task log.

## Task 5: Render one immutable proof campaign

**Files:**

- Modify: `scripts/blender/pimm_production/blender_proof_render.py`
- Modify: `scripts/blender/pimm_production/contact_sheet.py`
- Modify: `scripts/blender/pimm_production/tests/test_proof_contract.py`
- Modify: `scripts/blender/pimm_production/tests/test_approval_release.py`
- Create external: the generated proof contract under `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\scenes\contracts\proofs\`
- Create external: the immutable generation directory reported by the proof runner under `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\proofs\`

- [ ] Add failing tests that require one campaign proof contract to bind all 22 scene hashes, reject missing/duplicate shots, reject mixed masters or scene revisions, and publish no partial proof root after one shot fails.
- [ ] Extend proof output to include, per shot: product RGBA, shadow-only RGBA, white/checker/dark composites, full-frame composition, and named 100% crops. Require gauge/regulator/AirTAC/controller crops for pneumatic/control details and feet/tooling/black-material crops where applicable.
- [ ] Generate one labelled campaign index sheet plus model/hero/editorial/detail/workshop sheets. Each label must show shot ID, output aspect, lens, f-stop, proof generation ID, scene hash prefix, alpha margins, and contact status.
- [ ] Run all 22 proofs through Blender in one fail-closed generation. Require `fingerprints_unchanged: true`, 22 passing image-safety records, 22 scene-authority records, and zero stale-master links.
- [ ] Inspect the sheets at 100% and verify: all feet contact; shadow never clips; white metal retains edge contrast; base underside is readable; decals and controller segments are legible; dark finishes retain shape; props never obscure the machine; protected-copy areas remain clean.
- [ ] Re-run both master foot-contact commands and all Python governance tests after proof generation.
- [ ] Commit only proof-pipeline code:

```powershell
git add -- scripts/blender/pimm_production/blender_proof_render.py scripts/blender/pimm_production/contact_sheet.py scripts/blender/pimm_production/tests/test_proof_contract.py scripts/blender/pimm_production/tests/test_approval_release.py
git commit -m "Produce atomic PIMM campaign proofs"
```

## Task 6: Owner proof-review checkpoint — mandatory stop

- [ ] Present the immutable generation ID, contact-sheet paths, report SHA-256, all 22 shot statuses, master fingerprint comparison, four-foot result, alpha-margin result, and any documented below-fold size exception to the owner.
- [ ] Do not interpret approval of this design document or this implementation plan as proof approval.
- [ ] Stop. Native final rendering remains unauthorized until the owner explicitly approves that exact proof generation.
- [ ] If any shot is rejected, create a new scene revision and entirely new proof generation; never replace bytes inside the rejected immutable proof root.

## Task 7: Render and publish one authorized final release

**Prerequisite:** The owner has explicitly approved the exact proof generation from Task 6.

**Files:**

- Modify: `scripts/blender/pimm_production/blender_final_render.py`
- Modify: `scripts/blender/pimm_production/release_manifest.py`
- Create: `scripts/blender/pimm_production/web_derivatives.py`
- Create: `scripts/blender/pimm_production/tests/test_web_derivatives.py`
- Modify: `scripts/blender/pimm_production/tests/test_approval_release.py`
- Create external: the owner-authorized immutable release directory under `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\renders\final\`

- [ ] Record the approval with `approval_manifest.py`, binding owner, all 22 shot IDs, exact proof manifest hash, exact scene hashes, and approval notes.
- [ ] Add failing tests that require a campaign final contract to authorize all 22 shots, reject partial output, reject mixed proof generations, and reject release publication unless all family manifests share the same release root and approval.
- [ ] Render native float EXR and transparent PNG for alpha heroes, native PNG/WebP for opaque editorial/contextual shots, and component masks/evidence required by the existing governance pipeline.
- [ ] Create responsive WebP derivatives without repainting or cropping away contracted safe areas. Preserve hero alpha. Enforce `<=500 KB` for heroes and `<=350 KB` for below-fold images unless an exact shot/bytes/legibility exception is written into the release manifest.
- [ ] Publish `release-manifest.json` last and atomically. It must enumerate 22 logical shots plus every derivative with dimensions, bytes, SHA-256, proof ID, scene SHA-256, master/material hashes, alpha evidence, and intended storefront role.
- [ ] Run final QA and the complete Python governance suite. Re-run both master foot-contact gates and require unchanged master/material hashes.
- [ ] Commit the final/release pipeline code:

```powershell
git add -- scripts/blender/pimm_production/blender_final_render.py scripts/blender/pimm_production/release_manifest.py scripts/blender/pimm_production/web_derivatives.py scripts/blender/pimm_production/tests/test_web_derivatives.py scripts/blender/pimm_production/tests/test_approval_release.py
git commit -m "Publish atomic PIMM photography releases"
```

## Task 8: Import exact released media into the theme

**Files:**

- Replace: `assets/pimm-unified-render-assets.v1.json`
- Create/replace: `assets/pimm-machine-*.webp` for the approved release only
- Modify: `scripts/tests/pimm-unified-render-assets.test.mjs`
- Modify: `scripts/tests/pimm-unified-product-page-contract.test.mjs`

- [ ] Change the render-assets fixture to schema `maliev.pimm-unified-render-assets/v2` and write failing assertions for one release ID, all 22 shot roles, all six responsive hero sources, exact dimensions, exact hashes, alpha-safe hero evidence, asset budgets, and no legacy release/asset path.
- [ ] Add a test that scans the PIMM template, section, snippets, CSS, JS, and lineage manifest and rejects references to legacy `pimm30-v*`, `pimm50-story-*`, `pimm-machine-*-hero-front.webp`, releases `r15`–`r23`, and any asset absent from v2 lineage.
- [ ] Copy only verified WebP derivatives from the approved release to `assets/`. Hash each destination after copy and compare it to the release manifest before updating lineage.
- [ ] Keep native EXR/PNG and proof evidence on the governed M-drive; do not bloat the theme repository with native masters.

Run first, expecting lineage failures:

```powershell
node --test scripts/tests/pimm-unified-render-assets.test.mjs scripts/tests/pimm-unified-product-page-contract.test.mjs
```

- [ ] Re-run the focused tests and `npm run verify:render-assets` after import.
- [ ] Commit the atomic asset import separately:

```powershell
git add -- assets/pimm-unified-render-assets.v1.json scripts/tests/pimm-unified-render-assets.test.mjs scripts/tests/pimm-unified-product-page-contract.test.mjs
$pimmAssetNames = (Get-Content -Raw -LiteralPath 'assets\pimm-unified-render-assets.v1.json' | ConvertFrom-Json).assets.name
foreach ($pimmAssetName in $pimmAssetNames) { git add -- (Join-Path 'assets' $pimmAssetName) }
git commit -m "Import approved PIMM photography campaign"
```

Before the second `git add`, print the manifest's `name` values and pass those exact paths. Do not use a wildcard that could stage unrelated pre-existing PIMM media changes.

## Task 9: Rebuild the Liquid media and narrative contract

**Files:**

- Modify: `sections/maliev-pimm-machine-product.liquid`
- Modify: `snippets/pimm-hero-console.liquid`
- Modify: `snippets/pimm-engineering-bento.liquid`
- Create: `snippets/pimm-family-comparison.liquid`
- Modify: `snippets/pimm-ownership.liquid`
- Create: `snippets/pimm-detail-gallery.liquid`
- Modify: `snippets/pimm-purchase-qualification.liquid`
- Modify: `templates/product.pimm-configurator.json`
- Modify: `locales/en.default.json`
- Modify: `locales/th.json`
- Modify: `scripts/tests/pimm-unified-product-page-contract.test.mjs`

- [ ] Write failing contract tests for a semantic responsive `<picture>` per model with mobile, tablet, and desktop sources; the required mobile order; one selected-model bright editorial plus four detail figures in the bento; shared family comparison; two workshop figures; selected-model detail gallery; and one final demo close.
- [ ] Assert every image has explicit dimensions/aspect ratio, translatable alt text, `loading="lazy" decoding="async"` below the fold, and no empty decorative fallback.
- [ ] Expand each model block schema from four assets to nine model-specific roles: three heroes, bright editorial, dark editorial, controls, pneumatics, tooling, and base/feet. Put comparison desktop/mobile and workshop wide/portrait in section settings because they are shared.
- [ ] Serialize the same role names into the variant JSON payload. Missing model-specific story media must omit that figure; missing responsive hero may fall back only to the same model's nearest approved hero aspect.
- [ ] Place commercial facts in the hero: model selector, full machine price, availability, lead time, and `Book a demo session`. Do not render a product form or any deposit/payment copy.
- [ ] Build the page sequence: responsive machine-first hero → photo-led engineering bento → family comparison → workshop ownership story → selected-model detail gallery → final demo CTA.
- [ ] Keep numeric capacity, temperature, envelope, and pressure in semantic HTML sourced from variant/metafield data; photographs are never the numeric authority.
- [ ] Add complete English/Thai keys and exact placeholder parity. Keep all installed locale files structurally compatible with `products.pimm_machine`.

Run first, expecting contract failures:

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
```

- [ ] Re-run the product-page contract and Theme Check after implementation.
- [ ] Commit the semantic product-story slice:

```powershell
git add -- sections/maliev-pimm-machine-product.liquid snippets/pimm-hero-console.liquid snippets/pimm-engineering-bento.liquid snippets/pimm-family-comparison.liquid snippets/pimm-ownership.liquid snippets/pimm-detail-gallery.liquid snippets/pimm-purchase-qualification.liquid templates/product.pimm-configurator.json locales/en.default.json locales/th.json scripts/tests/pimm-unified-product-page-contract.test.mjs
git commit -m "Build photo-led PIMM product story"
```

## Task 10: Implement intent-driven model media switching

**Files:**

- Modify: `assets/maliev-pimm-machine.js`
- Modify: `scripts/tests/pimm-unified-product-page-contract.test.mjs`

- [ ] Extend the controller harness tests first. Assert only the selected model's selected responsive hero candidate is eager/high priority; alternate sources remain inert until pointer, keyboard, touch, or selection intent; below-fold media remains lazy; selected model state updates every role; URL/focus/announcement remain correct; and no cross-model fallback occurs.
- [ ] Replace the current `isMediaItem(hero, 1800, 2200)` contract with exact role-aware descriptors:

```javascript
{
  hero: {
    mobile: { url, width: 1440, height: 2560 },
    tablet: { url, width: 2048, height: 1536 },
    desktop: { url, width: 2560, height: 1440 }
  },
  editorialBright: { url, width: 1800, height: 2250 },
  editorialDark: { url, width: 1800, height: 2250 },
  controls: { url, width: 1800, height: 2250 },
  pneumatics: { url, width: 1800, height: 2250 },
  tooling: { url, width: 1800, height: 2250 },
  baseFeet: { url, width: 1800, height: 2250 }
}
```

- [ ] Apply URLs to stable existing `<source>`/`<img>` nodes; do not rebuild semantic DOM. Decode the newly selected hero before the maximum 180ms opacity swap. Cancel stale rapid transitions.
- [ ] Use instant swaps when `prefers-reduced-motion: reduce`; preserve radio focus and announce model, full price, availability, and lead time.
- [ ] Re-run the contract tests and `node --check assets/maliev-pimm-machine.js`.
- [ ] Commit the controller slice:

```powershell
git add -- assets/maliev-pimm-machine.js scripts/tests/pimm-unified-product-page-contract.test.mjs
git commit -m "Load PIMM model photography on intent"
```

## Task 11: Rebuild responsive layout without overlap or clipping

**Files:**

- Modify: `assets/maliev-pimm-machine.css`
- Modify: `scripts/tests/pimm-unified-product-page-contract.test.mjs`
- Modify: `scripts/tests/pimm-unified-responsive-browser.test.mjs`

- [ ] Add static failures for negative hero image margins, unbounded hero overflow, absolute positioning of decision/media areas, missing `object-fit: contain`, missing aspect-ratio wrappers, header border in the PIMM overlay state, CTA shorter than 44px, and motion exceeding 180ms.
- [ ] Delete all current hero `margin-inline: -…`, oversized image width, overflow-visible compensation, and viewport-height special-case hacks.
- [ ] Use explicit named grid areas. Desktop/tablet keep title/selector/commercial facts in a decision column and machine in a bounded media area; mobile renders navbar → machine → selector/CTA → title/support copy. Let hero height be `min-height: 100svh` only where all content fits; never clip content to force one screen.
- [ ] Keep navbar transparent and borderless over the hero visual field with sufficient text/icon contrast. Preserve focus outlines and 44px controls.
- [ ] Implement a single asymmetric photo-led bento, then normal editorial sections. Do not turn the whole page into cards.
- [ ] Add stable aspect ratios to every media wrapper, zero horizontal overflow, and graceful single-column ordering at 320px and 200% zoom.

Run first, expecting CSS/geometry tests to fail:

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs scripts/tests/pimm-unified-responsive-browser.test.mjs
```

- [ ] Re-run the static contract test after CSS implementation. The browser test may skip until `PIMM_UNIFIED_PREVIEW_URL` is supplied.
- [ ] Commit the responsive layout slice:

```powershell
git add -- assets/maliev-pimm-machine.css scripts/tests/pimm-unified-product-page-contract.test.mjs scripts/tests/pimm-unified-responsive-browser.test.mjs
git commit -m "Rebuild responsive PIMM landing layout"
```

## Task 12: Run local browser, accessibility, and visual acceptance

**Files:**

- Modify only if a verified defect is found: files from Tasks 9–11
- Generate untracked evidence under: `tmp/pimm-unified-browser-evidence/`

- [ ] Start the development theme without changing production:

```powershell
npm run dev -- --host 127.0.0.1 --port 9393
```

- [ ] Set the exact preview URL returned by Shopify CLI:

```powershell
$env:PIMM_UNIFIED_PREVIEW_URL = 'http://127.0.0.1:9393/products_preview?preview_key=6a12c863784016889e64a8e014064eb2&view=pimm-configurator&variant=54823758659863'
```

- [ ] Run the automated browser matrix at `320x800`, `390x844`, `768x1024`, `1024x900`, `1440x900`, and `1920x1080` for 30G/50G and EN/TH.

```powershell
node --test scripts/tests/pimm-unified-responsive-browser.test.mjs
```

- [ ] Extend the browser probes to assert: header and hero do not overlap; machine and product/shadow bounds stay inside their media wrapper; selector/CTA/facts are visible in the intended first-screen composition; all page sections appear in sequence; no element causes horizontal overflow; no page-owned console error occurs; and alternate-model media requests begin only after intent.
- [ ] Run the same acceptance at 200% zoom, keyboard-only model switching, reduced motion, direct 30G/50G variant URLs, invalid/unavailable fixtures, and missing-media fixtures.
- [ ] Capture hero, bento, comparison, workshop, gallery, and final CTA screenshots at mobile/tablet/desktop. Inspect them at native size; verify all four feet are visually supported and no shadow edge is clipped.
- [ ] Run Impeccable detection on every captured viewport and treat overlap, clipping, weak hierarchy, undersized controls, and horizontal overflow as failures.
- [ ] Fix verified defects with a failing regression assertion first, then rerun the affected viewport and full browser matrix.
- [ ] Commit any browser-driven fixes as a coherent slice:

```powershell
git add -- assets/maliev-pimm-machine.css assets/maliev-pimm-machine.js sections/maliev-pimm-machine-product.liquid snippets/pimm-hero-console.liquid snippets/pimm-engineering-bento.liquid snippets/pimm-family-comparison.liquid snippets/pimm-ownership.liquid snippets/pimm-detail-gallery.liquid snippets/pimm-purchase-qualification.liquid templates/product.pimm-configurator.json locales/en.default.json locales/th.json scripts/tests/pimm-unified-product-page-contract.test.mjs scripts/tests/pimm-unified-responsive-browser.test.mjs
git commit -m "Polish verified PIMM responsive presentation"
```

## Task 13: Final verification and local handoff

- [ ] Verify the Blender governance modules and master assets:

```powershell
python -m unittest discover -s scripts\blender\master_assets\tests -v
python -m unittest discover -s scripts\blender\pimm_production\tests -v
node --test scripts/tests/pimm-blender-production-governance.test.mjs
```

- [ ] Verify the theme, asset lineage, product contract, and browser matrix:

```powershell
npm run verify
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
node --test scripts/tests/pimm-unified-responsive-browser.test.mjs
node --check assets/maliev-pimm-machine.js
git diff --check
```

- [ ] Parse all changed JSON files with Node or Python. Search all PIMM consumer files for deposit/payment language, legacy asset names, old release IDs, negative hero-image margins, and unapproved media paths; expect zero matches.
- [ ] Verify the final external release manifest has 22 logical shots, one proof generation, one release ID, interior hero alpha bounds, passing contact evidence, and hashes matching every committed WebP.
- [ ] Confirm `git status --short` contains no accidental proof files, EXRs, native PNGs, credentials, `.env`, temp browser profiles, or unrelated user changes.
- [ ] If final verification required edits, commit them by coherent cause after rerunning the affected checks. Do not create a catch-all commit for unrelated changes.
- [ ] Report: exact release/proof IDs; external scene/proof/final paths; asset counts and budgets; changed theme components; test/build/browser results with pass counts; commit hashes; skipped checks and residual risk. State explicitly that no push, deploy, product publication, or production theme mutation occurred.

## Definition of Done

- [ ] All 22 scene contracts and `.blend` files independently reopen and validate.
- [ ] Both masters and the material library retain their pre-campaign hashes; four feet pass the contact-plane gate.
- [ ] The owner approved the exact immutable proof generation used by finals.
- [ ] One atomic immutable release contains all 22 shots and responsive derivatives.
- [ ] Every hero product and shadow alpha bound is strictly interior with contracted margins.
- [ ] The theme lineage resolves only the new release and no legacy PIMM storefront media.
- [ ] The machine-first hero, photo-led bento, family comparison, workshop story, detail gallery, and final demo CTA render in English and Thai.
- [ ] All required viewport, zoom, keyboard, reduced-motion, loading, fallback, and overflow checks pass for both models.
- [ ] No deposit/payment language or control exists.
- [ ] All applicable automated checks pass and coherent local commits exist.
- [ ] Production remains untouched.
