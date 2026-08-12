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

test('focus treatment preserves MALIEV yellow with a contrasting dark indicator', () => {
  const focusRule = css.match(/\.pimm50-page__button:focus-visible,[\s\S]*?\.pimm50-purchase__form select:focus-visible\s*\{([^}]*)\}/)?.[1] ?? '';

  assert.match(focusRule, /box-shadow:\s*inset 0 0 0 \.3rem #ffd21c/i);
  assert.match(focusRule, /outline:\s*\.3rem solid #101820 !important/i);

  const channel = (value) => {
    const normalized = value / 255;
    return normalized <= 0.04045 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
  };
  const luminance = (hex) => {
    const rgb = hex.match(/[a-f\d]{2}/gi).map((value) => Number.parseInt(value, 16));
    return 0.2126 * channel(rgb[0]) + 0.7152 * channel(rgb[1]) + 0.0722 * channel(rgb[2]);
  };
  const contrast = (left, right) => {
    const [lighter, darker] = [luminance(left), luminance(right)].sort((a, b) => b - a);
    return (lighter + 0.05) / (darker + 0.05);
  };

  assert.ok(contrast('101820', 'ffffff') >= 3);
  assert.ok(contrast('101820', 'f3f5f6') >= 3);
  assert.ok(contrast('ffd21c', '101820') >= 3);
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
  const reducedMotion = css.match(/@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{([\s\S]*)\}\s*$/)?.[1] ?? '';

  assert.match(css, /\[data-pimm50-motion\]\s*\{[^}]*--p50-progress:\s*1/s);
  assert.match(css, /\.js\s+\[data-pimm50-motion\]:not\(\.is-in-view\)\s*\{[^}]*--p50-progress:\s*0/s);
  assert.match(css, /--p50-delay:\s*calc\(min\(var\(--p50-index, 0\), 5\) \* 45ms\)/);
  assert.match(css, /data-pimm50-motion="hero-copy"/);
  assert.match(css, /data-pimm50-motion="pneumatic-flow"/);
  assert.match(css, /data-pimm50-motion="heating-readouts"/);
  assert.match(css, /data-pimm50-motion="comparison-machines"/);
  assert.doesNotMatch(css, /data-pimm50-motion[^}]*opacity:\s*0(?:[;}])/s);
  assert.doesNotMatch(section, /data-pimm50-(?:digit|display-overlay|counter)/);
  assert.match(reducedMotion, /\.pimm50-page \[data-pimm50-motion\][\s\S]*\.pimm50-page \[data-pimm50-motion\] \*[\s\S]*\{[^}]*--p50-progress:\s*1[^}]*animation:\s*none[^}]*transition:\s*none[^}]*transform:\s*none[^}]*filter:\s*none[^}]*clip-path:\s*none/s);
  assert.match(js, /const revealMotionTarget = \(element\) => \{/);
  assert.match(js, /classList\.add\(['"]is-in-view['"]\)/);
  assert.match(js, /element\.dataset\.pimm50MotionState = 'complete'/);
  assert.match(js, /activeObserver\.unobserve\(entry\.target\)/);
  assert.doesNotMatch(js, /\.play\(|\.pause\(/);
  assert.doesNotMatch(js, /scroll|wheel|setInterval|requestAnimationFrame|\.animate\(/);
  assert.doesNotMatch(css, /transition[^;]*(?:height|width|top|right|bottom|left|margin|padding)/);
});

test('motion choreography keeps fixed delays and total duration within budget', () => {
  const motionRules = [...css.matchAll(/([^{}]*data-pimm50-motion[^{}]*)\{([^{}]*)\}/g)];
  const transitionTimings = [];

  for (const [, selector, body] of motionRules) {
    for (const transitionDelay of body.matchAll(/transition-delay:\s*([^;]+)/g)) {
      for (const delay of transitionDelay[1].matchAll(/(\d+)ms/g)) {
        assert.ok(Number.parseInt(delay[1], 10) <= 250, `${selector.trim()} uses a ${delay[1]}ms transition-delay`);
      }
    }
    for (const transition of body.matchAll(/transition:\s*([^;]+)/g)) {
      const items = transition[1].replace(/cubic-bezier\([^)]*\)/g, '').split(',');
      for (const item of items) {
        const timings = [...item.matchAll(/(\d+)ms/g)].map((match) => Number.parseInt(match[1], 10));
        if (timings.length > 1) {
          assert.ok(timings[1] <= 250, `${selector.trim()} uses a ${timings[1]}ms fixed transition delay`);
        }
      }
    }
  }

  const moldValues = css.match(/\[data-pimm50-motion="mold-dimension"\] > span,[\s\S]*?\[data-pimm50-motion="mold-dimension"\] > em\s*\{([^}]*)\}/)?.[1] ?? '';
  const moldTransition = moldValues.match(/transition:\s*([^;]+)/)?.[1] ?? '';
  for (const item of moldTransition.replace(/cubic-bezier\([^)]*\)/g, '').split(',')) {
    transitionTimings.push([...item.matchAll(/(\d+)ms/g)].map((match) => Number.parseInt(match[1], 10)));
  }

  assert.deepEqual(transitionTimings, [[620, 250], [620, 250]]);
  assert.ok(transitionTimings.every(([duration, delay]) => duration + delay <= 900));
});

test('heating readouts animate effective row rules and text opacity', () => {
  const rowRule = css.match(/\[data-pimm50-motion="heating-readouts"\] > div\s*\{([^}]*)\}/)?.[1] ?? '';
  const textRule = css.match(/\[data-pimm50-motion="heating-readouts"\] dt,[\s\S]*?\[data-pimm50-motion="heating-readouts"\] span\s*\{([^}]*)\}/)?.[1] ?? '';

  assert.match(rowRule, /border-inline-start:\s*1px solid/);
  assert.match(rowRule, /border-inline-start-color:\s*rgba\([^;]*var\(--p50-progress\)/);
  assert.match(rowRule, /transition:\s*border-inline-start-color 220ms cubic-bezier\(\.22, 1, \.36, 1\) var\(--p50-delay\)/);
  assert.match(textRule, /opacity:\s*calc\(\.84 \+ \(var\(--p50-progress\) \* \.16\)\)/);
  assert.match(textRule, /transition:\s*opacity 220ms cubic-bezier\(\.22, 1, \.36, 1\) var\(--p50-delay\)/);
  assert.doesNotMatch(textRule, /transition:[^;]*\bcolor\b/);
});

test('product sections expose distinct engineering motion roles', () => {
  const required = [
    'hero-media', 'hero-copy', 'hero-facts', 'overview-facts',
    'capacity-media', 'pneumatic-flow', 'melt-media', 'melt-proof',
    'heating-media', 'heating-readouts', 'mold-media', 'mold-dimension',
    'comparison-machines', 'comparison-facts', 'purchase-media', 'purchase-panel'
  ];
  const roles = [...section.matchAll(/data-pimm50-motion="([^"]+)"/g)].map((match) => match[1]).sort();

  assert.deepEqual(roles, [...required].sort());
  for (let index = 0; index < 4; index += 1) assert.match(section, new RegExp(`pimm50-hero__fact[^>]+style="[^"]*--p50-index: ${index}[^"]*"`));
  for (let index = 0; index < 2; index += 1) {
    assert.match(section, new RegExp(`data-pimm50-readout[^>]+style="[^"]*--p50-index: ${index}[^"]*"`));
    assert.match(section, new RegExp(`data-pimm50-comparison-machine[^>]+style="[^"]*--p50-index: ${index}[^"]*"`));
  }
});

test('50G template remains a single custom product journey', () => {
  assert.deepEqual(template.order, ['launch']);
  assert.deepEqual(Object.keys(template.sections), ['launch']);
  assert.equal(template.sections.launch.type, 'maliev-pimm-50g-launch');
});
