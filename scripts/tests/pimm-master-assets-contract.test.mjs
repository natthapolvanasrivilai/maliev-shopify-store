import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = process.cwd();
const manifestBuilder = path.join(root, 'scripts', 'blender', 'master_assets', 'pimm_step_manifest.py');
const requirements = path.join(root, 'scripts', 'blender', 'master_assets', 'requirements-step.txt');

test('STEP manifest pipeline pins the CAD runtime and authoritative sources', () => {
  assert.equal(fs.readFileSync(requirements, 'utf8').trim(), 'cadquery-ocp==7.9.3.1.1');
  const source = fs.readFileSync(manifestBuilder, 'utf8');
  assert.match(source, /F8AAA223A79B9FE3BB71470818C2E87591C0DECA9A7B0BC8E09AD4DDB0499295/);
  assert.match(source, /55914B756354C3BDCC522ED439732C9F3F0FBE43F7038A1FFA6045C92ADC1E98/);
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
