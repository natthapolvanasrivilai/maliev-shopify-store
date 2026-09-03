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

test('30G engineering band uses a quiet neutral surface and contrasting brand typefaces', async () => {
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  const band = css.match(/\.pimm-machine\[data-page-model="30G"\] \.pimm-machine__specifications \{([^}]+)\}/)[1];
  assert.match(band, /background: #f3f5f6/);
  assert.match(band, /color: var\(--pimm-ink\)/);
  for (const element of ['h2', 'dt', 'dd']) {
    const rule = css.match(new RegExp(`\\.pimm-machine__specifications ${element} \\{([^}]+)\\}`))[1];
    assert.match(rule, element === 'dt' ? /color: var\(--pimm-muted\)/ : /color: var\(--pimm-ink\)/);
    assert.match(rule, element === 'h2' ? /font-family: var\(--maliev-font-future\)/ : /font-family: var\(--maliev-font-sans\)/);
  }
});

test('30G engineering and commercial facts form a joined responsive summary without restyling values', async () => {
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  const band = css.match(/\.pimm-machine__specifications \{([^}]+)\}/)[1];
  assert.match(band, /grid-template-columns: minmax\(0, 1fr\)/);
  assert.match(band, /border-radius: 14px 14px 0 0/);
  const commercial = css.match(/\.pimm-machine__qualification-strip \{([^}]+)\}/)[1];
  assert.match(commercial, /border-radius: 0 0 14px 14px/);
  assert.match(commercial, /padding: 24px 32px/);
  assert.match(css, /\.pimm-machine__qualification-facts > div \{ grid-template-columns: 1fr; gap: 8px; \}/);
  assert.doesNotMatch(css, /\.pimm-machine__qualification-facts dd \{[^}]*font-/);
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

test('30G feature bento has varied tiles, real workshop stills and readable localized copy', async () => {
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  const story = await readFile(new URL('snippets/pimm-30g-product-story.liquid', rootUrl), 'utf8');
  assert.equal((story.match(/<h3>/g) ?? []).length, 4);
  assert.doesNotMatch(story, /pimm-story__index|pimm-story__chapter|data-pimm-reveal/);
  assert.equal((story.match(/<img /g) ?? []).length, 6);
  assert.match(story, /pimm-gallery-20260903-molding\.webp/);
  assert.match(story, /pimm-gallery-20260903-end-caps\.webp/);
  assert.match(css, /grid-template-areas: "controls controls" "capacity tooling" "configuration configuration" "workshop parts"/);
  assert.match(css, /grid-template-areas: "capacity" "controls" "tooling" "workshop" "configuration" "parts"/);
  assert.match(css, /\.pimm-bento__copy h3 \{[^}]*font-size: clamp\(2\.8rem, 1\.6rem \+ 1\.7vw, 4rem\) !important/);
  assert.match(css, /\.pimm-bento__copy p \{[^}]*font-size: 1\.6rem;[^}]*line-height: 1\.5/);
  assert.match(css, /\.pimm-story--30g:lang\(th\) :is\(h2, h3\) \{[^}]*letter-spacing: normal !important/);
});

test('bento type hierarchy keeps brand fonts, readable body text and locale-aware headlines', async () => {
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  const heading = css.match(/\.pimm-bento__copy h3 \{([^}]+)\}/)[1];
  const body = css.match(/\.pimm-bento__copy p \{([^}]+)\}/)[1];
  assert.match(heading, /font-weight: 600/);
  assert.match(heading, /max-width: 16ch/);
  assert.match(heading, /font-kerning: normal/);
  assert.match(body, /font-weight: 400/);
  assert.match(body, /max-width: 38ch/);
  assert.match(css, /\.pimm-bento:lang\(en\) \.pimm-bento__copy h3 \{ text-transform: uppercase; \}/);
  assert.match(css, /\.pimm-bento:lang\(th\) \.pimm-bento__copy h3 \{[^}]*line-height: 1\.3 !important;[^}]*letter-spacing: normal !important/);
  const bento = css.slice(css.indexOf('.pimm-bento {'), css.indexOf('.pimm-machine__ownership {'));
  assert.doesNotMatch(bento, /font-size: 1\.5rem/);
  assert.doesNotMatch(bento, /@font-face/);
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
  const expectedWebp = expectedMedia.filter((name) => name.endsWith('.webp') && (!name.includes('-30g-') || name.endsWith('-hero.webp'))).sort();
  assert.deepEqual(referenced, expectedWebp);
  assert.equal(matches.length, expectedWebp.length, 'a rendered asset must not be reused by two placements');
  assert.doesNotMatch(source, /(?:(?:pimm30-|pimm50-|pimm-(?:machine|editorial)-|maliev-pimm-)[^'"\s)]+\.(?:png|webp|webm|mp4))/i);
});

test('30G bento uses four approved full-tile native-size lossless renders', async () => {
  const manifest = JSON.parse(await readFile(new URL('assets/pimm-bento-assets.v1.json', rootUrl), 'utf8'));
  const approvalBytes = await readFile(new URL(manifest.approval, rootUrl));
  const approval = JSON.parse(approvalBytes);
  assert.equal(approval.decision, 'approved');
  assert.equal(manifest.generation, approval.generation);
  assert.equal(manifest.assets.length, 4);
  const story = await readFile(new URL('snippets/pimm-30g-product-story.liquid', rootUrl), 'utf8');
  assert.equal((story.match(/pimm-bento__tile--render/g) ?? []).length, 4);
  for (const asset of manifest.assets) {
    assert.equal(asset.approval_sha256, sha256(approvalBytes));
    const bytes = await readFile(new URL(`assets/${asset.filename}`, rootUrl));
    assert.equal(sha256(bytes), asset.sha256);
    assert.equal(bytes.toString('ascii', 12, 16), 'VP8L');
    const packed = bytes.readUInt32LE(21);
    assert.deepEqual([(packed & 0x3fff) + 1, ((packed >>> 14) & 0x3fff) + 1], asset.size);
    assert.ok(story.includes(asset.filename));
    assert.ok(story.includes(`width="${asset.size[0]}" height="${asset.size[1]}"`));
  }
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  assert.match(css, /\.pimm-bento__tile--render \.pimm-bento__media \{ position: absolute; inset: 0; \}/);
  assert.doesNotMatch(css, /(?:mask-image|filter):/);
});

test('bento compact captions retain matching locale keys and only replace prose at narrow widths', async () => {
  for (const name of await readdir(new URL('locales/', rootUrl))) {
    if (!name.endsWith('.json') || name.endsWith('.schema.json')) continue;
    const text = await readFile(new URL(`locales/${name}`, rootUrl), 'utf8');
    const locale = JSON.parse(text.replace(/\/\*[\s\S]*?\*\//g, ''));
    assert.deepEqual(Object.keys(locale.pimm_bento).sort(), ['configuration_compact', 'controls_compact', 'tooling_compact']);
    assert.ok(Object.values(locale.pimm_bento).every(value => typeof value === 'string' && value.length > 0));
  }
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  assert.match(css, /\.pimm-bento__text-compact \{ display: none; \}/);
  assert.match(css, /@media \(max-width: 749px\)[\s\S]*?\.pimm-bento__text-full \{ display: none; \}/);
});
