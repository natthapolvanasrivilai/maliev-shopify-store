import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../', import.meta.url);
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex').toUpperCase();

test('homepage PIMM media is derived from the two authoritative masters', async () => {
  const manifest = JSON.parse(await readFile(new URL('assets/maliev-homepage-pimm-assets.v1.json', root), 'utf8'));
  assert.equal(manifest.schema_version, 1);
  assert.equal(manifest.release_id, 'maliev-homepage-pimm-20260901-r02');
  assert.equal(manifest.renderer, 'scripts/blender/pimm_production/blender_homepage_alpha_render.py');
  assert.equal(manifest.masters['30g'].sha256, '98577604BB25033B5A7229A66A14D12703E6636DF6B064F877DF7EFC6E65CEFA');
  assert.equal(manifest.masters['50g'].sha256, 'CC26246CD01956B1145B1AA5744B968918F956B667B720205723E6B60A252D90');
  assert.ok(manifest.masters['30g'].foot_contact_spread_m <= 0.0002);
  assert.ok(manifest.masters['50g'].foot_contact_spread_m <= 0.0002);

  for (const asset of manifest.assets) {
    const bytes = await readFile(new URL(`assets/${asset.filename}`, root));
    assert.equal(sha256(bytes), asset.sha256, asset.filename);
    assert.equal(asset.alpha, true, asset.filename);
    assert.ok(asset.width >= 900, `${asset.filename} width`);
    assert.ok(asset.height >= 900, `${asset.filename} height`);
    assert.ok(asset.alpha_bbox, `${asset.filename} alpha bounds`);
    assert.ok(asset.alpha_bbox.top_ratio <= 0.04, `${asset.filename} top fill`);
    assert.ok(asset.alpha_bbox.bottom_ratio <= 0.04, `${asset.filename} bottom fill`);
    assert.ok(asset.alpha_bbox.left_ratio <= (asset.placement === 'hero-desktop' ? 0.45 : 0.06), `${asset.filename} left fill`);
    assert.ok(asset.alpha_bbox.right_ratio <= 0.06, `${asset.filename} right fill`);
  }
  assert.deepEqual(manifest.assets.map(({ placement }) => placement).toSorted(), ['catalogue', 'hero-desktop', 'hero-mobile', 'navigation']);
  assert.equal(new Set(manifest.assets.map(({ filename }) => filename)).size, manifest.assets.length);
});

test('homepage placements use distinct purpose-rendered assets', async () => {
  const [template, hero, catalogue, menu] = await Promise.all([
    readFile(new URL('templates/index.json', root), 'utf8'),
    readFile(new URL('sections/maliev-keynote-hero.liquid', root), 'utf8'),
    readFile(new URL('sections/maliev-catalogue.liquid', root), 'utf8'),
    readFile(new URL('snippets/maliev-menu-link.liquid', root), 'utf8'),
  ]);
  const active = `${template}\n${menu}`;
  for (const placement of ['hero-desktop', 'hero-mobile', 'catalogue', 'navigation']) {
    assert.match(active, new RegExp(`maliev-homepage-pimm-20260901-r02-${placement}-alpha\\.webp`));
  }
  const matches = active.match(/maliev-homepage-pimm-20260901-r02-(?:hero-desktop|hero-mobile|catalogue|navigation)-alpha\.webp/g) ?? [];
  assert.equal(matches.length, 4, 'each homepage location must reference exactly one unique asset');
  assert.doesNotMatch(`${template}\n${menu}`, /maliev-catalogue-machines\.webp/);
  assert.match(hero, /mkey__hero-machine--30g/);
  assert.match(hero, /mkey__hero-machine--50g/);
  assert.match(catalogue, /mcat__card--pimm-lineup/);
});

test('homepage alpha renderer locks shared perspective and a common ground plane', async () => {
  const renderer = await readFile(new URL('scripts/blender/pimm_production/blender_homepage_alpha_render.py', root), 'utf8');
  assert.match(renderer, /film_transparent = True/);
  assert.match(renderer, /is_shadow_catcher = True/);
  assert.match(renderer, /FRAME_HEIGHT_M = 1014\.5/);
  assert.match(renderer, /data\.type = "PERSP"/);
  assert.match(renderer, /data\.lens = 95\.0/);
  assert.match(renderer, /scene\.view_settings\.exposure = 0\.35/);
  assert.doesNotMatch(renderer, /save_as_mainfile|open_mainfile|maliev-catalogue-machines/i);
});
