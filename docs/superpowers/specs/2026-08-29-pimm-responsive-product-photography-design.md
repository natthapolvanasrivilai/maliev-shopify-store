# PIMM Responsive Product Photography and Landing Page Design

**Date:** 2026-08-29

**Status:** Owner-approved direction; written specification pending final owner review

**Scope:** Governed 30G/50G Blender stills, one atomic storefront media release, and the local Shopify PIMM configurator presentation

## Purpose

Replace the current mixed-generation, eight-image PIMM storefront library and its clipping-prone hero presentation with a complete responsive product-photography system. The system must make the machine the dominant visual subject, preserve physically credible grounding, and give buyers enough visual evidence to understand the machine family without turning the page into a specification dashboard.

This design supersedes the hero composition and render-programme portions of `2026-08-28-pimm-engineering-console-product-page-design.md`. It also supersedes every deposit or checkout reference in the earlier unified-product specifications. The storefront shows full machine price, availability, production lead time, model selection, and demo-session conversion; it does not mention or accept a deposit.

## Current defects and evidence

- The current hero source is a portrait `1800 x 2200` alpha asset reused across desktop, tablet, mobile, and zoomed layouts.
- The released 50G PNG alpha bounding box is `[0, 0, 1800, 2200]`. Non-zero alpha reaches every canvas edge, so the shadow is already clipped before CSS renders it.
- CSS compensates with oversized image widths, negative inline margins, overflow visibility, and breakpoint-specific ordering. These rules cause collisions between the machine, model selector, heading, and evidence rail.
- The storefront manifest combines hero release `r23` with overview, engineering, and tooling releases `r15` through `r20`. The next presentation must resolve one atomic approved campaign release instead of mixing generations.
- Fresh read-only verification confirms both current masters contain four independently identifiable nylon feet on one Z=0 contact plane. The 30G and 50G spreads are each `0.000009355`, below the `0.0002` scene-unit tolerance. The apparent floating or uneven result is therefore a shot, shadow, occlusion, and composition defect rather than a current master-contact defect.

## Success criteria

- Desktop, tablet, and mobile heroes use separately authored camera compositions with matching native aspect ratios.
- Every hero shows the complete machine, all visible feet, and the complete soft shadow with no alpha touching the output edge.
- No product image overlaps the navbar, title, selector, price, evidence, or CTA at any supported viewport or at 200% browser zoom.
- The page uses at least 22 purposeful product photographs. Each image either establishes the machine, compares models, explains a component, or establishes workshop context.
- Model selection updates every model-specific hero, editorial, and detail image without borrowing media from the other model.
- One photo-led bento remains, but the page as a whole is not a tile grid.
- The primary and final conversion action is `Book a demo session`. No storefront copy, control, schema, or state mentions a deposit.
- New storefront assets resolve only one immutable approved release manifest.
- No production theme, product publication, push, or deployment occurs in this scope.

## Visual direction

The physical scene is a precision machine photographed in a bright controlled industrial studio during a Thai factory product shoot: neutral daylight, broad metal reflections, readable control artwork, a grounded base, and enough architectural structure to feel manufactured rather than rendered in a void.

The page uses MALIEV's existing black, white, Signal Blue, Focus Yellow, and restrained cool-neutral system. The visual voice is direct, mechanical, and assured. Product photographs carry the atmosphere; cards, decorative gradients, glass effects, and oversized specification tiles do not.

Hero media is transparent and portable. Editorial and contextual images may use physical cycloramas, plinths, reflection cards, workbenches, trays, fixtures, material samples, and unbranded workshop props. Props must support scale and use context, never obscure the machine or imply that optional equipment is included.

## Governed shot library

Every row below is one `.blend` file and one JSON scene contract. Render scenes link the approved `PIMM_PUBLISHED` collection and own only shot-specific cameras, lights, reflection cards, world, shadow catcher, compositor, render layers, and output configuration.

### Responsive alpha heroes — 6 shots

