import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8');
const parseTemplate = (source) => JSON.parse(source.replace(/^\/\*[\s\S]*?\*\//, '').trim());

const section = read('sections/maliev-pimm-30g-story.liquid');
const chapter = read('snippets/maliev-pimm-30g-chapter.liquid');
const styles = read('assets/maliev-pimm-30g.css');
const blenderBuilder = read('scripts/blender/create_pimm50_red_stage.py');
const template = parseTemplate(read('templates/product.injection-molding-machine.json'));
const en = parseTemplate(read('locales/en.default.json'));
const th = parseTemplate(read('locales/th.json'));

const nextModelLocale = (locale, localeName) => {
  assert.ok(locale.products, `${localeName}: products locale namespace must exist`);
  assert.ok(locale.products.pimm30_story, `${localeName}: products.pimm30_story must exist`);
  assert.ok(
    locale.products.pimm30_story.next_model,
    `${localeName}: products.pimm30_story.next_model must exist`,
  );
  return locale.products.pimm30_story.next_model;
};

test('50G uses made-to-order commerce wording', () => {
  assert.equal(nextModelLocale(en, 'en').made_to_order, 'Made to order');
  assert.equal(nextModelLocale(th, 'th').made_to_order, 'ผลิตตามคำสั่งซื้อ');

  const nextModelBranch = section.match(/\{%- when 'next_model' -%\}([\s\S]*?)\{%- else -%\}/)?.[1];
  assert.ok(nextModelBranch, 'next_model Liquid branch must exist');
  const availableBranch = nextModelBranch.match(
    /\{%[-\s]*if\s+next_variant\.available\s*[-]?%\}([\s\S]*?)\{%[-\s]*else\s*[-]?%\}/,
  )?.[1];
  assert.ok(availableBranch, 'next_variant.available Liquid branch must exist');
  assert.match(availableBranch, /data-pimm50-made-to-order/);
  assert.match(
    availableBranch,
    /\{\{\s*'products\.pimm30_story\.next_model\.made_to_order'\s*\|\s*t\s*\}\}/,
  );
  assert.doesNotMatch(availableBranch, /inventory_in_stock/);
});

test('50G facts remain verified and localized', () => {
  const expectedFacts = [
    {
      locale: en,
      name: 'en',
      facts: {
        capacity: '50g shot capacity',
        melt_zone: 'Steel melt zone',
        heaters: '2 × 350W hot-runner heater bands',
      },
    },
    {
      locale: th,
      name: 'th',
      facts: {
        capacity: 'ความจุการฉีด 50 กรัม',
        melt_zone: 'ชุดหลอมผลิตจากเหล็ก',
        heaters: 'ฮีตเตอร์ฮอตรันเนอร์ 350 วัตต์ 2 ชุด',
      },
    },
  ];

  for (const { locale, name, facts: expected } of expectedFacts) {
    const nextModel = nextModelLocale(locale, name);
    const facts = nextModel.facts;
    assert.ok(facts, `${name}: products.pimm30_story.next_model.facts must exist`);
    assert.equal(Object.keys(facts).length, 3);
    assert.deepEqual(facts, expected);
    assert.doesNotMatch(JSON.stringify(facts), /350\s*°?C/i);
  }
});

test('only the next-model chapter opts into looping video', () => {
  assert.match(
    chapter,
    /assign is_looping = false[\s\S]{0,140}if block\.settings\.role\s*==\s*'next_model'[\s\S]{0,140}assign is_looping = true/,
  );
  assert.deepEqual(
    [...chapter.matchAll(/assign is_looping = (true|false)/g)].map(([, value]) => value),
    ['false', 'true'],
    'is_looping must have only its false default and next_model true assignment',
  );

  const videos = [...chapter.matchAll(/<video\b[\s\S]*?>/g)].map(([video]) => video);
  assert.equal(videos.length, 2, 'desktop and mobile responsive video elements must both exist');
  for (const video of videos) {
    const conditionalLoop = /\{%[-\s]*if\s+is_looping\s*[-]?%\}\s*loop\s*\{%[-\s]*endif\s*[-]?%\}/;
    assert.match(video, conditionalLoop);
    assert.doesNotMatch(video.replace(conditionalLoop, ''), /\bloop\b/);
  }
});

test('product story wires dedicated red-stage assets', () => {
  const story = template.sections.pimm30_story;
  const nextId = story.block_order.find((id) => story.blocks[id].settings.role === 'next_model');
  const settings = story.blocks[nextId].settings;
  assert.equal(settings.desktop_video_asset, 'pimm50-red-stage-desktop.webm');
  assert.equal(settings.mobile_video_asset, 'pimm50-red-stage-mobile.webm');
  assert.equal(settings.desktop_poster_asset, 'pimm50-red-stage-desktop.webp');
  assert.equal(settings.mobile_poster_asset, 'pimm50-red-stage-mobile.webp');
});

test('50G cinematic lockup uses condensed title typography and a brush backdrop', () => {
  assert.match(section, /class="pimm50-lockup__title"/);
  assert.match(styles, /--pimm50-font-impact:\s*'Antonio'/);
  assert.match(styles, /--pimm50-font-marker:\s*'Permanent Marker'/);
  assert.match(
    styles,
    /data-pimm30-layer='pimm30-next_model'\]::before[\s\S]*?content:\s*'50G'[\s\S]*?var\(--pimm50-font-marker\)/,
  );
});

test('50G Blender builder preserves alpha production and hides unsupported controller digits', () => {
  assert.match(blenderBuilder, /PIMM-50g-red-stage-loop-v2\.blend/);
  assert.match(blenderBuilder, /film_transparent\s*=\s*True/);
  assert.match(blenderBuilder, /neutralize_unverified_controller_readout/);
  assert.match(blenderBuilder, /create_smoke_cards/);
  assert.doesNotMatch(blenderBuilder, /350\s*°?C/i);
});
