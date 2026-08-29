# Unified PIMM Product Configurator Design

Date: 2026-08-26
Status: approved design, implementation not started

## Purpose

Replace the separate PIMM 30G and PIMM 50G storefront presentations with one product page backed by one Shopify product. The product has one customer-facing option, `Model`, with exactly two variants: `30G` and `50G`.

The page must help a Thai workshop buyer understand practical fit, choose a model, inspect credible engineering evidence, and contact the factory. A demo session remains the primary conversion. The selected model's 50% production deposit remains a secondary purchase path after qualification.

The design adds one purposeful bento section to an otherwise spacious product presentation. The whole page must not become a tile grid.

## Goals

- Present 30G and 50G as configurations of one coherent machine family.
- Let the buyer switch model without navigating to another product page.
- Update model imagery, verified specifications, price, availability, lead time and cart variant together.
- Use one asymmetric engineering bento section to compress the most important technical facts.
- Replace legacy page renders with governed, photoreal static assets from the approved Blender masters.
- Preserve Shopify-native variant, pricing, availability, cart, localization and Theme Editor behavior.
- Develop and validate against a duplicated Draft product without exposing it on any production sales channel.

## Non-goals

- No machine animation, plunger motion or controller-value animation.
- No accessory, voltage, mold or package configuration in version one.
- No production theme deployment, product publication, redirects or retirement of the two existing products.
- No generative image editing, AI upscaling, cloud enhancement or product repainting.
- No change to authoritative STEP geometry, approved master materials, decals or controller values.

## Product and publication model

Duplicate the current machine product as a new Shopify product with Draft status. Shopify documents that a duplicate can be created as Draft and previewed from Admin. The duplicate must remain unpublished from Online Store and every other sales channel throughout development.

The Draft product contract is:

- Product purpose: unified PIMM machine-family presentation and qualified deposit.
- Option name: `Model`.
- Variant values: exactly `30G` and `50G`.
- Variant price: the payable 50% production deposit for that model.
- Base full machine price: a verified Admin-currency variant money metafield that must equal exactly twice the Admin variant deposit and acts as qualification evidence.
- Storefront full machine price: market-aware presentment calculated as exactly twice Shopify's contextual `variant.price`, so taxes and market adjustments remain consistent with the displayed deposit rather than formatting the base metafield directly.
- Availability and inventory: Shopify variant state, never hardcoded theme copy.
- Lead time: verified variant metafield.
- Technical specification payload: exact versioned variant JSON metafield.

The technical specification JSON has this stable shape:

```json
{
  "schema_version": 1,
  "model": "30G",
  "shot_capacity_g": 30,
  "max_melt_temperature_c": 300,
  "mold_envelope_mm": {
    "width": 0,
    "height": 0,
    "depth": 0
  },
  "max_air_pressure_mpa": 0.8
}
```

The zero mold-envelope values above illustrate the wire shape only and must never be published as product data. Implementation must populate every numeric value from owner-approved machine documentation. A missing, malformed or model-mismatched payload fails closed.

The two existing product records remain unchanged during development. Historical orders remain attached to their original records. Product consolidation, redirects, canonical URLs and retirement of the old records require a later explicit production migration approval.

## Page architecture

### 1. Product hero and configurator

Use a conventional two-column product hero on desktop and a composed single-column hero on mobile. It contains:

- product family name and concise workshop-fit statement;
- the selected model's approved straight-on render;
- accessible 30G and 50G radio controls;
- market-aware full machine price, contextual 50% deposit, availability and lead time;
- primary `Book a demo session` action;
- secondary deposit action.

The machine remains the dominant visual event. The configurator is compact and task-focused; it is not a dashboard or a multi-step wizard.

### 2. Model-fit narrative

Follow the hero with an open, editorial section using a large three-quarter render and plain-language guidance about choosing from the intended part, material, mold and workshop constraints. This section is not card-based.

### 3. Engineering at a glance bento

Use one asymmetric bento cluster after the opening narrative. It contains:

- one dominant engineering-detail image;
- shot capacity;
- maximum melt temperature;
- mold envelope;
- pneumatic pressure and control context.

