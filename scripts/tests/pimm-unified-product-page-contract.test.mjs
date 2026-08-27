import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const readThemeFile = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8');

const stripShopifyComment = (source) => source.replace(/^\s*\/\*[\s\S]*?\*\/\s*/, '');

const [section, selector, bento, purchase, ownership, templateSource, js] = await Promise.all([
  readThemeFile('sections/maliev-pimm-machine-product.liquid'),
  readThemeFile('snippets/pimm-model-selector.liquid'),
  readThemeFile('snippets/pimm-engineering-bento.liquid'),
  readThemeFile('snippets/pimm-purchase-qualification.liquid'),
  readThemeFile('snippets/pimm-ownership.liquid'),
  readThemeFile('templates/product.pimm-configurator.json'),
  readThemeFile('assets/maliev-pimm-machine.js').catch(() => ''),
]);

const template = JSON.parse(stripShopifyComment(templateSource));
const schemaSource = section.match(/{% schema %}([\s\S]*?){% endschema %}/)?.[1];
const schema = JSON.parse(schemaSource);
const renderedContract = [section, selector, bento, purchase, ownership].join('\n');
const variantPayloadSource = section.match(/<script[^>]*data-pimm-variant-data[^>]*>([\s\S]*?)<\/script>/)?.[1] ?? '';

const variantFixture = ({ model, id, available = true, contractValid = true }) => ({
  id,
  model,
  depositPrice: model === '30G' ? 'THB 49,500.00' : 'THB 79,439.25',
  fullPrice: model === '30G' ? 'THB 99,000.00' : 'THB 158,878.50',
  available,
  leadTime: '30-day production lead time',
  specifications: {
    schema_version: 1,
    model,
    shot_capacity_g: model === '30G' ? 30 : 50,
    max_melt_temperature_c: model === '30G' ? 300 : 350,
    mold_envelope_mm: { width: 240, height: 240, depth: model === '30G' ? 150 : 100 },
    max_air_pressure_mpa: 0.7,
  },
  media: {
    hero: `https://cdn.example.test/${model}/hero.webp`,
    overview: `https://cdn.example.test/${model}/overview.webp`,
    engineering: `https://cdn.example.test/${model}/engineering.webp`,
    tooling: `https://cdn.example.test/${model}/tooling.webp`,
  },
  statusText: available && contractValid ? 'Made to order' : available ? 'Unavailable' : 'Out of stock',
  contractValid,
});

const createControllerHarness = (variants) => {
  let Controller;
  const browser = {
    HTMLElement: class {},
    URL,
    customElements: {
      define(name, constructor) {
        if (name === 'pimm-machine-product') Controller = constructor;
      },
      get() {
        return undefined;
      },
    },
    window: {
      location: { href: 'https://shop.example.test/products/pimm' },
      history: {
        replaceState(_state, _title, url) {
          browser.window.location.href = String(url);
        },
      },
    },
  };

  vm.runInNewContext(js, browser);
  assert.ok(Controller, 'controller must register the pimm-machine-product custom element');

  const payload = {
    textContent: JSON.stringify(variants),
    dataset: { pimmInvalidMessage: 'Unavailable' },
  };
  const values = ['depositPrice', 'fullPrice', 'leadTime'].map((field) => ({
    dataset: { pimmModelValue: field },
    textContent: '',
  }));
  const selected = { textContent: '' };
  const status = { textContent: '' };
  const deposit = { disabled: false };
  const factoryVisit = { href: '/pages/contact' };
  const radios = variants.map((variant, index) => ({ value: String(variant.id), checked: index === 0 }));
  const mediaGroups = variants.map((variant) => ({ dataset: { pimmMediaModel: variant.model }, hidden: false }));
  const mediaSlots = ['hero', 'overview', 'engineering', 'tooling'].map((slot) => ({
    dataset: { pimmMediaSlot: slot },
    src: '',
    hidden: false,
  }));

  const controller = new Controller();
  controller.querySelector = (selector) => ({
    '[data-pimm-variant-data]': payload,
    '[data-pimm-selected-model]': selected,
    '[data-pimm-variant-status]': status,
    '[data-pimm-deposit-action]': deposit,
    '[data-pimm-book-visit]': factoryVisit,
  })[selector] ?? null;
  controller.querySelectorAll = (selector) => ({
    '[data-pimm-model-value]': values,
    '[data-pimm-model-radio]': radios,
    '[data-pimm-media-model]': mediaGroups,
    '[data-pimm-media-slot]': mediaSlots,
  })[selector] ?? [];
  controller.addEventListener = () => {};
  controller.connectedCallback();

  return { controller, values, selected, status, deposit, factoryVisit, radios, mediaGroups, mediaSlots, browser };
};

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

