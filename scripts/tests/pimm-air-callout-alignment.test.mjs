import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../', import.meta.url);
const width = 400;
const height = 550;
const expected = { centerX: 250, centerY: 315, radius: 115 };

const midpoint = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;

test('white callout ring follows the native magnifier mask instead of drifting around it', async () => {
  const manifest = JSON.parse(await readFile(new URL('assets/pimm-bento-r30-control-motion.v1.json', root), 'utf8'));
  const asset = manifest.assets.find(({ shot }) => shot === 'air-pressure');
  const videoPath = new URL(`assets/${asset.filename}`, root);
  const decode = spawnSync('ffmpeg', [
    '-hide_banner', '-loglevel', 'error', '-ss', '5', '-i', videoPath.pathname.slice(1),
    '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1',
  ], { maxBuffer: width * height * 4 });

  assert.equal(decode.status, 0, decode.stderr.toString());
  assert.equal(decode.stdout.length, width * height * 3);

  const brightness = (x, y) => {
    const offset = (y * width + x) * 3;
    return (decode.stdout[offset] + decode.stdout[offset + 1] + decode.stdout[offset + 2]) / 3;
  };
  const whiteX = (from, to, y) => Array.from({ length: to - from + 1 }, (_, index) => from + index)
    .filter((x) => brightness(x, y) >= 248);
  const whiteY = (from, to, x) => Array.from({ length: to - from + 1 }, (_, index) => from + index)
    .filter((y) => brightness(x, y) >= 248);

  const left = midpoint(whiteX(120, 145, expected.centerY));
  const right = midpoint(whiteX(355, 380, expected.centerY));
  const top = midpoint(whiteY(188, 210, expected.centerX));
  const bottom = midpoint(whiteY(420, 445, expected.centerX));
  const measured = {
    centerX: (left + right) / 2,
    centerY: (top + bottom) / 2,
    radius: ((right - left) + (bottom - top)) / 4,
  };

  assert.ok(Math.abs(measured.centerX - expected.centerX) <= 1.5, `ring center x drifted to ${measured.centerX}`);
  assert.ok(Math.abs(measured.centerY - expected.centerY) <= 1.5, `ring center y drifted to ${measured.centerY}`);
  assert.ok(Math.abs(measured.radius - expected.radius) <= 1.5, `ring radius drifted to ${measured.radius}`);
});
