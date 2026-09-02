import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../', import.meta.url);
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex').toUpperCase();

test('homepage hero prioritizes machine exploration ahead of demo booking in both contexts', async () => {
  const template = JSON.parse(await readFile(new URL('templates/index.json', root), 'utf8'));
  const thailand = JSON.parse(await readFile(new URL('templates/index.context.thailand.json', root), 'utf8'));
  const hero = await readFile(new URL('sections/maliev-keynote-hero.liquid', root), 'utf8');
  const settings = template.sections.keynote_hero.settings;
  assert.equal(settings.primary_label, 'Explore the machines');
  assert.equal(settings.primary_link, '/collections/เครื่องฉีดพลาสติก');
  assert.equal(settings.secondary_label, 'Book a demo session');
  assert.equal(settings.secondary_link, '/pages/contact');
  assert.equal(thailand.sections.keynote_hero.settings.primary_label, 'ดูเครื่องทุกรุ่น');
  assert.equal(thailand.sections.keynote_hero.settings.secondary_label, 'นัดเยี่ยมชมโรงงาน');
  assert.match(hero, /class="mkey__btn"[^>]*section\.settings\.primary_link[^>]*>\{\{ section\.settings\.primary_label \}\}/);
  assert.match(hero, /class="mkey__textlink"[^>]*section\.settings\.secondary_link/);
  assert.ok(hero.indexOf('class="mkey__btn"') < hero.indexOf('class="mkey__textlink"'));
  const schema = JSON.parse(hero.match(/{% schema %}([\s\S]*?){% endschema %}/)[1]);
  assert.equal(schema.settings.find(item => item.id === 'primary_label').default, settings.primary_label);
  assert.equal(schema.settings.find(item => item.id === 'secondary_label').default, settings.secondary_label);
});