test('product model structure must be exactly Model with ordered 30G and 50G variants', () => {
  assert.match(section, /assign product_model_contract_valid = false/);
  assert.match(section, /product\.options\.size == 1/);
  assert.match(section, /product\.options\.first == 'Model'/);
  assert.match(section, /product\.variants\.size == 2/);
  assert.match(section, /assign first_model_variant = product\.variants\.first/);
  assert.match(section, /assign second_model_variant = product\.variants\.last/);
  assert.match(section, /first_model_variant\.option1 == '30G'/);
  assert.match(section, /second_model_variant\.option1 == '50G'/);

  const optionCountGate = section.indexOf('product.options.size == 1');
  const optionNameGate = section.indexOf("product.options.first == 'Model'");
  const variantCountGate = section.indexOf('product.variants.size == 2');
  const firstModelGate = section.indexOf("first_model_variant.option1 == '30G'");
  const secondModelGate = section.indexOf("second_model_variant.option1 == '50G'");
  const productGate = section.indexOf('if product_model_contract_valid');
  const selectedVariantGate = section.indexOf("if selected_model_code == '30G' or selected_model_code == '50G'");
  const enableContract = section.indexOf('assign model_contract_valid = true');

  assert.ok(optionNameGate > optionCountGate);
  assert.ok(variantCountGate > optionNameGate);
  assert.ok(firstModelGate > variantCountGate && secondModelGate > firstModelGate);
  assert.ok(productGate > secondModelGate && selectedVariantGate > productGate);
  assert.ok(enableContract > selectedVariantGate);
  assert.equal(section.match(/assign model_contract_valid = true/g)?.length, 1);
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

test('variant payload is JSON-safe and radios submit real variant IDs', () => {
  assert.match(section, /maliev-pimm-machine\.js/);
  assert.match(section, /product-form\.js/);
  assert.match(section, /<script[^>]*type="application\/json"[^>]*data-pimm-variant-data/);
  assert.match(selector, /type="radio"[^>]*name="id"[^>]*value="\{\{ variant\.id \}\}"[^>]*data-pimm-model-radio/s);
  assert.match(section, /variant\.option1 \| strip_html \| json/);
  assert.match(section, /variant\.price \| money_with_currency \| strip_html \| json/);
  assert.match(section, /variant\.metafields\.custom\.pimm_specifications\.value \| json/);
  assert.match(section, /"contractValid": \{\{ variant_contract_valid \| json \}\}/);
  for (const key of [
    'id',
    'model',
    'depositPrice',
    'fullPrice',
    'available',
    'leadTime',
    'specifications',
    'media',
    'statusText',
    'contractValid',
  ]) {
    assert.match(variantPayloadSource, new RegExp(`"${key}"\\s*:`));
  }
  for (const slot of ['hero', 'overview', 'engineering', 'tooling']) {
    assert.match(variantPayloadSource, new RegExp(`"${slot}"\\s*:`));
  }
  assert.match(variantPayloadSource, /variant_model_block_count == 1/);
  assert.match(variantPayloadSource, /variant_specifications\.schema_version == 1/);
  assert.match(variantPayloadSource, /variant_specifications\.model == variant_model/);
  assert.match(purchase, /role="status"[^>]*aria-live="polite"[^>]*aria-atomic="true"/);
  assert.match(purchase, /render 'loading-spinner'/);
  assert.doesNotMatch(js, /innerHTML|insertAdjacentHTML|document\.write/);
});

test('controller selects a valid variant without rebuilding DOM', () => {
  const variants = [variantFixture({ model: '30G', id: 101 }), variantFixture({ model: '50G', id: 202 })];
  const harness = createControllerHarness(variants);

  harness.controller.selectVariant(202);

  assert.equal(harness.selected.textContent, '50G');
  assert.equal(harness.status.textContent, 'Made to order');
  assert.equal(harness.deposit.disabled, false);
  assert.deepEqual(harness.values.map((node) => node.textContent), [
    'THB 79,439.25',
    'THB 158,878.50',
    '30-day production lead time',
  ]);
  assert.deepEqual(harness.radios.map((radio) => radio.checked), [false, true]);
  assert.match(harness.browser.window.location.href, /variant=202$/);
  assert.deepEqual(harness.mediaGroups.map((group) => group.hidden), [true, false]);
  assert.deepEqual(harness.mediaSlots.map((slot) => slot.src), Object.values(variants[1].media));
  assert.equal(harness.factoryVisit.href, '/pages/contact');
});

test('malformed, unavailable and unknown selections disable deposit without model fallback', () => {
  const malformed = variantFixture({ model: '50G', id: 202, contractValid: false });
  const harness = createControllerHarness([variantFixture({ model: '30G', id: 101 }), malformed]);

  harness.controller.selectVariant(202);
  assert.equal(harness.selected.textContent, '50G');
  assert.equal(harness.status.textContent, 'Unavailable');
  assert.equal(harness.deposit.disabled, true);
  assert.deepEqual(harness.radios.map((radio) => radio.checked), [false, true]);
  assert.deepEqual(harness.mediaGroups.map((group) => group.hidden), [true, true]);
  assert.ok(harness.mediaSlots.every((slot) => slot.hidden));
  assert.equal(harness.factoryVisit.href, '/pages/contact');

  const selectedBeforeUnknown = harness.selected.textContent;
  harness.controller.selectVariant(999);
  assert.equal(harness.selected.textContent, selectedBeforeUnknown);
  assert.equal(harness.status.textContent, 'Unavailable');
  assert.equal(harness.deposit.disabled, true);
  assert.deepEqual(harness.radios.map((radio) => radio.checked), [false, true]);

  const unavailable = createControllerHarness([
    variantFixture({ model: '30G', id: 101 }),
    variantFixture({ model: '50G', id: 202, available: false }),
  ]);
  unavailable.controller.selectVariant(202);
  assert.equal(unavailable.status.textContent, 'Out of stock');
  assert.equal(unavailable.deposit.disabled, true);
  assert.deepEqual(unavailable.mediaGroups.map((group) => group.hidden), [true, false]);
});

test('invalid payload structure hides all model media at connection time', () => {
  const reversed = createControllerHarness([
    variantFixture({ model: '50G', id: 202 }),
    variantFixture({ model: '30G', id: 101 }),
  ]);

  assert.equal(reversed.deposit.disabled, true);
  assert.equal(reversed.status.textContent, 'Unavailable');
  assert.ok(reversed.mediaGroups.every((group) => group.hidden));
  assert.ok(reversed.mediaSlots.every((slot) => slot.hidden));
});
