# PIMM Unified Draft Product Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create and verify one unpublished Shopify Draft product whose only option is `Model` with exact `30G` and `50G` deposit variants.

The local Draft contract validates Admin-currency qualification evidence: variants remain in exact source order `30G`, then `50G`, and both the checkout deposit and the customer-facing full-machine price remain positive THB amounts. The storefront renders `custom.full_machine_price` directly so the approved ฿120,000 / ฿170,000 machine prices are not inferred from tax-adjusted deposit variants.

**Architecture:** First capture both existing products read-only and validate a local desired-state contract. Then duplicate the 30G product through the authenticated Shopify Admin, keep it Draft and unpublished, replace its variant structure, and populate versioned variant metafields from verified source data. Every external write is followed by explicit readback; missing source facts block the write rather than being guessed.

**Tech Stack:** Shopify Admin in the user's authenticated Chrome profile, Node.js 20 built-in test runner, JSON desired-state validation, Shopify product/variant/metafield contracts.

**Spec:** `docs/superpowers/specs/2026-08-26-pimm-unified-product-configurator-design.md`

## Global Constraints

- Store: `10b918-e4.myshopify.com`.
- Source handles: `pneumatic-injection-molding-machine` and `pneumatic-injection-molding-machine-50g`.
- Development product must remain Draft and unpublished from every sales channel.
- Option name must equal `Model`; option values must equal `30G` and `50G`.
- Variant price is the payable 50% deposit; full machine price is a separate verified money metafield.
- Missing price, lead time, mold envelope, capacity, temperature or pressure blocks configuration of that variant.
- Never infer specifications from geometry or copy one model's data to the other.
- Do not modify, archive, unpublish or redirect the two existing products.
- Do not publish the Draft product or deploy the theme.

---

### Task 1: Add a local desired-state validator

**Files:**
- Create: `scripts/shopify/pimm_unified_product_contract.mjs`
- Create: `scripts/tests/pimm-unified-product-contract.test.mjs`

**Interfaces:**
- Consumes: a JSON object captured from authenticated read-only product inspection.
- Produces: `validateDesiredProduct(payload): string[]` and CLI invocation `node scripts/shopify/pimm_unified_product_contract.mjs .codex-tmp/pimm-unified-product/desired-product.json` with exit 0 only for an exact complete contract.

- [ ] **Step 1: Write the failing validator tests**

```javascript
const valid = {
  schema_version: 1,
  status: 'DRAFT',
  published_channels: [],
  option: { name: 'Model', values: ['30G', '50G'] },
  variants: [
    {
      model: '30G', currency_code: 'THB', deposit_price_minor: 5000,
      full_price_minor: 10000, available: true, lead_time_days: 30,
      specifications: {
        schema_version: 1, model: '30G', shot_capacity_g: 30,
        max_melt_temperature_c: 300,
        mold_envelope_mm: { width: 100, height: 100, depth: 100 },
        max_air_pressure_mpa: 0.7,
      },
    },
    {
      model: '50G', currency_code: 'THB', deposit_price_minor: 10000,
      full_price_minor: 20000, available: true, lead_time_days: 30,
      specifications: {
        schema_version: 1, model: '50G', shot_capacity_g: 50,
        max_melt_temperature_c: 350,
        mold_envelope_mm: { width: 240, height: 240, depth: 100 },
        max_air_pressure_mpa: 0.7,
      },
    },
  ],
};

test('accepts one exact unpublished two-model contract', () => {
  assert.deepEqual(validateDesiredProduct(valid), []);
});

test('rejects publication and variant drift while allowing tax-adjusted deposits', () => {
  assert.ok(validateDesiredProduct({ ...valid, status: 'ACTIVE' }).length);
  assert.ok(validateDesiredProduct({ ...valid, option: { name: 'Model', values: ['30 G', '50G'] } }).length);
  const wrongPrice = structuredClone(valid);
  wrongPrice.variants[0].deposit_price_minor = 4999;
  assert.deepEqual(validateDesiredProduct(wrongPrice), []);
});
```

