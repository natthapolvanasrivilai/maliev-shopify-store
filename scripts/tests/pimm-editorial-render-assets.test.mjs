import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join, win32 } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));
const assetsRoot = join(root, 'assets');
const manifestPath = join(assetsRoot, 'pimm-editorial-render-assets.v1.json');
const canonicalRoot = 'M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\renders\\final\\editorial-concepts-v1\\editorial-release-2026-08-30-r01';
const expected = [
  { scene: 'architectural-daylight', name: 'pimm-editorial-30g-architectural-daylight.webp', dimensions: [2560, 1440], shotId: 'pimm-30g--concept-architectural-daylight', sceneSha256: '926621C03C2387744E3602C330A33A0EEDC2B3590EEA60F116399CC89932BF33', pngSha256: '5E6B720593D00FA0B957B123B123F45D7387B4366BED563DB63035281A97F952', exrSha256: '873D8F1D9736FF289C9BB63E4E5A14C14499CEE1E70F2A9337A13ACD4E218E2C', sourceSha256: '5CBA51403B0CBE030CA6DAEB5EE867D762726BBEE6938574045C60F8BD053234', derivativeSha256: 'CC27E0E11893D6595D16CDA3DAE363590D74C5C532CA6E6D6E88E722DE8ECFD5' },
  { scene: 'dark-engineering', name: 'pimm-editorial-50g-dark-engineering.webp', dimensions: [2560, 1440], shotId: 'pimm-50g--concept-dark-engineering', sceneSha256: 'CE85B57C34CB5F165FE62DC6B402963C3071F1CC20A89AA905F4248F23C212DB', pngSha256: '8BD7445A57366FBF1AACEED543EC26B3A99CCB016A2ED35A403A0073477A7C85', exrSha256: '6827B3B26A1B62B9F53069867B27E144E13FFBC2580A999D9662304C27527978', sourceSha256: 'AAE9D7907B9D4DD2C294A5A9196C57E94F10CF6D9D17A6FB4F414DC9DE0E82D2', derivativeSha256: 'DF4AA9768C7C977960DF7695C9B3D8F1E1DBAA216626228AB1643EDC09EE67B8' },
  { scene: 'modern-workshop', name: 'pimm-editorial-50g-modern-workshop.webp', dimensions: [2560, 1440], shotId: 'pimm-50g--concept-modern-workshop', sceneSha256: '73D5D5FEF042B602626CA0771EC666D575FF1A467E93F8B5CF20F91DC1680EB3', pngSha256: '7913DBE4AC7E8DCBD0DD841EDF5072154168F091D2FC5033F6297AE041B2F159', exrSha256: 'DFCA5738CDFFBA2D22D6EFBD9C5B914747DE5C7490BBD23C24A672043AE7A389', sourceSha256: 'FA21D0D6FA82468CA1386DC22A49FBF3D21385B445652C8BA070D9F5777C0F12', derivativeSha256: '265F4D0725DF34A1DBA8FCDDCAD9253E99F0629EFA604AF3C8363139FFEBC05E' },
  { scene: 'process-still-life', name: 'pimm-editorial-30g-process-still-life.webp', dimensions: [1800, 2250], shotId: 'pimm-30g--concept-process-still-life', sceneSha256: '8483A0444A06BE6D80BEFAAC6B6E6EB18CE06E4E65ACE11C5065DB2476FFEFAD', pngSha256: '10D3B52034C109ED0B5434F573251773BB471C557C7C0F89040C3A3FB5DC491F', exrSha256: 'F3E72F223B1E1AC2CB2608AE5986490DD2360EB0E238188CA46021C05163F2A1', sourceSha256: 'A331525DE9659A53C7DF4A70DCB9FDB58985801B9CD73F37CE62D52BF2123ED6', derivativeSha256: '9B75167D0B4DE691F5302AA73AA8A9B60AEB1F443382B2290A28F93A9A86956F' },
];
const releaseManifestSha256 = '9CBCB6A3787DDD76DFBA5B1962DA36B30616E2838518FBD8469436F979733C5B';
const generationId = 'editorial-preview-20260830T120711.840572Z-63746b40-bca60b04';
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex').toUpperCase();
const readUint24LE = (bytes, offset) => bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16);
const lineagePath = (shotId, extension) => win32.join(canonicalRoot, `${shotId}.${extension}`);

