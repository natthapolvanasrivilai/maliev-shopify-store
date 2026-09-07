# PIMM Engineering Console Product Page Design

**Date:** 2026-08-28

**Status:** Approved direction; implementation specification pending owner review

**Scope:** Local development theme and governed Blender presentation assets only

## Objective

Redesign the unified pneumatic injection molding machine product page around one decisive product-presentation hero. The page must let a qualified buyer switch between the 30G and 50G, understand the selected machine, and move toward a demo session or configuration without treating a considered equipment purchase like an impulse checkout.

The visual reference contributes its composition, not its drone branding or unsupported claims: decision copy on the left, a dominant isolated product in the center, compact proof on the right, and a restrained framed canvas. MALIEV keeps its existing typography, signal blue, Shopify contracts, Thai-first clarity, and engineering evidence.

## Success criteria

- The machine is the dominant object at first paint and never overlaps copy, controls, or specification cells.
- The 30G/50G selector is visible in the hero and updates every selected-model value and image consistently.
- The hero communicates four verified specifications without becoming a dashboard or a repeated card-grid page.
- The primary machine conversion is a demo session; configuration and qualification remain explicit secondary paths.
- Desktop, tablet, and mobile layouts preserve complete product visibility and 44-pixel practical touch targets.
- Existing variant, price, deposit, availability, lead-time, localization, app-block, and fail-closed contracts remain intact.
- New storefront derivatives come only from owner-approved Blender proofs and immutable release lineage.

## Non-goals

- Do not copy the reference's navigation, partner logos, drone metrics, video claims, or decorative product name watermark.
- Do not turn the entire page into bento cards.
- Do not add autoplay video, animation sequences, plunger motion, or controller display animation in this slice.
- Do not change product catalog structure, variant IDs, prices, metafield schemas, deposit logic, or production theme state.
- Do not push, deploy, or update the production store without separate authorization.

## Reference extraction

The reference succeeds because it creates one visual hierarchy inside a bounded, pale product canvas:

1. A compact left decision rail carries the promise, supporting copy, price context, and actions.
2. A large center object is isolated from its background and framed with generous negative space.
3. A right evidence rail uses four compact facts plus one wider media panel.
4. The surrounding chrome is quiet enough that the product remains the focal point.

For MALIEV, the global Shopify header remains outside the product canvas. Recreating navigation inside the hero would duplicate controls and weaken accessibility. The hero uses the same alignment grid as the header so the two read as one system.

## Page architecture

### 1. Engineering-console hero

Desktop uses a 12-column layout within a maximum 1440-pixel page width:

- **Decision rail, columns 1–3:** product title, workshop-scale promise, concise fit statement, 30G/50G segmented selector, factory-visit action, and a configuration anchor.
- **Machine stage, columns 4–8:** the selected straight-on alpha render, visually centered and grounded.
- **Evidence rail, columns 9–12:** a 2-by-2 fact matrix for shot capacity, maximum melt temperature, mold envelope, and maximum air pressure. A wide engineering-detail panel below uses the selected controls image and links to the engineering section. It does not use a play icon unless a real accessible video is later supplied.

The hero surface uses MALIEV canvas and surface colors, a restrained 12–16-pixel radius, and no decorative glass effect. Signal blue is reserved for the selected model and primary action. The machine receives the visual weight; fact cells use flat separation and subtle surface contrast rather than wide shadows.

The hero should fit within the first desktop viewport where practical, but content is never clipped to force a fixed height. The global header remains functional and presentation-aware.

### 2. Qualification strip

Immediately below the hero, a quiet horizontal strip presents selected-model availability, full price, deposit amount, lead time, and the next action. This keeps commercial facts visible without crowding the hero or presenting checkout as the default journey.

On smaller screens the strip becomes a vertical summary with the factory-visit action first and deposit control last.

### 3. One engineering bento

Retain one contained bento section for engineering presentation. Its large cell shows the three-quarter machine; supporting cells explain pneumatic drive, temperature control, tooling envelope, and workshop utilities. The bento is a single narrative section, not the page's universal grammar.

