# PIMM Unified Product Story Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the obsolete unified PIMM bento/editorial page with a selected-model product story that uses the approved 30G and 50G production assets, presents every machine at useful scale with visible ground contact, and removes all deprecated storefront renders.

**Architecture:** Keep `pimm-machine-product` as the single Shopify variant controller and render one shared decision header plus two model-specific normal-scroll story panels. The template selects one governed asset-set identifier per model; focused Liquid snippets map those identifiers to the approved media families, while JavaScript exposes only the selected story and singular shared commerce controls. Migrate contracts before deleting old assets, then replace the large legacy CSS cascade with one asset-aware responsive presentation contract.

**Tech Stack:** Shopify Online Store 2.0 Liquid/JSON templates, vanilla JavaScript custom elements, CSS, Node.js 20 built-in test runner, Shopify Theme Check, Chrome DevTools Protocol browser tests.

**Spec:** `docs/superpowers/specs/2026-08-31-pimm-unified-product-story-replacement-design.md`

## Global Constraints

- Local implementation and validation only; do not push, merge, deploy, publish, or mutate the production store.
- Preserve product IDs, variant IDs, prices, deposit rules, availability, metafield schemas, catalog structure, app blocks, and Theme Editor schema validity.
- Keep one H1, one selected-model controller, one shared commerce form, complete English/Thai content, visible focus, 44-pixel practical targets, and WCAG 2.2 AA contrast.
- Use normal document flow, intrinsic media ratios, and `object-fit: contain`; do not crop, overlap, or absolutely position product media.
- Full-machine assets must be bottom-aligned by measured opaque bounds so their load-bearing feet visibly meet the stage baseline.
- Eager-load only the selected hero; inactive-model and below-fold media remain hidden, inert, inaccessible, and deferred.
- Preserve reduced-motion behavior and poster fallbacks for every 30G video.
- Remove the 12 listed `pimm-machine-*` and `pimm-editorial-*` derivatives, both release manifests, their obsolete snippet, and asset-only tests after runtime migration passes.

## File structure

- Create `snippets/pimm-30g-product-story.liquid`: authoritative 30G hero and evidence sequence using the current `pimm30-*` posters/videos.
- Create `snippets/pimm-50g-product-story.liquid`: authoritative 50G light-studio hero and evidence sequence using all six `pimm50-light-studio-*` images.
- Create `scripts/tests/pimm-unified-story-assets.test.mjs`: active asset existence/type/dimension checks and negative deprecated-reference scan.
- Modify `snippets/pimm-hero-console.liquid`: shared decision copy, selector, specifications, actions, and selected hero groups; remove the old engineering-detail panel.
- Modify `sections/maliev-pimm-machine-product.liquid`: render the two model stories, validate `story_asset_set`, and remove old bento/editorial composition.
- Modify `templates/product.pimm-configurator.json`: replace four obsolete filename settings per model with `story_asset_set` values `pimm30-production-v13` and `pimm50-light-studio-v1`.
- Modify `assets/maliev-pimm-machine.js`: keep variant state, add selected-video activation, and make story/media visibility deterministic under rapid switching and reduced motion.
- Replace `assets/maliev-pimm-machine.css`: one compact responsive system for the shared header, grounded hero stage, alternating evidence chapters, and model-story visibility.
- Modify `scripts/tests/pimm-unified-product-page-contract.test.mjs`: contract for asset sets, story structure, singular commerce, accessibility, and controller behavior.
- Modify `scripts/tests/pimm-unified-responsive-browser.test.mjs`: real selected-story geometry, ground-contact, loading, switching, localization, zoom, and screenshot assertions.
- Modify `package.json`: replace obsolete render verification scripts with the unified story asset test.
- Delete `snippets/pimm-engineering-bento.liquid`, `snippets/pimm-editorial-chapters.liquid`, `scripts/tests/pimm-unified-render-assets.test.mjs`, `scripts/tests/pimm-editorial-render-assets.test.mjs`, the two obsolete manifests, and the 12 deprecated WebP files named in the specification.

---

