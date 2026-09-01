import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import test from 'node:test';

const readThemeFile = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8');
const stripShopifyComment = (source) => source.replace(/^\s*\/\*[\s\S]*?\*\/\s*/, '');
const getPath = (value, path) => path.split('.').reduce((current, key) => current?.[key], value);
const flattenKeys = (value, prefix = '') => Object.entries(value ?? {}).flatMap(([key, child]) => {
  const path = prefix ? `${prefix}.${key}` : key;
  return child && typeof child === 'object' && !Array.isArray(child) ? flattenKeys(child, path) : [path];
});
const interpolationVariables = (value) => [...String(value).matchAll(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g)]
  .map((match) => match[1])
  .sort();

test('alternate collection template contains only the dedicated PIMM comparison section', async () => {
  const source = await readThemeFile('templates/collection.pimm-machines.json');
  const template = JSON.parse(stripShopifyComment(source));

  assert.deepEqual(template.order, ['main']);
  assert.deepEqual(Object.keys(template.sections), ['main']);
  assert.equal(template.sections.main.type, 'maliev-pimm-collection');
  assert.deepEqual(template.sections.main.settings, {
    pimm_product: 'pimm-pneumatic-injection-molding-machine-development',
    support_url: '',
    factory_visit_url: '',
  });
});

test('section resolves the exact two-model commerce contract and fails closed', async () => {
  const section = await readThemeFile('sections/maliev-pimm-collection.liquid');

  assert.match(section, /section\.settings\.pimm_product/);
  assert.match(section, /pimm_product\.options\.size == 1/);
  assert.match(section, /pimm_product\.options\.first == 'Model'/);
  assert.match(section, /pimm_product\.variants\.size == 2/);
  assert.match(section, /case variant\.option1 \| strip/);
  assert.match(section, /when '30G'[\s\S]*assign model_30g = variant/);
  assert.match(section, /when '50G'[\s\S]*assign model_50g = variant/);
  assert.match(section, /variant\.metafields\.custom\.full_machine_price\.value/);
  assert.match(section, /variant\.metafields\.custom\.pimm_specifications\.value/);
  assert.match(section, /variant\.metafields\.custom\.lead_time_days\.value/);
  assert.match(section, /specifications\.schema_version == 1/);
  assert.match(section, /specifications\.model == variant_model/);
  assert.match(section, /full_price > 0/);
  assert.match(section, /lead_time_days > 0/);
  assert.match(section, /if contract_valid[\s\S]*application\/ld\+json/);
  assert.match(section, /unless contract_valid[\s\S]*products\.pimm_collection\.configuration_error/);
  assert.doesNotMatch(section, /120[,.]000|170[,.]000|variant\.price\s*\|\s*times/);
});

