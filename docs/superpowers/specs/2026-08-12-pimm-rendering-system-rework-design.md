# PIMM 30G/50G Rendering System Rework

## Purpose

Rebuild the active Blender rendering pipeline for the MALIEV PIMM 30G and PIMM 50G storefront assets so that stills and animations match or exceed the supplied KeyShot 2023 references. The new output must preserve accurate machine geometry, mechanisms, decals, framing, and storefront behavior while correcting material realism, reflection control, exposure balance, and transparent ground shadows.

This is a rendering-system change, not a geometry redesign or storefront-layout redesign.

## Approved visual direction

### Bright studio

Use a calibrated bright product studio for:

- Every PIMM 50G still and animation.
- Every normal PIMM 30G product-story still and animation.
- Static posters derived from those animations.

The bright studio must resemble the supplied KeyShot references: high-key and neutral, but with retained highlight texture, readable shadow-side detail, clean metallic gradients, and a soft physical ground shadow.

### Dark studio exception

Only the PIMM 30G landing-page startup animation may use a dark studio. It must use the same approved material library as the bright scenes. Dedicated reflection cards and fill lighting must keep the machine readable before the presentation transitions into the bright studio.

No PIMM 50G asset may retain a dark or red keynote-stage treatment.

## Rendering architecture

Create a shared calibrated Blender rendering module used by both product families. It owns:

- Physically distinct material definitions.
- Bright-studio lighting and reflection geometry.
- The 30G dark-startup lighting variant.
- Cycles render and color-management settings.
- Transparent physical shadow catching.
- Alpha, exposure, material, camera, and animation validation helpers.

Product-specific builders retain responsibility for scene composition, camera framing, product mechanics, controller states, and animation timing. They consume the shared rendering module rather than duplicating lighting or material tuning.

Existing immutable source files remain read-only. Versioned calibrated Blender masters and proof outputs are created separately. Storefront asset filenames are replaced only after proof approval and final validation.

## Material system

The material library must distinguish the following finishes visibly and physically.

### CNC-milled aluminum

- Bright metallic response with controlled directional machining variation.
- Crisp bevel highlights and readable engraved details.
- No chalky, powdery, or sandblasted appearance.
- Surface variation must remain subtle at full-machine distance and become visible in close-ups.

### Cast aluminum

- Used for the pneumatic-cylinder end caps and any verified cast components.
- Slightly broader and softer reflections than CNC-milled parts.
- Subtle casting variation without turning the surface dark gray, porous, or powder-coated.

### Polished shafts and chrome hardware

- Continuous cylindrical highlight bands that describe roundness.
- Controlled dark reflection lines are permitted, but no shaft may read as a nearly black column.
- High polish must remain distinct from satin sheet metal and milled plates.

### Brushed or satin sheet metal

- Restrained directional finish for verified housings and enclosures.
- Moderate roughness and elongated reflections.
- Visually distinct from polished shafts and cast/milled aluminum.

### Other materials

- Rubber, black plastics, blue pneumatic tubing, painted springs, fasteners, gauges, controller glass, illuminated digits, printed labels, engravings, and decals retain independent physically appropriate materials.
- Controller digits, pressure-gauge faces, AIRTAC labels, warning graphics, and MALIEV engravings must remain legible at their intended framing.
- Existing verified vendor branding must remain intact and must not be replaced with generated overlays.

## Lighting and color management

### Bright studio rig

Use large neutral reflection sources positioned to create intentional gradients across polished and milled metal. The rig must include:

- A broad key source.
- Balanced shadow-side fill.
- Separate edge/rim definition where needed.
- White and dark reflection cards sized and placed for shafts, cylinder walls, and enclosures.
- Neutral world contribution sufficient to prevent black recesses without flattening form.

The accepted rig must not reproduce the former extreme key-to-fill ratio or negative-exposure look. Color management must preserve both highlight and shadow latitude, with no broad clipped metal regions and no crushed machine components.

