# PIMM Unified Product Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one responsive Shopify product presentation whose 30G/50G Model selector updates authoritative commerce state, photoreal media and one contained engineering bento section.

**Architecture:** Add a dedicated Online Store 2.0 template and a focused machine-product section rather than extending either legacy PIMM monolith. Liquid renders truthful initial variant state and an exact JSON payload; a small custom element progressively updates text, media, URL and the native product form. The page remains an open editorial product presentation with one asymmetric engineering bento cluster.

**Tech Stack:** Shopify Liquid/JSON templates, vanilla JavaScript custom elements, CSS, Shopify `product-form.js`, Node.js 20 built-in test runner, existing Chrome/CDP responsive browser harness, Theme Check.

**Spec:** `docs/superpowers/specs/2026-08-26-pimm-unified-product-configurator-design.md`

## Global Constraints

- Product option must equal `Model`; supported values are exactly `30G` and `50G`.
- Factory visit is the first/primary action; 50% deposit is secondary.
- Shopify variant state owns deposit price, availability and submitted variant ID.
- The full-machine-price metafield remains base Admin-currency qualification evidence; storefront full-price presentment is exactly twice contextual `variant.price`. Variant metafields also own lead time and versioned specifications.
- Missing/malformed model data disables the deposit action and preserves factory contact.
- The page has exactly one bento section; hero, narrative, ownership and purchase sections remain open compositions.
- Use MALIEV Surface/Canvas/Ink/Signal Blue tokens, 10px maximum tile corners, no decorative card shadows, glass, gradient text or repeated eyebrows.
- Content is visible before JavaScript; reduced motion preserves complete states.
- English and Thai require full content parity.
- No production deployment, Draft-product publication or retirement of existing product routes.

---

### Task 1: Create the semantic template and page skeleton

**Files:**
- Create: `templates/product.pimm-configurator.json`
- Create: `sections/maliev-pimm-machine-product.liquid`
- Create: `snippets/pimm-model-selector.liquid`
- Create: `snippets/pimm-engineering-bento.liquid`
- Create: `snippets/pimm-purchase-qualification.liquid`
- Create: `snippets/pimm-ownership.liquid`
- Create: `scripts/tests/pimm-unified-product-page-contract.test.mjs`

**Interfaces:**
- Consumes: Shopify `product`, `product.selected_or_first_available_variant`, section settings and model blocks.
- Produces: semantic `[data-pimm-machine-product]` root, one H1, `fieldset` Model selector, native product form, exactly one `[data-pimm-engineering-bento]`, narrative/ownership/purchase landmarks and valid section schema.

- [ ] **Step 1: Write the failing structural contract**

```javascript
const section = await readFile(new URL('../../sections/maliev-pimm-machine-product.liquid', import.meta.url), 'utf8');
const template = JSON.parse(stripShopifyComment(await readFile(new URL('../../templates/product.pimm-configurator.json', import.meta.url), 'utf8')));

test('unified template owns one semantic machine presentation', () => {
  assert.equal(template.sections.main.type, 'maliev-pimm-machine-product');
  assert.deepEqual(template.order, ['main']);
  assert.equal(section.match(/<h1\b/g)?.length, 1);
  assert.match(section, /data-pimm-machine-product/);
  assert.match(section, /<fieldset[^>]*data-pimm-model-selector/);
  assert.match(section, /<legend/);
  assert.equal(section.match(/data-pimm-engineering-bento/g)?.length, 1);
  assert.match(section, /\{%[-]?\s*form 'product'/);
  assert.match(section, /name="id"/);
  assert.match(section, /<product-form/);
  assert.match(section, /product-form__error-message-wrapper/);
  assert.match(section, /\{%[-]?\s*when '@app'/);
  assert.ok(section.indexOf('data-pimm-book-visit') < section.indexOf('data-pimm-deposit-action'));
});
```

- [ ] **Step 2: Run the focused test and confirm files are absent**

Run: `node --test scripts/tests/pimm-unified-product-page-contract.test.mjs`

Expected: FAIL on missing section/template.

- [ ] **Step 3: Create the exact section order**

