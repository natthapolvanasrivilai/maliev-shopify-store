import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../', import.meta.url);

test('plunger animation keeps a usable composition from phone through narrow tablet', async () => {
  const styles = await readFile(new URL('assets/maliev-pimm-30g-hero.css', root), 'utf8');

  assert.match(styles, /@media \(min-width: 560px\) and \(max-width: 749px\)[\s\S]*grid-template-columns: minmax\(0, \.8fr\) minmax\(0, 1\.2fr\);/);
  assert.match(styles, /@media \(min-width: 560px\) and \(max-width: 749px\)[\s\S]*\.pimm-bento__tile--plunger\s*\{[\s\S]*aspect-ratio: 1;/);
  assert.match(styles, /@media \(max-width: 559px\)[\s\S]*grid-template-areas: "controls controls" "capacity tooling" "temperature temperature" "air-pressure air-pressure" "plunger plunger" "configuration configuration";/);
  assert.match(styles, /@media \(max-width: 559px\)[\s\S]*\.pimm-bento__tile--plunger\s*\{[\s\S]*aspect-ratio: 16 \/ 11;[\s\S]*min-height: clamp\(220px, 65vw, 340px\);/);
  assert.match(styles, /@media \(max-width: 559px\)[\s\S]*\.pimm-bento__tile--plunger \.pimm-bento__copy\s*\{[\s\S]*width: 47%;/);
});
