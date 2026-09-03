import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, readdir } from 'node:fs/promises';
import test from 'node:test';

const rootUrl = new URL('../../', import.meta.url);
const assetsUrl = new URL('../../assets/', import.meta.url);
const release = 'pimm-master-20260901-r05';
const roles = ['configuration', 'controls', 'hero', 'overview', 'tooling'];
const expectedMedia = ['30g', '50g'].flatMap((model) => roles.flatMap((role) => [
  `${release}-${model}-${role}.png`,
  `${release}-${model}-${role}.webp`,
]));
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex').toUpperCase();

test('30G hero amplification stays model-scoped and preserves the full native render', async () => {
  const section = await readFile(new URL('sections/maliev-pimm-machine-product.liquid', rootUrl), 'utf8');
  assert.match(section, /if page_model == '30G'[\s\S]*?'maliev-pimm-30g-hero.css'[\s\S]*?endif/);
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  assert.match(css, /object-fit: contain/);
  assert.match(css, /grid-template-rows: minmax\(0, 1fr\)/);
  assert.match(css, /prefers-reduced-motion: reduce/);
  assert.doesNotMatch(css, /(?:filter|box-shadow|mask-image):/);
  assert.ok(css.split('\n').filter(line => line.trim().startsWith('.')).every(line => line.includes('[data-page-model="30G"]')));
});

test('30G hero poster and animation share a rounded media frame', async () => {
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  const frame = css.match(/pimm-hero-reveal \{([^}]+)\}/)[1];
  assert.match(frame, /border-radius: 14px/);
  assert.match(frame, /overflow: hidden/);
  const media = css.match(/pimm-hero-reveal :is\(img, video\) \{([^}]+)\}/)[1];
  assert.match(media, /border-radius: inherit/);
  assert.match(media, /object-fit: contain/);
});

test('30G engineering band separates heading, labels, values and units without changing data', async () => {
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  const band = css.match(/\.pimm-machine\[data-page-model="30G"\] \.pimm-machine__specifications \{([^}]+)\}/)[1];
  assert.match(band, /background: var\(--pimm-canvas\)/);
  assert.match(band, /color: var\(--pimm-ink\)/);
  for (const [element, color] of [['h2', 'blue'], ['dt', 'muted'], ['dd', 'ink']]) {
    const rule = css.match(new RegExp(`\\.pimm-machine__specifications ${element} \\{([^}]+)\\}`))[1];
    assert.ok(rule.includes(`color: var(--pimm-${color})`));
  }
  assert.match(css, /font-variant-numeric: lining-nums tabular-nums/);
  assert.match(css, /\[data-pimm-spec-unit\]\[hidden\] \{ display: none; \}/);
});

test('30G demo close gives the booking action a distinct neutral-to-blue treatment', async () => {
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  assert.match(css, /\.pimm-machine__purchase \{[^}]*--pimm-booking-surface: #e6f1fb;[^}]*background: var\(--pimm-booking-surface\)/);
  assert.match(css, /\.pimm-machine__purchase h2 \{ color: var\(--pimm-blue\)/);
  assert.match(css, /\.pimm-machine__purchase \.button--primary \{[^}]*background: var\(--pimm-ink\)/);
  assert.match(css, /\.pimm-machine__purchase \.button--primary:hover \{[^}]*background: var\(--pimm-blue\)/);
});

test('30G support typography pairs a bounded heading with readable responsive prose', async () => {
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  assert.match(css, /\.pimm-machine__ownership h2 \{[^}]*max-width: 18ch/);
  assert.match(css, /\.pimm-machine__ownership p \{[^}]*font-size: 2rem;[^}]*line-height: 1.65;[^}]*max-width: 60ch/);
  assert.match(css, /\.pimm-machine__ownership:lang\(th\) h2 \{[^}]*letter-spacing: normal/);
  assert.match(css, /@media \(max-width: 999px\) \{\s*\.pimm-machine\[data-page-model="30G"\] \.pimm-machine__ownership \.pimm-machine__prose \{\s*grid-template-columns: minmax\(0, 1fr\)/);
});

test('30G feature chapters have consistent unnumbered headings and readable copy', async () => {
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  const story = await readFile(new URL('snippets/pimm-30g-product-story.liquid', rootUrl), 'utf8');
  assert.equal((story.match(/<h3>/g) ?? []).length, 4);
  assert.doesNotMatch(story, /pimm-story__index/);
  assert.match(css, /\.pimm-story__copy h3 \{[^}]*font-size: clamp\(2\.8rem, 3\.2vw, 4\.8rem\) !important;[^}]*line-height: 1\.16 !important/);
  assert.match(css, /\.pimm-story__copy\) > p:last-child \{[^}]*font-size: 2rem;[^}]*line-height: 1\.65/);
  assert.match(css, /\.pimm-story--30g:lang\(th\) :is\(h2, h3\) \{[^}]*letter-spacing: normal !important/);
});

