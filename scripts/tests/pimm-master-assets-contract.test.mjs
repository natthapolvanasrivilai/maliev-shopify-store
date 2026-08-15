import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();
const manifestBuilder = path.join(root, 'scripts', 'blender', 'master_assets', 'pimm_step_manifest.py');
const requirements = path.join(root, 'scripts', 'blender', 'master_assets', 'requirements-step.txt');
const materialBuilder = path.join(root, 'scripts', 'blender', 'master_assets', 'pimm_material_library.py');
const masterBuilder = path.join(root, 'scripts', 'blender', 'master_assets', 'pimm_master_builder.py');
const masterAudit = path.join(root, 'scripts', 'blender', 'master_assets', 'pimm_master_audit.py');
const legacyInventory = path.join(root, 'scripts', 'blender', 'master_assets', 'pimm_legacy_inventory.py');
const partNameSync = path.join(root, 'scripts', 'blender', 'master_assets', 'pimm_part_name_sync.py');
const assetRoot = 'M:\\30_Products\\00_Pneumatic Injection Molding Machine\\blender-product-renders';

test('STEP manifest pipeline pins the CAD runtime and authoritative sources', () => {
  assert.equal(fs.readFileSync(requirements, 'utf8').trim(), 'cadquery-ocp==7.9.3.1.1');
  const source = fs.readFileSync(manifestBuilder, 'utf8');
  assert.match(source, /D1522BEB526BAF96C0A4707E0AC296F660BBC7339E60FE4A88931E1D5203E5CE/);
  assert.match(source, /405534913F74ABB1E801577EABDA1BC1F7C8C5FFC37FEB84D2D2EF15DF2BF455/);
  assert.match(source, /STEPCAFControl_Reader/);
  assert.match(source, /XCAFDoc_DocumentTool/);
});

test('STEP pipeline enumerates and exports individual solids with stable provenance', () => {
  const source = fs.readFileSync(manifestBuilder, 'utf8');
  assert.match(source, /TopAbs_SOLID/);
  assert.match(source, /stable_solid_id/);
  assert.match(source, /geometry_signature/);
  assert.match(source, /interchange_path/);
  assert.doesNotMatch(source, /\.obj\b|import_obj|OBJ canonical/i);
});

test('shared material library keeps physical materials distinct and branding local', () => {
  const source = fs.readFileSync(materialBuilder, 'utf8');
  for (const material of [
    'UNASSIGNED',
    'CNC_MILLED_ALUMINUM',
    'DIE_CAST_ALUMINUM',
    'SATIN_SHEET_ALUMINUM',
    'POLISHED_STAINLESS',
    'NICKEL_PLATED_SHAFT',
    'BLACK_OXIDE_STEEL',
    'BRASS',
    'BLACK_POWDERCOAT',
    'RUBBER_BLACK',
    'PNEUMATIC_TUBE_BLUE',
    'ENGINEERING_PLASTIC',
    'STAINLESS_BRUSHED_HAIRLINE',
    'ALUMINUM_SATIN_EXTRUSION',
    'PINK_POWDERCOAT_STEEL',
    'NYLON_PA6',
    'PEEK',
    'ASA_3D_PRINT_0_2MM',
    'WHITE_TEXTILE_CABLE',
    'STEEL_BRAIDED_CABLE',
    'STAINLESS_STEEL_FASTENERS',
    'STEEL_SATIN',
    'STEEL_HEAT_OXIDIZED_BLUEBLACK',
    'GREEN_ILLUMINATED_NUMERIC',
    'RED_ILLUMINATED_NUMERIC',
    'RED_ILLUMINATED_TRANSPARENT',
  ]) {
    assert.match(source, new RegExp(`"${material}"`));
  }
  assert.match(source, /pimm_material_scope.*shared/s);
  assert.match(source, /machine-local material cannot enter shared library/);
  assert.match(source, /cast_grain/);
  assert.match(source, /machined_fine/);
  assert.match(source, /brushed_linear/);
  assert.match(source, /emission_strength/);
  assert.match(source, /transmission/);
});

