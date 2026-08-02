---
name: "MALIEV Workshop Commerce"
description: "A custom product-led Shopify theme that presents engineered objects with the clarity of an excellent technical store and the confidence of a Thai manufacturer."
colors:
  ink: "#111315"
  ink-soft: "#353A40"
  graphite: "#626A73"
  rule: "#D9DDE1"
  canvas: "#F3F5F6"
  surface: "#FFFFFF"
  signal-blue: "#006FD6"
  signal-blue-hover: "#005BB5"
  focus-yellow: "#FFD21C"
  success: "#087A55"
  warning: "#9A5B00"
  danger: "#B42318"
  sim-carbon: "#0B0E11"
  sim-panel: "#171B20"
  sim-line: "#30363D"
  sim-cyan: "#18B7FF"
typography:
  home-display:
    fontFamily: "Audiowide, Chakra Petch, Aldrich, IBM Plex Sans, IBM Plex Sans Thai, sans-serif"
    fontSize: "clamp(4.8rem, 5.9vw, 9rem)"
    fontWeight: 400
    lineHeight: 0.96
    letterSpacing: "-0.025em"
  display:
    fontFamily: "IBM Plex Sans, IBM Plex Sans Thai, sans-serif"
    fontSize: "clamp(3.6rem, 5.8vw, 7.2rem)"
    fontWeight: 600
    lineHeight: 0.98
    letterSpacing: "-0.035em"
  heading:
    fontFamily: "IBM Plex Sans, IBM Plex Sans Thai, sans-serif"
    fontSize: "clamp(2.8rem, 4vw, 5.2rem)"
    fontWeight: 600
    lineHeight: 1.04
    letterSpacing: "-0.025em"
  title:
    fontFamily: "IBM Plex Sans, IBM Plex Sans Thai, sans-serif"
    fontSize: "clamp(2rem, 2.2vw, 2.8rem)"
    fontWeight: 600
    lineHeight: 1.16
    letterSpacing: "-0.012em"
  body:
    fontFamily: "IBM Plex Sans, IBM Plex Sans Thai, sans-serif"
    fontSize: "1.6rem"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "normal"
  label:
    fontFamily: "IBM Plex Sans, IBM Plex Sans Thai, sans-serif"
    fontSize: "1.4rem"
    fontWeight: 500
    lineHeight: 1.3
    letterSpacing: "normal"
  data:
    fontFamily: "IBM Plex Mono, ui-monospace, monospace"
    fontSize: "1.35rem"
    fontWeight: 400
    lineHeight: 1.35
    letterSpacing: "-0.01em"
rounded:
  control: "4px"
  compact: "6px"
  card: "10px"
  panel: "14px"
  pill: "999px"
spacing:
  2xs: "4px"
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "48px"
  section: "clamp(56px, 7vw, 104px)"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    height: "48px"
    padding: "12px 22px"
  button-action:
    backgroundColor: "{colors.signal-blue}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    height: "48px"
    padding: "12px 22px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    borderColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    height: "48px"
    padding: "12px 22px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    borderColor: "{colors.rule}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    height: "48px"
    padding: "11px 14px"
  product-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "0"
  spec-table:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    ruleColor: "{colors.rule}"
    labelTypography: "{typography.label}"
    valueTypography: "{typography.data}"
---

# Design System: MALIEV Workshop Commerce

## 1. Creative direction

### North star: The precision workbench

The storefront behaves like a beautifully organized workbench: every object has a clear purpose, every measurement is easy to find, and nothing decorative competes with the product. The physical product remains the dominant visual event. Structure, typography, and interaction make evaluation feel calm and competent.

The system borrows four useful patterns from current product stores without copying their styling:

- **Keychron:** product-family navigation, product-led merchandising, useful comparison, and a store that can carry a broad technical catalog.
- **Mode:** large product moments, editorial restraint, and premium pacing.
- **Framework:** compatibility, repair, parts, documentation, and ownership treated as commerce rather than footer material.
- **Wooting:** technical differentiation explained in plain language before purchase.

MALIEV's expression is its own: Thai manufacturing, compact production equipment, real support, and a strong relationship between the machine, the mold, the part, and the people who make them.

### Physical scene

