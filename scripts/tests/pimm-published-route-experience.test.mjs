import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();
const read = (file) => fs.readFile(path.join(root, file), 'utf8');

test('published PIMM products retain the approved cinematic and bento experience', async () => {
  const [section, hero, story30, story50] = await Promise.all([
    read('sections/maliev-pimm-machine-product.liquid'),
    read('snippets/pimm-hero-console.liquid'),
    read('snippets/pimm-30g-product-story.liquid'),
    read('snippets/pimm-50g-product-story.liquid'),
  ]);

  assert.match(section, /product\.handle == 'pneumatic-injection-molding-machine'[\s\S]*?assign page_model = '30G'/);
  assert.match(section, /product\.handle == 'pneumatic-injection-molding-machine-50g'[\s\S]*?assign page_model = '50G'/);
  assert.match(section, /maliev-pimm-cinematic\.js/);
  assert.match(hero, /render 'pimm-cinematic-hero'/);
  assert.match(hero, /render 'pimm-50g-cinematic-hero'/);
  assert.match(story30, /class="pimm-bento"/);
  assert.match(story50, /class="pimm-50g-bento"/);
});

test('published PIMM collection retains native hover lighting that dims the other machine', async () => {
  const [section, controller] = await Promise.all([
    read('sections/maliev-pimm-collection.liquid'),
    read('assets/maliev-pimm-collection.js'),
  ]);

  assert.match(section, /render 'pimm-collection-lighting', model: '30g'/);
  assert.match(section, /render 'pimm-collection-lighting', model: '50g'/);
  assert.match(section, /data-pimm-collection-video/);
  assert.match(controller, /pointerenter[\s\S]*?previewModel/);
  assert.match(controller, /setStudioLighting\(card, dim/);
  assert.match(controller, /is-studio-dim/);
});
