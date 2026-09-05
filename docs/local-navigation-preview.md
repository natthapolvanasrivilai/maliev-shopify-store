# Local storefront navigation preview

The new PIMM product is still a Shopify draft. Production product handles and
collection template assignments are deliberately unchanged. To test ordinary
storefront links against the new designs locally, use:

```powershell
npm run dev:local
```

Run this from the `pimm-unified-configurator` worktree. It starts a loopback-only
router on **http://127.0.0.1:9494** and Shopify theme dev on port **9495**, using
the current worktree. Browse port 9494; port 9495 bypasses the navigation router.
Stop the previous development server before starting this command.

The ignored `.env.local-preview` file must contain `PIMM_PREVIEW_KEY` from the
draft product's preview link. Never commit that file or put its value into theme
settings, theme assets, this document, or a public link. A missing/invalid key
prevents startup. If Shopify revokes the preview key, refresh the ignored file.

## Local route mapping

| Normal path | Local destination |
| --- | --- |
| `/collections/เครื่องฉีดพลาสติก` | New two-machine comparison preview |
| `/products/pneumatic-injection-molding-machine` | New configurator, 30G selected |
| `/products/pneumatic-injection-molding-machine-50g` | New configurator, 50G selected |
| `/products/pimm-pneumatic-injection-molding-machine-development` | New configurator, requested valid model variant |

The same rules support `/th/` and `/en/` prefixes, encoded Thai paths, and
collection-scoped product URLs. Old compressor-option variant IDs resolve to the
model implied by the old product handle; they are not equivalent commerce options
on the new draft. Known new 30G/50G variant IDs are preserved.

These are temporary, non-cacheable HTTP redirects: after following a normal link,
the address bar displays Shopify's localized `products_preview` URL. Existing
preview URLs are passed through, so configurator section requests and model
switching keep their current contract. Unrelated pages, JSON endpoints, cart
requests and POST bodies are not redirected. The proxy passes through upstream
errors, cookies and binary assets, and forwards WebSocket upgrades. Text responses
and redirect headers translate the private upstream origin back to port 9494 so
generated links do not escape the router. The upstream receives its own Host
header, required by Shopify CLI's development-server validation.

This is navigation acceptance only, not a production routing migration or a
checkout simulation. It does not publish products, change Shopify Admin settings,
deploy a production theme, or make draft variants purchasable.

## Verification (2026-09-02)

- Regression first: ten route assertions failed against the original no-routing
  behavior, then passed after implementation.
- `npm run verify`: Theme Check has zero errors and three pre-existing warnings
  in Shopify CLI dependency templates; all 81 existing regression tests pass.
- `PIMM_LOCAL_ROUTE_ACCEPTANCE=1 npm run verify:local-routes`: route coverage
  includes real HTTP proxy behavior and six live EN/TH collection/product routes.
  The hot-reload streaming regression also confirms events are not buffered.
- `node --check` for both server modules and `git diff --check` pass. These Node
  scripts have no compiled build target.
- In-app browser: catalogue's machine-family CTA opens the new comparison; its
  50G CTA opens the initialized configurator with variant 54823758659863. Direct
  Thai 50G navigation preserves `lang=th` and the same model selection.
- The full responsive browser suite reaches the navigation stage but fails on
  `/cart.js` returning 401 (expired/revoked/invalid access token). Direct requests
  to Shopify CLI on port 9495 reproduce the same error without this router.
  This remains an upstream development authentication blocker; full browser-suite
  acceptance is not claimed. Re-run the suite after that session is repaired.