const webpMetadata = (bytes) => {
  assert.equal(bytes.subarray(0, 4).toString('ascii'), 'RIFF', 'asset is not RIFF');
  assert.equal(bytes.subarray(8, 12).toString('ascii'), 'WEBP', 'asset is not WebP');
  assert.equal(bytes.readUInt32LE(4), bytes.length - 8, 'RIFF length is not exact');
  let found;
  for (let offset = 12; offset + 8 <= bytes.length;) {
    const type = bytes.subarray(offset, offset + 4).toString('ascii');
    const length = bytes.readUInt32LE(offset + 4);
    const data = offset + 8;
    const end = data + length + (length % 2);
    assert.ok(end <= bytes.length, `truncated ${type} chunk`);
    if (type === 'VP8X') {
      assert.equal(length, 10, 'invalid VP8X length');
      found = { codec: 'webp', alpha: (bytes[data] & 0x10) !== 0, dimensions: [readUint24LE(bytes, data + 4) + 1, readUint24LE(bytes, data + 7) + 1] };
    } else if (type === 'VP8 ') {
      assert.equal(bytes.subarray(data + 3, data + 6).toString('hex'), '9d012a', 'invalid VP8 signature');
      found = { codec: 'webp', alpha: false, dimensions: [bytes.readUInt16LE(data + 6) & 0x3fff, bytes.readUInt16LE(data + 8) & 0x3fff] };
    }
    offset = end;
  }
  assert.ok(found, 'WebP has no readable VP8/VP8X frame');
  return found;
};

const validateManifest = (manifest) => {
  assert.equal(manifest.schema, 'maliev.pimm-editorial-render-assets/v1');
  assert.equal(manifest.release_id, 'editorial-release-2026-08-30-r01');
  assert.equal(manifest.generation_id, generationId);
  assert.equal(manifest.release_manifest_sha256, releaseManifestSha256);
  assert.equal(manifest.assets.length, expected.length);
  for (const item of expected) {
    const entry = manifest.assets.find((asset) => asset.scene === item.scene);
    assert.ok(entry, `missing ${item.scene}`);
    assert.equal(entry.name, item.name);
    assert.deepEqual(entry.dimensions, item.dimensions);
    assert.equal(entry.shot_id, item.shotId);
    assert.equal(entry.scene_sha256, item.sceneSha256);
    assert.equal(entry.native.png.path, lineagePath(item.shotId, 'png'));
    assert.equal(entry.native.png.sha256, item.pngSha256);
    assert.equal(entry.native.exr.path, lineagePath(item.shotId, 'exr'));
    assert.equal(entry.native.exr.sha256, item.exrSha256);
    assert.equal(entry.source_webp.path, lineagePath(item.shotId, 'webp'));
    assert.equal(entry.source_webp.sha256, item.sourceSha256);
    assert.equal(entry.derivative.path, `assets/${item.name}`);
    assert.equal(entry.derivative.sha256, item.derivativeSha256);
    assert.equal(entry.derivative.codec, 'webp');
    assert.equal(entry.derivative.alpha, false);
  }
};

test('committed editorial assets bind immutable accepted lineage and portable WebP bytes', () => {
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  validateManifest(manifest);
  for (const item of expected) {
    const bytes = readFileSync(join(assetsRoot, item.name));
    assert.equal(sha256(bytes), item.derivativeSha256, `${item.name} derivative hash drifted`);
    assert.deepEqual(webpMetadata(bytes), { codec: 'webp', alpha: false, dimensions: item.dimensions });
  }
});

test('lineage validation rejects coordinated manifest hash mutations', () => {
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
  for (const field of ['scene_sha256', 'native.png.sha256', 'native.exr.sha256', 'source_webp.sha256', 'derivative.sha256']) {
    const mutated = structuredClone(manifest);
    const [parent, child] = field.split('.');
    if (child) mutated.assets[0][parent][child] = 'F'.repeat(64);
    else mutated.assets[0][parent] = 'F'.repeat(64);
    assert.throws(() => validateManifest(mutated), undefined, field);
  }
});

test('canonical lineage paths remain Windows paths on every CI host', () => {
  const path = lineagePath(expected[0].shotId, 'png');
  assert.equal(path.startsWith(['M:', '\\', '30_Products', '\\'].join('')), true);
  assert.equal(path.includes('/'), false);
});
