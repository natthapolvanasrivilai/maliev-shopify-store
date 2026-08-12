import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const section = await readFile(new URL('../../sections/maliev-pimm-50g-launch.liquid', import.meta.url), 'utf8');
const css = await readFile(new URL('../../assets/maliev-pimm-50g-story.css', import.meta.url), 'utf8');
const js = await readFile(new URL('../../assets/maliev-pimm-50g-story.js', import.meta.url), 'utf8');

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
});
