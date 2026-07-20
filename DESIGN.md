---
name: "MALIEV Storefront"
description: "A clean engineering showroom with two spotlighted stages: compact injection molding machines and SimMount sim racing hardware."
colors:
  precision-blue: "#006FD6"
  precision-blue-pressed: "#064FC4"
  engineering-ink: "#101214"
  alloy-gray: "#697078"
  optical-white: "#FFFFFF"
  workshop-canvas: "#F4F6F7"
  fine-rule: "#1012141A"
  foundry-dark: "#101418"
  support-green: "#00A36C"
  safety-yellow: "#FFD21C"
  carbon-black: "#0C1114"
  asphalt: "#161C22"
  telemetry-cyan: "#18B7FF"
typography:
  display:
    fontFamily: "Archivo, Inter, Noto Sans Thai, system-ui, sans-serif"
    fontSize: "clamp(4.2rem, 5.4vw, 7.8rem)"
    fontWeight: 700
    fontStretch: "118%"
    lineHeight: 0.96
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Archivo, Inter, Noto Sans Thai, system-ui, sans-serif"
    fontSize: "clamp(3.2rem, 4.4vw, 5.8rem)"
    fontWeight: 700
    fontStretch: "114%"
    lineHeight: 0.98
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Archivo, Inter, Noto Sans Thai, system-ui, sans-serif"
    fontSize: "clamp(1.9rem, 1.9vw, 2.4rem)"
    fontWeight: 600
    fontStretch: "108%"
    lineHeight: 1.2
    letterSpacing: "-0.005em"
  body:
    fontFamily: "Inter, Noto Sans Thai, system-ui, sans-serif"
    fontSize: "1.6rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Inter, Noto Sans Thai, system-ui, sans-serif"
    fontSize: "1.35rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "normal"
rounded:
  control: "4px"
  feature: "8px"
  card: "12px"
  panel: "16px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  section: "clamp(48px, 6vw, 88px)"
components:
  button-primary:
    backgroundColor: "{colors.precision-blue}"
    textColor: "{colors.optical-white}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "12.5px 22px"
    height: "48px"
  button-primary-hover:
    backgroundColor: "{colors.precision-blue-pressed}"
    textColor: "{colors.optical-white}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "12.5px 22px"
    height: "48px"
  button-secondary:
    backgroundColor: "{colors.optical-white}"
    textColor: "{colors.precision-blue}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "12.5px 22px"
    height: "48px"
  button-simmount:
    backgroundColor: "{colors.telemetry-cyan}"
    textColor: "{colors.carbon-black}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "12.5px 22px"
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
  chip:
    backgroundColor: "{colors.workshop-canvas}"
    textColor: "{colors.engineering-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "6px 14px"
  simmount-panel:
    backgroundColor: "{colors.asphalt}"
    textColor: "{colors.optical-white}"
    typography: "{typography.body}"
    rounded: "{rounded.panel}"
    padding: "clamp(28px, 5vw, 52px)"
---

# Design System: MALIEV Storefront

## 1. Overview

**Creative North Star: "One Factory, Two Stages"**

The storefront is a bright, exceptionally organized engineering showroom with two spotlighted stages inside it. The showroom itself — home, collections, cart, search, account — is a clean, functional store: cool white surfaces, honest prices, quiet structure, nothing performing. Step onto a product line's pages and the lights change. The injection molding machines stand on the workshop stage: optical white, precision blue, accurate renders, keynote pacing. SimMount stands on the paddock stage: carbon black, telemetry cyan, motorsport precision. One factory built both; the shared thread is engineering discipline, not shared styling.

Product imagery carries the emotional weight on both stages. Typography and layout establish the reading order, then get out of the product's way. Each major viewport on a keynote page advances one idea: compact fit, credible output, accessible ownership, local manufacturing, serviceability, or the next commercial action. Dense specifications belong in structured comparisons and downloadable documents, never in an undifferentiated wall of catalog content.

