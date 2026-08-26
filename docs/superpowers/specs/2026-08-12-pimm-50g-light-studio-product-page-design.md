# PIMM 50G Light Studio Product Page Design

Date: 2026-08-12

Status: Approved visual direction; implementation pending

Route: `/products/pneumatic-injection-molding-machine-50g`

## Objective

Replace the full-viewport Keynote story with a normally scrolling, premium product page tailored to the PIMM 50G. The page must feel like a clean industrial studio: authoritative machine scale, transparent Blender media, precise engineering evidence, and a demonstration-first purchase path.

This is not an imitation of an automotive brand. It adapts three useful patterns from premium automotive product pages:

- a decisive first product view;
- engineering stories organized around real assemblies and outcomes;
- media-led transitions that preserve direct configuration and enquiry actions.

## Audience and Conversion Goal

The primary audience is a Thai workshop owner, manufacturing engineer, educator, or small-production operator evaluating whether the 50G fits a specific mold, material, utility setup, and production workflow.

Primary conversion: book a factory visit or qualification conversation.

Secondary conversion: add the selected configuration to cart after qualification.

The page must answer, in this order:

1. What is the 50G and why is it different from the 30G?
2. What can it process and what workshop setup does it need?
3. How are the shot, heating, mold, and pneumatic systems engineered?
4. Which model is appropriate for the customer's part?
5. What does the configuration cost and what should happen next?

## Visual Direction

The physical scene is a precisely lit PIMM 50G in a bright MALIEV studio, inspected by a buyer under neutral workshop lighting. The page uses true white, cool neutral gray, MALIEV black, Signal Blue for actions, and controlled red only where heat or 50G differentiation requires emphasis.

The machine remains the dominant visual artifact. Decorative typography must never compete with it. Avoid giant watermarks, repeated eyebrow labels, identical metric cards, glass surfaces, faux automotive chrome, and dark cinematic chapters.

### Color Roles

- Canvas: true white or cool neutral white.
- Technical surface: cool gray with enough separation from white to define a new topic.
- Ink: MALIEV near-black.
- Body copy: contrast-safe neutral gray.
- Primary action: Signal Blue with white text.
- Thermal emphasis: restrained MALIEV red, limited to heat diagrams, readouts, or small technical details.
- Focus: Focus Yellow.

## Page Architecture

The page uses normal document flow. There is no `scroll-snap-type`, `scroll-snap-stop`, forced viewport-height chapter, or JS-controlled wheel navigation. Sections use content-driven heights and generous editorial spacing.

### 1. Light Studio Hero

A clean white hero presents the complete transparent 50G machine at authoritative scale. Desktop uses a 42/58 information-to-media split; mobile places the product media first and the decision content immediately below it.

Content:

- `PIMM 50G`
- concise proposition focused on larger shot capacity and reinforced heating hardware;
- 50 g shot, steel melt zone, 2 × 350 W heating, machine height;
- primary `Book a factory visit` action;
- secondary `Explore the engineering` anchor.

Motion:

- a short transparent Blender light-start sequence may play once when available;
- the sequence must finish on the exact same camera, scale, and machine position as the static alpha fallback;
- content remains visible without waiting for animation;
- reduced motion receives the final static frame.

### 2. Product Overview Strip

A compact, scannable technical band follows the hero. It consolidates the decision facts buyers otherwise have to remember across the page. It is not a grid of decorative cards; facts are separated by spacing and rules.

Required facts:

- maximum shot capacity;
- melt-zone material;
- heater configuration;
- mold envelope;
- made-to-order status and estimated lead time.

### 3. Capacity and Pneumatic Drive

An asymmetrical editorial section uses a complete or three-quarter alpha render with the larger cylinder and injection assembly prominent. Copy explains what 50 g capacity changes for part design without making unverifiable throughput claims.

A small CSS motion sequence may trace airflow or injection travel using line/opacity animation. It must not draw a fake component over the product or imply a physically incorrect stroke.

### 4. Steel Melt Zone

A neutral-gray section focuses on the steel melt-zone assembly. The alpha render remains complete enough to orient the customer, then a close-up provides material proof.

The section explains the concrete 30G-to-50G change and why repeated thermal cycling benefits from the steel construction. Red is allowed only as restrained heat-state emphasis.

### 5. Dual Heating System

The heating section combines an alpha close-up of the real controller assembly with a dedicated Blender animation showing both heating zones progressing independently. Controller digits must be authored in Blender and remain physically attached to the displays; HTML overlays are prohibited.

The animation must not change camera position, studio lighting, or controller geometry when it hands off to the static fallback.

### 6. Mold Workspace

A top-down or three-quarter alpha render focuses on the M10 grid and mold interface. CSS dimension lines may animate into place only after the product image is visible. Dimension annotations must be semantic text and must remain readable without animation.

### 7. 30G vs 50G Decision

A concise comparison presents both complete alpha machines on the same visual baseline. It avoids generic cards and clarifies the decision by part and setup:

- compact-shot work vs additional shot headroom;
- aluminum vs steel melt-zone construction where verified;
- heating configuration;
- mold and utility qualification;
- links to the 30G page and factory consultation.

### 8. Configuration and Purchase

The final section uses a large transparent 50G view beside a practical configuration panel in normal flow. The machine may run a single authored left-right Blender turntable preview, then stop on a clean three-quarter frame. If real rotational frames are unavailable, use a static render rather than a fake CSS rotator.

