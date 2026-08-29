# PIMM 50G Light Studio Product Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the PIMM 50G Keynote experience with a normally scrolling light-studio product page using authentic transparent Blender media, purposeful engineering motion, and native Shopify commerce.

**Architecture:** The Shopify section remains the single authoritative product journey, but its markup becomes content-driven normal flow instead of viewport chapters. A revised Blender builder owns transparent studio scenes and exact animation/poster pairs; focused Node contracts verify page semantics, media transparency, native commerce, normal scrolling, and fallback behavior. CSS handles editorial composition and explanatory micro-motion, while JavaScript only enhances already-visible content and media playback.

**Tech Stack:** Shopify Liquid and section schema, CSS, dependency-free browser JavaScript, Node.js test runner, Shopify Theme Check, Blender 5.2 Python API, Pillow for alpha validation, WebP/WebM asset optimization, browser viewport automation.

## Global Constraints

- The route is `/products/pneumatic-injection-molding-machine-50g`.
- The page scrolls normally: no `scroll-snap-type`, `scroll-snap-stop`, forced viewport chapter heights, wheel interception, or scripted section advancement.
- All machine stills use transparent alpha; no baked rectangles, CSS feather masks, side fades, or artificial CSS ground shadows.
- Animated and static asset pairs share the exact camera, projection, crop, transforms, lighting, color management, and final frame.
- Content is visible before JavaScript runs; enhancement must never gate the product, copy, specifications, or form.
- Motion uses restrained ease-out timing, does not fake 3D from a flat still, and supports `prefers-reduced-motion`.
- Demo session remains the primary conversion; Add to cart remains secondary and uses the native Shopify product form.
- Essential decision copy is never hidden to fit a breakpoint.
- All controls are at least 44px high and use Focus Yellow for `:focus-visible`.
- The page has zero horizontal document overflow at 320px and above.
- Do not restore Dawn product, related-product, app, or multicolumn sections beneath the custom journey.
- Do not publish unverified compressor consumption, warranty, commissioning, payment, or delivery claims.
- Do not push or deploy without explicit authorization.

## File and Interface Map

- `sections/maliev-pimm-50g-launch.liquid`: semantic product narrative, native form, picture/video fallbacks, merchant settings.
- `assets/maliev-pimm-50g-story.css`: light-studio tokens, normal-flow layouts, responsive composition, focus, and CSS explanatory motion.
- `assets/maliev-pimm-50g-story.js`: optional viewport reveals, finite media playback, fallback handling, and Shopify section lifecycle.
- `scripts/blender/create_pimm50_light_studio.py`: idempotent owner of dedicated light-studio Blender scenes and exports.
- `scripts/tests/pimm50-light-studio-blender.test.mjs`: source-level Blender contract.
- `scripts/tests/pimm50-light-studio-assets.test.mjs`: dimensions, alpha bounds, filenames, and animation/poster parity metadata.
- `scripts/tests/pimm50-product-page-contract.test.mjs`: Liquid/CSS/JS/template contract replacing the Keynote test.
- `scripts/tests/pimm50-responsive-browser.test.mjs`: live geometry, normal scroll, accessibility, media fallback, and commerce checks.
- `assets/pimm50-light-studio-*`: promoted transparent stills, posters, and approved finite animations.

---

### Task 1: Lock the Normal-Scroll Product Contract

**Files:**
- Create: `scripts/tests/pimm50-product-page-contract.test.mjs`
- Delete after replacement: `scripts/tests/pimm50-keynote-contract.test.mjs`
- Modify: `sections/maliev-pimm-50g-launch.liquid`
- Modify: `assets/maliev-pimm-50g-story.css`
- Modify: `assets/maliev-pimm-50g-story.js`

**Interfaces:**
- Consumes: existing `product`, `selected_or_first_available_variant`, `section.settings.visit_link`, and current verified 50G asset names.
- Produces: eight normal-flow section IDs, `[data-pimm50-page]`, `[data-pimm50-motion]`, `[data-pimm50-media]`, and a native product form.

- [ ] **Step 1: Write the failing product-page contract**

Create a test that explicitly rejects the Keynote behavior:

