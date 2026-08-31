import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import test from 'node:test';

const readThemeFile = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8');
const stripShopifyComment = (source) => source.replace(/^\s*\/\*[\s\S]*?\*\/\s*/, '');
const getPath = (value, path) => path.split('.').reduce((current, key) => current?.[key], value);

const [section, hero, selector, qualification, story30G, story50G, ownership, purchase, templateSource, js, css] = await Promise.all([
  readThemeFile('sections/maliev-pimm-machine-product.liquid'),
  readThemeFile('snippets/pimm-hero-console.liquid'),
  readThemeFile('snippets/pimm-model-selector.liquid'),
  readThemeFile('snippets/pimm-qualification-strip.liquid'),
  readThemeFile('snippets/pimm-30g-product-story.liquid'),
  readThemeFile('snippets/pimm-50g-product-story.liquid'),
  readThemeFile('snippets/pimm-ownership.liquid'),
  readThemeFile('snippets/pimm-purchase-qualification.liquid'),
  readThemeFile('templates/product.pimm-configurator.json'),
  readThemeFile('assets/maliev-pimm-machine.js'),
  readThemeFile('assets/maliev-pimm-machine.css'),
]);

const template = JSON.parse(stripShopifyComment(templateSource));
const schema = JSON.parse(section.match(/{% schema %}([\s\S]*?){% endschema %}/)?.[1]);
const renderedContract = [section, hero, selector, qualification, story30G, story50G, ownership, purchase].join('\n');

test('unified template declares governed model story sets and no retired media slots', () => {
  assert.equal(template.sections.main.type, 'maliev-pimm-machine-product');
  const blocks = template.sections.main.blocks;
  assert.deepEqual(template.sections.main.block_order, ['model_30g', 'model_50g']);
  assert.equal(blocks.model_30g.settings.story_asset_set, 'pimm30-production-v13');
  assert.equal(blocks.model_50g.settings.story_asset_set, 'pimm50-light-studio-v1');
  for (const block of Object.values(blocks)) {
    for (const retired of ['hero_asset', 'overview_asset', 'engineering_asset', 'tooling_asset']) {
      assert.equal(Object.hasOwn(block.settings, retired), false);
    }
  }
});

test('one controller owns one decision header two stories and singular conversion regions', () => {
  assert.match(section, /<pimm-machine-product[^>]*data-pimm-machine-product/);
  assert.equal(renderedContract.match(/<h1\b/g)?.length, 1);
  assert.equal(section.match(/render 'pimm-hero-console'/g)?.length, 1);
  assert.equal(section.match(/render 'pimm-30g-product-story'/g)?.length, 1);
  assert.equal(section.match(/render 'pimm-50g-product-story'/g)?.length, 1);
  assert.equal(section.match(/render 'pimm-ownership'/g)?.length, 1);
  assert.equal(section.match(/render 'pimm-purchase-qualification'/g)?.length, 1);
  assert.doesNotMatch(section, /pimm-engineering-bento|pimm-editorial-chapters/);
  assert.equal(section.match(/data-pimm-story-model="(?:30G|50G)"/g)?.length, 2);
  assert.match(section, /hidden inert aria-hidden="true"/);
});

