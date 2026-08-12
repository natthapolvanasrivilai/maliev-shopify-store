import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const section = await readFile(new URL('../../sections/maliev-pimm-50g-launch.liquid', import.meta.url), 'utf8');
const css = await readFile(new URL('../../assets/maliev-pimm-50g-story.css', import.meta.url), 'utf8');
const js = await readFile(new URL('../../assets/maliev-pimm-50g-story.js', import.meta.url), 'utf8');
const template = JSON.parse(await readFile(new URL('../../templates/product.pimm-50g.json', import.meta.url), 'utf8').then((value) => value.replace(/^\/\*[\s\S]*?\*\/\s*/, '')));

const sectionById = (id) => section.match(new RegExp(`<section[^>]+id="${id}"[\\s\\S]*?<\\/section>`))?.[0] ?? '';

test('50G is a normally scrolling product narrative', () => {
  assert.match(section, /data-pimm50-page/);
  for (const id of ['hero', 'overview', 'capacity', 'melt-zone', 'heating', 'mold-space', 'comparison', 'purchase']) {
    assert.match(section, new RegExp(`id="pimm50-${id}"`));
  }
  assert.doesNotMatch(css, /scroll-snap-(?:type|align|stop)/);
  assert.doesNotMatch(css, /height:\s*calc\(100s?vh/);
  assert.doesNotMatch(js, /wheel|scrollIntoView|preventDefault/);
});

test('product and commerce remain visible without JavaScript', () => {
  assert.equal(section.match(/<h1\b/g)?.length, 1);
  assert.match(section, /<h1[^>]*>\s*PIMM 50G/);
  assert.match(section, /\{%[-]?\s*form 'product'/);
  assert.match(section, /name="id"/);
  assert.match(section, /name="add"/);
  assert.match(section, /Book a factory visit/);
  assert.doesNotMatch(css, /opacity:\s*0[^}]*data-pimm50-page/);
  assert.match(css, /\.pimm50-page__text-link\s*\{[^}]*align-items:\s*center[^}]*display:\s*inline-flex[^}]*min-height:\s*4\.8rem[^}]*padding:\s*0\s+2rem/s);
});

test('approved transparent media replaces every superseded story asset', () => {
  for (const name of ['hero', 'capacity', 'melt-zone', 'heating', 'mold-space', 'purchase']) {
    assert.match(section, new RegExp(`<picture[^>]*>[\\s\\S]*?pimm50-light-studio-${name}\\.webp[\\s\\S]*?<\\/picture>`));
  }
  assert.doesNotMatch(section, /pimm50-(?:red-stage|keynote|story-)/);
  assert.doesNotMatch(section, /<video\b/);
  assert.doesNotMatch(section, /data-pimm50-(?:rail|chapter)/);
  assert.doesNotMatch(css, /mask(?:-image)?\s*:|filter\s*:\s*drop-shadow|linear-gradient\s*\(/);
});

test('hero and overview expose the complete decision proof in semantic HTML', () => {
  const hero = sectionById('pimm50-hero');
  const overview = sectionById('pimm50-overview');

  assert.equal(hero.match(/data-pimm50-hero-fact/g)?.length, 4);
  assert.match(hero, /href="\{\{ visit_link \}\}"[^>]*>[^<]*(?:Book a factory visit|นัดชมเครื่อง)/);
  assert.match(hero, /href="#pimm50-capacity"/);

  assert.equal(overview.match(/<dl\b/g)?.length, 1);
  assert.equal(overview.match(/<dt\b/g)?.length, 5);
  for (const evidence of ['50 g', 'Steel', '2 × 350 W', '240 × 240 × 100 mm']) {
    assert.match(overview, new RegExp(evidence.replace(/[×]/g, '×')));
  }
  assert.match(overview, /data-pimm50-lead-time/);
});

test('engineering sections carry distinct evidence-led compositions', () => {
  const capacity = sectionById('pimm50-capacity');
  const meltZone = sectionById('pimm50-melt-zone');
  const heating = sectionById('pimm50-heating');
  const moldSpace = sectionById('pimm50-mold-space');

  assert.match(capacity, /data-pimm50-flow/);
  assert.match(meltZone, /pimm50-melt-zone__proof/);
  assert.equal(heating.match(/data-pimm50-readout/g)?.length, 2);
  assert.match(moldSpace, /data-pimm50-dimension/);
  assert.match(moldSpace, /240 × 240 × 100/);
});

test('comparison and purchase keep evaluation ahead of checkout', () => {
  const comparison = sectionById('pimm50-comparison');
  const purchase = sectionById('pimm50-purchase');

  assert.match(comparison, /data-pimm50-comparison-baseline/);
  assert.match(comparison, /maliev-pimm-30g-alpha\.webp/);
  assert.match(comparison, /pimm50-light-studio-hero\.webp/);
  assert.match(comparison, /<dl[^>]+pimm50-comparison__facts/);
  assert.match(comparison, /href="\/products\/pneumatic-injection-molding-machine"/);
  assert.match(comparison, /href="\{\{ visit_link \}\}"/);

  assert.match(purchase, /pimm50-light-studio-purchase\.webp/);
  assert.ok(purchase.indexOf('href="{{ visit_link }}"') < purchase.indexOf('name="add"'));
  assert.doesNotMatch(purchase, /drag|rotat(?:e|or)|360/i);
});

test('motion is a visible-default, reduced-motion-safe enhancement', () => {
  assert.match(css, /\[data-pimm50-motion\]\s*\{[^}]*--p50-progress:\s*1/s);
  assert.match(css, /\.js\s+\[data-pimm50-motion\]:not\(\.is-in-view\)\s*\{[^}]*--p50-progress:\s*0/s);
  assert.match(css, /translateY\(calc\(\(1 - var\(--p50-progress\)\) \* 2%\)\)/);
  assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)[\s\S]*--p50-progress:\s*1/);
  assert.match(js, /classList\.add\(['"]is-in-view['"]\)/);
  assert.doesNotMatch(js, /\.play\(|\.pause\(/);
  assert.doesNotMatch(css, /transition[^;]*(?:height|width|top|right|bottom|left|margin|padding)/);
});

test('50G template remains a single custom product journey', () => {
  assert.deepEqual(template.order, ['launch']);
  assert.deepEqual(Object.keys(template.sections), ['launch']);
  assert.equal(template.sections.launch.type, 'maliev-pimm-50g-launch');
});
