---
target: footer
total_score: 25
p0_count: 0
p1_count: 2
timestamp: 2026-08-02T12-49-21Z
slug: sections-maliev-footer-liquid
---
# Footer critique

Method: dual-agent (A: `/root/footer_recritique_design` · B: `/root/footer_recritique_detector`)

## Design Health Score

| # | Heuristic | Score | Key issue |
| --- | --- | ---: | --- |
| 1 | Visibility of System Status | 3 | Localization indicates busy state, but lacks durable visible failure/retry feedback. |
| 2 | Match System / Real World | 3 | Labels are plain, but “Support” promises a destination that does not exist. |
| 3 | User Control and Freedom | 2 | Native controls are reversible; the dead Support action and immediate locale navigation weaken control. |
| 4 | Consistency and Standards | 3 | Strong visual consistency; external manufacturing link lacks an external-destination cue. |
| 5 | Error Prevention | 2 | Inputs are constrained and duplicate submissions guarded, but dead navigation remains an avoidable error. |
| 6 | Recognition Rather Than Recall | 3 | Labels stay visible; owners must still infer where documentation, parts, warranty, and service live. |
| 7 | Flexibility and Efficiency | 3 | Keyboard-native controls and no-JS fallback are efficient; ownership shortcuts are absent. |
| 8 | Aesthetic and Minimalist Design | 3 | Clean and restrained, but desktop leaves an unused-column feeling and mobile is too long. |
| 9 | Error Recovery | 2 | Newsletter errors recover well; localization lacks inline retry if navigation fails. |
| 10 | Help and Documentation | 1 | Support resolves to `#`; no clear ownership/help map is present. |
| **Total** |  | **25/40** | **Acceptable** |

## Anti-Patterns Verdict

**LLM assessment:** Pass. The footer avoids generic AI treatments—no gradient text, glass cards, ghost shadows, oversized radii, repeated eyebrows, or decorative industrial clichés. Its dark workshop-like field, real MALIEV language, and flat controls feel credible. The weakness is under-articulation: it resembles a competent premium-commerce footer more than a uniquely useful MALIEV ownership map.

**Deterministic scan:** The source detector returned `[]` with zero findings for `sections/maliev-footer.liquid`. Browser injection reported 52 page-wide findings, but none targeted the footer: 49 tiny-text hits were almost entirely non-rendered script/style metadata, two clipped-overflow hits belonged to the catalogue and a third-party widget, and one layout-transition hit belonged to the global body. These are not actionable footer findings.

**Visual overlays:** Injection succeeded and produced browser overlay nodes, but sub-agent browser visibility is unsupported, so no reliable user-visible overlay remains. Screenshot, DOM measurement, console, and source evidence were used instead; all injected nodes and the temporary detector server were cleaned up.

## Overall Impression

The footer is visually disciplined, responsive, and technically progressive. Its single biggest opportunity is functional trust: the page currently ends with payment infrastructure more convincingly than it ends with support, documentation, and human ownership help.

## What’s Working

- The near-black surface, white wordmark, cool-gray copy, thin rule, and flat controls feel like an organized workshop rather than industrial theatre.
- JavaScript auto-applies localization while native selects and compact no-JavaScript submit buttons preserve accessibility and resilience.
- Desktop and 390px layouts have no horizontal overflow; the newsletter and localization controls retain usable dimensions.

## Priority Issues

### [P1] Support is a false affordance

**Why it matters:** The rendered Support link uses `href="#"`. A buyer or owner can choose the most trust-sensitive destination and remain on the same page without explanation.

**Fix:** Remove dead links and provide a real task-shaped support/contact destination.

**Suggested command:** `$impeccable harden`

### [P1] The footer is not yet an ownership map

**Why it matters:** Machine buyers, SimMount customers, and existing owners cannot directly find contact, factory visits, guides, or manufacturing help. The fourth desktop column reads empty rather than intentionally restrained.

**Fix:** Add a concise merchant-editable support group using verified destinations, with roughly four task-shaped links.

**Suggested command:** `$impeccable layout`

### [P2] Mobile is stable but excessively long

**Why it matters:** At 390px the footer measured roughly 1,150px tall. Shop, newsletter, localization, legal, social, and payments create a long low-priority corridor, amplified by the cookie-consent overlay.

**Fix:** Collapse lower-priority footer navigation groups into accessible mobile disclosures while keeping support and localization easy to reach.

**Suggested command:** `$impeccable adapt`

### [P2] Localization needs explicit feedback and retry recovery

**Why it matters:** Busy opacity alone can look frozen on a slow request, and a failed submission has no inline recovery path.

**Fix:** Add localized live status text, lock both localization controls while submitting, and reveal the native submit fallback with an actionable error state if navigation does not occur.

**Suggested command:** `$impeccable harden`

### [P3] Mobile touch targets are undersized

**Why it matters:** Social links measured about 20×27px and text links about 18px high, below the practical 44px mobile target.

**Fix:** Give mobile social, menu, and policy links a minimum 44px interactive box without making the desktop footer visually heavy.

**Suggested command:** `$impeccable adapt`

## Persona Red Flags

- **Casey — distracted mobile shopper:** No horizontal overflow and large selects are strong, but a roughly 1,150px footer plus undersized link targets creates excessive traversal and tap precision.
- **Riley — stress tester:** Support resolves to `#`. Rapid locale changes are guarded, but failed navigation offers no visible retry control.
- **Jordan — first-time buyer:** Labels are understandable, yet the footer does not answer where help, visits, guides, or post-purchase support live; the external manufacturing destination is not announced.
- **Sam — keyboard/screen-reader user:** Semantic labels and native controls are strong. Silent auto-navigation, weak failure feedback, and small mobile targets remain risks.

## Minor Observations

- Payment marks provide strong transactional reassurance but currently finish the composition more decisively than support does.
- The image-based wordmark retains a shop-name accessible label.
- The cookie-consent panel obscured portions of the footer during visual inspection; it is a cross-component composition issue rather than a footer-source defect.
- All inspected countries showed THB in the local market state; that is a Shopify Markets configuration question outside this design-source critique.

## Questions to Consider

- If MALIEV promises direct access to the people who build the products, should the footer end on payment logos or on a human support path?
- Should support expose real ownership tasks—contact, visit, guides, and manufacturing help—rather than a generic label?
- Is newsletter subscription more important than helping a machine buyer book a visit or helping an owner find assistance?

Questions skipped: the user explicitly requested resolution of every detected issue, and the fixes are concrete and bounded.
