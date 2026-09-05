# PIMM Unified Product Story Replacement Design

**Date:** 2026-08-31

**Status:** Owner-approved direction; written specification pending owner review

**Scope:** Local Shopify development theme only

## Objective

Replace the current unified PIMM configurator presentation rather than restyling it. The selected 30G or 50G variant must drive a complete, professionally composed product story using the purpose-made asset family already produced for that model. The machine must remain large, correctly proportioned, visibly grounded, and useful as product evidence at every supported viewport.

The replacement removes the old engineering bento, generic tooling split, workshop editorial, dark editorial, and undersized overview compositions. It preserves the product, variant, price, qualification, localization, accessibility, and Shopify Theme Editor contracts.

## Success criteria

- The selected model controls the whole page story, not only labels inside a shared old layout.
- The 30G story uses the governed `pimm30-*` production media already built for the 30G product page.
- The 50G story uses the six `pimm50-light-studio-*` production images already built for the 50G product page.
- Full-machine views are visually dominant and retain their complete machine bounds.
- Every full-machine view meets a visible ground-contact acceptance check: the lowest foot pixels sit on the stage baseline with no unexplained gap.
- Detail images are used only for the feature they were framed to explain and are never stretched into generic wide backgrounds.
- The page uses normal document flow, intrinsic aspect ratios, and `object-fit: contain`; it does not crop, overlap, or absolutely position product media.
- All obsolete unified and editorial storefront renders, manifests, runtime references, and tests are removed.
- Both models pass English and Thai desktop, tablet, mobile, short/tall viewport, reduced-motion, keyboard, 200% zoom, and overflow validation.

## Non-goals

- Do not produce another visual refresh of the existing bento/editorial layout.
- Do not generate replacement imagery when the already-produced model asset families satisfy the approved composition.
- Do not change product IDs, variant IDs, prices, deposit rules, availability, metafield schemas, or catalog structure.
- Do not merge, push, deploy, publish, or modify the production theme.
- Do not remove historical documentation or the governed Blender production toolchain merely because its prior storefront derivatives are retired.

## Root cause and replacement boundary

The current `product.pimm-configurator` template points at a parallel set of eight `pimm-machine-*` renders. Its section then adds four `pimm-editorial-*` images through an editorial-chapter snippet. Those assets and compositions are independent of the purpose-made 30G and 50G pages, so making their copy variant-aware left the wrong presentation intact.

The correction is an asset-authority and page-architecture migration:

1. Keep one unified product and one selected-model controller.
2. Replace the current shared presentation with model-specific story content.
3. Reuse the already-produced 30G and 50G production media.
4. Retire every storefront derivative owned exclusively by the old unified/editorial presentation.

## Selected-model page architecture

### Shared decision header

The page begins with one restrained product-introduction surface containing:

- one H1 for the PIMM family;
- the accessible 30G/50G radio selector;
- selected-model positioning and verified commercial facts;
- a dominant selected-model hero;
- the demo-session action followed by the configuration or qualification action.

The hero uses a pale MALIEV studio canvas. The image box derives from the asset's intrinsic ratio rather than a fixed crop. The machine is sized by its useful opaque bounds and bottom-aligned to a shared ground baseline. Empty transparent pixels must not make the product appear artificially small.

### 30G story

The selected 30G page adapts the proven normal-scroll 30G presentation and its latest production assets:

- contained hero: `pimm30-v13-hero-desktop-contained.webp` and its mobile counterpart;
- shot-capacity evidence: `pimm30-capacity-three-cube-*`;
- temperature-control evidence: `pimm30-temperature-controller-*`;
- cylinder evidence: the latest `pimm30-v11-cylinder-*` family;
- direct-operation evidence: `pimm30-direct-operation-*` with the `pimm30-v16-operation-*` posters;
- regulator evidence: `pimm30-v10-regulator-*`;
- fixture evidence: `pimm30-v15-fixture-*`;
- materials evidence: `pimm30-v10-capacity-*`;
- final configuration evidence: `pimm30-configuration-turntable-*`.