The existing verified specification data remains the source for numeric facts. No metric is hardcoded into decorative markup.

### 4. Alternating product story

After the bento, use broad alternating sections rather than more card grids:

- tooling and mold-planning area;
- ownership, support, warranty, documentation, and replacement parts;
- final qualification and purchase/deposit controls.

Each section has one dominant image and one focused decision. Background treatment may alternate between white and MALIEV canvas, but typography and spacing remain consistent.

## Responsive behavior

### Desktop, 1200 pixels and above

- Use the complete three-part hero composition.
- Machine stage is visually centered in the page, not merely centered in its grid cell.
- Evidence facts remain two columns.
- Preserve a complete, grounded machine with no vertical crop.

### Tablet, 750–1199 pixels

- Use a two-column first row: decision rail and machine stage.
- Evidence facts move below as four equal-width items using flexible wrapping.
- The engineering-detail panel spans the full content width.
- Selector and actions remain above the fold where viewport height allows.

### Mobile, below 750 pixels

- Order: title and fit statement, model selector, machine, actions, specification facts, engineering-detail panel.
- Machine media uses a stable aspect ratio and `object-fit: contain`; it must not rely on absolute positioning.
- Facts use two columns where at least 320 pixels remain available and one column at narrow zoomed widths.
- No horizontal overflow, clipped focus outline, hidden content, or scroll-jacking.

## Variant and interaction contract

The existing `pimm-machine-product` custom element remains the single controller. It continues to:

- require exactly the 30G and 50G records in that order;
- validate each record and fail closed when commerce, specification, or media contracts disagree;
- update the selected model, URL variant parameter, specification values, media, availability, price, and deposit state;
- decode only the selected hero eagerly;
- crossfade model media in 180 milliseconds and switch instantly under reduced motion;
- keep hidden model media inert and unavailable to assistive technology.

The redesign adds presentation slots but does not introduce a second state system. Hero fact cells bind to the existing `data-pimm-spec` contract. The engineering-detail panel binds to the existing engineering media slot. Qualification remains driven by the selected variant record.

## Content hierarchy

The hero message should use the verified positioning: real injection molding capability, sized and supported for a Thai workshop. Exact English and Thai copy belongs in locale keys, not directly in Liquid.

Action order:

1. Book a demo session.
2. Configure the selected machine or review qualification requirements.
3. Open documentation or contact MALIEV through the existing support path.
4. Place the deposit only after the buyer reaches the qualification section.

Do not add unsupported partner logos, testimonials, savings, throughput, certification, or performance claims.

## Blender and storefront render contract

### Required shot family per model

1. **Hero front:** existing governed `pimm-<model>--hero--front` scene, 1800 × 2200, transparent output, straight-on eye-level presentation, complete machine, consistent apparent scale between models.
2. **Overview three-quarter:** governed 2400 × 1800 overview scene using the approved 85 mm setup.
3. **Engineering controls:** governed 2400 × 1800 close-up using the approved 135 mm setup; regulator and actuator artwork must remain visible.
4. **Tooling front detail:** governed 2400 × 1800 close-up using the approved 135 mm setup and the median-foot physical contact plane.

The current hero contract does not declare focal length. Its existing governed camera remains authoritative. Any camera-optics change requires a scene-contract revision, a new proof, owner approval, native final, and a new immutable release rather than an ad hoc render override.

### Framing requirements

- Render both models against identical camera intent, HDRI, exposure, color transform, and product-scale policy.
- Keep the full machine inside safe alpha bounds with enough headroom and floor contact for responsive containment.
- Use physical contact shadows. Do not paint or generate shadows in post-production.
- Preserve decals, controller displays, pressure-gauge artwork, materials, and linked master geometry.
- Do not use generative pixel edits, AI upscaling, cloud enhancement, or background replacement.

### Storefront derivatives

- Hero derivatives retain alpha and use lossless-enough WebP settings validated by the render-lineage tests.
- Detail derivatives may use alpha or approved pale-studio composites according to their scene release.
- File dimensions and media-slot declarations must match the variant JSON contract exactly.
- CSS owns the pale hero canvas. Blender owns the product, materials, lighting, and physical shadow.
- A derivative is eligible only after proof approval and immutable release publication. Working proofs never enter `assets/`.

