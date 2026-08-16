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

test('Task 5 fixture proof generations never write into the production proof tree', () => {
  const fixtureGenerationIds = [
    'proof-20260815T153000Z-a1b2c3d',
    'proof-20260815T153001Z-b2c3d4e',
  ];

  for (const generationId of fixtureGenerationIds) {
    assert.equal(
      fs.existsSync(path.join(assetRoot, 'renders', 'proofs', generationId)),
      false,
      `${generationId} must remain temporary fixture output only`,
    );
  }
});

test('Task 6 fixture approvals fail closed and publish only immutable release manifests', () => {
  const program = [
    'from pathlib import Path',
    'import json',
    'from tempfile import TemporaryDirectory',
    'from unittest.mock import patch',
    'import scripts.blender.pimm_production.approval_manifest as approval_module',
    'import scripts.blender.pimm_production.release_manifest as release_module',
    'from scripts.blender.pimm_production.blender_final_render import authorize_final_render',
    'from scripts.blender.pimm_production.release_manifest import build_release_manifest',
    'from scripts.blender.pimm_production.tests.test_approval_release import APPROVED_COMPONENT_MACHINE_FIXTURE, RELEASE_ID, _float_exr_bytes, _structured_component_pixels, write_release_output_fixture',
    'fixture_png, fixture_masks = _structured_component_pixels()',
    'fixture_regeneration = (fixture_png, _float_exr_bytes(64, 48), fixture_masks)',
    "with patch.object(approval_module, '_machine_contract_path', return_value=APPROVED_COMPONENT_MACHINE_FIXTURE), patch.object(release_module, '_regenerate_component_evidence', return_value=fixture_regeneration):",
    '    with TemporaryDirectory() as root_text:',
    '        root = Path(root_text)',
    "        output = write_release_output_fixture(root, 'proof-20260815T153000Z-a1b2c3d')",
    "        payload = json.loads(output.read_text(encoding='utf-8'))",
    "        authorize_final_render(Path(payload['approval_path']), Path(payload['authorized_final_contract_path']))",
    '        print(build_release_manifest(RELEASE_ID, [output]).name)',
  ].join('\n');
  const result = execFileSync('python', ['-c', program], {
    cwd: repoRoot,
    encoding: 'utf8',
  });

  assert.equal(result.trim(), 'release-manifest.json');
});

test('Task 7 inventory schema accounts once for blend recovery and nested render assets', () => {
  const program = [
    'import json',
    'from pathlib import Path',
    'from tempfile import TemporaryDirectory',
    'from scripts.blender.master_assets.pimm_legacy_inventory import inventory_workspace, inventory_payload',
    'with TemporaryDirectory() as root_text:',
    '    root = Path(root_text)',
    "    for relative in ('legacy/PIMM-old.blend1', 'renders/proofs/gen-a/nested/hero.png', 'archive/manifests/consumer-graph.json', 'manifests/blender-project-inventory.json', 'manifests/render-generation-inventory.json', 'manifests/consumer-graph.json', 'manifests/blender-project-migration-report.md'):",
    '        path = root / relative',
    '        path.parent.mkdir(parents=True, exist_ok=True)',
    "        path.write_bytes(b'fixture')",
    '    print(json.dumps(inventory_payload(inventory_workspace(root))))',
  ].join('\n');
  const payload = JSON.parse(execFileSync('python', ['-c', program], {
    cwd: repoRoot,
    encoding: 'utf8',
  }));

  assert.equal(payload.schema, 'pimm-asset-inventory/v2');
  assert.deepEqual(payload.discovered_paths, [
    'archive/manifests/consumer-graph.json',
    'legacy/PIMM-old.blend1',
    'renders/proofs/gen-a/nested/hero.png',
  ]);
  assert.deepEqual(payload.records.map((record) => record.path), payload.discovered_paths);
  assert.deepEqual(payload.generated_path_policy, {
    excluded_paths: [
      'manifests/blender-project-inventory.json',
      'manifests/blender-project-migration-report.md',
      'manifests/consumer-graph.json',
      'manifests/render-generation-inventory.json',
    ],
    rule: 'exact-path exclusion; generated children are hash-bound by the inventory authority',
  });
  assert.equal(payload.records.some((record) => record.proposed_disposition === 'delete'), false);
});

test('Task 7 consumer graph CLI is diagnostic-only and cannot publish outputs', () => {
  const program = [
    'import json',
    'import subprocess',
    'import sys',
    'from pathlib import Path',
    'from tempfile import TemporaryDirectory',
    'from scripts.blender.master_assets.pimm_legacy_inventory import AssetRecord, InventoryManifest, inventory_payload',
    'with TemporaryDirectory() as root_text:',
    '    root = Path(root_text)',
    "    asset_root = root / 'assets'",
    '    asset_root.mkdir()',
    "    record = AssetRecord(path='legacy/example.blend1', kind='blend-recovery', size=7, mtime_ns=1, sha256='0' * 64)",
    "    inventory = root / 'inventory.json'",
    "    inventory.write_text(json.dumps(inventory_payload(InventoryManifest((record,), (record.path,), str(asset_root)))), encoding='utf-8')",
    "    results = []",
    "    for destination in (root / 'outside.json', asset_root / 'manifests' / 'consumer-graph.json'):",
    "        destination.parent.mkdir(parents=True, exist_ok=True)",
    "        destination.write_text('sentinel', encoding='utf-8')",
    "        process = subprocess.run([sys.executable, '-m', 'scripts.blender.pimm_production.consumer_graph', '--inventory', str(inventory), '--repo-root', str(root), '--asset-root', str(asset_root), '--output', str(destination)], cwd=Path.cwd(), capture_output=True, text=True)",
    "        results.append({'returncode': process.returncode, 'destination': destination.read_text(encoding='utf-8')})",
    "    print(json.dumps(results))",
  ].join('\n');
  const result = JSON.parse(execFileSync('python', ['-c', program], {
    cwd: repoRoot,
    encoding: 'utf8',
  }));

  assert.equal(result.length, 2);
  for (const attempt of result) {
    assert.notEqual(attempt.returncode, 0);
    assert.equal(attempt.destination, 'sentinel');
  }
});
