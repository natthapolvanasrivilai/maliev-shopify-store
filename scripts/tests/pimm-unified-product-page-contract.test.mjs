import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const readThemeFile = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8');

const stripShopifyComment = (source) => source.replace(/^\s*\/\*[\s\S]*?\*\/\s*/, '');

const [section, selector, bento, purchase, ownership, templateSource, js, css, enLocaleSource, thLocaleSource] = await Promise.all([
  readThemeFile('sections/maliev-pimm-machine-product.liquid'),
  readThemeFile('snippets/pimm-model-selector.liquid'),
  readThemeFile('snippets/pimm-engineering-bento.liquid'),
  readThemeFile('snippets/pimm-purchase-qualification.liquid'),
  readThemeFile('snippets/pimm-ownership.liquid'),
  readThemeFile('templates/product.pimm-configurator.json'),
  readThemeFile('assets/maliev-pimm-machine.js').catch(() => ''),
  readThemeFile('assets/maliev-pimm-machine.css').catch(() => ''),
  readThemeFile('locales/en.default.json'),
  readThemeFile('locales/th.json'),
]);

const template = JSON.parse(stripShopifyComment(templateSource));
const enLocale = JSON.parse(stripShopifyComment(enLocaleSource));
const thLocale = JSON.parse(stripShopifyComment(thLocaleSource));
const storefrontLocaleNames = (await readdir(new URL('../../locales/', import.meta.url)))
  .filter((name) => name.endsWith('.json') && !name.endsWith('.schema.json'))
  .sort();
const storefrontLocales = await Promise.all(
  storefrontLocaleNames.map(async (name) => ({
    name,
    value: JSON.parse(stripShopifyComment(await readThemeFile(`locales/${name}`))),
  })),
);
const schemaSource = section.match(/{% schema %}([\s\S]*?){% endschema %}/)?.[1];
const schema = JSON.parse(schemaSource);
const sectionRuntime = section.split('{% schema %}')[0];
const renderedContract = [section, selector, bento, purchase, ownership].join('\n');
const variantPayloadSource = section.match(/<script[^>]*data-pimm-variant-data[^>]*>([\s\S]*?)<\/script>/)?.[1] ?? '';

const flattenKeys = (value, prefix = '') =>
  Object.entries(value).flatMap(([key, nested]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return nested && typeof nested === 'object' && !Array.isArray(nested) ? flattenKeys(nested, path) : [path];
  });

const getPath = (value, path) => path.split('.').reduce((current, key) => current?.[key], value);

const placeholders = (value) =>
  [...String(value).matchAll(/{{\s*([\w.]+)\s*}}/g)].map((match) => match[1]).sort();

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
    hero: { src: `https://cdn.example.test/${model}/hero.webp`, alt: `${model} machine front view` },
    overview: { src: `https://cdn.example.test/${model}/overview.webp`, alt: `${model} machine overview` },
    engineering: { src: `https://cdn.example.test/${model}/engineering.webp`, alt: `${model} engineering detail` },
    tooling: { src: `https://cdn.example.test/${model}/tooling.webp`, alt: `${model} tooling detail` },
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
  const mediaGroups = variants.flatMap((variant) =>
    ['hero', 'overview', 'engineering', 'tooling'].map((slot) => {
      const image = {
        src: variant.media[slot].src,
        alt: variant.media[slot].alt,
        decodeCount: 0,
        decode() {
          this.decodeCount += 1;
          return Promise.resolve();
        },
      };

      return {
        dataset: { pimmMediaModel: variant.model, pimmMediaSlot: slot },
        hidden: false,
        ariaHidden: 'false',
        image,
        querySelector(selector) {
          return selector === 'img' ? image : null;
        },
      };
    }),
  );
  const specificationNodes = [
    'shot_capacity_g',
    'max_melt_temperature_c',
    'mold_envelope',
    'max_air_pressure_mpa',
  ].map((field) => ({ dataset: { pimmSpec: field }, textContent: '', ariaLabel: '' }));
  const specificationUnits = [
    'shot_capacity_g',
    'max_melt_temperature_c',
    'mold_envelope',
    'max_air_pressure_mpa',
  ].map((field) => ({ dataset: { pimmSpecUnit: field }, hidden: false, ariaHidden: 'true' }));

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
    '[data-pimm-spec]': specificationNodes,
    '[data-pimm-spec-unit]': specificationUnits,
  })[selector] ?? [];
  controller.addEventListener = () => {};
  controller.connectedCallback();

  return {
    controller,
    values,
    selected,
    status,
    deposit,
    factoryVisit,
    radios,
    mediaGroups,
    specificationNodes,
    specificationUnits,
    browser,
  };
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

