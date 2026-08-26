# PIMM 50G Content Motion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add restrained, engineering-led, one-shot content animation to the normally scrolling PIMM 50G light-studio product page.

**Architecture:** Keep the existing Intersection Observer as the single trigger and enrich the existing `data-pimm50-motion` contract with named roles and bounded stagger indices. Liquid owns semantic motion roles, CSS owns each product-specific choreography, and JavaScript only reveals targets once and immediately resolves all targets when motion is reduced or Intersection Observer is unavailable.

**Tech Stack:** Shopify Liquid, CSS custom properties/transitions, vanilla JavaScript Intersection Observer, Node `node:test`, Chromium DevTools Protocol browser harness, Shopify Theme Check.

## Global Constraints

- Preserve normal browser scrolling; never add scroll snap, wheel interception, or viewport-locked chapters.
- Keep meaningful server-rendered content visible without JavaScript; no opacity-zero content gate.
- Animate each sequence once, without looping or blocking interaction.
- Keep total section choreography at or below 900ms and stagger windows at or below 250ms.
- Do not replace, overlay, count, or simulate controller digits in HTML.
- Do not fake 3D rotation of a flat product render.
- Preserve transparent alpha media, current asset loading, native Shopify product form behavior, Focus Yellow treatment, and zero horizontal overflow.
- `prefers-reduced-motion: reduce` must resolve every target immediately to its complete final state.
- Do not push, deploy, or add video/Blender work in this slice.

---

### Task 1: Freeze the Named Motion Contract

**Files:**
- Modify: `scripts/tests/pimm50-product-page-contract.test.mjs:176-190`
- Modify: `sections/maliev-pimm-50g-launch.liquid:46-242`

**Interfaces:**
- Consumes: existing `data-pimm50-motion` and `.is-in-view` behavior.
- Produces: named roles `hero-media`, `hero-copy`, `hero-facts`, `overview-facts`, `capacity-media`, `pneumatic-flow`, `melt-media`, `melt-proof`, `heating-media`, `heating-readouts`, `mold-media`, `mold-dimension`, `comparison-machines`, `comparison-facts`, `purchase-media`, and `purchase-panel`.

- [ ] **Step 1: Write the failing markup-contract test**

Add a test that extracts all `data-pimm50-motion="…"` values and asserts the exact required role set. Assert four hero fact children expose `style="--p50-index: 0"` through `3`, two heating readouts expose indices `0` and `1`, and both comparison machine figures expose indices `0` and `1`.

```js
test('product sections expose distinct engineering motion roles', () => {
  const required = [
    'hero-media', 'hero-copy', 'hero-facts', 'overview-facts',
    'capacity-media', 'pneumatic-flow', 'melt-media', 'melt-proof',
    'heating-media', 'heating-readouts', 'mold-media', 'mold-dimension',
    'comparison-machines', 'comparison-facts', 'purchase-media', 'purchase-panel'
  ];
  for (const role of required) assert.match(liquid, new RegExp(`data-pimm50-motion="${role}"`));
  for (let index = 0; index < 4; index += 1) assert.match(liquid, new RegExp(`pimm50-hero__fact[^>]+--p50-index: ${index}`));
});
```

- [ ] **Step 2: Run the focused contract test and verify RED**

Run: `node --test scripts/tests/pimm50-product-page-contract.test.mjs`

Expected: FAIL because the named role values and stagger indices do not yet exist.

- [ ] **Step 3: Add semantic role values and indices in Liquid**

Replace boolean motion attributes with the named values above. Add `data-pimm50-motion` to the relevant copy/fact containers, not to every section. Add inline `--p50-index` only to list items that form a legitimate bounded sequence. Do not alter text, links, form names, variant IDs, asset filenames, or section schema.

- [ ] **Step 4: Re-run the focused contract test**

Run: `node --test scripts/tests/pimm50-product-page-contract.test.mjs`

Expected: PASS for the new role test and all existing contracts.

- [ ] **Step 5: Commit the markup contract**

```powershell
git add sections/maliev-pimm-50g-launch.liquid scripts/tests/pimm50-product-page-contract.test.mjs
git commit -m "Define PIMM 50G engineering motion roles"
```

### Task 2: Implement Product-Specific CSS Choreography

**Files:**
- Modify: `scripts/tests/pimm50-product-page-contract.test.mjs:176-190`
- Modify: `assets/maliev-pimm-50g-story.css:514-640`

**Interfaces:**
- Consumes: named motion roles and `--p50-index` from Task 1; `--p50-progress` remains `0` before reveal and `1` after reveal.
- Produces: section-specific transform/clip/emphasis transitions with `--p50-delay: calc(min(var(--p50-index, 0), 5) * 45ms)`.

