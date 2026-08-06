# MALIEV Product Image Guidelines

This brief guides Blender, KeyShot, photography, and post-production work for the MALIEV storefront. It is written to support product-launch storytelling while keeping the machine technically credible and easy to evaluate.

## Creative direction

The visual idea is **engineering clarity with product-launch polish**. Every image should make MALIEV feel ingenious, dependable, and approachable.

- Render the real machine accurately. Dimensions, controls, fasteners, materials, clearances, and safety features must match the product being sold.
- Present the machine as compact without making it look lightweight, miniature, or toy-like.
- Prefer clean, confident light over dark, aggressive industrial drama.
- Keep camera behavior, materials, color, and lighting consistent across the complete image set.
- Leave useful negative space for responsive page composition, but never bake headings, labels, prices, or calls to action into a render.
- Use customer-owned molds, parts, names, and logos only with explicit permission.

## Priority production set

### 1. Desktop hero

- Three-quarter front view with the machine facing slightly toward the intended text area.
- Use a clean studio or a believable compact-workshop setting.
- Reserve substantial negative space on one side for a heading, explanation, and CTA.
- Compose intentionally for a wide `16:9` frame rather than cropping a square render.
- Preferred master: `3840 x 2160` pixels or larger.

### 2. Mobile hero

- Create a dedicated portrait composition; do not rely on an automatic crop of the desktop hero.
- Keep the machine readable behind or below short interface copy.
- Preferred master: `2160 x 2700` pixels or larger.

### 3. Isolated product

- Show the complete machine from its clearest three-quarter angle.
- Deliver a transparent-background version.
- If possible, provide the soft grounding shadow as a separate pass.
- Use a square or `4:5` canvas, at least 3000 pixels on the long edge.

### 4. Compact-workshop scale scene

- Place the machine in a credible small workshop, prototyping room, or office workshop.
- Include a person, workbench, doorway, or another familiar reference that communicates honest scale.
- Keep the environment believable and useful rather than empty or excessively pristine.
- Produce both landscape and portrait compositions.

### 5. Engineering details

Produce four to six close views using matching light, color, and camera treatment. Prioritize:

- controls and operator interface;
- injection assembly;
- mold and clamping area;
- heaters and pneumatic components;
- safety and service-access features;
- construction details that demonstrate in-house quality.

### 6. Serviceability and support

- Show an accessible panel, replaceable components, or an organized set of genuine replacement parts.
- Consider an accurate exploded or cutaway render where it improves understanding.
- Communicate that MALIEV builds, maintains, and supports the machine locally; do not turn the scene into a decorative technical diagram.

### 7. Production workflow

- Use a generic MALIEV-owned demonstration mold and non-confidential sample parts.
- Show the relationship from mold to machine to repeatable finished output.
- Avoid customer-owned geometry even when branding has been removed.

### 8. Model comparison

- Render each machine model at the same angle, camera distance, lighting, and scale.
- Use a neutral background and preserve honest physical proportions.
- Provide individual images and a combined lineup composition.

## Blender and KeyShot setup

- Use physically accurate dimensions, materials, and surface finishes.
- Prefer a 70-100 mm full-frame-equivalent lens for primary product views to minimize wide-angle distortion.
- Keep architectural verticals vertical and avoid exaggerated perspective.
- Build the lighting around broad soft sources, controlled highlights, and a restrained contact shadow.
- Avoid excessive bloom, crushed blacks, dramatic colored rim lights, and mirror-like materials that hide construction details.
- Keep the editable Blender project, linked assets, textures, HDRI files, color-management settings, and any fonts together.
- Use consistent object names and collections so individual assemblies can be isolated for future detail or exploded renders.
- Render large archival masters as lossless PNG, TIFF, or OpenEXR. Convert copies for the storefront only after composition and color are approved.
- Export web-facing color in sRGB. Check the final image on an ordinary calibrated or well-behaved sRGB display, not only inside the renderer.
- Where practical, retain transparent-background, object-mask, material-ID, depth, and shadow passes to support future crops and controlled post-production.

## Composition and crop safety

For every critical product scene:

- deliver a clean version without embedded text or graphic labels;
- compose separate landscape and portrait frames;
- keep roughly 15-20% usable space around the machine;
- keep controls, moving assemblies, and meaningful details away from crop edges;
- consider both left-facing and right-facing variants for flexible page layouts;
- inspect the image at small mobile size to confirm the product silhouette and essential details remain legible.

Do not place vague decorative space around a tiny product. The machine should remain the dominant visual subject.

## Optional motion plates

The same scene can support restrained product-launch motion:

- a five-to-eight-second controlled turntable;
- slow camera passes across two or three meaningful engineering details;
- a short, technically accurate exploded-component sequence;
- a machine rotation on a plain or transparent background;
- a mechanism demonstration when it accurately represents safe operation.

Use smooth, deliberate movement. Avoid constant spinning, dramatic fly-throughs, excessive depth of field, and animation that hides the technical information. Export a strong still frame for every animation so visitors who prefer reduced motion receive equivalent content.

## Review checklist

Before an asset is approved, verify:

- the rendered machine matches the sellable configuration;
- scale and perspective are honest;
- materials do not hide important details;
- no customer intellectual property is visible;
- no unsupported performance claim is implied;
- the image works in its intended desktop and mobile crops;
- alternative text can describe the useful information in one concise sentence;
- a reduced-motion still exists for any animated scene;
- the editable source and rendering dependencies are archived together.

## Recommended starting sequence

Create these first because they unlock the largest storefront improvements:

1. Desktop hero.
2. Mobile hero.
3. Isolated transparent machine.
4. Compact-workshop scale scene.

After those are approved, build the engineering-detail, serviceability, workflow, comparison, and motion sets from the same locked materials and lighting system.
