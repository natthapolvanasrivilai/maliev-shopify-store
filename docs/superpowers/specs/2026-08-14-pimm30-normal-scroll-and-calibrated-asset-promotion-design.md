# PIMM 30G Normal-Scroll Redesign and Calibrated Asset Promotion

Date: 2026-08-14
Status: Approved design direction; implementation pending written-spec approval

## 1. Outcome

Replace the obsolete 30G and 50G storefront render assets with the approved calibrated Blender output, correct the 50G controller readout to the machine's actual 350°C maximum, and redesign the PIMM 30G product page as an ordinary, customer-friendly product journey.

The redesigned 30G page must scroll normally. It must not use keynote-style chapters, scroll snapping, fixed-height slides, wheel interception, or exact-viewport staging. Motion is a progressive enhancement attached to normal document flow.

## 2. Product truth

These values are non-negotiable content and rendering contracts:

- PIMM 30G maximum temperature: **300°C**.
- PIMM 50G maximum temperature: **350°C**.
- PIMM 50G heater power: **2 × 350 W**. Heater wattage and maximum temperature are separate facts and must never be conflated.
- Every controller-bearing 50G render must display **350/350** on both controllers.
- Every controller-bearing 30G render and supporting copy must remain consistent with the 30G's **300°C** maximum.

The current calibrated 50G proof generation that displays 300/300 is invalid for storefront promotion and must be regenerated as 350/350 before any 50G asset is copied into the theme.

## 3. Scope

### In scope

- Regenerate and validate the calibrated 50G controller readouts as 350/350.
- Promote the approved calibrated 30G and corrected calibrated 50G stills and animations into versioned Shopify theme assets.
- Update every 30G and 50G Liquid, JSON-template, poster, comparison, and animation consumer to the new versioned files.
- Remove the 30G keynote interaction model and redesign the page as six natural-height product sections.
- Replace the 30G page's red-stage 50G comparison media with corrected bright-studio 50G media.
- Add restrained one-time content reveals without changing native page scrolling.
- Enable full motion on the local `127.0.0.1:9393` development preview so the in-app browser can test animation even when its environment reports reduced motion.
- Preserve production reduced-motion support on hosted storefronts.
- Validate product forms, pricing, availability, keyboard flow, responsive layout, alpha rendering, and zero horizontal overflow.

### Out of scope

- Production deployment, theme publication, or pushing the branch.
- Changing machine specifications, prices, variants, inventory, or purchase qualification rules.
- Rebuilding unrelated product, collection, editorial, or policy pages.
- Deleting legacy render files in the first implementation slice. They may remain in the repository as unused rollback assets until the new storefront has been approved.
- Introducing scroll-driven video scrubbing, WebGL product viewers, or a new animation framework.

## 4. Asset promotion contract

### 4.1 Source and proof integrity

- Blender source files remain immutable during render generation. SHA-256, byte length, and modification time are recorded before and after each generation.
- Only a coherent proof generation that passes its rendering contracts and original-resolution visual review may be promoted.
- The 30G dark-studio startup remains exclusive to the 30G landing-page hero. Normal 30G product imagery uses the bright calibrated studio.
- Every 50G asset uses the bright calibrated studio. No red-stage or dark-studio 50G media may appear on the 50G page or in the 30G comparison section.
- Complete-machine assets retain transparent RGBA output with a light, physical, uncut ground shadow. Feature close-ups may use intentional contextual fades only when their protected subject is fully visible and the fade is validated.

### 4.2 Storefront formats

- Calibrated stills are converted from validated native RGBA PNG proofs to alpha-preserving WebP at the contracted storefront dimensions.
- Animations use WebM with a matching alpha-safe poster. A still fallback is always present.
- Conversion must not clip the alpha shadow, introduce white matte contamination, alter color-management intent, or reduce controller and engraving legibility.
- Render-to-storefront conversion is verified by dimensions, alpha presence, representative pixel comparisons, and visual inspection over white, canvas-gray, and dark checker backgrounds.

### 4.3 Versioned filenames and consumers

Use explicit versioned names rather than overwriting ambiguous legacy files. The implementation plan will freeze the final mapping, using these families:

- `pimm30-cal-v1-*` for calibrated 30G assets.
- `pimm50-cal-v2-350c-*` for corrected calibrated 50G assets.

The implementation must update all exact consumers, including:

- `sections/maliev-pimm-30g-story.liquid`
- `templates/product.injection-molding-machine.json`
- `sections/maliev-pimm-50g-launch.liquid`
- 30G comparison media that currently references `pimm50-red-stage-*`
- Posters, desktop/mobile sources, preload references, and alt text

No new storefront file is considered promoted while an active Liquid or template consumer still resolves to an obsolete equivalent.

## 5. PIMM 30G information architecture

The current ten keynote-like chapters are consolidated into six customer-decision sections. Each section has one clear purpose, a bounded amount of copy, and adjacent visual evidence.

### 5.1 Hero: Start small, make real parts

- A contained dark-studio startup animation introduces the machine and resolves to the bright complete-machine view.
- Show the PIMM 30G name, a concise value proposition, primary purchase/configuration action, and factory-visit action.
- Place the primary commercial action above the fold without making the hero a viewport-locked slide.
- Video failure or reduced motion shows the validated bright endpoint poster and all content immediately.

### 5.2 Fit and output

- Explain workshop footprint, 30 g shot capacity, and the type of parts the machine suits.
- Use bright calibrated capacity/complete-machine media.
- Present critical dimensions and capacity as a compact specification group rather than scattered chapter facts.

### 5.3 Controls and heating

- Explain the dual-zone temperature controls, the 300°C operating ceiling, and what the user monitors during a cycle.
- Use the corrected 30G temperature-controller render.
- Keep temperature, heater power, and pneumatic pressure as separate labelled facts.

### 5.4 Direct operation

- Explain the pneumatic injection sequence, regulator requirements, and operator actions in a short, ordered operating flow.
- Combine the former operation, cylinder, and regulator material without repeating the same machine claim.
- Use ordinary cards or numbered steps; do not tie progression to scroll position.

### 5.5 Mold workspace and setup

- Explain mold space, fixture compatibility, material path, and practical setup.
- Keep the protected mold/fixture subject visually complete.
- Put dimensions and compatibility notes next to the relevant image instead of in a distant slide.

### 5.6 Choose, qualify, and buy

- Compare 30G and 50G using bright calibrated media for both machines.
- Explain who should choose each model without overstating capability.
- Include Thailand-based support, factory demonstration, lead time, qualification copy, variant selection, price, availability, and Add to Cart.
- The product form remains native Shopify markup and behavior.

## 6. Layout and visual direction

The page follows the bright MALIEV product language already established by the 50G light-studio page:

- White and cool-canvas surfaces, dark ink, signal blue, restrained yellow focus accents.
- IBM Plex typography and existing theme tokens.
- Precise engineering spacing, fine rules, compact specification typography, minimal decoration.
- Bright alpha machine renders float naturally within the layout rather than being trapped in framed cards.
- Desktop uses varied two-column compositions, alternating visual weight without mechanically alternating every section.
- Mobile keeps the relevant image, explanation, and specification together; it must not separate a machine image from its explanation by a viewport or more.

Explicitly prohibited:

- `scroll-snap-type`, `scroll-snap-align`, or `scroll-snap-stop` on the product story.
- Fixed, sticky, or viewport-height chapter stages.
- Wheel, touchmove, or keyboard interception for chapter navigation.
- Programmatic `scrollIntoView` as a presentation mechanism.
- Mandatory animation before content becomes available.
- Desktop compositions that depend on product art being cropped outside the viewport.

## 7. Motion model

### 7.1 Normal behavior

- All content is visible and usable without JavaScript.
- JavaScript adds a page-ready class and observes marked elements with `IntersectionObserver`.
- Each target reveals once when it enters the viewport, then is unobserved.
- Recommended reveal duration is 420–700 ms with small translation, opacity, rule-draw, or value-emphasis changes appropriate to the component.
- Related elements may use short bounded staggering, with the complete sequence staying below 900 ms.
- No scroll listener, requestAnimationFrame loop, timeline scrubbing, or repeated viewport animation is needed.

### 7.2 Reduced motion and local testing

- On hosted storefront URLs, `prefers-reduced-motion: reduce` reveals all content immediately and suppresses nonessential CSS/video motion.
- On `127.0.0.1:9393`, the page applies an explicit local debug-motion class and runs the full authored motion even if the in-app browser reports reduced motion.
- The same local override must cover both the 30G and 50G product pages so animation QA is deterministic.
- The override is hostname-and-port scoped; it must not disable reduced-motion support on preview-share URLs or production.