```js
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const section = await readFile(new URL('../../sections/maliev-pimm-50g-launch.liquid', import.meta.url), 'utf8');
const css = await readFile(new URL('../../assets/maliev-pimm-50g-story.css', import.meta.url), 'utf8');
const js = await readFile(new URL('../../assets/maliev-pimm-50g-story.js', import.meta.url), 'utf8');

test('50G is a normally scrolling product narrative', () => {
  assert.match(section, /data-pimm50-page/);
  for (const id of ['hero', 'overview', 'capacity', 'melt-zone', 'heating', 'mold-space', 'comparison', 'purchase']) {
    assert.match(section, new RegExp(`id="pimm50-${id}"`));
  }
  assert.doesNotMatch(css, /scroll-snap-(?:type|align|stop)/);
  assert.doesNotMatch(css, /height:\s*calc\(100s?vh/);
  assert.doesNotMatch(js, /wheel|scrollIntoView|preventDefault/);
});

test('product and commerce remain visible without JavaScript', () => {
  assert.match(section, /<h1[^>]*>\s*PIMM 50G/);
  assert.match(section, /\{%[-]?\s*form 'product'/);
  assert.match(section, /name="id"/);
  assert.match(section, /name="add"/);
  assert.match(section, /Book a demo session/);
  assert.doesNotMatch(css, /opacity:\s*0[^}]*data-pimm50-page/);
});
```

- [ ] **Step 2: Run the contract and prove it fails against the Keynote implementation**

Run:

```powershell
node --test scripts/tests/pimm50-product-page-contract.test.mjs
```

Expected: failure on the missing `data-pimm50-page` hook and forbidden scroll-snap rules.

- [ ] **Step 3: Replace chapter semantics with normal-flow product sections**

In Liquid, keep one H1 and use section elements with content-driven wrappers:

```liquid
<div class="pimm50-page" data-pimm50-page>
  <section class="pimm50-hero" id="pimm50-hero" aria-labelledby="pimm50-title">...</section>
  <section class="pimm50-overview" id="pimm50-overview" aria-labelledby="pimm50-overview-title">...</section>
  <!-- capacity, melt-zone, heating, mold-space, comparison, purchase -->
</div>
```

Remove the fixed chapter rail, scroll cue, `data-pimm50-chapter`, and reveal-state dependencies. Keep current verified copy and the native product form until new media is promoted.

- [ ] **Step 4: Replace viewport CSS with light-studio normal flow**

Establish the page shell without forcing section heights:

```css
.pimm50-page {
  --p50-canvas: #fff;
  --p50-surface: #f2f4f5;
  --p50-ink: #111315;
  --p50-muted: #4d5762;
  --p50-blue: #006fd6;
  background: var(--p50-canvas);
  color: var(--p50-ink);
  overflow: clip;
}

.pimm50-page > section {
  min-height: auto;
  padding-block: clamp(6rem, 10vw, 14rem);
}
```

Hero desktop starts with a 42/58 grid; below 768px it becomes media-first stacked flow. Do not add a new hiding rule for explanatory paragraphs.

- [ ] **Step 5: Reduce JavaScript to progressive enhancement**

Expose only idempotent initialization and visible-by-default motion hooks:

```js
const init = (page) => {
  if (page.dataset.ready === 'true') return;
  page.dataset.ready = 'true';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduced) return;
  // Observe optional [data-pimm50-motion] elements and play finite media once.
};
```

No observer may control layout, scrolling, active navigation, or initial visibility.

- [ ] **Step 6: Run focused checks**

Run:

```powershell
node --test scripts/tests/pimm50-product-page-contract.test.mjs
npm run verify
git diff --check
```

Expected: contract passes, Theme Check reports zero errors, diff check is clean.

- [ ] **Step 7: Commit the normal-scroll structural slice**

```powershell
git add -- sections/maliev-pimm-50g-launch.liquid assets/maliev-pimm-50g-story.css assets/maliev-pimm-50g-story.js scripts/tests/pimm50-product-page-contract.test.mjs scripts/tests/pimm50-keynote-contract.test.mjs
git commit -m "Replace PIMM 50G keynote scrolling with product flow"
```

