import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import test from 'node:test';

import { validateDesiredProduct } from '../shopify/pimm_unified_product_contract.mjs';

const valid = {
  schema_version: 1,
  status: 'DRAFT',
  published_channels: [],
  option: { name: 'Model', values: ['30G', '50G'] },
  variants: [
    {
      model: '30G',
      currency_code: 'THB',
      deposit_price_minor: 5000,
      full_price_minor: 10000,
      available: true,
      lead_time_days: 30,
      specifications: {
        schema_version: 1,
        model: '30G',
        shot_capacity_g: 30,
        max_melt_temperature_c: 300,
        mold_envelope_mm: { width: 100, height: 100, depth: 100 },
        max_air_pressure_mpa: 0.7,
      },
    },
    {
      model: '50G',
      currency_code: 'THB',
      deposit_price_minor: 10000,
      full_price_minor: 20000,
      available: true,
      lead_time_days: 30,
      specifications: {
        schema_version: 1,
        model: '50G',
        shot_capacity_g: 50,
        max_melt_temperature_c: 350,
        mold_envelope_mm: { width: 240, height: 240, depth: 100 },
        max_air_pressure_mpa: 0.7,
      },
    },
  ],
};

const validatorPath = resolve('scripts/shopify/pimm_unified_product_contract.mjs');

test('accepts one exact unpublished two-model contract', () => {
  assert.deepEqual(validateDesiredProduct(valid), []);
});

test('rejects malformed or missing payload structure', () => {
  assert.ok(validateDesiredProduct(undefined).length > 0);
  assert.ok(validateDesiredProduct(null).length > 0);
  assert.ok(validateDesiredProduct([]).length > 0);
  assert.ok(validateDesiredProduct({}).length > 0);
});

test('rejects publication and option drift', () => {
  assert.ok(validateDesiredProduct({ ...valid, status: 'ACTIVE' }).includes('status must equal DRAFT'));
  assert.ok(validateDesiredProduct({ ...valid, published_channels: ['Online Store'] }).includes('published_channels must be empty'));
  assert.ok(validateDesiredProduct({ ...valid, option: { name: 'Size', values: ['30G', '50G'] } }).includes('option name must equal Model'));
  assert.ok(validateDesiredProduct({ ...valid, option: { name: 'Model', values: ['50G', '30G'] } }).includes('option values must equal 30G,50G'));
});

test('rejects duplicate, missing and extra variants', () => {
  const duplicate = structuredClone(valid);
  duplicate.variants[1].model = '30G';
  assert.ok(validateDesiredProduct(duplicate).includes('variant models must equal ordered 30G,50G'));

  const missing = structuredClone(valid);
  missing.variants.pop();
  assert.ok(validateDesiredProduct(missing).includes('50G variant is required'));

  const extra = structuredClone(valid);
  extra.variants.push({ ...structuredClone(valid.variants[1]), model: '75G' });
  assert.ok(validateDesiredProduct(extra).includes('exactly two variants are required'));
});

test('rejects reversed variant order instead of normalizing it', () => {
  const reversed = structuredClone(valid);
  reversed.variants.reverse();
  assert.ok(validateDesiredProduct(reversed).includes('variant models must equal ordered 30G,50G'));
});

test('rejects invalid money while keeping deposit and displayed full price independent', () => {
  const marketAdjusted = structuredClone(valid);
  marketAdjusted.variants[0].deposit_price_minor = 4999;
  assert.deepEqual(validateDesiredProduct(marketAdjusted), []);

  for (const [field, value] of [
    ['deposit_price_minor', 0],
    ['deposit_price_minor', 5000.5],
    ['full_price_minor', -1],
    ['full_price_minor', 10000.5],
  ]) {
    const payload = structuredClone(valid);
    payload.variants[0][field] = value;
    assert.ok(validateDesiredProduct(payload).some((error) => error.startsWith(`30G ${field === 'deposit_price_minor' ? 'deposit' : 'full price'} must be a positive integer`)));
  }
});