```liquid
<pimm-machine-product class="pimm-machine" data-pimm-machine-product data-section-id="{{ section.id }}">
  <section class="pimm-machine__hero" aria-labelledby="PimmMachineTitle-{{ section.id }}">
    <h1 id="PimmMachineTitle-{{ section.id }}">{{ 'products.pimm_machine.title' | t }}</h1>
    {% render 'pimm-model-selector', product: product, selected_variant: selected_variant, section: section %}
  </section>
  <section class="pimm-machine__fit" aria-labelledby="PimmMachineFit-{{ section.id }}">
    <h2 id="PimmMachineFit-{{ section.id }}">{{ 'products.pimm_machine.fit.title' | t }}</h2>
    <p>{{ 'products.pimm_machine.fit.body' | t }}</p>
  </section>
  {% render 'pimm-engineering-bento', product: product, selected_variant: selected_variant, section: section %}
  <section class="pimm-machine__tooling" aria-labelledby="PimmMachineTooling-{{ section.id }}">
    <h2 id="PimmMachineTooling-{{ section.id }}">{{ 'products.pimm_machine.tooling.title' | t }}</h2>
    <p>{{ 'products.pimm_machine.tooling.body' | t }}</p>
  </section>
  {% render 'pimm-ownership', section: section %}
  {% render 'pimm-purchase-qualification', product: product, selected_variant: selected_variant, section: section %}
</pimm-machine-product>
```

The hero contains one H1, selected front render, model selector, full-price/deposit/availability/lead-time summary and actions. The fit and tooling sections use figures plus copy, not cards.

- [ ] **Step 4: Add an exact two-block model schema**

Each `model` block has `model_code`, `hero_asset`, `overview_asset`, `engineering_asset`, `tooling_asset` and English/Thai alt text. Template defaults create exactly one 30G and one 50G block with the eight filenames from the render-assets plan. Section settings include only factory-visit URL and document/support links.

Allow `@app` blocks and render them in one bounded integration area after purchase qualification so installed product apps retain Shopify-native behavior without entering the engineering bento.

- [ ] **Step 5: Add fail-closed Liquid selection**

Map the selected variant's first option to the matching block. If the block or specification metafield is absent, set `model_contract_valid = false`, render an unavailable-data message, preserve factory visit and disable the deposit button.

- [ ] **Step 6: Run structural and schema checks**

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
npm run verify
```

Expected: contract PASS and Theme Check zero errors.

- [ ] **Step 7: Commit the semantic skeleton**

```powershell
git add -- templates/product.pimm-configurator.json sections/maliev-pimm-machine-product.liquid snippets/pimm-model-selector.liquid snippets/pimm-engineering-bento.liquid snippets/pimm-purchase-qualification.liquid snippets/pimm-ownership.liquid scripts/tests/pimm-unified-product-page-contract.test.mjs
git commit -m "Build unified PIMM product structure"
```

### Task 2: Implement exact variant-state serialization and model switching

**Files:**
- Create: `assets/maliev-pimm-machine.js`
- Modify: `sections/maliev-pimm-machine-product.liquid`
- Modify: `snippets/pimm-model-selector.liquid`
- Modify: `snippets/pimm-purchase-qualification.liquid`
- Modify: `scripts/tests/pimm-unified-product-page-contract.test.mjs`

**Interfaces:**
- Consumes: `<script type="application/json" data-pimm-variant-data>` containing `id`, `model`, formatted deposit/full price, availability, lead time, validated specifications and model media.
- Produces: `PimmMachineProduct` custom element with `selectVariant(variantId)`; exact `name="id"` radio submission; safe text/media/URL state updates.

Each serialized record has this exact JavaScript shape:

```javascript
{
  id: 123,
  model: '30G',
  depositPrice: 'THB 49,500.00',
  fullPrice: 'market-aware formatted value equal to contextual depositPrice × 2',
  available: true,
  leadTime: '30-day production lead time',
  specifications: {
    schema_version: 1,
    model: '30G',
    shot_capacity_g: 30,
    max_melt_temperature_c: 300,
    mold_envelope_mm: { width: 1, height: 1, depth: 1 },
    max_air_pressure_mpa: 0.7,
  },
  media: { hero: '', overview: '', engineering: '', tooling: '' },
  statusText: 'Made to order',
  contractValid: true,
}
```

The prices and dimensions above are serialization examples for interface shape only; Liquid replaces every value from the current Shopify variant/metafields and the matched model block.

- [ ] **Step 1: Write failing variant contract tests**

```javascript
test('model radios submit real variant IDs and payload is sanitized', () => {
  assert.match(section, /type="radio"[^>]*name="id"[^>]*value="\{\{ variant\.id \}\}"/);
  assert.match(section, /variant\.option1 \| strip_html \| json/);
  assert.match(section, /variant\.price \| money_with_currency \| strip_html \| json/);
  assert.match(section, /variant\.metafields\.custom\.pimm_specifications\.value \| json/);
  assert.match(section, /role="status"[^>]*aria-live="polite"[^>]*aria-atomic="true"/);
  assert.doesNotMatch(js, /innerHTML|insertAdjacentHTML|document\.write/);
});
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `node --test scripts/tests/pimm-unified-product-page-contract.test.mjs`

