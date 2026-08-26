import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const docRoot = path.join(repoRoot, 'docs', 'pimm-blender-governance');
const assetRoot = String.raw`M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders`;
const governanceRoot = String.raw`M:\30_Products\00_Pneumatic Injection Molding Machine\blender-product-renders-governance`;
const archivePlanPath = path.join(
  governanceRoot,
  'manifests',
  'archive-plans',
  'legacy-recovery-files-01.json',
);
const archivePlanSha256 = '80484BBE3E420987407306E908BB9E0AF7E42B785396855E2C72D74224DE608E';
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

test('Task 8 production CLI rejects caller-selected authority manifests', () => {
  const archiveSource = fs.readFileSync(
    path.join(repoRoot, 'scripts', 'blender', 'pimm_production', 'archive_plan.py'),
    'utf8',
  );
  assert.match(archiveSource, /ARCHIVE_GOVERNANCE_ROOT = ASSET_ROOT\.parent \/ f"\{ASSET_ROOT\.name\}-governance"/);
  assert.match(archiveSource, /ARCHIVE_PLAN_ROOT = ARCHIVE_GOVERNANCE_ROOT \/ "manifests" \/ "archive-plans"/);
  const program = [
    'import hashlib',
    'import json',
    'import subprocess',
    'import sys',
    'from pathlib import Path',
    'from tempfile import TemporaryDirectory',
    'from scripts.blender.master_assets.pimm_legacy_inventory import AssetRecord, InventoryManifest, inventory_payload',
    'from scripts.blender.pimm_production.consumer_graph import ConsumerGraph, consumer_graph_payload',
    'with TemporaryDirectory() as root_text:',
    '    root = Path(root_text)',
    "    asset_root = root / 'blender-product-renders'",
    "    source = asset_root / 'legacy' / 'old.blend1'",
    "    replacement = asset_root / 'legacy' / 'old.blend'",
    '    source.parent.mkdir(parents=True)',
    "    source.write_bytes(b'recovery')",
    "    replacement.write_bytes(b'current')",
    '    def record(path, kind, disposition):',
    '        status = path.stat()',
    "        return AssetRecord(path=path.relative_to(asset_root).as_posix(), size=status.st_size, mtime_ns=status.st_mtime_ns, sha256=hashlib.sha256(path.read_bytes()).hexdigest().upper(), kind=kind, proposed_disposition=disposition, filesystem_identity=(status.st_dev, status.st_ino, status.st_ctime_ns, status.st_size))",
    "    recovery = record(source, 'blend-recovery', 'pending-archive')",
    "    current = record(replacement, 'blend-project', 'unresolved')",
    '    inventory = InventoryManifest((recovery, current), (recovery.path, current.path), str(asset_root.resolve()), (asset_root.stat().st_dev, asset_root.stat().st_ino))',
    '    graph = ConsumerGraph(consumers={recovery.path: (), current.path: ()}, producers={recovery.path: (), current.path: ()})',
    "    inventory_path = root / 'inventory.json'",
    "    graph_path = root / 'graph.json'",
    "    output = root / 'plan.json'",
    "    inventory_path.write_text(json.dumps(inventory_payload(inventory)), encoding='utf-8')",
    "    graph_path.write_text(json.dumps(consumer_graph_payload(graph)), encoding='utf-8')",
    '    before = source.read_bytes()',
    "    process = subprocess.run([sys.executable, 'scripts/blender/pimm_production/archive_plan.py', '--batch-id', 'node-plan-only', '--inventory', str(inventory_path), '--graph', str(graph_path), '--output', str(output)], cwd=Path.cwd(), capture_output=True, text=True)",
    "    payload = json.loads(output.read_text(encoding='utf-8')) if output.exists() else {}",
    "    print(json.dumps({'returncode': process.returncode, 'stderr': process.stderr, 'stdout': process.stdout, 'source_unchanged': source.read_bytes() == before, 'destination_exists': Path(payload['items'][0]['destination']).exists() if payload.get('items') else False, 'item_count': payload.get('summary', {}).get('item_count')}))",
  ].join('\n');
  const result = JSON.parse(execFileSync('python', ['-c', program], {
    cwd: repoRoot,
    encoding: 'utf8',
  }));

  assert.notEqual(result.returncode, 0);
  assert.match(result.stderr, /unrecognized arguments|canonical Task 7 authority/i);
  assert.equal(result.item_count, null);
  assert.equal(result.source_unchanged, true);
  assert.equal(result.destination_exists, false);
});

