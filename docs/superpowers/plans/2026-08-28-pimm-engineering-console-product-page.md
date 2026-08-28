# PIMM Engineering Console Product Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recompose the unified 30G/50G pneumatic injection molding machine page into the approved engineering-console presentation while preserving the existing fail-closed variant, commerce, localization, accessibility, and immutable render-lineage contracts.

**Architecture:** Keep `pimm-machine-product` and its variant JSON as the sole state controller. Extract the hero and qualification presentation into focused Liquid snippets that consume the existing model blocks and `data-pimm-*` bindings, then place the existing overview, engineering, and tooling media into one contained bento plus broad alternating story sections. CSS owns responsive composition; released Blender derivatives remain immutable inputs.

**Tech Stack:** Shopify Online Store 2.0 Liquid/JSON, vanilla CSS, vanilla JavaScript custom elements, Node.js built-in test runner, Shopify Theme Check, Playwright-compatible browser acceptance harness, FFmpeg/FFprobe for opt-in pixel inspection.

**Spec:** `docs/superpowers/specs/2026-08-28-pimm-engineering-console-product-page-design.md`

## Global Constraints

- Work only in `.worktrees/pimm-unified-configurator` on `codex/pimm-unified-configurator`.
- Do not push, deploy, mutate Shopify catalog data, publish a theme, or replace a production asset.
- Preserve exactly two ordered model records: `30G`, then `50G`. Do not change variant IDs, price/deposit arithmetic, metafields, or product schema.
- Keep `assets/maliev-pimm-machine.js` as the only state owner. New presentation must consume its existing `data-pimm-model-value`, `data-pimm-spec`, `data-pimm-media-model`, and `data-pimm-media-slot` interfaces.
- Factory visit is the primary conversion. Configuration/qualification is secondary. The 50% deposit control remains only in the final qualification flow.
- Use exactly one bento section. The rest of the page is an open hero, a qualification strip, and alternating editorial sections.
- Reuse only the eight assets authenticated by `assets/pimm-unified-render-assets.v1.json`. Working proofs and corrected-but-unapproved tooling proofs are not storefront inputs.
- Add no animation sequence, autoplay media, frontend framework, partner logos, unsupported claims, decorative watermark, glass effect, or duplicated storefront navigation.
- Preserve all 31 storefront locale files, Thai and English alt text, semantic headings, keyboard radio behavior, visible focus, reduced-motion behavior, 44px targets, and WCAG 2.2 AA contrast.
- Preserve unrelated dirty work. Stage only the files named by the current task and commit each validated slice separately.

---

## Task 1: Lock and Extract the Engineering-Console Hero Contract

**Files:**

- Create: `snippets/pimm-hero-console.liquid`
- Create: `snippets/pimm-qualification-strip.liquid`
- Modify: `sections/maliev-pimm-machine-product.liquid`
- Modify: `scripts/tests/pimm-unified-product-page-contract.test.mjs`

### Interface to preserve

`pimm-hero-console` receives `product`, `section`, `selected_model_code`, `selected_model_block`, `model_contract_valid`, `selected_variant`, and `factory_visit_url`. It renders existing model-block media and commerce values; it does not construct a second JSON payload.

`pimm-qualification-strip` receives `section`, `selected_model_code`, `selected_variant`, `full_price_cents`, `lead_time`, `model_contract_valid`, and `factory_visit_url`. It exposes the selected `statusText`, `fullPrice`, `depositPrice`, and `leadTime` values through the controller's existing `data-pimm-model-value` interface.

- [ ] **Step 1: Add failing semantic and narrative-order tests**

Extend the initial `Promise.all` and `renderedContract` assembly so both new snippets are read as first-class contract surfaces:

```js
const [section, heroConsole, qualificationStrip, selector, bento, purchase, ownership, templateSource, js, css, enLocaleSource, thLocaleSource] = await Promise.all([
  readThemeFile('sections/maliev-pimm-machine-product.liquid'),
  readThemeFile('snippets/pimm-hero-console.liquid'),
  readThemeFile('snippets/pimm-qualification-strip.liquid'),
  readThemeFile('snippets/pimm-model-selector.liquid'),
  readThemeFile('snippets/pimm-engineering-bento.liquid'),
  readThemeFile('snippets/pimm-purchase-qualification.liquid'),
  readThemeFile('snippets/pimm-ownership.liquid'),
  readThemeFile('templates/product.pimm-configurator.json'),
  readThemeFile('assets/maliev-pimm-machine.js'),
  readThemeFile('assets/maliev-pimm-machine.css'),
  readThemeFile('locales/en.default.json'),
  readThemeFile('locales/th.json'),
]);

const renderedContract = [section, heroConsole, qualificationStrip, selector, bento, purchase, ownership].join('\n');
```

Replace the old `pimm-machine__fit` ordering assertion with the approved page flow:

```js
const orderedLandmarks = [
  "render 'pimm-hero-console'",
  "render 'pimm-qualification-strip'",
  "render 'pimm-engineering-bento'",
  'pimm-machine__tooling',
  "render 'pimm-ownership'",
  "render 'pimm-purchase-qualification'",
];

assert.match(heroConsole, /<section[^>]*class="pimm-machine__hero-console"/);
assert.match(heroConsole, /<h1[^>]*id="PimmMachineTitle-/);
assert.match(heroConsole, /<figure[^>]*data-pimm-hero-media/);
assert.match(heroConsole, /data-pimm-hero-evidence/);
assert.match(qualificationStrip, /<section[^>]*data-pimm-qualification-strip/);
assert.doesNotMatch(section, /class="pimm-machine__fit"/);
```

- [ ] **Step 2: Run the focused contract test and confirm RED**

Run:

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
```

Expected: failure because `pimm-hero-console.liquid` and `pimm-qualification-strip.liquid` do not exist yet.

- [ ] **Step 3: Extract the hero without changing state ownership**

Move the current hero media loop and selector into `pimm-hero-console.liquid`. Use this structural contract:

```liquid
<section class="pimm-machine__hero-console" aria-labelledby="PimmMachineTitle-{{ section.id }}" data-pimm-hero-console>
  <div class="pimm-machine__hero-decision">
    <h1 id="PimmMachineTitle-{{ section.id }}">{{ product.title | remove: ' (Development)' | escape }}</h1>
    <p class="pimm-machine__hero-promise">{{ 'products.pimm_machine.hero.promise' | t }}</p>
    <p class="pimm-machine__hero-fit">{{ 'products.pimm_machine.hero.fit_statement' | t }}</p>
    {% render 'pimm-model-selector', product: product, selected_variant: selected_variant, section: section %}
    <div class="pimm-machine__hero-actions">
      <a class="button" href="{{ factory_visit_url }}">{{ 'products.pimm_machine.purchase.book_visit' | t }}</a>
      <a class="pimm-machine__text-link" href="#PimmMachinePurchase-{{ section.id }}">{{ 'products.pimm_machine.actions.configure' | t }}</a>
    </div>
  </div>

  <figure class="pimm-machine__hero-stage" data-pimm-hero-media></figure>
  <aside class="pimm-machine__hero-evidence" data-pimm-hero-evidence aria-labelledby="PimmMachineEvidence-{{ section.id }}">
    <h2 id="PimmMachineEvidence-{{ section.id }}">{{ 'products.pimm_machine.hero.evidence_heading' | t }}</h2>
    <dl class="pimm-machine__hero-facts"></dl>
    <a class="pimm-machine__hero-detail" href="#PimmMachineEngineering-{{ section.id }}">
      <span>{{ 'products.pimm_machine.hero.engineering_detail' | t }}</span>
    </a>
  </aside>