### Task 1: Freeze the new selected-model and asset-authority contract

**Files:**
- Modify: `scripts/tests/pimm-unified-product-page-contract.test.mjs`
- Create: `scripts/tests/pimm-unified-story-assets.test.mjs`
- Modify: `templates/product.pimm-configurator.json`
- Modify: `sections/maliev-pimm-machine-product.liquid`

**Interfaces:**
- Consumes: existing `data-pimm-machine-product`, `data-pimm-model-radio`, `data-pimm-story-model`, `data-pimm-variant-data`, variant specification schema version 1.
- Produces: model block setting `story_asset_set: string`; allowed values `pimm30-production-v13` for `30G` and `pimm50-light-studio-v1` for `50G`; JSON record field `storyAssetSet: string`; required snippets `pimm-30g-product-story` and `pimm-50g-product-story`.

- [ ] **Step 1: Replace old presentation assertions with failing asset-set and story assertions**

Add a contract test shaped exactly like this, using the existing `readThemeFile` helper and parsed `template` object:

```js
test('unified template declares governed model story sets and no retired media slots', () => {
  const blocks = template.sections.main.blocks;
  assert.equal(blocks.model_30g.settings.story_asset_set, 'pimm30-production-v13');
  assert.equal(blocks.model_50g.settings.story_asset_set, 'pimm50-light-studio-v1');
  for (const block of Object.values(blocks)) {
    for (const retired of ['hero_asset', 'overview_asset', 'engineering_asset', 'tooling_asset']) {
      assert.equal(Object.hasOwn(block.settings, retired), false);
    }
  }
  assert.match(section, /render 'pimm-30g-product-story'/);
  assert.match(section, /render 'pimm-50g-product-story'/);
  assert.doesNotMatch(section, /pimm-engineering-bento|pimm-editorial-chapters/);
  assert.match(section, /"storyAssetSet":\s*\{\{ variant_story_asset_set \| json \}\}/);
});
```

Update the existing controller fixture records to include `storyAssetSet` and assert that `validateVariantRecord()` rejects a 30G record carrying the 50G set.

- [ ] **Step 2: Create the failing active-asset test**

Create `scripts/tests/pimm-unified-story-assets.test.mjs` with explicit arrays, not directory globs:

```js
const active30G = [
  'pimm30-v13-hero-desktop-contained.webm',
  'pimm30-v13-hero-desktop-contained.webp',
  'pimm30-v13-hero-mobile-contained.webm',
  'pimm30-v13-hero-mobile-contained.webp',
  'pimm30-capacity-three-cube-desktop.webm',
  'pimm30-capacity-three-cube-desktop.webp',
  'pimm30-temperature-controller-desktop.webm',
  'pimm30-temperature-controller-desktop.webp',
  'pimm30-v11-cylinder-desktop.webp',
  'pimm30-direct-operation-desktop.webm',
  'pimm30-v16-operation-desktop.webp',
  'pimm30-v16-operation-mobile.webp',
  'pimm30-v10-regulator-desktop.webp',
  'pimm30-v15-fixture-desktop.webp',
  'pimm30-v15-fixture-mobile.webp',
  'pimm30-v10-capacity-desktop.webp',
  'pimm30-v10-capacity-mobile.webp',
  'pimm30-configuration-turntable-desktop.webm',
  'pimm30-configuration-turntable-desktop.webp',
  'pimm30-v10-commerce-mobile.webp',
];
const active50G = ['hero', 'capacity', 'melt-zone', 'heating', 'mold-space', 'purchase']
  .map((name) => `pimm50-light-studio-${name}.webp`);
```

Assert every path exists. Require RIFF/WEBP signatures for `.webp` and the EBML header bytes `1a 45 df a3` for `.webm`. Keep the deprecated-reference scan out of this first contract test because the migration deliberately leaves the old files available until Task 4; Task 4 adds the active negative test before deletion.

- [ ] **Step 3: Run the focused tests and verify the expected failures**

