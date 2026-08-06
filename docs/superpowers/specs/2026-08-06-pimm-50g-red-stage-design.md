# PIMM 50G Red Stage Design

## Purpose

Upgrade the final chapter of the PIMM 30G presentation into a distinct 50G product reveal. The chapter should feel more forceful than the preceding light technical slides without becoming a fictional sci-fi scene or obscuring the real machine. Its job is to communicate the step up in capacity and heat-system durability, then send a qualified customer to the live 50G Shopify product.

## Approved direction

Use a product-first transparent stage:

- Blender renders only the authentic 50G machine, contact shadow, restrained rear fog, and a red backlight pulse.
- HTML and CSS own every word, specification, price, availability message, and call to action.
- The page background is CSS, not baked into the render, so the same asset remains composable across phones, tablets, desktop monitors, localization, and future content changes.
- The corrected Blender master remains untouched. Production work starts from a new file named `PIMM-50g-red-stage-loop.blend`.

## Visual system

### Physical scene

The 50G machine stands directly on a dark neutral floor. A single dominant neutral-white key light comes from camera-left at approximately 5000K. A weaker same-temperature fill protects detail in the cylinder, vertical shafts, controller enclosure, and frame. The red source is an intentional rear effect light, not a competing key: it grows through fog behind the machine and never changes the material colour of the front-facing product surfaces.

The machine must remain sharp from its front feet to the top cylinder. Depth of field is either disabled or kept deep enough that no product component becomes visibly soft. Ground contact is proven by a wide, soft contact shadow that never clips at any animation frame.

### Colour

- Chapter background: neutral near-black, not blue-black.
- Primary text: cool white.
- Secondary text: a light neutral gray that meets WCAG AA.
- 50G accent: oxidized signal red, approximately `#d51f1f`, reserved for the model label, verified upgrade facts, and primary CTA.
- Success green is not used for available inventory because both machines are made to order.
- The red glow may bloom behind the machine, but no gradient text is used.

### Typography

- Add **Antonio** as the 50G chapter display family for the compact model label, headline, verified specifications, price, and CTA. Its tall industrial proportions distinguish the 50G chapter from the handwritten 30G hero without imitating automotive branding.
- Continue using the existing MALIEV sans/Thai families for body copy and localized text. Thai falls back to Chakra Petch and IBM Plex Sans Thai already bundled with the theme.
- Do not introduce a second similar condensed display family.
- Display letter spacing stays at or above `-0.03em`; body text remains sentence case.

## Animation contract

Duration is exactly five seconds and loops seamlessly.

1. **0.0–0.8 seconds — held power:** The grounded machine is already readable under the neutral key. Rear fog is faint and the red backlight is at its minimum loop value.
2. **0.8–3.5 seconds — heat build:** Red energy grows behind the cylinder and upper frame. Fog rolls upward and outward behind the silhouette. Machine exposure remains stable.
3. **3.5–4.2 seconds — peak:** The red backlight reaches maximum intensity with a restrained bloom. Smoke remains behind the machine and never covers the controller displays, pressure gauge, hoses, or frame.
4. **4.2–5.0 seconds — settle:** Fog flow and red intensity return to the opening state without a visible cut.

Loop requirements:

- Frame 1 and the frame immediately after the last rendered frame must match in fog position and red-light intensity.
- Use cyclic procedural drivers or periodic noise rather than a simulation that cannot close cleanly.
- No camera movement. The machine stays locked in a confident three-quarter front view.
- Render separate desktop and mobile compositions from the same scene. Both show the full machine and its complete contact shadow with safe transparent margins.
- Render RGBA with Film Transparent. Do not render typography, the CSS background, or a phone frame.
- Produce transparent WebM animation for capable browsers, static transparent WebP posters for reduced motion and media failure, and a lightweight CSS red-atmosphere fallback so unsupported browsers still retain the art direction.

## Responsive chapter composition

### Mobile

