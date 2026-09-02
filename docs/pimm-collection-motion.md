# PIMM collection motion revision

The collection comparison now uses a separate, native Blender animation for each
machine instead of swapping three still views. Each clip contains 72 rendered
frames at 24fps (three seconds), easing front → left 12° → right 12° → front.
Hover, keyboard focus, or Compare starts one pass. Exit, completion, playback
failure, or reduced-motion preference restores the static front poster.

## Render provenance

Current high-density release: `maliev-pimm-collection-motion-20260902-r02`.
The original `r01` assets remain available for rollback. The new native frames,
posters and videos are 1440×1920, twice the original width and height. Depth of
field is disabled for motion so controls and rear edges stay in focus. Camera
position, lighting, physical shadows and the 72-frame movement are unchanged.
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

The collection uses three existing local type families with distinct roles:
Antonio for model names, Chakra Petch for headings and technical measurements,
and IBM Plex Sans/Thai for prose, availability and prices. Prices use semibold
proportional lining numerals. No new font assets or external font requests are
introduced; a collection-only Chakra Petch face enables both Latin and Thai.

`pimm-collection-price.liquid` formats the governed full-machine price in satang
as grouped baht, with the translated unit after the amount: `120,000 บาท` in
Thai and `120,000 THB` in English. Whole prices omit `.00`; nonzero satang are
preserved. Cards, server-rendered dossiers and the interactive model payload
use this same formatter. Product prices, deposits and checkout are unchanged.

## Layout and validation

At 1280×720 and larger, the comparison and compact legal footer occupy one
viewport. Two poster cards sit left; the introduction and selected-model dossier
sit right. Smaller windows and mobile keep natural document scrolling.

```powershell
npm run verify
py -3 -m unittest discover -s scripts/blender/pimm_production/tests -p 'test_collection*.py'
py -3 scripts/tests/pimm-collection-viewport.py --url <preview-url> --motion
py -3 scripts/tests/pimm-collection-viewport.py --url <preview-url> --motion --pixel-density 2 --check-native-resolution
$env:PIMM_COLLECTION_PREVIEW_URL = '<preview-url>'
node --test scripts/tests/pimm-collection-responsive-browser.test.mjs
```

This revision does not publish the draft unified product, assign a collection
template, or deploy the theme. The product preview remains the validation route.

Initial r01 verification on 2026-09-02: `npm run verify` passed all 68 tests and Theme
Check reported no errors (three existing warnings inside Shopify CLI dependency
templates). The collection renderer suite passed 13 tests. The live viewport
probe passed English and Thai at 1280×720, 1440×900, 1536×864, 1920×720,
1920×1080, and 390×844, including both model videos and reduced motion.
No separate compiled build target exists for this Liquid theme.

High-density r02 verification on 2026-09-02: `npm run verify` passed all 70 tests;
Theme Check reported zero errors and the same three Shopify CLI dependency
warnings. The renderer suite passed 15 tests. The 2× pixel-density probe passed
all twelve English/Thai viewport cases above, with no source upscaling (largest
physical-pixel/source-pixel ratio: 0.971 at 1920×1080) or desktop overflow.
The full responsive/interaction/localization browser acceptance test passed;
its no-URL sentinel was intentionally skipped because a preview URL was supplied.
Price font assertions passed in-browser. Both encoded videos are under 1 MB.
Fresh screenshots were visually reviewed; `git diff --check` passed.

Typesetting follow-up on 2026-09-02: 73 regression tests passed, including exact
localized price strings, fractional satang, all 31 locale contracts and matching
server/interactive prices. English/Thai browser acceptance passed at seven sizes,
including 1280×720 and 640×360 reflow, with loaded font-role checks and contained
desktop dossier content. The existing twelve-case 2× image-density probe also
passed. Text contrast checks measured 6.67:1 for muted text on the page and
15.11:1 for light body text in the dossier. Theme Check had zero errors and the
same three dependency warnings. The Shopify skill's separate validator could not
start because its installed package lacks `@shopify/theme-check-common`; the
repository's Shopify CLI Theme Check and executable Liquid tests ran instead.
