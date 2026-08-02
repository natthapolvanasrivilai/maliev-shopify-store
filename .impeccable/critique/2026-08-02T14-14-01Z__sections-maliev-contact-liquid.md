---
target: Contact Us page and on-site machine demo request
total_score: 17
p0_count: 0
p1_count: 4
timestamp: 2026-08-02T14-14-01Z
slug: sections-maliev-contact-liquid
---
# Contact Us page critique

Method: dual-agent (A: `/root/contact_critique_design` · B: `/root/contact_critique_detector`)

## Design Health Score

| # | Heuristic | Score | Key issue |
| --- | --- | ---: | --- |
| 1 | Visibility of System Status | 2 | Success and email-error states exist, but the form does not explain what happens after a demo request. |
| 2 | Match System / Real World | 1 | “Comment” and “Send” do not match the real task of requesting an on-site machine demonstration. |
| 3 | User Control and Freedom | 3 | The standard form and alternate channels are easy to leave; no trapping flow was observed. |
| 4 | Consistency and Standards | 2 | Brand styling is restrained, but duplicate H1s and visually undiscoverable inputs break page and form conventions. |
| 5 | Error Prevention | 1 | Only email is required, the phone pattern rejects common formatting, and demo qualification is unstructured. |
| 6 | Recognition Rather Than Recall | 1 | Customers must invent what machine-demo information MALIEV needs inside a generic comment box. |
| 7 | Flexibility and Efficiency | 2 | Form, LINE, email, and map exist, but there is no direct, efficient demo-request path. |
| 8 | Aesthetic and Minimalist Design | 1 | Large dead zones, repeated titles, weak control boundaries, and generic content reduce clarity. |
| 9 | Error Recovery | 2 | Email recovery is associated correctly; other fields and state preservation have no equivalent evidence. |
| 10 | Help and Documentation | 2 | Office details help, but no demo prerequisites, location expectation, or confirmation model is explained. |
| **Total** |  | **17/40** | **Poor** |

## Anti-Patterns Verdict

**LLM assessment:** Fail through generic-template under-design, not decorative excess. The page avoids gradients, glass cards, inflated radii, fake metrics, and industrial theatre, but the oversized generic Contact heading, repeated Contact form label/title, four-field form, and unused white space do not feel specific to MALIEV, Thailand, injection molding, or an on-site demonstration.

**Deterministic scan:** `node .agents/skills/impeccable/scripts/detect.mjs --json sections/maliev-contact.liquid` returned `[]` with zero rules, locations, or false positives. Mutable script injection preflight succeeded and was cleaned up. The live overlay was not run after browser work was stopped, so deterministic evidence is source-only.

## Overall Impression

The page is technically serviceable but commercially incomplete. It presents a calm contact surface with genuine address and LINE details, yet it forces high-intent machine buyers to translate “I want to see this machine run” into an unstructured generic enquiry. The form should become a clear request-and-review journey for a demonstration at MALIEV’s location, while retaining a secondary general-contact route.

## What’s Working

- Strong black-and-white contrast, restrained typography, and no horizontal overflow at the inspected 390px mobile width.
- Explicit labels, autocomplete, required email, inline and summary email errors, and success/error containers provide a useful semantic base.
- LINE, email, physical office details, business hours, and Google Maps supply real trust evidence.
- Inputs are about 49px high and the CTA about 48px high, providing reasonable touch dimensions.

## Priority Issues

### [P1] No dedicated on-site machine-demo request

**Evidence:** The form only asks for Name, Email, Phone, and Comment; its CTA is “Send.” A factory-visit link appears only in the footer.

**Fix:** Make the primary path “Request a machine demo at MALIEV” and retain “General enquiry” as a secondary intent. Collect only operationally useful facts: company, contact method, machine/model interest, intended part or material, preferred visit date range, attendee count, and notes. Use Shopify contact fields plus a stable `demo-request` tag.

**Suggested command:** `$impeccable clarify`

### [P1] Inputs are visually undiscoverable

**Evidence:** Rendered computed styles showed `border: 0 none` and transparent backgrounds; screenshots read as labels floating over blank space.

**Fix:** Restore visible flat control boundaries with the MALIEV rule color, white surface, 4px corners, 48px minimum height, and clear hover/focus/error states. Preserve persistent labels above every field.

