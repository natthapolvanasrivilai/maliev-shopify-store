# MALIEV Machine-First Homepage Design

**Status:** Approved direction

**Date:** 2026-07-17

**Design system:** `DESIGN.md` — The Compact Production Keynote

**Product context:** `PRODUCT.md`

**Image production:** `IMAGE_GUIDELINES.md`

## Outcome

Redesign the MALIEV storefront homepage as a focused product-launch journey for the 30g and 50g pneumatic injection molding machines. The page must make the machines immediately understandable, establish MALIEV as a dependable Thai manufacturer, and guide qualified buyers toward scheduling a demonstration or requesting a quotation.

The homepage is not a general catalogue. Mesh Splitter, SimMount, 3D-printed products, and guides remain discoverable in a visually secondary “More from MALIEV” area near the bottom.

## Audience and decision model

Primary visitors are manufacturers, workshops, makers, and product developers considering small-batch plastic production. This is a high-consideration purchase: most visitors will not complete checkout immediately. They need to understand fit, capacity, ownership cost, support, and the next step before purchasing.

The conversion hierarchy is:

1. **Schedule a demonstration** — primary action throughout the page.
2. **Request a quotation** — secondary action for visitors with a defined project.
3. **Chat on LINE** — convenient, lower-commitment contact route.
4. **Download specifications** — self-service technical evaluation.
5. **View product details or purchase** — available without dominating the narrative.

## Experience direction

Use a “Guided Keynote” structure: large product imagery, short declarative messages, progressive technical explanation, and restrained scroll-led transitions. The reference is the clarity and pacing of a premium product launch, not visual imitation of Apple.

The experience should communicate:

- **Ingenious:** practical engineering makes injection molding accessible.
- **Dependable:** in-house manufacturing, one-year warranty, local support, and replacement parts.
- **Approachable:** understandable language, easy operation, and comfortable access to advice and demonstrations.

Avoid generic Shopify-theme composition, dense card grids above the fold, decorative gradients, excessive glass effects, and motion without explanatory value.

## Homepage narrative

### 1. Machine launch hero

Open with the 30g and 50g machines together against a bright, controlled studio environment. Keep generous negative space for copy and preserve the products as the dominant visual subject.

Recommended message:

- Eyebrow: `Pneumatic injection molding machines`
- Heading: `Small footprint. Real production.`
- Supporting copy: compact machines for prototypes and small batches, made and supported by MALIEV in Thailand.
- Primary CTA: `Schedule a demonstration`
- Secondary CTA: `Request a quotation`
- Tertiary links: `Compare 30g and 50g` and `Download specifications`

The hero should fit the primary message and actions within the first desktop viewport while allowing the machines to retain visual scale. On mobile, copy precedes a contained product image with no text baked into the asset.

### 2. Compact capability

Show one machine in a clean, credible small workshop or product-development space. Use environmental scale cues to make the footprint legible without publishing an unverified numerical claim.

Message focus:

- Fits workshops where industrial equipment would be impractical.
- Supports prototyping and small-batch production close to the product team.
- Makes real injection molding available without the overhead or intimidation of a traditional factory installation.

This section should feel spacious and visual, not like a feature-card grid.

### 3. Small-batch economics

Explain the practical economic advantage in three plain-language ideas:

- Lower machine investment than conventional industrial equipment.
- Mold paths suited to small-batch production and product development.
- Local assistance reduces the uncertainty of tooling, setup, and replacement parts.

Do not publish unsupported savings percentages or competitor comparisons. The section may use a simple progression or comparison layout, but it must clearly label qualitative claims and avoid implying universal total-cost outcomes.

### 4. Choose the right machine

Present the 30g and 50g as a coherent family rather than unrelated product cards. Each model needs:

- Product image using the real machine geometry.
- Shot-size designation.
- Short best-fit description.
- Verified technical highlights sourced from the product data or editable section settings.
- `View 30g` or `View 50g` detail action.
- Specification download action when a valid document URL is configured.

Desktop may use a two-column comparison. Mobile must stack the models and keep labels adjacent to their values; do not use a horizontally scrolling comparison table.

Prices may be shown when accurate and merchant-controlled. The presentation must still prioritize demonstration and quotation because configuration and tooling affect the buying decision.

### 5. Engineering made approachable

Use a close engineering-detail image of the real controller, pneumatic assembly, tubing, frame, and hardware. Pair the image with a concise explanation of:

- Straightforward controls.
- Serviceable construction.
- Accessible replacement parts.
- Guidance from the team that builds the machine.

The visual may use a gentle sticky or pinned composition on large screens, provided all content remains in normal document flow and fully usable when motion is disabled.

### 6. Made and supported in Thailand

Create a trust chapter based only on claims MALIEV can substantiate:

- Designed and manufactured in-house.
- Local Thai support.
- One-year machine warranty.
- Replacement parts available.
- Direct access to the manufacturer for setup and maintenance guidance.

Do not use customer logos, named customer claims, or confidential customer molds. Trust should come from specific operating commitments, engineering detail, and transparent contact routes.

### 7. Mold-making assistance

Explain that MALIEV can assist with mold design and making for its machines. Use diagrams, neutral tooling imagery, or non-customer demonstration assets only.

Frame the service as a path:

1. Share the part or product requirement.
2. Review machine, material, and tooling fit.
3. Develop the mold and production setup.

The CTA should lead to the quotation/contact route with enough context to distinguish a mold inquiry from a general message.