test('model stories use only their authoritative production families', () => {
  for (const name of ['hero', 'capacity', 'melt-zone', 'heating', 'mold-space', 'purchase']) {
    assert.match([hero, story50G].join('\n'), new RegExp(`pimm50-light-studio-${name}\\.webp`));
  }
  for (const name of [
    'pimm30-v13-hero-desktop-contained',
    'pimm30-v13-hero-mobile-contained',
    'pimm30-capacity-three-cube-desktop',
    'pimm30-temperature-controller-desktop',
    'pimm30-v11-cylinder-desktop',
    'pimm30-v16-operation-desktop',
    'pimm30-v10-regulator-desktop',
    'pimm30-v15-fixture-desktop',
    'pimm30-v10-capacity-desktop',
    'pimm30-configuration-turntable-desktop',
  ]) assert.match([hero, story30G].join('\n'), new RegExp(`${name}\\.webp`));
  assert.doesNotMatch(story30G, /pimm50-/);
  assert.doesNotMatch(story50G, /pimm30-/);
  assert.doesNotMatch(renderedContract, /pimm-(?:machine|editorial)-[^'"\s)]+\.webp/);
});

test('full-machine views expose a measurable stage baseline and complete intrinsic media', () => {
  assert.equal([hero, story30G, story50G].join('\n').match(/data-pimm-full-machine/g)?.length, 4);
  assert.equal([hero, story30G, story50G].join('\n').match(/data-pimm-stage-baseline/g)?.length, 4);
  assert.match(css, /\[data-pimm-stage-baseline\][^{]*\{[^}]*align-items:\s*end/s);
  assert.match(css, /\[data-pimm-full-machine\][^{]*img[^}]*object-fit:\s*contain/s);
  assert.doesNotMatch(css, /object-fit:\s*cover\s*!important/);
});

test('normal-scroll responsive CSS contains no legacy slide or editorial cascade', () => {
  assert.match(css, /\.pimm-story__chapter[^}]*display:\s*grid/s);
  assert.match(css, /@media \(max-width:\s*749px\)/);
  assert.match(css, /@media \(prefers-reduced-motion:\s*reduce\)/);
  assert.doesNotMatch(css, /height:\s*100s?vh|scroll-snap|position:\s*sticky/);
  assert.doesNotMatch(css, /\.pimm-machine__editorial|\.pimm-machine__bento/);
  assert.doesNotMatch(css, /object-fit:\s*cover/);
});

test('model records bind exact story sets and fail closed on identity drift', () => {
  assert.match(section, /assign expected_variant_story_asset_set = 'pimm30-production-v13'/);
  assert.match(section, /assign expected_variant_story_asset_set = 'pimm50-light-studio-v1'/);
  assert.match(section, /if variant_story_asset_set == expected_variant_story_asset_set/);
  assert.match(section, /"storyAssetSet":\s*\{\{ variant_story_asset_set \| json \}\}/);
  assert.match(js, /variant\.storyAssetSet === expectedStoryAssetSet/);
  assert.match(js, /variant\?\.model === '30G'[\s\S]*?'pimm30-production-v13'/);
  assert.match(js, /variant\?\.model === '50G'[\s\S]*?'pimm50-light-studio-v1'/);
  assert.match(js, /showOnlyStory\(contractValid \? variant\.model : ''\)/);
});

test('variant payload preserves verified commerce and specification boundaries', () => {
  assert.match(section, /assign selected_full_price_cents = selected_variant\.price \| times: 2/);
  assert.match(section, /assign variant_full_price_cents = variant\.price \| times: 2/);
  assert.match(section, /metafields\.custom\.full_machine_price\.value/);
  assert.match(section, /metafields\.custom\.lead_time_days\.value/);
  assert.match(section, /variant_specifications\.schema_version == 1/);
  assert.match(section, /data-pimm-taxes-included="\{\{ cart\.taxes_included \}\}"/);
  assert.match(section, /data-pimm-country="\{\{ localization\.country\.iso_code/);
  assert.match(section, /data-pimm-currency="\{\{ cart\.currency\.iso_code/);
  assert.doesNotMatch(renderedContract, /deposit|มัดจำ|50%/i);
});

test('selector remains native accessible and model state uses stable DOM nodes', () => {
  assert.match(selector, /<fieldset[^>]*data-pimm-model-selector/);
  assert.match(selector, /type="radio"/);
  assert.match(selector, /data-pimm-model-radio/);
  assert.match(selector, /<output[^>]*data-pimm-selected-model/);
  assert.match(js, /querySelectorAll\('\[data-pimm-media-model\]'\)/);
  assert.match(js, /querySelectorAll\('\[data-pimm-story-model\]'\)/);
  assert.match(js, /group\.inert = hidden/);
  assert.match(js, /story\.inert = hidden/);
  assert.doesNotMatch(js, /innerHTML|insertAdjacentHTML|document\.write/);
});

test('selected hero is eager while inactive and below-fold media remain deferred', () => {
  assert.match(hero, /loading="\{% if selected_model_code == '30G' %\}eager\{% else %\}lazy\{% endif %\}"/);
  assert.match(hero, /loading="\{% if selected_model_code == '50G' %\}eager\{% else %\}lazy\{% endif %\}"/);
  assert.match(hero, /fetchpriority="high"/);
  assert.equal([story30G, story50G].join('\n').match(/loading="lazy"/g)?.length, 13);
  assert.doesNotMatch([story30G, story50G].join('\n'), /loading="eager"|fetchpriority="high"/);
});

test('all referenced copy uses the complete installed storefront locale contract', async () => {
  const translationKeys = [...new Set([...renderedContract.matchAll(/'([^']+)'\s*\|\s*t/g)].map((match) => match[1]))];
  const localeNames = (await readdir(new URL('../../locales/', import.meta.url)))
    .filter((name) => name.endsWith('.json') && !name.endsWith('.schema.json'));
  for (const name of localeNames) {
    const locale = JSON.parse(stripShopifyComment(await readThemeFile(`locales/${name}`)));
    for (const key of translationKeys) assert.notEqual(getPath(locale, key), undefined, `${name} is missing ${key}`);
  }
});

test('section schema keeps two governed model blocks and approved external links', () => {
  const model = schema.blocks.find((block) => block.type === 'model');
  assert.equal(model.limit, 2);
  assert.deepEqual(model.settings.map((setting) => setting.id), ['model_code', 'story_asset_set']);
  assert.deepEqual(schema.settings.map((setting) => setting.id), ['factory_visit_url', 'document_url', 'support_url']);
  assert.ok(schema.blocks.some((block) => block.type === '@app'));
});
