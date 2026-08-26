# PIMM Static Front Render Design

## Scope

Create governed straight-on static hero scenes for the PIMM 30G and 50G. Improve product illumination before generating new low-resolution proofs. Do not create animation rigs, actions, drivers, controller-value animation, native final renders, storefront replacements, uploads, or deployments.

## Project ownership

- `masters/` owns authoritative linked product geometry, approved materials, labels, displays, and stable identities.
- `scenes/stills/` owns one `.blend` per static shot: camera, studio lights, world, compositor, shadow catcher, and render settings.
- `scenes/animations/` is reserved for future shot files; it remains absent or untouched in this slice.
- `rigs/` is reserved for future reusable operation controls and may not be inferred from geometry.
- `scenes/contracts/` binds each shot to machine, master, material library, camera, output dimensions, and purpose.
- `renders/proofs/<proof-id>/` is immutable low-resolution review evidence.
- `renders/final/<release-id>/` is reserved for owner-approved native outputs.

## Static hero composition

Each machine receives a dedicated `pimm-<machine>--hero--front.blend` scene. The camera is centered on the machine front axis, placed near the machine mid-height, and aimed with no horizontal yaw. A small downward pitch of no more than 3 degrees may preserve floor and depth. Lens and distance keep the entire machine inside a portrait 1800 by 2200 native frame.

## Lighting

Use an inspectable product-photography rig: a broad frontal key above camera, softer front fill, two controlled side or rear edge lights, and a neutral world contribution. Black powder-coated and black-oxide parts must retain separation without washing out stainless steel, PEEK, controller digits, or labels. Proofs use the same authored lighting as finals; only resolution percentage and samples differ.

## Governance

Update the canonical PIMM workspace `AGENTS.md` to define master, rig, still-shot, animation-shot, contract, proof, final, and storefront-derivative ownership. Animation work must remain blocked until the owner supplies verified travel, endpoints, timing, display semantics, and values. Install the canonical document into the external Blender workspace and verify hash parity.

## Validation

The checked-in scene authoring configuration is tested before implementation. Reopen and validate each saved `.blend`, verify scene contracts and linked authority, render fresh immutable composition proofs, confirm pass status and unchanged fingerprints, inspect both contact sheets, and request owner approval before any native final or storefront work.
