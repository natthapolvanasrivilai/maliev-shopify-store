# PIMM collection motion revision

The collection comparison now uses a separate, native Blender animation for each
machine instead of swapping three still views. Each clip contains 72 rendered
frames at 24fps (three seconds), easing front → left 12° → right 12° → front.
Hover, keyboard focus, or Compare starts one pass. Exit, completion, playback
failure, or reduced-motion preference restores the static front poster.

## Render provenance

Release: `maliev-pimm-collection-motion-20260902-r01`.
The release manifest records master hashes, all native frame hashes and angles,
and the final video/poster hashes. The original master files remain unchanged.
Lighting and ground shadows come from the physical Blender Cycles studio scene.
There is no still-frame synthesis, shadow compositing, or image transformation.

Run `blender_collection_card_render.py` with each approved master, its expected
SHA256, `--motion --samples 128 --scale 1.24`, and a new output directory. Once
both model sidecars exist, run:

```powershell
py -3 scripts/blender/pimm_production/finalize_collection_motion.py --render-dir <native-frame-directory> --asset-dir assets
```

The finalizer requires Pillow, ffmpeg and ffprobe. It verifies every native
frame, encodes H.264 at 24fps without interpolating frames, checks the encoded
dimensions/duration/frame count, and converts the first frame to lossless WebP.
It refuses to overwrite an existing release.

## Layout and validation

At 1280×720 and larger, the comparison and compact legal footer occupy one
viewport. Two poster cards sit left; the introduction and selected-model dossier
sit right. Smaller windows and mobile keep natural document scrolling.

```powershell
npm run verify
py -3 -m unittest discover -s scripts/blender/pimm_production/tests -p 'test_collection*.py'
py -3 scripts/tests/pimm-collection-viewport.py --url <preview-url> --motion
$env:PIMM_COLLECTION_PREVIEW_URL = '<preview-url>'
node --test scripts/tests/pimm-collection-responsive-browser.test.mjs
```

This revision does not publish the draft unified product, assign a collection
template, or deploy the theme. The product preview remains the validation route.

Verified locally on 2026-09-02: `npm run verify` passed all 68 tests and Theme
Check reported no errors (three existing warnings inside Shopify CLI dependency
templates). The collection renderer suite passed 13 tests. The live viewport
probe passed English and Thai at 1280×720, 1440×900, 1536×864, 1920×720,
1920×1080, and 390×844, including both model videos and reduced motion.
No separate compiled build target exists for this Liquid theme.
