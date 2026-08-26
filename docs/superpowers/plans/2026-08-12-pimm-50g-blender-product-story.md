# PIMM 50G Blender Product Story Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the PIMM 50G page's AI imagery with a faithful Blender-rendered, responsive keynote product story while preserving Shopify commerce behavior.

**Architecture:** An idempotent Blender builder copies the corrected immutable 50G master into a dedicated multi-scene product-story project and emits desktop/mobile stills plus rotation frames. A focused Shopify section consumes only those validated assets and keeps price, variants, booking, and cart controls in HTML. Node contract tests and browser geometry tests guard asset ownership, responsive one-viewport chapters, interaction, and accessibility.

**Tech Stack:** Blender 5.2 Python API, Cycles/EEVEE proof rendering, Shopify Liquid/CSS/JavaScript, Node test runner, Shopify Theme Check, browser viewport automation.

## Global Constraints

- Never save over `PIMM-50g-keynote-reveal-v2-regulator-materials.blend` or the open PIMM 30G project.
- Preserve the `Machine_50g` 481-object contract, materials, controller faces, regulator, hoses, and vendor decals.
- Use `PIMM50_STORY_` ownership for generated Blender data and separate desktop/mobile cameras.
- Complete-machine shots use containment with at least 15% breathing room; detail shots crop only around the named component.
- Keep Shopify price, availability, variants, lead time, booking, and cart behavior as live HTML.
- Each mobile/tablet chapter fits one effective viewport and advances with one deliberate gesture.
- Support WCAG 2.2 AA, 44px controls, keyboard focus, touch rotation, and `prefers-reduced-motion`.
- Do not deploy. Do not push implementation commits without separate authorization.

---

### Task 1: Blender Product-Story Contract

**Files:**
- Create: `scripts/tests/pimm50-product-story.test.mjs`
- Create: `scripts/blender/create_pimm50_product_story.py`

**Interfaces:**
- Consumes: corrected master blend and `Machine_50g` collection.
- Produces: `PIMM-50g-product-story-v1.blend`, JSON build summary, desktop/mobile PNG proofs, and rotation frames.

- [ ] Write a failing Node source-contract test for immutable paths, 481 objects, owned scene names, portrait/desktop cameras, transparent RGBA, render outputs, and no source overwrite.
- [ ] Run `node --test scripts/tests/pimm50-product-story.test.mjs` and confirm failure because the builder is absent.
- [ ] Implement the idempotent Blender builder with explicit geometry/material assertions, camera specs, bright studio lighting, shadow catcher, overview/detail/comparison/purchase scenes, and summary output.
- [ ] Run `python -m py_compile scripts/blender/create_pimm50_product_story.py` and the Node contract test.
- [ ] Run Blender headlessly from the corrected source to create the dedicated target and proof renders; verify the source hash and timestamp are unchanged.
- [ ] Inspect desktop/mobile overview and representative detail proofs visually; correct framing or lighting before promotion.
- [ ] Commit the validated builder and contract test.

### Task 2: Promote Validated Blender Assets

**Files:**
- Create: `assets/pimm50-story-*.webp`
- Create: `assets/pimm50-story-rotate-*.webp`
- Create: `scripts/tests/pimm50-story-assets.test.mjs`

**Interfaces:**
- Consumes: Task 1 PNG proofs and rotation frames.
- Produces: optimized theme assets with alpha, fixed dimensions, and manifest-like filename contract.

- [ ] Write a failing test for required desktop/mobile assets, dimensions, alpha, size ceilings, and frame sequence completeness.
- [ ] Convert approved Blender PNGs to WebP without flattening alpha.
- [ ] Run the asset test and inspect alpha bounds to prove complete-machine shadows remain inside the canvas.
- [ ] Commit only validated render assets and asset tests.

### Task 3: Keynote Storefront Structure

**Files:**
- Modify: `sections/maliev-pimm-50g-launch.liquid`
- Create: `assets/maliev-pimm-50g-story.css`
- Create: `assets/maliev-pimm-50g-story.js`
- Create: `scripts/tests/pimm50-keynote-contract.test.mjs`

**Interfaces:**
- Consumes: Task 2 asset names and Shopify `product`/variant data.
- Produces: semantic eight-chapter presentation, localized copy, live purchase controls, and JS hooks under `[data-pimm50-story]`.

- [ ] Write a failing contract test for eight chapter IDs, `<picture>` desktop/mobile sources, no AI asset references, semantic headings, live money/variant form, booking CTA, reduced-motion hooks, and external CSS/JS assets.
- [ ] Replace the monolithic AI-backed section with the approved narrative: reveal, overview, capacity, melt zone, heating, mold space, comparison, purchase.
- [ ] Keep the section schema valid and merchant-editable while binding prices and variants to Shopify.
- [ ] Implement the bright/dark chapter styling, one-viewport responsive layouts, contained complete-machine media, intentional detail framing, focus states, and short-landscape rules.
- [ ] Implement scroll chapter activation, finite reveal, reduced-motion fallback, and rotation intro that yields immediately to pointer/touch drag.
- [ ] Run focused Node tests and `npm run verify`.
- [ ] Commit the storefront structure only after focused checks pass.

### Task 4: Responsive and Commerce Browser Verification

**Files:**
- Create: `scripts/tests/pimm50-responsive-browser.test.mjs`
- Modify: storefront files from Task 3 only when tests expose defects.

**Interfaces:**
- Consumes: live local product route and Task 3 DOM hooks.
- Produces: repeatable geometry, scroll, touch, commerce, and accessibility assertions.

- [ ] Add assertions for chapter viewport height, one-gesture chapter advancement, no horizontal overflow, no text/media overlap, complete-media containment, 44px controls, CTA visibility, and drag rotation.
- [ ] Cover 3840×2160, 1440×900, 1024×768, 820×1180, 768×1024, 720×540, 540×720, 430×932, 412×915, 393×852, 384×824, 852×393, and 824×384.
- [ ] Verify the live price/variant form, booking CTA, add-to-cart form wiring, keyboard focus, and reduced-motion state.
- [ ] Fix every deterministic failure and rerun focused tests, browser matrix, and `npm run verify`.
- [ ] Commit the responsive/browser regression gate with fixes.

### Task 5: Impeccable Critique and Final Verification

**Files:**
- Modify: only files implicated by confirmed critique findings.
- Create: `.impeccable/critique/<timestamp>__sections-maliev-pimm-50g-launch-liquid.md` through the Impeccable critique workflow.

**Interfaces:**
- Consumes: validated live page and project design context.
- Produces: scored critique, resolved P0/P1/P2 findings, final screenshots, and verification evidence.

- [ ] Run `$impeccable critique sections/maliev-pimm-50g-launch.liquid` using the live route, brand register, Jordan/Riley/Casey personas, and Thai workshop-buyer context.
- [ ] Triage every finding against the approved spec; fix all confirmed P0/P1 and all in-scope P2 findings.
- [ ] Rerun the critique and require no unresolved P0/P1; document any rejected finding with evidence.
- [ ] Run `git diff --check`, all focused Node tests, Python compile, Blender contract validation, `npm run verify`, and the complete browser matrix.
- [ ] Inspect final desktop, portrait-tablet, phone, and short-landscape screenshots.
- [ ] Commit the final polish only when every applicable check passes; leave deployment and push untouched.