test('machine masters preserve one selectable object per solid and block publication', () => {
  const source = fs.readFileSync(masterBuilder, 'utf8');
  assert.match(source, /PIMM_WORKING/);
  assert.match(source, /PIMM_PUBLISHED/);
  assert.match(source, /pimm_stable_id/);
  assert.match(source, /pimm_geometry_signature/);
  assert.match(source, /pimm_part_name/);
  assert.match(source, /pimm_material_state/);
  assert.match(source, /pimm_part_name.*solid\["original_name"\]/s);
  assert.match(source, /PIMM_UNASSIGNED/);
  assert.match(source, /SOURCE_TO_BLENDER_ROTATION_X\s*=\s*-math\.pi\s*\/\s*2\.0/);
  assert.match(source, /SOURCE_TO_BLENDER_SCALE\s*=\s*0\.01/);
  assert.match(source, /MILLIMETERS/);
  assert.match(source, /BLENDER_SCENE_SCALE_LENGTH\s*=\s*0\.001/);
  assert.match(source, /scene\.unit_settings\.scale_length\s*=\s*BLENDER_SCENE_SCALE_LENGTH/);
  assert.match(source, /imported \{len\(meshes\)\} mesh objects; expected 1/);
  assert.doesNotMatch(source, /bpy\.ops\.object\.join|join_by_material|merge_by_distance/);
});

test('part-name sync initializes labels without overwriting manual edits by default', () => {
  const source = fs.readFileSync(partNameSync, 'utf8');
  assert.match(source, /if current and not force/);
  assert.match(source, /current != original\.strip\(\)/);
  assert.match(source, /obj\["pimm_part_name"\] = original/);
  assert.match(source, /--force/);
  assert.match(source, /remaining_blank/);
});

test('master audit is read-only and manual material assignments are authoritative', () => {
  const source = fs.readFileSync(masterAudit, 'utf8');
  assert.match(source, /mode.*working.*publish/s);
  assert.match(source, /local copy of shared material/);
  assert.match(source, /machine-local semantic marked shared/);
  assert.match(source, /objects remain unassigned/);
  assert.match(source, /pimm_source_to_blender_scale/);
  assert.match(source, /BLENDER_LENGTH_UNIT/);
  assert.match(source, /machine master changed during read-only audit/);
  assert.doesNotMatch(source, /save_as_mainfile|save_mainfile|bpy\.ops\.object\.join/);
});

test('legacy inventory is non-destructive and accounts for every project', () => {
  const source = fs.readFileSync(legacyInventory, 'utf8');
  assert.match(source, /keep-authoritative/);
  assert.match(source, /migrate-scene/);
  assert.match(source, /archive-after-validation/);
  assert.match(source, /No file was moved, renamed, or deleted/);
  assert.doesNotMatch(source, /shutil\.(move|rmtree)|Path\([^)]*\)\.unlink|os\.remove/);
});

test('generated external handoff artifacts have exact manifest-to-master parity', () => {
  for (const machine of ['30G', '50G']) {
    const manifestPath = path.join(assetRoot, 'manifests', `PIMM-${machine}-import-manifest.json`);
    const auditPath = path.join(assetRoot, 'manifests', `PIMM-${machine}-material-audit.json`);
    const masterPath = path.join(assetRoot, 'masters', `PIMM-${machine}-MASTER.blend`);
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    const audit = JSON.parse(fs.readFileSync(auditPath, 'utf8'));
    assert.equal(manifest.summary.solid_count, 478);
    assert.equal(manifest.summary.non_solid_product_count, 4);
    assert.equal(new Set(manifest.solids.map((solid) => solid.stable_id)).size, 478);
    assert.equal(manifest.solids.every((solid) => fs.statSync(solid.interchange_path).size > 0), true);
    assert.equal(audit.object_count, 478);
    assert.equal(audit.unique_id_count, 478);
    assert.equal(audit.unassigned_ids.length, 478);
    assert.deepEqual(audit.errors, []);
    assert.equal(audit.publishable, false);
    assert.equal(audit.source_ok, true);
    assert.equal(audit.master_unchanged, true);
    assert.ok(fs.statSync(masterPath).size > 1_000_000);
  }

  const inventory = JSON.parse(
    fs.readFileSync(path.join(assetRoot, 'manifests', 'blender-project-inventory.json'), 'utf8'),
  );
  assert.equal(inventory.summary.project_count, inventory.projects.length);
  assert.equal(inventory.projects.length, 77);
  assert.equal(inventory.projects.every((project) => project.proposed_disposition !== 'delete'), true);
  assert.equal(inventory.projects.every((project) => project.blender?.inspection_error == null), true);
});
