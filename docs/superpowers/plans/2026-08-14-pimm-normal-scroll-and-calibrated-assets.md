# PIMM Normal-Scroll and Calibrated Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace obsolete 30G/50G storefront media with validated calibrated assets, correct every 50G controller to 350/350, and rebuild the 30G page as a six-section normal-scrolling product presentation with testable motion.

**Architecture:** Import the already-reviewed shared Blender calibration pipeline, correct and rerender the 50G product truth before promotion, then convert coherent native proofs into versioned theme assets. Rebuild the 30G section and template around six semantic roles in ordinary document flow, and use a small one-shot IntersectionObserver enhancement with a port-scoped local motion override.

**Tech Stack:** Shopify Liquid and JSON templates, CSS, browser JavaScript, Node `node:test`, Chromium CDP, Blender 5.2 Python/Cycles, WebP/WebM storefront media, Shopify Theme Check.

## Global Constraints

- PIMM 30G maximum temperature is exactly 300°C.
- PIMM 50G maximum temperature is exactly 350°C; every controller-bearing 50G render displays physical mesh 350/350.
- PIMM 50G heater power remains a separate `2 × 350 W` fact.
- The 30G dark-studio startup appears only in the 30G hero; all normal 30G imagery and every 50G asset use the bright studio.
- Blender source SHA-256, size, and modification time must be identical before and after render generation.
- Use versioned storefront filenames: `pimm30-cal-v1-*` and `pimm50-cal-v2-350c-*`.
- Do not use `scroll-snap-*`, fixed/sticky story stages, viewport-height chapters, wheel/touch interception, or programmatic chapter scrolling.
- All content is visible without JavaScript; motion is a one-time progressive enhancement.
- Hosted storefronts honor `prefers-reduced-motion`; only `127.0.0.1:9393` forces full motion for QA.
- Preserve native Shopify variant, price, availability, Add to Cart, and factory-visit behavior.
- Do not push, deploy, or publish the theme.

---

## File Structure

- `scripts/blender/pimm_rendering_system.py` — shared material, studio, alpha-shadow, mask, and proof-quality contracts.
- `scripts/blender/create_pimm30_calibrated_studio.py` — coherent calibrated 30G scene/proof builder.
- `scripts/blender/create_pimm50_calibrated_studio.py` — coherent calibrated 50G scene/proof builder with correct 350/350 physical readouts.
- `scripts/blender/pimm_active_render_manifest.json` — immutable source identities and contracted output inventory.
- `scripts/blender/test_pimm_rendering_system.py` — Blender semantic mutation tests.
- `scripts/tests/pimm*-calibrated-blender.test.mjs` — Node wrappers for source, builder, and non-promotion contracts.
- `scripts/tests/pimm-storefront-assets.test.mjs` — new versioned asset and product-truth consumer contract.
- `scripts/tests/pimm30-normal-scroll-contract.test.mjs` — new section/template/motion source contract.
- `scripts/tests/pimm30-normal-scroll-browser.test.mjs` — new responsive, motion, focus, and commerce browser harness.
- `sections/maliev-pimm-30g-story.liquid` — six-section 30G product presentation and native product form.
- `assets/maliev-pimm-30g.css` — normal-flow 30G layout and reveal styling.
- `assets/maliev-pimm-30g.js` — one-shot reveal and local debug-motion behavior.
- `templates/product.injection-molding-machine.json` — six semantic 30G section blocks and calibrated asset defaults.
- `sections/maliev-pimm-50g-launch.liquid` — corrected versioned 50G asset consumers and product truth.
- `assets/maliev-pimm-50g-story.js` / `.css` — local motion override while retaining hosted reduced-motion behavior.
- `assets/pimm30-cal-v1-*` / `assets/pimm50-cal-v2-350c-*` — promoted calibrated storefront files.

---

### Task 1: Integrate the validated calibrated rendering pipeline

**Files:**
- Create: `scripts/blender/create_pimm30_calibrated_studio.py`
- Create: `scripts/blender/create_pimm50_calibrated_studio.py`
- Create: `scripts/blender/pimm_rendering_system.py`
- Create: `scripts/blender/pimm_active_render_manifest.json`
- Create: `scripts/blender/test_pimm_rendering_system.py`
- Create: `scripts/tests/pimm-rendering-system-contract.test.mjs`
- Create: `scripts/tests/pimm30-calibrated-blender.test.mjs`
- Create: `scripts/tests/pimm50-calibrated-blender.test.mjs`
- Modify: `scripts/blender/create_pimm30_direct_operation_toggle.py`

