import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const docRoot = path.join(repoRoot, 'docs', 'pimm-blender-governance');
const assetRoot = String.raw`M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders`;

test('canonical governance files map only to the exact external workspace paths', () => {
  const expectedMappings = [
    ['docs/pimm-blender-governance/AGENTS.md', `${assetRoot}\\AGENTS.md`],
    ['docs/pimm-blender-governance/README.md', `${assetRoot}\\README.md`],
    ['docs/pimm-blender-governance/animation-rigging.md', `${assetRoot}\\docs\\animation-rigging.md`],
    ['docs/pimm-blender-governance/lighting-and-cameras.md', `${assetRoot}\\docs\\lighting-and-cameras.md`],
    ['docs/pimm-blender-governance/material-authoring.md', `${assetRoot}\\docs\\material-authoring.md`],
    ['docs/pimm-blender-governance/rendering-and-approval.md', `${assetRoot}\\docs\\rendering-and-approval.md`],
  ];

  const mappingProgram = [
    'import json',
    'from pathlib import Path',
    'from scripts.blender.pimm_production.workspace_docs import canonical_workspace_docs',
    'repository_root = Path.cwd()',
    'mapping = canonical_workspace_docs(repository_root)',
    'rows = sorted((source.relative_to(repository_root).as_posix(), str(destination)) for source, destination in mapping.items())',
    'print(json.dumps(rows))',
  ].join('\n');
  const actualMappings = JSON.parse(
    execFileSync('python', ['-c', mappingProgram], {
      cwd: repoRoot,
      encoding: 'utf8',
    }),
  );

  assert.deepEqual(actualMappings, expectedMappings);
});

test('approved local tool section excludes paid and cloud enhancers', () => {
  const agents = fs.readFileSync(path.join(docRoot, 'AGENTS.md'), 'utf8');
  const allowedTools = agents.match(/## Approved local tools\n([\s\S]*?)(?=\n## |$)/)?.[1] ?? '';

  assert.match(allowedTools, /Blender 5\.2/);
  assert.match(allowedTools, /BlenderMCP/);
  assert.doesNotMatch(allowedTools, /paid|subscription|cloud|upscal|generative/i);
});
