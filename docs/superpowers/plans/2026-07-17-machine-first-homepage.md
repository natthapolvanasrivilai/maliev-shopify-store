# MALIEV Machine-First Homepage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a responsive, machine-first Shopify homepage that presents the MALIEV 30g and 50g pneumatic injection molding machines and prioritizes demonstration and quotation inquiries.

**Architecture:** Replace the current category-led homepage order with seven focused Online Store 2.0 sections sharing one namespaced presentation asset and one progressive-enhancement script. Keep all content and media merchant-editable, preserve accurate existing machine renders as fallbacks, and route demo, quotation, and mold CTAs to a query-aware contact form.

**Tech Stack:** Shopify Liquid, Online Store 2.0 JSON templates and section schemas, CSS, dependency-free browser JavaScript, Node.js verification script, Shopify Theme Check.

## Global Constraints

- Follow `DESIGN.md`, `PRODUCT.md`, `IMAGE_GUIDELINES.md`, and `docs/superpowers/specs/2026-07-17-machine-first-homepage-design.md`.
- Schedule a demonstration is the primary action; request a quotation is secondary; LINE and specification downloads are tertiary.
- Preserve the real 30g and 50g machine geometry and relative identity; final Blender renders must remain swappable through Theme Editor media settings.
- Do not show customer logos, confidential molds, unsupported savings percentages, or unsupported competitor comparisons.
- Preserve semantic heading order, visible focus, WCAG 2.2 AA contrast, reduced-motion behavior, no-JavaScript readability, and zero horizontal overflow.
- Preserve valid `{% schema %}` contracts and locale-ready user-facing interface labels.
- Do not add third-party frontend dependencies.
- Run `npm run verify` before every implementation commit.

---

## File map

### Create

- `assets/maliev-machine-home.css` — shared `mm-*` visual system, layout, responsive rules, focus states, and reduced-motion behavior.
- `assets/maliev-machine-home.js` — optional intersection reveals and enhancement state; content stays visible without JavaScript.
- `assets/maliev-contact-inquiry.js` — preselects a valid contact inquiry type from the `inquiry` query parameter.
- `sections/maliev-machine-hero.liquid` — dual-machine launch hero and primary conversion actions.
- `sections/maliev-machine-capability.liquid` — compact-workshop story and qualitative small-batch economics.
- `sections/maliev-machine-models.liquid` — accessible stacked/two-column 30g and 50g comparison.
- `sections/maliev-machine-engineering.liquid` — controller/engineering detail chapter with optional desktop sticky media.
- `sections/maliev-machine-support.liquid` — Thai manufacturing commitments and three-step mold assistance path.
- `sections/maliev-machine-conversion.liquid` — final demo/quotation/LINE decision section.
- `sections/maliev-more-from-maliev.liquid` — quiet secondary discovery area for Mesh Splitter, SimMount, printed products, and guides.
- `scripts/verify-homepage.mjs` — structural regression checks for section order, CTA routes, Thai overrides, and removal of category-led sections from the active homepage order.

### Modify

- `templates/index.json` — define and order the seven machine-first sections with English defaults.
- `templates/index.context.thailand.json` — override the same section and block IDs with Thai copy.
- `sections/contact-form.liquid` — add the inquiry selector and load query preselection JavaScript.
- `locales/en.default.json` — add English inquiry labels.
- `locales/th.json` — add Thai inquiry labels.
- `package.json` — run structural homepage checks before Theme Check.

### Preserve

- Existing `maliev-*` homepage sections remain available to other templates and the Theme Editor but are removed from `templates/index.json` and its Thailand context order.
- Existing 30g Shopify CDN render and `assets/machine-portrait-50g-front-studio.png` provide accurate temporary product media.
- Existing `pimm-50g-*` launch assets remain untouched.

---

### Task 1: Add the homepage structural regression gate

**Files:**

- Create: `scripts/verify-homepage.mjs`
- Modify: `package.json`

**Interfaces:**

