---
target: the landing page
total_score: 30
p0_count: 1
p1_count: 2
timestamp: 2026-07-19T10-42-33Z
slug: templates-index-json
---
Method: dual-agent (A: design-review agent · B: detector-evidence agent)

# Design Critique #2 — MALIEV Landing Page (templates/index.json + maliev-keynote sections)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | `#simmount` anchor jump is instant with no scroll cue; brand shift marked only by the color flip |
| 2 | Match System / Real World | 3 | "PIMM" now defined inline (good); TH lead mistranslates "pneumatic clamping" as "ระบบปิด" (reads "closed system", should be "ระบบปิดแม่พิมพ์") |
| 3 | User Control and Freedom | 2 | Autoplaying looping video has **no pause control** (WCAG 2.2.2 Level A); LINE links navigate away in the same tab |
| 4 | Consistency and Standards | 3 | Tokens disciplined; transition durations drift (180/300/500/700ms); Dawn footer *copy* still speaks the old brand |
| 5 | Error Prevention | 3 | All 25 section links fetch-verified 200; LINE link lacks `rel` |
| 6 | Recognition Rather Than Recall | 4 | Prices, deposit note, spec chips, and shipping scope all co-located with what they qualify — best on the page |
| 7 | Flexibility and Efficiency | 3 | Skip-link works; sim-racer hero shortcut works; no add-to-cart from homepage, no back-to-top |
| 8 | Aesthetic and Minimalist Design | 3 | Sections exemplary; the Mesh Splitter infographic video and the footer copy cost the point |
| 9 | Error Recovery | 3 | Video has poster now; images sized (no CLS) |
| 10 | Help and Documentation | 3 | Three human-contact paths; guides still skew SimMount/maker over machine buyers |
| **Total** | | **30/40** | **Good — up from 27; losses now concentrated in one video asset and shell content, not the design system** |

## Anti-Patterns Verdict

**LLM assessment:** A designer would not call the section system AI-made. Every previously confirmed issue is fixed and verified: buttons measure white-on-blue 4.95:1, the yellow-plus-ink-halo focus ring is visible on both light and dark stages (screenshotted), no eyebrows, no numbered scaffolding, radii/weights fully on-token. Two things still read template-ish: the **Mesh Splitter video asset** (checkmark-list infographic with clip-art — "the one moment the page looks template-made") and a **borderline identical-grid tic**: four chapters in a row resolve to the same intro → chips → card grid → actions skeleton; each grid is styled differently, but the compositional rhythm repeats.

**Deterministic scan:** CLI detector over all six sections: **zero findings** again. In-page detector: the previous 6× low-contrast button findings are **gone** (P0 fix deterministically confirmed). Remaining: 6× cyan-on-dark (the documented Telemetry Cyan system, measured at a passing 7.57:1 — intentional); 2× tight leading on guide-card anchors (still measuring 1.20 despite the 1.35 title rule — something is overriding the inherit; needs a direct line-height on the anchor); 1× long line on the machines availability note (~165 chars/line); 46× tiny-text false positives (all non-rendered head scripts/styles from Shopify apps); Google-widget and Dawn-header items out of scope.

**Visual overlays:** injection succeeded in a temporary tab during evidence collection; the overlay server was stopped afterward.

## Overall Impression

The score moved 27 → 30 and, more importantly, the failures changed class: nothing in the design system itself is broken anymore — contrast, focus, tokens, routing, scoping copy, and the two-world split all now exist and verify. What remains is one genuinely severe operational discovery — **the Mesh Splitter chapter autoplays a 46MB video (~125MB observed transfer in one session) on a page where everything else totals 0.69MB** — plus a set of art-direction judgments: the video asset's infographic style, the portrait hero's grey headroom on tablet, and the honest verdict that the new "scale" model cards still don't make the 30G/50G size difference legible at card size.

## What's Working

1. **The motion architecture survived adversarial review twice.** JS-off verified, reduced-motion unhooks everything including hover transforms, on-screen groups reveal without pop-in, 6s safety net. "Most agencies ship worse."
2. **Trust-content placement.** Assurance chips answer the four real objections; price and "50% deposit starts production" are never separated; "See it run. Then decide." encodes the whole sales model in five words.
3. **Token discipline + the two-stage focus ring.** Every measured contrast clears AA (4.95–17.32); the ink-halo focus ring works on both stages — a detail most systems miss.

