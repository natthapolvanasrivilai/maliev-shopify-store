# 30G bento lighting and camera-orbit review

Status: proof-only, pending owner approval. No storefront assets, Liquid, CSS,
JavaScript, production theme, master geometry, or product materials changed.

The owner requested stronger machine-image contrast and a subtle, slow camera
orbit for Inspect pneumatic controls, with a static reduced-motion alternative.
Impeccable motion guidance limits animation to this one informative view.

## Exact review generations

- Four stills: `bento-20260903-r10-lighting` (capacity, controls, tooling,
  configuration), under `renders/proofs/<generation>/<shot>/still.png`.
- Camera-only animation: `bento-20260903-r10-orbit`, under
  `renders/proofs/<generation>/controls/frame-0001.png` through `frame-0192.png`.
- Each scene has a new immutable file in `scenes/stills` or `scenes/animations`
  and a hash-bound receipt in `scenes/contracts` with `approval: pending`.
- The animation review folder contains the lossless native-proof-size animated
  WebP, lighting contact sheet, accessible local review page, and encoding receipt.
- r07/r08 lighting tests darkened the backdrop too far. r09 restored its ambient
  light. All exploratory generations remain untouched and are not release inputs.

## Lighting and camera scope

The worker reopens the exact hash-verified owner-approved r06 scene, links the
published 30G master and shared materials, and changes only scene-local lighting,
AgX look, and (for the animation shot) the camera. AgX High Contrast replaces
Medium High Contrast; exposure remains 1.1 and ambient strength remains 0.65.
The large front reflection emitter drops from 2.0 to 0.65, key light increases
to 180 W, fill drops to 6 W, and background wash increases to 1600 W.

The physical floor, product materials, decals, labels, 300/300 controller
geometry and four foot contact positions remain unchanged. No CSS filters,
image repainting, image masks or synthetic shadows are involved.

Camera orbit: sinusoidal +/-3 degrees about the controls at 24 fps, 192 frames
(eight seconds). Frame 193 is the matching loop endpoint, not an extra encoded
frame. Machine movement is explicitly excluded. No mechanical-motion authority
is inferred from this camera-only request.

Native scene intent remains 100% resolution and 128 samples. Review renders use
25% resolution, 32 samples and denoising; they must never become storefront
derivatives. The orbit review is 600 x 300, not final-resolution quality.

## Validation and release boundary

- Source approval, scene, master, material-library, HDRI and locked-tool hashes
  are verified by the existing final-worker dependency preflight.
- Every authored scene is independently reopened before proof rendering.
- Read-only animation audit verifies only the camera has animation, all 556
  product objects stay stationary, frame endpoints close, and fps/range match.
- Python compilation and focused bento proof/orbit tests cover the camera
  envelope, cadence, proof-only boundary and review's reduced-motion handling.
  Eight tests pass. Review-page browser checks pass at 1440 and 390 pixels,
  including actual changing animation frames, pause/play, live reduced-motion
  preference changes, no animation request when initially reduced, and no overflow.
- The adjacent `bento-r10-review-manifest.json` pins the five exact contracts and
  the animation/contact-sheet hashes for the owner's review decision.
- `npm run verify` passes with 117 render tests and 15 route tests; one opt-in
  live-route test is skipped. Three existing Shopify CLI dependency warnings
  remain; there is no separate compiled-theme build target.
- The broader Blender governance suite is not rerun for this isolated proof
  worker; its previously recorded external mapped-drive fixtures are excluded.

Next gate: owner approval of these exact proofs. Only then render native stills
and video, verify full-resolution quality and poster parity, and integrate one
immutable release into the local storefront. The intended component will load
motion only with no reduced-motion preference, pause outside the viewport or
hidden tab, expose pause/play, and restore the matching static frame on live
preference changes. These storefront behaviors are not implemented by this
proof-only slice and must be browser-tested during integration.
