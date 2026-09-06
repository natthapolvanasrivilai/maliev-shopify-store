import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, readdir } from 'node:fs/promises';
import test from 'node:test';
import { Liquid } from 'liquidjs';

const rootUrl = new URL('../../', import.meta.url);
const assetsUrl = new URL('../../assets/', import.meta.url);
const release = 'pimm-master-20260901-r05';
const roles = ['configuration', 'controls', 'hero', 'overview', 'tooling'];
const expectedMedia = ['30g', '50g'].flatMap((model) => roles.flatMap((role) => [
  `${release}-${model}-${role}.png`,
  `${release}-${model}-${role}.webp`,
]));
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex').toUpperCase();

test('support delight renders localized services and preserves merchant and model boundaries', async () => {
  const source = await readFile(new URL('snippets/pimm-ownership.liquid', rootUrl), 'utf8');
  const engine = new Liquid({ strictFilters: true });
  engine.registerTag('doc', { parse(_token, tokens) { while (tokens.length && tokens.shift().name !== 'enddoc') {} }, render() { return ''; } });
  for (const [locale, root] of [['en.default', '/'], ['th', '/th/'], ['th', '/th']]) {
    const text = await readFile(new URL(`locales/${locale}.json`, rootUrl), 'utf8');
    const translations = JSON.parse(text.replace(/^\s*\/\*[\s\S]*?\*\/\s*/, ''));
    engine.registerFilter('t', key => {
      const value = key.split('.').reduce((node, part) => node?.[part], translations);
      assert.equal(typeof value, 'string', key);
      return value;
    });
    const render = (model, settings = {}) => engine.parseAndRender(source, { page_model: model, routes: { root_url: root }, section: { id: 'support-test', settings } });
    const html = await render('30G');
    assert.equal((html.match(/<li>/g) ?? []).length, 3);
    assert.equal((html.match(/class="pimm-support-services__icon"/g) ?? []).length, 3);
    assert.doesNotMatch(html, /data-support-motion|pimm-support-motion>/);
    assert.ok(html.indexOf(translations.pimm_support.guidance) < html.indexOf('</li>'));
    assert.ok(html.indexOf(translations.pimm_support.documentation) < html.indexOf('</li>'));
    assert.ok(html.includes(translations.products.pimm_machine.ownership.body));
    assert.ok(html.includes(translations.pimm_support.made_in_thailand));
    assert.match(html, /class="pimm-support-origin"><svg[^>]*aria-hidden="true"/);
    assert.ok(html.includes(`href="${root.replace(/\/$/, '')}/pages/contact"`));
    assert.doesNotMatch(html, /<button|<script|<details/);
    const configured = await render('30G', { support_url: '/support-owner', document_url: '/manual-owner' });
    assert.match(configured, /href="\/support-owner"/);
    assert.match(configured, /href="\/manual-owner"/);
    const other = await render('50G');
    assert.doesNotMatch(other, /pimm-support-services|pimm-support-origin|<nav/);
    const legacy = await render('50G', { support_url: '/original-support' });
    assert.match(legacy, /href="\/original-support"/);
  }
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  assert.match(css, /\.pimm-support-services__icon \{[^}]*stroke-width: 1\.75;[^}]*shape-rendering: geometricPrecision;/);
  assert.match(css, /@media \(prefers-reduced-motion: no-preference\) \{[\s\S]*?\.pimm-support-services li:hover \.pimm-support-services__icon \{[^}]*transform: translate3d\(0, -3px, 0\);/);
  assert.doesNotMatch(css, /stroke-dasharray|stroke-dashoffset/);
  assert.match(css, /@media \(prefers-reduced-motion: no-preference\) \{[\s\S]*?\.pimm-machine\[data-page-model="30G"\] \.pimm-support-contact svg/);
  assert.match(css, /\.pimm-support-contact a:focus-visible \{ outline: 2px solid/);
});

test('30G hero copy inset is desktop-only and bounded at the requested 64px', async () => {
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  assert.match(css, /@media \(min-width: 1000px\) \{\s*\.pimm-machine\[data-page-model="30G"\] \.pimm-machine__decision \{\s*padding-inline-start: clamp\(24px, calc\(8vw - 56px\), 64px\);/);
  assert.doesNotMatch(css.match(/\.pimm-machine\[data-page-model="30G"\] \.pimm-machine__decision \{([^}]+)\}/)[1], /padding-inline|padding-left/);
});

test('30G hero amplification stays model-scoped and preserves the full native render', async () => {
  const section = await readFile(new URL('sections/maliev-pimm-machine-product.liquid', rootUrl), 'utf8');
  assert.match(section, /if page_model == '30G'[\s\S]*?'maliev-pimm-30g-hero.css'[\s\S]*?endif/);
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  assert.match(css, /object-fit: contain/);
  assert.match(css, /grid-template-rows: minmax\(0, 1fr\)/);
  assert.match(css, /prefers-reduced-motion: reduce/);
  assert.doesNotMatch(css, /(?:^|[;\s])filter:/);
  // A focus-style reset is not a shadow applied to machine pixels.
  assert.doesNotMatch(css, /box-shadow:\s*(?!none\b)\S/);
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
  assert.match(css, /\.pimm-machine__purchase \{[^}]*--pimm-booking-surface: #f3f5f6;[^}]*background: var\(--pimm-booking-surface\)/);
  assert.match(css, /\.pimm-machine__purchase h2 \{\s*color: var\(--pimm-ink\)/);
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

test('30G feature bento has seven native render tiles without video stills or empty grid areas', async () => {
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  const story = await readFile(new URL('snippets/pimm-30g-product-story.liquid', rootUrl), 'utf8');
  assert.equal((story.match(/<h3>/g) ?? []).length, 7);
  assert.doesNotMatch(story, /pimm-story__index|pimm-story__chapter|data-pimm-reveal/);
  assert.equal((story.match(/<img /g) ?? []).length, 7);
  assert.doesNotMatch(story, /pimm-gallery-20260903-(?:molding|end-caps)\.webp|pimm-bento__tile--(?:workshop|parts)|figcaption/);
  assert.doesNotMatch(css, /pimm-bento__tile--(?:workshop|parts)/);
  assert.match(css, /\.pimm-machine\[data-page-model="30G"\] \.pimm-bento__tile \{[^}]*border: 0;/);
  assert.doesNotMatch(css, /\.pimm-bento__tile--configuration \{[^}]*border:/);
  assert.match(css, /\.pimm-bento__tile--capacity \{ grid-area: capacity; aspect-ratio: 1600 \/ 2200; \}/);
  assert.match(css, /\.pimm-bento__tile--tooling \{ grid-area: tooling; aspect-ratio: 1600 \/ 2200; \}/);
  assert.match(css, /\.pimm-bento__tile--air-pressure \{ grid-area: air-pressure; aspect-ratio: 8 \/ 11; \}/);
  assert.match(css, /\.pimm-bento__tile--plunger \{ grid-area: plunger; aspect-ratio: 16 \/ 11; \}/);
  assert.match(css, /\.pimm-bento__tile--temperature \{ grid-area: temperature; \}/);
  assert.match(css, /grid-template-areas: "capacity controls controls" "temperature temperature tooling" "air-pressure plunger plunger" "configuration configuration configuration";/);
  assert.match(css, /@media \(max-width: 999px\)[\s\S]*?grid-template-columns: repeat\(2, minmax\(0, 1fr\)\);[\s\S]*?grid-template-areas: "controls controls" "capacity tooling" "temperature temperature" "air-pressure plunger" "configuration configuration";/);
  assert.match(css, /@media \(min-width: 750px\) and \(max-width: 999px\)[\s\S]*?\.pimm-bento__tile--plunger \.pimm-bento__copy \{[\s\S]*?width: 64%;[\s\S]*?margin: 7% 0 0 5%;[\s\S]*?\.pimm-bento__tile--plunger \.pimm-bento__copy p \{[\s\S]*?max-width: 24ch;[\s\S]*?\.pimm-bento__tile--plunger \.pimm-bento__media :is\(img, video\) \{[\s\S]*?object-position: 90% center;/);
  assert.match(css, /@media \(max-width: 749px\)[\s\S]*?\.pimm-bento \{ gap: 10px; \}/);
  assert.match(css, /@media \(max-width: 749px\)[\s\S]*?font-size: 2rem !important/);
  assert.match(css, /\.pimm-bento__tile--air-pressure \.pimm-bento__copy \{[\s\S]*?align-self: start;[\s\S]*?margin-top: 7%;/);
  assert.doesNotMatch(css, /\.pimm-bento__tile--air-pressure::after/);
  assert.match(css, /\.pimm-bento__tile--plunger \.pimm-bento__copy \{[\s\S]*?width: 38%;[\s\S]*?margin-left: 5%;/);
  assert.match(css, /\.pimm-bento__copy h3 \{[^}]*font-size: clamp\(2\.8rem, 1\.6rem \+ 1\.7vw, 4rem\) !important/);
  assert.match(css, /\.pimm-bento__copy p \{[^}]*font-size: 1\.6rem;[^}]*line-height: 1\.5/);
  assert.match(css, /\.pimm-story--30g:lang\(th\) :is\(h2, h3\) \{[^}]*letter-spacing: normal !important/);
});

test('bento uses Outfit 700 headlines and 400 text with locale-aware spacing', async () => {
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  const heading = css.match(/\.pimm-bento__copy h3 \{([^}]+)\}/)[1];
  const body = css.match(/\.pimm-bento__copy p \{([^}]+)\}/)[1];
  assert.match(heading, /font-weight: 700 !important/);
  assert.match(heading, /font-family: var\(--pimm-bento-font\)/);
  assert.match(body, /font-family: var\(--pimm-bento-font\)/);
  assert.match(heading, /max-width: 16ch/);
  assert.match(heading, /font-kerning: normal/);
  assert.match(body, /font-weight: 400/);
  assert.match(body, /max-width: 38ch/);
  assert.match(css, /\.pimm-bento:lang\(en\) \.pimm-bento__copy h3 \{ text-transform: uppercase; \}/);
  assert.match(css, /\.pimm-bento:lang\(th\) \.pimm-bento__copy h3 \{[^}]*line-height: 1\.3 !important;[^}]*letter-spacing: normal !important/);
  const bento = css.slice(css.indexOf('.pimm-bento {'), css.indexOf('.pimm-machine__ownership {'));
  assert.doesNotMatch(bento, /font-size: 1\.5rem/);
  assert.doesNotMatch(bento, /@font-face/);
  assert.match(bento, /--pimm-bento-font: 'Outfit', 'IBM Plex Sans Thai', sans-serif/);
  assert.doesNotMatch(bento, /figcaption/);
});

test('Outfit font weights are locally bundled with a redistribution license', async () => {
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  const faces = [...css.matchAll(/@font-face \{([^}]+)\}/g)].map(match => match[1]);
  assert.equal(faces.length, 2);
  for (const face of faces) {
    assert.match(face, /font-family: 'Outfit'/);
    assert.match(face, /font-weight: 400 700/);
    assert.match(face, /font-display: swap/);
    const file = face.match(/url\('\.\/([^']+)'\)/)[1];
    const bytes = await readFile(new URL(file, assetsUrl));
    assert.equal(bytes.subarray(0, 4).toString('ascii'), 'wOF2');
    assert.ok(bytes.length > 1000 && bytes.length < 100000);
  }
  const license = await readFile(new URL('Outfit-OFL.txt', assetsUrl), 'utf8');
  assert.match(license, /The Outfit Project Authors/);
  assert.match(license, /SIL OPEN FONT LICENSE Version 1.1/);
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

test('30G bento uses approved full-tile native-size renders and control animations', async () => {
  const manifest = JSON.parse(await readFile(new URL('assets/pimm-bento-r12-assets.v1.json', rootUrl), 'utf8'));
  assert.equal(manifest.generation, 'bento-20260903-r12');
  const previousManifest = await readFile(new URL(`assets/${manifest.previous_manifest}`, rootUrl));
  assert.equal(sha256(previousManifest), manifest.previous_manifest_sha256);
  assert.equal(manifest.assets.length, 4);
  const story = await readFile(new URL('snippets/pimm-30g-product-story.liquid', rootUrl), 'utf8');
  assert.equal((story.match(/pimm-bento__tile--render/g) ?? []).length, 7);
  for (const asset of manifest.assets) {
    const approvalBytes = await readFile(new URL(asset.approval, rootUrl));
    const approval = JSON.parse(approvalBytes);
    assert.equal(approval.decision, 'approved');
    assert.ok((approval.generations ?? [approval.generation]).includes(asset.generation));
    assert.equal(asset.approval_sha256, sha256(approvalBytes));
    const bytes = await readFile(new URL(`assets/${asset.filename}`, rootUrl));
    assert.equal(sha256(bytes), asset.sha256);
    assert.equal(bytes.toString('ascii', 12, 16), 'VP8L');
    const packed = bytes.readUInt32LE(21);
    assert.deepEqual([(packed & 0x3fff) + 1, ((packed >>> 14) & 0x3fff) + 1], asset.size);
    assert.ok(story.includes(asset.filename));
    assert.ok(story.includes(`width="${asset.size[0]}" height="${asset.size[1]}"`));
  }
  const configuration = manifest.assets.find(asset => asset.shot === 'configuration');
  assert.equal(configuration.generation, 'bento-20260903-r12-white-detail');
  assert.equal(manifest.assets.find(asset => asset.shot === 'controls').generation, 'bento-20260903-r10-orbit');
  assert.doesNotMatch(story, /pimm-bento-20260903-r06|pimm-bento-20260903-r11-30g-configuration/);
  assert.equal((story.match(/<pimm-bento-orbit /g) ?? []).length, 6);
  assert.ok(story.includes(manifest.animation.filename));
  assert.deepEqual(manifest.animation.size, [2400, 1200]);
  assert.equal(manifest.animation.fps, 24);
  assert.equal(manifest.animation.frames, 192);
  const video = await readFile(new URL(`assets/${manifest.animation.filename}`, rootUrl));
  assert.equal(sha256(video), manifest.animation.sha256);
  assert.equal(video.subarray(4, 8).toString(), 'ftyp');
  const fixtureManifest = JSON.parse(await readFile(new URL('assets/pimm-bento-r13-fixture-motion.v1.json', rootUrl), 'utf8'));
  assert.equal(fixtureManifest.schema, 'maliev.pimm-bento-fixture-motion/v1');
  assert.deepEqual(fixtureManifest.size, [800, 1100]);
  assert.equal(fixtureManifest.aspect_ratio, '8:11');
  assert.equal(fixtureManifest.fps, 24);
  assert.equal(fixtureManifest.frames, 912);
  assert.equal(fixtureManifest.duration_seconds, 38);
  assert.ok(story.includes(fixtureManifest.filename));
  const fixtureVideo = await readFile(new URL(`assets/${fixtureManifest.filename}`, rootUrl));
  assert.equal(sha256(fixtureVideo), fixtureManifest.sha256);
  assert.equal(fixtureVideo.subarray(4, 8).toString(), 'ftyp');
  const controlManifest = JSON.parse(await readFile(new URL('assets/pimm-bento-r30-control-motion.v1.json', rootUrl), 'utf8'));
  assert.equal(controlManifest.schema, 'maliev.pimm-bento-control-motion/v1');
  assert.equal(controlManifest.assets.length, 3);
  assert.deepEqual(controlManifest.assets.map(asset => asset.size), [[400, 550], [1440, 960], [960, 660]]);
  assert.deepEqual(controlManifest.assets.map(asset => asset.fps), [24, 24, 24]);
  assert.deepEqual(controlManifest.assets.map(asset => asset.frames), [288, 336, 288]);
  for (const asset of controlManifest.assets) {
    assert.ok(story.includes(asset.filename));
    assert.ok(story.includes(asset.poster));
    const videoBytes = await readFile(new URL(`assets/${asset.filename}`, rootUrl));
    const posterBytes = await readFile(new URL(`assets/${asset.poster}`, rootUrl));
    assert.equal(videoBytes.length, asset.bytes);
    assert.equal(posterBytes.length, asset.poster_bytes);
    assert.equal(sha256(videoBytes).toLowerCase(), asset.sha256);
    assert.equal(sha256(posterBytes).toLowerCase(), asset.poster_sha256);
    assert.equal(videoBytes.subarray(4, 8).toString(), 'ftyp');
    assert.equal(posterBytes.toString('ascii', 12, 16), 'VP8L');
  }
  const section = await readFile(new URL('sections/maliev-pimm-machine-product.liquid', rootUrl), 'utf8');
  assert.match(section, /if page_model == '30G'[\s\S]*?pimm-bento-orbit.js[\s\S]*?defer="defer"[\s\S]*?endif/);
  assert.match(section, /if page_model == '30G'[\s\S]*?pimm-bento-spin\.css[\s\S]*?pimm-bento-spin\.js[\s\S]*?defer="defer"[\s\S]*?endif/);
  const motionManifest = JSON.parse(await readFile(new URL('assets/pimm-bento-r27-motion-delivery.v1.json', rootUrl), 'utf8'));
  assert.equal(motionManifest.schema, 'maliev.pimm-bento-motion-delivery/v1');
  assert.deepEqual(motionManifest.capacity.size, [800, 1100]);
  assert.equal(motionManifest.capacity.frames, 192);
  assert.equal(motionManifest.capacity.duration_seconds, 8);
  assert.equal(motionManifest.configuration.total_frames, 840);
  assert.equal(motionManifest.configuration.frames_per_row, 120);
  assert.equal(motionManifest.configuration.rows, 7);
  assert.equal(motionManifest.configuration.generation, 'bento-20260903-r28-final-motion-review');
  assert.deepEqual(motionManifest.configuration.size, [1200, 600]);
  assert.ok(story.includes(motionManifest.capacity.filename));
  assert.ok(story.includes(motionManifest.configuration.file_template.replace('{row}', '00').replace('{frame}', '0001')));
  assert.match(story, /<pimm-bento-spin[\s\S]*?data-frame-source="\{\{[^}]+asset_url[^}]+\}\}"[\s\S]*?data-frame-count="120"[\s\S]*?data-row-count="7"[\s\S]*?data-default-row="3"[\s\S]*?data-row-step="2"/);
  const capacityMotion = await readFile(new URL(`assets/${motionManifest.capacity.filename}`, rootUrl));
  assert.equal(sha256(capacityMotion).toLowerCase(), motionManifest.capacity.sha256);
  assert.equal(capacityMotion.length, motionManifest.capacity.bytes);
  const spinNames = (await readdir(assetsUrl))
    .filter(name => /^pimm-bento-20260904-r28-30g-configuration-r\d{2}-f\d{4}\.webp$/.test(name))
    .sort();
  assert.equal(spinNames.length, motionManifest.configuration.total_frames);
  const spinHashes = [];
  let spinBytes = 0;
  for (const name of spinNames) {
    const bytes = await readFile(new URL(`assets/${name}`, rootUrl));
    spinBytes += bytes.length;
    spinHashes.push(`${name}:${sha256(bytes).toLowerCase()}`);
  }
  assert.equal(spinBytes, motionManifest.configuration.bytes);
  assert.equal(sha256(Buffer.from(spinHashes.join('\n'))).toLowerCase(), motionManifest.configuration.aggregate_sha256);
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  assert.match(css, /\.pimm-bento__tile--render \.pimm-bento__media \{ position: absolute; inset: 0; \}/);
  assert.doesNotMatch(css, /(?:^|[;\s])filter:/);
  assert.doesNotMatch(css, /\.pimm-bento__tile--configuration \{[^}]*border:/);
  assert.match(css, /\.pimm-bento__tile--configuration :is\(img, canvas\) \{ object-position: 76% center; \}/);
});

test('bento compact captions retain matching locale keys and only replace prose at narrow widths', async () => {
  for (const name of await readdir(new URL('locales/', rootUrl))) {
    if (!name.endsWith('.json') || name.endsWith('.schema.json')) continue;
    const text = await readFile(new URL(`locales/${name}`, rootUrl), 'utf8');
    const locale = JSON.parse(text.replace(/\/\*[\s\S]*?\*\//g, ''));
    assert.deepEqual(Object.keys(locale.pimm_bento).sort(), ['air_pressure_body', 'air_pressure_compact', 'air_pressure_heading', 'capacity_body', 'capacity_compact', 'configuration_compact', 'controls_body', 'controls_compact', 'controls_heading', 'plunger_body', 'plunger_compact', 'plunger_heading', 'temperature_body', 'temperature_compact', 'temperature_heading', 'tooling_body', 'tooling_compact', 'tooling_heading']);
    assert.ok(Object.values(locale.pimm_bento).every(value => typeof value === 'string' && value.length > 0));
  }
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', rootUrl), 'utf8');
  assert.match(css, /\.pimm-bento__text-compact \{ display: none; \}/);
  assert.match(css, /@media \(max-width: 749px\)[\s\S]*?\.pimm-bento__text-full \{ display: none; \}/);
});

test('30G bento describes features in both languages without changing the demo card or other models', async () => {
  const source = await readFile(new URL('snippets/pimm-30g-product-story.liquid', rootUrl), 'utf8');
  const engine = new Liquid({ strictFilters: true });
  engine.registerTag('doc', { parse(_token, tokens) { while (tokens.length && tokens.shift().name !== 'enddoc') {} }, render() { return ''; } });
  engine.registerFilter('asset_url', value => `/assets/${value}`);
  for (const name of ['en.default', 'th']) {
    const locale = JSON.parse((await readFile(new URL(`locales/${name}.json`, rootUrl), 'utf8')).replace(/\/\*[\s\S]*?\*\//g, ''));
    engine.registerFilter('t', key => {
      const value = key.split('.').reduce((node, part) => node?.[part], locale);
      assert.equal(typeof value, 'string', key);
      return value;
    });
    const html = await engine.parseAndRender(source, { story_asset_set: 'pimm-master-20260901-r05-30g' });
    for (const value of Object.values(locale.pimm_bento)) assert.ok(html.includes(value));
    assert.ok(html.includes(locale.products.pimm_machine.specs.capacity.label));
    assert.ok(html.includes(locale.products.pimm_machine.purchase.heading));
    assert.ok(html.includes(locale.products.pimm_machine.purchase.body));
    assert.doesNotMatch(html, /Inspect pneumatic controls|Confirm your mold path|Include the part, runner/);
    assert.equal((html.match(/pimm-bento__tile--render/g) ?? []).length, 7);
    assert.equal((await engine.parseAndRender(source, { story_asset_set: 'pimm-master-20260901-r05-50g' })).trim(), '');
    const copy = locale.pimm_bento;
    if (name === 'en.default') {
      for (const key of ['capacity_body', 'capacity_compact']) assert.match(copy[key], /30g.*aluminum melt bore.*heater bands.*resin/i);
     assert.equal(copy.controls_heading, 'Pneumatic operation');
      assert.equal(copy.plunger_heading, 'Simple injection control');
      assert.equal(copy.plunger_body, 'A simple pneumatic hand toggle controls injection and retraction, delivering up to 876 kgf of cylinder force for confident, repeatable shots.');
      assert.equal(copy.plunger_compact, 'One pneumatic toggle controls up to 876 kgf of injection force.');
      assert.equal(copy.air_pressure_heading, 'Control force with air');
      assert.equal(copy.temperature_heading, 'Precise temperature control');
      assert.equal(copy.tooling_heading, 'Flexible fixture mounting');
      for (const key of ['tooling_body', 'tooling_compact']) assert.match(copy[key], /custom fixtures/);
    } else {
      for (const key of ['capacity_body', 'capacity_compact']) assert.match(copy[key], /30.*อะลูมิเนียม.*ฮีตเตอร์.*เม็ดพลาสติก/);
     assert.equal(copy.controls_heading, 'ขับเคลื่อนด้วยระบบลม');
      assert.equal(copy.plunger_heading, 'ควบคุมการฉีดได้ง่าย');
      assert.equal(copy.plunger_body, 'โยกวาล์วลมด้วยมือเพื่อฉีดหรือดึงลูกสูบกลับ พร้อมแรงขับจากกระบอกลมสูงสุด 876 kgf เพื่อให้แต่ละช็อตมั่นใจและทำซ้ำได้');
      assert.equal(copy.plunger_compact, 'โยกวาล์วลมครั้งเดียว ควบคุมแรงฉีดได้สูงสุด 876 kgf');
      assert.equal(copy.air_pressure_heading, 'ควบคุมแรงฉีดด้วยแรงดันลม');
      assert.equal(copy.temperature_heading, 'ควบคุมอุณหภูมิอย่างแม่นยำ');
    }
  }
});