### Dark startup rig

The 30G startup environment remains deliberately dark. It uses the same materials but lowers the environment and visible stage illumination. Reflection strips and targeted fill keep critical machine geometry readable. The existing startup-to-bright choreography remains unchanged unless a render-parity adjustment is required.

### Scene-specific adjustment limits

Individual cameras may receive bounded light repositioning to accommodate close-ups, but may not redefine material values, color-management policy, or the core studio ratios. Any exception must be explicit in the builder and covered by a proof.

## Transparent ground shadow

Every ground-bearing shot uses a physical Cycles shadow catcher aligned with the verified machine contact plane.

The master output must contain:

- Transparent RGBA around the product.
- Complete machine alpha.
- A soft contact shadow directly beneath the feet.
- A broader, lower-density ambient shadow that describes weight without looking painted.
- Sufficient transparent canvas around the full shadow to prevent clipping.

The final alpha must not contain an opaque studio floor, baked white background, rectangular plane edge, artificial radial disc, or side/bottom feather mask. Shadow behavior must be validated over white, light gray, dark gray, and checkerboard composites.

## Render-quality standard

Master stills and animation frames use Cycles with:

- GPU rendering when a verified supported backend is available; deterministic CPU fallback otherwise.
- Adaptive sampling with a final threshold appropriate for glossy metal.
- Sufficient samples to remove denoiser smearing, mottled reflections, and unstable animation noise.
- A denoiser configured for glossy product rendering.
- High-bit-depth lossless intermediate output before website conversion.
- Transparent film and a render pipeline that preserves the shadow catcher.

Website WebP and alpha WebM files are derived from approved masters. Encoding must preserve alpha, color, sharp edges, fine decals, animation duration, and endpoint frames.

## Proof-gated workflow

No active storefront asset is replaced before proof approval.

### PIMM 30G proof package

- Bright-studio full-machine hero.
- Material close-up showing CNC-milled aluminum, cast aluminum, polished shafts, housing metal, tubing, fasteners, and decals.
- Dark-startup key frames covering the darkest state, machine illumination, and the final transition-aligned state.

### PIMM 50G proof package

- Bright-studio full-machine hero.
- Material close-up covering the same finish families.
- Hero-animation and heating-animation key frames, including poster-matching endpoints.

Every proof master is composited over white, light gray, dark gray, and checkerboard backgrounds for review.

### Proof acceptance criteria

A proof passes only when:

- The complete intended subject and ground shadow fit within the alpha canvas without clipping.
- Alpha contains no opaque background or visible shadow-plane boundary.
- Soft contact and ambient ground shadows remain visible on both light and dark composites.
- Broad metallic highlights retain tonal detail.
- Shadow-side machine components remain readable.
- CNC-milled, cast, brushed/satin, and polished finishes are visibly distinct.
- Shafts show controlled continuous highlights rather than black columns.
- Decals, gauges, labels, engravings, and controller digits are legible.
- Poster and corresponding animation endpoint match in camera, scale, material, lighting, exposure, and alpha bounds.
- Approved animation mechanics and timing are unchanged.
- No temporal noise, denoising flicker, or reflection pumping is visible in animations.

## Active asset scope

### PIMM 30G

Rebuild the customer-facing media referenced by `templates/product.injection-molding-machine.json`:

- Landing startup/hero desktop and mobile video/poster.
- Shot-capacity desktop and mobile animation/poster.
- Temperature-controller desktop and mobile animation/poster.
- Cylinder desktop and mobile poster.
- Direct-operation desktop and mobile animation/poster.
- Pressure-regulator desktop and mobile poster.
- Fixture-grid desktop and mobile poster.
- Scale/capacity desktop and mobile poster.
- Configuration-turntable desktop animation/poster and mobile poster.

There are 22 unique active asset files in this template contract. The exact inventory is frozen in the implementation plan before rendering begins.

### PIMM 50G

