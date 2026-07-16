---
name: "MALIEV Storefront"
description: "Compact production machinery presented with keynote clarity and Thai engineering confidence."
colors:
  foundry-navy: "#07182D"
  deep-workshop-blue: "#0B2442"
  precision-blue: "#075DE8"
  precision-blue-active: "#064DCC"
  blueprint-wash: "#EAF2FF"
  engineering-ink: "#111F33"
  alloy-gray: "#5B6777"
  optical-white: "#FFFFFF"
  cool-workshop-canvas: "#F4F7FB"
  fine-rule: "#DCE4EE"
  safety-yellow: "#FFD21C"
  support-green: "#00A36C"
typography:
  display:
    fontFamily: "Inter, Noto Sans Thai, system-ui, sans-serif"
    fontSize: "clamp(4.2rem, 4.2vw, 5.68rem)"
    fontWeight: 600
    lineHeight: 1.08
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Inter, Noto Sans Thai, system-ui, sans-serif"
    fontSize: "clamp(3.4rem, 4.4vw, 5.6rem)"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Inter, Noto Sans Thai, system-ui, sans-serif"
    fontSize: "clamp(1.84rem, 1.8vw, 2.4rem)"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Inter, Noto Sans Thai, system-ui, sans-serif"
    fontSize: "1.6rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Inter, Noto Sans Thai, system-ui, sans-serif"
    fontSize: "1.3rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "normal"
rounded:
  control: "4px"
  feature: "6px"
  card: "12px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  section-min: "44px"
  section-max: "64px"
components:
  button-primary:
    backgroundColor: "{colors.precision-blue}"
    textColor: "{colors.optical-white}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "12px 24.8px"
    height: "48px"
  button-primary-hover:
    backgroundColor: "{colors.precision-blue-active}"
    textColor: "{colors.optical-white}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "12px 24.8px"
    height: "48px"
  button-secondary:
    backgroundColor: "{colors.optical-white}"
    textColor: "{colors.precision-blue}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "12px 22px"
    height: "48px"
  input-standard:
    backgroundColor: "{colors.optical-white}"
    textColor: "{colors.engineering-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "12px 16px"
    height: "48px"
  product-card:
    backgroundColor: "{colors.optical-white}"
    textColor: "{colors.engineering-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.card}"
    padding: "16px"
  feature-panel:
    backgroundColor: "{colors.optical-white}"
    textColor: "{colors.engineering-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.feature}"
    padding: "clamp(28px, 5vw, 52px)"
---

# Design System: MALIEV Storefront

## 1. Overview

**Creative North Star: "The Compact Production Keynote"**

The storefront should feel like a precise product unveiling held inside a bright, exceptionally organized workshop. It borrows the discipline of an Apple product launch—decisive imagery, progressive explanation, controlled pacing, confident pricing, and purposeful motion—without borrowing Apple's assets, voice, or interface styling. MALIEV remains the subject: ingenious Thai engineering made dependable and approachable.

Product imagery carries the emotional weight. Typography and layout establish the reading order, then get out of the machine's way. Each major viewport should advance one idea: compact fit, credible output, accessible ownership, local manufacturing, serviceability, or the next commercial action. Dense specifications belong in structured comparisons and downloadable documents, not in an undifferentiated wall of catalog content.

This system explicitly rejects anything that looks or behaves like a lightly customized Shopify template, especially recognizable Dawn patterns. It also rejects generic industrial-supplier clutter and visual theatrics that obscure engineering facts, pricing, or contact paths.

**Key Characteristics:**

- Product-first compositions with accurate, high-quality machine imagery.
- Deep navy structure, optical white space, and a controlled precision-blue action color.
- One sans-serif family with disciplined weight, scale, and Thai-language support.
- Flat, crisp surfaces with compact radii and restrained functional elevation.
- Choreographed explanation with an equivalent reduced-motion still state.
- Clear routes to schedule a demo, request a quotation, chat on LINE, or download specifications.

## 2. Colors

The palette combines clean product-studio light with the authority of a Thai engineering workshop. Blue identifies action and technical focus; navy carries institutional confidence; neutrals protect image fidelity and reading clarity.

### Primary

- **Precision Blue** (`#075DE8`): primary actions, prices requiring emphasis, active carousel states, and focused technical links. Its scarcity gives it authority.
- **Pressed Precision Blue** (`#064DCC`): active and hover state for Precision Blue controls; never a competing decorative accent.

