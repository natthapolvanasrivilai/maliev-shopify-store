# PIMM collection motion revision

The collection comparison now uses a separate, native Blender animation for each
machine instead of swapping three still views. Each clip contains 72 rendered
frames at 24fps (three seconds), easing front → left 12° → right 12° → front.
Hover, keyboard focus, or Compare starts one pass. Exit, completion, playback
failure, or reduced-motion preference restores the static front poster.

## Cinematic focus

Cards remain stationary, with transparent borders and no hover shadow. On a
fine-pointer hover, the other card's media eases to 68% opacity over 420ms;
its model name and price use the existing readable muted ink. The active render
stays at full opacity. Supporting copy is not faded. No lighting, ground shadows,
render assets, or video timing are modified. Keyboard focus provides the same
emphasis with the visible focus outline retained. Touch does not leave a sticky
hover effect; reduced motion removes emphasis transitions and video playback.
Browsers without `:has()` retain the normal cards and existing rotation behavior.

Validated in the English/Thai seven-viewport browser matrix, including real CDP
mouse movement across both cards, unchanged card bounds, pointer exit, keyboard
focus, dynamic reduced-motion preference and emulated mobile touch. Screenshots
of both hovered models were captured and English/Thai examples visually reviewed.
The suite passes with zero navigation retries (one intentional no-URL sentinel
skip). All 74 repository regression tests pass. Theme Check reports no errors and
the same three existing warnings inside Shopify CLI dependency templates. A new
exact Shop Pay production-domain CSP signature is excluded only on the local
product-preview route, alongside the existing preview-only exemptions.
Physical mobile-device and Firefox/Safari testing were not performed. No shared
theme styles, commerce records, localization strings, or unrelated routes changed.

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

The desktop detail panel reads model/recommendation → full-width machine price →
availability/lead-time pair → capacity/mold-envelope pair → temperature/pressure
pair. Its action group is anchored to the bottom: the full-width machine link
leads, followed by equal-width factory-visit and support text links with a quiet
separator. DOM reading/focus order, translated labels, optional-link settings,
and destination URLs remain unchanged. At 900px height and above the panel uses
larger model/price type and more space; 720–800px desktops compress vertical
padding instead of clipping controls. Inline mobile dossiers are unchanged.
Panel-layout validation: 76 regression tests passed via `npm run verify`; Theme
Check has zero errors and the same three dependency warnings. The English/Thai
ten-viewport browser suite passed (one intentional sentinel skip, zero retries),
including full-width price, bottom-aligned action hierarchy, 44px targets,
support destinations, keyboard, touch and reduced motion. Desktop English,
short-desktop Thai and mobile English screenshots were reviewed. Impeccable's
layout detector returned no findings before or after the scoped CSS changes.

At 1280×720 and larger, the comparison and compact legal footer occupy one
viewport. Two poster cards sit left; the introduction and selected-model dossier
sit right. Smaller windows and mobile keep natural document scrolling.

For desktop heights from 720–900px, the bottom controls use an 8px edge inset,
44px button targets, a 4px price-to-button gap and 22px price type. This keeps
the controls below the r02 machine-foot guide at 84% of source image height.
The image still fills the entire card interior, without repositioning, shrinking,
cropping its shadows, or changing the native animation. The shortest 1280×720
layout has 9.13px clearance from that guide to the price. Taller desktop windows
retain the roomier original control offsets.

The preview initially served older r01 stills and pre-typesetting price markup
despite the current worktree. Restarting the local CLI with an explicit worktree
`--path` and reloading the user's tab restored r02 1440×1920 posters/clips and
the current localized prices. Browser clearance assertions also pin the r02
asset URL and native dimensions so stale framing cannot silently pass.
Clearance validation: `npm run verify` passed all 75 tests (zero Theme Check
errors, three existing dependency warnings). The English/Thai browser suite
passed at ten viewport sizes, including 1440×900 and the 900/901px layout
boundary, with no navigation retries. In-app 1280×720 and saved 1440×900
screenshots were visually reviewed. No new renders or production deployment.

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

## CTA color audit and correction — 2026-09-02

Scope: collection card and dossier CTAs only, including both inline dossiers.
The user explicitly requested audit and fixes together. No imagery, commerce
contract, destination, translation, header or card-animation changes were made.

Anti-pattern verdict: pass for the corrected CTA surface. It uses the existing
brand colors, restrained outlines and color-only transitions, without lift,
shadows or competing filled colors. The original cascade assigned color by
breakpoint instead of action role; role variables now own the default state and
one shared rule owns hover and keyboard focus.

| Audit dimension | After / 4 | Evidence and scope |
| --- | --- | --- |
| Accessibility | 3 | Hover labels measure 4.58:1; keyboard focus retains its separate outline; this is not a whole-page WCAG certification. |
| Performance | 4 | CSS-only color transitions; no new JS, assets or layout animation. |
| Responsive design | 4 | Ten viewport sizes per locale pass; all seven visible CTA targets are at least 44px in both dimensions at 1280×720 and 390×844. |
| Theming | 3 | Shared role variables work on existing light cards and dark dossiers; this fixed page palette is not a new theme-switching system. |
| Anti-patterns | 4 | Consistent black/transparent defaults, one blue interaction color, no decorative motion. |
| Total | 18/20 | Excellent within the audited CTA scope. |

Findings: zero P0/P1, two P2 and one P3, all corrected:

- **P2 / Theming:** the later dossier rule forced its main CTA white, contrary
  to the requested black/transparent hierarchy. It is now transparent with a
  bright outline on the dark panel; card primaries remain black. No WCAG claim
  applies to this hierarchy preference. Refinement lane: `impeccable colorize`.
- **P2 / Theming:** a more-specific desktop support rule suppressed the shared
  blue background. Removed that override so support, compare and configure
  actions all become blue with white text, including keyboard focus. Refinement
  lane: `impeccable colorize`.
- **P3 / Accessibility:** the reduced-motion block omitted button transitions.
  Added every collection CTA, retaining visible focus and instantaneous color
  feedback. Refinement lane: `impeccable polish`.

Positive contracts retained: semantic links/buttons, localized labels, exact
configure/support destinations, bottom-anchored dossier actions and full-width
primary action. No further CTA fix is queued after the polish/verification pass.

Validation: `npm run verify` passed all 77 tests. Theme Check reported zero errors
and the same three existing Shopify CLI dependency-template warnings; no compiled
build target exists. The responsive browser suite passed (one acceptance test,
one intentional no-URL sentinel skip, zero navigation retries), covering English
and Thai at ten sizes each. New real-pointer and keyboard checks cover all seven
CTA roles on desktop and mobile-width layouts, default/hover/focus colors,
contrast, target size, no hover size shift and reduced motion. Existing touch,
commerce-selection, no-JavaScript, localization and destination checks pass.
Screenshots in `.codex-tmp/pimm-cta-color-audit` were visually reviewed.
`git diff --check` passed. Impeccable's detector reported only the pre-existing
`PIMM Chakra Petch` font alias absent from DESIGN.md; typography was left unchanged.

## Collection-to-configurator navigation — 2026-09-02

The collection previously emitted the development product's plain public URL.
That discarded both the draft preview access key and the `pimm-configurator`
template selection. The reported destination was a 404; the authenticated local
reproduction instead showed Shopify's generic product template and deposit price.
Neither was the intended machine configurator.

Server-rendered card, inline-dossier and desktop-dossier URLs now explicitly use
`view=pimm-configurator` with the governed model variant. The matching JSON payload
uses that same route. Client validation permits only that optional view value,
requires it to match the trusted server link, and retains same-origin, product-path,
positive-variant and duplicate/unknown-query rejection.

On the dedicated product-preview collection only, the validated controller builds
actual anchor hrefs from the current localized `products_preview` path, its single
opaque preview key, the configurator view and the selected model ID. The server
must first confirm that the preview product matches the collection's product.
The key is read at runtime, never committed, never added to public product URLs,
and never copied to support/external links. Unrelated query parameters and hashes
are discarded. Original hrefs are restored before disconnect/reconnect validation.
Normal published-product fallback links remain server-rendered and need no JS;
draft-preview key preservation requires JavaScript because Liquid does not expose
arbitrary request query parameters. This change does not publish the draft, assign
product/collection templates in Admin, change redirects or deploy the live theme.

Validation: `npm run verify` passed 81 tests, with zero Theme Check errors and the
same three existing dependency-template warnings. New executable Liquid and
controller cases cover explicit configurator URLs, both models, locale preservation,
preview guards, malformed/duplicate keys, untrusted payloads, query agreement and
reconnection. The Shopify skill's separate validator could not start because its
installed package lacks `@shopify/theme-check-common`; the repository validator ran
successfully instead. The collection/configurator runtime boundary is additionally
covered by actual browser clicks and Back navigation, not just href inspection.

Final browser acceptance passed: one acceptance test, one intentional no-URL
sentinel skip, zero navigation retries. It includes the ten-size English/Thai
layout matrix, eight actual collection-to-configurator clicks (30G/50G × EN/TH ×
desktop card/mobile inline dossier), correct destination model and locale, all
five machine-link hrefs, and browser Back restoring the enhanced collection.
The destination readiness gate checks the initialized, contract-valid configurator
and selected radio/media model rather than waiting for unrelated third-party
resources to finish the document load. The in-app browser also verified the
desktop detail CTA, mobile 50G CTA and in-configurator model switching preserving
the preview key. `node --check` and `git diff --check` passed.

## Stronger inactive machine dimming — 2026-09-02

Hovering or keyboard-focusing one machine now lowers the other machine media to
42% brightness instead of fading it toward white at 68% opacity. The active
machine remains at full brightness, and both return to full brightness on exit.
Source posters/videos are unchanged. Impeccable contrast guidance keeps desktop
overlaid model labels, prices and compare-button text white against the darkened
media; below desktop these labels retain dark ink on their separate light panel.
The visual inactive state never disables either card or its links. Existing
reduced-motion, touch behavior and blue CTA hover states are preserved.

Validation: `npm run verify` passed all 81 tests with zero Theme Check errors and
the same three existing dependency-template warnings. No compiled build target
exists. Responsive browser acceptance passed (one acceptance test, one intentional
no-URL sentinel skip, zero navigation retries), including both machines, English
and Thai, keyboard/touch/reduced-motion states and configurator navigation.
New assertions cover brightness, restoration and readable inactive overlay text.
Both English hover screenshots in `.codex-tmp/pimm-dark-dim` were visually reviewed.
`git diff --check` passed. Impeccable's detector reported only the pre-existing
`PIMM Chakra Petch` font alias absent from DESIGN.md.
