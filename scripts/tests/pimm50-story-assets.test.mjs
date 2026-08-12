import assert from 'node:assert/strict';
import { access, readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';

const root = path.resolve(import.meta.dirname, '../..');
const chapters = ['overview', 'capacity', 'melt-zone', 'heating', 'mold-space', 'comparison', 'purchase'];

test('optimized Blender story assets exist and remain bounded', async () => {
  for (const chapter of chapters) {
    for (const layout of ['desktop', 'mobile']) {
      const file = path.join(root, 'assets', `pimm50-story-${chapter}-${layout}.webp`);
      await access(file);
      const details = await stat(file);
      assert.ok(details.size > 20_000, `${path.basename(file)} is unexpectedly empty`);
      assert.ok(details.size < 900_000, `${path.basename(file)} exceeds the delivery ceiling`);
      const header = await readFile(file, { length: 12 });
      assert.equal(header.subarray(0, 4).toString(), 'RIFF');
      assert.equal(header.subarray(8, 12).toString(), 'WEBP');
    }
  }
});