**Interfaces:**
- Consumes: immutable 30G and 50G `.blend` identities from `pimm_active_render_manifest.json`.
- Produces: `build_calibrated_studio(...)`, model-specific scene builders, proof validators, and CLI `--validate-only` / proof-generation contracts used by Tasks 2 and 3.

- [ ] **Step 1: Import the reviewed rendering commits**

Run:

```powershell
git cherry-pick 3d213dc^..24c6245
```

Expected: all rendering-system commits apply on top of the current branch without modifying theme consumers.

- [ ] **Step 2: Run the focused contracts before product-truth correction**

Run:

```powershell
node --test scripts/tests/pimm-rendering-system-contract.test.mjs scripts/tests/pimm30-calibrated-blender.test.mjs scripts/tests/pimm50-calibrated-blender.test.mjs
```

Expected: rendering architecture tests pass, while Task 2 will add a new failing 350/350 contract before changing the 50G builder.

- [ ] **Step 3: Confirm no storefront promotion occurred**

Run:

```powershell
git diff f1df6ce..HEAD -- assets sections templates
```

Expected: no calibrated theme assets or Liquid/template consumer edits from the rendering pipeline integration.

---

### Task 2: Correct the 50G controller truth to 350/350

**Files:**
- Modify: `scripts/blender/create_pimm50_calibrated_studio.py`
- Modify: `scripts/blender/test_pimm_rendering_system.py`
- Modify: `scripts/tests/pimm50-calibrated-blender.test.mjs`

**Interfaces:**
- Consumes: physical controller-segment builder and exact legacy LED mesh inventory from Task 1.
- Produces: `CONTROLLER_READOUT_C = 350`, physical mesh pattern `350`, exact red/green segment counts, and a coherent 10-proof native generation eligible for conversion.

- [ ] **Step 1: Write the failing 350°C contract**

Add assertions equivalent to:

```js
assert.match(builder, /CONTROLLER_READOUT_C\s*=\s*350/);
assert.match(builder, /CONTROLLER_READOUT_PATTERN\s*=\s*["']350["']/);
assert.doesNotMatch(builder, /CONTROLLER_READOUT_C\s*=\s*300/);
```

and Blender semantic assertions that every controller-bearing scene has four physical `350` readouts, all legacy source LED meshes are hidden, no `FONT` or image overlay is used, and controller-free outputs remain controller-free.

- [ ] **Step 2: Run the contract to verify RED**

Run:

```powershell
node --test scripts/tests/pimm50-calibrated-blender.test.mjs
```

Expected: FAIL because the imported builder encodes 300/300.

- [ ] **Step 3: Restore the physical 350/350 builder contract**

Change only model truth and exact segment expectations:

```python
CONTROLLER_READOUT_C = 350
CONTROLLER_READOUT_PATTERN = "350"
```

Update readout comments, validation properties, and segment-count assertions so they describe 50G 350°C operation. Keep `2 × 350 W` separate.

- [ ] **Step 4: Validate the builder without rendering**

Run:

```powershell
python -m py_compile scripts/blender/create_pimm50_calibrated_studio.py scripts/blender/pimm_rendering_system.py
node --test scripts/tests/pimm50-calibrated-blender.test.mjs
```

Expected: Node test passes, Blender semantic tests pass, immutable source identity is unchanged, and no theme asset exists yet.

- [ ] **Step 5: Render and review the coherent 50G native generation**

Run the builder against the immutable manifest source using its documented proof CLI at 100% and the contracted sample count. Require all ten outputs in one generation: hero, capacity, melt zone, heating, mold space, purchase, desktop start/end, and mobile start/end.

Expected: all proof validators pass; every controller-bearing original shows physical 350/350; desktop and mobile start/end pixels are identical; source SHA/size/mtime are unchanged.

- [ ] **Step 6: Commit the product-truth correction**

