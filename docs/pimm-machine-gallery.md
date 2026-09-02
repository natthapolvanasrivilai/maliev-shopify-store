# 30G machine gallery

The dedicated 30G product template includes an editable gallery immediately before demo booking. The 50G template and commerce/model contracts are unchanged.

## Theme Editor

Open the 30G product template (`product.pimm-configurator`) and its **PIMM machine product** section.

- Add **Gallery video (30G)** or **Gallery image (30G)** blocks. Reorder them to change gallery and viewer order. The first populated item is the large featured tile. Remove blocks to remove media.
- Video: select a full uploaded video, or paste a YouTube link. A full uploaded video takes priority. Clicking opens the full video from the beginning with controls.
- Preview: select a short uploaded video under **Muted preview clip**. Set the start and length (3–15 seconds). The preview is separate from full playback; it never replaces the full video destination.
- The three original YouTube videos have optional bundled, owner-authorized six-second previews. **Use original MALIEV preview** only applies to their exact YouTube IDs. Changing a video cannot accidentally show the old clip. A selected uploaded preview always takes priority.
- Cover image overrides the automatic poster. A custom caption overrides the translated default; translate custom captions using Shopify's content translation tools.
- Images can use an uploaded image or one of the two existing 30G detail renders. Empty blocks are omitted outside the editor.
- The section permits 50 total blocks, including its two model records and any app blocks. Keep model records unchanged.

## Playback and accessibility

Native previews are muted, inline, and loaded only when their media tile enters view. They pause off-screen, in hidden tabs, while the viewer is open, or when **Pause previews** is selected. Reduced-motion and data-saving settings retain still images without loading preview videos. If autoplay is blocked, the still image and full-video link remain usable.

The viewer uses a native modal dialog, keyboard focus containment, Escape to close, previous/next buttons and arrow keys, and restores focus to the originating tile. Images are shown uncropped. All tiles remain ordinary source links when JavaScript is unavailable. The full-media source link remains available if an embedded player is blocked by the visitor's browser or network. YouTube is not embedded or loaded until requested.

English and Thai UI strings are localized. Other installed locales retain explicit English fallback strings, matching the existing PIMM convention.

## Media provenance

`docs/pimm-gallery-media.json` records the source URLs, selected source time ranges, encoding parameters, and SHA-256 for each preview/poster. Preview clips preserve the real portrait footage. No artificial camera movement or generated machine imagery is used.

## Verification

- `npm run verify`: Shopify Theme Check plus theme contracts, media provenance and local navigation suites.
- `node --test scripts/tests/pimm-machine-gallery.test.mjs`: focused gallery rendering, localization, source precedence, autoplay guards and segment-loop checks.
- `py -3 scripts/tests/pimm-machine-gallery.browser.py`: live local-preview desktop/mobile, English/Thai, modal, loop, reduced-motion and data-saving checks. Requires Playwright for Python and its Chromium runtime; server must already be running on port 9494.

This work is for the development theme/local navigation preview only. Nothing in this feature publishes the production theme.
