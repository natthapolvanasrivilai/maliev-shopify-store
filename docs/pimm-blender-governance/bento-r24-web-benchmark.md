# R22 approval and web-render benchmark

Observed 2026-09-03. Local review only; no production deployment or storefront
asset promotion. The owner approved r22, then clarified that renders should be
optimized for the web after the first native frame took roughly 130 seconds.

## Completed evidence

- Exact r22 approval: `bento-r22-approval.json`. Geometry, physical controller
  values, materials, camera animation and the four-component reveal are unchanged.
- R23 native capacity frame 1: 1600 x 2200, 128 Cycles samples, PNG and 32-bit EXR,
  with a hash-bound receipt under external `renders/final/bento-20260903-r23-native-motion/`.
- The full R23 queue was stopped. Only frame 1 completed; no output was deleted.
- R24 diagnostic proofs: 800 x 1100, 48 samples, unchanged adaptive threshold
  0.008 and persistent data disabled. No authoritative scene was saved or edited.
- External evidence: `renders/proofs/bento-20260903-r24-web-benchmark/benchmark.json`.

| Capacity state | Frame | Render and PNG-save time |
| --- | ---: | ---: |
| Solid machine | 1 | 23.98 seconds |
| Reveal transition | 50 | 20.39 seconds |
| Four-component emphasis | 100 | 20.16 seconds |

Source verification and scene/device setup took another 135.71 seconds once,
not per frame. The test does not include final EXR saving or video encoding, so
these figures are not a complete release-time estimate. The benchmark measures
only capacity, not the tooling loop or the 840-view two-axis viewer.

All three PNGs were inspected at native size: no black gauge, valve-label or
controller-face artifact was visible in these samples. Three samples do not
establish temporal stability across a complete sequence. Full-frame motion QA
remains necessary. Identical hold-frame reuse has not yet been implemented.

## Validation and boundary

- Python compilation passed for both new render workers.
- Focused native-worker tests: 4 passed; benchmark tests: 2 passed.
- `py -3 -m unittest discover -s scripts/blender/pimm_production/tests -p 'test_bento*.py'`: 100 passed.
- Source/contract/review hashes and linked product identity were checked before
  rendering; the source scene and linked product were checked again afterward.
- The new output size and sample count are diagnostic, not an approved release.
  The existing governance requires approval of the changed quality settings before
  final rendering. R22 art-direction approval is retained separately.
- No animation queue or follow-up automation is currently running. Neither the
  benchmark nor the single native frame replaces the page's current animation.