This system explicitly rejects anything that looks or behaves like a lightly customized Shopify template — especially recognizable Dawn patterns — along with generic industrial-supplier clutter and gamer-RGB noise. The PIMM-50G dark cinematic launch page (near-black surfaces, heat-orange accents) is a deliberate campaign one-off; its palette is not part of this system and must not leak into other surfaces.

**Key Characteristics:**

- A neutral, transactional store shell that never competes with the product stages.
- Machine stage: optical white, precision blue, accurate KeyShot/Blender renders, keynote pacing.
- SimMount stage: carbon black and asphalt surfaces, telemetry cyan, motorsport-technical density.
- One bilingual sans-serif family (Inter + Noto Sans Thai) at two weights, everywhere.
- Flat, crisp surfaces; compact engineered radii; functional elevation only.
- Clear routes to book a factory visit, place a production deposit, request a quote, chat on LINE — or simply add SimMount to cart.

## 2. Colors

A cool, product-studio neutral field with one blue voice for action — and a second, contained world of carbon and cyan reserved for SimMount surfaces.

### Primary

- **Precision Blue** (`#006FD6`): primary actions, active states, focused technical links, and prices requiring emphasis across the store shell and machine pages. Its scarcity gives it authority.
- **Pressed Precision Blue** (`#064FC4`): hover and active state for Precision Blue controls; never a competing decorative accent.

### Secondary

- **Telemetry Cyan** (`#18B7FF`): SimMount's action and emphasis color — CTAs, active states, data highlights, and speed cues on carbon surfaces. It does not appear on machine or store-shell surfaces.
- **Carbon Black** (`#0C1114`): SimMount page field; the paddock-dark ground that makes cyan read like a HUD.
- **Asphalt** (`#161C22`): SimMount panels and cards; one tonal step above Carbon Black for structure without borders.

### Tertiary

- **Safety Yellow** (`#FFD21C`): keyboard-focus treatment and rare safety-relevant emphasis only. It is not a marketing highlight color.
- **Support Green** (`#00A36C`): verified service, availability, and success states only.

### Neutral

- **Engineering Ink** (`#101214`): headings, body copy, controls, and technical facts on light surfaces.
- **Alloy Gray** (`#697078`): supporting copy and metadata on white or canvas surfaces; never for sustained body paragraphs.
- **Optical White** (`#FFFFFF`): product studio surfaces, cards, controls, and image-compatible breathing room; also text on dark SimMount surfaces.
- **Workshop Canvas** (`#F4F6F7`): the restrained page field behind white surfaces in the store shell and machine pages.
- **Fine Rule** (`#1012141A`, 10% ink): borders, dividers, and quiet structural separation on light surfaces.
- **Foundry Dark** (`#101418`): the store shell's single dark contrast surface (footer, deliberate dark bands).

### Named Rules

**The Precision Blue Rule.** Precision Blue marks an action, an active state, or a technical point of focus; it never becomes ambient decoration.

**The Two Stages Rule.** Telemetry Cyan and carbon surfaces belong to SimMount; Precision Blue and workshop light belong to machines and the shell. The two palettes never mix on one surface.

**The Campaign One-Off Rule.** The PIMM-50G launch page's dark heat palette (`#070B10`, `#FF7A1A`, `#FFB347`) is campaign scenery, not a system token. Do not reuse it on new surfaces.

**The Safety Yellow Rule.** Safety Yellow is reserved for keyboard focus and genuine attention states; using it as a promotional accent is prohibited.

## 3. Typography

**Display Font:** Archivo, expanded widths (with Inter, Noto Sans Thai, and system sans-serif fallback)

**Body Font:** Inter (with Noto Sans Thai and system sans-serif fallback)

