---
target: the landing page
total_score: 27
p0_count: 1
p1_count: 2
timestamp: 2026-07-19T05-56-02Z
slug: templates-index-json
---
Method: dual-agent (A: design-review agent · B: detector-evidence agent)

# Design Critique — MALIEV Landing Page (templates/index.json + maliev-keynote sections)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | Homepage `<title>` is "Online Shop - MALIEV Co., Ltd." with boilerplate meta description; no nav active states |
| 2 | Match System / Real World | 3 | Buyer-language copy is strong, but "PIMM" is never expanded and "30 g shot capacity" assumes domain knowledge |
| 3 | User Control and Freedom | 3 | Linear scroll, no traps; video muted/loop and paused under reduced motion |
| 4 | Consistency and Standards | 2 | `.mkey a { color: inherit }` cascade bug breaks CTA/link colors site-wide (P0); `http://` LINE links; navy Dawn footer is a third brand world |
| 5 | Error Prevention | 3 | Robust triple image-fallback chains in every section schema |
| 6 | Recognition Rather Than Recall | 3 | Chips externalize facts well, but 30G/50G renders are visually indistinguishable — text must do all the differentiating |
| 7 | Flexibility and Efficiency | 2 | No fast path for the SimMount audience; no anchor/jump nav on a ~7,000px page |
| 8 | Aesthetic and Minimalist Design | 4 | Restrained, chaptered, confident — the strongest heuristic |
| 9 | Error Recovery | 2 | Mesh Splitter video gets no poster when configured via `asset_name` (the way index.json configures it) — failure = black box |
| 10 | Help and Documentation | 3 | LINE, machine documents, guides, "Talk to our engineers" — human help is one click away |
| **Total** | | **27/40** | **Acceptable–Good: solid foundation, deductions concentrated in one bug + audience routing** |

## Anti-Patterns Verdict

**LLM assessment:** Not AI slop — a designed page, "Apple-keynote grade with three cracks in it." No eyebrows, no numbered scaffolding, no gradient CSS text, no glassmorphism, no hero-metric template, weights 400/600 only, display type under the project's committed ceiling, measured body contrast 8.8–9.6:1. Three things drag toward "clean template": (1) the untouched Dawn header + navy footer bracketing the keynote story; (2) the Mesh Splitter marketing tile (baked-in gradient wordmark on dark grid floor — the most generic-SaaS moment on the page); (3) the near-identical 30G/50G model card renders.

**Deterministic scan:** CLI detector over all six keynote sections: **zero findings** (exit 0). In-page detector: 6× low-contrast on `a.mkey__btn` (confirmed real — see P0, with cascade evidence: `.mkey a{color:inherit}` at specificity 0,1,1 beats `.mkey__btn` at 0,1,0); 6× "cyan neon on dark" in the SimMount stage (accurate measurement, judged intentional — it is the documented Telemetry Cyan brand system, not RGB noise); 2× tight leading (1.2) on guides article title links — caught by the detector, missed by the design review; 1× overused-font (Inter 100% — intentional identity). False positives: 45× "tiny text" (all `<script>`/`<style>`/`<title>`/`<noscript>` head elements from Shopify/third-party apps), 1× clipped overflow (Google merchant widget), 1× layout transition on the Dawn header logo (shell scope, not the keynote work).

**Visual overlays:** injection succeeded in a temporary tab (badges over the flagged buttons and chips); the overlay server was stopped after evidence collection, so the overlays do not persist.

## Overall Impression

This is a real keynote page, not a dressed-up Dawn template: one idea per viewport, honest THB pricing next to deposit framing, textbook progressive-enhancement motion, and a closing line ("See it run. Then decide.") that matches how these machines are actually bought. But its most important element — the "Book a factory visit" button — currently renders dark-ink-on-blue at 3.79:1 everywhere outside the SimMount section because of a one-line CSS cascade bug, and the page never tells an international visitor that machines are Thailand-only. The single biggest opportunity: make the trust story real — the funnel asks for an in-person factory visit, yet the page contains zero photographic evidence the factory exists.

## What's Working

1. **Motion architecture is textbook.** The `.mk-motion` gate means content is fully visible without JS; reduced motion is honored in CSS and JS (with a live change listener that also pauses video); above-fold groups pre-reveal to avoid load pop-in; a 6s safety net guarantees nothing ships hidden. Verified live under `prefers-reduced-motion`.
2. **Copy discipline matches the funnel.** Factory visit stays primary everywhere; price is always paired with "50% deposit starts production"; the Thai template is a genuine translation, not filler.
3. **Asset discipline.** 36–52KB WebP renders at 2400–2600px; ~0.8MB page excluding streamed video; distinct card treatments per chapter (white/bordered vs asphalt/borderless vs bare image).

## Priority Issues