---

### Task 2: Build the Dedicated Transparent Light-Studio Blender Project

**Files:**
- Create: `scripts/blender/create_pimm50_light_studio.py`
- Create: `scripts/tests/pimm50-light-studio-blender.test.mjs`
- Create off-repository: `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\PIMM-50g-light-studio-v1.blend`

**Interfaces:**
- Consumes: immutable corrected source `PIMM-50g-keynote-reveal-v2-regulator-materials.blend`, `Machine_50g`, 481-object contract.
- Produces: scenes prefixed `PIMM50_LIGHT_`, RGBA PNG proofs, animation frames, and a JSON summary between `PIMM50_LIGHT_STUDIO_SUMMARY_BEGIN/END`.

- [ ] **Step 1: Write the failing Blender source contract**

Assert the dedicated target, source hash guard, ownership prefix, transparent film, RGBA output, scene list, and paired poster/animation camera assertions:

```js
test('builder owns transparent light studio scenes', () => {
  assert.match(script, /PIMM-50g-light-studio-v1\.blend/);
  assert.match(script, /EXPECTED_MACHINE_OBJECTS\s*=\s*481/);
  assert.match(script, /PREFIX\s*=\s*"PIMM50_LIGHT_"/);
  assert.match(script, /film_transparent\s*=\s*True/);
  assert.match(script, /color_mode\s*=\s*"RGBA"/);
  for (const scene of ['HERO', 'CAPACITY', 'MELT_ZONE', 'HEATING', 'MOLD_SPACE', 'PURCHASE']) {
    assert.match(script, new RegExp(scene));
  }
  assert.match(script, /assert_animation_poster_parity/);
});
```

- [ ] **Step 2: Run tests and prove the builder is absent**

Run:

```powershell
node --test scripts/tests/pimm50-light-studio-blender.test.mjs
```

Expected: failure because `create_pimm50_light_studio.py` does not exist.

- [ ] **Step 3: Implement immutable source and scene ownership guards**

Reuse the verified source hash and object contract from `create_pimm50_product_story.py`. Delete or replace only objects/scenes whose names start with `PIMM50_LIGHT_`. Never alter or save over the corrected source.

- [ ] **Step 4: Create the studio render configuration**

For every scene set:

```python
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.film_transparent = True
scene.view_settings.look = "AgX - Medium High Contrast"
```

Use neutral area lights derived from the approved master. Contact shadows must fade within the alpha canvas. Do not add a visible world plane or baked white background.

- [ ] **Step 5: Create named still scenes with explicit focus**

Produce:

- `PIMM50_LIGHT_HERO`: complete front three-quarter machine with full shadow bounds;
- `PIMM50_LIGHT_CAPACITY`: larger cylinder and plunger assembly while preserving orientation;
- `PIMM50_LIGHT_MELT_ZONE`: steel melt-zone assembly;
- `PIMM50_LIGHT_HEATING`: real controller enclosure and digits;
- `PIMM50_LIGHT_MOLD_SPACE`: M10 grid and mold interface;
- `PIMM50_LIGHT_PURCHASE`: complete three-quarter machine for configuration.

Each complete-machine scene must retain at least 8% alpha breathing room on all sides of the non-transparent bounding box.

- [ ] **Step 6: Create finite hero and heating animation scenes**

The hero sequence animates only studio light energy/exposure and ends on the still-scene lighting. The heating sequence changes the controller display materials authored on the actual display geometry. It does not use compositor text, image overlays, or HTML digits.

Add a function that compares final animated camera matrix, object transforms, render resolution, and color settings to its poster scene and raises on drift:

```python
def assert_animation_poster_parity(animation, poster):
    assert tuple(animation.camera.matrix_world) == tuple(poster.camera.matrix_world)
    assert animation.render.resolution_x == poster.render.resolution_x
    assert animation.render.resolution_y == poster.render.resolution_y
    assert animation.view_settings.look == poster.view_settings.look
```

- [ ] **Step 7: Compile and run the Blender builder**

Run:

```powershell
python -m py_compile scripts/blender/create_pimm50_light_studio.py
node --test scripts/tests/pimm50-light-studio-blender.test.mjs
blender -b "M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\PIMM-50g-keynote-reveal-v2-regulator-materials.blend" -P scripts/blender/create_pimm50_light_studio.py -- --render-proofs
```

Expected: target `.blend` created, source SHA/timestamp unchanged, summary lists all owned scenes and proof paths.

- [ ] **Step 8: Inspect proof renders before animation export**

Review hero, heating, mold-space, and purchase proofs at original resolution. Reject any render with clipped machine extents, rectangular alpha, controller digit drift, excessive dark reflection, or camera mismatch.

- [ ] **Step 9: Commit the Blender builder and contract**

```powershell
git add -- scripts/blender/create_pimm50_light_studio.py scripts/tests/pimm50-light-studio-blender.test.mjs
git commit -m "Build dedicated PIMM 50G light studio scenes"
```

The `.blend` target stays off-repository.

---

### Task 3: Promote and Validate Transparent Media

**Files:**
- Create: `assets/pimm50-light-studio-hero.webp`
- Create: `assets/pimm50-light-studio-capacity.webp`
- Create: `assets/pimm50-light-studio-melt-zone.webp`
- Create: `assets/pimm50-light-studio-heating.webp`
- Create: `assets/pimm50-light-studio-mold-space.webp`
- Create: `assets/pimm50-light-studio-purchase.webp`
- Create when approved: `assets/pimm50-light-studio-hero.webm`
- Create when approved: `assets/pimm50-light-studio-heating.webm`
- Create: `scripts/tests/pimm50-light-studio-assets.test.mjs`

**Interfaces:**
- Consumes: Task 2 RGBA proofs and finite Blender frame sequences.
- Produces: optimized theme media with stable filenames and verified transparent bounds.

- [ ] **Step 1: Write the failing asset contract**

Use Pillow through Node child-process execution or a small inline Python probe to assert every still opens as RGBA, has non-empty alpha, and retains required breathing room:

```js
for (const name of requiredStills) {
  assert.ok(existsSync(new URL(`../../assets/${name}`, import.meta.url)));
}
assert.equal(probe.every((asset) => asset.mode === 'RGBA'), true);
assert.equal(probe.every((asset) => asset.alpha_bbox !== null), true);
assert.equal(probe.every((asset) => asset.edge_clearance_ratio >= 0.08), true);
```

- [ ] **Step 2: Run the test and confirm missing promoted assets**

Run:

```powershell
node --test scripts/tests/pimm50-light-studio-assets.test.mjs
```

Expected: failure listing the missing `pimm50-light-studio-*` assets.

- [ ] **Step 3: Convert approved PNG stills without flattening alpha**

Use Pillow with lossless WebP first; reduce quality only if the rendered comparison remains visually identical:

```python
image = Image.open(source).convert("RGBA")
image.save(target, "WEBP", lossless=True, method=6)
```

- [ ] **Step 4: Encode finite animations with alpha only when storefront support is proven**

Prefer VP9 WebM with alpha. If the local browser test reports missing alpha playback, ship the transparent poster and defer animation rather than flattening to white or black.

- [ ] **Step 5: Run alpha, dimension, size, and parity validation**

Run:

```powershell
node --test scripts/tests/pimm50-light-studio-assets.test.mjs
```

Expected: all required stills pass alpha bounds; optional animations pass dimensions/duration/final-frame parity.

- [ ] **Step 6: Commit validated media**

```powershell
git add -- assets/pimm50-light-studio-* scripts/tests/pimm50-light-studio-assets.test.mjs
git commit -m "Add transparent PIMM 50G light studio media"
```

---

### Task 4: Build the Editorial Product Sections and Motion

**Files:**
- Modify: `sections/maliev-pimm-50g-launch.liquid`
- Modify: `assets/maliev-pimm-50g-story.css`
- Modify: `assets/maliev-pimm-50g-story.js`
- Modify: `scripts/tests/pimm50-product-page-contract.test.mjs`