test('homepage PIMM media is derived from the two authoritative masters', async () => {
  const manifest = JSON.parse(await readFile(new URL('assets/maliev-homepage-pimm-assets.v1.json', root), 'utf8'));
  assert.equal(manifest.schema_version, 1);
  assert.equal(manifest.release_id, 'maliev-homepage-pimm-20260901-r14');
  assert.equal(manifest.source_render_release_id, 'maliev-homepage-pimm-20260901-r14');
  assert.equal(manifest.shadow_source, 'Blender Cycles physical studio for hero; shadow catcher for transparent placements; no post-render edits');
  assert.equal(manifest.renderer, 'scripts/blender/pimm_production/blender_homepage_alpha_render.py');
  assert.equal(manifest.composition, 'Purpose-staged 30G and 50G pair renders from one Blender scene per placement');
  assert.equal(manifest.masters['30g'].sha256, '98577604BB25033B5A7229A66A14D12703E6636DF6B064F877DF7EFC6E65CEFA');
  assert.equal(manifest.masters['50g'].sha256, 'CC26246CD01956B1145B1AA5744B968918F956B667B720205723E6B60A252D90');
  assert.ok(manifest.masters['30g'].foot_contact_spread_m <= 0.0002);
  assert.ok(manifest.masters['50g'].foot_contact_spread_m <= 0.0002);

  for (const asset of manifest.assets) {
    const bytes = await readFile(new URL(`assets/${asset.filename}`, root));
    assert.equal(sha256(bytes), asset.sha256, asset.filename);
    const isHero = asset.placement.startsWith('hero-');
    assert.equal(asset.alpha, !isHero, asset.filename);
    assert.ok(asset.width >= 900, `${asset.filename} width`);
    assert.ok(asset.height >= 900, `${asset.filename} height`);
    if (isHero) {
      assert.equal(asset.alpha_bbox, undefined, `${asset.filename} must be a complete Blender studio render`);
      assert.match(asset.filename, /-studio\.webp$/);
      continue;
    }
    assert.ok(asset.alpha_bbox, `${asset.filename} alpha bounds`);
    if (asset.placement === 'catalogue') {
      assert.ok(asset.alpha_bbox.top_ratio >= 0.43, `${asset.filename} must preserve the catalogue copy-safe area`);
      assert.ok(asset.alpha_bbox.top_ratio <= 0.5, `${asset.filename} must keep the machines prominent below the copy`);
    } else {
      assert.ok(asset.alpha_bbox.top_ratio <= 0.14, `${asset.filename} top fill`);
    }
    if (asset.placement === 'catalogue') {
      assert.ok(asset.alpha_bbox.bottom_ratio >= 0.04, `${asset.filename} catalogue shadow margin`);
      assert.ok(asset.alpha_bbox.bottom_ratio <= 0.1, `${asset.filename} catalogue bottom fill`);
    }
    const leftMaximum = asset.placement === 'catalogue' ? 0.25 : 0.08;
    assert.ok(asset.alpha_bbox.left_ratio <= leftMaximum, `${asset.filename} left fill`);
    const rightMaximum = asset.placement === 'catalogue' ? 0.3 : 0.08;
    assert.ok(asset.alpha_bbox.right_ratio <= rightMaximum, `${asset.filename} right fill`);
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
  const expectedAssets = [
    'maliev-homepage-pimm-20260901-r14-hero-desktop-studio.webp',
    'maliev-homepage-pimm-20260901-r14-hero-mobile-studio.webp',
    'maliev-homepage-pimm-20260901-r14-catalogue-alpha.webp',
    'maliev-homepage-pimm-20260901-r14-navigation-alpha.webp',
  ];
  for (const filename of expectedAssets) assert.match(active, new RegExp(filename.replaceAll('.', '\\.')));
  const matches = active.match(/maliev-homepage-pimm-20260901-r14-(?:hero-(?:desktop|mobile)-studio|(?:catalogue|navigation)-alpha)\.webp/g) ?? [];
  assert.equal(matches.length, 4, 'each homepage location must reference exactly one unique asset');
  assert.doesNotMatch(`${template}\n${menu}`, /maliev-catalogue-machines\.webp/);
  assert.doesNotMatch(hero, /mkey__hero-machines|mkey__hero-machine--30g|mkey__hero-machine--50g/);
  assert.doesNotMatch(hero, /asset_name_30g|asset_name_50g/);
  assert.match(hero, /<source media="\(max-width: 989px\)" srcset="\{\{ section\.settings\.mobile_asset_name \| asset_url \}\}">/);
  assert.match(catalogue, /mcat__card--pimm-lineup/);
});

test('homepage header overlays the hero and becomes a white bar after a short scroll', async () => {
  const [header, chrome, keynoteScript, keynoteStyles] = await Promise.all([
    readFile(new URL('sections/maliev-header.liquid', root), 'utf8'),
    readFile(new URL('assets/maliev-chrome.css', root), 'utf8'),
    readFile(new URL('assets/maliev-keynote.js', root), 'utf8'),
    readFile(new URL('assets/maliev-keynote.css', root), 'utf8'),
  ]);

  assert.match(header, /request\.page_type == 'index'[\s\S]*assign header_is_home = true/);
  assert.match(header, /header_is_home[\s\S]*mc-header--home/);
  assert.match(chrome, /\.mc-header--home\s*\{[\s\S]*background: transparent;[\s\S]*position: fixed;/);
  assert.match(chrome, /\.mc-header--home\.is-solid[\s\S]*background: var\(--maliev-surface\);/);
  assert.match(chrome, /@media \(prefers-reduced-motion: reduce\)[\s\S]*\.mc-header--home[\s\S]*transition: none;/);
  assert.match(keynoteScript, /solidThreshold = Math\.max\(16, Math\.round\(header\.offsetHeight \* 0\.25\)\)/);
  assert.match(keynoteScript, /window\.scrollY > solidThreshold/);
  assert.match(keynoteScript, /addEventListener\('scroll', requestSync, \{ passive: true \}\)/);
  assert.match(keynoteStyles, /\.mkey--hero-overlay \.mkey__frame\s*\{[\s\S]*min-height: 100svh;/);
  assert.match(keynoteStyles, /\.template-index \.mkey--hero-overlay \.mkey__hero-bg\s*\{\s*top: 0;/);
  assert.doesNotMatch(keynoteStyles, /\.template-index \.mkey--hero-overlay \.mkey__hero-bg\s*\{\s*top: var\(--maliev-header-h/);
});

test('desktop homepage studio render fills the full hero viewport without side gutters', async () => {
  const keynoteStyles = await readFile(new URL('assets/maliev-keynote.css', root), 'utf8');

  assert.match(
    keynoteStyles,
    /@media screen and \(min-width: 990px\)[\s\S]*\.template-index \.mkey--hero-overlay \.mkey__hero-bg--gallery > picture > img\s*\{[^}]*height:\s*100%;[^}]*object-fit:\s*cover;[^}]*object-position:\s*center bottom;[^}]*width:\s*100%;/,
  );
});

test('homepage renderer gives each content location a purpose-specific staging contract', async () => {
  const [renderer, studioRenderer] = await Promise.all([
    readFile(new URL('scripts/blender/pimm_production/blender_homepage_alpha_render.py', root), 'utf8'),
    readFile(new URL('scripts/blender/pimm_production/blender_master_storefront_render.py', root), 'utf8'),
  ]);
  assert.match(renderer, /cyclorama\.is_shadow_catcher = not hero_studio/);
  assert.match(renderer, /scene\.render\.film_transparent = not hero_studio/);
  assert.match(renderer, /scene\.render\.image_settings\.color_mode = "RGB" if hero_studio else "RGBA"/);
  assert.match(renderer, /bpy\.data\.libraries\.load/);
  assert.match(renderer, /requested\.scenes = \[available\.scenes\[0\]\]/);
  assert.match(renderer, /bpy\.context\.scene\.collection\.children\.link\(collection\)/);
  assert.match(renderer, /obj\.name\.startswith\("PIMM50_MASTER_"\)/);
  assert.match(renderer, /APPEND_FOOT_TOLERANCE = 0\.001/);
  assert.match(renderer, /-bounds_min\[2\]/);
  assert.match(renderer, /HERO_ROTATION_DEGREES = -45\.0/);
  assert.match(renderer, /HERO_DESKTOP_CAMERA_DISTANCE_MULTIPLIER = 1\.30/);
  assert.match(renderer, /HERO_DESKTOP_CAMERA_SHIFT_Y = 0\.02/);
  assert.match(renderer, /CATALOGUE_ROTATION_DEGREES = 0\.0/);
  assert.match(renderer, /CATALOGUE_DEPTH_STAGGER_RATIO = 0\.0/);
  assert.match(renderer, /CATALOGUE_PAIR_GAP_RATIO = 0\.08/);
  assert.match(renderer, /NAVIGATION_ROTATION_DEGREES = 18\.0/);
  assert.match(renderer, /_place_pair_for_placement/);
  assert.match(renderer, /"catalogue-copy-safe-46-front"/);
  assert.match(renderer, /CATALOGUE_COPY_SAFE_RATIO = 0\.46/);
  assert.match(renderer, /CATALOGUE_CAMERA_DISTANCE_MULTIPLIER = 2\.00/);
  assert.match(renderer, /CATALOGUE_CAMERA_SHIFT_Y = CATALOGUE_COPY_SAFE_RATIO - 0\.20/);
  assert.match(renderer, /data\.shift_y = \([\s\S]*CATALOGUE_CAMERA_SHIFT_Y[\s\S]*placement == "hero-desktop"/);
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
  assert.match(renderer, /CATALOGUE_CAMERA_SHIFT_X = 0\.02/);
  assert.match(renderer, /else CATALOGUE_CAMERA_SHIFT_X/);
  assert.match(renderer, /data\.clip_end = distance \* 2\.5/);
  assert.match(renderer, /scene\.view_settings\.exposure = 0\.35/);
  assert.match(renderer, /scene\.render\.image_settings\.color_depth = "16"/);
  assert.match(renderer, /def _tune_homepage_studio/);
  assert.match(renderer, /if placement\.startswith\("hero-"\):\s+key\.use_shadow = True/);
  assert.match(renderer, /if placement\.startswith\("hero-"\):\s+fill\.use_shadow = True/);
  assert.match(renderer, /overhead\.size = extent \* \(4\.0 if placement\.startswith\("hero-"\) else 3\.4\)/);
  assert.match(renderer, /background\.use_shadow = False/);
  assert.match(renderer, /ambient\.inputs\["Strength"\]\.default_value = 0\.35/);
  assert.match(renderer, /_configure_render\([\s\S]*_tune_homepage_studio\(bpy, runtime, extent, placement\)/);
  assert.match(renderer, /scene\.compositing_node_group = None/);
  assert.match(studioRenderer, /CYCLORAMA_GROUND_EXTENT_MULTIPLIER = 1_000\.0/);
  assert.match(studioRenderer, /y_front = center\[1\] - extent \* CYCLORAMA_GROUND_EXTENT_MULTIPLIER/);
  assert.match(studioRenderer, /y_back = center\[1\] \+ extent \* 1\.6/);
  assert.match(studioRenderer, /half_width = extent \* CYCLORAMA_GROUND_EXTENT_MULTIPLIER/);
  assert.doesNotMatch(renderer, /save_as_mainfile|open_mainfile|maliev-catalogue-machines/i);
});

test('homepage finalizer preserves Blender studio and shadow-catcher outputs without post-processing', async () => {
  const finalizer = await readFile(new URL('scripts/blender/pimm_production/finalize_homepage_pimm_assets.py', root), 'utf8');
  assert.doesNotMatch(finalizer, /alpha_composite|_composite_pair|30g-alpha\.png|50g-alpha\.png/);
  assert.match(finalizer, /for placement, dimensions in PLACEMENTS\.items\(\)/);
  assert.match(finalizer, /"hero-desktop": "studio"/);
  assert.match(finalizer, /"catalogue": "alpha"/);
  assert.doesNotMatch(finalizer, /_soften_ground_shadow|putalpha|pixels\s*=/);
  assert.match(finalizer, /"shadow_source": "Blender Cycles physical studio for hero; shadow catcher for transparent placements; no post-render edits"/);
  assert.match(finalizer, /--source-release-id/);
});

test('catalogue PIMM card ends its text veil before the machine composition begins', async () => {
  const styles = await readFile(new URL('assets/maliev-catalogue.css', root), 'utf8');
  assert.match(styles, /\.mcat__card--pimm-lineup::after\s*\{[\s\S]*transparent 48%/);
});

test('homepage catalogue ends with a distinct MALIEV manufacturing services card', async () => {
  const [templateSource, catalogueSection] = await Promise.all([
    readFile(new URL('templates/index.json', root), 'utf8'),
    readFile(new URL('sections/maliev-catalogue.liquid', root), 'utf8'),
  ]);
  const template = JSON.parse(templateSource);
  const catalogue = template.sections.catalogue;
  const manufacturing = catalogue.blocks.manufacturing_services;

  assert.equal(catalogue.block_order.at(-2), 'molding_materials');
  assert.equal(catalogue.block_order.at(-1), 'manufacturing_services');
  assert.equal(manufacturing.settings.link, 'https://www.maliev.com/');
  assert.equal(manufacturing.settings.asset_name, 'maliev-catalogue-manufacturing-services.webp');
  assert.equal(
    new Set(Object.values(catalogue.blocks).map(({ settings }) => settings.asset_name)).size,
    Object.keys(catalogue.blocks).length,
    'catalogue cards must not reuse image assets',
  );
  assert.match(catalogueSection, /if card_link contains 'www\.maliev\.com'/);
  assert.match(catalogueSection, /if request\.locale\.iso_code contains 'th'[\s\S]*assign destination_culture = 'th'/);
  assert.match(catalogueSection, /append: '[&?]culture=' \| append: destination_culture/);
  assert.match(catalogueSection, /href="\{\{ card_link \}\}"/);
});

test('footer social links use quiet borderless surfaces with a distinct hover state', async () => {
  const chrome = await readFile(new URL('assets/maliev-chrome.css', root), 'utf8');

  assert.match(chrome, /\.mc-footer__social \.list-social__link\s*\{[\s\S]*background: rgba\(255, 255, 255, 0\.06\);[\s\S]*border: 0;[\s\S]*opacity: 0\.72;/);
  assert.match(chrome, /\.mc-footer__social \.list-social__link:hover\s*\{[\s\S]*background: rgba\(255, 255, 255, 0\.12\);[\s\S]*opacity: 1;/);
});