Run:

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs scripts/tests/pimm-unified-story-assets.test.mjs
```

Expected: the product contract fails because `story_asset_set`, both new snippets, and `storyAssetSet` are absent. The asset existence/signature checks pass.

- [ ] **Step 4: Migrate the template and section payload minimally**

In `templates/product.pimm-configurator.json`, replace each model block's four media settings and their old alt fields with:

```json
"story_asset_set": "pimm30-production-v13"
```

and:

```json
"story_asset_set": "pimm50-light-studio-v1"
```

In the section schema replace the eight old filename/alt settings with one text setting:

```json
{ "type": "text", "id": "story_asset_set", "label": "Governed story asset set" }
```

During variant JSON construction, derive and validate the set by model and emit:

```liquid
"storyAssetSet": {{ variant_story_asset_set | json }},
```

Render temporary semantic story shells so the new render assertions pass without yet duplicating the existing page content:

```liquid
<div data-pimm-story-model="30G" {% unless selected_model_code == '30G' %}hidden inert aria-hidden="true"{% endunless %}>
  {% render 'pimm-30g-product-story', story_asset_set: 'pimm30-production-v13', selected_model_code: selected_model_code %}
</div>
<div data-pimm-story-model="50G" {% unless selected_model_code == '50G' %}hidden inert aria-hidden="true"{% endunless %}>
  {% render 'pimm-50g-product-story', story_asset_set: 'pimm50-light-studio-v1', selected_model_code: selected_model_code %}
</div>
```

Create both snippet files with guarded empty semantic roots so Liquid resolution succeeds; the complete markup is Task 2.

- [ ] **Step 5: Run the focused contract tests**

Run:

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs scripts/tests/pimm-unified-story-assets.test.mjs
```

Expected: all asset-set, asset-existence, and focused product contract tests PASS.

- [ ] **Step 6: Commit the contract migration**

```powershell
git add templates/product.pimm-configurator.json sections/maliev-pimm-machine-product.liquid snippets/pimm-30g-product-story.liquid snippets/pimm-50g-product-story.liquid scripts/tests/pimm-unified-product-page-contract.test.mjs scripts/tests/pimm-unified-story-assets.test.mjs
git commit -m "Define governed PIMM model story sets"
```

### Task 2: Build the 30G and 50G normal-scroll product stories

**Files:**
- Modify: `snippets/pimm-hero-console.liquid`
- Modify: `snippets/pimm-30g-product-story.liquid`
- Modify: `snippets/pimm-50g-product-story.liquid`
- Modify: `sections/maliev-pimm-machine-product.liquid`
- Modify: `assets/maliev-pimm-machine.js`
- Modify: `locales/en.default.json`
- Modify: `locales/th.json`
- Test: `scripts/tests/pimm-unified-product-page-contract.test.mjs`

**Interfaces:**
- Consumes: `storyAssetSet`, model specifications, existing selector radios, shared `data-pimm-spec` values, existing price/availability/lead-time/deposit bindings.
- Produces: `[data-pimm-story-model="30G|50G"]`; `[data-pimm-authoritative-media]`; `[data-pimm-full-machine]`; `[data-pimm-stage-baseline]`; 30G videos marked `[data-pimm-story-video]`; singular shared ownership and qualification regions.

- [ ] **Step 1: Add failing semantic and media-identity tests**

Add assertions that each story contains one introduction figure and its required evidence assets:

```js
test('model stories use only their authoritative production families', () => {
  for (const name of ['hero', 'capacity', 'melt-zone', 'heating', 'mold-space', 'purchase']) {
    assert.match(story50G, new RegExp(`pimm50-light-studio-${name}\\.webp`));
  }
  for (const name of [
    'pimm30-v13-hero-desktop-contained', 'pimm30-capacity-three-cube-desktop',
    'pimm30-temperature-controller-desktop', 'pimm30-v11-cylinder-desktop',
    'pimm30-v16-operation-desktop', 'pimm30-v10-regulator-desktop',
    'pimm30-v15-fixture-desktop', 'pimm30-v10-capacity-desktop',
    'pimm30-configuration-turntable-desktop',
  ]) assert.match(story30G, new RegExp(`${name}\\.(?:webp|webm)`));
  assert.doesNotMatch(story30G, /pimm50-/);
  assert.doesNotMatch(story50G, /pimm30-/);
});
```