- Consumes: `templates/index.json` and `templates/index.context.thailand.json` as JSON-with-leading-comment files.
- Produces: a zero exit status and `Homepage structure verified.` when the required section contract is present.

- [ ] **Step 1: Write the failing structural verifier**

Create `scripts/verify-homepage.mjs` with a comment-tolerant JSON reader and exact assertions:

```js
import { readFile } from 'node:fs/promises';

const readThemeJson = async (path) => {
  const source = await readFile(path, 'utf8');
  return JSON.parse(source.replace(/^\/\*[\s\S]*?\*\/\s*/, ''));
};

const home = await readThemeJson('templates/index.json');
const thailand = await readThemeJson('templates/index.context.thailand.json');
const expectedOrder = [
  'machine_hero',
  'machine_capability',
  'machine_models',
  'machine_engineering',
  'machine_support',
  'machine_conversion',
  'more_from_maliev'
];

const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};

assert(JSON.stringify(home.order) === JSON.stringify(expectedOrder), 'English homepage order is not machine-first.');
assert(JSON.stringify(thailand.order) === JSON.stringify(expectedOrder), 'Thailand homepage order is not machine-first.');
assert(home.sections.machine_hero.type === 'maliev-machine-hero', 'Machine hero section is missing.');
assert(home.sections.machine_hero.settings.primary_link.includes('inquiry=demo'), 'Demo CTA must label the inquiry.');
assert(home.sections.machine_hero.settings.secondary_link.includes('inquiry=quote'), 'Quote CTA must label the inquiry.');
assert(thailand.sections.machine_hero.settings.primary_label.length > 0, 'Thai hero CTA override is missing.');

const retiredPrimarySections = ['maliev_tool_pricing', 'maliev_family_grid', 'maliev_workflow'];
for (const sectionId of retiredPrimarySections) {
  assert(!home.order.includes(sectionId), `${sectionId} must not appear in the primary homepage order.`);
}

console.log('Homepage structure verified.');
```

- [ ] **Step 2: Add the verifier to the project gate**

Change the `package.json` scripts object to:

```json
"scripts": {
  "dev": "shopify theme dev --store 10b918-e4.myshopify.com",
  "verify:homepage": "node scripts/verify-homepage.mjs",
  "verify:theme": "shopify theme check --path . --fail-level error --no-color",
  "verify": "npm run verify:homepage && npm run verify:theme",
  "sync:live": "shopify theme pull --store 10b918-e4.myshopify.com --theme 190305730839 --nodelete"
}
```

- [ ] **Step 3: Run the verifier and confirm the intended failure**

Run: `npm run verify:homepage`

Expected: FAIL with `English homepage order is not machine-first.`

- [ ] **Step 4: Commit the red regression gate with the first passing homepage slice, not independently**

Do not commit a deliberately failing branch. Stage these files with Task 2 after the hero and template skeleton make the gate pass.

---

### Task 2: Build the shared visual foundation and launch hero

**Files:**

- Create: `assets/maliev-machine-home.css`
- Create: `assets/maliev-machine-home.js`
- Create: `sections/maliev-machine-hero.liquid`
- Modify: `templates/index.json`
- Modify: `templates/index.context.thailand.json`
- Modify: `scripts/verify-homepage.mjs`
- Modify: `package.json`

**Interfaces:**

- Produces: `.mm-home`, `.mm-shell`, `.mm-button`, `.mm-button--secondary`, `.mm-eyebrow`, `.mm-section-heading`, `[data-mm-reveal]`, and the `mm-enhanced` document class used by later sections.
- Produces template IDs `machine_hero`, `machine_capability`, `machine_models`, `machine_engineering`, `machine_support`, `machine_conversion`, and `more_from_maliev`; later tasks replace temporary section types one by one.

- [ ] **Step 1: Create the shared CSS tokens and accessible primitives**

Start `assets/maliev-machine-home.css` with:

```css
.mm-home {
  --mm-ink: #101114;
  --mm-muted: #5f636b;
  --mm-line: #dfe2e7;
  --mm-surface: #f5f6f8;
  --mm-blue: #1267d6;
  --mm-blue-hover: #0c55b7;
  --mm-radius: 2rem;
  color: var(--mm-ink);
  background: #fff;
  overflow: clip;
}

.mm-shell {
  width: min(100% - 3rem, 144rem);
  margin-inline: auto;
}

.mm-button {
  display: inline-flex;
  min-height: 4.8rem;
  align-items: center;
  justify-content: center;
  padding: 1.2rem 2.2rem;
  border: 1px solid var(--mm-blue);
  border-radius: 999px;
  background: var(--mm-blue);
  color: #fff;
  font-weight: 600;
  text-decoration: none;
}

.mm-button:hover { background: var(--mm-blue-hover); }
.mm-button--secondary { background: transparent; color: var(--mm-ink); border-color: var(--mm-line); }
.mm-button:focus-visible, .mm-link:focus-visible { outline: 3px solid #78aef2; outline-offset: 3px; }

[data-mm-reveal] { opacity: 1; transform: none; }
.mm-enhanced [data-mm-reveal] { opacity: 0; transform: translateY(2rem); }
.mm-enhanced [data-mm-reveal].is-visible { opacity: 1; transform: none; transition: opacity 600ms ease, transform 600ms ease; }

@media (prefers-reduced-motion: reduce) {
  .mm-enhanced [data-mm-reveal] { opacity: 1; transform: none; transition: none; }
  .mm-home *, .mm-home *::before, .mm-home *::after { scroll-behavior: auto !important; animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }
}
```

Add responsive shell, type, hero, action, and dual-product-stage rules. At widths below `750px`, stack copy before imagery and make the first two CTA buttons full width. At widths `990px` and above, use a two-column hero with copy occupying approximately 40% and imagery 60%.

- [ ] **Step 2: Create progressive reveal behavior**

Create `assets/maliev-machine-home.js`:

```js
(() => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const elements = [...document.querySelectorAll('[data-mm-reveal]')];
  if (!elements.length || !('IntersectionObserver' in window)) return;
  document.documentElement.classList.add('mm-enhanced');
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    }
  }, { rootMargin: '0px 0px -10% 0px', threshold: 0.12 });
  elements.forEach((element) => observer.observe(element));
})();
```

- [ ] **Step 3: Create the launch hero section**

Create `sections/maliev-machine-hero.liquid` with:

- Shared stylesheet and deferred script tags.
- One `<section class="mm-home mm-hero">` and one `<h1>`.
- Escaped eyebrow, heading, lead, CTA labels, links, and alt text.
- Shopify image-picker output first, URL fallback second, and `machine-portrait-50g-front-studio.png` asset fallback for 50g.
- A 30g URL fallback of `https://cdn.shopify.com/s/files/1/0856/7426/2807/files/machine-portrait.14.png?v=1737114840`.
- Explicit image widths, heights, `sizes`, `srcset`/`image_tag`, eager loading, and high fetch priority.
- A proof strip rendered from up to three `proof` blocks.
- Valid schema settings for all copy, links, both images/URLs/alts, and proof blocks.

The CTA markup must be:

```liquid
<div class="mm-actions">
  <a class="mm-button" href="{{ section.settings.primary_link }}">{{ section.settings.primary_label | escape }}</a>
  <a class="mm-button mm-button--secondary" href="{{ section.settings.secondary_link }}">{{ section.settings.secondary_label | escape }}</a>
</div>
<div class="mm-text-links">
  <a class="mm-link" href="#machine-models">{{ section.settings.compare_label | escape }}</a>
  {%- if section.settings.spec_label != blank and section.settings.spec_link != blank -%}
    <a class="mm-link" href="{{ section.settings.spec_link }}">{{ section.settings.spec_label | escape }}</a>
  {%- endif -%}
</div>
```

- [ ] **Step 4: Replace the homepage with the complete target ID skeleton**

