import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../', import.meta.url);
const expected = { centerX: 250, centerY: 315, radius: 115 };

const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');

test('white callout ring follows the native magnifier mask instead of drifting around it', async () => {
  const manifest = JSON.parse(await readFile(new URL('assets/pimm-bento-r30-control-motion.v1.json', root), 'utf8'));
  const asset = manifest.assets.find(({ shot }) => shot === 'air-pressure');
  const overlay = asset.callout_overlay;
  const sourceBytes = await readFile(new URL(overlay.source, root));
  const source = sourceBytes.toString('utf8');

  assert.deepEqual(overlay.center, [expected.centerX, expected.centerY]);
  assert.equal(overlay.radius, expected.radius);
  assert.equal(sha256(sourceBytes), overlay.source_sha256);
  assert.match(source, /<circle cx="250" cy="315" r="115"[^>]*stroke="#fff"[^>]*stroke-width="6"/);
  assert.match(source, /<path d="M 169 397 L 139 435 L 181 407 Z"[^>]*stroke-linejoin="round"/);
  assert.deepEqual(overlay.pointer_tip, [139, 435]);
});