**Suggested command:** `$impeccable harden`

### [P1] Heading hierarchy and page sequence are broken

**Evidence:** `maliev-page` renders the page title as H1, then `maliev-contact` renders another H1 and repeats the translated title as an eyebrow. The result is generic and redundant.

**Fix:** Use one H1: “Request an on-site machine demo.” Follow it with concise expectation copy, use an H2 for the form if needed, and move business hours and alternate channels into clearly secondary support content.

**Suggested command:** `$impeccable typeset`

### [P1] Submission expectations and safeguards are insufficient

**Evidence:** The page does not distinguish a request from a confirmed appointment. The phone pattern `[0-9\-]*` rejects `+`, spaces, and parentheses, and only email has explicit validation recovery.

**Fix:** State before submission that preferred dates are requests subject to review. Use success copy that confirms receipt but not an appointment. Accept normal Thai and international phone formatting, keep inline help and errors attached to each constrained field, and never expose apparently live slots without a verified scheduling integration.

**Suggested command:** `$impeccable harden`

### [P2] Mobile conversion is too effortful

**Evidence:** At 390×844 the document measured about 2,810px tall, the form began around y=526, and Send appeared around y=1,059.

**Fix:** Tighten the intro, group fields into short logical chunks, replace avoidable typing with accessible selections, keep help next to the relevant field, and make the primary CTA full-width on mobile.

**Suggested command:** `$impeccable adapt`

## Recommended Booking Contract

- Location model: request a demonstration at MALIEV’s listed Nonthaburi location; do not imply customer-site visits unless that service is explicitly confirmed.
- Availability model: request-and-review, not instant booking. Preferred week or two broad date choices are safer than fabricated live time slots.
- Required identity: name, email, phone, and company or organization where applicable.
- Useful qualification: interested machine/model, intended part/material, mold status, attendee count, and accessibility or visit notes.
- Expectation copy: “Submitting this form requests a visit; it does not confirm an appointment.”
- Success copy: confirm receipt and say MALIEV will contact the customer to arrange details, without inventing a response-time SLA, demo duration, availability, production outcome, or utilities requirement.
- Data boundary: use Shopify’s contact form payload with translatable custom field names and a stable demo-request tag; do not collect more personal or technical data than the team actually needs.

## Cognitive Load

**4/8 failures — high load at the point of intent.** Chunking, one-thing-at-a-time, minimal choices, and no cross-screen memory bridge pass. Single focus, grouping, visual hierarchy, and progressive disclosure fail. The problem is ambiguity and recall burden, not too many visible options.

## Emotional Journey

- Entry: calm and legitimate, but generic and disconnected from machines or the factory.
- Evaluation: office details build trust, while the lack of demo guidance introduces uncertainty.
- Action: invisible-looking controls and a blank Comment field make the customer guess what MALIEV needs.
- Submission: Send feels like a black box because it does not distinguish a request from confirmation.
- End: alternate contact channels restore some confidence but feel detached from the primary journey.

## Persona Red Flags

- **Jordan — first-time buyer:** Cannot tell whether the form is appropriate for a demonstration, what to write, or what happens after Send.
- **Sam — keyboard/screen-reader user:** Labels and email error associations are a good base; duplicate H1s weaken navigation and browser focus traversal could not be proven.
- **Casey — distracted mobile buyer:** Must scroll more than one viewport to the CTA and type an unstructured request; interruption recovery is unknown.
- **Narin — Thai workshop owner evaluating a compact machine:** Sees no structured way to state machine interest, intended part/material, mold status, preferred visit timing, or attendance needs.

## Minor Observations

- “Use this form below” is redundant; “Other ways to reach MALIEV” is clearer than “Below are a few other ways…”.
- Business hours should name Bangkok time when an international audience may see the page.
- Prefer HTTPS for the LINE destination if supported, and make the plain-text website address a link.
- The cookie-consent panel obscured part of the desktop form during inspection.

## Questions to Consider

1. Should demo requests cover only visits to MALIEV in Nonthaburi, or are customer-site demonstrations genuinely offered too?
2. Which qualification fields does the team actually use: machine model, intended part/material, mold status, attendee count, or preferred week?
3. Is there a verified calendar or CRM integration, or should Shopify email the request for manual confirmation?