Rewrite `templates/index.json` so its order is exactly:

```json
[
  "machine_hero",
  "machine_capability",
  "machine_models",
  "machine_engineering",
  "machine_support",
  "machine_conversion",
  "more_from_maliev"
]
```

Use `maliev-machine-hero` for `machine_hero`. Until later tasks create the remaining types, point their entries to existing valid types only during the local edit, then complete all section files before running Theme Check. English hero defaults:

```json
{
  "eyebrow": "Pneumatic injection molding machines",
  "heading": "Small footprint. Real production.",
  "lead": "Compact machines for prototypes and small batches, made and supported by MALIEV in Thailand.",
  "primary_label": "Schedule a demonstration",
  "primary_link": "/pages/contact?inquiry=demo#ContactForm",
  "secondary_label": "Request a quotation",
  "secondary_link": "/pages/contact?inquiry=quote#ContactForm",
  "compare_label": "Compare 30g and 50g",
  "spec_label": "Download specifications"
}
```

Rewrite `templates/index.context.thailand.json` to inherit `index.json`, preserve the same IDs/order, and use:

```json
{
  "eyebrow": "เครื่องฉีดพลาสติกระบบนิวเมติก",
  "heading": "ขนาดกะทัดรัด พร้อมผลิตจริง",
  "lead": "เครื่องสำหรับงานต้นแบบและการผลิตจำนวนน้อย ผลิตและดูแลโดยทีม MALIEV ในประเทศไทย",
  "primary_label": "นัดชมการสาธิต",
  "secondary_label": "ขอใบเสนอราคา",
  "compare_label": "เปรียบเทียบรุ่น 30g และ 50g",
  "spec_label": "ดาวน์โหลดสเปก"
}
```

- [ ] **Step 5: Run the structural and theme gates**

Run: `npm run verify`

Expected: `Homepage structure verified.`, Theme Check exits `0`, and only the known baseline warnings remain.

- [ ] **Step 6: Commit the foundation**

```powershell
git add package.json scripts/verify-homepage.mjs assets/maliev-machine-home.css assets/maliev-machine-home.js sections/maliev-machine-hero.liquid templates/index.json templates/index.context.thailand.json
git commit -m "feat: establish machine-first homepage hero"
```

---

### Task 3: Build compact capability and model comparison

**Files:**

- Create: `sections/maliev-machine-capability.liquid`
- Create: `sections/maliev-machine-models.liquid`
- Modify: `assets/maliev-machine-home.css`
- Modify: `scripts/verify-homepage.mjs`
- Modify: `templates/index.json`
- Modify: `templates/index.context.thailand.json`

**Interfaces:**

- Consumes shared `mm-*` primitives from Task 2.
- Produces the `#machine-models` anchor and `model` block contract with `product`, `title`, `shot_size`, `best_for`, `spec_1`, `spec_2`, `spec_3`, media, detail link, and specification link settings.

- [ ] **Step 1: Create the capability section**

Implement `maliev-machine-capability.liquid` as one media/text chapter followed by a three-item qualitative economics row. The section schema contains image/image URL/alt, eyebrow, heading, text, and up to three `advantage` blocks with `number`, `title`, and `text`.

Use these English blocks in `index.json`:

```json
{
  "access": { "number": "01", "title": "Bring production closer", "text": "Run prototypes and small batches where your product team already works." },
  "investment": { "number": "02", "title": "Start with less overhead", "text": "A compact pneumatic platform lowers the equipment barrier compared with conventional industrial installations." },
  "support": { "number": "03", "title": "Build with local guidance", "text": "Plan the machine, mold, material, and replacement parts with the team that makes the equipment." }
}
```

Use equivalent natural Thai copy in the market context, preserving the same block IDs.

- [ ] **Step 2: Create the non-carousel model comparison**

Implement `maliev-machine-models.liquid` with `id="machine-models"`, one section heading, and a semantic `<ul>` of exactly two model blocks. Each card resolves an image in this order: image picker, product featured image, image URL, theme asset name. It renders a product-derived price only when a product is selected and `show_price` is true.

