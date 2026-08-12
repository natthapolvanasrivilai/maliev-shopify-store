import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const section = await readFile(new URL('../../sections/maliev-pimm-50g-launch.liquid', import.meta.url), 'utf8');
const css = await readFile(new URL('../../assets/maliev-pimm-50g-story.css', import.meta.url), 'utf8');
const js = await readFile(new URL('../../assets/maliev-pimm-50g-story.js', import.meta.url), 'utf8');
const template = JSON.parse(await readFile(new URL('../../templates/product.pimm-50g.json', import.meta.url), 'utf8').then((value) => value.replace(/^\/\*[\s\S]*?\*\/\s*/, '')));

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
  assert.match(section, /<h1[^>]*>\s*PIMM 50G/);
  assert.match(section, /\{%[-]?\s*form 'product'/);
  assert.match(section, /name="id"/);
  assert.match(section, /name="add"/);
  assert.match(section, /Book a factory visit/);
  assert.doesNotMatch(css, /opacity:\s*0[^}]*data-pimm50-page/);
  assert.match(css, /\.pimm50-page__text-link\s*\{[^}]*align-items:\s*center[^}]*display:\s*inline-flex[^}]*min-height:\s*4\.8rem[^}]*padding:\s*0\s+2rem/s);
});

test('50G template remains a single custom product journey', () => {
  assert.deepEqual(template.order, ['launch']);
  assert.deepEqual(Object.keys(template.sections), ['launch']);
  assert.equal(template.sections.launch.type, 'maliev-pimm-50g-launch');
});
