import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const section = await readFile(new URL('../../sections/maliev-pimm-50g-launch.liquid', import.meta.url), 'utf8');
const css = await readFile(new URL('../../assets/maliev-pimm-50g-story.css', import.meta.url), 'utf8');
const js = await readFile(new URL('../../assets/maliev-pimm-50g-story.js', import.meta.url), 'utf8');
const template = JSON.parse(await readFile(new URL('../../templates/product.pimm-50g.json', import.meta.url), 'utf8').then((value) => value.replace(/^\/\*[\s\S]*?\*\/\s*/, '')));

test('story owns eight semantic keynote chapters backed by Blender assets', () => {
  for (const id of ['reveal', 'overview', 'capacity', 'melt-zone', 'heating', 'mold-space', 'comparison', 'purchase']) {
    assert.match(section, new RegExp(`id="pimm50-${id}"`));
  }
  assert.equal((section.match(/class="pimm50-story__chapter/g) || []).length, 8);
  assert.match(section, /pimm50-story-overview-desktop\.webp/);
  assert.match(section, /pimm50-story-overview-mobile\.webp/);
  assert.doesNotMatch(section, /pimm-50g-launch-(?:backdrop|air-energy|melt-energy|heater-coils)/);
  assert.doesNotMatch(section, /pimm-50g-wide-(?:hero|tall-frame|base-space)/);
});

test('purchase remains live Shopify HTML with accessible actions', () => {
  assert.match(section, /selected_or_first_available_variant/);
  assert.match(section, /\| money_without_trailing_zeros/);
  assert.match(section, /\{%[-]?\s*form 'product'/);
  assert.match(section, /name="id"/);
  assert.match(section, /name="add"/);
  assert.match(section, /section\.settings\.visit_link/);
  assert.match(section, /Suitable compressed-air supply required/);
  assert.match(section, /Up to 240 × 240 × 100 mm/);
  assert.match(section, /Demonstration and setup guidance available/);
  assert.match(section, /aria-label=/);
});

test('50G template is a single custom product journey without Dawn duplication', () => {
  assert.deepEqual(template.order, ['launch']);
  assert.deepEqual(Object.keys(template.sections), ['launch']);
});

test('story supplies responsive motion and interaction contracts', () => {
  assert.match(section, /maliev-pimm-50g-story\.css/);
  assert.match(section, /maliev-pimm-50g-story\.js/);
  assert.match(css, /100svh/);
  assert.match(css, /prefers-reduced-motion/);
  assert.match(css, /focus-visible/);
  assert.match(js, /IntersectionObserver/);
  assert.match(js, /aria-current/);
  assert.match(section, /pimm50-story__rail/);
  assert.match(js, /prefers-reduced-motion/);
});