- Use the full viewport below the transparent header.
- Place the compact `PIMM 50G` display title and short upgrade statement at the top.
- Let the animated machine occupy the central visual field without clipping its sides, top, feet, or shadow.
- Present three verified upgrade facts below or beside the machine depending on available height: `50g shot capacity`, `Steel melt zone`, and `2 × 350W hot-runner heaters`.
- Product title, made-to-order status, live THB price, and the red CTA remain readable without overlapping the machine.
- Allow normal document scrolling on short mobile viewports; the chapter must not hide the CTA or trap the footer.

### Desktop

- Use an asymmetric 40/60 composition: conversion copy and live commerce data on the left, machine stage on the right.
- A large low-contrast `50G` background mark may sit behind the right stage, rendered in HTML/CSS.
- The machine is vertically centered and large enough to feel like the higher-capacity model while preserving the full floor shadow.
- Text never crosses into the media column.

## Content and commerce contract

The following are source-backed claims in the current theme and may be displayed:

- 50g shot capacity.
- Steel melt zone.
- Two 350W hot-runner heater bands.

Do not display `350°C` until an authoritative product field or source confirms it. Do not infer a temperature limit from heater wattage.

The chapter must continue to read the selected 50G product and first available variant from Shopify for:

- Product title.
- THB price using Shopify money formatting.
- Product URL.
- Purchasability.

For an available variant, the customer-facing status is **Made to order**, not **In stock**. Show the configured lead time when a product metafield supplies it. If Shopify reports the variant unavailable, show the normal translated out-of-stock state and keep the CTA destination safe.

English and Thai remain supported through locale keys. No customer-facing text is baked into imagery.

## Accessibility and resilience

- Preserve semantic heading order and the existing product link.
- The red CTA must meet at least 4.5:1 text contrast and retain a visible keyboard focus state.
- Decorative fog and the background model mark are hidden from assistive technology.
- `prefers-reduced-motion: reduce` uses the final transparent poster with no looping video or pulsing CSS effect.
- If the video fails or its codec is unsupported, switch to the poster without collapsing the stage.
- Offscreen animation uses `preload="none"` and starts only when the 50G chapter becomes active. It pauses when the chapter leaves the viewport.
- The chapter has zero horizontal overflow at 320px, 390px, 768px, 1024px, and 1440px viewport widths.

## Implementation boundaries

### Blender

- Source: a copy of `PIMM-50g-keynote-reveal-v2-regulator-materials.blend`.
- Preserve corrected pressure-regulator materials and authentic 50G geometry.
- Add named collections for `RED_STAGE_LIGHTS`, `RED_STAGE_FOG`, `RED_STAGE_GROUND`, and `RED_STAGE_CAMERAS` so the treatment can be adjusted without touching product geometry.
- Save a reproducible setup/render script beside the existing Blender scripts.

### Shopify theme

- Extend the existing `next_model` chapter rather than creating a parallel product page or hardcoded template.
- Keep media selectable through the existing section schema and filename fallbacks.
- Add only the markup needed for the 50G identity, verified facts, live commerce data, and robust media fallback.
- Scope all new styles and behavior to the PIMM story chapter.

## Validation

1. Inspect the copied Blender scene for missing files, material assignments, camera framing, transparent film, and object visibility.
2. Render representative frames at the loop minimum, heat build, peak, and final state for both desktop and mobile.
3. Compare the first and end states to prove the loop closes without a visible lighting or fog jump.
4. Inspect alpha bounds to prove full transparency outside the machine, fog, and shadow.
5. Encode and inspect the five-second animation plus static posters; record dimensions, duration, alpha presence, and file sizes.
6. Run `npm run verify` and `git diff --check`.
7. Validate the local storefront at mobile, tablet, and desktop widths for full-machine framing, text contrast, live THB data, made-to-order wording, reduced motion, media failure fallback, and zero horizontal overflow.
8. Commit the Blender production script/assets and theme implementation as coherent validated slices. Do not push or deploy.