Also assert one H1 across the section, one product form, one ownership render, one purchase-qualification render, ordered H2s, all inactive panels using `hidden inert aria-hidden="true"`, and every full-machine figure carrying `data-pimm-full-machine data-pimm-stage-baseline`.

- [ ] **Step 2: Run the contract test red**

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
```

Expected: FAIL on missing authoritative media, evidence chapters, and full-machine stage hooks.

- [ ] **Step 3: Refactor the shared decision header**

Keep the selector, title, selected specifications, demo action, and qualification link in `pimm-hero-console.liquid`. Remove the obsolete overview/engineering/tooling cells. Render two hero media groups inside the same stage:

```liquid
<div class="pimm-machine__hero-media" data-pimm-media-model="30G" data-pimm-media-slot="hero">
  <picture>...</picture>
  <video data-pimm-story-video muted playsinline loop preload="metadata">...</video>
</div>
<div class="pimm-machine__hero-media" data-pimm-media-model="50G" data-pimm-media-slot="hero">...</div>
```

Use `pimm30-v13-hero-desktop-contained` desktop/mobile poster and WebM pairs for 30G, and `pimm50-light-studio-hero.webp` for 50G. Both wrappers carry `data-pimm-full-machine data-pimm-stage-baseline`; only the selected 30G video receives metadata preload.

- [ ] **Step 4: Implement the complete 30G story snippet**

Guard output with:

```liquid
{% if story_asset_set == 'pimm30-production-v13' %}
  <section class="pimm-story pimm-story--30g" aria-label="{{ 'products.pimm_machine.story_30g.label' | t | escape }}">...</section>
{% endif %}
```

Create eight alternating evidence chapters in this order: shot capacity, temperature control, cylinder, direct operation, regulator, fixture, materials, configuration. Each chapter uses one `<figure>` followed by one copy block, explicit width/height, localized alt text, and the exact desktop/mobile poster or video pair from the specification. The configuration chapter is the second full-machine view and carries both grounding hooks.

- [ ] **Step 5: Implement the complete 50G story snippet**

Guard output with `story_asset_set == 'pimm50-light-studio-v1'`. Create five evidence chapters after the shared hero: capacity, melt zone, heating, mold space, and purchase preparation. Use each remaining light-studio image once, with the purchase image marked as a full-machine grounded view.

- [ ] **Step 6: Keep shared commerce singular and complete localization**

In the section, render the model-story panels between the shared intro and shared ownership/qualification snippets. Add matching English and Thai keys under `products.pimm_machine.story_30g` and `story_50g` for labels, headings, body copy, and alt text. Copy only verified facts already present in the existing 30G and 50G sections; do not add throughput, savings, certification, or performance claims.

- [ ] **Step 7: Extend model switching for video lifecycle**

Add these methods to `PimmMachineProduct` and call `syncStoryVideos(model)` after `showOnlyStory(model)` settles:

```js
syncStoryVideos(model) {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  this.querySelectorAll('[data-pimm-story-video]').forEach((video) => {
    const owner = video.closest('[data-pimm-media-model], [data-pimm-story-model]');
    const ownerModel = owner?.dataset.pimmMediaModel || owner?.dataset.pimmStoryModel;
    const active = !reduceMotion && ownerModel === model;
    if (!active) { video.pause(); video.currentTime = 0; return; }
    const playback = video.play();
    if (typeof playback?.catch === 'function') playback.catch(() => {});
  });
}
```

When the closest node is a story panel, read `dataset.pimmStoryModel`. Keep poster images visible when playback is unavailable. Update fixture tests with stubbed `play()` and `pause()` calls and assert inactive videos reset.

- [ ] **Step 8: Run focused tests and locale parsing**

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
node -e "JSON.parse(require('fs').readFileSync('locales/en.default.json')); JSON.parse(require('fs').readFileSync('locales/th.json')); console.log('locales ok')"
```

