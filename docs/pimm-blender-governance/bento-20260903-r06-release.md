# 30G full-tile bento release

Owner approved the exact `bento-20260903-r06` proof generation on 2026-09-03.
The adjacent approval JSON pins all four original proof contracts. Native renders
reopen the approved saved scenes and alter only the output destination; no product
geometry, material, camera, lighting, world or compositor changes are made.

Native PNGs and receipts live under the production asset root at
`renders/final/bento-20260903-r06-native2/`. An earlier capacity PNG without a
completed receipt remains in `renders/final/bento-20260903-r06/`; it is not a
release consumer and was neither deleted nor used for the storefront.

The final worker restores process-local OPTIX/CUDA device preferences, which are
not saved in `.blend` files. This matches the proof worker's backend selection.
The saved scene's GPU setting is not changed. Blender emitted a HIP discovery
warning while successfully using the available alternative backend.

## Storefront boundary

- Four native-size lossless WebP files, totaling about 1.5 MB.
- Capacity: 1600 x 2200; tooling: 1600 x 2000.
- Controls and configuration: 2400 x 1200 each.
- `assets/pimm-bento-assets.v1.json` binds each derivative to its native PNG,
  proof, scene, master and exact owner approval hashes.
- A single full-tile image sits behind readable text. No masks, painted ground,
  image fades, synthetic shadows or product-pixel edits.
- English and Thai compact captions keep narrow layouts clear. Other locales
  retain English fallback text, consistent with the existing gallery keys.
- Existing workshop stills, gallery videos, hero and 50G product remain unchanged.
- Local development preview only; no production push or deployment.

## Validation

- Python compile checks and four focused bento renderer tests pass.
- All four native Blender jobs completed; authority hashes were checked before
  and after rendering. Lossless exports retain native dimensions.
- `npm run verify` passes: Theme Check has zero errors and three pre-existing
  warnings in bundled Shopify CLI template files; render and route suites pass.
- Focused story/asset suite: 13 tests pass, including hashes, dimensions and
  locale key parity. The route suite has 15 passes and one opt-in live test skip.
- Actual English and Thai local product routes return HTTP 200. Browser checks
  at 320, 390, 768 and 1440 pixels load all four renders with no horizontal
  overflow. Individual tiles were visually inspected; 1024px English was also
  checked during integration.
- The repository's wider Blender governance suite previously encountered
  mapped-drive approval fixture failures and was stopped. It was not represented
  as passing or rerun for this isolated render integration.
- There is no separate compiled theme build target. Theme Check, asset tests,
  route tests and the running Shopify development renderer cover this slice.

Proof and native scene sources remain immutable. A future camera, lighting,
material or output-size change requires a new proof generation and approval.
