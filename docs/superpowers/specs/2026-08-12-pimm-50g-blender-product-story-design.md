# PIMM 50G Blender Product Story Design

**Status:** Approved for implementation planning
**Date:** 2026-08-12
**Storefront:** MALIEV Thailand Shopify product page
**Product:** Pneumatic Injection Molding Machine 50G

## Objective

Replace the PIMM 50G page's AI-generated feature imagery with mechanically faithful Blender assets and restructure the page as a responsive keynote-style product presentation. The result must combine a distinctive dark-red launch reveal with bright, technically inspectable product slides that help a Thai workshop buyer understand the machine, verify fit, and arrange a factory visit.

The work must preserve Shopify pricing, availability, variant selection, cart behavior, localization, accessibility, and merchant-editable product data.

## Audience, Offer, and Conversion

### Primary audience

- Thai workshop owners, manufacturers, prototyping teams, schools, and product-development teams that need more shot capacity than the PIMM 30G.
- Existing 30G prospects evaluating whether the larger melt system, frame, heating system, and mold workspace justify the 50G investment.
- Buyers who require visible proof of machine construction, workshop footprint, utility requirements, mold compatibility, serviceability, and local support before purchasing.

### Core offer

The PIMM 50G is the higher-capacity MALIEV pneumatic injection molding platform for buyers who need a 50 g shot capacity, steel melt zone, dual 350 W heating, and a larger working envelope while retaining a workshop-scale footprint.

All specifications shown on the page must come from the verified product contract or the physical Blender model. Visuals must never imply geometry, accessories, finishes, or functions that are not present on the production machine.

### Conversion hierarchy

1. **Primary:** Book a factory visit.
2. **Secondary:** Configure the machine and confirm mold compatibility.
3. **Transactional:** Add the selected Shopify variant to cart only after the product and configuration context is visible.

The page must display live Shopify price, availability, variant selection, and lead-time information rather than baking these values into images.

### Buyer objections the story must answer

- Is the 50 g capacity real and visibly different from the 30G?
- Will the buyer's mold and fixture fit the available working envelope?
- How are the melt zone and two heating zones constructed and controlled?
- What utilities and pneumatic supply are required?
- How large is the machine in a real workshop?
- Can MALIEV demonstrate, support, service, and supply parts for it in Thailand?
- What is included, what is optional, how much does it cost, and what is the lead time?

## Visual Direction

### Hybrid presentation

The opening uses a dark-red studio reveal to distinguish the 50G from the 30G and communicate additional capacity. After the reveal, the presentation transitions to the MALIEV bright precision-studio system so buyers can inspect the machine without cinematic lighting obscuring the product.

The red treatment is an accent, not the default background for the entire page. Technical slides use a near-white workshop surface, neutral metal rendering, broad soft lighting, accurate shadows, black typography, Signal Blue interaction color, and restrained red 50G identifiers.

### Image rules

- Blender renders are the source of truth for machine geometry and materials.
- Product images must remain free of baked marketing copy, UI, gradients, technical diagrams, or prices.
- Complete-machine slides must show the full machine and natural contact shadow without clipping.
- Feature slides may use intentional close framing only when the named component remains understandable in relation to adjacent machine geometry.
- Transparent output must retain the authentic alpha channel. CSS masking is allowed only for an explicitly designed soft edge on detail shots; it must not create a visible rectangular boundary.
- Desktop and portrait compositions use separately framed cameras. A desktop render must not be cropped into a portrait layout.
- Controller displays, vendor decals, fasteners, hoses, gauges, and product labels must remain faithful and legible where the shot scale permits.
- No third-party equipment may receive MALIEV branding.
- AI-generated PIMM 50G machine imagery must not remain in the final presentation.

## Blender Project Architecture

### Source and target

The corrected master is immutable input:

`M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\PIMM-50g-keynote-reveal-v2-regulator-materials.blend`

Implementation creates a dedicated target project:

`M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders\PIMM-50g-product-story-v1.blend`

The target must be created by an idempotent repository script. The script must never save over the corrected master or the currently open PIMM 30G Blender project.

### Geometry contract

- Use the existing `Machine_50g` collection as the authoritative 50G model.
- Preserve the known 50G source inventory of 481 objects and its verified model bounds unless a documented mechanical correction requires a change.
- Keep original material assignments, AIRTAC/vendor decals, controller faces, gauge artwork, hoses, and regulator materials.
- Shared machine geometry and materials remain linked or duplicated consistently across scenes. Slide-specific cameras, lights, floors, world settings, and animation controls use a dedicated `PIMM50_STORY_` ownership prefix.
- The project may include `Machine_30g` only for the controlled same-angle comparison scene.
- Blender file references must resolve without missing textures before rendering.

### Scene model

One multi-scene Blender project supplies the product story. Each visual subject has desktop and portrait scenes with shared geometry and lighting definitions. Separate projects per slide are rejected because they would encourage material, scale, and lighting drift.

Required initial scene families:

