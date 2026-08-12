import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const builderUrl = new URL('../blender/create_pimm50_light_studio.py', import.meta.url);

test('builder owns transparent light studio scenes', async () => {
  const script = await readFile(builderUrl, 'utf8');

  assert.match(script, /PIMM-50g-light-studio-v1\.blend/);
  assert.match(script, /PIMM-50g-keynote-reveal-v2-regulator-materials\.blend/);
  assert.match(script, /EXPECTED_MACHINE_OBJECTS\s*=\s*481/);
  assert.match(script, /SOURCE_SHA256\s*=\s*"C19DDA7902BE63A2B28A77D3EF349D17555642399A9589B9A06EFCC05EAB882A"/);
  assert.match(script, /PREFIX\s*=\s*"PIMM50_LIGHT_"/);
  assert.match(script, /film_transparent\s*=\s*True/);
  assert.match(script, /color_mode\s*=\s*"RGBA"/);
  for (const scene of ['HERO', 'CAPACITY', 'MELT_ZONE', 'HEATING', 'MOLD_SPACE', 'PURCHASE']) {
    assert.match(script, new RegExp(scene));
  }
  assert.match(script, /assert_animation_poster_parity/);
  assert.match(script, /PIMM50_LIGHT_STUDIO_SUMMARY_BEGIN/);
  assert.doesNotMatch(script, /save_as_mainfile\(filepath=str\(SOURCE_BLEND\)/);
  assert.doesNotMatch(script, /CompositorNodeImage|bpy\.data\.curves\.new/);
});

test('builder names finite poster and animation outputs explicitly', async () => {
  const script = await readFile(builderUrl, 'utf8');

  assert.match(script, /PIMM50_LIGHT_HERO_ANIMATION/);
  assert.match(script, /PIMM50_LIGHT_HEATING_ANIMATION/);
  assert.match(script, /CONTACT_SHADOW_RADIUS_X\s*=\s*0\.34/);
  assert.match(script, /CONTACT_SHADOW_RADIUS_Y\s*=\s*0\.25/);
  assert.match(script, /assert_finite_alpha_bounds/);
});

test('heating poster is isolated from animated display materials', async () => {
  const script = await readFile(builderUrl, 'utf8');

  assert.match(script, /PIMM50_LIGHT_HEATING_POSTER_MACHINE/);
  assert.match(script, /PIMM50_LIGHT_HEATING_ANIMATION_MACHINE/);
  assert.match(script, /assert_poster_materials_unanimated/);
  assert.match(script, /assert_heating_material_parity_at_final/);
});

test('poster parity uses comprehensive evaluated scene snapshots', async () => {
  const script = await readFile(builderUrl, 'utf8');

  for (const snapshot of [
    'camera_projection_snapshot',
    'render_output_snapshot',
    'lighting_snapshot',
    'world_snapshot',
    'color_management_snapshot',
  ]) {
    assert.match(script, new RegExp(snapshot));
  }
});
