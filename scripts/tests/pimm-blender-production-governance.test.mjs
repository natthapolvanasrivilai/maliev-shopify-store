import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const docRoot = path.join(repoRoot, 'docs', 'pimm-blender-governance');
const assetRoot = String.raw`M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders`;
const linkedTemplate = path.join(
  assetRoot,
  'scenes',
  'shared-templates',
  'pimm-linked-studio-template.blend',
);

test('canonical governance files map only to the exact external workspace paths', () => {
  const expectedMappings = [
    ['docs/pimm-blender-governance/AGENTS.md', `${assetRoot}\\AGENTS.md`],
    ['docs/pimm-blender-governance/README.md', `${assetRoot}\\README.md`],
    ['docs/pimm-blender-governance/animation-rigging.md', `${assetRoot}\\docs\\animation-rigging.md`],
    ['docs/pimm-blender-governance/lighting-and-cameras.md', `${assetRoot}\\docs\\lighting-and-cameras.md`],
    ['docs/pimm-blender-governance/machine-operation-30g.md', `${assetRoot}\\docs\\machine-operation-30g.md`],
    ['docs/pimm-blender-governance/machine-operation-50g.md', `${assetRoot}\\docs\\machine-operation-50g.md`],
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

test('free tool lock lists only the pinned local production toolchain', () => {
  const lockPath = path.join(assetRoot, 'manifests', 'free-tools-lock.json');
  const lock = JSON.parse(fs.readFileSync(lockPath, 'utf8'));
  const serialized = JSON.stringify(lock).toLowerCase();

  assert.deepEqual(
    lock.tools.map((tool) => tool.id).sort(),
    ['blender', 'blender-mcp', 'pillow', 'python'],
  );
  for (const tool of lock.tools) {
    assert.equal(tool.execution, 'local');
    assert.match(tool.version, /\S/);
    assert.match(tool.license, /\S/);
    assert.match(tool.path, /^(?:[A-Z]:\\|\\\\)/i);
    assert.match(tool.sha256, /^[A-F0-9]{64}$/);
  }
  assert.doesNotMatch(serialized, /subscription|paid|cloud|https?:\/\//);
  assert.equal(lock.schema, 'pimm-free-tools-lock/v1');
  assert.deepEqual(Object.keys(lock).sort(), ['license_evidence', 'schema', 'tools']);
  assert.deepEqual(Object.keys(lock.license_evidence), ['blender-mcp']);
  assert.deepEqual(Object.keys(lock.license_evidence['blender-mcp']).sort(), ['path', 'sha256']);
});

test('free tool lock rejects an injected network endpoint', () => {
  const lockPath = path.join(assetRoot, 'manifests', 'free-tools-lock.json');
  const lock = JSON.parse(fs.readFileSync(lockPath, 'utf8'));
  lock.tools[0].endpoint = 'http://127.0.0.1:8000';
  const validationProgram = [
    'import json, sys',
    'from scripts.blender.pimm_production.tool_policy import validate_tool_lock',
    'print(json.dumps(validate_tool_lock(json.loads(sys.stdin.read()))))',
  ].join('\n');
  const result = execFileSync('python', ['-c', validationProgram], {
    cwd: repoRoot,
    encoding: 'utf8',
    input: JSON.stringify(lock),
  });

  assert.match(result, /network-bearing field/);
});

test('production Python requirements pin the approved Pillow release', () => {
  const requirements = fs.readFileSync(
    path.join(repoRoot, 'scripts', 'blender', 'pimm_production', 'requirements-production.txt'),
    'utf8',
  );
  assert.equal(requirements, 'Pillow==12.2.0\n');
});

test('machine contracts retain their separate physical controller values and blocked animation state', () => {
  const contractRoot = path.join(repoRoot, 'scripts', 'blender', 'pimm_production', 'contracts', 'machines');
  const thirty = JSON.parse(fs.readFileSync(path.join(contractRoot, '30g.json'), 'utf8'));
  const fifty = JSON.parse(fs.readFileSync(path.join(contractRoot, '50g.json'), 'utf8'));

  assert.deepEqual(thirty.controller.display_values, ['300', '300']);
  assert.deepEqual(fifty.controller.display_values, ['350', '350']);
  for (const contract of [thirty, fifty]) {
    assert.equal(contract.schema_version, 1);
    assert.equal(contract.controller.geometry_mode, 'physical-seven-segment-mesh');
    assert.equal(contract.controller.allow_font, false);
    assert.equal(contract.controller.allow_image_overlay, false);
    assert.equal(contract.controller.inactive_segments_required, true);
    assert.equal(contract.animation.status, 'blocked_pending_owner_motion_map');
    assert.deepEqual(contract.animation.allowed_controls, []);
  }
});

test('manual material approval gate leaves the production linked template absent', () => {
  assert.equal(fs.existsSync(linkedTemplate), false);
});
