# PIMM 50G Content Motion Design

Date: 2026-08-12

Status: Approved direction; implementation pending

Route: `/products/pneumatic-injection-molding-machine-50g`

## Objective

Add restrained, engineering-led motion to the existing light-studio PIMM 50G product page. Motion must explain product relationships and guide attention without restoring Keynote-style scrolling, delaying access to content, or making the page feel like a generic sequence of fade-up effects.

## Motion Principles

- The machine remains the visual authority; copy and UI motion support it.
- Every sequence runs once when its subject enters the viewport.
- Content is fully visible without JavaScript and remains usable throughout animation.
- Motion uses transforms, bounded opacity changes, clip reveals, and small color or glow changes; it does not animate layout-driving dimensions.
- Durations remain between 180 and 800 milliseconds with confident deceleration easing.
- No bounce, elastic easing, endless loops, scroll hijacking, faux 3D product rotation, or animation-only information.
- `prefers-reduced-motion: reduce` resolves every component directly to its complete final state.

## Signature Hero Sequence

The hero is the single primary entrance moment.

1. The complete alpha machine settles upward by no more than 2% while scaling from 0.975 to 1.
2. The `PIMM 50G` heading and proposition resolve through a short editorial clip reveal rather than a generic opacity-zero fade.
3. The four engineering facts enter as one list rhythm, with a capped stagger of 45 milliseconds per item.
4. The action row becomes visually active last, but remains clickable and visible throughout.

The sequence starts only when the hero is in view and completes within approximately 800 milliseconds. It must not change the machine crop, alpha shadow, or final placement.

## Section Choreography

### Overview Strip

The horizontal rule draws once, then the facts sharpen in as a compact list rhythm. This establishes scan order without turning the strip into animated cards.

### Capacity and Pneumatic Drive

The machine render uses the standard 2% settle. The pneumatic flow diagram then traces from supply to cylinder to injection stroke. Each segment begins after the previous segment has substantially completed. Labels remain visible from the start.

### Steel Melt Zone

The close-up resolves with a short horizontal crop reveal aligned to the physical melt-zone direction. The material proof line draws once and the supporting fact pair follows. Red emphasis remains localized and does not pulse continuously.

### Dual Heating System

The controller render settles into focus first. The two real readout rows illuminate sequentially using restrained border and text-emphasis transitions. Digits are never replaced, overlaid, counted, or simulated in HTML. The sequence communicates independent zones without changing the authored values.

### Mold Workspace

The product image resolves before any annotations. Width and height dimension lines draw from their origins, followed by their semantic values. The sequence cannot obscure the M10 grid or crop the alpha render.

### 30G vs 50G Comparison

Both complete machines settle from small opposing horizontal offsets onto the same baseline. The baseline draws once, then verified comparison facts resolve as one group. This is a scale comparison, not a fake rotator.

### Configuration and Purchase

The final machine render settles first. The configuration summary, qualification list, selector, and actions follow in decision order with a short capped stagger. Demo session remains visually primary. Motion never disables or intercepts Shopify form controls.

## Implementation Architecture

The existing Intersection Observer remains the sole scroll trigger. It adds `is-in-view` once and unobserves the target. Markup receives named motion roles through `data-pimm50-motion` values and bounded child stagger indices. CSS owns the choreography through `--p50-progress`, `--p50-delay`, and section-specific selectors. JavaScript does not calculate element positions or manipulate scroll.

No new animation dependency is introduced. The existing alpha WebP assets remain authoritative; no WebM is added until transparent playback and exact poster parity can be proven in the browser.

## Accessibility and Fallbacks

- Default server-rendered content is visible and readable before JavaScript initializes.
- Initial motion states may use only mild offsets, partial clipping, or opacity above 0.82; no meaningful content begins invisible.
- Keyboard focus, focus outlines, pointer hit targets, and native Shopify controls are unaffected.
- Reduced motion forces progress to 1, removes animation and transition timing, and keeps all annotations and values visible.
- If Intersection Observer is unavailable, the script applies the complete state immediately.

## Performance Budget

- Animate transform and opacity by default.
- Restrict clip-path and glow effects to small isolated regions.
- Do not apply `will-change` globally.
- Unobserve each element after its first entrance.
- Cap each section sequence at 900 milliseconds total and list staggers at 250 milliseconds total.
- Preserve lazy loading and current image-priority behavior.

## Testing Strategy

Contract tests will prove:

- named motion roles exist for each engineered sequence;
- hero and list stagger totals stay within the motion budget;
- no selector hides meaningful content with zero opacity;
- heating animation does not create replacement display digits;
- reduced motion resolves all motion roles to their final state;
- normal scrolling remains free of snap or wheel interception.

The Chromium matrix will verify:

- motion completes once across representative desktop, tablet, portrait mobile, and short-landscape viewports;
- reduced-motion content is immediately complete;
- content geometry, focus order, purchase controls, and horizontal overflow remain unchanged;
- the alpha machine renders stay fully visible at their intended bounds.

## Acceptance Criteria

1. The hero has one coherent, premium entrance rather than multiple unrelated effects.
2. Pneumatic flow, heater independence, mold dimensions, and model comparison each have a distinct explanatory sequence.
3. No meaningful text, price, specification, or control is hidden while waiting for JavaScript.
4. Animations run once, do not loop, and do not block interaction.
5. Reduced-motion users receive the complete static page with no transition delay.
6. The page retains normal browser scrolling and zero horizontal overflow at the existing viewport matrix.
7. Product-page contracts, live Chromium tests, Theme Check, Impeccable detector, and visual review pass before completion.

## Deliberately Excluded

- Scroll-snap or slide navigation.
- Generic fade-and-rise on every section.
- Faux 3D manipulation of flat renders.
- HTML overlays that replace or animate controller digits.
- New Blender or video rendering in this slice.
- Deployment or production push.
