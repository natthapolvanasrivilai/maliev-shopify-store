# PIMM Dedicated Collection Experience Design

**Date:** 2026-09-01  
**Status:** Approved  
**Surface:** Injection molding machine collection  
**Aesthetic lane:** Precision industrial specimen sheet

## 1. Purpose

Replace the injection molding machine collection's generic Shopify collection layout with a dedicated, full-page comparison experience for the MALIEV PIMM 30G and 50G.

The page must make the two-machine decision legible without filters, sorting, pagination, or conventional product-grid furniture. It must preserve MALIEV's precision-workbench visual language while giving the machines a more dramatic, image-led presentation.

The page is a comparison and routing surface, not a second product configurator. Its primary outcomes are:

1. Help a buyer understand which machine fits their workshop.
2. Make price, availability, lead time, and technical differences explicit.
3. Route the buyer into the existing unified PIMM configurator with the chosen model preselected.

## 2. Existing boundaries

- The current collection uses `templates/collection.json` with `maliev-collection-hero` and `maliev-collection-grid`.
- The collection currently contains two legacy machine product cards.
- The authoritative machine experience is the unified PIMM product configurator, whose validated contract requires exactly two `Model` variants in the order `30G`, then `50G`.
- Authoritative machine facts come from variant data and metafields, including:
  - full machine price;
  - availability;
  - lead time;
  - shot capacity;
  - maximum melt temperature;
  - mold envelope;
  - maximum air pressure.
- Model photography is derived from the separate authoritative Blender masters `PIMM-30G-MASTER.blend` and `PIMM-50G-MASTER.blend`.
- The current header supports transparent overlay states and a solid white scrolled state. The dedicated collection must extend that behavior rather than introduce a second incompatible header system.

## 3. Chosen approach

Use an **industrial comparison dossier** layout.

At desktop and larger widths, the viewport is divided into:

- a left product stage occupying approximately 64-68% of the usable width;
- a right sticky dossier occupying approximately 32-36%.

The left stage contains two tall model cards displayed side by side. The right dossier updates to describe the active card. The 30G is active initially.

This approach was selected over separate scrolling showroom bays and a single-machine toggle because it preserves simultaneous comparison while still giving each model a large, purpose-rendered image.

## 4. Page architecture

Create a dedicated collection template and reusable section rather than conditionally overloading the generic collection grid.

The dedicated surface owns:

- the collection introduction;
- the paired machine cards;
- active-model state;
- the comparison dossier;
- localized copy;
- render-sequence playback;
- links into the canonical unified configurator.

The generic collection template remains unchanged for all other collections.

The dedicated section receives the canonical unified PIMM product as an explicit product setting. It resolves 30G and 50G by the `Model` option values, never by collection ordering, display title, product price, or hardcoded variant IDs.

If the canonical product or its exact two-variant contract is unavailable, the section must fail closed with an editor-visible configuration message and must not publish invented prices or specifications.

## 5. Visual composition

### 5.1 Opening viewport

- The collection artwork extends behind the header at the top of the page.
- The header is transparent while the page is at the opening position.
- After crossing a small scroll threshold, the header becomes solid white with its normal border and contrast treatment.
- The transition uses the existing restrained ease-in/out timing and must not flash or jump during restoration, resizing, or Shopify section reloads.

### 5.2 Product stage

The product stage is bright, high-contrast, and photographic. It avoids dashboard styling and generic rounded-card grids.

Each machine card contains:

- a dedicated Blender-rendered machine scene;
- model name and capacity designation;
- concise best-for statement;
- full machine price;
- availability and lead-time status;
- three high-value specification callouts;
- primary action to open the unified configurator;
- secondary affordance to make the model active in the dossier.

The cards use distinct scene art direction while preserving realistic materials and exact machine geometry. Backdrop, crop, lighting emphasis, and typographic composition may differ, but the machine itself must not be recolored or cosmetically altered.

Recommended visual distinction:

- **30G:** compact, closer framing with a cooler silver-blue studio field and emphasis on workshop footprint.
- **50G:** taller composition with a neutral graphite-to-silver field and emphasis on extended shot capacity.

The product image remains dominant. Text overlays occupy deliberate copy-safe regions and must never obscure controls, tooling, or the machine silhouette.

### 5.3 Hover elevation

At rest, cards remain visually grounded. Hover or keyboard focus produces one restrained elevation event:

- a small upward translation;
- a modest border/contrast change;
- a physically plausible soft shadow belonging to the card surface, not a fake machine shadow;
- no excessive scale jump, glow, or spring effect.

## 6. Blender render system

Each model receives its own purpose-specific render sequence. Homepage hero, homepage catalogue, product-story, and other existing images must not be reused.

Required sequence per model:

1. front hero frame;
2. left three-quarter frame;
3. front return frame;
4. right three-quarter frame;
5. front resting frame.

The sequence must be generated from the appropriate authoritative Blender master. It must not use CSS transforms, horizontal mirroring, perspective warping, layered cutouts, or artificial ground-shadow compositing.

Render requirements:

- identical camera target, focal length, exposure, lighting rig, output dimensions, and machine scale across a model's sequence;
- only the physical model staging/camera azimuth changes between angle frames;
- a physically rendered studio floor with an effectively infinite receiving surface;
- no clipped shadow catcher, hard compositing seam, or post-render fake floor;
- clear copy-safe region in the upper portion of each vertical card frame;
- lossless source PNG publication followed by optimized WebP storefront derivatives;
- render metadata and checksums recorded in a dedicated asset manifest;
- unique asset names and roles so no card frame silently aliases another storefront location.

The resting front frame is the eager/LCP candidate. Angle frames load after the resting frame and may be deferred until the card approaches the viewport.

## 7. Interaction model

### 7.1 Active model