```powershell
git add scripts/blender/create_pimm50_calibrated_studio.py scripts/blender/test_pimm_rendering_system.py scripts/tests/pimm50-calibrated-blender.test.mjs
git commit -m "Correct PIMM 50G calibrated controller readouts"
```

---

### Task 3: Convert and promote coherent calibrated storefront assets

**Files:**
- Create: `scripts/tests/pimm-storefront-assets.test.mjs`
- Create: `assets/pimm30-cal-v1-*`
- Create: `assets/pimm50-cal-v2-350c-*`
- Modify: `sections/maliev-pimm-30g-story.liquid`
- Modify: `templates/product.injection-molding-machine.json`
- Modify: `sections/maliev-pimm-50g-launch.liquid`

**Interfaces:**
- Consumes: coherent approved native PNG/EXR proofs and validated animation endpoints from Tasks 1–2.
- Produces: versioned WebP/WebM/poster files and exact Liquid/template mappings used by the redesigned pages.

- [ ] **Step 1: Write the failing storefront asset contract**

Assert exact conditions:

```js
assert.doesNotMatch(activeConsumers, /pimm50-red-stage-/);
assert.doesNotMatch(activeConsumers, /pimm50-light-studio-/);
assert.match(activeConsumers, /pimm50-cal-v2-350c-/);
assert.match(activeConsumers, /pimm30-cal-v1-/);
assert.match(section50, /350\s*(?:°C|degrees Celsius)/);
assert.doesNotMatch(section50, /300\s*(?:°C|degrees Celsius)/);
```

For every referenced asset, check file existence, expected dimensions, alpha where contracted, and paired poster/video presence.

- [ ] **Step 2: Run the contract to verify RED**

Run:

```powershell
node --test scripts/tests/pimm-storefront-assets.test.mjs
```

Expected: FAIL because active consumers still reference legacy files and the versioned files do not exist.

- [ ] **Step 3: Convert the validated native proofs**

Use the workspace image/video conversion tools to create alpha-preserving WebP stills and WebM animations. Preserve source aspect ratio; do not crop or add a matte. Create deterministic desktop/mobile filenames under the two version families.

Expected: converted dimensions and alpha channels match the manifest; representative image comparisons show no shadow cut, controller blur, engraving loss, or color shift.

- [ ] **Step 4: Update exact 50G consumers**

Replace the six `pimm50-light-studio-*` references and any comparison/poster sources with `pimm50-cal-v2-350c-*`. Update alt text and visible copy to say 350°C while leaving `2 × 350 W` intact.

- [ ] **Step 5: Update exact 30G consumers**

Replace current chapter media defaults with `pimm30-cal-v1-*`. Replace `pimm50-red-stage-*` comparison media with bright `pimm50-cal-v2-350c-*` desktop/mobile assets.

- [ ] **Step 6: Run asset and legacy-reference contracts**

Run:

```powershell
node --test scripts/tests/pimm-storefront-assets.test.mjs scripts/tests/pimm50-story-assets.test.mjs
rg -n "pimm50-red-stage-|pimm50-light-studio-" sections/maliev-pimm-30g-story.liquid sections/maliev-pimm-50g-launch.liquid templates/product.injection-molding-machine.json
rg -n "300 degrees Celsius|300°C" sections/maliev-pimm-50g-launch.liquid templates/product.pimm-50g.json
```

Expected: tests pass; search returns no obsolete active consumer and no 300°C claim in the 50G section.

- [ ] **Step 7: Commit promoted assets and mappings**

Stage only the new versioned files, the two sections, template, and asset test. Commit:

```powershell
git commit -m "Promote calibrated PIMM storefront assets"
```

---

### Task 4: Rebuild the 30G page as six normal-flow sections

**Files:**
- Create: `scripts/tests/pimm30-normal-scroll-contract.test.mjs`
- Modify: `sections/maliev-pimm-30g-story.liquid`
- Modify: `assets/maliev-pimm-30g.css`
- Modify: `templates/product.injection-molding-machine.json`
- Stop loading: `assets/maliev-pimm-30g-keynote.css`
- Stop loading: `assets/maliev-pimm-30g-no-crop.css`

**Interfaces:**
- Consumes: versioned calibrated assets and native Shopify product data from Task 3.
- Produces: six `.pimm30-section[data-pimm30-section]` roles: `hero`, `fit-output`, `controls-heating`, `direct-operation`, `mold-setup`, and `choose-buy`.