Use this accessible spec list shape:

```liquid
<ul class="mm-model__specs" aria-label="{{ block.settings.title | escape }} specifications">
  {%- for index in (1..3) -%}
    {%- assign key = 'spec_' | append: index -%}
    {%- if block.settings[key] != blank -%}<li>{{ block.settings[key] | escape }}</li>{%- endif -%}
  {%- endfor -%}
</ul>
```

English model block data:

```json
{
  "model_30g": {
    "title": "MALIEV 30g",
    "shot_size": "Up to 30g per shot",
    "best_for": "A compact starting point for prototypes, trials, and smaller parts.",
    "spec_1": "Dual PID-controlled heating zones",
    "spec_2": "Compact pneumatic architecture",
    "spec_3": "Air compressor required",
    "detail_label": "View 30g machine",
    "detail_link": "/products/pneumatic-injection-molding-machine"
  },
  "model_50g": {
    "title": "MALIEV 50g",
    "shot_size": "Up to 50g per shot",
    "best_for": "More shot capacity for larger parts, thicker sections, and expanded tooling plans.",
    "spec_1": "Steel melt zone",
    "spec_2": "2 × 220V 350W heater bands",
    "spec_3": "Maximum mold size 240 × 240 × 100mm",
    "detail_label": "View 50g machine",
    "detail_link": "/products/pneumatic-injection-molding-machine-50g",
    "asset_name": "machine-portrait-50g-front-studio.png"
  }
}
```

Extend `scripts/verify-homepage.mjs` after the hero assertions with:

```js
assert(home.sections.machine_models.type === 'maliev-machine-models', 'Machine models section is missing.');
assert(home.sections.machine_models.blocks.model_30g, '30g model block is missing.');
assert(home.sections.machine_models.blocks.model_50g, '50g model block is missing.');
```

- [ ] **Step 3: Add responsive media and comparison styles**

Add `.mm-capability`, `.mm-advantages`, `.mm-model-grid`, `.mm-model`, and `.mm-model__specs` rules. Desktop uses balanced media/text and two equal model columns. Below `750px`, every unit stacks vertically, the model media uses a consistent aspect ratio, and no horizontal scroll is introduced.

- [ ] **Step 4: Verify and commit**

Run: `npm run verify`

Expected: structural verifier and Theme Check pass at error level.

```powershell
git add sections/maliev-machine-capability.liquid sections/maliev-machine-models.liquid assets/maliev-machine-home.css scripts/verify-homepage.mjs templates/index.json templates/index.context.thailand.json
git commit -m "feat: compare MALIEV machine capability"
```

---

### Task 4: Build engineering, support, and mold-assistance chapters

**Files:**

- Create: `sections/maliev-machine-engineering.liquid`
- Create: `sections/maliev-machine-support.liquid`
- Modify: `assets/maliev-machine-home.css`
- Modify: `scripts/verify-homepage.mjs`
- Modify: `templates/index.json`
- Modify: `templates/index.context.thailand.json`

**Interfaces:**

- Consumes shared media resolution and `mm-*` classes.
- Produces a `feature` block contract for engineering details, a `commitment` block contract for trust claims, and a `process` block contract for the mold path.

- [ ] **Step 1: Implement the engineering chapter**

Create a two-column section with sticky media only above `990px`; keep the content in normal DOM order. Use a controller-detail image picker and URL fallback. Render up to four feature blocks as semantic list items.

English feature copy:

- `Straightforward controls` — `Two heating zones keep the operating information clear and close to the machine.`
- `Serviceable construction` — `The open pneumatic architecture keeps key components visible and accessible.`
- `Parts you can source locally` — `Replacement components are available directly from MALIEV.`
- `Guidance from the builder` — `Setup and maintenance questions go to the team that manufactures the machine.`

- [ ] **Step 2: Implement local support and mold assistance**

