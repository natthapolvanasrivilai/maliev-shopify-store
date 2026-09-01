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
  assert.equal(blocks.model_30g.settings.story_asset_set, 'pimm-master-20260831-r04-30g');
  assert.equal(blocks.model_50g.settings.story_asset_set, 'pimm-master-20260831-r04-50g');
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

test('hero and stories use product-first hierarchy without decorative eyebrows', () => {
  assert.match(hero, /assign display_product_title = product\.title \| remove: ' \(Development\)' \| strip/);
  assert.match(hero, /<h1 class="pimm-machine__title">\{\{ display_product_title \| escape \}\}<\/h1>/);
  assert.doesNotMatch(renderedContract, /pimm-machine__eyebrow/);
  assert.doesNotMatch(css, /\.pimm-machine__eyebrow/);
});

test('hero introduction has a deliberate display hierarchy and reading measure', () => {
  assert.match(hero, /<div class="pimm-machine__introduction">[\s\S]*?<h1 class="pimm-machine__title">[\s\S]*?pimm-machine__promise[\s\S]*?pimm-machine__fit[\s\S]*?<\/div>/);
  assert.match(css, /\.pimm-machine \.pimm-machine__title[^}]*font-size:\s*clamp\(4rem, 4\.8vw, 6rem\)[^}]*max-width:\s*15ch/s);
  assert.match(css, /\.pimm-machine__introduction[^}]*display:\s*grid[^}]*gap:\s*1\.6rem/s);
  assert.match(css, /\.pimm-machine \.pimm-machine__fit[^}]*font-size:\s*1\.6rem[^}]*line-height:\s*1\.6[^}]*max-width:\s*45ch/s);
  assert.match(css, /\.pimm-machine \.pimm-machine__model-selector[^}]*margin-top:\s*clamp\(3\.2rem, 4vw, 4\.8rem\)/s);
});

test('engineering summary uses a responsive technical ledger instead of equal cards', () => {
  assert.match(hero, /<aside class="pimm-machine__specifications"[\s\S]*?<h2[^>]*>[\s\S]*?<dl>[\s\S]*?<dt>[\s\S]*?<dd>/);
  assert.match(css, /\.pimm-machine__specifications dd\s*\{[^}]*font-variant-numeric:\s*tabular-nums/s);
  assert.match(css, /@media \(max-width:\s*1299px\)[\s\S]*?\.pimm-machine__specifications\s*\{[^}]*border-block:[^}]*grid-template-columns:\s*minmax\(18rem, \.6fr\) minmax\(0, 1\.4fr\)[^}]*padding-block:/s);
  assert.match(css, /@media \(max-width:\s*1299px\)[\s\S]*?\.pimm-machine__specifications dl\s*\{[^}]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/s);
  assert.match(css, /@media \(max-width:\s*749px\)[\s\S]*?\.pimm-machine__specifications\s*\{[^}]*grid-template-columns:\s*1fr/s);
  assert.match(css, /@media \(max-width:\s*479px\)[\s\S]*?\.pimm-machine__specifications dl\s*\{[^}]*grid-template-columns:\s*1fr/s);
});

test('capacity selector and every engineering chapter expose deliberate type roles', () => {
  assert.equal(selector.match(/class="pimm-machine__model-name"/g)?.length, 1);
  assert.equal(selector.match(/class="pimm-machine__model-price"/g)?.length, 1);
  assert.match(css, /\.pimm-machine__model-name[^}]*font-size:\s*1\.6rem[^}]*font-weight:\s*600/s);
  assert.match(css, /\.pimm-machine__model-price[^}]*font-family:\s*var\(--maliev-font-mono/s);
  assert.equal([story30G, story50G].join('\n').match(/class="pimm-story__index"/g)?.length, 8);
  assert.match(css, /\.pimm-story__copy[^}]*grid-template-columns:\s*4\.8rem minmax\(0, 1fr\)/s);
  assert.match(css, /\.pimm-story__copy h3[^}]*font-size:\s*clamp\(2\.8rem, 4vw, 5\.2rem\)/s);
  assert.match(css, /\.pimm-story__copy p:last-child[^}]*max-width:\s*60ch/s);
});

test('model stories use only their authoritative production families', () => {
  for (const model of ['30g', '50g']) {
    for (const role of ['hero', 'three-quarter', 'controls', 'tooling']) {
      assert.match([hero, model === '30g' ? story30G : story50G].join('\n'), new RegExp(`pimm-master-20260831-r04-${model}-${role}\\.webp`));
    }
  }
  assert.doesNotMatch(story30G, /pimm-master-20260831-r04-50g/);
  assert.doesNotMatch(story50G, /pimm-master-20260831-r04-30g/);
  assert.doesNotMatch(renderedContract, /(?:(?:pimm30-|pimm50-|pimm-(?:machine|editorial)-|maliev-pimm-)[^'"\s)]+\.(?:png|webp|webm|mp4))/i);
});

test('full-machine views use physical ground contact without CSS compensation', () => {
  assert.equal([hero, story30G, story50G].join('\n').match(/data-pimm-full-machine/g)?.length, 4);
  assert.equal([hero, story30G, story50G].join('\n').match(/data-pimm-physical-ground-contact/g)?.length, 4);
  assert.doesNotMatch([hero, story30G, story50G, css].join('\n'), /data-pimm-stage-baseline|pimm-ground-line-offset|translate[XY]?\(/);
  assert.match(css, /\[data-pimm-full-machine\][^{]*img[^}]*object-fit:\s*contain/s);
  assert.match(css, /\[data-pimm-full-machine\][^{]*img[^}]*transform:\s*none/s);
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
  assert.match(section, /assign expected_variant_story_asset_set = 'pimm-master-20260831-r04-30g'/);
  assert.match(section, /assign expected_variant_story_asset_set = 'pimm-master-20260831-r04-50g'/);
  assert.match(section, /if variant_story_binding_valid and variant_specifications != blank/);
  assert.match(section, /"storyAssetSet":\s*\{\{ variant_story_asset_set \| json \}\}/);
  assert.match(js, /variant\.storyAssetSet === expectedStoryAssetSet/);
  assert.match(js, /variant\?\.model === '30G'[\s\S]*?'pimm-master-20260831-r04-30g'/);
  assert.match(js, /variant\?\.model === '50G'[\s\S]*?'pimm-master-20260831-r04-50g'/);
  assert.match(js, /showOnlyStory\(contractValid \? variant\.model : ''\)/);
});

test('existing theme blocks migrate a blank story setting to the governed model set', () => {
  assert.match(section, /assign selected_story_binding_valid = false/);
  assert.match(section, /if selected_model_block\.settings\.story_asset_set == blank or selected_model_block\.settings\.story_asset_set == expected_story_asset_set/);
  assert.match(section, /assign variant_story_asset_set = expected_variant_story_asset_set/);
  assert.match(section, /if variant_model_block\.settings\.story_asset_set == blank or variant_model_block\.settings\.story_asset_set == expected_variant_story_asset_set/);
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
  assert.equal([story30G, story50G].join('\n').match(/loading="lazy"/g)?.length, 8);
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