test('Task 8 governing plan and design bind archive plans to the sibling governance root', () => {
  const governingFiles = [
    path.join(repoRoot, 'docs', 'superpowers', 'plans', '2026-08-15-pimm-blender-production-governance.md'),
    path.join(repoRoot, 'docs', 'superpowers', 'specs', '2026-08-15-pimm-blender-production-governance-design.md'),
  ];
  const expected = 'M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders-governance\\manifests\\archive-plans\\<batch-id>.json';
  for (const file of governingFiles) {
    assert.match(fs.readFileSync(file, 'utf8'), new RegExp(expected.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
});

test('Task 9 fail-closed lifecycle behaviors pass through their public contracts', () => {
  const cases = [
    'scripts.blender.pimm_production.tests.test_scene_contract.SceneContractTests.test_private_mesh_and_localized_product_material_fail',
    'scripts.blender.pimm_production.tests.test_proof_contract.ProofContractTests.test_contract_rejects_cost_path_generation_and_hash_mutations',
    'scripts.blender.pimm_production.tests.test_approval_release.ApprovalReleaseTests.test_owner_and_shot_are_required_for_an_approval',
    'scripts.blender.pimm_production.tests.test_approval_release.ApprovalReleaseTests.test_atomic_json_never_exposes_a_partial_final_path',
    'scripts.blender.pimm_production.tests.test_approval_release.ApprovalReleaseTests.test_release_rejects_duplicate_assets_missing_exr_and_proof_paths',
    'scripts.blender.pimm_production.tests.test_consumer_graph.ConsumerGraphTests.test_active_consumer_prevents_archive',
    'scripts.blender.pimm_production.tests.test_archive_plan.ArchivePlanTests.test_restore_recreates_original_path_and_hash',
    'scripts.blender.pimm_production.tests.test_archive_plan.ArchivePlanTests.test_plan_containing_delete_is_rejected_before_mutation',
  ];

  assert.doesNotThrow(() => execFileSync('python', ['-m', 'unittest', ...cases, '-q'], {
    cwd: repoRoot,
    encoding: 'utf8',
    timeout: 180_000,
  }));
});

test('Task 9 read-only handoff report matches the complete current external authority', () => {
  for (const [canonical, installed] of [
    [path.join(docRoot, 'AGENTS.md'), path.join(assetRoot, 'AGENTS.md')],
    [path.join(docRoot, 'README.md'), path.join(assetRoot, 'README.md')],
  ]) {
    const canonicalBytes = fs.readFileSync(canonical);
    const installedBytes = fs.readFileSync(installed);
    assert.equal(createHash('sha256').update(installedBytes).digest('hex').toUpperCase(), createHash('sha256').update(canonicalBytes).digest('hex').toUpperCase());
    assert.deepEqual(installedBytes, canonicalBytes);
  }

  const manifestRoot = path.join(assetRoot, 'manifests');
  const inventory = JSON.parse(fs.readFileSync(path.join(manifestRoot, 'blender-project-inventory.json'), 'utf8'));
  const renderInventory = JSON.parse(fs.readFileSync(path.join(manifestRoot, 'render-generation-inventory.json'), 'utf8'));
  const graph = JSON.parse(fs.readFileSync(path.join(manifestRoot, 'consumer-graph.json'), 'utf8'));
  assert.equal(inventory.schema, 'pimm-asset-inventory/v2');
  assert.equal(inventory.publication_id, 'bc320a119a214ec5907288ac78412e06');
  assert.equal(inventory.records.length, 5434);
  assert.equal(inventory.discovered_paths.length, 5434);
  assert.equal(inventory.summary.bytes, 23278163353);
  assert.equal(inventory.records.length, inventory.discovered_paths.length);
  assert.equal(inventory.summary.record_count, inventory.records.length);
  assert.deepEqual(inventory.records.map((record) => record.path), inventory.discovered_paths);
  assert.equal(new Set(inventory.discovered_paths).size, inventory.discovered_paths.length);
  assert.equal(Object.keys(graph.ambiguous_references).length, 87);
  assert.equal(Object.keys(graph.unresolved_references).length, 400);
  assert.equal(inventory.publication_id, graph.publication_id);
  assert.equal(inventory.publication_id, renderInventory.publication_id);
  assert.deepEqual(renderInventory.releases, {});

  const verifierProgram = [
    'from scripts.blender.master_assets.pimm_legacy_inventory import ASSET_ROOT, verify_published_outputs',
    'authority = verify_published_outputs(ASSET_ROOT)',
    "print('PUBLISHED_AUTHORITY', authority['publication_id'], len(authority['records']), len(authority['discovered_paths']))",
  ].join('\n');
  const verifiedAuthority = execFileSync('python', ['-c', verifierProgram], {
    cwd: repoRoot,
    encoding: 'utf8',
    timeout: 2_400_000,
  }).trim();
  assert.equal(verifiedAuthority, 'PUBLISHED_AUTHORITY bc320a119a214ec5907288ac78412e06 5434 5434');

  const planBytes = fs.readFileSync(archivePlanPath);
  const plan = JSON.parse(planBytes);
  assert.equal(createHash('sha256').update(planBytes).digest('hex').toUpperCase(), archivePlanSha256);
  assert.equal(plan.summary.item_count, 0);
  assert.equal(plan.summary.total_bytes, 0);
  assert.deepEqual(plan.items, []);
  assert.equal(plan.summary.operation, 'reversible-archive-only');
  assert.equal(fs.existsSync(plan.summary.destination), false);
  assert.equal(fs.existsSync(path.join(governanceRoot, 'manifests', 'archive-approvals')), false);
  assert.equal(fs.existsSync(path.join(assetRoot, 'manifests', 'archive-approvals')), false);

  const report = fs.readFileSync(path.join(docRoot, 'rendering-and-approval.md'), 'utf8');
  for (const required of [
    '## Task 9 read-only governance report',
    'blocked_manual_material_approval',
    archivePlanSha256,
    'BlenderMCP connector was unavailable',
    'No permanent deletion occurred',
    '5,434',
    '23,278,163,353',
  ]) {
    assert.match(report, new RegExp(required.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  }
});

test('Task 9 plan classifies combined Node failures as external handoff drift', () => {
  const plan = fs.readFileSync(
    path.join(repoRoot, 'docs', 'superpowers', 'plans', '2026-08-15-pimm-blender-production-governance.md'),
    'utf8',
  );
  assert.match(plan, /external handoff drift/i);
  assert.match(plan, /not (?:a claim that )?all repository gates are green/i);
});