A Thai workshop owner reviews the store on a laptop beside a bright production bench in daytime. The room is practical and well maintained, not a showroom. Product images and specifications must remain legible in ambient light, so the default shell is light, crisp, and high contrast. SimMount earns a contained carbon mode because it is evaluated in a cockpit context, but the controls and information architecture remain the same.

### Color strategy

**Restrained with committed product chapters.** The global shell uses white, cool gray, ink, and sparse Signal Blue. Machine storytelling may commit to blue in one chapter at a time. SimMount uses Carbon and Cyan only inside its own surfaces. Neither accent becomes ambient decoration.

## 2. Typography

The core commerce system uses one coordinated IBM Plex superfamily. The homepage is the controlled pilot for a more engineered display voice: Audiowide for the Latin hero headline, Aldrich for other Latin display headings, and Chakra Petch for Thai display text. Other templates remain on IBM Plex until they are deliberately redesigned rather than inheriting the homepage treatment accidentally.

- **Audiowide:** homepage Latin hero headline at weight 400 only.
- **Aldrich:** other homepage Latin display headings at weight 400 only.
- **Chakra Petch:** Thai glyphs for homepage display headings, using its geometric loop construction to fit both Latin display faces.
- **IBM Plex Sans / IBM Plex Sans Thai:** homepage navigation, body copy, actions, and dense interface text remain in the more readable commerce family.

- **IBM Plex Sans:** Latin interface, editorial copy, headings, navigation, buttons, and prices.
- **IBM Plex Sans Thai:** Thai glyphs in the same line and at the same hierarchy as Latin.
- **IBM Plex Mono:** dimensions, tolerances, file sizes, material codes, part numbers, compatibility codes, and compact technical values only.

Self-host the same subsets used by `R:\maliev-web\Maliev.Web`: Sans 400/500/600 Latin1 and Pi, Thai 400/500/600, and Mono 400/600 Latin1 and Pi. Use `font-display: swap` and unicode ranges so English visitors do not download Thai fonts unnecessarily.

Named rules:

- **Controlled homepage exception:** Audiowide, Aldrich, and Chakra Petch apply only to `.template-index` and `.mc-header--home` until each remaining template is redesigned and validated.
- **No synthetic display weights:** Audiowide and Aldrich ship at 400 here; hierarchy comes from scale, spacing, and composition rather than browser-generated bold.
- **Commerce continuity:** no Archivo, Inter, Noto Sans Thai, or theme-selected body font remains in the custom system; IBM Plex continues to own dense commerce and long-form reading.
- **Three working weights:** 400 for reading, 500 for UI emphasis, 600 for headings and decisive emphasis. Never synthesize bold.
- **Mono means data:** never use monospace for mood, labels, navigation, or entire specification paragraphs.
- **Thai parity:** Thai headings do not shrink merely to imitate Latin line lengths. Test real localized strings at every breakpoint.
- Display tracking never goes below `-0.035em`; body and Thai copy use normal tracking.

## 3. Color

### Global shell

- **Ink `#111315`:** headings, primary commercial controls, and high-priority facts.
- **Ink Soft `#353A40`:** secondary headings and dense UI copy.
- **Graphite `#626A73`:** metadata only, after contrast verification.
- **Rule `#D9DDE1`:** dividers, form boundaries, and table structure.
- **Canvas `#F3F5F6`:** alternate sections, media wells, and utility surfaces.
- **Surface `#FFFFFF`:** default page field and controls.
- **Signal Blue `#006FD6`:** links, selected states, machine conversion actions, and technical focus.

### Semantic states

- Focus Yellow `#FFD21C` is reserved for a visible 3px keyboard-focus ring.
- Success `#087A55`, Warning `#9A5B00`, and Danger `#B42318` always pair with text or an icon and are never decorative.

### SimMount mode

- Carbon `#0B0E11` is the section/page field.
- Panel `#171B20` separates related controls and specifications.
- Sim Line `#30363D` structures dark surfaces.
- Cyan `#18B7FF` marks actions, compatibility, and selected states.

Signal Blue and Sim Cyan never appear as competing accents on the same surface.

## 4. Layout system

### Grid