| Machine | Shot ID | Output | Composition |
| --- | --- | --- | --- |
| 30G | `pimm-30g--hero--desktop` | 2560 x 1440, 16:9 | Machine right of center with protected HTML-copy area on the left |
| 30G | `pimm-30g--hero--tablet` | 2048 x 1536, 4:3 | Centered machine with balanced side clearance |
| 30G | `pimm-30g--hero--mobile` | 1440 x 2560, 9:16 | Machine in the upper visual field with selector/CTA clearance below |
| 50G | `pimm-50g--hero--desktop` | 2560 x 1440, 16:9 | Machine right of center with protected HTML-copy area on the left |
| 50G | `pimm-50g--hero--tablet` | 2048 x 1536, 4:3 | Centered machine with balanced side clearance |
| 50G | `pimm-50g--hero--mobile` | 1440 x 2560, 9:16 | Machine in the upper visual field with selector/CTA clearance below |

Each hero produces a float EXR master with isolated product and physical-shadow passes plus a composited transparent PNG and WebP. The ground is invisible. The machine silhouette keeps at least 8% clearance from every relevant edge and the complete shadow keeps at least 12% clearance. The alpha bounding box must remain strictly inside the canvas.

### Full-machine editorial studies — 4 shots

| Machine | Shot ID | Output | Composition |
| --- | --- | --- | --- |
| 30G | `pimm-30g--editorial-bright--three-quarter` | 1800 x 2250, 4:5 | Bright seamless studio, eye-level three-quarter view |
| 30G | `pimm-30g--editorial-dark--three-quarter` | 1800 x 2250, 4:5 | Dark architectural studio with controlled rim separation |
| 50G | `pimm-50g--editorial-bright--three-quarter` | 1800 x 2250, 4:5 | Bright seamless studio, eye-level three-quarter view |
| 50G | `pimm-50g--editorial-dark--three-quarter` | 1800 x 2250, 4:5 | Dark architectural studio with controlled rim separation |

### Component photography — 8 shots

| Machine | Shot ID | Subject |
| --- | --- | --- |
| 30G | `pimm-30g--controls--macro` | Physical controller segments and enclosure |
| 30G | `pimm-30g--pneumatics--macro` | Regulator, gauge, valve, fittings, tubing, gauge decal, and AirTAC artwork |
| 30G | `pimm-30g--tooling--macro` | Nozzle, platen, fixture grid, and usable tooling zone |
| 30G | `pimm-30g--base-feet--macro` | Base plate, springs, posts, and all relevant foot contacts |
| 50G | `pimm-50g--controls--macro` | Physical controller segments and enclosure |
| 50G | `pimm-50g--pneumatics--macro` | Regulator, gauge, valve, fittings, tubing, gauge decal, and AirTAC artwork |
| 50G | `pimm-50g--tooling--macro` | Nozzle, platen, fixture grid, and usable tooling zone |
| 50G | `pimm-50g--base-feet--macro` | Base plate, springs, posts, and all relevant foot contacts |

Each component shot is 1800 x 2250, 4:5. Detail cameras use a realistic working distance, restrained depth of field, and a 135–200mm lens. Decision-relevant markings and the complete component group remain sharp.

### Family and workshop context — 4 shots

| Shot ID | Output | Composition |
| --- | --- | --- |
| `pimm-30g-50g--comparison--desktop` | 2560 x 1440, 16:9 | Aligned family pair with both machines fully grounded |
| `pimm-30g-50g--comparison--mobile` | 1440 x 1800, 4:5 | Vertically composed family pair with unambiguous scale relationship |
| `pimm-50g--workshop--wide` | 2560 x 1440, 16:9 | 50G in a clean unbranded workshop environment |
| `pimm-50g--workshop--portrait` | 1800 x 2250, 4:5 | Workshop detail with spatial context and protected copy area |

No person is introduced without an owner-approved MALIEV-owned or compatibly licensed Thai-person source. No third-party equipment carries MALIEV branding. Unbranded props do not imply inclusion with the machine.

## Camera, lighting, and material contract

- Blender 5.2 Cycles with GPU configuration, adaptive sampling, OpenImageDenoise, and persistent data.
- 36mm sensor with perspective cameras; no orthographic full-product presentation.
- 85mm at approximately f/11–f/16 for desktop full-machine views.
- 135mm at approximately f/11 for tablet, mobile, and three-quarter product studies.
- 135–200mm at approximately f/8–f/11 for component photography.
- Camera height remains within 14% of machine height from the shot's explicit focus target; complete-product working distance is at least three machine heights where the studio permits.
- AgX Medium High Contrast, exposure `0`, gamma `1`.
- Existing pinned `studio_kontrast_04_4k.exr` at contracted rotation and calibrated strength unless a proof demonstrates a superior licensed replacement.
- Broad key, fill, rim, lower bounce, and dedicated reflection geometry. White aluminum retains form; stainless, black oxide, powder coat, brass, PEEK, tubing, and nylon remain distinguishable.
- Physical shadow catcher only. No painted shadow, radial mask, arbitrary exposure repair, finite catcher edge, or tilted floor compensation.