### 8. Conversion close

End the machine narrative with a high-clarity decision section:

- Heading: `See what the right machine can make possible.`
- Primary CTA: `Schedule a demonstration`
- Secondary CTA: `Request a quotation`
- Supporting contact: LINE.

On small screens, a restrained sticky contact bar may expose the primary demo action after the hero. It must not cover content, interfere with Shopify cart controls, or trap keyboard focus.

### 9. More from MALIEV

Condense secondary offerings into a quiet, reusable discovery area after the primary conversion close:

- Mesh Splitter.
- SimMount hardware.
- 3D-printed products.
- Guides and workshop resources.

Use compact editorial links or tiles. Do not repeat full pricing tables, large carousels, or a second competing hero. Machine-related guides may receive slightly greater prominence than unrelated content.

## Image direction and asset handling

The authoritative product identity comes from the existing 30g and 50g renders and Blender project under:

`M:\30_Products\00_Pneumatic Injection Molding Machine`

Generated temporary images are composition and lighting references only. They must not be treated as dimensional or component truth. Final production assets should be rendered from the Blender source so the frame, cylinders, platens, controls, tubing, springs, fasteners, proportions, and 30g/50g scale relationship remain accurate.

Required final image families:

1. Dual-machine bright hero, desktop and mobile crops.
2. Single-machine compact workshop scene.
3. 30g and 50g consistent comparison renders.
4. Controller and pneumatic assembly detail.
5. Optional neutral mold-process or service diagram without customer IP.

All meaningful images require editable alt text. Decorative crops use empty alt text. Never place essential copy inside an image.

Temporary site implementation may use the best existing accurate renders while preserving media settings so final Blender exports can be swapped through the Theme Editor without code changes.

## Visual system

Follow `DESIGN.md`:

- Optical white and cool neutral surfaces.
- Near-black typography with restrained blue action color.
- Large, confident product headlines with compact supporting copy.
- Spacious vertical rhythm and strong alignment.
- Fine rules, subtle tonal separation, and minimal shadows.
- Product photography and engineering detail provide the visual interest.

Use the storefront’s established typography and core tokens unless a verified design-system improvement applies globally. Do not introduce a homepage-only novelty typeface.

## Interaction and motion

Motion must explain hierarchy or product detail:

- Gentle hero entrance after the page is ready.
- Subtle reveal of key messages as they enter the viewport.
- Optional slow product position or scale transition between narrative chapters.
- Clear hover and focus states on actions and model choices.

Rules:

- No scroll hijacking.
- No autoplay audio.
- No essential information revealed only by animation.
- Avoid layout shifts and expensive continuous effects.
- `prefers-reduced-motion: reduce` must remove non-essential transforms, smooth scrolling, and transition delays.
- Content must remain readable with JavaScript unavailable.

## Responsive behavior

Design mobile intentionally rather than shrinking desktop:

- Copy precedes or immediately follows its related image.
- CTAs become full-width when needed, with the primary action first.
- Model comparison stacks vertically.
- Sticky desktop chapters return to normal flow.
- Touch targets meet accessibility sizing guidance.
- No horizontal overflow at supported viewport widths.
- Use responsive image sources and explicit dimensions to control layout shift.

## Accessibility and content requirements

- Target WCAG 2.2 AA.
- Maintain semantic heading order and landmark structure.
- Preserve visible keyboard focus.
- Provide accessible names for all links, controls, and any carousel or disclosure behavior.
- Meet color contrast requirements in default, hover, focus, and disabled states.
- Do not encode model differences through color alone.
- Keep English source copy compatible with Shopify localization; merchant-facing content remains editable through section settings.
- Use plain language and define technical terms where they first appear.

## Shopify architecture

Implement the narrative as reusable Online Store 2.0 sections and blocks, not a monolithic hardcoded homepage.

Each section must:

- Include a valid `{% schema %}` contract.
- Expose useful headings, body text, links, product/media selectors, alt text, and layout controls to the Theme Editor.
- Render sensible defaults while tolerating empty optional settings.
- Avoid hardcoded store-domain URLs when Shopify URL or object settings are available.
- Keep user-facing interface labels locale-ready.

Existing sections may be refactored where their contract supports the new hierarchy. Remove the current homepage’s Mesh Splitter pricing, generic family grid, broad workflow, and unrelated new-arrivals block from the primary narrative. Their underlying reusable components may remain available to other templates.

## Validation contract

Implementation is complete only when:

1. The homepage order matches the machine-first narrative and secondary products appear only after the primary conversion close.
2. Demonstration is the most prominent conversion action; quotation is consistently second.
3. Both 30g and 50g are clearly represented with accurate product imagery and distinct paths.
4. Local manufacturing, warranty, parts support, and mold assistance are present without unsupported proof claims.
5. All merchant-facing sections retain valid Theme Editor schemas.
6. `npm run verify` passes at error level.
7. Desktop and mobile browser checks confirm readable hierarchy, functional links and controls, visible focus, reduced-motion behavior, and zero horizontal overflow.
8. The page remains understandable without animation and usable without JavaScript-enhanced effects.

## Deferred work

- Final Blender production renders and their Shopify CDN upload.
- Customer logos or testimonials unless explicit permission is later obtained.
- Confidential mold photography.
- Checkout or product-page redesign beyond adjustments strictly required by homepage links.
- Unsupported numerical ROI or competitor benchmarking.