The numeric values in this unit-test fixture exercise schema behavior only; they are not product facts and are never used to create the Shopify product.

- [ ] **Step 2: Run the test and confirm the validator is absent**

Run: `node --test scripts/tests/pimm-unified-product-contract.test.mjs`

Expected: FAIL because the validator module does not exist.

- [ ] **Step 3: Implement exact fail-closed validation**

```javascript
export function validateDesiredProduct(payload) {
  const errors = [];
  if (payload?.schema_version !== 1) errors.push('schema_version must equal 1');
  if (payload?.status !== 'DRAFT') errors.push('status must equal DRAFT');
  if (!Array.isArray(payload?.published_channels) || payload.published_channels.length) errors.push('published_channels must be empty');
  if (payload?.option?.name !== 'Model') errors.push('option name must equal Model');
  if (JSON.stringify(payload?.option?.values) !== JSON.stringify(['30G', '50G'])) errors.push('option values must equal 30G,50G');
  for (const model of ['30G', '50G']) {
    const variant = payload?.variants?.find((item) => item.model === model);
    if (!variant) { errors.push(`${model} variant is required`); continue; }
    if (variant.currency_code !== 'THB') errors.push(`${model} currency must equal THB`);
    if (!Number.isInteger(variant.full_price_minor) || variant.full_price_minor <= 0) errors.push(`${model} full price must be a positive integer`);
    if (!Number.isInteger(variant.lead_time_days) || variant.lead_time_days <= 0) errors.push(`${model} lead time must be positive`);
    if (variant.specifications?.model !== model || variant.specifications?.schema_version !== 1) errors.push(`${model} specification identity mismatch`);
    for (const key of ['shot_capacity_g', 'max_melt_temperature_c', 'max_air_pressure_mpa']) {
      if (!(variant.specifications?.[key] > 0)) errors.push(`${model} ${key} must be positive`);
    }
    for (const key of ['width', 'height', 'depth']) {
      if (!(variant.specifications?.mold_envelope_mm?.[key] > 0)) errors.push(`${model} mold ${key} must be positive`);
    }
  }
  if (payload?.variants?.length !== 2) errors.push('exactly two variants are required');
  return errors;
}
```

The CLI must print the errors and exit 1; it must never write to Shopify.

- [ ] **Step 4: Run focused tests and malformed-input cases**

Run: `node --test scripts/tests/pimm-unified-product-contract.test.mjs`

Expected: PASS, including missing file, invalid JSON, duplicate model, extra variant, zero dimensions and model mismatch cases.

- [ ] **Step 5: Commit the local safety gate**

```powershell
git add -- scripts/shopify/pimm_unified_product_contract.mjs scripts/tests/pimm-unified-product-contract.test.mjs
git commit -m "Validate unified PIMM draft product state"
```

### Task 2: Capture and validate source product facts read-only

**Files:**
- Create locally, never commit: `.codex-tmp/pimm-unified-product/source-products.json`
- Create locally, never commit: `.codex-tmp/pimm-unified-product/desired-product.json`

**Interfaces:**
- Consumes: authenticated Shopify Admin pages for both existing handles and owner-approved product documentation.
- Produces: a complete desired-state JSON accepted by Task 1's validator.

- [ ] **Step 1: Preflight authenticated Admin access**

Open each source product in the user's signed-in Chrome profile. Record product ID, handle, status, sales channels, title, current full price, availability, lead-time metafield and all existing technical metafields. Do not click Save.

- [ ] **Step 2: Reconcile source facts with checked-in evidence**

Confirm 30G capacity `30 g`, maximum temperature `300 °C`, maximum input air pressure `0.7 MPa`, two `300 W` heating zones and controller `300/300`. Confirm 50G capacity `50 g`, maximum temperature `350 °C`, mold envelope `240 x 240 x 100 mm`, two `350 W` heating zones and controller `350/350`. Read the 30G mold envelope and any 50G pressure limit from the current owner-approved product record/documentation; do not infer them from CAD.

- [ ] **Step 3: Stop on any missing or conflicting fact**