### Secondary

- **Foundry Navy** (`#07182D`): announcement bars, footer foundations, and moments where MALIEV's manufacturing authority needs a deep structural field.
- **Deep Workshop Blue** (`#0B2442`): tonal separation inside navy surfaces and controlled dark product contexts.

### Tertiary

- **Safety Yellow** (`#FFD21C`): high-visibility focus treatment and rare safety-relevant emphasis. It is not a marketing highlight color.
- **Support Green** (`#00A36C`): verified service, availability, or successful-state communication only.

### Neutral

- **Engineering Ink** (`#111F33`): headings, body copy requiring full emphasis, controls, and technical facts.
- **Alloy Gray** (`#5B6777`): supporting copy and metadata on white or cool-canvas surfaces while maintaining readable contrast.
- **Optical White** (`#FFFFFF`): product studio surfaces, primary cards, controls, and image-compatible breathing room.
- **Cool Workshop Canvas** (`#F4F7FB`): the restrained page field behind white product surfaces.
- **Blueprint Wash** (`#EAF2FF`): selected or informative blue-tinted states.
- **Fine Rule** (`#DCE4EE`): borders, dividers, and quiet structural separation.

### Named Rules

**The Precision Blue Rule.** Precision Blue marks an action, an active state, or a technical point of focus; it never becomes ambient decoration.

**The Safety Yellow Rule.** Safety Yellow is reserved for keyboard focus and genuine attention states; using it as a promotional accent is prohibited.

## 3. Typography

**Display Font:** Inter (with Noto Sans Thai and system sans-serif fallback)

**Body Font:** Inter (with Noto Sans Thai and system sans-serif fallback)

**Label Font:** Inter (with Noto Sans Thai and system sans-serif fallback)

**Character:** A single bilingual-capable sans-serif keeps the product story direct and mechanically precise. Personality comes from decisive scale, controlled line length, and the contrast between regular body copy and semibold technical hierarchy—not from decorative font pairing.

### Hierarchy

- **Display** (600, fluid `4.2rem–5.68rem`, 1.08): hero claims and singular launch moments; balance the lines and keep letter spacing no tighter than `-0.035em`.
- **Headline** (600, fluid `3.4rem–5.6rem`, 1): major product-story transitions and featured-machine statements.
- **Title** (600, fluid `1.84rem–2.4rem`, 1.2): product names, card titles, and technical subtopics.
- **Body** (400, `1.6rem`, 1.5): explanation and supporting copy; cap sustained reading lines at 65–72 characters.
- **Label** (600, `1.3rem`, normal spacing): prices, specifications, controls, and concise metadata. Uppercase with `0.08em` spacing is allowed only for compact panel labels, never for paragraph copy or every section heading.

### Named Rules

**The Two-Weight Rule.** Use 400 for sustained reading and 600 for hierarchy; heavier weights and artificial boldness are prohibited.

**The One Clear Claim Rule.** Every major product-story viewport gets one dominant headline; secondary text must support it rather than compete with it.

## 4. Elevation

MALIEV is flat by default. Depth comes from white-on-canvas tonal layering, precise rules, image planes, and responsive movement. Shadows are functional: a low ambient shadow may confirm a raised action state, while overlays use a broader structural shadow to separate from the page. Static catalog cards and feature panels remain shadowless.

### Shadow Vocabulary

- **Action Lift** (`0 4px 8px rgba(7, 93, 232, 0.22)`): primary-button hover or focus response only.
- **Overlay Separation** (`0 10px 28px rgba(16, 44, 78, 0.10)`): menus, predictive search, and other floating interface layers.

### Named Rules

**The Flat-by-Default Rule.** A surface at rest has no decorative shadow; if every card appears to float, the hierarchy has failed.

**The Eight-Pixel Ceiling Rule.** Bordered controls may use a response shadow with no more than 8px blur; broad ghost-card shadows are forbidden.

## 5. Components

Components feel precise, quiet, product-first, and technically approachable. Controls are compact enough for serious work but retain generous touch targets and visible keyboard focus.

### Buttons

