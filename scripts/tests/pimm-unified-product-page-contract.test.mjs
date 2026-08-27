import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const readThemeFile = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8');

const stripShopifyComment = (source) => source.replace(/^\s*\/\*[\s\S]*?\*\/\s*/, '');

const [section, selector, bento, purchase, ownership, templateSource] = await Promise.all([
  readThemeFile('sections/maliev-pimm-machine-product.liquid'),
  readThemeFile('snippets/pimm-model-selector.liquid'),
  readThemeFile('snippets/pimm-engineering-bento.liquid'),
  readThemeFile('snippets/pimm-purchase-qualification.liquid'),
  readThemeFile('snippets/pimm-ownership.liquid'),
  readThemeFile('templates/product.pimm-configurator.json'),
]);

const template = JSON.parse(stripShopifyComment(templateSource));
const schemaSource = section.match(/{% schema %}([\s\S]*?){% endschema %}/)?.[1];
const schema = JSON.parse(schemaSource);
const renderedContract = [section, selector, bento, purchase, ownership].join('\n');

test('unified template owns one semantic machine presentation', () => {
  assert.equal(template.sections.main.type, 'maliev-pimm-machine-product');
  assert.deepEqual(template.order, ['main']);
  assert.equal(renderedContract.match(/<h1\b/g)?.length, 1);
  assert.match(section, /data-pimm-machine-product/);
  assert.match(selector, /<fieldset[^>]*data-pimm-model-selector/);
  assert.match(selector, /<legend\b/);
  assert.equal(renderedContract.match(/data-pimm-engineering-bento/g)?.length, 1);
  assert.match(section, /<product-form\b/);
  assert.match(section, /{%[-]?\s*form 'product'/);
  assert.match(selector, /name="id"/);
  assert.match(section, /product-form__error-message-wrapper/);
});

test('open editorial sections surround one contained engineering bento', () => {
  const orderedLandmarks = [
    'pimm-machine__hero',
    'pimm-machine__fit',
    "render 'pimm-engineering-bento'",
    'pimm-machine__tooling',
    "render 'pimm-ownership'",
    "render 'pimm-purchase-qualification'",
  ];

  let cursor = -1;
  for (const landmark of orderedLandmarks) {
    const next = section.indexOf(landmark);
    assert.ok(next > cursor, `${landmark} must appear in the required narrative order`);
    cursor = next;
  }

  assert.match(ownership, /<section[^>]*data-pimm-ownership/);
  assert.match(purchase, /<section[^>]*data-pimm-purchase-qualification/);
});

test('factory visit remains primary and precedes the secondary deposit action', () => {
  const visit = purchase.indexOf('data-pimm-book-visit');
  const deposit = purchase.indexOf('data-pimm-deposit-action');

  assert.ok(visit >= 0 && deposit > visit);
  assert.match(purchase, /<a[^>]*class="[^"]*button--primary[^"]*"[^>]*data-pimm-book-visit/);
  assert.match(purchase, /<button[^>]*class="[^"]*button--secondary[^"]*"[^>]*data-pimm-deposit-action/);
});

test('model selection and deposit submission fail closed on malformed product data', () => {
  assert.match(section, /assign model_contract_valid = false/);
  assert.match(section, /selected_variant\.option1/);
  assert.match(section, /block\.settings\.model_code == selected_model_code/);
  assert.match(section, /model_block_match_count == 1/);
  assert.match(section, /specifications\.schema_version == 1/);
  assert.match(section, /specifications\.model == selected_model_code/);
  assert.match(section, /specifications\.shot_capacity_g > 0/);
  assert.match(section, /specifications\.max_melt_temperature_c > 0/);
  assert.match(section, /specifications\.max_air_pressure_mpa > 0/);
  assert.match(section, /specifications\.mold_envelope_mm\.width > 0/);
  assert.match(section, /specifications\.mold_envelope_mm\.height > 0/);
  assert.match(section, /specifications\.mold_envelope_mm\.depth > 0/);
  assert.match(section, /metafields\.custom\.full_machine_price\.value/);
  assert.match(section, /metafields\.custom\.lead_time_days\.value/);
  assert.match(purchase, /products\.product\.unavailable/);
  assert.match(purchase, /unless model_contract_valid[^]*disabled/);
});

test('app blocks stay in one bounded area after purchase qualification', () => {
  const purchaseRender = section.indexOf("render 'pimm-purchase-qualification'");
  const appArea = section.indexOf('data-pimm-app-integrations');
  const appRender = section.indexOf("when '@app'");

  assert.ok(purchaseRender >= 0 && appArea > purchaseRender && appRender > appArea);
  assert.equal(section.match(/data-pimm-app-integrations/g)?.length, 1);
  assert.equal(schema.blocks.filter((block) => block.type === '@app').length, 1);
});

test('section schema exposes only approved links and a two-model contract', () => {
  assert.deepEqual(schema.settings.map((setting) => setting.id), [
    'factory_visit_url',
    'document_url',
    'support_url',
  ]);

  const modelBlock = schema.blocks.find((block) => block.type === 'model');
  assert.ok(modelBlock);
  assert.equal(modelBlock.limit, 2);
  assert.deepEqual(modelBlock.settings.map((setting) => setting.id), [
    'model_code',
    'hero_asset',
    'overview_asset',
    'engineering_asset',
    'tooling_asset',
    'hero_alt_en',
    'hero_alt_th',
    'overview_alt_en',
    'overview_alt_th',
    'engineering_alt_en',
    'engineering_alt_th',
    'tooling_alt_en',
    'tooling_alt_th',
  ]);
});

test('template defaults contain exactly the 30G and 50G asset sets', () => {
  const blocks = template.sections.main.blocks;
  const modelBlocks = Object.values(blocks).filter((block) => block.type === 'model');

  assert.equal(modelBlocks.length, 2);
  assert.deepEqual(modelBlocks.map((block) => block.settings.model_code), ['30G', '50G']);

  assert.deepEqual(
    modelBlocks.map(({ settings }) => [
      settings.hero_asset,
      settings.overview_asset,
      settings.engineering_asset,
      settings.tooling_asset,
    ]),
    [
      [
        'pimm-machine-30g-hero-front.webp',
        'pimm-machine-30g-overview-three-quarter.webp',
        'pimm-machine-30g-engineering-controls.webp',
        'pimm-machine-30g-tooling-front-detail.webp',
      ],
      [
        'pimm-machine-50g-hero-front.webp',
        'pimm-machine-50g-overview-three-quarter.webp',
        'pimm-machine-50g-engineering-controls.webp',
        'pimm-machine-50g-tooling-front-detail.webp',
      ],
    ],
  );
});

test('content and native controls remain available without JavaScript', () => {
  assert.match(selector, /<input[^>]*type="radio"[^>]*name="id"/);
  assert.match(selector, /{%[-]?\s*for variant in product\.variants/);
  assert.match(purchase, /<button[^>]*type="submit"/);
  assert.doesNotMatch(renderedContract, /hidden[^>]*data-pimm-(machine-product|engineering-bento|purchase-qualification)/);
});