</section>
```

The empty `figure` and `dl` above show only the required outer interface. Populate them by transplanting the current proven hero model-block loop and four specification `<div>` elements unchanged: explicit 1800×2200 dimensions, selected-only eager loading, locale-specific alt resolution, hidden/`aria-hidden`/`inert` state, `data-pimm-media-model`, `data-pimm-media-slot="hero"`, `data-pimm-spec`, and localized `data-pimm-spec-unit`. Move the current engineering model-block loop into `.pimm-machine__hero-detail` with `data-pimm-media-slot="engineering"`, lazy loading, and explicit 2400×1800 dimensions. Do not leave explanatory comments or empty elements in production Liquid.

- [ ] **Step 4: Add the compact qualification strip**

Create `pimm-qualification-strip.liquid` with a semantic summary and existing controller hooks:

```liquid
<section class="pimm-machine__qualification-strip" data-pimm-qualification-strip aria-labelledby="PimmMachineCommercial-{{ section.id }}">
  <h2 id="PimmMachineCommercial-{{ section.id }}" class="visually-hidden">{{ 'products.pimm_machine.qualification.heading' | t }}</h2>
  <dl class="pimm-machine__qualification-facts">
    <div><dt>{{ 'products.pimm_machine.qualification.availability' | t }}</dt><dd data-pimm-model-value="statusText">{{ selected_status_text }}</dd></div>
    <div><dt>{{ 'products.pimm_machine.purchase.full_price' | t }}</dt><dd data-pimm-model-value="fullPrice">{{ full_price_cents | money_with_currency }}</dd></div>
    <div><dt>{{ 'products.pimm_machine.purchase.deposit_price' | t }}</dt><dd data-pimm-model-value="depositPrice">{{ selected_variant.price | money_with_currency }}</dd></div>
    <div><dt>{{ 'products.pimm_machine.purchase.lead_time_label' | t }}</dt><dd data-pimm-model-value="leadTime">{{ 'products.pimm_machine.purchase.lead_time' | t: days: lead_time }}</dd></div>
  </dl>
  <a class="button button--secondary" href="{{ factory_visit_url }}">
    {{ 'products.pimm_machine.purchase.book_visit' | t }}
  </a>
</section>
```

Compute `selected_status_text` with the same fail-closed branch used by the final qualification snippet. `full_price_cents` and `lead_time` are passed from the parent after its existing metafield validation. Repeating `data-pimm-model-value` is intentional because the controller updates every matching node. Do not repeat `data-pimm-variant-status`, render a second product form, or render a second deposit button.

- [ ] **Step 5: Recompose the parent section**

Replace the inline hero and separate fit section with focused renders. Keep the existing outer product form, app blocks, model validation, variant JSON, schema, tooling, ownership, and purchase flows intact:

```liquid
{% render 'pimm-hero-console',
  product: product,
  section: section,
  selected_model_code: selected_model_code,
  selected_model_block: selected_model_block,
  selected_variant: selected_variant,
  model_contract_valid: model_contract_valid,
  factory_visit_url: factory_visit_url
%}
{% render 'pimm-qualification-strip',
  section: section,
  selected_model_code: selected_model_code,
  selected_variant: selected_variant,
  full_price_cents: selected_full_price_cents,
  lead_time: lead_time,
  model_contract_valid: model_contract_valid,
  factory_visit_url: factory_visit_url
%}
{% render 'pimm-engineering-bento',
  selected_model_code: selected_model_code,
  specifications: specifications,
  model_contract_valid: model_contract_valid,
  section: section
%}
```

Resolve `factory_visit_url` once in the parent before the form, using `section.settings.factory_visit_url` with `routes.root_url | append: 'pages/contact'` as the existing fallback. Keep the final purchase snippet's behavior identical; passing the resolved URL into the new presentation snippets must not change the section schema.

- [ ] **Step 6: Run the focused contract test and confirm GREEN**

Run:

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
```

Expected: all product-page contract subtests pass.

- [ ] **Step 7: Commit the semantic composition slice**

```powershell
git add sections/maliev-pimm-machine-product.liquid snippets/pimm-hero-console.liquid snippets/pimm-qualification-strip.liquid scripts/tests/pimm-unified-product-page-contract.test.mjs
git commit -m "Recompose PIMM product presentation"
```

---

## Task 2: Place Released Media into One Bento and Broad Story Sections

**Files:**

