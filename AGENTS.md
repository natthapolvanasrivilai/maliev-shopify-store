# MALIEV Shopify Theme Guide

This repository contains the editable Shopify Online Store 2.0 theme for `shop.maliev.com`.

## Production boundary

- Store: `10b918-e4.myshopify.com`
- Live theme: `190305730839`
- Merges and pushes to `main` automatically deploy through the guarded GitHub Actions workflow authorized by the store owner.
- Do not push directly to the live theme from a feature branch. Use `scripts/deploy-production.ps1` only for an explicitly authorized recovery deployment, and do not bypass its clean-tree, branch, confirmation, or Theme Check gates.
- Production deployment intentionally excludes `config/settings_data.json` so merchant changes made in the Theme Editor are not overwritten accidentally.

## Development workflow

1. Synchronize production with `pwsh ./scripts/sync-live.ps1` before starting work when Shopify Admin edits may have occurred.
2. Create a feature branch from `main`.
3. Run `npm run dev` for the temporary development theme and hot-reloading preview.
4. Preserve Shopify section and block schemas so non-coders can continue customizing content.
5. Run `npm run verify` before committing.
6. Validate responsive storefront routes before requesting review.

## Design quality

- Use the Impeccable skill for design changes.
- Treat `https://www.maliev.com/` as the visual-language reference for typography, spacing, color, radii, and interaction restraint.
- Validate home, product, collection, blog, article, search, cart, contact, policy, and 404 templates at desktop and mobile widths.
- Preserve accessibility, focus visibility, reduced-motion behavior, and zero horizontal overflow.

## Theme architecture

- Prefer reusable sections, blocks, and snippets over hardcoded page markup.
- Every merchant-facing section must retain a valid `{% schema %}` contract and useful Theme Editor settings.
- Keep user-facing text translatable through locale keys.
- Do not commit credentials, Theme Access tokens, or local `.env` files.