## Priority Issues

- **[P0] 46MB autoplaying homepage video.** The Mesh Splitter mp4 fetches 46MB, and loop playback re-requests ranges (~125MB observed in one session), on every device including mobile. Everything else on the page totals 0.69MB. **Fix:** re-encode a ≤10s loop at ≤3MB, or poster + click-to-play. → /impeccable optimize
- **[P1] No pause mechanism on the looping video (WCAG 2.2.2 Level A).** `autoplay muted loop`, no controls; only reduced-motion users get it paused, which is not a user control. **Fix:** minimal 48px pause/play toggle or drop `loop`. → /impeccable harden
- **[P1] The video asset itself breaks the keynote register.** Clip-art infographic ("The answer: Let Mesh Splitter help you!") inside a minimalist frame. **Fix:** silent screen-capture of the actual tool splitting a mesh — the product is the demo. → content/asset task
- **[P2] Tablet hero art direction.** Below 990px the portrait render's upper ~45% is empty grey studio — at 834×1112 nearly a full screen of nothing between copy and machine, with a visible white/grey seam. **Fix:** crop the portrait asset tighter or cap height with `object-fit: cover; object-position: center bottom`. → /impeccable adapt
- **[P2] Scoping/routing exists but whispers.** The Thailand-only sentence is a muted 14px note orphaned up to 64px below the actions; the closing CTA is 100% machine-buyer content, so Marco's journey ends on someone else's ending; SimMount THB prices (฿3,520.30) need Markets currency confirmation before launch. **Fix:** promote scoping to a chip/badge; add one SimMount line to the closing CTA; verify Markets. → /impeccable clarify
- **[P3] Model cards still don't show scale.** The solo renders are honest but at card size the 50G is only marginally taller. **Fix:** one shared-scale composite or a dimension row (mold height, footprint). Plus hygiene: TH "ระบบปิด" → "ระบบปิดแม่พิมพ์"; LINE links `target="_blank" rel="noopener"`; double focus ring on card title links; guide-anchor leading override; note-to-actions gap; double cookie-consent surfaces; unused `--mk-green` token; two `<h1>`s (Dawn logo + hero).

## Persona Red Flags

**Somchai:** Thai copy is written Thai, not machine Thai — but the one technical mistranslation ("ระบบปิด") sits in exactly the sentence a machine buyer scrutinizes. No persistent LINE affordance (Thai-commerce norm) on a 9,485px page.

**Marco:** Hero shortcut works; carbon section credible. Fails him on THB-with-satang prices (pending Markets check) and a closing CTA that pushes a Thailand-only action at him.

**Casey (mobile):** Tap targets and thumb reach pass; **the 46MB autoplay video is the catastrophic item**; text links are 22px tall (saved by whitespace, WCAG 2.5.8 borderline).

**Riley:** JS-off passes; keyboard order logical; focus visible on both stages; two `<h1>`s; single-mp4 no-fallback video; double consent banners re-prompting mid-session.

**Jordan:** Still can't name what the company *is* after one visit — keynote says machines, header says Mesh Splitter and services, footer says Rapid Prototyping. The Mesh Splitter chapter has no "why does a machine company ship a browser tool" bridge.

## Minor Observations

- Footer merchant copy is the literal last thing every visitor reads and contradicts the positioning (content edit in admin, not code).
- Transition-duration drift: 180/300/500/700ms — pick and document a scale.
- EN template links "Explore the machines" to the Thai-script collection URL; an English handle with redirect would share cleaner.
- Hero `<picture>` swap and CSS stacking are coincidentally coupled at 989px — document it.

## Questions to Consider

1. The factory is the highest-trust asset this business owns and the primary CTA is "come see it" — why does the page spend zero pixels on the factory floor, the engineers, or a visit actually happening?
2. Does Mesh Splitter deserve a homepage chapter, or is it diluting "One Factory, Two Stages" into three? If it stays, why is the weakest asset attached to the easiest-to-demo product?
3. If you removed the color flip, could anyone tell the two brands apart by structure? What would a telemetry-native SimMount layout (spec tables, lap-style data, horizontal media) do that a palette swap cannot?