- Modify: `snippets/pimm-engineering-bento.liquid`
- Modify: `sections/maliev-pimm-machine-product.liquid`
- Modify: `scripts/tests/pimm-unified-product-page-contract.test.mjs`
- Verify unchanged: `assets/maliev-pimm-machine.js`

- [ ] **Step 1: Add failing media-placement tests**

Make each visual purpose explicit while keeping the same four controller slots:

```js
test('released media has one purpose per selected-model narrative position', () => {
  assert.equal(renderedContract.match(/data-pimm-engineering-bento/g)?.length, 1);
  assert.match(heroConsole, /data-pimm-media-slot="hero"/);
  assert.match(heroConsole, /data-pimm-media-slot="engineering"/);
  assert.match(bento, /data-pimm-media-slot="overview"/);
  assert.match(section, /class="pimm-machine__tooling[\s\S]*data-pimm-media-slot="tooling"/);
  assert.equal(renderedContract.match(/data-pimm-media-slot="overview"/g)?.length, 1);
  assert.equal(renderedContract.match(/data-pimm-media-slot="engineering"/g)?.length, 1);
});

test('the hero alone is eager and every detail render stays lazy', () => {
  assert.match(heroConsole, /loading="eager"[\s\S]*data-pimm-media-slot="hero"/);
  for (const source of [heroConsole, bento, section]) {
    for (const slot of ['overview', 'engineering', 'tooling']) {
      if (source.includes(`data-pimm-media-slot="${slot}"`)) {
        assert.match(source, new RegExp(`loading="lazy"[\\s\\S]*decoding="async"[\\s\\S]*data-pimm-media-slot="${slot}"`));
      }
    }
  }
});
```

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
```

Expected: media-placement assertions fail because the current bento owns the engineering controls render and the overview remains in the old fit layout.

- [ ] **Step 3: Make the overview the bento's dominant image**

Update `pimm-engineering-bento.liquid` so its large cell resolves `overview_asset`/localized overview alt text and falls back to the selected hero exactly as the variant contract does:

```liquid
{% assign block_overview_asset = block.settings.overview_asset %}
{% assign block_overview_alt = block.settings.overview_alt_en | strip_html %}
{% if is_thai and block.settings.overview_alt_th != blank %}
  {% assign block_overview_alt = block.settings.overview_alt_th | strip_html %}
{% endif %}
{% if block_overview_asset == blank %}
  {% assign block_overview_asset = block.settings.hero_asset %}
  {% assign block_overview_alt = block_hero_alt %}
{% endif %}

<picture
  data-pimm-media-model="{{ block.settings.model_code }}"
  data-pimm-media-slot="overview"
  aria-hidden="{% if media_is_selected %}false{% else %}true{% endif %}"
  {% unless media_is_selected %}hidden inert{% endunless %}
>
  <img
    src="{{ block_overview_asset | asset_url }}"
    alt="{{ block_overview_alt | escape }}"
    width="{{ block_overview_width }}"
    height="{{ block_overview_height }}"
    loading="lazy"
    decoding="async"
    data-pimm-media-image
  >