## External asset policy

Use locally authored geometry first. A small number of CC0 Poly Haven materials, HDRIs, or unbranded workshop props may be added only when they materially improve the contextual shots. Every external item must be recorded before use with source URL, asset/version identifier, license, local path, SHA-256, and intended scenes. Paid assets, account-gated downloads, cloud AI, generative repainting, AI upscaling, and unlicensed resources remain prohibited.

Downloaded props are scene-local support assets. They never enter a machine master, alter product geometry, replace decals, or receive MALIEV branding.

## Blender file and release architecture

- Masters remain `masters/PIMM-30G-MASTER.blend`, `masters/PIMM-50G-MASTER.blend`, and `masters/PIMM-MATERIAL-LIBRARY.blend`.
- New still scenes live under `scenes/stills/` with matching contracts under `scenes/contracts/`.
- Repeatable scene creation and validation live in checked-in Blender Python. Scripts never overwrite a master.
- Proofs live under one immutable `renders/proofs/<generation-id>/` campaign batch with labelled white, checker, dark, full-composition, and 100% detail evidence.
- Exact owner approval records bind master, material library, scene, script, external asset, render-setting, and proof hashes.
- Native outputs publish atomically under one new `renders/final/<release-id>/` campaign release. The release manifest includes all 22 logical shots and responsive WebP derivatives. Partial or mixed-generation storefront promotion is forbidden.

Approval of this design authorizes scene and proof creation. It does not authorize native final rendering. Native finals require approval of the exact generated proof batch as required by the Blender workspace.

## Shopify landing-page architecture

### 1. Responsive machine-first hero

Use a semantic `<picture>` per model with desktop, tablet, and mobile native sources. The global navbar overlays the same white visual field without its own border. The hero uses explicit grid areas; the media, decision copy, model selector, commercial facts, and CTA never share an overlapping absolute-position layer.

Desktop and tablet fill the first viewport where content fits without clipping. Mobile order is navbar, machine image, model selector, `Book a demo session`, then the compact product title and supporting copy. Image wrappers use contracted aspect ratios and `object-fit: contain`; negative image margins and unbounded overflow are prohibited.

### 2. Model decision rail

The 30G/50G selector remains a real fieldset and radio group. It shows model name and full machine price. A compact adjacent summary shows availability and production lead time. The CTA is demo-only. No product form, deposit control, or deposit copy is rendered.

### 3. Photo-led engineering bento

Retain one asymmetric bento. Its dominant cell uses the selected model's bright three-quarter editorial image. Four supporting cells use the selected controls, pneumatics, tooling, and base/feet photographs with concise HTML captions. Numeric specifications remain semantic HTML beside the relevant photograph rather than being repeated as large dashboard cards.

### 4. Family comparison

Use the dual-machine composition with an accessible 30G versus 50G comparison. Explain capacity, melt temperature, mold envelope, and workshop fit in one direct comparison structure. The image establishes relative scale; Shopify/metafield data remains the numeric authority.

### 5. Workshop ownership story

Use the wide and portrait workshop scenes to explain Thai manufacturing, demonstrations, installation, parts, warranty, and support. Avoid invented operation claims, mold behavior, accessories, or animation.

### 6. Detail gallery and final demo close

Provide a selected-model detail gallery that can be inspected without horizontal page overflow and without hover-only access. Finish with one confident `Book a demo session` action and support contact context. Do not repeat full price or specifications more than needed to preserve the selected-model decision.

## Model-state and media data flow

The existing exact two-variant `Model` contract remains. Liquid serializes stable selected-model media descriptors for the six hero roles and six selected-model story roles. JavaScript applies state to existing semantic nodes; it does not rebuild the page or invent media.