If full price, lead time or any required specification is absent or contradictory, report the exact field and source conflict. Do not proceed to product duplication until the owner resolves it.

- [ ] **Step 4: Build the local desired-state file**

Populate `desired-product.json` with exact captured full prices in minor THB units, deposits equal to half, exact lead time, availability and complete specification payloads. Include `status: DRAFT`, `published_channels: []` and exact Model values.

- [ ] **Step 5: Validate before any write**

Run: `node scripts/shopify/pimm_unified_product_contract.mjs .codex-tmp/pimm-unified-product/desired-product.json`

Expected: exit 0 and `PIMM_DRAFT_PRODUCT_CONTRACT_OK`.

No repository commit applies to authenticated local snapshots.

### Task 3: Duplicate the 30G product as a hidden Draft

**Files:**
- External Shopify state only.
- Update locally, never commit: `.codex-tmp/pimm-unified-product/draft-readback.json`

**Interfaces:**
- Consumes: validated desired state from Task 2.
- Produces: one new Draft product titled `PIMM Pneumatic Injection Molding Machine (Development)` with handle `pimm-pneumatic-injection-molding-machine-development` and no sales-channel publication.

- [ ] **Step 1: Reconfirm the write boundary**

Read back both source products and verify no edit is pending. Confirm the duplicate action is targeting the 30G source and that the duplicate dialog status is Draft.

- [ ] **Step 2: Create exactly one duplicate**

In Shopify Admin choose Duplicate, set the exact development title, choose Draft, preserve media/metafields for later reconciliation, and create the duplicate. Do not select Active or Unlisted.

- [ ] **Step 3: Verify immediate safe state**

Read back status `Draft`, exact handle, zero published sales channels and a distinct product ID. Confirm the two source product IDs and statuses are unchanged.

- [ ] **Step 4: Fail closed on accidental exposure**

If the duplicate is Active, Unlisted or attached to any channel, immediately change only the duplicate back to Draft, verify zero channels, record the correction and stop before variant edits.

No repository commit applies to this scoped external-state write.

### Task 4: Configure exact Model variants and metafields

**Files:**
- External Shopify state only.
- Update locally, never commit: `.codex-tmp/pimm-unified-product/draft-readback.json`

**Interfaces:**
- Consumes: validated `desired-product.json` and Draft product ID from Task 3.
- Produces: exact `Model` variants plus `custom.full_machine_price`, `custom.lead_time_days` and `custom.pimm_specifications` variant metafields.

- [ ] **Step 1: Replace the option structure**

Set the product's single option name to `Model`. Create exactly `30G` and `50G`. Remove the duplicated default/source configuration only after both target variants exist and the product remains Draft.

- [ ] **Step 2: Apply prices and availability from desired state**

Set each variant price to its 50% deposit. Keep full machine price in the money metafield. Apply captured availability and lead time; do not hardcode the values in theme settings.

- [ ] **Step 3: Apply versioned specification JSON**

Write each exact `custom.pimm_specifications` payload. Verify model identity, numeric values and JSON type in Admin readback.

- [ ] **Step 4: Confirm no inherited 30G-only product data remains authoritative**

Inspect product title, description, SEO preview, media and product-level metafields. Remove or rewrite only duplicate data that incorrectly claims the family is 30G-only. Do not change the source product.

- [ ] **Step 5: Re-read the complete Draft product**

Capture status, channels, option/variants, IDs, prices, availability and metafields into `draft-readback.json`. Normalize it to the Task 1 desired-state shape.

- [ ] **Step 6: Run the validator against readback**

Run: `node scripts/shopify/pimm_unified_product_contract.mjs .codex-tmp/pimm-unified-product/draft-readback.json`

Expected: exit 0 and exact parity with `desired-product.json` for every contract field.

- [ ] **Step 7: Verify the production boundary**

Confirm both existing products remain active exactly as before, the new product remains Draft, no channel includes it and no production theme/template assignment was changed.

No repository commit applies to this external-state configuration task. Report the new Draft product ID and handle, source IDs, readback evidence and explicit no-publication result.