### Future animation readiness

The wide evidence panel is designed to accept a real poster/video pair later. Future plunger motion or controller-number animation requires its own owner-approved motion map, Blender scene contract, endpoint proofs, reduced-motion poster, and video delivery plan. This static redesign does not imply that animation is currently available.

## Component and file boundaries

- `sections/maliev-pimm-machine-product.liquid`: hero composition, qualification-strip placement, section ordering, and existing schema ownership.
- `snippets/pimm-model-selector.liquid`: accessible 30G/50G selector, restyled without changing radio semantics.
- `snippets/pimm-engineering-bento.liquid`: the single engineering bento and engineering-detail media.
- `snippets/pimm-ownership.liquid`: support and ownership narrative.
- `snippets/pimm-purchase-qualification.liquid`: price, lead-time, qualification, and deposit controls.
- `assets/maliev-pimm-machine.css`: responsive layout, visual hierarchy, focus states, and reduced-motion treatment.
- `assets/maliev-pimm-machine.js`: existing validated variant state and media transitions; extend only if a new slot cannot use the current data bindings.
- `templates/product.pimm-configurator.json`: merchant-configurable model asset declarations and bilingual alt text.
- `locales/en.default.json` and `locales/th.json`: all new user-facing copy.
- `scripts/tests/pimm-unified-render-assets.test.mjs` and focused PIMM product tests: media lineage, contract, and responsive behavior coverage.
- Governed Blender scripts and manifests: new proof/final work only when existing released assets cannot satisfy the approved composition.

Avoid creating another monolithic section, duplicate variant controller, or parallel data payload.

## Accessibility

- Preserve semantic `h1`, ordered `h2` hierarchy, landmarks, `figure`, `dl`, fieldset, and legend usage.
- Keep selector radios keyboard-operable with visible focus and an announced selected model.
- Maintain at least WCAG 2.2 AA contrast and practical 44-pixel action targets.
- Provide useful Thai and English alternative text for each model and shot purpose.
- Do not hide essential facts behind hover, animation, color, or spatial position.
- Reduced motion removes crossfade choreography without changing information or state.
- At 200% zoom, the hero becomes a readable single-column flow with no loss of controls.

## Performance

- Eager-load only the selected hero; defer the alternate model and below-fold images.
- Keep explicit image dimensions to prevent layout shift.
- Use responsive derivatives where Shopify asset behavior permits without weakening exact lineage checks.
- Do not add a frontend framework, autoplay media, WebGL, or third-party runtime for this composition.
- Keep model switching transform/opacity-based and avoid layout animation.

## Error handling

- Invalid or incomplete variant payloads continue to fail closed: deposit disabled, unavailable status shown, and no stale model media presented as valid.
- Missing optional detail media may fall back to the validated hero under the existing contract.
- Missing or invalid hero media invalidates the model presentation and purchase state.
- Image decode failure must not block text, selector, or qualification access.

## Validation

Implementation is complete only after:

1. Focused Liquid/JavaScript contract tests pass for 30G and 50G switching, invalid payloads, URL updates, price/deposit state, and every media slot.
2. Render-lineage tests authenticate every committed derivative and reject mismatched identity, dimensions, alpha, or authority.
3. `npm run verify` passes with zero Theme Check errors.
4. Desktop visual QA covers 1440 × 900 and 1280 × 800.
5. Mobile visual QA covers 390 × 844 and 360 × 800.
6. Keyboard, focus, 200% zoom, reduced motion, Thai, English, missing-media, and unavailable-variant states are inspected.
7. No horizontal overflow, machine overlap, accidental crop, floating contact, or unexpected content shift remains.
8. The local preview route is reviewed before any push or production action.

## Release boundary

This design authorizes local implementation only after the owner approves this specification and its implementation plan. It does not authorize production deployment, a push to `main`, Shopify product mutation, catalog publication, or replacement of a released render without the corresponding Blender approval chain.
