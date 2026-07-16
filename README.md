# MALIEV Shopify Store

Version-controlled Shopify Online Store 2.0 theme for [shop.maliev.com](https://shop.maliev.com/).

The repository was initialized from the live `Maliev` theme (`190305730839`). Theme code remains Liquid-based and compatible with Shopify's Theme Editor so merchant users can continue changing content, sections, and settings without writing code.

## Prerequisites

- Node.js 20 or newer
- A Shopify account with Themes permission
- GitHub CLI for repository and pull-request work

Install the pinned Shopify CLI:

```powershell
npm ci
```

## Local development

Start a temporary development theme backed by real store data:

```powershell
npm run dev
```

Shopify CLI provides a local hot-reloading URL, a Theme Editor URL, and a shareable preview URL. The temporary development theme does not change production.

## Verification

Run the same Liquid, JSON, schema, and theme checks used by GitHub Actions:

```powershell
npm run verify
```

Pull requests and pushes to `main` must pass the `Theme Check` workflow.

For design changes, also inspect the representative storefront routes at mobile and desktop widths:

- Home
- Product
- Collection
- Blog and article
- Search
- Cart
- Contact
- Policy
- 404

## Synchronizing Shopify Admin edits

Theme Editor and code-editor changes can happen outside Git. Synchronize them before starting a branch:

```powershell
pwsh ./scripts/sync-live.ps1
```

Review and commit the resulting diff before beginning unrelated work.

## Production deployment

Production deployment is manual and intentionally guarded. It requires `main`, a clean working tree, a passing Theme Check, and the exact live theme ID:

```powershell
pwsh ./scripts/deploy-production.ps1 -ConfirmThemeId 190305730839
```

The deployment excludes `config/settings_data.json` by default. This prevents a stale branch from overwriting merchant-managed Theme Editor configuration. Deploy that file only as a separate, explicitly reviewed operation.

## Branch workflow

1. Synchronize live Admin edits.
2. Create a feature branch from `main`.
3. Develop with `npm run dev`.
4. Run `npm run verify` and complete responsive browser checks.
5. Open a pull request.
6. Merge only after CI and visual review pass.
7. Deploy the reviewed `main` commit manually.
