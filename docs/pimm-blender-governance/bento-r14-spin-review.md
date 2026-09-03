# Configuration bento: native 360-degree interaction proof

Status: interactive proof complete; exact native-resolution proof approval is pending. The 9494 storefront remains unchanged. No production deployment or push.

## Review

Open `http://127.0.0.1:61283/review-v2/`. Drag the machine horizontally through the front, sides and rear. The visible card has no buttons. A one-time native-view nudge suggests dragging; a grab cursor, touch gestures and keyboard arrows/Home support discovery and operation. Keyboard focus has a visible outline; hover does not add a blue border.

The model remains stationary and the scene-local camera orbits 360 degrees. There are 120 distinct views at 3-degree intervals, with a matching 121st endpoint authored only for closure validation. The linked machine meshes, materials, controller geometry and physical studio lighting are unchanged from the owner-approved r12 configuration scene. Text stays fixed on the left; mobile stacks the whole machine above the text.

- Generation: `bento-20260903-r14-configuration-spin`.
- Contract: `M:/30_Products/00_Pneumatic Injection Molding Machine/blender-product-renders/scenes/contracts/pimm-30g--bento-20260903-r14-configuration-spin--configuration.json`.
- Contract SHA256: `61F98CCD09D522EE02F0F1CCCAA8963AD0B5462F7E24DA7ABB2424FE4284ED16`.
- Review package: `renders/proofs/bento-20260903-r14-configuration-spin/review-v2/review.json`, including exact page, viewer and font hashes.
- Proof frames: 600 x 300, Cycles 32 samples; final scene intent: 2400 x 1200, 128 samples. Proof frames must never be used as storefront derivatives.
- The first r13 authoring attempt failed the exact endpoint closure check before rendering; it remains untouched and is not a release input. r14 assigns the matching endpoint exactly to avoid float32 trigonometric drift in millimetre-scale coordinates.

## Interaction contract

`pimm-bento-spin` accepts a numbered frame URL template, count, localized accessible label, localized angle-value template and an instruction element ID. The still is always present. A canvas uses declared native dimensions independently of CSS display width. At most two frame requests and six decoded cached frames are retained. Explicit interaction loads the selected view and nearby views; it does not download all 120 frames on page load.

Reduced motion and data saving suppress the introductory hint, but deliberate dragging and arrow-key rotation remain usable. Offscreen/hidden/disconnected states stop background work. Errors preserve the static image; stale loads cannot paint an older requested angle. Horizontal touch dragging retains native vertical scrolling and pinch zoom. No automatic spin continues after release.

## Validation

- Python compilation passed. The related proof/native/release suite passed 63 tests, including five new 360-degree coverage and boundary checks.
- JavaScript syntax check and 15 new component regression tests passed. The standard verification command includes those tests.
- `npm run verify`: Theme Check zero errors; 143 component/asset tests and 15 local-route tests passed. One opt-in live route test remains skipped. Three existing Shopify CLI dependency-template warnings remain.
- Browser path: Browser plugin absent; installed Python Playwright/Chromium used without adding dependencies.
- Live proof tested at 1433, 768 and 390 CSS pixels with DPR 2: correct page/title/content, no blank page or framework overlay, zero page errors, zero horizontal overflow, full 360 keyboard wrap, actual changed rendered pixels at the rear, real pointer dragging, release stability and manual rotation under reduced motion.
- CDP touch input on the 390-pixel page verified horizontal rotation and native vertical page scrolling. Initial reduced-motion navigation requested only the static first image. Screenshots were visually inspected; a mobile crop/text collision in review v1 was corrected in immutable review v2.
- Design-hook review: Outfit 700/400 and the single-family bento typography intentionally preserve the user's explicit earlier selection. They are not new font choices. The extra review-label gray was replaced with existing `#111315` ink; no hook suppression was added.

## Remaining gate

Owner approval of this exact r14 proof is required by the Blender workspace policy before rendering its 120 native frames. The full-resolution frame release, localized Liquid integration, final device loading/performance checks and storefront verification are not complete. Safari and assistive-technology device testing are not covered by this Chromium proof check.

This request concerns only the configuration bento's draggable 360-degree view. The separately proposed capacity push-in and tooling tilt were not implemented by this slice.
