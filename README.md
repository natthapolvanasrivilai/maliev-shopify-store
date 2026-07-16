# MALIEV Shopify Store

Version-controlled Shopify Online Store 2.0 theme for [shop.maliev.com](https://shop.maliev.com/).

The repository was initialized from the live `Maliev` theme (`190305730839`). Theme code remains Liquid-based and compatible with Shopify's Theme Editor so merchant users can continue changing content, sections, and settings without writing code.

## Prerequisites

- Node.js 20 or newer
- The official Shopify Theme Access app and its theme-development password
- GitHub CLI for repository and pull-request work

Install the pinned Shopify CLI:

```powershell
npm ci
```

Store the Theme Access password outside the repository as the
`SHOPIFY_CLI_THEME_TOKEN` user environment variable. The same value is stored in
GitHub Actions as the encrypted `SHOPIFY_CLI_THEME_TOKEN` repository secret.
Never add the password to an `.env` file or commit it.

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

After a pull request is merged, the successful `Theme Check` workflow
automatically publishes the verified `main` commit to the existing live theme
`190305730839`. The publish job uses the Theme Access secret, requires the check
job to pass, and cannot create or select a different theme.

`config/settings_data.json` is excluded from automatic deployment. This prevents
a stale branch from overwriting merchant-managed Theme Editor configuration.

For a deliberate recovery deployment from a verified local `main`, the guarded
manual command is:

```powershell
pwsh ./scripts/deploy-production.ps1 -ConfirmThemeId 190305730839
```

Deploy `config/settings_data.json` only as a separate, explicitly reviewed
operation when a code change intentionally adds or migrates Theme Editor state.

## Branch workflow

1. Synchronize live Admin edits.
2. Create a feature branch from `main`.
3. Develop with `npm run dev`.
4. Run `npm run verify` and complete responsive browser checks.
5. Open a pull request.
6. Merge only after CI and visual review pass.
7. GitHub Actions automatically publishes the verified `main` commit.
