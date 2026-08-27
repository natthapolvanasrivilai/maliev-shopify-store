import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const REQUIRED_MODELS = ['30G', '50G'];
const REQUIRED_SPECIFICATIONS = [
  'shot_capacity_g',
  'max_melt_temperature_c',
  'max_air_pressure_mpa',
];
const REQUIRED_MOLD_DIMENSIONS = ['width', 'height', 'depth'];

function isPositiveNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) && value > 0;
}

function isPositiveInteger(value) {
  return Number.isInteger(value) && value > 0;
}

export function validateDesiredProduct(payload) {
  const errors = [];

  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    errors.push('payload must be a JSON object');
  }
  if (payload?.schema_version !== 1) errors.push('schema_version must equal 1');
  if (payload?.status !== 'DRAFT') errors.push('status must equal DRAFT');
  if (!Array.isArray(payload?.published_channels) || payload.published_channels.length !== 0) {
    errors.push('published_channels must be empty');
  }
  if (payload?.option?.name !== 'Model') errors.push('option name must equal Model');
  if (JSON.stringify(payload?.option?.values) !== JSON.stringify(REQUIRED_MODELS)) {
    errors.push('option values must equal 30G,50G');
  }

  const variants = Array.isArray(payload?.variants) ? payload.variants : [];
  if (variants.length !== 2) errors.push('exactly two variants are required');
  if (JSON.stringify(variants.map((variant) => variant?.model)) !== JSON.stringify(REQUIRED_MODELS)) {
    errors.push('variant models must equal ordered 30G,50G');
  }

  for (const model of REQUIRED_MODELS) {
    const matchingVariants = variants.filter((variant) => variant?.model === model);
    if (matchingVariants.length === 0) {
      errors.push(`${model} variant is required`);
      continue;
    }
    if (matchingVariants.length > 1) {
      errors.push(`${model} variant must be unique`);
      continue;
    }

    const variant = matchingVariants[0];
    if (variant.currency_code !== 'THB') errors.push(`${model} currency must equal THB`);
    if (!isPositiveInteger(variant.deposit_price_minor)) {
      errors.push(`${model} deposit must be a positive integer`);
    }
    if (!isPositiveInteger(variant.full_price_minor)) {
      errors.push(`${model} full price must be a positive integer`);
    }
    if (variant.deposit_price_minor * 2 !== variant.full_price_minor) {
      errors.push(`${model} deposit must equal exactly 50% of full price`);
    }
    if (typeof variant.available !== 'boolean') errors.push(`${model} availability must be boolean`);
    if (!isPositiveInteger(variant.lead_time_days)) {
      errors.push(`${model} lead time must be a positive integer`);
    }

    const specifications = variant.specifications;
    if (specifications?.model !== model || specifications?.schema_version !== 1) {
      errors.push(`${model} specification identity mismatch`);
    }
    for (const key of REQUIRED_SPECIFICATIONS) {
      if (!isPositiveNumber(specifications?.[key])) errors.push(`${model} ${key} must be positive`);
    }
    for (const key of REQUIRED_MOLD_DIMENSIONS) {
      if (!isPositiveNumber(specifications?.mold_envelope_mm?.[key])) {
        errors.push(`${model} mold ${key} must be positive`);
      }
    }
  }

  return errors;
}

function runCli(filePath) {
  if (!filePath) {
    console.error('Usage: node scripts/shopify/pimm_unified_product_contract.mjs <desired-product.json>');
    return 1;
  }

  let source;
  try {
    source = readFileSync(filePath, 'utf8');
  } catch (error) {
    console.error(`Unable to read desired product file: ${error.message}`);
    return 1;
  }

  let payload;
  try {
    payload = JSON.parse(source);
  } catch (error) {
    console.error(`Desired product file is not valid JSON: ${error.message}`);
    return 1;
  }

  const errors = validateDesiredProduct(payload);
  if (errors.length > 0) {
    console.error('PIMM draft product contract validation failed:');
    for (const error of errors) console.error(`- ${error}`);
    return 1;
  }

  console.log('PIMM_DRAFT_PRODUCT_CONTRACT_OK');
  return 0;
}

const invokedPath = process.argv[1] ? pathToFileURL(process.argv[1]).href : '';
if (invokedPath === import.meta.url) {
  process.exitCode = runCli(process.argv[2]);
}
