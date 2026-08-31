import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, readdir } from 'node:fs/promises';
import test from 'node:test';

const rootUrl = new URL('../../', import.meta.url);
const assetsUrl = new URL('../../assets/', import.meta.url);
const release = 'pimm-master-20260831-r02';
const roles = ['controls', 'hero', 'three-quarter', 'tooling'];
const expectedMedia = ['30g', '50g'].flatMap((model) => roles.flatMap((role) => [
  `${release}-${model}-${role}.png`,
  `${release}-${model}-${role}.webp`,
]));
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex').toUpperCase();

test('master-derived release is the only PIMM media family in theme assets', async () => {
  const names = await readdir(assetsUrl);
  const pimmMedia = names.filter((name) => /^(?:pimm|maliev-pimm).+\.(?:avif|jpe?g|png|webp|webm|mp4)$/i.test(name)).sort();
  assert.deepEqual(pimmMedia, expectedMedia.toSorted());
});

test('manifest locks every native render and storefront derivative to exact hashes', async () => {
  const manifest = JSON.parse(await readFile(new URL('../../assets/pimm-master-storefront-assets.v1.json', import.meta.url), 'utf8'));
  assert.equal(manifest.schema_version, 1);
  assert.equal(manifest.release_id, release);
  assert.equal(manifest.renderer, 'scripts/blender/pimm_production/blender_master_storefront_render.py');
  assert.equal(manifest.masters['30g'].filename, 'PIMM-30G-MASTER.blend');
  assert.equal(manifest.masters['50g'].filename, 'PIMM-50G-MASTER.blend');
  assert.equal(manifest.masters['30g'].foot_count, 4);
  assert.equal(manifest.masters['50g'].foot_count, 4);
  assert.ok(manifest.masters['30g'].foot_contact_spread_m <= 0.0002);
  assert.ok(manifest.masters['50g'].foot_contact_spread_m <= 0.0002);
  assert.equal(manifest.assets.length, 8);

  const declared = [];
  for (const asset of manifest.assets) {
    for (const output of [asset.native, asset.storefront]) {
      const bytes = await readFile(new URL(`../../assets/${output.filename}`, import.meta.url));
      assert.equal(sha256(bytes), output.sha256, output.filename);
      assert.ok(output.width >= 1600, `${output.filename} width`);
      assert.ok(output.height >= 1200, `${output.filename} height`);
      declared.push(output.filename);
    }
  }
  assert.deepEqual(declared.toSorted(), expectedMedia.toSorted());
});

test('active configurator references all and only release WebP assets', async () => {
  const paths = [
    'sections/maliev-pimm-machine-product.liquid',
    'snippets/pimm-hero-console.liquid',
    'snippets/pimm-30g-product-story.liquid',
    'snippets/pimm-50g-product-story.liquid',
    'templates/product.pimm-configurator.json',
    'assets/maliev-pimm-machine.js',
  ];
  const source = (await Promise.all(paths.map((path) => readFile(new URL(path, rootUrl), 'utf8')))).join('\n');
  const referenced = [...new Set(source.match(new RegExp(`${release}-(?:30g|50g)-(?:controls|hero|three-quarter|tooling)\\.webp`, 'g')))].sort();
  const expectedWebp = expectedMedia.filter((name) => name.endsWith('.webp')).sort();
  assert.deepEqual(referenced, expectedWebp);
  assert.doesNotMatch(source, /(?:(?:pimm30-|pimm50-|pimm-(?:machine|editorial)-|maliev-pimm-)[^'"\s)]+\.(?:png|webp|webm|mp4))/i);
});
