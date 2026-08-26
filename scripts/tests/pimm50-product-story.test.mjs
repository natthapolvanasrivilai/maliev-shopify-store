import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../blender/create_pimm50_product_story.py', import.meta.url), 'utf8');

test('builder creates a dedicated immutable-source product story', () => {
  assert.match(source, /PIMM-50g-keynote-reveal-v2-regulator-materials\.blend/);
  assert.match(source, /PIMM-50g-product-story-v1\.blend/);
  assert.match(source, /EXPECTED_MACHINE_OBJECTS\s*=\s*481/);
  assert.match(source, /SOURCE_SHA256\s*=\s*"C19DDA7902BE63A2B28A77D3EF349D17555642399A9589B9A06EFCC05EAB882A"/);
  assert.match(source, /assert_source_immutable/);
  assert.doesNotMatch(source, /save_as_mainfile\(filepath=str\(SOURCE_BLEND\)/);
});

test('builder owns all desktop and mobile story scenes', () => {
  for (const chapter of ['REVEAL', 'OVERVIEW', 'CAPACITY', 'MELT_ZONE', 'HEATING', 'MOLD_SPACE', 'COMPARISON', 'PURCHASE']) {
    assert.match(source, new RegExp(`PIMM50_STORY_${chapter}_DESKTOP`));
    assert.match(source, new RegExp(`PIMM50_STORY_${chapter}_MOBILE`));
  }
  assert.match(source, /film_transparent\s*=\s*True/);
  assert.match(source, /color_mode\s*=\s*"RGBA"/);
  assert.match(source, /70\.0/);
  assert.match(source, /88\.0/);
});

test('proof renderer emits separate desktop and mobile assets', () => {
  assert.match(source, /pimm50-story-\{slug\}-\{layout\}\.png/);
  assert.match(source, /"desktop": \(1800, 1600\)/);
  assert.match(source, /"mobile": \(1350, 1800\)/);
  assert.match(source, /render_proofs/);
});