**Interfaces:**
- Consumes: Task 3 stable asset names and Task 1 normal-flow hooks.
- Produces: media-first hero, overview strip, five engineering sections, comparison, purchase, finite animation fallbacks, and responsive editorial layouts.

- [ ] **Step 1: Extend the failing contract for approved media and semantic structure**

Assert every promoted asset appears in a `<picture>`, `<video>`, or poster fallback; require one H1; reject the old red-stage/keynote asset names and fixed rail.

- [ ] **Step 2: Implement the 42/58 light-studio hero**

Use a `<picture>` poster beneath an optional finite `<video muted playsinline>` so failure leaves the alpha still visible. Keep the H1, proposition, four proof facts, demo session, and engineering anchor in HTML.

- [ ] **Step 3: Implement the overview proof strip**

Use one semantic `<dl>` separated by rules and spacing, not individual cards. Include shot, steel melt zone, heating, mold envelope, and made-to-order/lead-time evidence.

- [ ] **Step 4: Implement varied engineering compositions**

Capacity uses an asymmetrical machine-led composition; melt zone uses a cool-gray close-up; heating uses controller media plus real readouts; mold space uses dimension annotations; no two consecutive sections share an identical template.

- [ ] **Step 5: Implement CSS explanatory motion**

Use visible defaults and opt-in `is-in-view` enhancement:

```css
[data-pimm50-motion] { --p50-progress: 1; }
.js [data-pimm50-motion]:not(.is-in-view) { --p50-progress: 0; }
@media (prefers-reduced-motion: reduce) {
  [data-pimm50-motion] { --p50-progress: 1; transition: none; }
}
```

Limit media travel to 2–3%, use clip/scale for dimension lines, and never animate page geometry.

- [ ] **Step 6: Implement finite media playback and fallback**

JavaScript plays each video once when it approaches the viewport, pauses on end, and leaves the poster-aligned final frame. On `error`, add `is-media-failed` and reveal the poster; no content visibility changes.

- [ ] **Step 7: Implement matched-scale comparison**

Align the complete 30G and 50G alpha machines on a common baseline. Present verified decision facts in semantic rows and link to the 30G product plus factory consultation.

- [ ] **Step 8: Implement configuration and purchase in normal flow**

Keep the current native select/form. Use the approved purchase alpha render and no fake drag/3D interaction. Make the demo session button visually primary and Add to cart secondary.

- [ ] **Step 9: Run focused validation**

Run:

```powershell
node --test scripts/tests/pimm50-product-page-contract.test.mjs scripts/tests/pimm50-light-studio-assets.test.mjs
npm run verify
git diff --check
```

- [ ] **Step 10: Commit the product presentation**

```powershell
git add -- sections/maliev-pimm-50g-launch.liquid assets/maliev-pimm-50g-story.css assets/maliev-pimm-50g-story.js scripts/tests/pimm50-product-page-contract.test.mjs
git commit -m "Present PIMM 50G in a light studio product flow"
```

---

### Task 5: Harden Responsive, Accessibility, and Commerce Behavior

**Files:**
- Create: `scripts/tests/pimm50-responsive-browser.test.mjs`
- Modify only when failing: `sections/maliev-pimm-50g-launch.liquid`
- Modify only when failing: `assets/maliev-pimm-50g-story.css`
- Modify only when failing: `assets/maliev-pimm-50g-story.js`

**Interfaces:**
- Consumes: local route, `[data-pimm50-page]`, native product form, and optional media hooks.
- Produces: repeatable browser geometry and behavior evidence.

- [ ] **Step 1: Add normal-scroll assertions before layout fixes**

At each viewport, record initial `scrollY`, issue a 400px wheel/scroll delta, and assert document movement is proportional rather than landing on a section boundary. Assert computed `scrollSnapType === 'none'` and no section uses viewport-fixed height.

- [ ] **Step 2: Add geometry and content assertions**

For 320×568, 390×844, 430×932, 768×1024, 820×1180, 1024×768, 1440×900, 1920×1080, 3840×2160, 720×540, and 852×393, assert:

- document `scrollWidth === clientWidth`;
- every H1/H2, paragraph, fact, select, and action is inside its section;
- no copy/media collision obscures semantic text;
- alpha media use `object-fit: contain`;
- purchase controls are at least 44px high and enabled when the variant is available.