test('dedicated product templates lock model identity independently of query selection', async () => {
  for (const [view, model] of [['pimm-configurator', '30G'], ['pimm-50g', '50G']]) {
    const source = await readFile(new URL(`templates/product.${view}.json`, rootUrl), 'utf8');
    const template = JSON.parse(source.replace(/\/\*[\s\S]*?\*\//g, ''));
    assert.equal(template.sections.main.settings.page_model, model);
  }
  const section = await readFile(new URL('sections/maliev-pimm-machine-product.liquid', rootUrl), 'utf8');
  assert.match(section, /assign selected_variant = product\.variants \| where: 'option1', page_model \| first/);
  const hero = await readFile(new URL('snippets/pimm-hero-console.liquid', rootUrl), 'utf8');
  assert.match(hero, /unless section.settings.page_model == '30G' or section.settings.page_model == '50G'/);
  assert.match(hero, /PIMM {{ selected_model_code \| escape }}/);
});

test('master-derived release is the only PIMM media family in theme assets', async () => {
  const names = await readdir(assetsUrl);
  const pimmMedia = names.filter((name) =>
    name.startsWith(`${release}-`) && /\.(?:avif|jpe?g|png|webp|webm|mp4)$/i.test(name),
  ).sort();
  assert.deepEqual(pimmMedia, expectedMedia.toSorted());
});

test('manifest locks every native render and storefront derivative to exact hashes', async () => {
  const manifest = JSON.parse(await readFile(new URL('../../assets/pimm-master-storefront-assets.v1.json', import.meta.url), 'utf8'));
  assert.equal(manifest.schema_version, 1);
  assert.equal(manifest.release_id, release);
  assert.equal(manifest.renderer, 'scripts/blender/pimm_production/blender_master_storefront_render.py');
  assert.equal(manifest.masters['30g'].filename, 'PIMM-30G-MASTER.blend');
  assert.equal(manifest.masters['50g'].filename, 'PIMM-50G-MASTER.blend');
  assert.equal(manifest.masters['30g'].foot_count, 4);
  assert.equal(manifest.masters['50g'].foot_count, 4);
  assert.ok(manifest.masters['30g'].foot_contact_spread_m <= 0.0002);
  assert.ok(manifest.masters['50g'].foot_contact_spread_m <= 0.0002);
  assert.equal(manifest.assets.length, 10);

  const declared = [];
  for (const asset of manifest.assets) {
    for (const output of [asset.native, asset.storefront]) {
      const bytes = await readFile(new URL(`../../assets/${output.filename}`, import.meta.url));
      assert.equal(sha256(bytes), output.sha256, output.filename);
      assert.ok(output.width >= 1600, `${output.filename} width`);
      assert.ok(output.height >= 1200, `${output.filename} height`);
      declared.push(output.filename);
    }
  }
  assert.deepEqual(declared.toSorted(), expectedMedia.toSorted());
});

test('active configurator gives every media placement its own release WebP asset', async () => {
  const paths = [
    'sections/maliev-pimm-machine-product.liquid',
    'snippets/pimm-hero-console.liquid',
    'snippets/pimm-30g-product-story.liquid',
    'snippets/pimm-50g-product-story.liquid',
    'templates/product.pimm-configurator.json',
    'assets/maliev-pimm-machine.js',
  ];
  const source = (await Promise.all(paths.map((path) => readFile(new URL(path, rootUrl), 'utf8')))).join('\n');
  const matches = source.match(new RegExp(`${release}-(?:30g|50g)-(?:configuration|controls|hero|overview|tooling)\\.webp`, 'g')) ?? [];
  const referenced = [...new Set(matches)].sort();
  const expectedWebp = expectedMedia.filter((name) => name.endsWith('.webp')).sort();
  assert.deepEqual(referenced, expectedWebp);
  assert.equal(matches.length, expectedWebp.length, 'a rendered asset must not be reused by two placements');
  assert.doesNotMatch(source, /(?:(?:pimm30-|pimm50-|pimm-(?:machine|editorial)-|maliev-pimm-)[^'"\s)]+\.(?:png|webp|webm|mp4))/i);
});
