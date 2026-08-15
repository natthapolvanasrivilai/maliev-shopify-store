import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const docRoot = path.join(repoRoot, 'docs', 'pimm-blender-governance');
const assetRoot = String.raw`M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders`;

test('canonical governance files map only to the exact external workspace paths', () => {
  const expectedCanonicalFiles = [
    'AGENTS.md',
    'README.md',
    'material-authoring.md',
    'lighting-and-cameras.md',
    'animation-rigging.md',
    'rendering-and-approval.md',
  ];

  for (const name of expectedCanonicalFiles) {
    assert.equal(fs.existsSync(path.join(docRoot, name)), true, `missing canonical ${name}`);
  }

  const installer = fs.readFileSync(
    path.join(repoRoot, 'scripts', 'blender', 'pimm_production', 'workspace_docs.py'),
    'utf8',
  );
  const paths = fs.readFileSync(
    path.join(repoRoot, 'scripts', 'blender', 'pimm_production', 'paths.py'),
    'utf8',
  );
  assert.match(installer, /ASSET_ROOT/);
  assert.match(installer, /AGENTS\.md/);
  assert.match(installer, /README\.md/);
  assert.match(installer, /ASSET_ROOT \/ "docs"/);
  assert.match(paths, new RegExp(assetRoot.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
});

test('approved local tool section excludes paid and cloud enhancers', () => {
  const agents = fs.readFileSync(path.join(docRoot, 'AGENTS.md'), 'utf8');
  const allowedTools = agents.match(/## Approved local tools\n([\s\S]*?)(?=\n## |$)/)?.[1] ?? '';

  assert.match(allowedTools, /Blender 5\.2/);
  assert.match(allowedTools, /BlenderMCP/);
  assert.doesNotMatch(allowedTools, /paid|subscription|cloud|upscal|generative/i);
});