- Maximum content width: `1440px`.
- Reading/content width: `720px`.
- Technical comparison width: up to `1200px`.
- Gutters: `20px` mobile, `32px` tablet, `48px` desktop.
- Major vertical sections use `clamp(56px, 7vw, 104px)` with deliberate tighter transitions between related chapters.

Use Grid for product/media comparisons and Flexbox for toolbars, actions, metadata, and wrapping filters. Avoid container-shaped decoration. Surfaces become panels only when grouping improves a task.

### Responsive rules

- Mobile is composed, not cropped: dedicated image positions, stacked comparisons, adjacent labels and values, and full-width primary actions when necessary.
- Header navigation becomes an accessible drawer below `990px`; search remains immediately available.
- Filters move into a disclosure/drawer while active filters remain visible near results.
- Product purchase controls remain in document order; any sticky purchase affordance mirrors state but never replaces the canonical form.
- Tables become labeled rows or scroll only when the data relationship truly requires columns.
- No viewport may develop horizontal document overflow at 320px or above.

## 5. Global shell

### Announcement bar

One concise operational message only: Thailand machine availability, international SimMount shipping, or a genuine service notice. No carousel, countdown, or rotating promotions. Minimum height `36px`.

### Header

The header is a custom, compact commerce instrument—not Dawn chrome.

- Desktop height `68px`, mobile `60px`.
- MALIEV wordmark at the start; product-family navigation in the center; search, market/language, account, and cart at the end.
- Mega navigation organizes by Machines, SimMount, Parts & Molds, Tools, Learn, and Support. Each group contains a short path description, never promotional filler.
- Search opens a full-width, task-focused layer with product, article, document, and collection result groups.
- Cart count and active navigation state have accessible text equivalents.

### Footer

The footer is an ownership map: shop, service, documentation, contact, market/language, policies, and company identity. Keep newsletter secondary. Use a single Foundry-dark surface without decorative columns or oversized marketing copy.

## 6. Commerce components

### Buttons and links

- Primary neutral button: Ink on light surfaces; decisive universal commerce action.
- Machine action: Signal Blue for demonstration, quotation, or qualified deposit.
- SimMount action: Cyan on Carbon.
- Secondary button: 1px Ink border without a resting shadow.
- Text links use a visible underline on hover/focus and an arrow only when direction adds meaning.
- Corners remain `4px`; commercial buttons are never pills.
- All states: default, hover, focus, active, disabled, loading, and error.

### Product cards

Product cards are image-first catalog entries, not floating tiles.

- Flat at rest with no decorative shadow.
- Media well on Canvas; consistent product scale within a family.
- Name, one decision-relevant descriptor, price, availability, and compatibility follow in that order.
- Quick add appears only for simple, low-risk products. Machines never use quick add.
- Badges are limited to factual state: New, Pre-order, Sold out, or verified discount.

### Product page

- Gallery and purchase information form the first decision zone.
- Product title, concise fit statement, price/deposit terms, availability, variants, and primary action remain grouped.
- Machine templates replace cold-purchase emphasis with Book a visit / Request a quotation; deposit remains available with explicit terms.
- SimMount templates prioritize compatibility before Add to cart.
- Technical chapters use full-width media, labeled specifications, compatibility, what's included, service, documents, and FAQ.
- Variant, quantity, selling-plan, pickup, tax, inventory, and dynamic-checkout behaviors continue to use Shopify-native data and events.

### Collection and search

- Family header explains the decision and exposes a useful path to guidance.
- Toolbar keeps result count, sort, filters, and view behavior compact.
- Grid defaults to 2 columns mobile, 3 tablet, and 4 desktop when image/detail density allows.
- Empty results explain how to broaden the search and provide direct support.

### Cart and drawers

- Cart drawer is a fast confirmation surface, not a promotional mini-homepage.
- Line items keep image, variant, quantity, price, discounts, errors, and remove controls together.
- Machine deposit items surface their deposit context before checkout.
- Shipping, taxes, duties, and market-dependent currency messaging remain accurate and non-speculative.

## 7. Storytelling patterns

### Machine chapters

Sequence: workshop fit → real output → choose 30G/50G → operating flow → mold path → local manufacturing/support → demonstration.

Use bright, accurate product imagery and real factory evidence. Specifications stay near the claim they support. One chapter may use a blue field for emphasis, but most of the journey remains light and inspectable.

