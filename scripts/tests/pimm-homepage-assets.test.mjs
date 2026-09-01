import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../', import.meta.url);
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex').toUpperCase();

test('homepage PIMM media is derived from the two authoritative masters', async () => {
  const manifest = JSON.parse(await readFile(new URL('assets/maliev-homepage-pimm-assets.v1.json', root), 'utf8'));
  assert.equal(manifest.schema_version, 1);
  assert.equal(manifest.release_id, 'maliev-homepage-pimm-20260901-r04');
  assert.equal(manifest.renderer, 'scripts/blender/pimm_production/blender_homepage_alpha_render.py');
  assert.equal(manifest.composition, 'Purpose-staged 30G and 50G pair renders from one Blender scene per placement');
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
    const portrait = asset.placement === 'hero-mobile' || asset.placement === 'catalogue';
    assert.ok(asset.alpha_bbox.top_ratio <= (portrait ? 0.1 : 0.04), `${asset.filename} top fill`);
    assert.ok(asset.alpha_bbox.bottom_ratio <= 0.04, `${asset.filename} bottom fill`);
    assert.ok(asset.alpha_bbox.left_ratio <= (asset.placement === 'hero-desktop' ? 0.45 : 0.08), `${asset.filename} left fill`);
    assert.ok(asset.alpha_bbox.right_ratio <= (asset.placement === 'hero-desktop' ? 0.06 : 0.08), `${asset.filename} right fill`);
  }
  assert.deepEqual(manifest.assets.map(({ placement }) => placement).toSorted(), ['catalogue', 'hero-desktop', 'hero-mobile', 'navigation']);
  assert.equal(new Set(manifest.assets.map(({ filename }) => filename)).size, manifest.assets.length);
  const compositions = Object.fromEntries(manifest.assets.map(({ placement, composition_id }) => [placement, composition_id]));
  assert.equal(compositions['hero-desktop'], compositions['hero-mobile'], 'responsive hero crops may share one staged shot');
  assert.notEqual(compositions.catalogue, compositions['hero-desktop'], 'catalogue must not reuse the hero composition');
  assert.notEqual(compositions.navigation, compositions['hero-desktop'], 'navigation must not reuse the hero composition');
  assert.notEqual(compositions.navigation, compositions.catalogue, 'navigation must not reuse the catalogue composition');
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
    assert.match(active, new RegExp(`maliev-homepage-pimm-20260901-r04-${placement}-alpha\\.webp`));
  }
  const matches = active.match(/maliev-homepage-pimm-20260901-r04-(?:hero-desktop|hero-mobile|catalogue|navigation)-alpha\.webp/g) ?? [];
  assert.equal(matches.length, 4, 'each homepage location must reference exactly one unique asset');
  assert.doesNotMatch(`${template}\n${menu}`, /maliev-catalogue-machines\.webp/);
  assert.doesNotMatch(hero, /mkey__hero-machines|mkey__hero-machine--30g|mkey__hero-machine--50g/);
  assert.doesNotMatch(hero, /asset_name_30g|asset_name_50g/);
  assert.match(hero, /<source media="\(max-width: 989px\)" srcset="\{\{ section\.settings\.mobile_asset_name \| asset_url \}\}">/);
  assert.match(catalogue, /mcat__card--pimm-lineup/);
});

test('homepage renderer gives each content location a purpose-specific staging contract', async () => {
  const renderer = await readFile(new URL('scripts/blender/pimm_production/blender_homepage_alpha_render.py', root), 'utf8');
  assert.match(renderer, /film_transparent = True/);
  assert.match(renderer, /is_shadow_catcher = True/);
  assert.match(renderer, /bpy\.data\.libraries\.load/);
  assert.match(renderer, /requested\.scenes = \[available\.scenes\[0\]\]/);
  assert.match(renderer, /bpy\.context\.scene\.collection\.children\.link\(collection\)/);
  assert.match(renderer, /obj\.name\.startswith\("PIMM50_MASTER_"\)/);
  assert.match(renderer, /APPEND_FOOT_TOLERANCE = 0\.001/);
  assert.match(renderer, /-bounds_min\[2\]/);
  assert.match(renderer, /HERO_ROTATION_DEGREES = 45\.0/);
  assert.match(renderer, /CATALOGUE_ROTATION_DEGREES = -32\.0/);
  assert.match(renderer, /CATALOGUE_DEPTH_STAGGER_RATIO = 0\.14/);
  assert.match(renderer, /CATALOGUE_PAIR_OVERLAP_RATIO = 0\.18/);
  assert.match(renderer, /NAVIGATION_ROTATION_DEGREES = 18\.0/);
  assert.match(renderer, /_place_pair_for_placement/);
  assert.match(renderer, /"catalogue-stagger-minus32"/);
  assert.match(renderer, /"navigation-compact-18"/);
  assert.match(renderer, /PAIR_GAP_RATIO = 0\.04/);
  assert.match(renderer, /_stage_collection_root/);
  assert.match(renderer, /_hide_master_working_scene/);
  assert.match(renderer, /_flatten_published_meshes/);
  assert.match(renderer, /duplicate\.parent = None/);
  assert.match(renderer, /obj\.hide_render = True/);
  assert.match(renderer, /collection\.all_objects/);
  assert.match(renderer, /root\.instance_type = "COLLECTION"/);
  assert.match(renderer, /root\.instance_collection = collection/);
  assert.match(renderer, /collection\.instance_offset = \(0\.0, 0\.0, 0\.0\)/);
  assert.match(renderer, /PLACEMENTS = \{/);
  assert.match(renderer, /"hero-desktop": \(1800, 1200\)/);
  assert.match(renderer, /"hero-mobile": \(1200, 1500\)/);
  assert.match(renderer, /data\.type = "PERSP"/);
  assert.match(renderer, /data\.lens = lens/);
  assert.match(renderer, /data\.shift_x = -0\.18 if placement == "hero-desktop" else 0\.0/);
  assert.match(renderer, /data\.clip_end = distance \* 2\.5/);
  assert.match(renderer, /scene\.view_settings\.exposure = 0\.35/);
  assert.match(renderer, /scene\.compositing_node_group = None/);
  assert.doesNotMatch(renderer, /save_as_mainfile|open_mainfile|maliev-catalogue-machines/i);
});

test('homepage finalizer never overlays separately rendered machine images', async () => {
  const finalizer = await readFile(new URL('scripts/blender/pimm_production/finalize_homepage_pimm_assets.py', root), 'utf8');
  assert.doesNotMatch(finalizer, /alpha_composite|_composite_pair|30g-alpha\.png|50g-alpha\.png/);
  assert.match(finalizer, /for placement, dimensions in PLACEMENTS\.items\(\)/);
});