1. `PIMM50_STORY_REVEAL_DESKTOP` and `PIMM50_STORY_REVEAL_MOBILE`
2. `PIMM50_STORY_OVERVIEW_DESKTOP` and `PIMM50_STORY_OVERVIEW_MOBILE`
3. `PIMM50_STORY_CAPACITY_DESKTOP` and `PIMM50_STORY_CAPACITY_MOBILE`
4. `PIMM50_STORY_MELT_ZONE_DESKTOP` and `PIMM50_STORY_MELT_ZONE_MOBILE`
5. `PIMM50_STORY_HEATING_DESKTOP` and `PIMM50_STORY_HEATING_MOBILE`
6. `PIMM50_STORY_MOLD_SPACE_DESKTOP` and `PIMM50_STORY_MOLD_SPACE_MOBILE`
7. `PIMM50_STORY_COMPARISON_DESKTOP` and `PIMM50_STORY_COMPARISON_MOBILE`
8. `PIMM50_STORY_PURCHASE_DESKTOP` and `PIMM50_STORY_PURCHASE_MOBILE`

The existing authentic red-stage animation may be retained for the reveal if it passes the geometry, decal, framing, and motion checks. All bright technical scenes must be generated by the dedicated product-story project.

### Camera and render contract

- Use restrained product-photography perspective, normally within a 70–100 mm full-frame-equivalent lens range.
- Keep at least 15% visual breathing room around complete-machine geometry and its contact shadow.
- Desktop and portrait cameras must target the subject independently rather than share a crop.
- Overview, comparison, and purchase scenes must show the whole machine.
- Detail scenes must identify the component through framing, not annotations baked into the image.
- Use broad soft key, fill, and rim lighting that preserves brushed metal form without black shafts, cloudy overexposure, or uncontrolled mirror reflections.
- Bright scenes render with transparent film, a separate or preserved contact-shadow treatment, denoising, color management, and reproducible sampling settings.
- Produce WebP stills for static fallbacks and WebM only when animation materially improves understanding.
- Reduced-motion users receive the representative final still without an autoplay dependency.

## Presentation Narrative and Slide Contract

### 1. Dark-red reveal

Open with the 50G machine emerging in a controlled dark studio with a visible red halo. The animation establishes silhouette and scale before copy and actions appear. It must not obscure geometry, change material colors, or introduce a fake background machine.

The reveal ends in a pose that aligns with its static fallback so the transition has no size or position flash.

### 2. Bright complete-machine overview

Transition to a clean, bright studio view showing the full machine and natural contact shadow. This is the primary inspection image and the visual benchmark for scale on the rest of the page.

The slide states the 50G value proposition and verified headline specifications without covering the machine.

### 3. Capacity and cylinder

Show the larger pneumatic cylinder and injection assembly in context. The frame must make the increased capacity tangible without cropping away the assembly relationship that explains how the machine works.

The copy explains the 50 g shot capacity using verified language and avoids generic AI-generated scale imagery.

### 4. Steel melt zone

Focus on the melt-zone construction and the relevant surrounding components. The image must clarify what is steel and why the construction supports the intended material and duty cycle.

### 5. Dual 350 W heating

Frame the actual two-zone controller and heater system. Controller values, labels, materials, and adjacent geometry must be faithful. Generic glowing coils are not acceptable substitutes for the installed heating system.

### 6. Mold workspace and M10 grid

Show the base, mold working envelope, fixture points, and M10 grid at an angle that makes usable space understandable. The complete relevant plate and grid must remain visible. Dimensions belong in HTML or an accessible diagram layer, not in the Blender pixels.

### 7. 30G versus 50G comparison

Render both machines with matched camera angle, scale reference, lighting, and floor. The comparison must make physical differences visible without relying on exaggerated perspective.

### 8. Configuration and purchase

Use a large complete-machine view with an initial restrained left-right rotation followed by pointer and touch drag-to-rotate interaction. The animation plays once and then releases control. User input must interrupt the intro and take control immediately.

Live Shopify price, variant selector, lead time, factory-visit CTA, and add-to-cart action remain HTML. On narrow layouts the two actions remain side by side when each can retain a 44 px minimum touch target and readable labels; otherwise the layout may stack them without shrinking or clipping text.

## Responsive Keynote Layout

### Shared rules

- Every chapter occupies one effective viewport and advances with one deliberate scroll or swipe gesture.
- The sticky site header and safe-area insets are included in the available-height calculation.
- Active chapters must not produce internal page scrolling, nested scroll traps, horizontal overflow, or multiple wheel gestures before the next chapter.
- Machine media and copy use separate layout regions. Text must not overlap product geometry.
- Background lettering, when used, remains centered in the media region and behind the machine. It is omitted from the dark-red reveal and any slide where it harms technical legibility.
- All interactive controls maintain visible focus, keyboard operation, and at least a 44 px touch target.

### Desktop and wide landscape