Animation is optional enhancement. Posters remain complete and authoritative under reduced motion or unsupported video.

### 50G story

The selected 50G page adapts the proven light-studio presentation and its six purpose-made images:

- `pimm50-light-studio-hero.webp`;
- `pimm50-light-studio-capacity.webp`;
- `pimm50-light-studio-melt-zone.webp`;
- `pimm50-light-studio-heating.webp`;
- `pimm50-light-studio-mold-space.webp`;
- `pimm50-light-studio-purchase.webp`.

Each image is paired with the product decision it was framed to support. The hero and purchase views remain full-machine compositions. Capacity, melt-zone, heating, and mold-space images remain feature-specific evidence and are not coerced into a one-size-fits-all card ratio.

### Story rhythm

Both models use a consistent MALIEV product-story grammar:

1. selected-model introduction and dominant hero;
2. compact verified specification summary;
3. alternating full-width evidence chapters with one image and one focused explanation;
4. ownership, support, documentation, and installation preparation;
5. selected-model qualification and demo/deposit controls.

This is normal-scroll editorial sequencing, not a dashboard and not a repeated bento grid. White and cool-gray surfaces may alternate, but dark scene bands and unrelated workshop backgrounds are removed.

## Variant and state contract

The existing `pimm-machine-product` custom element remains the only selected-model controller unless focused tests prove that a smaller replacement controller is safer. It must continue to:

- require and validate exactly one 30G and one 50G record;
- initialize from the Shopify variant and synchronize the URL variant parameter;
- update selected-model copy, specifications, price, availability, lead time, deposit state, media, and qualification content;
- expose only the selected story to assistive technology and tab order;
- eagerly load only the selected hero and defer inactive or below-fold media;
- fail closed when selected-model commerce or required media data is incomplete;
- switch without scroll jumps, stale captions, mixed-model media, or duplicate headings.

Model-specific story markup may be rendered in two panels for reliable Liquid composition, but the inactive panel must be hidden, inert, lazy, and excluded from accessibility APIs. Shared commerce controls remain singular.

## Responsive composition and grounding

### Desktop

- Use a wide but bounded content grid aligned with the storefront header.
- Hero copy and media may sit side by side, with the machine receiving the larger visual area.
- Full-machine imagery should occupy approximately 70–85% of its media stage's usable height after transparent-bound compensation.
- Evidence chapters alternate image/text placement without cropping either side.

### Tablet

- Stack the decision content and hero when a two-column composition would make the machine small.
- Preserve asset-specific aspect ratios and useful media height.
- Keep selector and primary action before the long story.

### Mobile and zoom

- Order: title, positioning, selector, selected hero, actions, specifications, story chapters, ownership, qualification.
- Use one column at narrow widths and at 200% zoom.
- Never use fixed viewport heights to force the machine into a slide.
- Preserve complete feet, focus outlines, captions, and controls with zero horizontal overflow.

### Ground-contact acceptance

CSS must establish one explicit stage baseline and bottom-align the useful rendered object to it. Asset padding must be measured rather than guessed; transparent margins may be compensated with an asset-specific object-position or wrapper contract. A render fails visual acceptance if a visible gap remains between any load-bearing foot and the stage, or if cropping conceals the contact point.

## Deprecated storefront removal

Delete the following 12 obsolete derivatives after the new page has no runtime references:

- `assets/pimm-machine-30g-hero-front.webp`
- `assets/pimm-machine-30g-overview-three-quarter.webp`
- `assets/pimm-machine-30g-engineering-controls.webp`
- `assets/pimm-machine-30g-tooling-front-detail.webp`
- `assets/pimm-machine-50g-hero-front.webp`
- `assets/pimm-machine-50g-overview-three-quarter.webp`
- `assets/pimm-machine-50g-engineering-controls.webp`
- `assets/pimm-machine-50g-tooling-front-detail.webp`
- `assets/pimm-editorial-30g-architectural-daylight.webp`
- `assets/pimm-editorial-30g-process-still-life.webp`
- `assets/pimm-editorial-50g-modern-workshop.webp`
- `assets/pimm-editorial-50g-dark-engineering.webp`

