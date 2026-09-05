---
target: PIMM landing page
total_score: 26
p0_count: 0
p1_count: 3
timestamp: 2026-08-29T06-14-45Z
slug: sections-maliev-pimm-machine-product-liquid
---
# PIMM landing-page critique

## Design Health Score

| Heuristic | Score | Key issue |
|---|---:|---|
| Visibility of system status | 3/4 | Variant state updates coherently, but purchase errors can appear far from the triggering control. |
| Match with the real world | 3/4 | Exact prices and engineering values are credible; 30G/50G terminology is not translated into real part or workshop fit. |
| User control and freedom | 3/4 | Model selection is reversible, but “Configure” only jumps to a purchase section. |
| Consistency and standards | 3/4 | Controls are coherent, though demo actions and commercial facts are duplicated. |
| Error prevention | 3/4 | Invalid states fail closed, but an unqualified visitor can place a high-value deposit. |
| Recognition rather than recall | 2/4 | There is no direct model comparison or recommendation; users must remember their own constraints. |
| Flexibility and efficiency | 2/4 | Selection is fast, but experts lack a compact comparison or shortcut to compatibility evidence. |
| Aesthetic and minimalist design | 3/4 | The object-led hero works; the colored bento and repeated summaries add template-like noise. |
| Error recovery | 2/4 | Failure states do not provide a clear recovery route and may appear remotely from the action. |
| Help and documentation | 2/4 | Ownership language is good, but contextual documentation/support links are absent. |
| **Total** | **26/40** | **Acceptable — meaningful UX improvements needed.** |

## Anti-Patterns Verdict

- **LLM assessment:** Mostly bespoke and credible. The product renders, exact machine data, bilingual content, and qualification language feel manufacturer-specific. The engineering bento is the obvious AI-pattern pocket: oversized heading, one large image, four colored metric cards, and repeated “at a glance” facts.
- **Deterministic scan:** 0 findings across the four requested Liquid markup targets. No rules, locations, or false positives were emitted.
- **Rendered overlay:** Not reliable. Injection succeeded, but the browser detector crashed with `TypeError: elId.startsWith is not a function`; no overlay finding was claimed or left behind.

## Overall Impression

The page has a strong authentic core: the machine is real, the commercial details are unusually transparent, and the interface accurately switches between 30G and 50G. Its main weakness is decision architecture. On mobile, the buyer sees a large title and model controls before seeing the machine or primary action. Farther down, repeated specs and prices lengthen the page without answering the questions that actually determine model fit, utilities, tooling compatibility, included equipment, warranty, or qualification status.

## What’s Working

1. **Authentic, product-led evidence.** Model-specific hero, overview, engineering, and tooling imagery keep the physical machine central.
2. **Commercial transparency.** Full price, deposit, lead time, availability, and Thailand demo context are visible before purchase.
3. **Strong accessible foundations.** Native radios, meaningful alt text, clear focus treatment, `aria-live` updates, reduced-motion handling, and no document-level horizontal overflow at tested breakpoints.

## Priority Issues

1. **P1 — Mobile first-screen hierarchy hides the product and conversion action.** At 390×844, the five-line H1 and capacity cards consume the first screen; the machine and demo CTA are below the fold. Reduce the visual title to roughly 3.2–3.6rem, shorten its line structure, and compose the machine plus demo CTA inside the first viewport while retaining the full semantic title. Suggested command: `/arrange`.
2. **P1 — Mobile commercial facts collapse into four narrow columns.** A higher-specificity four-column rule overrides the intended mobile layout, fragmenting prices and lead-time values. Add an equally or more specific ≤749px two-column override and a one-column fallback at ≤359px; keep monetary values together. Suggested command: `/normalize`.
3. **P1 — Qualification-first positioning conflicts with an immediately enabled deposit.** “See the machine before you commit” and “after qualification” imply a gate, while the deposit remains active. Either enforce qualification state or label the route “Already qualified? Place 50% deposit,” with a visible process: discuss part → confirm mold/utilities → approve model → deposit. Suggested command: `/clarify`.
4. **P2 — Later sections repeat facts rather than advance the decision.** Specifications, price, deposit, lead time, and demo CTAs recur several times. Keep one selected-model summary and replace later repetition with comparison, compressor/utility requirements, mold-fit examples, included equipment, warranty, and downloadable documentation. Suggested command: `/distill`.
5. **P2 — Cookie consent obscures critical content and actions.** The consent dialog covers significant content at desktop, tablet, and mobile sizes. Coordinate with the theme shell: use a compact banner or scrollable mobile bottom sheet, shorten disclosure, and reserve space so it cannot cover the primary CTA. Suggested command: `/harden`.

## Persona Red Flags

- **Jordan, first-time machine buyer:** The page does not translate 30G/50G, mold envelope, MPa, or shot capacity into parts, molds, compressor setup, or workshop examples. “Configure” overpromises, and the active deposit conflicts with qualification language.
- **Riley, stress tester:** Contract failures lack a useful recovery route, add-to-cart errors may render several screens away from the button, long Thai text faces the same dense layouts, and blank documentation settings silently remove support routes.
- **Casey, distracted mobile buyer:** The machine and CTA are below the initial viewport, the commercial strip is fragmented, repeated facts lengthen the journey, and consent UI can obscure the final actions.

## Minor Observations

- `font-weight: 650` may synthesize an unintended weight; the documented inventory supports 600.
- The explanatory fit statement disappears below 1200px, removing useful context on tablets.
- “Selected machine” duplicates the selected-model status without adding recommendation logic.
- The bento palette reads more like a SaaS dashboard than a precision workshop.
- The sticky header is compact and no horizontal document overflow appeared at tested widths.
- Preview console errors from BucksCC and rejected access-text JSON appear external to the four owned Liquid targets and were not counted as PIMM defects.

## Questions to Consider

1. Should qualification be mandatory before deposit, or should the page explicitly separate “already qualified” buyers from first-time buyers?
2. Should the mobile first screen prioritize a large machine image plus demo CTA before model selection, or keep model selection visible alongside a smaller but still dominant machine?
3. Should the engineering bento become an annotated-machine story, a 30G/50G comparison, or an ownership-readiness checklist?
4. Should the consent experience be redesigned globally now, or tracked as a separate theme-shell issue while the PIMM layout proceeds?