- [ ] **Step 1: Write failing CSS safety and choreography tests**

Add assertions for:

```js
assert.match(css, /--p50-delay:\s*calc\(min\(var\(--p50-index, 0\), 5\) \* 45ms\)/);
assert.match(css, /data-pimm50-motion="hero-copy"/);
assert.match(css, /data-pimm50-motion="pneumatic-flow"/);
assert.match(css, /data-pimm50-motion="heating-readouts"/);
assert.match(css, /data-pimm50-motion="comparison-machines"/);
assert.doesNotMatch(css, /data-pimm50-motion[^}]*opacity:\s*0(?:[;}])/s);
assert.doesNotMatch(liquid, /data-pimm50-(?:digit|display-overlay|counter)/);
```

Also assert the reduced-motion block forces progress `1`, transform `none`, clip-path `none`, animation `none`, and transition `none` for page-owned motion targets and descendants.

- [ ] **Step 2: Run the contract test and verify RED**

Run: `node --test scripts/tests/pimm50-product-page-contract.test.mjs`

Expected: FAIL on missing named-role choreography and the stronger reduced-motion final-state contract.

- [ ] **Step 3: Replace the generic settle rules with distinct sequences**

Implement:

- hero media: `translateY(2%) scale(.975)` to final placement;
- hero copy: shallow `clip-path: inset(0 0 calc((1 - var(--p50-progress)) * 12%) 0)` plus at least `.86` initial opacity;
- list rhythms: per-child transform of no more than `.7rem` and opacity of at least `.84`, with 45ms capped indices;
- airflow: existing line scale plus sequential delays on segments;
- melt proof: horizontal clip reveal and localized rule draw;
- heating readouts: two sequential border/text emphasis transitions without changing digits;
- mold dimensions: retain origin-correct line drawing and reveal semantic values after the line;
- comparison: opposing `translateX` of no more than `1.25rem`, settling to the shared baseline;
- purchase panel: short decision-order stagger while all controls stay visible and enabled.

Use `cubic-bezier(.22, 1, .36, 1)`. Keep feedback transitions between 180–250ms and entrance transitions between 520–800ms.

- [ ] **Step 4: Strengthen reduced-motion CSS**

Within `@media (prefers-reduced-motion: reduce)`, force final custom-property state and remove transition, animation, transform, filter, and clip-path effects for all page motion roles and their animated descendants. Do not use a global `*` selector outside `.pimm50-page`.

- [ ] **Step 5: Run the focused contract test**

Run: `node --test scripts/tests/pimm50-product-page-contract.test.mjs`

Expected: PASS.

- [ ] **Step 6: Commit the choreography**

```powershell
git add assets/maliev-pimm-50g-story.css scripts/tests/pimm50-product-page-contract.test.mjs
git commit -m "Animate PIMM 50G engineering content"
```

### Task 3: Harden One-Shot Reveal Behavior

**Files:**
- Modify: `scripts/tests/pimm50-product-page-contract.test.mjs:176-190`
- Modify: `assets/maliev-pimm-50g-story.js:1-83`

**Interfaces:**
- Consumes: every element matching `[data-pimm50-motion]`.
- Produces: `revealMotionTarget(element)` which adds `is-in-view` and `data-pimm50-motion-state="complete"`; observed targets are unobserved after their first intersection.

- [ ] **Step 1: Write the failing JavaScript contract test**

Assert the script defines and uses a single reveal helper, records a complete state, unobserves intersected elements, retains Intersection Observer, and contains no `scroll`, `wheel`, `requestAnimationFrame`, Web Animations API, or timer-driven looping.

```js
assert.match(js, /const revealMotionTarget = \(element\) => \{/);
assert.match(js, /element\.dataset\.pimm50MotionState = 'complete'/);
assert.match(js, /activeObserver\.unobserve\(entry\.target\)/);
assert.doesNotMatch(js, /setInterval|requestAnimationFrame|\.animate\(/);
```

- [ ] **Step 2: Run the focused contract test and verify RED**

Run: `node --test scripts/tests/pimm50-product-page-contract.test.mjs`

Expected: FAIL because the complete-state helper is absent.

- [ ] **Step 3: Implement the one-shot reveal helper**

Refactor `revealAll` and the observer callback to call `revealMotionTarget`. Preserve the existing `data-ready` guard, commerce behavior, threshold `.12`, root margin, Shopify section reload support, reduced-motion fallback, and no-Intersection-Observer fallback.

- [ ] **Step 4: Run focused tests**

