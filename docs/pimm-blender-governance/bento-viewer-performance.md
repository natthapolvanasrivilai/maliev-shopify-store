# Bento viewer delivery optimization

Observed 2026-09-03. No production deployment or final-render promotion.

## Reproduction and cause

The interactive surface was the r22 review at port 61284. The 9494 Shopify
product preview still contained the approved static configuration image, not a
`pimm-bento-spin` instance. This distinction was verified against rendered DOM
and `pimm-30g-product-story.liquid`; do not claim the review viewer is already
integrated into the product template.

The review fetched approximately 490 KB PNGs, kept six decoded views, and warmed
only two horizontal neighbors. At a simulated 5 Mbps / 60 ms latency, the first
diagonal drag requested 88 positions but displayed just four changed views.
Frames that finished after the pointer moved were correctly rejected, but this
left the machine frozen while the next exact target downloaded.

## Changes

- Lossless WebP review derivatives: all 840 views, same dimensions, all seven
  pitch rows and 120 yaw positions. No resampling, repainting or new rendering.
- 407,613,084 source bytes became 23,181,438 WebP bytes (94.3% smaller).
- Decoded working set uses a 64 MiB pixel budget, up to 96 frames; the 600 x 300
  review uses 93. Large 2400 x 1200 frames retain five instead. In-flight decoding
  and the canvas require additional memory beyond the cache budget.
- Nearby views warm on both axes, with bounded concurrency. Save-data remains
  demand-only. Explicit `decode()` completes before exposing an image.
- During pointer dragging only, the nearest available native view may be shown
  within eight yaw steps and one pitch row. Release resolves the exact target;
  keyboard navigation never approximates a view. No synthetic/interpolated frames.
- Unchanged views skip canvas repaint; gesture bounds are read once per gesture.
- Visibility, teardown, reduced-motion and data-saving safeguards remain intact.

## Measured local results

Final packaged r26, fresh Chromium context, 1433 x 1032 viewport, simulated
5 Mbps and 60 ms latency, same 90-step diagonal drag and return:

| Run | Original r22 visible updates | Optimized r26 visible updates |
| --- | ---: | ---: |
| Initial drag | 4 | 43 |
| Repeated drag | 7 | 80 |

These are changed canvas views, not FPS or field Core Web Vitals. The final
initial drag's largest gap between updates was approximately 253 ms. This is a
major improvement, not a guarantee of stutter-free interaction on slow devices.
No physical low-end mobile device was available; mobile checks used Chromium
viewport/touch emulation.

## Validation and handoff

- `npm run verify`: 157 component tests and 15 route tests passed, one opt-in live
  route test skipped. Theme Check had zero errors and three existing CLI-template warnings.
- Viewer focused tests: 26 passed, including decode completion, memory budget,
  two-axis prefetch, stale-load rejection, nearby native views and exact release.
- Python Bento suite: 101 passed; new packaging workers compile.
- All 840 WebPs decode identically to source 8-bit RGB pixels using Pillow.
  Chromium canvas comparisons at front, oblique and final yaw: zero changed
  channels in three samples.
- r26 browser QA at 1433, 768, 390 and 320 px: keyboard yaw/pitch/Home, reduced
  motion, bounded cache, no controls buttons and no overflow passed; zero page errors.
- Support section QA in English and Thai at the same four widths: three groups,
  one-time entrance, hover replay, live reduced motion and localized support links
  passed. Existing Bucks currency SDK errors are unrelated and unchanged.

Review: `http://127.0.0.1:61284/bento-20260903-r26-smooth-drag-review/`.
Both r22 and r25 remain untouched. r26 references verified proof-only images and
is not a final storefront release. Full web-resolution renders and their product
template integration remain pending; the r24 capacity quality approval is recorded
separately rather than being requested again.