</picture>
```

Keep the four specification terms bound to existing `data-pimm-spec` fields; their values must never be copied into decorative Liquid literals.

- [ ] **Step 4: Keep engineering and tooling media singular**

The hero evidence panel owns the sole `engineering` slot. The tooling story owns the sole `tooling` slot. Remove the retired overview/fit media block from the parent section. Preserve selected-model `hidden`, `aria-hidden`, and `inert` semantics on every model media group.

- [ ] **Step 5: Prove the JavaScript interface did not change**

Run:

```powershell
git diff --exit-code -- assets/maliev-pimm-machine.js
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
```

Expected: no JavaScript diff; all contract subtests pass, including model switching, fail-closed behavior, URL updates, image decode, and slot fallback.

- [ ] **Step 6: Commit the media narrative slice**

```powershell
git add snippets/pimm-engineering-bento.liquid sections/maliev-pimm-machine-product.liquid scripts/tests/pimm-unified-product-page-contract.test.mjs
git commit -m "Align PIMM renders with product story"
```

---

## Task 3: Build the Responsive Engineering-Console Visual System

**Files:**

- Modify: `assets/maliev-pimm-machine.css`
- Modify: `snippets/pimm-hero-console.liquid`
- Modify: `snippets/pimm-qualification-strip.liquid`
- Modify: `snippets/pimm-model-selector.liquid`
- Modify: `locales/en.default.json`
- Modify: `locales/th.json`
- Modify: `locales/*.json` for the remaining 29 installed storefront locales
- Modify: `scripts/tests/pimm-unified-product-page-contract.test.mjs`

- [ ] **Step 1: Add failing layout, accessibility, and locale assertions**

Replace the old two-column hero assertion with the approved 12-column contract:

```js
test('engineering console uses the approved three-rail grid without card-page effects', () => {
  assert.match(css, /\.pimm-machine__hero-console\s*\{[^}]*display:\s*grid[^}]*grid-template-columns:\s*repeat\(12,\s*minmax\(0,\s*1fr\)\)/s);
  assert.match(css, /\.pimm-machine__hero-decision\s*\{[^}]*grid-column:\s*1\s*\/\s*4/s);
  assert.match(css, /\.pimm-machine__hero-stage\s*\{[^}]*grid-column:\s*4\s*\/\s*9/s);
  assert.match(css, /\.pimm-machine__hero-evidence\s*\{[^}]*grid-column:\s*9\s*\/\s*-1/s);
  assert.match(css, /\.pimm-machine__hero-console\s*\{[^}]*border-radius:\s*var\(--pimm-radius-lg,\s*14px\)/s);
  assert.doesNotMatch(css, /backdrop-filter|linear-gradient|radial-gradient|filter:\s*drop-shadow/i);
  assert.match(css, /@media\s*\(max-width:\s*1199px\)/);
  assert.match(css, /@media\s*\(max-width:\s*749px\)/);
  assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)/);
  assert.match(css, /min-height:\s*44px/);
  assert.match(css, /object-fit:\s*contain/);
});
```

Add these keys to the locale contract list:

```js
const consoleKeys = [
  'hero.promise',
  'hero.evidence_heading',
  'hero.engineering_detail',
  'actions.configure',
  'qualification.heading',
  'qualification.availability',
];
```

Require Thai and English to have native values, while other installed locales retain the established English fallback values and identical placeholder sets.

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
```

Expected: CSS and locale-key assertions fail.

- [ ] **Step 3: Add exact English and Thai console copy**

Under `products.pimm_machine`, add:

```json
{
  "hero": {
    "promise": "Real injection molding capability, sized for your workshop.",
    "evidence_heading": "Selected machine",
    "engineering_detail": "Inspect pneumatic controls"
  },
  "actions": {
    "configure": "Configure this machine"
  },
  "qualification": {
    "heading": "Commercial summary",
    "availability": "Availability"
  }
}
```

Thai values:

```json
{
  "hero": {
    "promise": "ฉีดพลาสติกจริงในขนาดที่เหมาะกับเวิร์กช็อปของคุณ",
    "evidence_heading": "เครื่องที่เลือก",
    "engineering_detail": "ดูระบบควบคุมนิวแมติก"
  },
  "actions": {
    "configure": "กำหนดสเปกเครื่องนี้"
  },
  "qualification": {
    "heading": "สรุปข้อมูลการสั่งซื้อ",
    "availability": "สถานะการผลิต"
  }
}
```

Merge keys into the existing objects; do not replace or duplicate `hero`. Copy the English fallback strings into the corresponding namespace for the other 29 locale files so every installed locale has the same key/placeholder contract.

- [ ] **Step 4: Implement the desktop 12-column composition**

Use design tokens and flat surface separation:

```css
.pimm-machine__hero-console {
  --pimm-radius-lg: 14px;
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: clamp(1.5rem, 3vw, 3.5rem);
  align-items: center;
  max-width: 1440px;
  margin-inline: auto;
  padding: clamp(1.5rem, 3.5vw, 4rem);
  overflow: clip;
  border: 1px solid rgb(var(--color-foreground) / 0.08);
  border-radius: var(--pimm-radius-lg, 14px);
  background: rgb(var(--color-background));
}

.pimm-machine__hero-decision { grid-column: 1 / 4; min-width: 0; }
.pimm-machine__hero-stage { grid-column: 4 / 9; min-width: 0; align-self: stretch; }
.pimm-machine__hero-evidence { grid-column: 9 / -1; min-width: 0; }
.pimm-machine__hero-stage img { width: 100%; height: 100%; max-height: min(72vh, 720px); object-fit: contain; }
.pimm-machine__hero-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
```

Use existing MALIEV Ink/Canvas/Surface/Signal Blue variables where present. Do not add a large shadow or make each entire page section a floating card.

- [ ] **Step 5: Implement tablet and mobile source order**

```css
@media (max-width: 1199px) {
  .pimm-machine__hero-console {
    grid-template-columns: minmax(240px, 4fr) minmax(360px, 6fr);
  }
  .pimm-machine__hero-decision { grid-column: 1 / 2; grid-row: 1; }
  .pimm-machine__hero-stage { grid-column: 2 / -1; grid-row: 1; }
  .pimm-machine__hero-evidence { display: grid; grid-column: 1 / -1; grid-row: 2; grid-template-columns: 1fr 1fr; }
}

@media (max-width: 749px) {
  .pimm-machine__hero-console {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    overflow: visible;
  }
  .pimm-machine__hero-decision { display: contents; }
  .pimm-machine__hero-title-group { order: 1; }
  .pimm-machine__model-selector { order: 2; }
  .pimm-machine__hero-stage { order: 3; aspect-ratio: 9 / 11; }
  .pimm-machine__hero-actions { order: 4; }
  .pimm-machine__hero-evidence { order: 5; }
  .pimm-machine__hero-facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .pimm-machine__qualification-strip { display: flex; flex-direction: column; }
}

@media (max-width: 359px) {
  .pimm-machine__hero-facts { grid-template-columns: minmax(0, 1fr); }
}
```

Group title/fit and actions in explicit wrappers so `display: contents` produces the required mobile order without JavaScript or duplicated controls. Confirm focus outlines are not clipped and all buttons/radios are at least 44px high.

- [ ] **Step 6: Run focused tests and Theme Check**

Run:

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
npm run verify:theme
```

Expected: all Node subtests pass; Theme Check exits zero with zero errors.

- [ ] **Step 7: Commit the visual-system slice**

```powershell
git add assets/maliev-pimm-machine.css snippets/pimm-hero-console.liquid snippets/pimm-qualification-strip.liquid snippets/pimm-model-selector.liquid locales scripts/tests/pimm-unified-product-page-contract.test.mjs
git commit -m "Style PIMM engineering console responsively"
```

---

## Task 4: Strengthen Released-Render Layout Eligibility

**Files:**

- Modify: `scripts/tests/pimm-unified-render-assets.test.mjs`
- Verify unchanged: `assets/pimm-unified-render-assets.v1.json`
- Verify unchanged: the eight `assets/pimm-machine-*.webp` files

- [ ] **Step 1: Add failing role-specific layout eligibility tests**

Promote the existing dimension and alpha requirements into explicit role policy:

```js
const expectedRolePolicy = new Map([
  ['hero-front', { dimensions: [1800, 2200], alpha: true, orientation: 'portrait' }],
  ['overview-three-quarter', { dimensions: [2400, 1800], alpha: true, orientation: 'landscape' }],
  ['engineering-controls', { dimensions: [2400, 1800], alpha: true, orientation: 'landscape' }],
  ['tooling-front-detail', { dimensions: [2400, 1800], alpha: true, orientation: 'landscape' }],
]);

test('released roles remain eligible for their responsive presentation slots', () => {
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  for (const entry of manifest.assets) {
    const policy = expectedRolePolicy.get(entry.shot);
    assert.ok(policy, `missing role policy for ${entry.shot}`);
    assert.deepEqual(entry.dimensions, policy.dimensions, `${entry.name} no longer fits ${entry.shot}`);
    assert.equal(entry.dimensions[0] > entry.dimensions[1], policy.orientation === 'landscape');
    assert.equal(webpMetadata(readFileSync(join(root, 'assets', entry.name))).alpha, policy.alpha);
  }
});
```

This is a test-only hardening slice over already released files, so a contrived RED phase is not appropriate. The new invariant should pass immediately if the current release is intact; any failure is evidence of real asset, manifest, or policy drift. Do not mutate a released asset to manufacture failure.

- [ ] **Step 2: Run lineage tests with decoder inspection**

Run:

```powershell
$env:PIMM_RENDER_DECODER_CHECK = '1'
node --test scripts/tests/pimm-unified-render-assets.test.mjs
Remove-Item Env:PIMM_RENDER_DECODER_CHECK
```

Expected final result: all tests pass; FFprobe reports WebP, exact dimensions match role policy, every image includes transparent pixels and fully opaque subject pixels, and all hashes still match the immutable manifest. If `ffmpeg`/`ffprobe` is absent, report the missing executable and run the non-decoder test without claiming pixel inspection.

- [ ] **Step 3: Prove no render or manifest mutation occurred**

Run:

```powershell
git diff --exit-code -- assets/pimm-unified-render-assets.v1.json assets/pimm-machine-30g-hero-front.webp assets/pimm-machine-30g-overview-three-quarter.webp assets/pimm-machine-30g-engineering-controls.webp assets/pimm-machine-30g-tooling-front-detail.webp assets/pimm-machine-50g-hero-front.webp assets/pimm-machine-50g-overview-three-quarter.webp assets/pimm-machine-50g-engineering-controls.webp assets/pimm-machine-50g-tooling-front-detail.webp
```

Expected: exit zero and no output.

- [ ] **Step 4: Commit only the strengthened gate**

```powershell
git add scripts/tests/pimm-unified-render-assets.test.mjs
git commit -m "Guard PIMM render layout eligibility"
```

---

## Task 5: Add Browser Geometry Acceptance and Finish Local Validation

**Files:**

- Modify: `scripts/tests/pimm-unified-responsive-browser.test.mjs`
- Modify only if browser evidence exposes a defect: `assets/maliev-pimm-machine.css`
- Modify only if browser evidence exposes a semantic defect: `snippets/pimm-hero-console.liquid`, `snippets/pimm-qualification-strip.liquid`
- Evidence only, do not commit: existing ignored browser screenshot directory used by the harness

- [ ] **Step 1: Add a failing engineering-console browser probe**

Extend the existing page probe:

```js
const consoleProbe = await session.evaluate(() => {
  const rect = (selector) => {
    const value = document.querySelector(selector)?.getBoundingClientRect();
    return value ? { left: value.left, right: value.right, top: value.top, bottom: value.bottom, width: value.width, height: value.height } : null;
  };
  const overlaps = (a, b) => a && b && a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
  const decision = rect('.pimm-machine__hero-decision');
  const stage = rect('.pimm-machine__hero-stage');
  const evidence = rect('.pimm-machine__hero-evidence');
  const selectedHero = document.querySelector('[data-pimm-media-model]:not([hidden])[data-pimm-media-slot="hero"] img');
  const image = selectedHero?.getBoundingClientRect();
  return {
    decision,
    stage,
    evidence,
    overlaps: {
      decisionStage: overlaps(decision, stage),
      stageEvidence: overlaps(stage, evidence),
    },
    imageContained: Boolean(image && stage && image.left >= stage.left - 1 && image.right <= stage.right + 1 && image.top >= stage.top - 1 && image.bottom <= stage.bottom + 1),
    naturalSize: selectedHero ? [selectedHero.naturalWidth, selectedHero.naturalHeight] : null,
    visibleFactCount: [...document.querySelectorAll('.pimm-machine__hero-facts [data-pimm-spec]')].filter((node) => node.getClientRects().length > 0).length,
    qualificationTop: rect('[data-pimm-qualification-strip]')?.top ?? null,
    heroBottom: rect('[data-pimm-hero-console]')?.bottom ?? null,
    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  };
});
```

Assert for every model/language/viewport case:

```js
assert.equal(consoleProbe.overlaps.decisionStage, false);
assert.equal(consoleProbe.overlaps.stageEvidence, false);
assert.equal(consoleProbe.imageContained, true);
assert.deepEqual(consoleProbe.naturalSize, [1800, 2200]);
assert.equal(consoleProbe.visibleFactCount, 4);
assert.ok(consoleProbe.qualificationTop >= consoleProbe.heroBottom - 1);
assert.ok(consoleProbe.overflowX <= 1);
```

- [ ] **Step 2: Run the browser matrix against the integrated local implementation**

With the authenticated local preview server running on port 9393, run:

```powershell
$env:PIMM_BROWSER_ACCEPTANCE = '1'
$env:PIMM_PREVIEW_URL = 'http://127.0.0.1:9393/products_preview?preview_key=6a12c863784016889e64a8e014064eb2&view=pimm-configurator&variant=54823758659863'
node --test scripts/tests/pimm-unified-responsive-browser.test.mjs
```

Expected: the local preview loads the new console and the geometry assertions pass. A missing selector or failed geometry assertion is a real integration defect. If the preview key has expired, restart `npm run dev`, use the newly printed local preview URL, and rerun; do not weaken the test.

- [ ] **Step 3: Validate the complete responsive matrix**

Exercise both `30G` and `50G`, English and Thai, at:

- 1440 × 900
- 1280 × 800
- 1024 × 768
- 390 × 844
- 360 × 800

Keep the existing harness checks for selected radio state, URL variant state, exact media, alt text, loading policy, unavailable model behavior, keyboard switching, and reduced motion. Add or retain screenshot capture for each desktop/mobile hero state.

At 200% browser zoom, manually inspect the 390 × 844 flow for source order, visible focus, one- or two-column facts as space permits, and no lost commercial controls. Record this as visual evidence, not an automated WCAG claim.

- [ ] **Step 4: Correct only evidence-backed geometry defects**

If the browser probe shows crop, overlap, floating composition, or overflow, make the smallest CSS/markup correction and rerun the exact failing viewport before the full matrix. Do not alter released pixels to compensate for CSS geometry.

- [ ] **Step 5: Run the full repository gate**

Run:

```powershell
node --test scripts/tests/pimm-unified-product-page-contract.test.mjs
$env:PIMM_RENDER_DECODER_CHECK = '1'
node --test scripts/tests/pimm-unified-render-assets.test.mjs
Remove-Item Env:PIMM_RENDER_DECODER_CHECK
npm run verify
node --test scripts/tests/pimm-unified-responsive-browser.test.mjs
git status --short
```

Expected:

- Product-page contract: all subtests pass.
- Render-assets contract: all subtests pass, including decoder inspection.
- `npm run verify`: Theme Check and render-assets gate exit zero.
- Browser acceptance: all English/Thai, 30G/50G, viewport, failure-state, keyboard, and reduced-motion cases pass.
- Working tree contains only the intended browser-test and evidence-backed correction files before commit.

- [ ] **Step 6: Commit the browser acceptance slice**

```powershell
git add scripts/tests/pimm-unified-responsive-browser.test.mjs
git add assets/maliev-pimm-machine.css snippets/pimm-hero-console.liquid snippets/pimm-qualification-strip.liquid
git diff --cached --check
git commit -m "Verify PIMM console across responsive states"
```

Before committing, unstage any listed markup/CSS file that has no task-owned diff. Never stage screenshots, local preview credentials, `.env` files, or unrelated changes.

- [ ] **Step 7: Report the local-only result**

Report:

- the exact files and components changed;
- that `pimm-machine-product` remains the sole controller;
- that the eight released asset hashes and manifest were unchanged;
- actual Node test counts, Theme Check result, browser matrix result, and screenshots reviewed;
- commit hashes for each slice;
- any skipped decoder/browser/zoom checks and their exact blocker;
- explicitly that nothing was pushed, deployed, published, or changed in the Shopify catalog.