test('rejects non-boolean availability and invalid lead time', () => {
  for (const availability of [1, 'true', null]) {
    const payload = structuredClone(valid);
    payload.variants[0].available = availability;
    assert.ok(validateDesiredProduct(payload).includes('30G availability must be boolean'));
  }

  for (const leadTime of [0, -1, 2.5, '30']) {
    const payload = structuredClone(valid);
    payload.variants[0].lead_time_days = leadTime;
    assert.ok(validateDesiredProduct(payload).includes('30G lead time must be a positive integer'));
  }
});

test('rejects specification schema or model identity drift', () => {
  const wrongSchema = structuredClone(valid);
  wrongSchema.variants[0].specifications.schema_version = 2;
  assert.ok(validateDesiredProduct(wrongSchema).includes('30G specification identity mismatch'));

  const wrongModel = structuredClone(valid);
  wrongModel.variants[1].specifications.model = '30G';
  assert.ok(validateDesiredProduct(wrongModel).includes('50G specification identity mismatch'));
});

test('rejects missing or non-positive required specifications', () => {
  for (const field of ['shot_capacity_g', 'max_melt_temperature_c', 'max_air_pressure_mpa']) {
    for (const value of [undefined, 0, -1, '1']) {
      const payload = structuredClone(valid);
      payload.variants[0].specifications[field] = value;
      assert.ok(validateDesiredProduct(payload).includes(`30G ${field} must be positive`));
    }
  }
});

test('rejects a missing or non-positive three-dimensional mold envelope', () => {
  for (const dimension of ['width', 'height', 'depth']) {
    for (const value of [undefined, 0, -1, '1']) {
      const payload = structuredClone(valid);
      payload.variants[1].specifications.mold_envelope_mm[dimension] = value;
      assert.ok(validateDesiredProduct(payload).includes(`50G mold ${dimension} must be positive`));
    }
  }
});

test('CLI accepts a complete local contract without modifying it', () => {
  const directory = mkdtempSync(join(tmpdir(), 'pimm-contract-'));
  const payloadPath = join(directory, 'desired-product.json');
  try {
    writeFileSync(payloadPath, JSON.stringify(valid));
    const before = execFileSync(process.execPath, ['-e', `process.stdout.write(require('node:fs').readFileSync(${JSON.stringify(payloadPath)}, 'utf8'))`], { encoding: 'utf8' });
    const output = execFileSync(process.execPath, [validatorPath, payloadPath], { encoding: 'utf8' });
    const after = execFileSync(process.execPath, ['-e', `process.stdout.write(require('node:fs').readFileSync(${JSON.stringify(payloadPath)}, 'utf8'))`], { encoding: 'utf8' });
    assert.equal(output.trim(), 'PIMM_DRAFT_PRODUCT_CONTRACT_OK');
    assert.equal(after, before);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('CLI fails closed with actionable errors for missing and invalid JSON files', () => {
  const directory = mkdtempSync(join(tmpdir(), 'pimm-contract-'));
  try {
    const missing = spawnSync(process.execPath, [validatorPath, join(directory, 'missing.json')], { encoding: 'utf8' });
    assert.notEqual(missing.status, 0);
    assert.match(missing.stderr, /Unable to read desired product file/);

    const invalidPath = join(directory, 'invalid.json');
    writeFileSync(invalidPath, '{not json');
    const invalid = spawnSync(process.execPath, [validatorPath, invalidPath], { encoding: 'utf8' });
    assert.notEqual(invalid.status, 0);
    assert.match(invalid.stderr, /Desired product file is not valid JSON/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('CLI prints validation errors and exits nonzero', () => {
  const directory = mkdtempSync(join(tmpdir(), 'pimm-contract-'));
  const payloadPath = join(directory, 'desired-product.json');
  try {
    writeFileSync(payloadPath, JSON.stringify({ ...valid, status: 'ACTIVE' }));
    const result = spawnSync(process.execPath, [validatorPath, payloadPath], { encoding: 'utf8' });
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /status must equal DRAFT/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