**Character:** Two voices on one contrast axis: Archivo — a grotesque with industrial-signage DNA, run at expanded widths (108–118%) and bold weight — carries display claims, section headlines, and product names; Inter carries all sustained reading. The pairing contrasts through width and weight rather than through genre costume; Thai text renders in Noto Sans Thai at every level. The same pairing serves both stages; SimMount differentiates through color and density, not fonts.

### Hierarchy

- **Display** (Archivo 700 @ 118% width, fluid `4.2rem–7.8rem`, 0.96): hero claims on keynote pages only; balance the lines and never track tighter than `-0.035em`.
- **Headline** (Archivo 700 @ 114% width, fluid `3.2rem–5.8rem`, 0.98): major product-story transitions and section-defining statements.
- **Title** (Archivo 600 @ 108% width, fluid `1.9rem–2.4rem`, 1.2): product names, card titles, and technical subtopics.
- **Body** (Inter 400, `1.6rem`, 1.5): explanation and supporting copy; cap sustained reading at 65–72 characters. Lead paragraphs may scale to `clamp(1.7rem, 1.8vw, 2.1rem)` at 1.48.
- **Label** (Inter 600, `1.35rem`, 1.2): prices, specifications, buttons, and concise metadata. Uppercase with tracking is allowed only for compact panel labels, never as section scaffolding.

### Named Rules

**The Two-Voice Rule.** Archivo speaks only at display/headline/title level and only at 600–700; Inter 400 carries sustained reading and Inter 600 carries labels. No third family, no additional weights.

**The One Clear Claim Rule.** Every major keynote viewport gets one dominant headline; secondary text supports it rather than competes with it.

## 4. Elevation

MALIEV is flat by default. Depth comes from tonal layering (white on canvas in the shell; asphalt on carbon for SimMount), precise rules, and image planes. Shadows are functional responses to state, never resting decoration. Static catalog cards and feature panels remain shadowless.

### Shadow Vocabulary

- **Action Lift** (`0 4px 8px rgba(0, 111, 214, 0.22)`): primary-button hover or focus response only; SimMount substitutes a cyan-tinted equivalent at the same geometry.
- **Overlay Separation** (`0 10px 28px rgba(16, 44, 78, 0.10)`): menus, predictive search, drawers, and other floating layers.

### Named Rules

**The Flat-by-Default Rule.** A surface at rest has no decorative shadow; if every card appears to float, the hierarchy has failed.

**The Eight-Pixel Ceiling Rule.** Control response shadows may blur no more than 8px; broad ghost-card shadows are forbidden.

## 5. Components

Components feel precise, quiet, and product-first. Controls are compact enough for serious work but keep generous touch targets and visible keyboard focus. Transitions run at `180ms cubic-bezier(0.22, 1, 0.36, 1)`.

### Buttons

- **Shape:** compact engineered corners (`4px`); pills are prohibited for commercial actions.
- **Primary:** Precision Blue with Optical White text, semibold `1.45rem` label, minimum `48px` height, `12.5px 22px` padding. On SimMount surfaces, Telemetry Cyan with Carbon Black text at identical geometry.
- **Hover / Focus:** background deepens to Pressed Precision Blue; upward translation of at most `2px`; keyboard focus is a `3px` Safety Yellow outline with `3px` offset. Reduced motion removes translation.
- **Secondary:** Optical White with Precision Blue text and a `1px` Precision Blue border. Text-only actions serve genuinely secondary paths (LINE chat, spec downloads) beside a stronger CTA.

### Chips

- **Style:** Workshop Canvas surface, Engineering Ink text, semibold label, full-pill geometry — chips are the only pill-shaped element in the system. On SimMount surfaces: Asphalt ground with Optical White or Telemetry Cyan text.
- **State:** chips carry machine facts and spec metadata, not decorative badges. Selected states increase color commitment without shadows.

### Cards / Containers