The panel contains:

- current variant and price;
- made-to-order status and estimated lead time;
- air, mold, heating, and support qualification summary;
- variant selector;
- primary factory-visit action;
- secondary Add to cart action.

Factory visit remains visually primary because this is a considered machine purchase.

## Media and Blender Requirements

All machine stills must use transparent alpha output. No baked white rectangles, additional CSS feather masks, side fades, or artificial CSS ground shadows may alter the render. Natural Blender contact shadows are allowed only when they fade fully inside the alpha canvas.

Required assets:

1. hero light-start animation and final alpha poster;
2. complete front three-quarter machine render;
3. capacity/pneumatic assembly render;
4. steel melt-zone close-up;
5. dual-heater Blender animation and final still;
6. mold-grid close-up;
7. matched-scale 30G and 50G comparison renders;
8. optional real turntable animation or authored frame sequence.

Every animated and static pair must share camera, projection, resolution, crop, object transforms, lighting, color management, and alpha treatment. No visual jump is acceptable at playback completion.

## CSS and Interaction Motion

Use motion to explain the machine, not decorate the page.

Allowed:

- slow media translation of at most 2–3% during normal scroll;
- opacity/clip reveals for annotations;
- animated dimension lines;
- controller status changes driven by Blender media;
- subtle button and anchor feedback;
- a sticky media column on selected desktop engineering sections when the adjacent copy is taller.

Prohibited:

- forced scroll progression;
- invisible-until-JS content;
- bounce or elastic easing;
- faux 3D transforms of a flat product image;
- looping autoplay that distracts from reading;
- animation that changes physical machine behavior.

All motion must respect `prefers-reduced-motion`. Static content and final media frames must be complete without JavaScript.

## Responsive Behavior

### Desktop, 1200 px and wider

- asymmetrical editorial compositions;
- large alpha product media with complete extents visible;
- selective sticky media for long engineering explanations;
- maximum readable copy width of approximately 65–70 characters.

### Tablet, 768–1199 px

- media and copy may remain side by side where both stay legible;
- otherwise use media-first stacked composition;
- no section depends on a fixed viewport height;
- purchase controls remain fully visible in normal flow.

### Mobile, below 768 px

- product media first, copy second;
- no decision copy is hidden to make a composition fit;
- alpha renders use `object-fit: contain` and preserve the entire intended product canvas;
- CTAs are at least 44 px high and become two columns only when both labels remain readable;
- normal scrolling must move proportionally through the page with no snap interception.

### Short Landscape

- use compact side-by-side compositions when useful;
- fall back to normal stacked flow when content needs more height;
- never compress essential text, forms, or buttons into one viewport.

## Accessibility and Performance

- Every meaningful render has accurate alt text; decorative motion is hidden from assistive technology.
- Headings form a logical single-H1 hierarchy.
- Body and control contrast meet WCAG AA.
- All controls expose a visible Focus Yellow focus state.
- Video does not block first contentful display and uses optimized WebM/MP4 sources where required by storefront support.
- Below-fold images and video are lazy loaded; the hero poster and final alpha still are prioritized.
- The page must have zero horizontal document overflow at 320 px and above.
- The Shopify product form remains native and variant availability remains authoritative.

## Error and Fallback Behavior

- If an animation fails, the matching final alpha poster remains visible.
- If JavaScript is unavailable, every section remains readable and the product form works.
- Unavailable variants remain disabled.
- Add to cart must preserve Shopify form behavior and must not be simulated.
- Missing optional media must not leave an empty section; the closest verified alpha still is used.

## Implementation Boundaries

Primary files expected to change:

- `sections/maliev-pimm-50g-launch.liquid`
- `assets/maliev-pimm-50g-story.css`
- `assets/maliev-pimm-50g-story.js`
- `scripts/tests/pimm50-keynote-contract.test.mjs` (rename or replace with a product-page contract test)
- existing PIMM 50G Blender source and export scripts where new renders are needed.

The single custom product template remains authoritative. Do not restore Dawn's duplicate product, related-products, or app sections beneath it.

## Acceptance Criteria

1. The route scrolls normally using browser-native document scrolling; no snap rules or wheel interception remain.
2. The hero presents a complete, large alpha 50G render without a rectangular image background or clipped shadow.
3. Every machine media asset is alpha-capable, or a transparent poster replaces unsupported animated alpha playback.
4. Animation-to-static handoffs do not change machine position, scale, crop, lighting, or controller state.
5. Essential decision information remains visible at desktop, tablet, portrait mobile, and short landscape.
6. The purchase form remains native Shopify HTML with factory visit primary and Add to cart secondary.
7. `prefers-reduced-motion` produces a complete static experience.
8. No document horizontal overflow occurs at 320, 390, 768, 1024, 1440, or 3840 px widths.
9. Theme Check, focused product-page contract tests, the Impeccable detector, and browser geometry checks pass.
10. A final dual Impeccable critique is completed before the page is presented for user review.

## Deliberately Excluded

- Copying Porsche, Ferrari, Lamborghini, or Bugatti branding, typography, navigation, or proprietary visual assets.
- WebGL or a fake interactive 3D model without verified authored product data.
- Publishing unverified compressor consumption, warranty, commissioning, payment, or delivery promises.
- Deployment or production-theme push without explicit authorization.