### SimMount chapters

Use a contained carbon surface with crisp product photography, compatibility diagrams, and data-like callouts. Density may increase, but the page must remain commerce-first and avoid RGB/gaming theatrics.

### Editorial and service pages

Articles use a strong reading column, visible metadata, useful figures, related products/documents, and plain next actions. Service pages explain input → process → deliverable → constraints → quotation. Neither uses generic card grids as the default rhythm.

## 8. System pages and states

Account, login, registration, addresses, orders, contact, policies, password, gift card, 404, search-empty, collection-empty, cart-empty, loading, validation, and service-error surfaces share the same tokens and controls.

- Empty states teach the next useful action.
- Form errors appear beside the field and in a linked summary when appropriate.
- Loading uses skeletons for content and an inline progress state for buttons.
- Customer and payment forms retain native semantics, autocomplete, and error associations.
- Policy and article prose cap at `72ch`.

## 9. Motion and interaction

- Standard transitions: `180ms cubic-bezier(0.22, 1, 0.36, 1)`.
- Motion communicates state, relationship, or product operation.
- Product galleries, disclosures, drawers, predictive search, variant state, and cart feedback may animate.
- No orchestrated page-load sequence, scroll hijacking, continuous parallax, decorative counters, bounce, or elastic easing.
- Content is visible before enhancement. `prefers-reduced-motion: reduce` removes transforms and delays while preserving clear state changes.

## 10. Elevation and shape

- Flat by default. Canvas/Surface and Carbon/Panel tonal steps create hierarchy.
- Static cards have no shadow.
- Floating navigation, predictive search, drawers, and dialogs may use `0 10px 28px rgba(17, 19, 21, 0.12)` without an additional decorative border when the shadow supplies separation.
- Control feedback may use at most `0 4px 8px` blur.
- Cards top out at `10px`, feature panels at `14px`, and controls at `4px`. Pills are reserved for factual filter chips and compact status tags.

## 11. Shopify implementation rules

- Build reusable sections, blocks, snippets, and token layers rather than template-specific monoliths.
- Every merchant-facing section retains a valid schema with useful settings and sensible empty behavior.
- User-facing interface strings use locale keys; template content remains market-context editable where Shopify supports it.
- Do not hardcode product prices, availability, translated URLs, customer state, cart state, or store-domain URLs.
- Preserve Shopify section rendering, Theme Editor selection, app blocks, dynamic checkout, product-model/media, predictive-search, cart, customer, localization, and analytics hooks.
- `config/settings_data.json` remains merchant-owned and outside production deployment.

## 12. Definition of done

The custom theme system is complete only when:

1. No representative page reads visually or structurally as Dawn.
2. Every template family uses the MALIEV tokens, typography, components, focus system, responsive grid, and state vocabulary.
3. Machines retain demonstration-first conversion and explicit Thailand/THB context.
4. SimMount retains direct international commerce and clear compatibility.
5. IBM Plex Sans, IBM Plex Sans Thai, IBM Plex Mono, Audiowide, Aldrich, and Chakra Petch load locally with their intended scope and weights.
6. All merchant-facing schemas and Shopify commerce behaviors remain valid.
7. Theme Check passes, focused contract checks pass, and the relevant theme suite passes.
8. Desktop and mobile browser checks cover home, each product mode, collections, blog/article, search, cart/drawer, contact/pages/policies, account/auth, password, gift card, and 404.
9. Keyboard focus, reduced motion, localization, empty/error/loading states, and zero horizontal overflow are directly verified.

## 13. Do and do not

### Do

- Let accurate product imagery and construction evidence carry the page.
- Put compatibility, specifications, service, and documentation near the decision.
- Keep navigation and catalog density useful for a growing technical product range.
- Reuse one component vocabulary across every page.
- Compose separately for mobile and real Thai copy.

### Do not

- Copy Keychron, Mode, Framework, or Wooting layouts, colors, components, or voice.
- Preserve Dawn composition under new colors.
- Mix Signal Blue and Sim Cyan on one surface.
- Use cream, gradient text, glassmorphism, decorative grids, broad card shadows, oversized radii, or repeated section eyebrows.
- Hide content behind animation, truncate localized copy, or make product data decorative.
