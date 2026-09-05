# Bento r12 local-preview release

Released locally on 2026-09-03 after the owner's existing r10 orbit approval and explicit r12 lighting approval. No production deployment or push.

## What is live

- The 30G `Inspect pneumatic controls` tile now loads the completed native Blender camera orbit: 2400 x 1200, 24 fps, 192 frames, 8 seconds, H.264/yuv420p BT.709, 5,377,728 bytes. It autoplays muted and loops only while visible. There are no playback or pause buttons.
- The always-present native poster remains the fallback for reduced motion, data saving, failed playback and loading. No video is requested when reduced motion is enabled initially.
- The white configuration tile uses the approved r12 lower-exposure native render at 2400 x 1200, exported losslessly with decoded RGB pixel equality. Its existing subtle border and rounded corners remain.
- Capacity, tooling and configuration are still images; only controls has an authored orbit. The 50G page is unchanged.

The missing-animation cause was incomplete asset integration: the storefront still contained an `img` without the orbit element or its script. The final encoded video, custom element and 30G-only deferred script are now connected in `pimm-30g-product-story.liquid` and `maliev-pimm-machine-product.liquid`.

## Provenance

- `bento-r12-white-detail-approval.json` pins the approved configuration scene, proof and contract.
- `pimm-bento-r11-motion.v1.json` records the completed approved orbit alongside the earlier still set.
- `pimm-bento-r12-assets.v1.json` retains that orbit and the other three approved stills, replacing only configuration. Asset, scene, approval and source hashes are checked by the release tooling and regression tests.

## Validation

- Python compilation passed for the changed production helpers and tests. The affected native-render/release suite passed 59 tests; the five r12 tests passed again after adding the approval-change-during-export regression.
- `npm run verify` passed: Theme Check zero errors, 128 component/asset tests and 15 route tests passed. One opt-in live route test was skipped. Three pre-existing Shopify CLI dependency warnings remain.
- Independent Chromium checks passed on English and Thai canonical 30G routes at 390, 768 and 1440 pixels: actual decoded playback, dimensions, muted looping, no controls/buttons, offscreen unloading, reduced-motion static fallback and no horizontal overflow. Initial reduced-motion navigation made zero orbit MP4 requests. An intermittent preference-emulation timeout on the first Thai run did not recur in the completed three-width rerun.
- The exact user `products_preview` URL also passed autoplay and an eight-second loop-boundary check. The existing user tab was not forcibly reloaded.
- Playback and configuration screenshots were visually inspected. FFprobe decoded all 192 frames and confirmed the encoded resolution, frame rate, duration and color metadata.
- The additional Shopify skill validator could not run because its plugin lacks `@shopify/theme-check-common`; the repository's own Theme Check succeeded. There is no separate compiled-theme build target.

Unrelated site templates, checkout and production were not changed or release-tested by this scoped local-preview slice.