- [ ] **Step 1: Write the failing normal-scroll source contract**

Assert that the section/template expose exactly six roles and reject keynote mechanics:

```js
for (const banned of [
  /scroll-snap-(?:type|align|stop)/,
  /position\s*:\s*sticky/,
  /100(?:s|d|l)?vh/,
  /scrollIntoView\s*\(/,
  /addEventListener\s*\(\s*["'](?:wheel|touchmove)["']/,
]) assert.doesNotMatch(sourceBundle, banned);
```

Also assert one H1, one native product form, one variant selector, one factory link, and one Add to Cart action.

- [ ] **Step 2: Run the contract to verify RED**

Run:

```powershell
node --test scripts/tests/pimm30-normal-scroll-contract.test.mjs
```

Expected: FAIL because the current page has ten keynote chapters and loads keynote CSS.

- [ ] **Step 3: Replace the section structure**

Implement the six approved semantic sections in ordinary document order. Keep the hero's contained dark-startup video with bright fallback, consolidate specs/copy into the approved decision groups, and keep product form controls in the final section.

- [ ] **Step 4: Replace keynote layout CSS**

Make `.pimm30-page` a normal block flow. Use bounded `max-width`, CSS grid/flex for desktop two-column compositions, media-first or context-adjacent mobile ordering, and intrinsic section padding. Do not use sticky stages or viewport section heights.

- [ ] **Step 5: Migrate the product JSON template**

Replace ten chapter blocks with the six exact roles and corrected default copy/assets. Preserve section ID, product template association, merchant settings, and native commerce configuration.

- [ ] **Step 6: Run focused structure and schema checks**

Run:

```powershell
node --test scripts/tests/pimm30-normal-scroll-contract.test.mjs scripts/tests/pimm30-presentation-regressions.test.mjs
npm run verify
```

Expected: source contract passes; schema/Theme Check reports no new offenses.

- [ ] **Step 7: Commit the normal-scroll redesign**

```powershell
git add sections/maliev-pimm-30g-story.liquid assets/maliev-pimm-30g.css templates/product.injection-molding-machine.json scripts/tests/pimm30-normal-scroll-contract.test.mjs
git commit -m "Redesign PIMM 30G as a normal-scroll product page"
```

---

### Task 5: Add ordinary reveal motion and deterministic local QA

**Files:**
- Modify: `assets/maliev-pimm-30g.js`
- Modify: `assets/maliev-pimm-30g.css`
- Modify: `assets/maliev-pimm-50g-story.js`
- Modify: `assets/maliev-pimm-50g-story.css`
- Modify: `scripts/tests/pimm30-normal-scroll-contract.test.mjs`
- Modify: `scripts/tests/pimm50-product-page-contract.test.mjs`

**Interfaces:**
- Consumes: `[data-pimm30-motion]` / `[data-pimm50-motion]` markup.
- Produces: `is-motion-ready`, `is-motion-complete`, and local `is-debug-motion` state without changing scroll position.

- [ ] **Step 1: Write failing motion contracts**

Require:

```js
const localMotion = location.hostname === '127.0.0.1' && location.port === '9393';
const reduceMotion = !localMotion && matchMedia('(prefers-reduced-motion: reduce)').matches;
```

Reject `scroll`, `wheel`, `touchmove`, `setInterval`, `requestAnimationFrame`, `.animate(`, and `scrollIntoView`. Require one shared completion function used by both observer and fallback paths.

- [ ] **Step 2: Run focused contracts to verify RED**

Run:

```powershell
node --test scripts/tests/pimm30-normal-scroll-contract.test.mjs scripts/tests/pimm50-product-page-contract.test.mjs
```

Expected: 50G fails the local debug-motion assertion; 30G fails the new normal-flow motion contract until rewritten.

- [ ] **Step 3: Implement one-time 30G reveals**

Initialize content visibly. After JavaScript is ready, prepare only offscreen marked targets, observe with IntersectionObserver, call one completion function, unobserve, and disconnect when no targets remain. Reduced motion reveals all immediately.

- [ ] **Step 4: Add the same local-only override to 50G**