Also delete:

- `assets/pimm-unified-render-assets.v1.json`;
- `assets/pimm-editorial-render-assets.v1.json`;
- `snippets/pimm-editorial-chapters.liquid`;
- obsolete asset-only tests for those releases;
- old template defaults and browser assertions that name or require those assets.

Before committing deletion, run a repository-wide reference scan. Historical design documents and Blender source contracts may retain factual references to retired releases because they are not storefront runtime dependencies. They are not considered active renders and remain unless separately deprecated.

## Component boundaries

- `templates/product.pimm-configurator.json`: selected-model data and authoritative media declarations.
- `sections/maliev-pimm-machine-product.liquid`: shared header, story ordering, schema, app blocks, and commerce integration.
- New focused snippets or adapted existing model snippets: 30G story, 50G story, shared specifications, ownership, and qualification.
- `assets/maliev-pimm-machine.css`: unified responsive shell, asset-aware sizing, grounding, focus, and reduced-motion behavior.
- `assets/maliev-pimm-machine.js`: selected-model state only; no decorative scroll controller.
- Existing `maliev-pimm-30g*`, `maliev-pimm-50g*`, and `maliev-pimm-product-system.css` sources: reuse or extract proven presentation rules without duplicating conflicting cascades.
- Locale files: complete English and Thai copy with parity across required storefront locales.

Avoid a second controller, duplicated commerce forms, monolithic hardcoded markup, or late CSS overrides that conflict with the media contract.

## Accessibility and performance

- Preserve one H1, ordered H2 sections, landmarks, figures, useful alternative text, fieldset/legend semantics, and visible focus.
- Keep 44-pixel practical pointer targets and WCAG 2.2 AA contrast.
- Essential information may not depend on motion, hover, spatial position, or color alone.
- Explicit image dimensions or aspect ratios prevent layout shift.
- The selected hero is the only eager product image; inactive-model and below-fold assets are deferred.
- Videos use posters, no autoplay audio, and reduced-motion-safe static behavior.
- Do not add a frontend framework, WebGL, or a third-party runtime.

## Tests and validation

Implementation is complete only after all of the following pass:

1. Focused contract tests prove selected-model initialization, switching, URL synchronization, specifications, price, availability, deposit state, media identity, inactive-story accessibility, and invalid-payload failure behavior.
2. Asset tests prove that every active 30G and 50G file exists with expected media type and dimensions.
3. A negative repository scan proves no runtime, template, CSS, JavaScript, locale, or active test references any deleted `pimm-machine-*` or `pimm-editorial-*` derivative.
4. The affected build and `npm run verify` pass with zero errors.
5. Browser QA covers both models in English and Thai at 1440 x 900, 1280 x 800, 1024 x 768, 390 x 844, and 360 x 800.
6. Browser QA also covers a short desktop viewport, a tall mobile viewport, keyboard navigation, reduced motion, and 200% zoom.
7. Automated geometry checks report no horizontal overflow, product/text overlap, unexpected image crop, mixed-model media, or zero-sized visible content.
8. Screenshot review confirms large professional product sizing and visible foot-to-ground contact for every full-machine view.
9. The local preview is reloaded with a new cache-busting value and visually compared against this specification before completion is claimed.

## Commit and release boundary

Implementation should be split into coherent validated commits: contract and story migration, deprecated asset removal, and any necessary browser-validation correction. Documentation may remain a separate commit.

This specification authorizes local implementation and local validation only. It does not authorize pushing, merging, deploying, production theme changes, or catalog mutation.