- Only the initially selected model's mobile/tablet/desktop hero candidate is eligible for eager loading and high fetch priority.
- Below-fold selected-model images are lazy and async decoded.
- Alternate-model sources are not fetched eagerly. They become eligible after direct model intent or selection.
- Shared comparison and workshop assets are lazy.
- Model changes preserve focus, update the URL variant, update every model-specific media slot and alt text, and announce selected model, full price, and availability.
- A bounded opacity transition of at most 180ms is allowed. Reduced motion swaps instantly.
- Missing model-specific media fails closed to the same model's approved responsive hero; it never borrows the other model or a legacy asset.

## Performance budgets

- Hero WebP: target at or below 500KB per responsive source, with alpha integrity retained.
- Below-fold WebP: target at or below 350KB each unless 100% artwork legibility requires a documented exception.
- Explicit dimensions or aspect ratios on every image to prevent layout shift.
- No initial download of both complete model libraries.
- No JavaScript image carousel dependency. Native picture, semantic figures, and the existing controller remain sufficient.
- The local responsive acceptance run must show no page-owned console errors, no horizontal overflow from 320px upward, and no media/control overlap.

## Failure handling

- Missing responsive hero source: render the same model's nearest approved aspect source with `object-fit: contain`, never crop it and never use another model.
- Missing below-fold shot: omit its figure and preserve the surrounding narrative; do not show an empty decorative card.
- Invalid or unavailable model contract: keep demo contact available, hide unavailable technical claims, and show a concise status.
- Asset hash or release mismatch: fail storefront asset verification and block promotion.
- Proof shadow touches an edge, foot contact fails, artwork is unreadable, or a scene links stale master state: reject that shot before owner review.

## Validation

### Blender and release gates

- Run `verify_foot_contact_plane.py` against both masters before proof generation.
- Reopen every saved `.blend` independently.
- Validate one linked approved master, no private product mesh, no localized product material, exact controller values, exact decals, camera/sensor/lens/f-stop contract, and managed output paths.
- Check product and shadow alpha bounding boxes against required safe margins.
- Generate white, checker, and dark composites plus 100% crops for regulator, gauge, AirTAC artwork, controller segments, black materials, tooling, and feet.
- Validate external asset provenance and checksums.
- Require owner approval of the exact proof batch before native finals.
- Validate one atomic release manifest and responsive WebP hashes before repository integration.

### Theme and browser gates

- Add contract tests that reject deposit copy or controls, legacy asset references, mixed releases, missing responsive picture sources, negative hero-image margins, and overlapping hero regions.
- Run `npm run verify`, focused Node tests, Impeccable detection, JSON parsing, JavaScript syntax, and `git diff --check`.
- Browser-test 30G and 50G in English and Thai at 320x800, 390x844, 768x1024, 1024x900, 1440x900, and 1920x1080.
- Verify 200% browser zoom, keyboard operation, reduced motion, model switching, URL state, alternate-media loading, missing-media fallback, and zero horizontal overflow.
- Capture and inspect hero, bento, comparison, workshop, detail, and final CTA evidence at desktop, tablet, and mobile widths.

## Implementation sequence and commit boundaries

1. Add campaign scene contracts, external-asset provenance schema, alpha-safe validators, and failing tests.
2. Author the 22 one-shot Blender scenes from linked corrected masters and validate scene ownership.
3. Generate one governed proof batch and labelled contact sheets; stop for exact owner proof approval.
4. Render and publish one authorized native campaign release, then export responsive WebP derivatives and the immutable consumer manifest.
5. Integrate the atomic asset release into the PIMM template, section, snippets, locales, controller, and responsive styles.
6. Run full Blender, repository, browser, accessibility, performance, and visual validation.
7. Commit coherent validated slices. Do not push, deploy, publish the product, or modify production theme state.

## Acceptance criteria

The slice is complete when:

- all 22 contracted scenes and contracts exist and validate;
- both masters still pass the exact four-foot contact-plane gate;
- every hero has an interior alpha bounding box and complete shadow clearance;
- the exact proof batch is approved and one atomic final release is published;
- the storefront references only that release and no legacy PIMM media;
- desktop, tablet, mobile, zoomed, English, and Thai layouts have no media/control overlap or clipping;
- the photo-led bento, comparison, workshop story, detail gallery, and demo close are present;
- no storefront deposit reference exists;
- all applicable automated and visual checks pass;
- local commits exist, while production remains untouched.