Every tile updates with the selected model. The cluster uses flat Canvas and Surface tonal steps, at most 10px corners, no broad decorative shadows and no nested cards. On mobile, the dominant image appears first and facts become a stable two-column or single-column reading order; masonry and horizontal overflow are prohibited.

### 4. Operation, tooling and construction

Return to spacious full-width or split narrative sections. Use the tooling-zone render to explain nozzle, platen and mold fit. Explain operation only through verified static facts. Do not imply unapproved travel, timing, sequence or controller behavior.

### 5. Ownership

Explain Thai manufacturing, factory demonstration, installation, replacement parts, support, warranty and documents. This remains a calm content section rather than a second bento grid.

### 6. Purchase qualification

Repeat the selected model, full price, deposit, availability and lead time near the end. Keep `Book a demo session` primary. The deposit action remains secondary and must clearly state that it is a 50% production deposit after qualification.

## Storefront component architecture

Create a dedicated template and reusable machine-presentation section rather than extending either legacy monolith:

- `templates/product.pimm-configurator.json`
- `sections/maliev-pimm-machine-product.liquid`
- focused snippets for model selection, engineering bento, purchase qualification and ownership content;
- `assets/maliev-pimm-machine.css`
- `assets/maliev-pimm-machine.js`
- English and Thai locale entries;
- focused Node contract and browser tests.

The section schema owns merchant-editable render assignments and links. Shopify owns price, variant availability and cart behavior. Verified specifications remain variant metafields, not duplicated theme settings.

Liquid serializes an exact, escaped variant-state payload for the two Model variants. Each model radio uses the real Shopify variant ID as its submitted `id` value, so the product form remains truthful without JavaScript. The JavaScript controller has one responsibility: apply a selected variant state to the existing semantic document. Selection updates:

- checked radio and hidden product-form variant ID;
- selected media and alt text;
- specification values;
- market-aware full price, contextual deposit price, availability and lead time;
- deposit-button enabled state;
- URL `variant` parameter;
- polite live-region status.

Content is fully visible before enhancement. Without JavaScript, the native radio and product form submit the chosen variant ID; enhanced price and media swapping are not required for purchase correctness. JavaScript does not invent prices, specifications or availability.

## Failure behavior

- If a model variant is absent, do not render its selector.
- If the selected variant lacks a valid specification contract, retain the factory-visit action, mark technical data unavailable and disable deposit purchase.
- If a model-specific image is missing, use the approved selected-model front hero; never borrow the other model's image.
- If availability changes, use Shopify's current variant state and announce the update.
- If cart submission fails, preserve the selected configuration, show an associated error and keep the factory-contact path available.
- If JavaScript fails, the server-rendered selected variant remains truthful and operable.

## Accessibility and localization

- Model choices are a real `fieldset` and `legend` with radio inputs.
- Touch targets are at least 44px where practical.
- Selected-state information does not rely on color alone.
- Variant changes preserve focus and announce price and availability without moving the user.
- Focus uses the existing 3px Focus Yellow system.
- Thai and English strings use locale keys and tolerate full native wording without truncation.
- Headings maintain a logical hierarchy; bento facts use semantic definition lists where appropriate.
- Reduced-motion mode changes selected content instantly without transforms or delayed visibility.

## Render asset programme

The canonical workspace remains:

`M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders`

The authoritative masters remain `PIMM-30G-MASTER.blend`, `PIMM-50G-MASTER.blend` and `PIMM-MATERIAL-LIBRARY.blend`. Render scenes link `PIMM_PUBLISHED`; they never copy product geometry or localize approved product materials.

Reuse the two approved straight-on hero finals. Create three new governed still scenes per model:

| Machine | Scene | Purpose | Camera | Native output |
| --- | --- | --- | --- | --- |
| 30G | `pimm-30g--overview--three-quarter.blend` | model-fit narrative | 85mm | 2400 x 1800 |
| 30G | `pimm-30g--engineering--controls.blend` | bento dominant detail | 135mm | 2400 x 1800 |
| 30G | `pimm-30g--tooling--front-detail.blend` | tooling chapter | 135mm | 2400 x 1800 |
| 50G | `pimm-50g--overview--three-quarter.blend` | model-fit narrative | 85mm | 2400 x 1800 |
| 50G | `pimm-50g--engineering--controls.blend` | bento dominant detail | 135mm | 2400 x 1800 |
| 50G | `pimm-50g--tooling--front-detail.blend` | tooling chapter | 135mm | 2400 x 1800 |

