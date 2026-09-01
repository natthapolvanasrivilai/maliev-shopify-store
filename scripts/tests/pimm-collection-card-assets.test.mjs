import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, readdir } from 'node:fs/promises';
import test from 'node:test';

const assetsUrl = new URL('../../assets/', import.meta.url);
const release = 'maliev-pimm-collection-20260901-r01';
const expectedPairs = ['30g', '50g'].flatMap((model) =>
  ['front', 'left', 'right'].map((angle) => `${model}:${angle}`),
);
const expectedNative = expectedPairs.map(
  (pair) => `${release}-${pair.replace(':', '-')}.png`,
);
const expectedStorefront = expectedPairs.map(
  (pair) => `${release}-${pair.replace(':', '-')}.webp`,
);
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex').toUpperCase();

function pngMetadata(bytes) {
  assert.equal(bytes.subarray(0, 8).toString('hex'), '89504e470d0a1a0a', 'PNG signature');
  assert.equal(bytes.subarray(12, 16).toString('ascii'), 'IHDR', 'PNG IHDR');
  return {
    width: bytes.readUInt32BE(16),
    height: bytes.readUInt32BE(20),
    bitDepth: bytes[24],
    mode: bytes[25] === 2 ? 'RGB' : `PNG color type ${bytes[25]}`,
  };
}

function webpMetadata(bytes) {
  assert.equal(bytes.subarray(0, 4).toString('ascii'), 'RIFF', 'WebP RIFF signature');
  assert.equal(bytes.subarray(8, 12).toString('ascii'), 'WEBP', 'WebP signature');
  assert.equal(bytes.subarray(12, 16).toString('ascii'), 'VP8L', 'lossless WebP chunk');
  assert.equal(bytes[20], 0x2f, 'lossless WebP signature byte');
  const bits = bytes.readUInt32LE(21);
  return {
    width: (bits & 0x3fff) + 1,
    height: ((bits >>> 14) & 0x3fff) + 1,
    mode: ((bits >>> 28) & 1) === 0 ? 'RGB' : 'RGBA',
    version: bits >>> 29,
  };
}

function declaredFilenames(manifest) {
  return (manifest.assets ?? []).flatMap((asset) =>
    [asset.native?.filename, asset.storefront?.filename].filter(Boolean),
  );
}

test('collection cards use six unique purpose-rendered Blender views', async () => {
  const manifest = JSON.parse(
    await readFile(
      new URL('../../assets/maliev-pimm-collection-assets.v1.json', import.meta.url),
      'utf8',
    ),
  );
  assert.equal(manifest.schema_version, 1);
  assert.equal(manifest.release_id, release);
  assert.equal(manifest.renderer, 'scripts/blender/pimm_production/blender_collection_card_render.py');
  assert.equal(manifest.finalizer, 'scripts/blender/pimm_production/finalize_collection_card_assets.py');
  assert.equal(manifest.samples, 256);
  assert.equal(manifest.assets.length, 6);
  assert.deepEqual(
    manifest.assets.map(({ model, angle }) => `${model}:${angle}`).toSorted(),
    expectedPairs.toSorted(),
  );
  assert.equal(new Set(manifest.assets.map(({ storefront }) => storefront.filename)).size, 6);
  assert.equal(
    manifest.shadow_source,
    'Blender Cycles physical studio floor; no post-render shadow compositing',
  );
  assert.deepEqual(
    manifest.masters,
    {
      '30g': {
        filename: 'PIMM-30G-MASTER.blend',
        sha256: '98577604BB25033B5A7229A66A14D12703E6636DF6B064F877DF7EFC6E65CEFA',
      },
      '50g': {
        filename: 'PIMM-50G-MASTER.blend',
        sha256: 'CC26246CD01956B1145B1AA5744B968918F956B667B720205723E6B60A252D90',
      },
    },
  );

  const declaredNative = [];
  const declaredStorefront = [];
  for (const asset of manifest.assets) {
    assert.equal(asset.angle_degrees, { front: 0, left: -12, right: 12 }[asset.angle]);
    for (const [kind, expectedExtension] of [['native', '.png'], ['storefront', '.webp']]) {
      const output = asset[kind];
      assert.ok(output.filename.endsWith(expectedExtension), `${output.filename} extension`);
      assert.deepEqual(
        [output.width, output.height],
        [1200, 1600],
        `${output.filename} manifest dimensions`,
      );
      const bytes = await readFile(new URL(output.filename, assetsUrl));
      assert.equal(sha256(bytes), output.sha256, `${output.filename} hash`);
      const metadata = kind === 'native' ? pngMetadata(bytes) : webpMetadata(bytes);
      assert.deepEqual(
        [metadata.width, metadata.height],
        [1200, 1600],
        `${output.filename} encoded dimensions`,
      );
      assert.equal(metadata.mode, 'RGB', `${output.filename} encoded mode`);
      if (kind === 'native') {
        assert.equal(metadata.bitDepth, 16, `${output.filename} native bit depth`);
        declaredNative.push(output.filename);
      } else {
        assert.equal(metadata.version, 0, `${output.filename} lossless WebP version`);
        declaredStorefront.push(output.filename);
      }
    }
  }
  assert.deepEqual(declaredNative.toSorted(), expectedNative.toSorted());
  assert.deepEqual(declaredStorefront.toSorted(), expectedStorefront.toSorted());
});

test('collection release filenames do not collide with other PIMM manifests', async () => {
  const names = await readdir(assetsUrl);
  const manifestNames = names.filter((name) =>
    name !== 'maliev-pimm-collection-assets.v1.json'
      && /pimm.*assets.*\.json$/i.test(name),
  );
  const otherDeclared = new Set();
  for (const name of manifestNames) {
    const manifest = JSON.parse(await readFile(new URL(name, assetsUrl), 'utf8'));
    for (const filename of declaredFilenames(manifest)) otherDeclared.add(filename);
  }
  for (const filename of [...expectedNative, ...expectedStorefront]) {
    assert.equal(
      otherDeclared.has(filename),
      false,
      `${filename} collides with another PIMM manifest`,
    );
  }
});