Expected: FAIL because the payload/controller is absent.

- [ ] **Step 3: Render truthful native radio inputs**

```liquid
<fieldset data-pimm-model-selector>
  <legend>{{ 'products.pimm_machine.model_legend' | t }}</legend>
  {% for variant in product.variants %}
    {% if variant.option1 == '30G' or variant.option1 == '50G' %}
      <label>
        <input type="radio" name="id" value="{{ variant.id }}" data-pimm-model-radio{% if variant.id == selected_variant.id %} checked{% endif %}>
        <span>{{ variant.option1 | escape }}</span>
      </label>
    {% endif %}
  {% endfor %}
</fieldset>
```

The radios live inside the canonical product form. Without JavaScript, submitting posts the checked variant ID.

Wrap the form in the existing `<product-form>` custom element, include `product-form.js`, the loading spinner and `product-form__error-message-wrapper`. Cart failure must preserve the selected radio, surface the associated Shopify error and leave Book a factory visit operable.

- [ ] **Step 4: Serialize exact variant JSON**

Each record must contain only JSON-safe values produced by Liquid filters. Reject records unless option1 is exact, specification schema/model match, dimensions are positive, the corresponding model block exists and its hero is present. Missing non-hero media resolves to that same model's hero source, hero alt and hero intrinsic dimensions without invalidating commerce; a missing hero remains invalid. Include `contractValid` rather than repairing any other invalid data.

- [ ] **Step 5: Implement the custom element**

```javascript
class PimmMachineProduct extends HTMLElement {
  connectedCallback() {
    this.variants = JSON.parse(this.querySelector('[data-pimm-variant-data]').textContent);
    this.addEventListener('change', (event) => {
      if (event.target.matches('[data-pimm-model-radio]')) this.selectVariant(Number(event.target.value));
    });
  }

  selectVariant(variantId) {
    const variant = this.variants.find((item) => item.id === variantId);
    if (!variant) return;
    this.querySelectorAll('[data-pimm-model-value]').forEach((node) => {
      node.textContent = String(variant[node.dataset.pimmModelValue] ?? '');
    });
    this.querySelector('[data-pimm-selected-model]').textContent = variant.model;
    const button = this.querySelector('[data-pimm-deposit-action]');
    button.disabled = !variant.available || !variant.contractValid;
    this.querySelector('[data-pimm-variant-status]').textContent = variant.statusText;
    const url = new URL(window.location.href);
    url.searchParams.set('variant', String(variant.id));
    history.replaceState({}, '', url);
    this.applyMedia(variant.model);
  }
}

customElements.define('pimm-machine-product', PimmMachineProduct);
```

Use `textContent`, property assignments and existing nodes only. Do not recreate controls or HTML from JSON.

- [ ] **Step 6: Add unavailable and invalid-contract tests**

Assert that unavailable variants and malformed specification payloads disable deposit, preserve Book a factory visit, show explicit localized status and never fall back to the other model.

