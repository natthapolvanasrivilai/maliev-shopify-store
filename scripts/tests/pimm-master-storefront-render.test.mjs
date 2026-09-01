import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const rendererPath = new URL('../blender/pimm_production/blender_master_storefront_render.py', import.meta.url);
const renderer = await readFile(rendererPath, 'utf8');

test('master storefront renderer accepts only the two authoritative machine masters', () => {
  assert.match(renderer, /"30G": "PIMM-30G-MASTER\.blend"/);
  assert.match(renderer, /"50G": "PIMM-50G-MASTER\.blend"/);
  assert.match(renderer, /EXPECTED_OBJECT_COUNT = 556/);
  assert.match(renderer, /PIMM_PUBLISHED/);
  assert.match(renderer, /FOOT_TOLERANCE = 0\.0002/);
});

test('master storefront renderer creates a new isolated release family', () => {
  assert.match(renderer, /RELEASE_ID = "pimm-master-20260901-r05"/);
  assert.match(renderer, /SHOT_NAMES = \("hero", "overview", "controls", "tooling", "configuration"\)/);
  assert.doesNotMatch(renderer, /pimm30-v\d|light-studio|red-stage|editorial-concepts|pimm-machine-/i);
});

test('master storefront renderer never saves or opens a legacy Blender scene', () => {
  assert.doesNotMatch(renderer, /save_as_mainfile|open_mainfile|\.blend1|shared-templates|scenes[\\/]/i);
  assert.match(renderer, /refusing to overwrite storefront render/);
  assert.match(renderer, /bpy\.ops\.render\.render\(write_still=True\)/);
});

test('master storefront renderer uses the locked physical studio and photographic camera contract', () => {
  assert.match(renderer, /studio_kontrast_04_4k\.exr/);
  assert.match(renderer, /HDRI_SHA256 = "9A982ADE8702402A895F3297BF3CB652CB6F9C8C9CCCA961D2C7603107094A06"/);
  assert.match(renderer, /scene\.render\.engine = "CYCLES"/);
  assert.match(renderer, /data\.type = "PERSP"/);
  assert.match(renderer, /data\.dof\.use_dof = True/);
  assert.match(renderer, /data\.dof\.aperture_fstop = fstop/);
  assert.match(renderer, /PIMM_WHITE_CYCLORAMA/);
  assert.match(renderer, /CYCLORAMA_GROUND_EXTENT_MULTIPLIER = 100\.0/);
  assert.match(renderer, /y_front = center\[1\] - extent \* CYCLORAMA_GROUND_EXTENT_MULTIPLIER/);
  assert.match(renderer, /half_width = extent \* CYCLORAMA_GROUND_EXTENT_MULTIPLIER/);
  assert.match(renderer, /NEGATIVE_FILL_LEFT/);
  assert.match(renderer, /CompositorNodeLensdist/);
  assert.match(renderer, /CompositorNodeGlare/);
});

test('tooling shot looks down at the M10 threaded base plate instead of the injection tube', () => {
  assert.match(
    renderer,
    /elif shot == "tooling":\s+aspect = \(resolution, int\(resolution \* 0\.78\)\)\s+target_z, lens, fstop = height \* 0\.04, 105\.0, 8\.0\s+camera_offset = \(0\.0, -1\.30, 0\.65\)/,
  );
});