- 30G is active on initial load.
- Pointer hover previews a model in the dossier.
- Keyboard focus previews a model in the dossier.
- Click or touch commits that model as active.
- Pointer exit restores the last committed model rather than unexpectedly switching to a different card.
- The active state is communicated visually and through `aria-current` or an equivalent accessible state.

### 7.2 Angle playback

- Hover or focus begins one short front-left-front-right-front sequence.
- Playback stops on the front frame.
- Repeated pointer movement must not create overlapping timers or uncontrolled loops.
- Touch activation plays at most one cycle.
- With `prefers-reduced-motion: reduce`, only the front frame is shown and elevation is reduced to a non-moving contrast change.
- With JavaScript unavailable or an angle frame missing, the front frame and all navigation remain fully functional.

### 7.3 Configurator routing

The primary action navigates to the canonical unified PIMM product URL with the selected variant encoded using Shopify's supported variant URL parameter. Variant IDs are resolved from the current product object at render time.

The destination configurator remains the only model-selection and detailed product-story surface.

## 8. Sticky comparison dossier

The right-hand dossier stays visible within the viewport on desktop without overlapping the header or footer.

It contains:

- active model label and one-sentence recommendation;
- full price, availability, and lead time;
- shot capacity;
- mold envelope;
- maximum melt temperature;
- maximum air pressure;
- a concise "choose this when" statement;
- a compact comparison against the other model;
- primary demo/configurator action;
- secondary support or factory-visit action when configured.

Specification values update atomically when the active model changes. Screen-reader announcements must be concise and must not repeat on pointer movement alone.

The dossier is not a modal, drawer, or popover. It remains part of the document flow and preserves access to both cards.

## 9. Responsive behavior

### Desktop and large tablet

- Two cards remain side by side in the left stage.
- Dossier remains sticky on the right.
- The complete opening composition fits without horizontal scrolling.

### Medium tablet

- Cards may remain side by side when each retains sufficient image width and readable type.
- Otherwise, cards stack above an inline dossier.
- Sticky positioning is removed before it can constrain content height or create nested scrolling.

### Mobile

Order:

1. concise collection introduction;
2. 30G card;
3. 50G card;
4. full comparison dossier;
5. final demo/support action.

Cards use a tall mobile crop rendered for the card, not a desktop crop forced through `object-fit`.

Touch targets are at least 44px, pricing remains visible without expanding content, and the page has zero horizontal overflow.

## 10. Typography and color

Preserve the existing MALIEV identity rather than introducing a new font family solely for this page.

- Display typography may use the existing machine/homepage display treatment for model identifiers and decisive headings.
- Body copy and specifications use the existing commerce typography for bilingual readability.
- Short technical labels may be uppercase, but body copy must not be all caps.
- Prices receive stronger hierarchy than compare-at or supporting metadata.
- Thai and English line lengths must be tested independently.

The palette stays within MALIEV black, white, cool canvas neutrals, and controlled instrumentation blue. Blue indicates selection and interactive state, not decoration.

## 11. Localization and content ownership

- All user-facing fixed copy is stored in locale keys with Thai and English parity.
- Product titles, availability, prices, and variant facts remain Shopify data.
- The section schema exposes only useful merchant controls, including the canonical PIMM product and optional support/factory-visit destinations.
- The implementation must preserve valid Shopify section schema and Theme Editor reload behavior.

## 12. Accessibility

- Cards and dossier controls are fully operable by keyboard.
- Focus indicators remain visible over both light and dark imagery.
- Hover is never the only way to reveal product facts or actions.
- Images have model- and angle-specific alt text; decorative transition frames may use empty alt text while the resting image supplies the accessible name.
- Live-region updates are limited to committed model changes.
- Color is not the sole active-state signal.
- Reduced-motion behavior is mandatory.
- The document retains one logical `h1` and a sequential heading hierarchy.

## 13. Performance

- The 30G resting frame is preloaded or given high fetch priority only when it is the actual opening LCP candidate.
- Other resting and animation frames use responsive image sources and deferred loading.
- Angle playback uses decoded images to avoid blank flashes.
- JavaScript is scoped to the dedicated section and must clean up listeners and timers on Shopify section unload.
- No video is required; a short deterministic still sequence provides the requested motion with predictable loading and accessible fallback.

## 14. SEO and structured data

- Preserve collection canonical behavior and a valid `CollectionPage`/`ItemList` representation.
- The structured list contains the canonical unified product/model destinations rather than presenting stale legacy product contracts.
- Page title and description remain localized and collection-specific.
- Visual replacement of the generic grid must not remove crawlable model names, prices, or destination links.

## 15. Validation gates

Implementation is complete only after:

1. Blender sequence outputs pass asset provenance, dimension, uniqueness, and shadow-safety checks.
2. Dedicated section Liquid and schema pass Theme Check.
3. JavaScript state and playback behavior have focused automated tests.
4. Locale keys exist in Thai and English and locale JSON parses successfully.
5. Unified product contract resolution is tested for valid, missing, and malformed data.
6. Desktop and mobile browser validation covers:
   - transparent-to-solid header transition;
   - 30G/50G active state;
   - hover, keyboard, touch, and reduced-motion behavior;
   - correct model-specific configurator URLs;
   - responsive stacking and sticky release;
   - no horizontal overflow;
   - no reused image roles;
   - no clipped or artificial machine shadows.
7. `npm run verify` passes before the implementation commits are created.

## 16. Deliberate exclusions

- Do not change the unified product configurator's information architecture.
- Do not migrate or delete legacy product records as part of this page redesign.
- Do not apply this layout to other Shopify collections.
- Do not use WebGL or client-side 3D model loading.
- Do not push, deploy, assign the template in production, or alter merchant settings without separate authorization.

