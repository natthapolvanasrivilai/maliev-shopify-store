# PIMM Editorial Product Photography Expansion

**Date:** 2026-08-30  
**Status:** Owner-approved direction; implementation review pending  
**Scope:** Preview-resolution Blender campaign expansion for the PIMM 30G and 50G product page

## Objective

Expand the existing governed PIMM render campaign beyond isolated catalog imagery. The new work must present the machines through deliberate commercial product-photography sets that use supporting props, environmental context, directional lighting, and designed shadows while preserving the machines as the dominant, physically grounded subjects.

The first delivery is a four-concept preview pack. It does not authorize native-resolution finals, storefront publication, production deployment, or animation work.

## Creative direction

The approved visual language draws from recurring product-photography patterns found in Pinterest references:

- directional hard light and geometric shadows;
- layered set geometry and restrained plinth-like forms;
- dark environments with controlled rim highlights;
- environmental workshop storytelling;
- contextual still-life props that explain product use.

Reference categories:

- <https://www.pinterest.com/ideas/studio-hard-light-still-life-shadow-photography-textured-backdrop/956699407811/>
- <https://www.pinterest.com/ideas/light-and-shadow-product-photography/903364410509/>
- <https://www.pinterest.com/ideas/dark-product-photography-lighting/941850823444/>

References define composition and lighting principles only. Their images and proprietary set assets must not be copied into the MALIEV project.

## Preview concepts

### 1. Architectural daylight

- Full grounded machine in an eye-level three-quarter composition.
- Warm-grey textured wall and floor with a soft tonal transition.
- Directional sun or focused area light through a procedural window-frame gobo.
- Distinct geometric cast shadow that does not obscure the feet, controls, gauge, decals, or mold area.
- 85 mm full-frame-equivalent camera, verticals kept upright, no wide-angle exaggeration.

### 2. Dark engineering

- Full grounded machine against graphite and near-black surfaces.
- Narrow side and rear strips create readable rim highlights around the cylinder, posts, hose, control enclosure, base, and feet.
- Restrained MALIEV-blue accent light may separate the pneumatic hose and stainless edges, but must not recolor materials.
- One shaped key produces an intentional elongated shadow with readable—not crushed—underside detail.
- 135 mm full-frame-equivalent camera at machine eye level.

### 3. Modern workshop

- Full grounded machine in a clean, credible small-production workshop.
- Supporting elements may include a workbench, tooling cart, mold halves, calipers, resin-pellet containers, technical drawings, and restrained wall storage.
- Props must not intersect the machine, hide any foot, imply unsupported machine accessories, or carry third-party branding.
- If a person is included, they must be a Thai technician wearing a plain black shirt or a correctly legible white `MALIEV` wordmark on the left chest. A small, back-turned, or oblique figure uses no shirt text.
- 85 mm environmental camera with foreground and background depth but no staged clutter.

### 4. Process still life

- Machine remains identifiable while molds, finished molded parts, resin pellets, inspection tools, and a technical drawing establish the production workflow.
- Foreground props create depth without covering the nozzle, mold area, controllers, gauge, valve, or feet.
- 135–200 mm full-frame-equivalent camera with controlled depth of field.
- Lighting emphasizes material contrast among stainless steel, black finishes, blue pneumatic hose, polymers, and tooling.

## Preview deliverables

Create exactly four new preview-resolution renders for the first review round:

| Preview | Machine | Orientation | Minimum preview size | Camera |
| --- | --- | --- | --- | --- |
| Architectural daylight | 30G | landscape | 1280 × 720 | 85 mm |
| Dark engineering | 50G | landscape | 1280 × 720 | 135 mm |
| Modern workshop | 50G | landscape | 1280 × 720 | 85 mm |
| Process still life | 30G | portrait | 900 × 1125 | 135–200 mm |

Each preview must have its own Blender scene revision and output directory. A labelled contact sheet must show all four concepts, shot identifiers, machine, focal length, f-stop, render engine, scene hash, and asset-provenance status.

## Asset policy

- Prefer procedural scene geometry for walls, floors, gobos, flags, acrylic panels, and simple blocks.
- Prefer locally authored props when practical.
- External assets require a direct downloadable source, exact license, creator/source URL, local relative path, SHA-256, and intended shot identifiers before they may enter a scene.
- Prefer CC0 sources, primarily Poly Haven: <https://polyhaven.com/license>.
- BlenderKit assets may be used only after the exact asset license is captured: <https://www.blendkit.com/docs/licenses/>.
- Account-gated, scraped, unverifiable, or Pinterest-hosted scene assets are forbidden.
- External assets remain scene-local support. They must never be linked into or saved over either PIMM master or the shared material library.

## Scene and master boundaries

- `PIMM-30G-MASTER.blend`, `PIMM-50G-MASTER.blend`, and `PIMM-MATERIAL-LIBRARY.blend` remain immutable inputs.
- Each preview scene links the exact published master collection and retains stable object/material identities.
- Props, environment geometry, cameras, lights, gobos, shadow catchers, and compositing are owned by the preview scene.
- All four feet must resolve to one common contact plane. No machine may float or use a visible ground plane in a transparent derivative.
- The first review may use opaque environmental frames. Any later transparent derivative must retain shadow-only alpha without visible floor pixels or clipped shadow boundaries.

## Lighting and rendering

- Blender Cycles is the render authority for previews and finals.
- AgX color management is required; exposure compensation starts at `0.0` and is changed only through a recorded scene revision.
- Lighting rigs differ materially between concepts rather than reusing one five-light studio arrangement with renamed profiles.
- Metallic highlights must retain texture and edge contrast without clipping.
- Lower-machine fill must keep the base plate, feet, underside, and shadow transition readable.
- Shadows are compositional elements but may not hide required product evidence.
- Denoising, sample count, bounce limits, and color transforms are recorded in each preview manifest.

## Acceptance criteria

Every preview must demonstrate:

- complete machine framing appropriate to the concept;
- all four feet contacting one plane;
- no prop intersection or accidental occlusion;
- no clipped product or intentional shadow;
- readable white metal, dark finish, base underside, gauge, controller segments, and AirTAC artwork where visible;
- physically credible scale, camera height, perspective, and depth of field;
- materially distinct lighting from the other three concepts;
- unchanged master and material-library hashes before and after render;
- complete external-asset provenance with no unsupported asset.

The owner reviews the four preview images and may approve, reject, or combine directions. No native final render or storefront integration begins until the exact selected preview revisions are explicitly approved.

## Validation

- Validate campaign and scene contracts before authoring.
- Reopen each authored scene in a fresh Blender process.
- Verify current four-foot geometry from linked masters.
- Render previews without cache reuse.
- Inspect every preview at 100 percent and produce image-bound evidence.
- Run focused composition, authoring, proof, and provenance tests.
- Record broader-suite failures separately when they predate or do not exercise these four preview scenes.

## Excluded work

- Animation sequences and controller/plunger motion.
- Native-resolution final renders.
- Shopify theme integration or asset replacement.
- Production deployment.
- Changes to master geometry, material assignments, decals, or controller values.