## 8. Shopify and commerce contracts

- Preserve Shopify section schemas and useful Theme Editor settings.
- Migrate the current product template from ten chapter blocks to six semantic section roles without losing product configuration data.
- Preserve selected variant ID serialization, price, availability, quantity behavior, Add to Cart, accelerated checkout behavior if present, and factory-visit link.
- Variant and purchase actions must remain reachable in logical keyboard order.
- User-facing copy remains translatable through locale keys or existing merchant-editable schema settings.
- Duplicate default Shopify product galleries or product-info wrappers must remain suppressed on the custom landing page.
- One product H1 only.

## 9. Responsive and accessibility requirements

Validate at minimum:

- 1440 × 900 desktop
- 820 × 1180 portrait tablet
- 390 × 844 mobile portrait
- 852 × 393 short mobile landscape

At every viewport:

- No document horizontal overflow.
- No semantic content or purchase control is clipped.
- Complete-machine renders remain complete; intentionally contextual close-ups retain their protected subject.
- Tap targets are at least 44 × 44 CSS pixels; primary commercial controls target 48 px height.
- Text contrast meets WCAG AA; focus indicators meet the existing dark-outline plus yellow-inset design contract.
- Alt text states what the image proves and uses the correct model-specific temperature.
- DOM order matches reading order when visual columns reverse.
- Lazy-loaded media does not cause disruptive layout shift.

## 10. Validation and acceptance

### 10.1 Asset and product contracts

- Immutable Blender-source readback passes for both models.
- Corrected 50G proofs show physical mesh `350/350` readouts in every controller-bearing output; no lingering `300/300` 50G output is promoted.
- 30G assets and copy retain the 300°C contract.
- Every active consumer resolves to a calibrated versioned filename.
- No active 30G/50G consumer references `pimm50-red-stage-*` or an obsolete equivalent.
- Storefront media preserve expected dimensions, alpha, endpoint parity, and shadow clearance.

### 10.2 Interaction contracts

- Automated source checks reject scroll snapping, viewport chapter heights, sticky story stages, wheel/touch interception, and programmatic chapter scrolling.
- With normal motion, representative reveal targets transition from prepared to complete once during ordinary scrolling.
- With hosted reduced motion emulation, every target and poster is immediately visible and usable.
- On local `127.0.0.1:9393`, full motion runs even when the browser preference is reduced.
- Keyboard traversal proves variant selector, factory-visit action, and Add to Cart order and focus appearance.

### 10.3 Browser and theme checks

- Focused product-page contract tests pass.
- Responsive Chromium matrix passes at all four required viewports.
- Product selection and Add to Cart serialization are verified against the native Shopify product form.
- Impeccable detector returns no findings on changed section files.
- `npm run verify` and Theme Check pass with no new offenses.
- `git diff --check` passes.
- Original-resolution visual review covers every promoted asset and both product pages.

## 11. Implementation boundaries

The implementation should be divided into independently reviewable commits:

1. **Correct and validate 50G 350°C rendering** — restore 350/350 physical controller meshes, regenerate the coherent calibrated proof generation, and preserve all rendering/source-integrity gates.
2. **Promote calibrated storefront assets** — convert validated proofs, add versioned assets, update exact 30G/50G consumers, and remove active red-stage/legacy references.
3. **Redesign the 30G product page** — replace keynote chapters with the six-section normal-flow structure and preserve Shopify commerce/schema contracts.
4. **Add and harden ordinary reveal motion** — one-time content reveals, hosted reduced-motion support, and local-only full-motion override for both product pages.
5. **Responsive and final Impeccable polish** — browser matrix, commerce/focus verification, detector, Theme Check, and original-resolution asset/page review.

Each commit must be internally valid and must not include unrelated existing work. No production deployment or push is part of this design.

## 12. Definition of done

The work is ready for user review when:

- The local 30G page scrolls like a conventional premium product page, with six readable decision sections and restrained reveal motion.
- The local 50G page uses only corrected bright calibrated assets and every visible controller reads 350/350.
- The 30G page uses calibrated 30G imagery and a bright calibrated 50G comparison, with no keynote scrolling or red-stage 50G media.
- The local in-app browser visibly runs animations on port 9393, while hosted reduced-motion behavior remains accessible.
- Both pages pass the defined responsive, accessibility, commerce, asset, Impeccable, and theme validation gates.
- The user can review the completed local preview before any publication decision.
