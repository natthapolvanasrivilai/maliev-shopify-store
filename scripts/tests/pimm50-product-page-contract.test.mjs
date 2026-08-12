import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const section = await readFile(new URL('../../sections/maliev-pimm-50g-launch.liquid', import.meta.url), 'utf8');
const css = await readFile(new URL('../../assets/maliev-pimm-50g-story.css', import.meta.url), 'utf8');
const js = await readFile(new URL('../../assets/maliev-pimm-50g-story.js', import.meta.url), 'utf8');
const template = JSON.parse(await readFile(new URL('../../templates/product.pimm-50g.json', import.meta.url), 'utf8').then((value) => value.replace(/^\/\*[\s\S]*?\*\/\s*/, '')));

const sectionById = (id) => section.match(new RegExp(`<section[^>]+id="${id}"[\\s\\S]*?<\\/section>`))?.[0] ?? '';
const cssRule = (selector) => css.match(new RegExp(`${selector.replace(/[.*+?^${}()|[\\]\\]/g, '\\$&')}\\s*\\{([^}]*)\\}`))?.[1] ?? '';

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
  assert.match(hero, /href="#pimm50-purchase"/);
  assert.ok(hero.indexOf('href="{{ visit_link }}"') < hero.indexOf('href="#pimm50-purchase"'), 'Factory visit must remain the first hero action');

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
  for (const fact of ['30 g', '50 g', '2 × 300 W', '2 × 350 W', 'Aluminum', 'Steel']) {
    assert.match(comparison, new RegExp(fact));
  }
  assert.match(section, /assign comparison_product = all_products\['pneumatic-injection-molding-machine'\]/);
  assert.match(comparison, /href="\{\{ comparison_product\.url \}\}"/);
  assert.doesNotMatch(comparison, /href="\/products\//);
  assert.match(comparison, /href="\{\{ visit_link \}\}"/);

  assert.match(purchase, /pimm50-light-studio-purchase\.webp/);
  assert.ok(purchase.indexOf('href="{{ visit_link }}"') < purchase.indexOf('name="add"'));
  assert.doesNotMatch(purchase, /drag|rotat(?:e|or)|360/i);
});

test('comparison calibration matches visible alpha height and baseline', () => {
  const comparison = sectionById('pimm50-comparison');
  const assets = [
    { model: '30g', bounds: [520, 1602, 1750] },
    { model: '50g', bounds: [250, 1170, 1400] },
  ];
  const calibrated = [];

  for (const { model, bounds } of assets) {
    assert.match(comparison, new RegExp(`data-pimm50-comparison-machine="${model}"[\\s\\S]*?data-pimm50-alpha-bounds="${bounds.join(' ')}"`));
    const rule = cssRule(`.pimm50-comparison__machine--${model}`);
    const canvasHeight = Number(rule.match(/--p50-comparison-canvas-height:\s*([\d.]+)/)?.[1]);
    const canvasBottom = Number(rule.match(/--p50-comparison-canvas-bottom:\s*([\d.]+)/)?.[1]);
    assert.ok(Number.isFinite(canvasHeight), `${model} canvas-height calibration is missing`);
    assert.ok(Number.isFinite(canvasBottom), `${model} canvas-bottom calibration is missing`);

    const [alphaTop, alphaBottom, canvasSize] = bounds;
    calibrated.push({
      visibleHeight: canvasHeight * ((alphaBottom - alphaTop) / canvasSize),
      visibleBottom: canvasBottom + canvasHeight * ((canvasSize - alphaBottom) / canvasSize),
    });
  }

  assert.ok(Math.abs(calibrated[0].visibleHeight - calibrated[1].visibleHeight) < .0005);
  assert.ok(Math.abs(calibrated[0].visibleBottom - calibrated[1].visibleBottom) < .0005);
  assert.match(cssRule('.pimm50-comparison__machines'), /align-items:\s*start/);
  assert.match(css, /\.pimm50-comparison__stage img\s*\{[^}]*bottom:\s*calc\(var\(--p50-comparison-canvas-bottom\)\s*\*\s*100%\)[^}]*height:\s*calc\(var\(--p50-comparison-canvas-height\)\s*\*\s*100%\)/s);
});

test('variant changes progressively update sanitized commerce readouts', () => {
  const purchase = sectionById('pimm50-purchase');

  for (const hook of ['data-pimm50-variant-title', 'data-pimm50-variant-price', 'data-pimm50-availability', 'data-pimm50-variant-data']) {
    assert.match(purchase, new RegExp(hook));
  }
  assert.match(purchase, /data-pimm50-variant-status[^>]*role="status"[^>]*aria-live="polite"[^>]*aria-atomic="true"/);
  assert.match(purchase, /variant\.title \| strip_html \| escape/);
  assert.match(purchase, /variant\.price \| money_with_currency \| strip_html \| escape/);
  assert.match(purchase, /variant\.title \| strip_html \| json/);
  assert.match(purchase, /variant\.price \| money_with_currency \| strip_html \| json/);
  assert.match(js, /addEventListener\(['"]change['"]/);
  assert.match(js, /variantTitle\.textContent\s*=\s*variant\.title/);
  assert.match(js, /variantPrice\.textContent\s*=\s*variant\.price/);
  assert.match(js, /availability\.textContent\s*=/);
  assert.match(js, /addButton\.disabled\s*=\s*!variant\.available/);
  assert.doesNotMatch(js, /innerHTML/);
});

test('hero and purchase expose alpha-aware authoritative-media hooks', () => {
  const hero = sectionById('pimm50-hero');
  const purchase = sectionById('pimm50-purchase');

  assert.match(hero, /data-pimm50-authoritative-media="hero"[^>]*data-pimm50-alpha-bounds="506 250 895 1170 1400 1400"/);
  assert.match(purchase, /data-pimm50-authoritative-media="purchase"[^>]*data-pimm50-alpha-bounds="514 250 894 1167 1400 1400"/);
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