- **[P0] Cascade bug kills CTA and link colors** — `assets/maliev-keynote.css:35` `.mkey a { color: inherit }` (0,1,1) beats `.mkey__btn` and `.mkey__textlink` (0,1,0). Measured live: primary buttons render #101214 on #006FD6 = **3.79:1, AA fail**, on hero, machines, Mesh, services, and closing CTA; all light-stage text links lose their blue affordance. Both agents found this independently (design review + detector). **Fix:** scope the inherit rule (`.mkey a:not(.mkey__btn):not(.mkey__textlink)`) or raise component specificity (`.mkey .mkey__btn`). **Suggested command:** /impeccable polish
- **[P1] Thailand-only scoping + audience routing absent.** An international visitor can read the whole machines chapter and click "Book a factory visit" without learning machines don't ship abroad; a sim racer gets no above-fold signal SimMount exists. Wasted inquiries both ways. **Fix:** one scoping line in the machines chapter ("Sold and supported in Thailand — SimMount ships worldwide ↓") and a small SimMount cross-link near the hero. **Suggested command:** /impeccable clarify
- **[P1] Focus indicator invisible on light stages.** Safety-yellow #FFD21C outline on white/canvas ≈ 1.45:1 (needs 3:1, WCAG 2.2) — keyboard users lose their place on 5 of 7 sections. **Fix:** pair the yellow with a dark ring (e.g. outline + `box-shadow: 0 0 0 5px` ink) on light surfaces. **Suggested command:** /impeccable polish
- **[P2] All-render imagery undermines the factory-visit funnel.** Zero photographs of the real factory, real molded parts, or people, for a purchase whose ritual is an in-person visit. **Fix:** swap one chapter's media (services is the natural slot) to real workshop photography. **Suggested command:** /impeccable delight (imagery direction) or content task
- **[P2] SimMount reads as a dark-mode card strip, not a second world.** Two of three product photos are white-background studio shots inside carbon cards; only the Pro Pivot photo delivers the motorsport world. **Fix:** dark-background photography/renders for VESA + ShakeHolder (or transparent cutouts on asphalt), and consider one full-width dark rig hero image. **Suggested command:** /impeccable bolder (scoped to the SimMount section)
- **[P3] Hygiene cluster:** `http://` LINE links → https; Mesh Splitter video poster not wired for `asset_name`; generic homepage `<title>`/meta description; guides title links at 1.2 line-height (detector); `--mk-ease` (0.16,1,0.3,1) vs DESIGN.md token (0.22,1,0.36,1). **Suggested command:** /impeccable polish

## Persona Red Flags

**Somchai (Thai workshop owner — primary buyer):** No phone number anywhere in the keynote flow; "Chat with us on LINE" — the most Thai-natural channel — is the *least* visible element in the closing CTA stack (a text link, currently rendered ink by the P0 bug); zero real factory/people imagery for a buyer whose decision ritual is "go see it and talk to the person."

**Marco (Italian sim racer):** Nothing above the fold says "sim racing"; SimMount is 2 viewports deep and the page ends on a factory visit he can't use; THB-only prices with no market context. He needs a router, not a story.

**Jordan (first-timer):** "PIMM" never expanded; 30G vs 50G visually indistinguishable at card size (a ฿64k delta explained only in text); the MALIEV↔SimMount relationship never stated.

**Riley (stress tester):** JS-off passes (content fully visible); tab order logical; focus ring fails on light stages (P1 above); Thai-script collection URL percent-encodes into a ~150-char string when shared; `asset_name`-configured video has no poster → black box on slow networks.

**Casey (mobile):** Tap targets ≥48px, CTAs land in thumb reach, ~0.8MB page — passes; cookie banner interrupts first hero paint (shell scope).

## Minor Observations

- 30G/50G cards need a visual scale cue (bench, hand, silhouette overlay) to justify the price delta.
- `.mkey__btn:hover` lift+shadow is the one motion contradicting flat-by-default; defensible but noted.
- All three guide articles are SimMount/3D-printing topics — the machine buyer gets zero editorial support (nothing on molds, materials, or what a 30g shot can make).
- `.mkey__chip { white-space: nowrap }` is an overflow tripwire for longer Thai strings at 320px.
- The Dawn header and navy footer are the two untreated surfaces bookending the keynote story — the last word on every page belongs to the oldest branding.

## Questions to Consider

1. If every buyer visits the factory before paying, why does the homepage contain zero evidence the factory exists — no photo, no address, no map, no engineer's face? What is "Book a factory visit" asking them to trust?
2. Does SimMount deserve a chapter in MALIEV's story, or does Marco deserve his own front door — a dedicated SimMount landing page with the homepage acting as a two-stage router?
3. The page gives three self-descriptions in one scroll — keynote MALIEV ("we build machines"), Dawn title ("Online Shop"), footer ("Online Manufacturing Services… 3D scanning, printing, CNC"). Which company is this, and why does the last word belong to the oldest branding?