Expected: all focused tests PASS and locale parsing prints `locales ok`.

- [ ] **Step 9: Commit the complete story migration**

```powershell
git add sections/maliev-pimm-machine-product.liquid snippets/pimm-hero-console.liquid snippets/pimm-30g-product-story.liquid snippets/pimm-50g-product-story.liquid assets/maliev-pimm-machine.js locales/en.default.json locales/th.json scripts/tests/pimm-unified-product-page-contract.test.mjs
git commit -m "Replace unified PIMM page with model stories"
```

### Task 3: Replace the old cascade with grounded responsive presentation

**Files:**
- Replace: `assets/maliev-pimm-machine.css`
- Modify: `scripts/tests/pimm-unified-product-page-contract.test.mjs`
- Modify: `scripts/tests/pimm-unified-responsive-browser.test.mjs`

**Interfaces:**
- Consumes: `pimm-machine__hero-*`, `pimm-story`, `pimm-story__chapter`, `data-pimm-full-machine`, `data-pimm-stage-baseline`, selected/hidden model state.
- Produces: custom properties `--pimm-stage-object-bottom`, `--pimm-stage-object-height`, `--pimm-story-gap`; geometry probe fields `groundGap`, `opaqueFillRatio`, `overlap`, `overflowX`, `renderedRatio`.

- [ ] **Step 1: Add failing static CSS contract assertions**

Assert the new CSS contains normal-flow grid/flex composition and rejects the known failure modes:

```js
test('unified story CSS preserves intrinsic media and a measurable ground baseline', () => {
  assert.match(css, /\[data-pimm-stage-baseline\][^{]*\{[^}]*align-items:\s*end/s);
  assert.match(css, /\[data-pimm-full-machine\]\s+img[^}]*object-fit:\s*contain/s);
  assert.match(css, /\.pimm-story__chapter[^}]*display:\s*grid/s);
  assert.doesNotMatch(css, /object-fit:\s*cover\s*!important/);
  assert.doesNotMatch(css, /height:\s*100s?vh|scroll-snap|position:\s*sticky/);
  assert.doesNotMatch(css, /\.pimm-machine__editorial|\.pimm-machine__bento/);
});
```

- [ ] **Step 2: Run the static test red**

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
```

Expected: FAIL because the old 1,063-line cascade still contains bento/editorial and contradictory sizing rules.

- [ ] **Step 3: Replace the CSS file with one scoped system**

Write a fresh `.section-pimm-machine-product .pimm-machine` stylesheet using the established MALIEV canvas, surface, ink, cool gray, signal blue, IBM Plex, focus yellow, and dark outline tokens. Required layout rules:

```css
.pimm-machine__hero { display: grid; grid-template-columns: minmax(18rem, .8fr) minmax(22rem, 1.35fr); }
[data-pimm-stage-baseline] { display: grid; align-items: end; overflow: visible; }
[data-pimm-full-machine] img { display: block; inline-size: 100%; block-size: 100%; object-fit: contain; object-position: 50% 100%; }
.pimm-story__chapter { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(18rem, .85fr); align-items: center; }
.pimm-story__chapter:nth-child(even) .pimm-story__media { order: 2; }
[data-pimm-story-model][hidden] { display: none !important; }
```

Use per-asset full-machine sizing variables on the 30G hero, 30G configuration, 50G hero, and 50G purchase stages. Set them from the existing alpha-bound evidence in the 30G/50G tests; do not invent a shadow or hide contact points. At `max-width: 749px` and at a zoom-safe `max-width: 48rem`, switch the hero and chapters to one column and restore source order.

- [ ] **Step 4: Rewrite browser probes around the new story geometry**

Remove bento/editorial counts. For every selected model collect:

```js
const visibleStory = document.querySelector(`[data-pimm-story-model="${model}"]:not([hidden])`);
const fullMachines = [...document.querySelectorAll(
  `[data-pimm-story-model="${model}"]:not([hidden]) [data-pimm-full-machine], [data-pimm-media-model="${model}"]:not([hidden])[data-pimm-full-machine]`
)];
```

For each full-machine image return container/image rectangles, natural dimensions, rendered aspect ratio, opaque-bounds metadata, and `groundGap = baseline.bottom - image.bottom`. Assert `Math.abs(groundGap) <= 2`, image height is at least 60% of the stage height on desktop and 50% on mobile, and copy/media rectangles do not intersect.

- [ ] **Step 5: Run static tests and a single local browser fixture**

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
$env:PIMM_UNIFIED_PREVIEW_URL='http://127.0.0.1:9494/products_preview?preview_key=83c2b39bfb9a9fc14dad67d340dded26&view=pimm-configurator&variant=54823758659863&cb=story-css'
node --test --test-name-pattern "responsive browser acceptance" scripts/tests/pimm-unified-responsive-browser.test.mjs
```