Keep its existing one-shot choreography but calculate reduced motion through the port-scoped `localMotion` exemption. Add the CSS selector needed for debug motion to override the reduced-motion suppression only on localhost port 9393.

- [ ] **Step 5: Validate authored timing and no-JS visibility**

Keep complete reveal sequences under 900 ms. Verify the DOM has no hidden content before the JavaScript readiness class and that a missing IntersectionObserver reveals all.

- [ ] **Step 6: Commit motion behavior**

```powershell
git add assets/maliev-pimm-30g.js assets/maliev-pimm-30g.css assets/maliev-pimm-50g-story.js assets/maliev-pimm-50g-story.css scripts/tests/pimm30-normal-scroll-contract.test.mjs scripts/tests/pimm50-product-page-contract.test.mjs
git commit -m "Enable normal-scroll PIMM reveals and local motion QA"
```

---

### Task 6: Browser validation and final Impeccable polish

**Files:**
- Create: `scripts/tests/pimm30-normal-scroll-browser.test.mjs`
- Modify: `sections/maliev-pimm-30g-story.liquid`
- Modify: `assets/maliev-pimm-30g.css`
- Modify: `assets/maliev-pimm-30g.js`
- Modify: `sections/maliev-pimm-50g-launch.liquid`
- Modify: `assets/maliev-pimm-50g-story.css`
- Modify: `assets/maliev-pimm-50g-story.js`

**Interfaces:**
- Consumes: live local routes on `http://127.0.0.1:9393` and existing built-in CDP harness patterns.
- Produces: viewport/motion/commerce/focus evidence and a final zero-P0/P1 Impeccable review.

- [ ] **Step 1: Write the responsive browser matrix**

Cover 1440×900, 820×1180, 390×844, and 852×393. Assert no horizontal overflow, no clipped semantic/control descendants, six 30G sections, one H1, ordinary increasing section positions, correct asset URLs, and complete purchase controls.

- [ ] **Step 2: Add motion and reduced-motion browser cases**

On port 9393 with reduced-motion emulation, assert the local debug class is present and at least one representative target transitions from prepared to complete. On a non-9393 test origin or injected production-mode predicate, assert reduced motion reveals everything immediately with no transition.

- [ ] **Step 3: Add keyboard and commerce cases**

Tab sequentially through the control before the selector, variant selector, factory visit, and Add to Cart. Assert focus visibility, serialized selected variant ID, availability agreement, enabled/disabled Add state, and 44/48 px target sizing.

- [ ] **Step 4: Run the full PIMM suite**

Run:

```powershell
node --test scripts/tests/pimm*.test.mjs
npm run verify
node .agents/skills/impeccable/scripts/detect.mjs --json sections/maliev-pimm-30g-story.liquid
node .agents/skills/impeccable/scripts/detect.mjs --json sections/maliev-pimm-50g-launch.liquid
git diff --check
```

Expected: all tests pass, Theme Check has no new offenses, both detector outputs are `[]`, and diff check is clean.

- [ ] **Step 5: Run the final Impeccable critique**

Inspect both live product routes at all four viewports with normal motion and reduced motion. Classify findings by P0/P1/P2, fix every P0/P1, rerun the relevant browser and detector gates, and repeat until no P0/P1 remains.

- [ ] **Step 6: Verify original-resolution promoted assets**

Inspect every new WebP/WebM poster over white, canvas, and checker backgrounds. Confirm 30G 300°C, 50G 350/350, silver shafts, differentiated CNC/die-cast finishes, complete physical shadows, and no alpha clipping.

- [ ] **Step 7: Commit final validation hardening**

```powershell
git add scripts/tests/pimm30-normal-scroll-browser.test.mjs sections/maliev-pimm-30g-story.liquid assets/maliev-pimm-30g.css assets/maliev-pimm-30g.js sections/maliev-pimm-50g-launch.liquid assets/maliev-pimm-50g-story.css assets/maliev-pimm-50g-story.js
git commit -m "Harden PIMM product pages across breakpoints"
```

- [ ] **Step 8: Prepare the local review handoff**

Confirm `http://127.0.0.1:9393/products/pneumatic-injection-molding-machine-50g` and the 30G product route return HTTP 200 from the current worktree. Report commits, exact test counts, known external Shopify preview warnings, and explicitly state that no push/deploy/publication occurred.