Rebuild the active bright-studio media referenced by `sections/maliev-pimm-50g-launch.liquid`:

- Hero.
- Capacity.
- Melt zone.
- Heating controls.
- Mold space.
- Purchase.

Also replace the four active 50G next-model files referenced by `templates/product.injection-molding-machine.json` with newly named bright-studio derivatives:

- Desktop animation and matching poster.
- Mobile animation and matching poster.

The 30G template references are updated only after these replacement files pass the same proof, alpha, endpoint-parity, and responsive presentation gates as the dedicated 50G page media.

Also rebuild the dedicated 50G hero and heating Blender animation scenes and their proof frames so future animation exports remain consistent with the stills. These scenes use only the bright studio.

### Excluded assets

- Unreferenced legacy 30G exports such as older `v2`, `v4`, and `v10` files are not rerendered solely because they remain in `assets/`.
- Unreferenced retired 50G keynote/red-stage media is not rerendered. The four currently referenced red-stage next-model files are replaced by new bright-studio derivatives before the old files are retired.
- Original KeyShot references, CAD sources, and immutable Blender sources are never overwritten.
- Storefront layout, copy, commerce behavior, localization, and interaction mechanics are outside this rendering-system change unless an asset-contract adjustment is unavoidable.

## Replacement and recovery strategy

1. Freeze the active source-to-output manifest and source hashes.
2. Build the shared material and studio module against versioned target blends.
3. Render and review representative proof packages.
4. Lock accepted material, light, color, camera, shadow, and quality parameters.
5. Propagate the locked system to all active still and animation scenes.
6. Render high-bit-depth masters and generate optimized storefront derivatives.
7. Validate all contracts and visual outputs.
8. Replace active storefront files while preserving their expected filenames and dimensions where required by Liquid/template contracts.
9. Run browser and responsive regression checks before deleting or archiving any superseded output.

Existing outputs remain recoverable through Git and the versioned render directories until the replacement is verified.

## Automated validation

The implementation must add or extend tests that verify:

- Immutable source file hash, timestamp, expected object count, transforms, and material slots.
- Every required versioned scene, camera, collection, light, reflection card, material, and shadow catcher exists.
- Material-family assignments match the approved map.
- Render engine, transparency, bit depth, color-management, sampling, denoising, and device settings do not drift.
- Poster scenes remain unanimated.
- Animation mechanics, frame ranges, and required material/controller keyframes remain correct.
- Poster and animation endpoint parity.
- Transparent RGBA is present and alpha bounds are finite.
- Complete-machine and complete-shadow margins satisfy the canvas-clearance threshold.
- Shadow alpha has no hard rectangular boundary.
- Highlight and shadow luminance remain inside approved proof-derived thresholds.
- WebP/WebM derivatives match required dimensions, duration, alpha, and endpoint frames.
- Every active Liquid/template asset reference resolves.

## Storefront validation

After asset replacement, run:

- Blender builder/contract tests for 30G and 50G.
- Full active proof render verification.
- Media metadata and alpha validation.
- Existing PIMM 30G regression and viewport suites.
- Existing PIMM 50G product-page, motion, and responsive browser suites.
- Shopify Theme Check and the repository verification command.
- Desktop, tablet, portrait-mobile, and short-landscape browser checks for image completeness, shadow clearance, poster/video parity, reduced motion, zero horizontal overflow, commerce controls, and focus behavior.

No asset is declared complete based solely on a successful render command. Native-resolution visual inspection and multi-background alpha composites are mandatory.

## Commit boundaries

Implementation should remain reviewable through coherent commits:

1. Shared calibrated rendering module and contract tests.
2. PIMM 30G proof scenes and accepted pipeline integration.
3. PIMM 50G proof scenes and accepted pipeline integration.
4. Full active asset regeneration and optimized derivatives.
5. Storefront asset replacement and browser regression hardening.

No push or deployment is included without separate explicit authorization.
