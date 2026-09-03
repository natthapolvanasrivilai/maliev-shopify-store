# Technical-reveal render stability

The 30G capacity reveal combines three Cycles view layers. On the local Blender
5.2 / OptiX render path, advancing this scene's timeline with
`scene.render.use_persistent_data = True` intermittently produced black faces on
the gauge, valve and controller assembly. The defect existed in native PNGs,
before video encoding or storefront playback.

## Controlled comparison, 2026-09-03

The first 29 frames have identical camera and reveal settings. Rendering those
frames from the same r17 scene at 25% resolution and 32 samples produced:

| Render setting | Frames with changes over 10 channel levels | Maximum channel difference |
| --- | ---: | ---: |
| Persistent data enabled | 6 / 29 | 230 / 255 |
| Persistent data disabled | 0 / 29 | 1 / 255 |

Repeating a single frame without advancing the timeline did not reproduce the
defect. This isolates the working correction to cross-frame persistent render
data in this configuration; it does not establish Blender's underlying internal
failure mechanism or implicate every scene using persistent data.

## Corrected generation

- `blender_bento_stable_reveal_proof.py` derives r21 from the immutable r17 scene.
- Only persistent render data is disabled. Product meshes, materials, transforms,
  lighting, camera animation, compositor, four opaque components and 20% ghost
  opacity remain unchanged.
- Saved scenes retain full-resolution intent; review PNGs remain native 25%
  proofs. Do not use these proofs as storefront final assets.
- The worker verifies the approved source chain, its own frozen hash, the source
  animation contract, all 556 linked product meshes and each output frame.
- Packaging rejects a capacity contract that does not explicitly disable
  persistent data. r22 combines the corrected capacity loop with the unchanged
  tooling loop and two-axis rotation proof.

Regression checks live in `test_bento_motion_review.py`. For rendered validation,
compare the stationary frame ranges 1–29 and 174–192 together, and 78–125 as a
separate reveal hold. No face should change to black within either group.
Inspect moving transitions and the encoded loop in the browser as well.

The completed r21 proof decoded successfully for all 192 frames. Both stationary
groups (48 frames each) had zero pixels changing by more than 10 channel levels;
their maximum channel difference was 1/255. The ending hold matched the starting
hold, including the loop seam. Native transition frames 50 and 150 were also
visually inspected without black gauge or valve faces.

Keep previous generations immutable. Any subsequent render-setting change needs
a new generation and exact-proof review under the existing production gates.
