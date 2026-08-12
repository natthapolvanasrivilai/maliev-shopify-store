import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

const root = path.resolve(import.meta.dirname, '../..');
const approvedRenderRoot = 'M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders\\renders\\pimm50-light-studio-v1\\proofs';
const requiredStills = [
  ['hero', 'pimm50-light-hero.png', true],
  ['capacity', 'pimm50-light-capacity.png', false],
  ['melt-zone', 'pimm50-light-melt-zone.png', false],
  ['heating', 'pimm50-light-heating.png', false],
  ['mold-space', 'pimm50-light-mold-space.png', false],
  ['purchase', 'pimm50-light-purchase.png', true],
];

const pythonProbe = String.raw`
import json, sys
from PIL import Image, ImageChops

entries = json.loads(sys.stdin.read())
results = []
for entry in entries:
    source = Image.open(entry['source']).convert('RGBA')
    promoted = Image.open(entry['target']).convert('RGBA')
    alpha_bbox = promoted.getchannel('A').getbbox()
    if alpha_bbox is None:
        clearance = 0
    else:
        left, top, right, bottom = alpha_bbox
        clearance = min(left, top, promoted.width - right, promoted.height - bottom) / min(promoted.width, promoted.height)
    diff = ImageChops.difference(source, promoted)
    max_channel_delta = max(channel[1] for channel in diff.getextrema())
    results.append({
        'name': entry['name'],
        'source_mode': source.mode,
        'mode': promoted.mode,
        'source_dimensions': [source.width, source.height],
        'dimensions': [promoted.width, promoted.height],
        'alpha_bbox': alpha_bbox,
        'edge_clearance_ratio': clearance,
        'max_channel_delta': max_channel_delta,
    })
print(json.dumps(results))
`;

test('promoted PIMM 50G light-studio stills preserve approved transparent renders', () => {
  const entries = requiredStills.map(([name, sourceName, requiresMachineClearance]) => ({
    name,
    requiresMachineClearance,
    source: path.join(approvedRenderRoot, sourceName),
    target: path.join(root, 'assets', `pimm50-light-studio-${name}.webp`),
  }));

  for (const entry of entries) {
    assert.ok(existsSync(entry.source), `approved source is missing: ${entry.source}`);
    assert.ok(existsSync(entry.target), `promoted asset is missing: ${entry.target}`);
  }

  const probe = spawnSync('python', ['-c', pythonProbe], {
    input: JSON.stringify(entries),
    encoding: 'utf8',
  });
  assert.equal(probe.status, 0, probe.stderr);
  const results = JSON.parse(probe.stdout);

  for (const result of results) {
    assert.equal(result.source_mode, 'RGBA', `${result.name} source must be RGBA`);
    assert.equal(result.mode, 'RGBA', `${result.name} must remain RGBA`);
    assert.deepEqual(result.dimensions, result.source_dimensions, `${result.name} dimensions changed`);
    assert.notEqual(result.alpha_bbox, null, `${result.name} lost alpha bounds`);
    if (requiredStills.find(([name]) => name === result.name)[2]) {
      assert.ok(result.edge_clearance_ratio >= 0.08, `${result.name} needs 8% edge clearance; got ${result.edge_clearance_ratio}`);
    }
    assert.equal(result.max_channel_delta, 0, `${result.name} differs from its approved lossless source`);
  }
});