Run: `node --test scripts/tests/pimm50-product-page-contract.test.mjs`

Expected: PASS.

- [ ] **Step 5: Commit the behavior contract**

```powershell
git add assets/maliev-pimm-50g-story.js scripts/tests/pimm50-product-page-contract.test.mjs
git commit -m "Harden PIMM 50G one-shot motion"
```

### Task 4: Prove Motion and Reduced-Motion in Chromium

**Files:**
- Modify: `scripts/tests/pimm50-responsive-browser.test.mjs:895-920`

**Interfaces:**
- Consumes: named roles, `data-pimm50-motion-state="complete"`, and computed styles from Tasks 1–3.
- Produces: browser evidence that targets complete once, remain visible, preserve geometry, and resolve immediately under reduced motion.

- [ ] **Step 1: Add a failing browser test for real motion completion**

At `1440x900`, navigate to the product route with no-preference motion, collect the hero media transform and hero-copy clip-path before completion, then wait until their motion state is complete and assert final transform/clip-path. Scroll the pneumatic, heating, mold, comparison, and purchase targets into view and assert every named role reports complete exactly once.

The test must also assert every meaningful target has computed opacity `>= .82` before completion and no target has `pointer-events: none`.

- [ ] **Step 2: Run only the new browser test and verify RED**

Run: `node --test --test-name-pattern="content motion" scripts/tests/pimm50-responsive-browser.test.mjs`

Expected: FAIL because named complete states and distinct initial/final computed styles are not yet proven by the harness.

- [ ] **Step 3: Complete the browser assertions**

Use the harness's existing CDP navigation, evaluation, wait, and media-emulation helpers. Do not add a browser dependency. Disable cache before navigation so the latest Shopify preview assets are measured.

- [ ] **Step 4: Extend the reduced-motion test**

Assert all named roles have progress `1`, motion state complete, transform `none`, no running animation, transition duration effectively zero, visible geometry, and unoccluded authoritative posters.

- [ ] **Step 5: Run the responsive browser suite**

Run: `node --no-experimental-websocket --test scripts/tests/pimm50-responsive-browser.test.mjs`

Expected: all browser subtests PASS, including all 11 viewport geometry rows, keyboard focus, commerce alignment, content motion, and reduced motion.

- [ ] **Step 6: Commit browser evidence**

```powershell
git add scripts/tests/pimm50-responsive-browser.test.mjs
git commit -m "Verify PIMM 50G motion across breakpoints"
```

### Task 5: Final Impeccable Polish and Repository Gates

**Files:**
- Inspect: `sections/maliev-pimm-50g-launch.liquid`
- Inspect: `assets/maliev-pimm-50g-story.css`
- Inspect: `assets/maliev-pimm-50g-story.js`
- Inspect: `scripts/tests/pimm50-product-page-contract.test.mjs`
- Inspect: `scripts/tests/pimm50-responsive-browser.test.mjs`

**Interfaces:**
- Consumes: the complete motion implementation.
- Produces: release evidence with no P0/P1 Impeccable findings.

- [ ] **Step 1: Run the complete PIMM 50G suite**

Run: `node --test scripts/tests/pimm50-*.test.mjs`

Expected: all tests PASS with no unhandled test-process errors.

- [ ] **Step 2: Run theme and static validation**

Run:

```powershell
npm run verify
node .agents/skills/impeccable/scripts/detect.mjs --json sections/maliev-pimm-50g-launch.liquid
git diff --check
```

Expected: Theme Check reports 190 files and zero offenses; detector returns `[]`; diff check is clean.

- [ ] **Step 3: Visually inspect representative states**

Inspect hero, pneumatic flow, heating readouts, mold dimensions, comparison, and purchase at `1440x900`, `820x1180`, `390x844`, and `852x393`. Verify alpha edges and shadows remain intact, copy is readable during and after motion, controls never move out of reach, and normal wheel scrolling remains proportional.

- [ ] **Step 4: Run Impeccable critique and polish**

Evaluate hierarchy, animation purpose, duration, fatigue, focus, reduced motion, performance, and AI-slop. Resolve every P0/P1 issue and rerun affected gates. Record any accepted P2 issue with concrete evidence.

- [ ] **Step 5: Commit only if final polish changes production files**

```powershell
git add sections/maliev-pimm-50g-launch.liquid assets/maliev-pimm-50g-story.css assets/maliev-pimm-50g-story.js scripts/tests/pimm50-product-page-contract.test.mjs scripts/tests/pimm50-responsive-browser.test.mjs
git commit -m "Polish PIMM 50G content motion"
```

Do not create an empty commit. Do not stage unrelated untracked files. Do not push or deploy.