- Use a two-column keynote composition with copy and actions on the left and media on the right.
- The machine should consume the available media height while remaining completely inside the frame.
- The product, not empty background, is the dominant visual area.
- Detail slides may let the component extend toward the media-region edges only when an intentional soft fade is part of the shot contract.

### Portrait tablet and mobile

- Media sits above the copy and actions.
- The complete-machine media region receives the largest flexible share of the viewport after reserving room for required copy and controls.
- Supporting text is shortened at constrained heights; verified specifications and primary actions remain visible.
- The media uses the dedicated portrait render and `contain` geometry. Ground shadows, hoses, cylinders, decals, and machine feet must not be clipped.
- Feature copy aligns consistently and must not float on top of imagery.

### Short landscape

- Use a compact two-column composition.
- Reduce descriptive copy before reducing machine legibility, CTA touch targets, or specification readability.
- The machine, primary specification, and primary CTA must fit without collision.

## Motion and Interaction

- Reveal motion is staged and finite. It must not loop indefinitely.
- Product-story animations explain a real mechanical or spatial property; decoration alone is insufficient justification for video.
- Configuration rotation plays one left-right demonstration, returns to the canonical pose, and then remains directly draggable with mouse, pen, or touch.
- Pointer capture and `touch-action` behavior must allow horizontal model manipulation without breaking vertical chapter navigation.
- `prefers-reduced-motion: reduce` skips staged animations, shows the canonical still, and preserves all content and controls.
- Animation-to-static transitions must use the same camera, object transform, framing, and visual bounds so there is no flash or jump.

## Storefront Architecture

- Keep product price, availability, variants, lead time, and cart operations bound to Shopify data.
- Split the current monolithic launch implementation into focused, testable presentation, media, comparison, and purchase responsibilities where required by the implementation plan.
- Retain valid section schema and useful Theme Editor controls.
- Keep translatable copy in locale-backed or merchant-configurable fields.
- Provide semantic headings, descriptive alternative text, keyboard controls, focus styles, and reduced-motion fallbacks.
- Remove storefront references to superseded AI-generated PIMM 50G feature images after Blender replacements are validated.

## Failure Handling

- If a Blender render or animation fails to load, show its verified still fallback without changing layout dimensions.
- If WebGL or drag interaction is unavailable, the purchase slide remains usable with the canonical machine still and all purchase controls.
- If Shopify price or availability cannot be resolved, do not display a stale value baked into content. Preserve Shopify's normal unavailable or error behavior.
- Missing Blender textures, geometry-count drift, invalid alpha output, or clipped proof renders block asset promotion.

## Validation and Acceptance Criteria

### Blender and asset validation

- The corrected source file checksum and modification timestamp remain unchanged.
- The dedicated target file opens successfully and contains the required owned scenes.
- `Machine_50g` retains the expected 481-object source contract unless a reviewed mechanical correction updates the contract.
- No required image, decal, font, or external file is missing.
- Complete-machine proof renders contain the entire machine and contact shadow with measurable clear space on every edge.
- Desktop and portrait renders use their intended cameras and output dimensions.
- Bright renders preserve neutral metal form, readable details, accurate controller displays, authentic decals, and non-black linear shafts.
- Transparent outputs contain a valid alpha channel and no baked page background.
- Render proofs are visually reviewed before storefront integration.

### Storefront validation

- No final slide references the superseded AI-generated PIMM 50G feature assets.
- The dark-to-bright transition preserves machine continuity and does not flash or jump.
- Every chapter advances with one deliberate scroll or swipe on the supported mobile and tablet matrix.
- No active chapter has internal overflow, horizontal document overflow, clipped required content, or media/text overlap.
- Complete-machine images and their shadows are never cropped by `object-fit: cover`, masks, or overflow containers.
- Configuration rotation demonstrates once, accepts mouse and touch drag afterward, and yields immediately to user input.
- Live product price, variant, availability, lead time, booking, and add-to-cart behavior continue to work.
- Keyboard focus, touch targets, alternative text, reduced motion, and high-contrast interaction states pass focused accessibility checks.
- Theme Check, focused unit tests, responsive browser tests, and the repository verification command pass before any storefront commit.

### Responsive viewport matrix

At minimum, validate the complete story at:

- 3840×2160
- 1440×900
- 1024×768
- 820×1180
- 768×1024
- 720×540
- 540×720
- 430×932
- 412×915
- 393×852
- 384×824
- 852×393
- 824×384

The implementation must also remain stable during continuous viewport resizing rather than only at named breakpoints.

## Delivery Slices

1. Create and validate the dedicated Blender product-story project and bright overview proof renders.
2. Produce and approve the technical detail scenes and still fallbacks.
3. Replace the AI-generated storefront media and establish the responsive keynote chapter shell.
4. Add the comparison and interactive configuration rotation.
5. Complete accessibility, reduced-motion, Shopify purchase-contract, and full viewport validation.

Each slice must be independently reviewable and committed only after its applicable Blender, asset, test, and storefront checks pass. Production deployment is explicitly outside this design task unless separately authorized.
