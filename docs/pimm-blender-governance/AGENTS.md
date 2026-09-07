# PIMM Blender Production Workspace

## Authority and operating boundary

Follow this authority order. When sources conflict, the higher authority wins:

1. Immutable STEP sources and import manifests.
2. Owner-approved machine and material documentation.
3. Published 30G or 50G master.
4. Shared material library.
5. Scene contract and approval manifest.
6. Checked-in render scripts.
7. Ad-hoc AI instructions.

Missing or ambiguous machine behavior blocks work; do not guess. Preserve the active user session and unrelated Blender processes. Never mutate authoritative STEP sources, product meshes, decals, controller values, or approved manual material assignments through automation.

## Approved local tools

- Blender 5.2, Cycles, AgX, OpenImageDenoise, the Blender compositor, and render passes.
- Blender Python, the Python standard library, and locally licensed OpenImageIO when locked.
- The locally installed free BlenderMCP implementation.
- Locally authored procedural textures, studio light fields, and reflection cards.
- MALIEV-owned or compatibly licensed reference images.

Every external tool or asset used in production must be recorded in the free-tools lock with version, source, license, and local checksum where applicable.

## Prohibited tools and pixel changes

Paid add-ons, subscriptions, and cloud AI are prohibited. Cloud render enhancement, AI upscaling, generative repainting, AI-created controller digits, decals, labels, geometry, or machine parts, and unlicensed textures, HDRIs, fonts, or artwork are prohibited. Final product pixels may not be generatively repainted, upscaled, or materially altered by AI.

## Masters, materials, and render scenes

The authoritative masters are `masters/PIMM-30G-MASTER.blend`, `masters/PIMM-50G-MASTER.blend`, and `masters/PIMM-MATERIAL-LIBRARY.blend`. Masters own imported geometry, stable object identity, approved product material assignments, machine-local artwork, decals, displays, labels, neutral transforms, and `PIMM_PUBLISHED`. Shared physical finishes remain linked from the material library; branding, serial labels, and controller artwork remain local to the applicable machine.

Manual material assignments are authoritative. AI may inspect, report, or suggest, but may not overwrite an approved assignment. Render scenes link the applicable approved `PIMM_PUBLISHED` collection and may own only shot-specific cameras, physical lights/reflection cards, shadow catchers, scene-local rigs, render layers, output formats, and paths. A private machine mesh, localized linked material, approved-material override, or unapproved master revision fails scene validation.

## Project layout and shot ownership

Keep one shot per `.blend`; never turn one scene file into a mutable all-purpose render project.

- `masters/` owns published product geometry, approved material assignments, labels, displays, stable identities, and neutral product transforms.
- `rigs/` is reserved for reusable, owner-approved mechanical controls, constraints, endpoints, and actions. A rig links a published master and may not duplicate or reshape product geometry.
- `scenes/stills/` owns static-shot files. Each file links one published machine and owns only its camera, studio lighting and reflection cards, world, compositor, shadow catcher, render layers, and output configuration.
- `scenes/animations/` is reserved for future animation-shot files. Each animation shot links the applicable published master and approved rig, then owns shot camera, lighting, selected action or NLA sequence, frame range, and output configuration.
- `scenes/contracts/` binds every still or animation shot to exact master, material-library, camera, output, and—when applicable—rig and animation authority.
- `renders/proofs/<proof-id>/` contains immutable low-resolution review evidence rendered from the authored final-intent scene state.
- `renders/final/<release-id>/` contains only native outputs authorized from an approved exact proof generation.

Name files `pimm-<machine>--<purpose>--<view>.blend` for stills and `pimm-<machine>--<operation>--<view>.blend` for animation shots. Do not silently reuse or rename a three-quarter scene as a front scene; create a distinct shot file and contract. Storefront derivatives are generated only from an approved final release and never from proof, working, unapproved, or mutable scene paths.

Animation remains blocked until the owner supplies verified motion travel, endpoints, timing, sequence, controller-display semantics, and allowed values. Temperature animation must state whether each number is a setpoint, measured value, or both. Do not infer operation from geometry, existing keyframes, photographs, or typical machine behavior. Static render authorization never authorizes animation work.

## Machine semantics

The 30G controller renders physical seven-segment `300/300`; the 50G controller renders physical seven-segment `350/350`. Illuminated segments use the applicable green or red emissive material while inactive segment geometry remains physical. Flat text, font objects, composited text, or image overlays cannot replace the controller geometry. Unknown motion, controller, mold, platen, injection, pneumatic, hose, cable, or endpoint behavior remains blocked until owner approval.

## BlenderMCP and file safety

Before a connected-session modification, inspect file path, dirty state, active scene and view layer, unit settings, library links, current selection and active object, and relevant object/material/collection identities. BlenderMCP defaults to read-only inspection. It may explore scenes, select objects, collect structured diagnostics and screenshots, and execute controlled checked-in scripts.

Do not overwrite a master without explicit authorization; auto-publish a collection; delete datablocks or files without an approved cleanup manifest; terminate unrelated Blender processes; assume names, materials, transforms, or values; or treat a successful save as validation. Repeatable mutations belong in checked-in Blender Python. Reopen every saved `.blend` and validate it independently.

## Render, approval, cleanup, and reporting gates

Preflight blocks rendering for a changed source hash, stale master link, local product copy, unauthorized material override, unapproved material state, wrong controller value, unknown animation transform, missing license provenance, unmanaged output, stale approval, active archive consumer, incomplete archive manifest, or forbidden dependency. Proofs use contracted low resolution and owner-review contact sheets. Each native-resolution rendering requires owner approval of the exact proof generation; any geometry, material, camera, lighting, world, compositor, animation, output-size, or setting change invalidates approval.

Never permanently delete files. An owner-approved cleanup batch may move only validated, non-authoritative, non-consumer assets to the read-only sibling archive at `M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders-archive\pending-delete\<date>-<batch-id>\` while preserving relative paths, hashes, sizes, and timestamps. Report validation evidence before completion: paths, stable IDs, changed datablocks, material IDs, outputs, hashes, gates, and failures. Validation never silently repairs product data.
