import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const assetUrl = (name) => new URL(`../../assets/${name}`, import.meta.url);

const active30G = [
  'pimm30-v13-hero-desktop-contained.webm',
  'pimm30-v13-hero-desktop-contained.webp',
  'pimm30-v13-hero-mobile-contained.webm',
  'pimm30-v13-hero-mobile-contained.webp',
  'pimm30-capacity-three-cube-desktop.webm',
  'pimm30-capacity-three-cube-desktop.webp',
  'pimm30-temperature-controller-desktop.webm',
  'pimm30-temperature-controller-desktop.webp',
  'pimm30-v11-cylinder-desktop.webp',
  'pimm30-direct-operation-desktop.webm',
  'pimm30-v16-operation-desktop.webp',
  'pimm30-v16-operation-mobile.webp',
  'pimm30-v10-regulator-desktop.webp',
  'pimm30-v15-fixture-desktop.webp',
  'pimm30-v15-fixture-mobile.webp',
  'pimm30-v10-capacity-desktop.webp',
  'pimm30-v10-capacity-mobile.webp',
  'pimm30-configuration-turntable-desktop.webm',
  'pimm30-configuration-turntable-desktop.webp',
  'pimm30-v10-commerce-mobile.webp',
];

const active50G = ['hero', 'capacity', 'melt-zone', 'heating', 'mold-space', 'purchase']
  .map((name) => `pimm50-light-studio-${name}.webp`);

test('governed unified story assets exist with their declared container signatures', async () => {
  for (const name of [...active30G, ...active50G]) {
    const bytes = await readFile(assetUrl(name));
    assert.ok(bytes.length > 16, `${name} must not be empty`);
    if (name.endsWith('.webp')) {
      assert.equal(bytes.subarray(0, 4).toString('ascii'), 'RIFF', `${name} must use RIFF`);
      assert.equal(bytes.subarray(8, 12).toString('ascii'), 'WEBP', `${name} must use WebP`);
    } else {
      assert.deepEqual([...bytes.subarray(0, 4)], [0x1a, 0x45, 0xdf, 0xa3], `${name} must use EBML/WebM`);
    }
  }
});
