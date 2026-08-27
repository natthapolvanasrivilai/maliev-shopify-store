import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../../', import.meta.url));
const assets = new Map([
  ['pimm-machine-30g-hero-front.webp', [1800, 2200]],
  ['pimm-machine-30g-overview-three-quarter.webp', [2400, 1800]],
  ['pimm-machine-30g-engineering-controls.webp', [2400, 1800]],
  ['pimm-machine-30g-tooling-front-detail.webp', [2400, 1800]],
  ['pimm-machine-50g-hero-front.webp', [1800, 2200]],
  ['pimm-machine-50g-overview-three-quarter.webp', [2400, 1800]],
  ['pimm-machine-50g-engineering-controls.webp', [2400, 1800]],
  ['pimm-machine-50g-tooling-front-detail.webp', [2400, 1800]],
]);

const probe = (path) => JSON.parse(execFileSync(
  'ffprobe',
  [
    '-v', 'error',
    '-select_streams', 'v:0',
    '-show_entries', 'stream=codec_name,width,height,pix_fmt',
    '-of', 'json',
    path,
  ],
  { encoding: 'utf8' },
)).streams[0];

const alphaRange = (path, width, height) => {
  const rgba = execFileSync(
    'ffmpeg',
    [
      '-hide_banner', '-loglevel', 'error',
      '-i', path,
      '-frames:v', '1',
      '-f', 'rawvideo',
      '-pix_fmt', 'rgba',
      'pipe:1',
    ],
    { maxBuffer: (width * height * 4) + 1024 },
  );
  let min = 255;
  let max = 0;
  for (let index = 3; index < rgba.length; index += 4) {
    min = Math.min(min, rgba[index]);
    max = Math.max(max, rgba[index]);
  }
  return { min, max };
};

test('unified PIMM render assets retain the governed WebP and alpha contract', () => {
  assert.equal(assets.size, 8);
  for (const [name, [sourceWidth, sourceHeight]] of assets) {
    const path = join(root, 'assets', name);
    const bytes = readFileSync(path);
    assert.ok(statSync(path).size > 20_000, `${name} is unexpectedly small`);
    assert.equal(bytes.subarray(0, 4).toString('ascii'), 'RIFF', `${name} is not RIFF`);
    assert.equal(bytes.subarray(8, 12).toString('ascii'), 'WEBP', `${name} is not WebP`);

    const metadata = probe(path);
    assert.equal(metadata.codec_name, 'webp', `${name} codec drifted`);
    assert.ok(metadata.width >= 1200 && metadata.height >= 900, `${name} is too small`);
    assert.ok(metadata.width <= sourceWidth, `${name} was enlarged horizontally`);
    assert.ok(metadata.height <= sourceHeight, `${name} was enlarged vertically`);
    assert.equal(
      metadata.width / metadata.height,
      sourceWidth / sourceHeight,
      `${name} aspect ratio drifted`,
    );

    const alpha = alphaRange(path, metadata.width, metadata.height);
    assert.ok(alpha.min < 255, `${name} lost transparent pixels`);
    assert.equal(alpha.max, 255, `${name} has no fully opaque subject pixels`);
  }
});