Create `maliev-machine-support.liquid` with a light trust chapter and a separate three-step mold path. The schema includes explicit `warranty_text`, `parts_text`, `mold_heading`, `mold_text`, `mold_cta_label`, and `mold_cta_link` settings so the structural verifier can inspect the claims.

Required English settings:

```json
{
  "heading": "Made here. Supported here.",
  "text": "MALIEV designs and manufactures the machines in-house in Thailand, so support stays close to the people who know the equipment.",
  "warranty_text": "Every machine includes a one-year warranty.",
  "parts_text": "Replacement parts are available directly from MALIEV.",
  "mold_heading": "From part idea to production setup.",
  "mold_text": "We can help plan and make molds for MALIEV machines without exposing customer tooling or product IP.",
  "mold_cta_label": "Discuss your mold project",
  "mold_cta_link": "/pages/contact?inquiry=mold#ContactForm"
}
```

Extend `scripts/verify-homepage.mjs` with:

```js
assert(home.sections.machine_support.type === 'maliev-machine-support', 'Machine support section is missing.');
assert(home.sections.machine_support.settings.warranty_text.includes('one-year'), 'Warranty commitment is missing.');
assert(home.sections.machine_support.settings.parts_text.length > 0, 'Replacement-parts commitment is missing.');
assert(home.sections.machine_support.settings.mold_cta_link.includes('inquiry=mold'), 'Mold CTA must label the inquiry.');
```

Process blocks are `Share the requirement`, `Review the production fit`, and `Develop the mold and setup`, with concise explanatory text. Add equivalent Thai overrides using the same IDs.

- [ ] **Step 3: Add sticky, trust, and process styles**

Add desktop `position: sticky` only to the engineering media wrapper with a safe header offset. Disable sticky positioning below `990px` and under reduced motion. Style commitments as fine-rule rows and the mold process as three numbered columns that stack on mobile.

- [ ] **Step 4: Verify and commit**

Run: `npm run verify`

Expected: structural verifier and Theme Check pass at error level.

```powershell
git add sections/maliev-machine-engineering.liquid sections/maliev-machine-support.liquid assets/maliev-machine-home.css scripts/verify-homepage.mjs templates/index.json templates/index.context.thailand.json
git commit -m "feat: explain local machine support"
```

---

### Task 5: Add the conversion close and secondary MALIEV discovery

**Files:**

- Create: `sections/maliev-machine-conversion.liquid`
- Create: `sections/maliev-more-from-maliev.liquid`
- Modify: `assets/maliev-machine-home.css`
- Modify: `scripts/verify-homepage.mjs`
- Modify: `templates/index.json`
- Modify: `templates/index.context.thailand.json`

**Interfaces:**

- Consumes the shared button and section-heading primitives.
- Produces final primary/secondary/LINE CTA settings and `resource` blocks for secondary discovery.

- [ ] **Step 1: Implement the final decision section**

Create a centered conversion section with heading `See what the right machine can make possible.`, primary demo link `/pages/contact?inquiry=demo#ContactForm`, secondary quote link `/pages/contact?inquiry=quote#ContactForm`, and tertiary LINE link `https://line.me/R/ti/p/@maliev`. External LINE opens in a new tab with `rel="noopener"`; contact links stay in the same tab.

- [ ] **Step 2: Implement More from MALIEV**

Create a compact editorial list of up to four `resource` blocks. Each block supports eyebrow, title, text, link label/link, image picker, image URL, and alt text. Use these entries:

- Mesh Splitter — `/tools/mesh-splitter`
- SimMount hardware — `/collections/sim-racing-solutions`
- 3D-printed products — `/collections/3d-printed-products`
- Guides and workshop resources — `/blogs/news`

Keep the section after the conversion close and visually quieter than every machine chapter.

Extend `scripts/verify-homepage.mjs` with the final section-type and Thai conversion assertions:

```js
assert(home.sections.machine_capability.type === 'maliev-machine-capability', 'Machine capability section is missing.');
assert(home.sections.machine_engineering.type === 'maliev-machine-engineering', 'Machine engineering section is missing.');
assert(home.sections.machine_conversion.type === 'maliev-machine-conversion', 'Machine conversion section is missing.');
assert(home.sections.more_from_maliev.type === 'maliev-more-from-maliev', 'More from MALIEV section is missing.');
assert(thailand.sections.machine_conversion.settings.heading.length > 0, 'Thai conversion override is missing.');
```

- [ ] **Step 3: Add conversion and editorial-resource styles**

Use a near-black conversion surface with AA-compliant white text and blue primary action. Resource cards use borders and type hierarchy rather than heavy shadows. At mobile widths, stack CTAs and resources with at least `4.4rem` interactive height.

- [ ] **Step 4: Verify and commit**

Run: `npm run verify`

Expected: structural verifier and Theme Check pass at error level.

```powershell
git add sections/maliev-machine-conversion.liquid sections/maliev-more-from-maliev.liquid assets/maliev-machine-home.css scripts/verify-homepage.mjs templates/index.json templates/index.context.thailand.json
git commit -m "feat: focus homepage conversion journey"
```

---

### Task 6: Distinguish demonstration, quotation, and mold inquiries

**Files:**

- Create: `assets/maliev-contact-inquiry.js`
- Modify: `sections/contact-form.liquid`
- Modify: `locales/en.default.json`
- Modify: `locales/th.json`

**Interfaces:**

- Consumes query values `demo`, `quote`, and `mold`.
- Produces a Shopify contact field named `contact[Inquiry type]` with the same values and a blank default.

- [ ] **Step 1: Add localized inquiry labels**

Under `templates.contact.form` add English keys:

```json
"inquiry": "What can we help with?",
"inquiry_select": "Select an inquiry type",
"inquiry_demo": "Schedule a machine demonstration",
"inquiry_quote": "Request a machine quotation",
"inquiry_mold": "Discuss a mold project"
```

Add Thai equivalents:

```json
"inquiry": "ต้องการให้เราช่วยเรื่องใด?",
"inquiry_select": "เลือกประเภทการติดต่อ",
"inquiry_demo": "นัดชมการสาธิตเครื่อง",
"inquiry_quote": "ขอใบเสนอราคาเครื่อง",
"inquiry_mold": "ปรึกษาโครงการแม่พิมพ์"
```

- [ ] **Step 2: Add a no-JavaScript-safe selector**

Insert before the contact message field:

```liquid
<div class="field">
  <select class="select__select" id="ContactForm-inquiry" name="contact[Inquiry type]" data-contact-inquiry>
    <option value="">{{ 'templates.contact.form.inquiry_select' | t }}</option>
    <option value="demo">{{ 'templates.contact.form.inquiry_demo' | t }}</option>
    <option value="quote">{{ 'templates.contact.form.inquiry_quote' | t }}</option>
    <option value="mold">{{ 'templates.contact.form.inquiry_mold' | t }}</option>
  </select>
  <label class="field__label" for="ContactForm-inquiry">{{ 'templates.contact.form.inquiry' | t }}</label>
</div>
```

Load `maliev-contact-inquiry.js` with `defer` after the stylesheet tag.

- [ ] **Step 3: Implement allowlisted query preselection**

Create `assets/maliev-contact-inquiry.js`:

```js
(() => {
  const select = document.querySelector('[data-contact-inquiry]');
  if (!select) return;
  const inquiry = new URLSearchParams(window.location.search).get('inquiry');
  if (!['demo', 'quote', 'mold'].includes(inquiry)) return;
  select.value = inquiry;
})();
```

- [ ] **Step 4: Verify and commit**

Run: `npm run verify`

Expected: structural verifier and Theme Check pass at error level.

```powershell
git add assets/maliev-contact-inquiry.js sections/contact-form.liquid locales/en.default.json locales/th.json
git commit -m "feat: classify machine inquiries"
```

---

### Task 7: Perform browser-first responsive and accessibility QA