- [ ] **Step 3: Add media and reduced-motion assertions**

Emulate reduced motion and assert videos are paused/hidden while posters remain visible. Force a media error and assert the poster stays rendered and section content does not move.

- [ ] **Step 4: Add keyboard and commerce assertions**

Tab through the variant select, demo session, and Add to cart. Require a visible yellow focus outline and correct element order. Verify the selected option's value is the submitted `name="id"` and the add button remains inside the Shopify form.

- [ ] **Step 5: Run the initial matrix and fix deterministic failures**

Run the local test command selected from the repository's available browser harness. If no checked-in browser runner exists, execute the same assertions through the in-app browser and record the viewport matrix in the task log rather than adding an un-runnable dependency.

- [ ] **Step 6: Run repository verification**

```powershell
npm run verify
node --test scripts/tests/pimm50-*.test.mjs
git diff --check
```

- [ ] **Step 7: Commit the hardening slice**

```powershell
git add -- scripts/tests/pimm50-responsive-browser.test.mjs sections/maliev-pimm-50g-launch.liquid assets/maliev-pimm-50g-story.css assets/maliev-pimm-50g-story.js
git commit -m "Harden PIMM 50G product page across breakpoints"
```

---

### Task 6: Final Impeccable Critique and Review Handoff

**Files:**
- Modify only files implicated by confirmed critique findings.
- Create through helper: `.impeccable/critique/<timestamp>__pimm-50g-light-studio-product-page.md`

**Interfaces:**
- Consumes: fully validated local route and approved design specification.
- Produces: two independent assessments, detector output, resolved priority findings, final screenshots, and a scoped final commit.

- [ ] **Step 1: Run Impeccable Assessment A**

Evaluate the live page against brand direction, AI-slop patterns, Nielsen heuristics, cognitive load, Jordan/Riley/Casey, and the Thai workshop buyer. Require special attention to product scale, normal scrolling, decision confidence, and automotive-reference restraint.

- [ ] **Step 2: Run independent Assessment B**

Run:

```powershell
node .agents/skills/impeccable/scripts/detect.mjs --json sections/maliev-pimm-50g-launch.liquid assets/maliev-pimm-50g-story.css
```

Independently verify geometry, contrast, keyboard focus, reduced motion, alpha containment, and purchase actions at the full matrix.

- [ ] **Step 3: Resolve all confirmed P0/P1 and in-scope P2 findings**

Reject findings only with direct browser/source evidence. Do not fix external Bucks SDK or cookie-app behavior by hacking the product section.

- [ ] **Step 4: Rerun both assessments**

Require zero unresolved P0/P1. Persist the final critique through `critique-storage.mjs` and record the trend.

- [ ] **Step 5: Run the complete final gate**

```powershell
python -m py_compile scripts/blender/create_pimm50_light_studio.py
node --test scripts/tests/pimm50-*.test.mjs
npm run verify
git diff --check
```

Also verify Blender source immutability, alpha bounds, desktop/tablet/mobile/short-landscape screenshots, and that no unrelated dirty files are staged.

- [ ] **Step 6: Commit final polish**

```powershell
git add -- <only confirmed in-scope files>
git commit -m "Polish PIMM 50G light studio product page"
```

- [ ] **Step 7: Open the local route for user review**

Open:

```text
http://127.0.0.1:9393/products/pneumatic-injection-molding-machine-50g?review=light-studio-final
```

Report commits and validation. Do not push or deploy.

## Self-Review Results

- Spec coverage: all page architecture, media, motion, responsive, accessibility, commerce, fallback, validation, and exclusion requirements map to Tasks 1–6.
- Placeholder scan: no implementation placeholders or undefined follow-up tasks remain.
- Interface consistency: `data-pimm50-page`, `data-pimm50-motion`, `data-pimm50-media`, `PIMM50_LIGHT_`, and `pimm50-light-studio-*` remain consistent across producing and consuming tasks.
- Scope: Blender production and storefront implementation are separate validated slices but converge on one deployable product page.