- [ ] **Step 7: Run focused tests and commit**

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
git add -- assets/maliev-pimm-machine.js sections/maliev-pimm-machine-product.liquid snippets/pimm-model-selector.liquid snippets/pimm-purchase-qualification.liquid scripts/tests/pimm-unified-product-page-contract.test.mjs
git commit -m "Switch unified PIMM model state safely"
```

### Task 3: Build the contained engineering bento and media system

**Files:**
- Modify: `snippets/pimm-engineering-bento.liquid`
- Modify: `sections/maliev-pimm-machine-product.liquid`
- Modify: `assets/maliev-pimm-machine.js`
- Modify: `scripts/tests/pimm-unified-product-page-contract.test.mjs`

**Interfaces:**
- Consumes: selected model and validated specification/media record from Task 2.
- Produces: exactly one `[data-pimm-engineering-bento]`, model-keyed `<picture>` groups and semantic capacity/temperature/mold/pressure readouts.

- [ ] **Step 1: Write the failing bento/media contract**

```javascript
test('one asymmetric engineering bento swaps complete model evidence', () => {
  assert.equal(section.match(/data-pimm-engineering-bento/g)?.length, 1);
  for (const model of ['30G', '50G']) assert.match(section, new RegExp(`data-pimm-media-model="${model}"`));
  for (const field of ['shot_capacity_g', 'max_melt_temperature_c', 'mold_envelope', 'max_air_pressure_mpa']) {
    assert.match(section, new RegExp(`data-pimm-spec="${field}"`));
  }
  assert.doesNotMatch(section, /data-pimm-engineering-bento[\s\S]*data-pimm-engineering-bento/);
});
```

- [ ] **Step 2: Run the test and confirm failure**

Run: `node --test scripts/tests/pimm-unified-product-page-contract.test.mjs`

Expected: FAIL on missing model media/spec hooks.

- [ ] **Step 3: Render all model media as stable existing nodes**

Use explicit width/height and model-specific alt text. The initially selected model is visible server-side; alternate-model figures are `hidden`. The initial hero is eager with `fetchpriority="high"`; all below-fold imagery is `loading="lazy"` and `decoding="async"`.

- [ ] **Step 4: Render semantic bento facts**

Use one dominant `<figure>` and one `<dl>`. Format the mold envelope from exact width, height and depth. Add units in visible text and accessible labels; do not store units in numeric JSON fields.

- [ ] **Step 5: Implement media/spec state changes**

`applyMedia(model)` updates only safe properties on existing model groups, updates specification text and runs one opacity crossfade of at most 180ms. The outgoing model becomes `aria-hidden` and pointer-inert immediately, remains in the same grid cell only until bounded cleanup, and rapid switches cancel stale cleanup so only the latest model remains. Reduced motion uses an instant hidden-state swap. On first direct 30G/50G intent, call `image.decode()` for the selected hero; do not preload all below-fold images.

- [ ] **Step 6: Run focused tests and commit**

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
git add -- snippets/pimm-engineering-bento.liquid sections/maliev-pimm-machine-product.liquid assets/maliev-pimm-machine.js scripts/tests/pimm-unified-product-page-contract.test.mjs
git commit -m "Present PIMM engineering at a glance"
```

### Task 4: Apply the MALIEV responsive visual system and localization

**Files:**
- Create: `assets/maliev-pimm-machine.css`
- Modify: `sections/maliev-pimm-machine-product.liquid`
- Modify: `snippets/pimm-model-selector.liquid`
- Modify: `snippets/pimm-engineering-bento.liquid`
- Modify: `snippets/pimm-purchase-qualification.liquid`
- Modify: `snippets/pimm-ownership.liquid`
- Modify: `locales/en.default.json`
- Modify: `locales/th.json`
- Modify: `scripts/tests/pimm-unified-product-page-contract.test.mjs`

**Interfaces:**
- Consumes: semantic structure from Tasks 1–3 and existing MALIEV tokens/fonts.
- Produces: conventional product hero, open narrative sections, one responsive asymmetric bento, visible focus and complete English/Thai content.

- [ ] **Step 1: Write failing design-system tests**

Assert:

```javascript
assert.match(css, /\.pimm-machine__hero\s*\{[^}]*display:\s*grid/s);
assert.match(css, /\.pimm-engineering-bento\s*\{[^}]*display:\s*grid/s);
assert.doesNotMatch(css, /border-radius:\s*(?:[2-9]\d|1[1-9])px/);
assert.doesNotMatch(css, /box-shadow:\s*0\s+\d+px\s+(?:1[6-9]|[2-9]\d)px/);
assert.doesNotMatch(css, /background-clip:\s*text|backdrop-filter|repeating-linear-gradient/);
assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);
```

- [ ] **Step 2: Run the test and confirm CSS/locales are absent**

Run: `node --test scripts/tests/pimm-unified-product-page-contract.test.mjs`