test('restrained workbench stylesheet composes one open responsive product page', () => {
  assert.match(section, /maliev-pimm-machine\.css[^]*stylesheet_tag/);
  assert.match(css, /\.pimm-machine\s*\{[^}]*max-width:\s*1440px[^}]*padding-inline:\s*48px/s);
  assert.match(css, /\.pimm-machine__hero\s*\{[^}]*display:\s*grid[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(0,\s*1fr\)/s);
  assert.match(css, /\.pimm-machine__engineering-bento\s*\{[^}]*display:\s*grid/s);
  assert.match(css, /\.pimm-machine__engineering-media\s*\{[^}]*grid-row:\s*span\s+2/s);
  assert.doesNotMatch(css, /\.pimm-machine\s*\{[^}]*display:\s*grid/s);
  assert.doesNotMatch(css, /box-shadow\s*:/);
  assert.doesNotMatch(css, /background-clip:\s*text|backdrop-filter|repeating-linear-gradient|linear-gradient/);
  assert.doesNotMatch(css, /border-radius:\s*(?:[2-9]\d|1[5-9])px/);
  assert.doesNotMatch(css, /#(?:f[ae][0-9a-f]{4}|f[0-9a-f]e[0-9a-f]{3})\b/i);
});

test('responsive controls preserve focus touch size motion and 320px containment', () => {
  assert.match(css, /\.pimm-machine\s*\{[^}]*display:\s*block/s);
  assert.match(css, /min-height:\s*(?:44|48)px/);
  assert.match(css, /border-radius:\s*4px/);
  assert.match(css, /:focus-visible[^}]*outline:\s*3px\s+solid\s+#FFD21C[^}]*border-color:\s*#111315/s);
  assert.match(css, /opacity\s+180ms\s+cubic-bezier\(0\.22,\s*1,\s*0\.36,\s*1\)/);
  assert.doesNotMatch(css, /(?:transition|animation)[^;]*(?:18[1-9]|1[9-9]\d|[2-9]\d{2,})ms/);
  assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)[^{]*\{[^}]*transition-duration:\s*0ms[^}]*transform:\s*none/s);
  assert.match(css, /@media\s*\(max-width:\s*989px\)[^{]*\{[^}]*padding-inline:\s*32px/s);
  assert.match(css, /@media\s*\(max-width:\s*749px\)[^{]*\{[^}]*padding-inline:\s*20px/s);
  assert.match(css, /@media\s*\(max-width:\s*359px\)[^{]*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/s);
  assert.match(css, /grid-template-areas:\s*"media"\s*"copy"/);
  assert.match(css, /overflow-x:\s*clip/);
  assert.match(css, /max-width:\s*100%/);
  assert.match(css, /min-width:\s*0/);
});

test('unified machine copy has complete English and Thai pimm_machine parity', () => {
  const en = enLocale.products?.pimm_machine;
  const th = thLocale.products?.pimm_machine;
  assert.ok(en && th);
  assert.deepEqual(flattenKeys(en), flattenKeys(th));

  const requiredKeys = [
    'hero.fit_statement',
    'model_selector.legend',
    'model_selector.selected_model',
    'model_selector.models.30g',
    'model_selector.models.50g',
    'fit.heading',
    'fit.body',
    'engineering.heading',
    'engineering.body',
    'specs.capacity.label',
    'specs.capacity.unit',
    'specs.temperature.label',
    'specs.temperature.unit',
    'specs.mold_envelope.label',
    'specs.mold_envelope.unit',
    'specs.pressure.label',
    'specs.pressure.unit',
    'tooling.heading',
    'tooling.body',
    'purchase.heading',
    'purchase.body',
    'purchase.full_price',
    'purchase.deposit_price',
    'purchase.lead_time_label',
    'purchase.lead_time',
    'purchase.deposit_explanation',
    'purchase.book_visit',
    'purchase.start_deposit',
    'status.made_to_order',
    'status.out_of_stock',
    'status.unavailable',
    'ownership.heading',
    'ownership.body',
    'ownership.navigation',
    'ownership.documents',
    'ownership.support',
    'app_integrations',
    'alt.30g.hero',
    'alt.30g.overview',
    'alt.30g.engineering',
    'alt.30g.tooling',
    'alt.50g.hero',
    'alt.50g.overview',
    'alt.50g.engineering',
    'alt.50g.tooling',
  ];

  for (const key of requiredKeys) {
    assert.equal(typeof getPath(en, key), 'string', `missing English ${key}`);
    assert.equal(typeof getPath(th, key), 'string', `missing Thai ${key}`);
    assert.ok(getPath(en, key).trim(), `empty English ${key}`);
    assert.ok(getPath(th, key).trim(), `empty Thai ${key}`);
  }
  for (const key of ['hero.fit_statement', 'fit.body', 'engineering.body', 'purchase.body', 'ownership.body', 'alt.30g.hero', 'alt.50g.hero']) {
    assert.match(getPath(th, key), /[\u0E00-\u0E7F]/, `${key} must contain native Thai copy`);
  }

  const translationReferences = [...renderedContract.matchAll(/'([^']+)'\s*\|\s*t/g)].map((match) => match[1]);
  assert.ok(translationReferences.length > 0);
  assert.ok(translationReferences.every((key) => key.startsWith('products.pimm_machine.')));
  assert.doesNotMatch(renderedContract, /products\.pimm30_story|maliev_home_i18n|templates\.contact|sections\.footer|products\.product/);
});

test('every installed storefront locale preserves the unified machine key and placeholder contract', () => {
  const defaultCopy = enLocale.products.pimm_machine;
  const defaultKeys = flattenKeys(defaultCopy);

  assert.equal(storefrontLocales.length, 31);
  for (const { name, value } of storefrontLocales) {
    const copy = value.products?.pimm_machine;
    assert.ok(copy, `${name} must define products.pimm_machine`);
    assert.deepEqual(flattenKeys(copy), defaultKeys, `${name} must preserve the default leaf-key order and set`);

    for (const key of defaultKeys) {
      assert.deepEqual(
        placeholders(getPath(copy, key)),
        placeholders(getPath(defaultCopy, key)),
        `${name} must preserve interpolation placeholders for ${key}`,
      );
    }

    if (name !== 'en.default.json' && name !== 'th.json') {
      assert.deepEqual(copy, defaultCopy, `${name} must use the approved English fallback copy`);
    }
  }
});

test('one asymmetric engineering bento exposes stable model media and semantic specifications', () => {
  assert.equal(renderedContract.match(/data-pimm-engineering-bento/g)?.length, 1);
  assert.match(bento, /class="pimm-machine__engineering-bento"/);
  assert.match(bento, /<figure[^>]*class="[^"]*pimm-machine__engineering-media/);
  assert.match(bento, /<dl[^>]*data-pimm-specifications/);

  for (const slot of ['hero', 'overview', 'engineering', 'tooling']) {
    assert.match(renderedContract, new RegExp(`data-pimm-media-slot="${slot}"`));
  }
  for (const field of ['shot_capacity_g', 'max_melt_temperature_c', 'mold_envelope', 'max_air_pressure_mpa']) {
    assert.match(bento, new RegExp(`data-pimm-spec="${field}"`));
  }

  assert.match(section, /for block in section\.blocks/);
  assert.match(renderedContract, /data-pimm-media-model="\{\{ block\.settings\.model_code \}\}"/);
  assert.match(renderedContract, /aria-hidden="\{%-? if media_is_selected/);
  assert.match(renderedContract, /unless media_is_selected[^]*hidden/);
  assert.doesNotMatch(renderedContract, /<img(?![^>]*width="1600"[^>]*height="1600")[^>]*data-pimm-media-slot/s);
});

test('only the selected hero is eager while below-fold model media stays lazy and async', () => {
  assert.match(section, /if media_is_selected[\s\S]*loading="eager"[\s\S]*fetchpriority="high"/);
  for (const slot of ['overview', 'engineering', 'tooling']) {
    assert.match(renderedContract, new RegExp(`loading="lazy"[\\s\\S]*decoding="async"[\\s\\S]*data-pimm-media-slot="${slot}"`));
  }
  assert.doesNotMatch(renderedContract, /rel="preload"|new Image\s*\(/);
});

test('engineering facts keep numeric values separate from visible accessible units', () => {
  assert.match(bento, /data-pimm-spec="shot_capacity_g"[^>]*aria-label=/);
  assert.match(bento, /data-pimm-spec="max_melt_temperature_c"[^>]*aria-label=/);
  assert.match(bento, /data-pimm-spec="mold_envelope"[^>]*aria-label=/);
  assert.match(bento, /data-pimm-spec="max_air_pressure_mpa"[^>]*aria-label=/);
  assert.match(bento, /data-pimm-spec-unit="shot_capacity_g"[^>]*>[^<]*products\.pimm_machine\.specs\.capacity\.unit/);
  assert.match(bento, /data-pimm-spec-unit="max_melt_temperature_c"[^>]*>[^<]*products\.pimm_machine\.specs\.temperature\.unit/);
  assert.match(bento, /data-pimm-spec-unit="mold_envelope"[^>]*>[^<]*products\.pimm_machine\.specs\.mold_envelope\.unit/);
  assert.match(bento, /data-pimm-spec-unit="max_air_pressure_mpa"[^>]*>[^<]*products\.pimm_machine\.specs\.pressure\.unit/);
  assert.doesNotMatch(variantPayloadSource, /shot_capacity_g[^\n]*["']g["']/);
  for (const field of ['shot_capacity_g', 'max_melt_temperature_c', 'mold_envelope', 'max_air_pressure_mpa']) {
    assert.match(bento, new RegExp(`data-pimm-spec-unit="${field}"`));
  }
  assert.equal(bento.match(/data-pimm-spec-unit=/g)?.length, 4);
  assert.equal(bento.match(/unless model_contract_valid[^%]*%}hidden/g)?.length, 4);
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
  assert.match(purchase, /products\.pimm_machine\.status\.unavailable/);
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

test('merchant model alt settings resolve initial and switched media with locale fallbacks', () => {
  const runtimeAltSources = `${sectionRuntime}\n${bento}`;
  const slots = ['hero', 'overview', 'engineering', 'tooling'];

  for (const slot of slots) {
    for (const locale of ['en', 'th']) {
      const setting = `${slot}_alt_${locale}`;
      assert.ok(
        (runtimeAltSources.match(new RegExp(`settings\\.${setting}\\b`, 'g')) ?? []).length >= 2,
        `${setting} must feed both initial markup and the variant switching payload`,
      );
    }

    const initialSource = slot === 'engineering' ? bento : sectionRuntime;
    const initialVariable = `block_${slot}_alt`;
    assert.match(initialSource, new RegExp(`assign ${initialVariable} = 'products\\.pimm_machine\\.alt\\.30g\\.${slot}' \\| t`));
    assert.match(initialSource, new RegExp(`assign ${initialVariable} = 'products\\.pimm_machine\\.alt\\.50g\\.${slot}' \\| t`));
    assert.match(
      initialSource,
      new RegExp(
        `if use_thai_alt[\\s\\S]*?if block\\.settings\\.${slot}_alt_th != blank[\\s\\S]*?assign ${initialVariable} = block\\.settings\\.${slot}_alt_th[\\s\\S]*?elsif block\\.settings\\.${slot}_alt_en != blank[\\s\\S]*?assign ${initialVariable} = block\\.settings\\.${slot}_alt_en`,
      ),
    );

    const payloadVariable = `variant_${slot}_alt`;
    assert.match(variantPayloadSource, new RegExp(`assign ${payloadVariable} = 'products\\.pimm_machine\\.alt\\.30g\\.${slot}' \\| t`));
    assert.match(variantPayloadSource, new RegExp(`assign ${payloadVariable} = 'products\\.pimm_machine\\.alt\\.50g\\.${slot}' \\| t`));
    assert.match(
      variantPayloadSource,
      new RegExp(
        `if use_thai_alt[\\s\\S]*?if variant_model_block\\.settings\\.${slot}_alt_th != blank[\\s\\S]*?assign ${payloadVariable} = variant_model_block\\.settings\\.${slot}_alt_th[\\s\\S]*?elsif variant_model_block\\.settings\\.${slot}_alt_en != blank[\\s\\S]*?assign ${payloadVariable} = variant_model_block\\.settings\\.${slot}_alt_en`,
      ),
    );
  }

  assert.match(sectionRuntime, /request\.locale\.iso_code == 'th'/);
  assert.match(sectionRuntime, /request\.locale\.iso_code contains 'th-'/);
  assert.match(bento, /request\.locale\.iso_code == 'th'/);
  assert.match(bento, /request\.locale\.iso_code contains 'th-'/);
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
  assert.doesNotMatch(section, /variant\.metafields\.custom\.pimm_specifications\.value \| json/);
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
    assert.match(
      variantPayloadSource,
      new RegExp(`"${slot}"\\s*:\\s*\\{[\\s\\S]*?"src"\\s*:[\\s\\S]*?"alt"\\s*:`, 'm'),
    );
  }
  assert.match(variantPayloadSource, /variant_model_block_count == 1/);
  assert.match(variantPayloadSource, /variant_specifications\.schema_version == 1/);
  assert.match(variantPayloadSource, /variant_specifications\.model == variant_model/);
  const specificationProjection = variantPayloadSource.match(/"specifications"\s*:\s*\{([\s\S]*?)\n\s*\},\n\s*"media"/)?.[1] ?? '';
  for (const field of [
    'schema_version',
    'model',
    'shot_capacity_g',
    'max_melt_temperature_c',
    'mold_envelope_mm',
    'width',
    'height',
    'depth',
    'max_air_pressure_mpa',
  ]) {
    assert.match(specificationProjection, new RegExp(`"${field}"\\s*:`));
  }
  const merchantControlledFixture = {
    unexpected_key: '</script><script>window.payloadEscaped = false</script>',
  };
  const emittedSpecificationKeys = [...specificationProjection.matchAll(/"([a-z_]+)"\s*:/g)].map((match) => match[1]);
  assert.deepEqual([...new Set(emittedSpecificationKeys)], [
    'schema_version',
    'model',
    'shot_capacity_g',
    'max_melt_temperature_c',
    'mold_envelope_mm',
    'width',
    'height',
    'depth',
    'max_air_pressure_mpa',
  ]);
  assert.equal(emittedSpecificationKeys.includes('unexpected_key'), false);
  assert.doesNotMatch(specificationProjection, new RegExp(merchantControlledFixture.unexpected_key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.doesNotMatch(specificationProjection, /variant_specifications\s*\|\s*json/);
  assert.match(variantPayloadSource, /variant_hero_alt \| strip_html \| json/);
  assert.match(variantPayloadSource, /variant_overview_alt \| strip_html \| json/);
  assert.match(variantPayloadSource, /variant_engineering_alt \| strip_html \| json/);
  assert.match(variantPayloadSource, /variant_tooling_alt \| strip_html \| json/);
  assert.doesNotMatch(js, /\b[a-zA-Z_$][\w$]*\.(?:src|alt)\s*=(?!=)/);
  assert.match(purchase, /role="status"[^>]*aria-live="polite"[^>]*aria-atomic="true"/);
  assert.match(purchase, /render 'loading-spinner'/);
  assert.doesNotMatch(js, /innerHTML|insertAdjacentHTML|document\.write/);
});

test('market-aware full prices double contextual variant cents while retaining metafield validation', () => {
  assert.match(section, /assign selected_full_price_cents = selected_variant\.price \| times: 2/);
  assert.match(section, /assign variant_full_price_cents = variant\.price \| times: 2/);
  assert.match(section, /metafields\.custom\.full_machine_price\.value/);
  assert.match(section, /if full_price != blank and lead_time > 0/);
  assert.match(section, /if variant_full_price != blank and variant_lead_time_days > 0/);
  assert.match(section, /data-pimm-taxes-included="\{\{ cart\.taxes_included \}\}"/);
  assert.match(section, /data-pimm-country="\{\{ localization\.country\.iso_code/);
  assert.match(section, /data-pimm-currency="\{\{ cart\.currency\.iso_code/);
  assert.match(purchase, /full_price_cents \| money_with_currency/);
  assert.doesNotMatch(renderedContract, /full_price\.amount|variant_full_price\.amount/);
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
  assert.deepEqual(harness.mediaGroups.map((group) => group.hidden), [true, true, true, true, false, false, false, false]);
  assert.deepEqual(harness.mediaGroups.map((group) => group.ariaHidden), ['true', 'true', 'true', 'true', 'false', 'false', 'false', 'false']);
  assert.deepEqual(harness.specificationNodes.map((node) => node.textContent), ['50', '350', '240 × 240 × 100', '0.7']);
  assert.deepEqual(harness.specificationNodes.map((node) => node.ariaLabel), ['50 g', '350 °C', '240 × 240 × 100 mm', '0.7 MPa']);
  assert.deepEqual(harness.mediaGroups.map((group) => group.image.decodeCount), [0, 0, 0, 0, 1, 0, 0, 0]);
  assert.deepEqual(
    harness.mediaGroups.map((group) => [group.image.src, group.image.alt]),
    variants.flatMap((variant) => Object.values(variant.media).map((media) => [media.src, media.alt])),
  );
  assert.equal(harness.factoryVisit.href, '/pages/contact');
});

test('direct model intent decodes only the selected hero and only once per model', () => {
  const variants = [variantFixture({ model: '30G', id: 101 }), variantFixture({ model: '50G', id: 202 })];
  const harness = createControllerHarness(variants);

  harness.controller.selectVariant(202);
  harness.controller.selectVariant(202);

  assert.deepEqual(harness.mediaGroups.map((group) => group.image.decodeCount), [0, 0, 0, 0, 1, 0, 0, 0]);
});

test('invalid specification state hides every unit and a later valid selection restores them', () => {
  const invalid50G = variantFixture({ model: '50G', id: 202, contractValid: false });
  const harness = createControllerHarness([variantFixture({ model: '30G', id: 101 }), invalid50G]);

  harness.controller.selectVariant(202);
  assert.ok(harness.specificationUnits.every((unit) => unit.hidden));
  assert.ok(harness.specificationUnits.every((unit) => unit.ariaHidden === 'true'));
  assert.ok(harness.specificationNodes.every((node) => node.ariaLabel === 'Unavailable'));

  harness.controller.selectVariant(101);
  assert.ok(harness.specificationUnits.every((unit) => !unit.hidden));
  assert.ok(harness.specificationUnits.every((unit) => unit.ariaHidden === 'true'));
  assert.deepEqual(harness.specificationNodes.map((node) => node.ariaLabel), [
    '30 g',
    '300 °C',
    '240 × 240 × 150 mm',
    '0.7 MPa',
  ]);
});

test('malformed, unavailable and unknown selections disable deposit without model fallback', () => {
  const malformed = variantFixture({ model: '50G', id: 202, contractValid: false });
  const harness = createControllerHarness([variantFixture({ model: '30G', id: 101 }), malformed]);

  harness.controller.selectVariant(202);
  assert.equal(harness.selected.textContent, '50G');
  assert.equal(harness.status.textContent, 'Unavailable');
  assert.equal(harness.deposit.disabled, true);
  assert.deepEqual(harness.radios.map((radio) => radio.checked), [false, true]);
  assert.ok(harness.mediaGroups.every((group) => group.hidden && group.ariaHidden === 'true'));
  assert.ok(harness.specificationNodes.every((node) => node.textContent === 'Unavailable'));
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
  assert.deepEqual(unavailable.mediaGroups.map((group) => group.hidden), [true, true, true, true, false, false, false, false]);
});

test('invalid payload structure hides all model media at connection time', () => {
  const reversed = createControllerHarness([
    variantFixture({ model: '50G', id: 202 }),
    variantFixture({ model: '30G', id: 101 }),
  ]);

  assert.equal(reversed.deposit.disabled, true);
  assert.equal(reversed.status.textContent, 'Unavailable');
  assert.ok(reversed.mediaGroups.every((group) => group.hidden));
  assert.ok(reversed.mediaGroups.every((group) => group.ariaHidden === 'true'));
});
