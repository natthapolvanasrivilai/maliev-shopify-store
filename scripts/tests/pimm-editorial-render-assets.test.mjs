import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));
const assetsRoot = join(root, 'assets');
const manifestPath = join(assetsRoot, 'pimm-editorial-render-assets.v1.json');
const canonicalRoot = 'M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\renders\\final\\editorial-concepts-v1\\editorial-release-2026-08-30-r01';
const releaseManifestSha256 = '9CBCB6A3787DDD76DFBA5B1962DA36B30616E2838518FBD8469436F979733C5B';
const expected = [
  ['architectural-daylight', 'pimm-editorial-30g-architectural-daylight.webp', [2560, 1440], 'pimm-30g--concept-architectural-daylight'],
  ['dark-engineering', 'pimm-editorial-50g-dark-engineering.webp', [2560, 1440], 'pimm-50g--concept-dark-engineering'],
  ['modern-workshop', 'pimm-editorial-50g-modern-workshop.webp', [2560, 1440], 'pimm-50g--concept-modern-workshop'],
  ['process-still-life', 'pimm-editorial-30g-process-still-life.webp', [1800, 2250], 'pimm-30g--concept-process-still-life'],
];

const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex').toUpperCase();
const probe = (path) => JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=codec_name,width,height,pix_fmt', '-of', 'json', path], { encoding: 'utf8' })).streams[0];
const alphaExtrema = (path, width, height) => {
  const rgba = execFileSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-i', path, '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgba', 'pipe:1'], { maxBuffer: width * height * 4 + 1024 });
  let min = 255;
  let max = 0;
  for (let index = 3; index < rgba.length; index += 4) {
    min = Math.min(min, rgba[index]);
    max = Math.max(max, rgba[index]);
  }
  return { min, max };
};

test('committed editorial assets bind the accepted release and exact opaque derivatives', () => {
  const manifestBytes = readFileSync(manifestPath);
  const manifest = JSON.parse(manifestBytes);
  assert.equal(manifest.schema, 'maliev.pimm-editorial-render-assets/v1');
  assert.equal(manifest.release_id, 'editorial-release-2026-08-30-r01');
  assert.equal(manifest.generation_id, 'editorial-preview-20260830T120711.840572Z-63746b40-bca60b04');
  assert.equal(manifest.release_manifest_sha256, releaseManifestSha256);
  assert.equal(manifest.assets.length, expected.length);
  assert.equal(sha256(readFileSync(join(canonicalRoot, 'release-manifest.json'))), releaseManifestSha256);

  for (const [scene, name, dimensions, shotId] of expected) {
    const entry = manifest.assets.find((asset) => asset.scene === scene);
    assert.ok(entry, `missing ${scene}`);
    assert.equal(entry.name, name);
    assert.deepEqual(entry.dimensions, dimensions);
    assert.equal(entry.shot_id, shotId);
    assert.equal(entry.derivative.codec, 'webp');
    assert.equal(entry.derivative.alpha, false);
    assert.equal(entry.native.png.path, join(canonicalRoot, `${shotId}.png`));
    assert.equal(entry.native.exr.path, join(canonicalRoot, `${shotId}.exr`));
    assert.equal(entry.source_webp.path, join(canonicalRoot, `${shotId}.webp`));
    for (const record of [entry.native.png, entry.native.exr, entry.source_webp, entry.derivative]) {
      assert.match(record.sha256, /^[0-9A-F]{64}$/);
    }
    const destination = join(assetsRoot, name);
    assert.ok(statSync(destination).size > 1000);
    assert.equal(sha256(readFileSync(destination)), entry.derivative.sha256);
    const metadata = probe(destination);
    assert.equal(metadata.codec_name, 'webp');
    assert.deepEqual([metadata.width, metadata.height], dimensions);
    assert.equal(metadata.pix_fmt, 'yuv420p');
    assert.deepEqual(alphaExtrema(destination, ...dimensions), { min: 255, max: 255 }, `${name} is not fully opaque`);
    assert.equal(sha256(readFileSync(entry.native.png.path)), entry.native.png.sha256);
    assert.equal(sha256(readFileSync(entry.native.exr.path)), entry.native.exr.sha256);
    assert.equal(sha256(readFileSync(entry.source_webp.path)), entry.source_webp.sha256);
  }
});
