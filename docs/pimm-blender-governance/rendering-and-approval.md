# PIMM Rendering and Approval

## Gate 0: preflight

Verify STEP/master/material identity, scene dependencies, linked geometry and materials, units and scale, controller values, animation endpoints, output path, generation ID, and absence of paid/cloud dependencies. Any failure blocks rendering.

## Gates 1–3: proofs and owner decision

Composition proof uses 12.5–25% contracted resolution, 16–32 Cycles samples, denoising, and white/checker/dark composites. Material and lighting proof normally uses 25% resolution, 32–64 samples, masks, targeted crops, quantitative tests, and a labelled contact sheet. The owner may approve, reject, or annotate individual shots. Record proof/contact-sheet, STEP, master, material-library, scene, script, and settings hashes plus decision, notes, owner, and timestamp.

Changing geometry, material, camera, lighting, world, compositor, animation, output size, or render settings invalidates approval.

## Gates 4–5: finals and release

Only an approved exact proof state may render native resolution. Use Cycles adaptive sampling (normally 128–256 maximum samples), float EXR master, and the required transparent PNG, WebP, or video deliverables. AI upscaling, cloud enhancement, generative texture replacement, and product repainting are prohibited.

Release QA verifies original-resolution visual inspection, white/checker/dark composites, physical controller value, dimensions, alpha mode, shadow containment, edge continuity, static/poster/animation endpoint parity, provenance hashes, and consumer filename/format. Consumers resolve only one immutable approved release manifest; proof, rejected, temporary, archived, and mixed-generation outputs are invalid. Output directories are immutable after approval.