test('valid server fallback exposes semantic cards dossiers payload and canonical variant routes', async () => {
  const section = await readThemeFile('sections/maliev-pimm-collection.liquid');

  assert.match(section, /<pimm-collection-comparison[^>]*data-pimm-collection-comparison/);
  assert.match(section, /data-header-overlay-sentinel/);
  assert.match(section, /data-header-overlay-tone="bright"/);
  assert.equal(section.match(/<h1\b/g)?.length, 1);
  assert.equal(section.match(/<article\b/g)?.length, 2);
  assert.match(section, /<aside[^>]*data-pimm-collection-dossier/);
  assert.equal(section.match(/data-pimm-collection-inline-dossier/g)?.length, 2);
  assert.match(section, /aria-live="polite"/);
  assert.match(section, /data-pimm-collection-models/);
  assert.match(section, /"id":\s*\{\{ variant\.id \| json \}\}/);
  assert.match(section, /"model":/);
  assert.match(section, /"url":/);
  assert.match(section, /"fullPrice":/);
  assert.match(section, /"available":/);
  assert.match(section, /"leadTime":/);
  assert.match(section, /"specifications":\s*\{/);
  assert.match(section, /"shotCapacityG":/);
  assert.match(section, /"maxMeltTemperatureC":/);
  assert.match(section, /"moldEnvelopeMm":\s*\{/);
  assert.match(section, /"maxAirPressureMpa":/);
  assert.match(section, /\?variant=/);
  assert.equal(section.match(/type="application\/ld\+json"/g)?.length, 1);
  assert.match(section, /"@type": "CollectionPage"/);
  assert.match(section, /"@type": "ItemList"/);
  assert.equal(section.match(/"@type": "ListItem"/g)?.length, 2);
});

test('cards own six unique collection-only physical render frames', async () => {
  const section = await readThemeFile('sections/maliev-pimm-collection.liquid');
  const filenames = section.match(/maliev-pimm-collection-20260901-r01-[^'"\s]+\.webp/g) ?? [];

  assert.equal(filenames.length, 6);
  assert.equal(new Set(filenames).size, 6);
  assert.deepEqual(filenames.toSorted(), [
    'maliev-pimm-collection-20260901-r01-30g-front.webp',
    'maliev-pimm-collection-20260901-r01-30g-left.webp',
    'maliev-pimm-collection-20260901-r01-30g-right.webp',
    'maliev-pimm-collection-20260901-r01-50g-front.webp',
    'maliev-pimm-collection-20260901-r01-50g-left.webp',
    'maliev-pimm-collection-20260901-r01-50g-right.webp',
  ]);
  assert.equal(section.match(/data-pimm-collection-frame="front"[^>]*>[\s\S]*?<img[^>]*alt="[^"]+"/g)?.length, 2);
  assert.equal(section.match(/data-pimm-collection-frame="(?:left|right)"[^>]*>[\s\S]*?<img[^>]*alt=""/g)?.length, 4);
  assert.doesNotMatch(section, /pimm-master-20260901-r05|maliev-pimm-home|maliev-pimm-catalog/);
});

test('every installed locale carries the collection key and interpolation contract', async () => {
  const [english, thai] = await Promise.all([
    readThemeFile('locales/en.default.json').then(stripShopifyComment).then(JSON.parse),
    readThemeFile('locales/th.json').then(stripShopifyComment).then(JSON.parse),
  ]);
  const englishCollection = getPath(english, 'products.pimm_collection');
  const thaiCollection = getPath(thai, 'products.pimm_collection');

  assert.ok(englishCollection);
  assert.ok(thaiCollection);
  const englishKeys = flattenKeys(englishCollection).sort();
  const thaiKeys = flattenKeys(thaiCollection).sort();
  assert.deepEqual(thaiKeys, englishKeys);
  const localeNames = (await readdir(new URL('../../locales/', import.meta.url)))
    .filter((name) => name.endsWith('.json') && !name.endsWith('.schema.json'));
  assert.equal(localeNames.length, 31);
  for (const name of localeNames) {
    const locale = JSON.parse(stripShopifyComment(await readThemeFile(`locales/${name}`)));
    const collection = getPath(locale, 'products.pimm_collection');
    assert.ok(collection, `${name} is missing products.pimm_collection`);
    assert.deepEqual(flattenKeys(collection).sort(), englishKeys, `${name} key paths drifted`);
    if (name !== 'en.default.json' && name !== 'th.json') {
      assert.deepEqual(collection, englishCollection, `${name} must use the approved English fallback copy`);
    }
    for (const key of englishKeys) {
      assert.deepEqual(
        interpolationVariables(getPath(collection, key)),
        interpolationVariables(getPath(englishCollection, key)),
        `${name}:${key}`,
      );
    }
  }
  assert.equal(englishCollection.title, 'Choose the machine for your workshop');
  assert.equal(thaiCollection.title, 'เลือกเครื่องที่เหมาะกับเวิร์กช็อปของคุณ');
});

test('section schema exposes only the canonical product and optional support destinations', async () => {
  const section = await readThemeFile('sections/maliev-pimm-collection.liquid');
  const schema = JSON.parse(section.match(/{% schema %}([\s\S]*?){% endschema %}/)?.[1]);

  assert.deepEqual(schema.settings.map((setting) => setting.id), ['pimm_product', 'support_url', 'factory_visit_url']);
  assert.equal(schema.settings[0].type, 'product');
  assert.deepEqual(schema.settings.slice(1).map((setting) => setting.type), ['url', 'url']);
});