**Files:**

- Modify as evidence requires: `assets/maliev-machine-home.css`, `assets/maliev-machine-home.js`, and affected `sections/maliev-machine-*.liquid` files.

**Interfaces:**

- Consumes a Shopify development-theme URL from `npm run dev`.
- Produces verified desktop/mobile homepage and contact journeys without console errors or overflow.

- [ ] **Step 1: Start the development theme**

Run: `npm run dev`

Expected: Shopify CLI prints a temporary development-theme preview URL. If authentication or network access blocks startup, record the exact output and continue with static validation without claiming browser completion.

- [ ] **Step 2: Verify the desktop journey at 1440 × 1000**

Check in order:

1. Hero heading and both machine identities are visible in the opening viewport.
2. Demo is visually primary and quote secondary.
3. Compact capability, economics, model comparison, engineering, support, mold path, conversion, and More from MALIEV appear in the approved order.
4. All contact, product, LINE, resource, and specification links resolve to their intended destination.
5. Sticky engineering media never overlaps the header or following section.
6. Browser console contains no new error.

- [ ] **Step 3: Verify mobile at 390 × 844 and 320 × 800**

Check copy/media order, full-width CTA behavior, stacked model comparison, touch-target size, no fixed element covering content, and `document.documentElement.scrollWidth === document.documentElement.clientWidth`.

- [ ] **Step 4: Verify keyboard and reduced motion**

Tab through all interactive elements, confirm visible focus and logical order, enable reduced motion, reload, and confirm all content is immediately visible with no transform or sticky-motion dependency.

- [ ] **Step 5: Verify contact routing**

Open the demo, quote, and mold links. Confirm the selector preselects `demo`, `quote`, and `mold` respectively. Remove JavaScript and confirm the selector remains manually usable.

- [ ] **Step 6: Smoke-test unaffected storefront routes**

At desktop and mobile widths, open one representative route for each required template class: 30g product, 50g product, machine collection, blog, article, search, cart, contact, policy, and 404. Confirm the namespaced `mm-*` CSS does not alter their layout, focus remains visible, and no horizontal overflow or new console error appears.

- [ ] **Step 7: Fix discovered issues and rerun gates**

Run: `npm run verify`

Expected: `Homepage structure verified.` and Theme Check exit `0` with no new errors.

- [ ] **Step 8: Commit QA fixes if files changed**

```powershell
git add assets/maliev-machine-home.css assets/maliev-machine-home.js sections/maliev-machine-*.liquid
git commit -m "fix: polish machine homepage responsiveness"
```

Skip this commit only when browser QA requires no file changes.

---

### Task 8: Complete the requirement-by-requirement audit

**Files:**

- Inspect: `docs/superpowers/specs/2026-07-17-machine-first-homepage-design.md`
- Inspect: all files changed by Tasks 1–7.

**Interfaces:**

- Produces final evidence that every specification requirement is implemented or an explicit blocker report that keeps the goal active.

- [ ] **Step 1: Check specification coverage**

Confirm authoritative evidence for all nine narrative chapters, CTA hierarchy, both models, warranty, parts, mold assistance, Thai manufacturing, secondary product demotion, Theme Editor editability, image replacement, accessibility, responsive behavior, reduced motion, and no-JavaScript readability.

- [ ] **Step 2: Check repository state and commit boundaries**

Run:

```powershell
git status --short --branch
git log --oneline --decorate -8
git diff main...HEAD --stat
```

Expected: clean worktree and logically separated documentation, homepage, contact-routing, and QA commits.

- [ ] **Step 3: Run the final verification gate**

Run: `npm run verify`

Expected: structural verifier passes and Theme Check exits `0`; compare warning count with the recorded 76-warning baseline and investigate any increase.

- [ ] **Step 4: Record final limitations honestly**

If final Blender exports are not yet available, state that accurate existing renders are active temporary assets and Theme Editor media settings are ready for replacement. Do not claim production browser verification if a Shopify preview URL was unavailable.