Expected: static tests PASS. The browser test reaches the preview and reports real geometry; fix CSS until ground gap, minimum scale, overlap, and overflow assertions pass for its initial matrix.

- [ ] **Step 6: Commit the responsive presentation**

```powershell
git add assets/maliev-pimm-machine.css scripts/tests/pimm-unified-product-page-contract.test.mjs scripts/tests/pimm-unified-responsive-browser.test.mjs
git commit -m "Ground PIMM stories across responsive layouts"
```

### Task 4: Remove every deprecated storefront render and reference

**Files:**
- Modify: `package.json`
- Modify: `scripts/tests/pimm-unified-story-assets.test.mjs`
- Modify: `scripts/tests/pimm-unified-responsive-browser.test.mjs`
- Delete: `snippets/pimm-engineering-bento.liquid`
- Delete: `snippets/pimm-editorial-chapters.liquid`
- Delete: `scripts/tests/pimm-unified-render-assets.test.mjs`
- Delete: `scripts/tests/pimm-editorial-render-assets.test.mjs`
- Delete: `assets/pimm-unified-render-assets.v1.json`
- Delete: `assets/pimm-editorial-render-assets.v1.json`
- Delete: all 12 WebP derivatives listed in the specification.

**Interfaces:**
- Consumes: active story asset test and migrated runtime from Tasks 1–3.
- Produces: `npm run verify:render-assets` executing only `scripts/tests/pimm-unified-story-assets.test.mjs`; zero active references and zero files matching `assets/pimm-machine-*.webp` or `assets/pimm-editorial-*.webp`.

- [ ] **Step 1: Activate the failing negative reference test**

Replace the deferred test with an active scan over `sections`, `snippets`, `templates`, `assets/*.css`, `assets/*.js`, `scripts/tests`, and `package.json`:

```js
test('active storefront has no retired unified or editorial render references', async () => {
  const violations = await findMatches(activeSourcePaths, /pimm-(?:machine|editorial)-[^'"\s)]+\.(?:webp|json)/g);
  assert.deepEqual(violations, []);
});
```

Add file absence assertions for all 14 deprecated asset/manifests.

- [ ] **Step 2: Run the asset test red**

```powershell
node --test scripts/tests/pimm-unified-story-assets.test.mjs
```

Expected: FAIL with the remaining old files, `package.json` test command, and browser fixture references.

- [ ] **Step 3: Remove old assertions and update the verification command**

Set:

```json
"verify:render-assets": "node --test scripts/tests/pimm-unified-story-assets.test.mjs"
```

Remove old browser fixtures and expected media maps that name the deprecated images. Preserve variant, header, menu, focus, localization, and commerce acceptance coverage.

- [ ] **Step 4: Delete the obsolete snippets, tests, manifests, and 12 renders**

Use `apply_patch` delete operations for text files and exact literal paths for binary removal. Before removal, verify the target list equals 12 WebP files and two manifests. Do not remove `pimm30-*`, `pimm50-light-studio-*`, historical documentation, or Blender production sources.

- [ ] **Step 5: Prove the deletion and active reference boundary**

```powershell
node --test scripts/tests/pimm-unified-story-assets.test.mjs
rg -n "pimm-machine-|pimm-editorial-" sections snippets templates assets scripts/tests package.json
Get-ChildItem assets\pimm-machine-*.webp,assets\pimm-editorial-*.webp -ErrorAction SilentlyContinue
```

