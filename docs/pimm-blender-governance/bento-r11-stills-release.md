# Approved native bento still release — 2026-09-03

The owner approved the r11 white configuration proof. The local 30G story now
uses four native-size lossless Blender stills recorded in
`assets/pimm-bento-r11-stills.v1.json`:

- Capacity and tooling: approved r10 lighting renders.
- Controls: actual first native frame of the approved r10 controls orbit.
- Configuration: approved r11 white-studio scene, rendered at 2400 × 1200,
  128 samples. Product geometry and materials remain unchanged.

Each asset retains its individual approval, saved-scene, source-image and encoded
asset hashes. Encoding verifies identical decoded RGB pixels; no resize, fake
shadow, background overlay or contrast filter is applied. Previous releases are
retained. Portrait cards retain their matching layout heights.

## Validation

- Python compile checks succeeded for the changed renderer and exporter modules.
- White approval/export regression tests: 17 passed.
- Native r10 renderer/encoder regression tests: 32 passed.
- `npm run verify`: 127 render/component tests and 15 local-route tests passed;
  one opt-in live-route test skipped. Theme Check reported zero errors and three
  existing warnings inside installed Shopify CLI dependency templates.
- Live canonical product route: English and Thai at 390, 768 and 1440 pixels;
  all six checks passed. Four current release images loaded at their declared
  native widths, portrait heights matched, no horizontal overflow or empty
  grid row, separate video gallery retained. White configuration inspected in
  the desktop screenshot.
- No compiled theme build target exists; Theme Check, component/asset tests and
  live rendering cover the applicable template boundary.

## Pending motion release

The full 192-frame native orbit is still rendering. This release deliberately
does not wire its video component or an incomplete video. The controls poster
comes from frame one so the eventual transition can preserve framing. After the
full orbit validates, encode it with Blender's bundled FFmpeg and add an immutable
motion release preserving the new white configuration still. Do not run an older
whole-set exporter that would replace the white configuration with the gray shot.

Only local preview has changed. No production publication or push was performed.