Expected: FAIL.

- [ ] **Step 3: Implement desktop composition**

Use a 1440px maximum content width, 48px desktop gutter, Surface/Canvas fields and Ink/Signal Blue actions. Hero is a two-column grid; narrative alternates open image/copy relationships; bento uses a dominant image spanning two rows plus four compact facts. Static sections have no shadow.

- [ ] **Step 4: Implement mobile/tablet composition**

At tablet collapse the hero without cropping the full machine. At mobile use 20px gutter; media precedes associated copy; bento facts form a two-column grid and become one column only when 320px content width requires it. Guarantee zero horizontal overflow from 320px upward.

- [ ] **Step 5: Implement interaction states**

Controls use 4px corners and at least 44px practical touch height. Focus uses 3px `#FFD21C` plus a contrasting Ink indicator. Model media uses a maximum 180ms opacity transition; reduced motion sets duration to zero and removes transforms.

- [ ] **Step 6: Add exact English and Thai locale keys**

Add all headings, model labels, units, status/error messages, factory-visit/deposit explanation, ownership/support copy and alt text beneath `products.pimm_machine`. No user-facing English/Thai conditional prose remains hardcoded in Liquid.

- [ ] **Step 7: Run focused tests, JSON parsing and Theme Check**

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
node -e "JSON.parse(require('fs').readFileSync('locales/en.default.json','utf8')); JSON.parse(require('fs').readFileSync('locales/th.json','utf8'))"
npm run verify
```

Expected: all PASS, Theme Check zero errors.

- [ ] **Step 8: Commit visual/localization slice**

```powershell
git add -- assets/maliev-pimm-machine.css sections/maliev-pimm-machine-product.liquid snippets/pimm-model-selector.liquid snippets/pimm-engineering-bento.liquid snippets/pimm-purchase-qualification.liquid snippets/pimm-ownership.liquid locales/en.default.json locales/th.json scripts/tests/pimm-unified-product-page-contract.test.mjs
git commit -m "Style and localize unified PIMM product page"
```

### Task 5: Validate the Draft-product preview in real browsers

**Files:**
- Create: `scripts/tests/pimm-unified-responsive-browser.test.mjs`
- Create locally, never commit: `.codex-tmp/pimm-unified-product/browser-evidence/`

**Interfaces:**
- Consumes: Draft product from the draft-product plan, development theme URL and completed theme assets.
- Produces: desktop/mobile English/Thai screenshots plus runtime assertions for both model variants.

- [ ] **Step 1: Write the failing browser acceptance test**

Copy the existing `launchBrowser()`, `waitForPage()`, `setViewport()`, `evaluate()`, `eventually()` and cleanup helpers from `scripts/tests/pimm50-responsive-browser.test.mjs` into the new standalone harness. For each viewport `1440x1000`, `1024x768`, `768x1024`, `390x844` and `320x800`, evaluate this browser-side probe:

```javascript
const probe = await evaluate(session, `(() => ({
  bentoCount: document.querySelectorAll('[data-pimm-engineering-bento]').length,
  h1Count: document.querySelectorAll('h1').length,
  noOverflow: document.documentElement.scrollWidth <= innerWidth,
  primaryBeforeDeposit:
    document.querySelector('[data-pimm-book-visit]').compareDocumentPosition(
      document.querySelector('[data-pimm-deposit-action]')
    ) & Node.DOCUMENT_POSITION_FOLLOWING,
}))()`);
assert.equal(probe.bentoCount, 1);
assert.equal(probe.h1Count, 1);
assert.equal(probe.noOverflow, true);
assert.ok(probe.primaryBeforeDeposit);
```

Then switch each model through the real radio and read back state with the existing `evaluate()` helper:

```javascript
for (const model of ['30G', '50G']) {
  const state = await evaluate(session, `(async () => {
    const radio = document.querySelector('[data-pimm-model-radio][data-model="${model}"]');
    radio.click();
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    return {
      checked: radio.checked,
      selected: document.querySelector('[data-pimm-selected-model]').textContent.trim(),
      url: location.href,
      visibleMedia: document.querySelectorAll('[data-pimm-media-model="${model}"]:not([hidden])').length,
      depositDisabled: document.querySelector('[data-pimm-deposit-action]').disabled,
    };
  })()`);
  assert.equal(state.checked, true);
  assert.equal(state.selected, model);
  assert.match(state.url, /variant=\d+/);
  assert.ok(state.visibleMedia > 0);
}
```

Also assert primary factory-visit order, keyboard focus, live-region updates, correct enabled/disabled deposit state, no console errors and reduced-motion completion.

- [ ] **Step 2: Run the test without a preview and confirm fail-closed behavior**

Run: `node --test scripts/tests/pimm-unified-responsive-browser.test.mjs`

Expected: SKIP only when `PIMM_UNIFIED_PREVIEW_URL` is absent; with an invalid URL, FAIL with the exact connection error.

- [ ] **Step 3: Start the development theme**

```powershell
shopify theme dev --store 10b918-e4.myshopify.com --host 127.0.0.1 --port 9393
```

Use the Draft product's Admin Preview route with the development theme and `view=pimm-configurator`. Save the exact authenticated preview URL to ignored file `.codex-tmp/pimm-unified-product/preview-url.txt`. Do not assign or publish the template on the live theme.

- [ ] **Step 4: Run English and Thai browser matrices**

```powershell
$env:PIMM_UNIFIED_PREVIEW_URL=(Get-Content -LiteralPath '.codex-tmp\pimm-unified-product\preview-url.txt' -Raw).Trim()
node --test scripts/tests/pimm-unified-responsive-browser.test.mjs
```

The environment value is runtime evidence, not committed configuration. Expected: all viewport/model assertions PASS. Save screenshots to the ignored evidence directory.

- [ ] **Step 5: Test failure states**

Use local fixture interception to test unavailable 50G, malformed specifications and missing engineering image. Unavailability and malformed specifications fail closed: Book a factory visit remains available, deposit disables, the other model's facts/media never appear and the live region explains the selected model's problem. Missing engineering media instead falls back to the same selected model hero source and hero alt while commerce remains valid; it never borrows the other model.

- [ ] **Step 6: Commit the browser harness**

```powershell
git add -- scripts/tests/pimm-unified-responsive-browser.test.mjs
git commit -m "Verify unified PIMM page responsively"
```

### Task 6: Run the full affected gate and prepare local handoff

**Files:**
- Modify only if validation finds an in-scope defect: files created in Tasks 1–5.
- Preserve: legacy 30G/50G templates and assets until a separately approved production migration.

**Interfaces:**
- Consumes: all theme slices, eight approved render assets and Draft product preview.
- Produces: clean, locally validated feature branch; no push/deploy/publication.

- [ ] **Step 1: Run focused Node contracts**

```powershell
node --test scripts/tests/pimm-unified-product-contract.test.mjs scripts/tests/pimm-unified-render-assets.test.mjs scripts/tests/pimm-unified-product-page-contract.test.mjs scripts/tests/pimm-unified-responsive-browser.test.mjs
```

Expected: all applicable tests PASS with counts reported; browser test may skip only when no preview URL is intentionally supplied, not during final browser validation.

- [ ] **Step 2: Run legacy PIMM regressions**

```powershell
node --test scripts/tests/pimm30-presentation-regressions.test.mjs scripts/tests/pimm50-product-page-contract.test.mjs scripts/tests/pimm50-product-story.test.mjs
```

Expected: PASS; existing routes remain intact.

- [ ] **Step 3: Run Theme Check and diff validation**

```powershell
npm run verify
git diff --check main...HEAD
git status --short
```

Expected: Theme Check zero errors, no whitespace errors and no unrelated files staged/modified.

- [ ] **Step 4: Verify all boundaries**

Read back the Shopify product as Draft with zero channels. Verify old products unchanged. Verify no production theme upload, push, redirect or publication occurred. Verify all eight theme assets trace to approved final-release manifests.

- [ ] **Step 5: Commit any final in-scope validation correction**

If a correction was required, return to the responsible task's file list, stage only the corrected paths from that list, rerun its focused test plus this full gate, and commit with `git commit -m "Harden unified PIMM product validation"`. If no correction was required, create no empty commit.

- [ ] **Step 6: Report the local handoff**

Report commit hashes, exact test counts, Theme Check result, browser viewport/language/model coverage, Draft product ID/handle/status, proof/final release IDs, asset hashes, skipped checks and the explicit no-push/no-deploy/no-publication boundary.