- **Corner Style:** catalog cards `12px`; keynote feature panels `16px`; compact nested items and media frames `4–8px`.
- **Background:** Optical White on Workshop Canvas in the shell and machine pages; Asphalt on Carbon Black for SimMount.
- **Shadow Strategy:** flat at rest; structure comes from Fine Rule borders or tonal contrast.
- **Border:** a single `1px` Fine Rule on light surfaces; SimMount panels rely on tonal steps instead of borders.
- **Internal Padding:** begin at `16px`; featured panels expand responsively from `28px` to `52px`.

### Inputs / Fields

- **Style:** Optical White field, Engineering Ink text, `4px` corners, `1px` Fine Rule border, minimum `48px` height.
- **Focus:** `3px` accessible outline with `3px` offset; focus never depends on color alone.
- **Error / Disabled:** pair color with explicit text and semantic state; disabled controls keep legible text with visibly reduced affordance.

### Navigation

- **Style:** Optical White header with a `1px` Fine Rule, Engineering Ink text, `72px` desktop / `64px` mobile height. Precision Blue marks hover and active states. Dropdowns are compact bordered overlays using Overlay Separation — never oversized glass panels.

### Featured Product Stage (machines)

The signature machine component pairs a large, accurately cropped render with a single explanation column: product name, concise capability statement, transparent price, spec chips, and primary/secondary actions. Desktop may run two columns; mobile collapses to one without reordering. Media stays dominant and never becomes a background behind unreadable text. Scroll choreography may reveal assemblies or sequence technical facts, but content must be fully legible without animation; reduced-motion mode presents final frames immediately.

### SimMount Telemetry Stage

SimMount's signature surface is a dark product stage: Carbon Black field, Asphalt panels, full-bleed product photography of printed parts on rigs, and Telemetry Cyan carrying data-like emphasis — load ratings, print material, compatibility, lap-ready specs presented with HUD-like precision. Density can run higher than machine pages; restraint shows in the two-color discipline (cyan + white on carbon), not in emptiness. Checkout actions are immediate and prominent: this stage sells directly.

## 6. Do's and Don'ts

### Do:

- **Do** keep the store shell (home, collections, cart, search) clean, fast, and transactional; reserve keynote theatrics for product-line pages.
- **Do** lead keynote pages with accurate product imagery and one clear claim.
- **Do** use Precision Blue (`#006FD6`) for action on light surfaces and Telemetry Cyan (`#18B7FF`) for action on SimMount carbon — never both on one surface.
- **Do** keep specifications, dimensions, warranty, replacement parts, deposit terms, and Thailand-only machine availability easy to verify.
- **Do** provide dedicated desktop and mobile image compositions rather than destructive automatic crops.
- **Do** preserve WCAG 2.2 AA contrast, keyboard access, visible focus, and equivalent reduced-motion states in both Thai and English.
- **Do** retain Shopify section schemas and merchant-editable content when implementing the system.

### Don't:

- **Don't** make the storefront look or behave like a lightly customized Shopify template, especially recognizable Dawn patterns.
- **Don't** introduce generic industrial-supplier clutter, dense walls of specifications, or visual theatrics that obscure engineering facts, pricing, or contact paths.
- **Don't** let SimMount collapse into gamer-RGB clutter or aggressive esports styling; motorsport-technical means precision and speed, not neon noise.
- **Don't** reuse the PIMM-50G launch campaign's dark heat palette (`#070B10`, `#FF7A1A`) on any new surface; it is a one-off.
- **Don't** use cream, sand, parchment, gradient text, decorative glassmorphism, or CSS grid-pattern backgrounds as shortcuts to a designed appearance.
- **Don't** repeat tiny uppercase tracked eyebrows or numbered markers as section scaffolding; labels must describe real technical hierarchy or sequence.
- **Don't** pair a `1px` decorative border with a broad shadow, exceed `16px` card radii, or turn every surface into a floating card.
- **Don't** gate content visibility on animation or ship motion without a reduced-motion equivalent.
- **Don't** show customer-owned molds, parts, names, or logos without explicit permission.