- **Shape:** compact engineered corners (`4px`), never oversized capsules for primary commercial actions.
- **Primary:** Precision Blue with Optical White text, semibold label, minimum `48px` height, and approximately `12px 24.8px` internal padding.
- **Hover / Focus:** move upward by no more than `2px` using `180ms cubic-bezier(0.22, 1, 0.36, 1)`; keyboard focus uses a `3px` Safety Yellow outline with `3px` offset. Reduced motion removes translation.
- **Secondary:** Optical White with Precision Blue text and border. Text-only actions are reserved for genuinely secondary navigation such as LINE or specification downloads beside a stronger commercial CTA.

### Chips

- **Style:** Blueprint Wash or a closely related cool blue surface, blue-gray text, a quiet blue border, semibold `1.2rem` label, and full-pill geometry only because chips are compact metadata.
- **State:** use chips for machine facts, not as decorative badges. Selected states increase color commitment without adding shadows.

### Cards / Containers

- **Corner Style:** global catalog cards use a restrained `12px` radius; keynote feature panels use a sharper `6px` radius; compact nested product items use `4px`.
- **Background:** Optical White on Cool Workshop Canvas; Foundry Navy is reserved for purposeful contrast sections.
- **Shadow Strategy:** flat at rest; use Fine Rule or tonal contrast for structure.
- **Border:** a single `1px` Fine Rule or equivalent low-opacity ink line.
- **Internal Padding:** begin at `16px`; featured product copy expands responsively from `28px` to `52px`.

### Inputs / Fields

- **Style:** Optical White field, Engineering Ink text, `4px` corners, `1px` Fine Rule, and a minimum `48px` height.
- **Focus:** `3px` accessible outline with `3px` offset; focus never depends on color alone.
- **Error / Disabled:** pair color with explicit text and semantic state. Disabled controls retain legible text and visibly reduced affordance.

### Navigation

- **Style:** Optical White header with a `1px` Fine Rule, dark engineering text, and a restrained `72px` desktop or `64px` mobile height. Precision Blue identifies hover and active states. Dropdowns are compact, bordered overlays with structural elevation rather than oversized glass panels.

### Featured Product Stage

The signature product component pairs a large, accurately cropped machine image with a single explanation column containing the product name, concise capability statement, transparent price, specification chips, and primary/secondary actions. Desktop may use a two-column stage; mobile collapses to one column without changing the reading order. Product media remains the dominant element and never becomes a decorative background behind unreadable text.

Purposeful motion may reveal a machine assembly, transition between exact model views, or sequence technical facts as the user scrolls. Content must be visible and understandable without animation; reduced-motion mode presents the same final frames and information immediately.

## 6. Do's and Don'ts

### Do:

- **Do** lead major pages with accurate machine imagery and one clear claim.
- **Do** borrow Apple product-launch discipline—pacing, photography, progressive explanation, engineering detail, and pricing clarity—while keeping MALIEV's own brand, voice, and visual assets.
- **Do** use Precision Blue (`#075DE8`) for primary action and active technical focus.
- **Do** keep product specifications, dimensions, warranty, replacement parts, and local support easy to verify.
- **Do** provide dedicated desktop and mobile image compositions rather than relying on destructive automatic crops.
- **Do** preserve WCAG 2.2 AA contrast, keyboard access, visible focus, and equivalent reduced-motion states.
- **Do** retain Shopify section schemas and merchant-editable content when implementing the system.

### Don't:

- **Don't** make the storefront look or behave like a lightly customized Shopify template, especially recognizable Dawn patterns.
- **Don't** reproduce Apple's typography, copy, assets, device chrome, or signature layouts; the reference is product-story discipline, not imitation.
- **Don't** introduce generic industrial-supplier clutter, dense walls of specifications, or visual theatrics that obscure engineering facts, pricing, or contact paths.
- **Don't** use cream, sand, parchment, gradient text, decorative glassmorphism, or CSS grid-pattern backgrounds as shortcuts to a designed appearance.
- **Don't** repeat tiny uppercase tracked eyebrows or numbered markers as section scaffolding. Labels must describe real technical hierarchy or sequence.
- **Don't** pair a `1px` decorative border with a broad shadow, use card radii above `12px`, or turn every surface into a floating card.
- **Don't** gate content visibility on animation or ship motion without a reduced-motion equivalent.
- **Don't** show customer-owned molds, parts, names, or logos without explicit permission.