Expected: asset test PASS; `rg` returns no active source matches; `Get-ChildItem` returns no files.

- [ ] **Step 6: Commit the deprecated asset removal**

```powershell
git add package.json scripts/tests/pimm-unified-story-assets.test.mjs scripts/tests/pimm-unified-responsive-browser.test.mjs
git add -u -- assets snippets scripts/tests
git commit -m "Remove deprecated PIMM storefront renders"
```

### Task 5: Run the complete browser matrix and repository verification

**Files:**
- Modify only if evidence finds a defect: `assets/maliev-pimm-machine.css`, `assets/maliev-pimm-machine.js`, the two story snippets, or their focused tests.
- Generate ignored/local evidence only: browser screenshots under the existing test output directory.

**Interfaces:**
- Consumes: completed unified page, preview server on port 9494, both variant records, English/Thai localization.
- Produces: passing build/theme check, focused tests, asset tests, browser matrix, screenshots for both model heroes and grounded full-machine chapters.

- [ ] **Step 1: Run build/static validation first**

```powershell
npm run verify:theme
```

Expected: Theme Check completes with zero errors. Record warnings separately and confirm whether they pre-existed.

- [ ] **Step 2: Run focused and relevant test suites**

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs scripts/tests/pimm-unified-product-contract.test.mjs scripts/tests/pimm-unified-story-assets.test.mjs scripts/tests/pimm30-presentation-regressions.test.mjs scripts/tests/pimm50-product-page-contract.test.mjs scripts/tests/pimm50-light-studio-assets.test.mjs
npm run verify
```

Expected: all tests PASS and `npm run verify` returns exit code 0.

- [ ] **Step 3: Run the required live preview matrix**

Reload the existing development preview with a fresh cache key:

```powershell
$env:PIMM_UNIFIED_PREVIEW_URL='http://127.0.0.1:9494/products_preview?preview_key=83c2b39bfb9a9fc14dad67d340dded26&view=pimm-configurator&variant=54823758659863&cb=unified-story-final'
node --test scripts/tests/pimm-unified-responsive-browser.test.mjs
```

The test must cover English and Thai at 1440x900, 1280x800, 1024x768, 390x844, and 360x800; switch both models at every viewport; run short-desktop, tall-mobile, keyboard, reduced-motion, and 200% zoom fixtures; and save selected-model hero plus every grounded full-machine screenshot.

- [ ] **Step 4: Review screenshots at actual pixels**

Open each generated 30G/50G hero, 30G configuration, and 50G purchase screenshot. Reject any frame with a visible foot gap, tiny product scale, clipped cylinder/base, stretched detail crop, mixed-model asset, unreadable controller, overlapping copy, or an unexplained empty media field. If a defect appears, first add or tighten the corresponding geometry assertion, make the smallest CSS/Liquid fix, then rerun Steps 1–3.

- [ ] **Step 5: Run final hygiene and reference checks**

```powershell
git diff --check
rg -n "pimm-machine-|pimm-editorial-" sections snippets templates assets scripts/tests package.json
git status --short
```

Expected: no whitespace errors; no active deprecated references; status contains only intentional validated corrections or is clean after the final commit.

- [ ] **Step 6: Commit any evidence-driven correction**

If Step 4 required a code correction:

```powershell
git add assets/maliev-pimm-machine.css assets/maliev-pimm-machine.js snippets/pimm-30g-product-story.liquid snippets/pimm-50g-product-story.liquid scripts/tests/pimm-unified-product-page-contract.test.mjs scripts/tests/pimm-unified-responsive-browser.test.mjs
git commit -m "Finish PIMM product story browser acceptance"
```

If no correction was needed, do not create an empty commit.

- [ ] **Step 7: Produce the completion report**

Report the exact files and assets removed, the selected-model and commerce boundaries preserved, every validation command with pass counts, screenshot locations, commit hashes, and any pre-existing warnings. State explicitly that no push, deployment, production theme mutation, or catalog mutation occurred.