Each scene gets a matching JSON scene contract, one shot per `.blend`, a low-resolution immutable proof, labelled contact sheet and exact approval record. Separate mobile camera scenes are created only when an approved native composition cannot be cropped without losing decision-relevant geometry.

## Photoreal rendering contract

Preserve the approved studio baseline:

- Blender 5.2 Cycles;
- adaptive sampling with 128–256 maximum final samples;
- OpenImageDenoise;
- 36mm sensor;
- 85mm at f/11 for complete-machine views;
- 135mm at approximately f/8–f/11 for component groups;
- pinned `studio_kontrast_04_4k.exr` HDRI at strength `0.5` and rotation `0`;
- AgX Medium High Contrast, exposure `0`, gamma `1`;
- 5500K broad key and fill, dedicated lower bounce and controlled reflection strips;
- physical transparent shadow catcher;
- float EXR master plus transparent PNG and WebP derivatives.

The detail cameras use realistic working distance and restrained depth of field. The entire decision-relevant component group must remain acceptably sharp.

Every proof must show:

- no clipped stainless highlights or featureless white aluminum;
- visible separation in black oxide and black powder coat;
- balanced light from top cylinder through base plate and feet;
- broad physically plausible metal reflections;
- readable pressure gauge, regulator markings, controller segments and AirTAC artwork in labelled 100% crops;
- complete contact shadow with no floating feet, dark contact bar, catcher boundary or clipped tail;
- clean silhouette on white, checker and dark composites;
- unchanged master, material-library, scene and dependency fingerprints.

Any geometry, material, camera, light, world, compositor or output-setting change invalidates proof approval. Native final rendering starts only after owner approval of the exact proof generation.

## Asset delivery and performance

Storefront media comes only from approved native final releases. Generate responsive WebP derivatives without AI scaling or repainting. Preserve source aspect ratio and provide model-specific alt text.

- Eager-load only the initially selected hero and give it high fetch priority.
- Lazy-load below-fold narrative and bento imagery.
- Do not eagerly download both machines' full media sets.
- Preload or decode the alternate selected-model hero only after initial critical work or direct user intent.
- Avoid cumulative layout shift with explicit dimensions or aspect ratios.
- Use a real opacity crossfade of at most 180ms for model media. During overlap the outgoing model is immediately `aria-hidden` and pointer-inert, cleanup is bounded, and rapid switching settles only the latest selection. Reduced motion swaps instantly.

## Validation

### Blender and publication gates

- Reopen and validate every authored scene independently.
- Validate exact master and material hashes, linked `PIMM_PUBLISHED`, scene-local ownership and output containment.
- Render composition and material proofs on white, checker and dark backgrounds.
- Inspect full compositions plus 100% artwork and material crops.
- Run the affected Blender/Python regression suites and immutable fingerprint checks.

### Theme and interaction gates

- Build the affected theme surface first through `npm run verify` and require zero Theme Check errors.
- Add focused contract tests for exact `Model` option values, variant payload shape, no hardcoded price/availability, CTA ordering and fail-closed behavior.
- Test JavaScript state changes, URL synchronization, live-region announcements and correct cart variant ID.
- Verify 30G and 50G at desktop, tablet and mobile widths in English and Thai.
- Verify keyboard-only operation, reduced motion, zoom, missing-media fallback and zero horizontal overflow from 320px upward.
- Confirm the development product remains Draft and unpublished after every external-state operation.

## Implementation and release boundaries

Implementation occurs on an isolated feature branch from local `main`. Do not disturb the active user checkout or unrelated untracked work. Commit coherent validated repository slices. Do not push, publish the Draft product, modify the live theme or deploy production without a later explicit authorization.

The eventual production migration is a separate operation. It must define final product handle, redirects, canonical behavior, publication ordering, old-product retirement, analytics continuity and rollback before any live write.
