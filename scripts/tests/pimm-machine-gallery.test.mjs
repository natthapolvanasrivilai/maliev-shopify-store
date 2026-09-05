import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { Liquid } from 'liquidjs';

const root = new URL('../../', import.meta.url);
const read = path => readFile(new URL(path, root), 'utf8');
const parse = source => JSON.parse(source.replace(/^\s*\/\*[\s\S]*?\*\/\s*/, ''));
async function render(blocks, language = 'en', designMode = false) {
  const locale = parse(await read(`locales/${language === 'en' ? 'en.default' : language}.json`));
  const engine = new Liquid({ root: fileURLToPath(new URL('snippets/', root)), extname: '.liquid', strictFilters: true });
  engine.registerTag('doc', { parse(_token, tokens) { while (tokens.length && tokens.shift().name !== 'enddoc') {} }, render() { return ''; } });
  engine.registerFilter('asset_url', value => `/assets/${value}`);
  engine.registerFilter('stylesheet_tag', value => `<link rel="stylesheet" href="${value}">`);
  engine.registerFilter('image_url', value => value?.url ?? '');
  engine.registerFilter('t', key => key.split('.').reduce((value, segment) => value?.[segment], locale) ?? `MISSING:${key}`);
  return engine.renderFile('pimm-machine-gallery', { section: { id: 'test', blocks }, request: { design_mode: designMode } });
}
const external = id => ({ type: 'youtube', id });
const videoBlock = (id = 'SlCkqUcpZ_Y', settings = {}) => ({ type: 'gallery_video', settings: { external_video: external(id), use_default_preview: true, ...settings } });

test('gallery is dedicated to 30G and sits between ownership and demo booking', async () => {
  const section = await read('sections/maliev-pimm-machine-product.liquid');
  assert.match(section, /if page_model == '30G' %}\s*{% render 'pimm-machine-gallery'/);
  assert.ok(section.indexOf("render 'pimm-ownership'") < section.indexOf("render 'pimm-machine-gallery'"));
  assert.ok(section.indexOf("render 'pimm-machine-gallery'") < section.indexOf("render 'pimm-purchase-qualification'"));
  const schema = JSON.parse(section.match(/{% schema %}([\s\S]*?){% endschema %}/)[1]);
  assert.equal(schema.max_blocks, 50);
  assert.equal(schema.blocks.find(block => block.type === 'model').limit, 2);
  assert.ok(schema.blocks.some(block => block.type === '@app'));
  for (const type of ['gallery_image', 'gallery_video']) assert.ok(schema.blocks.some(block => block.type === type));
});

test('default gallery contains only three real videos and preserves their destinations', async () => {
  const template = parse(await read('templates/product.pimm-configurator.json')).sections.main;
  const blocks = template.block_order.map(id => {
    const block = structuredClone(template.blocks[id]);
    if (block.settings.external_video) block.settings.external_video = external(new URL(block.settings.external_video).searchParams.get('v'));
    return block;
  });
  const output = await render(blocks);
  assert.equal((output.match(/data-gallery-item /g) ?? []).length, 3);
  assert.equal((output.match(/data-gallery-preview /g) ?? []).length, 3);
  assert.doesNotMatch(output, /<iframe|MISSING:/);
  for (const id of ['SlCkqUcpZ_Y', 'PHqab73X5C0', 'zoRajgCbsko']) assert.ok(output.includes(`watch?v=${id}`));
  assert.match(output, /data-src="\/assets\/pimm-gallery-20260903-demonstration.mp4"/);
  assert.doesNotMatch(output, /<video[^>]*\ssrc=/);
  assert.doesNotMatch(output, /pimm-master-|data-kind="image"/);
});

test('merchant photo blocks require an uploaded photo and never insert render fallbacks', async () => {
  assert.equal((await render([{ type: 'gallery_image', settings: { default_image: 'controls' } }])).trim(), '');
  const output = await render([{ type: 'gallery_image', settings: { image: { url: 'https://cdn.test/real-photo.jpg' }, title: 'Workshop photo' } }]);
  assert.match(output, /data-kind="image"/);
  assert.match(output, /href="https:\/\/cdn.test\/real-photo.jpg"/);
  assert.match(output, /Workshop photo/);
  assert.doesNotMatch(output, /pimm-master-|data-gallery-preview/);
  const section = await read('sections/maliev-pimm-machine-product.liquid');
  const schema = JSON.parse(section.match(/{% schema %}([\s\S]*?){% endschema %}/)[1]);
  const settings = schema.blocks.find(block => block.type === 'gallery_image').settings;
  assert.ok(settings.some(setting => setting.type === 'image_picker'));
  assert.ok(!settings.some(setting => setting.id === 'default_image'));
});

test('empty blocks are omitted outside editor, and all gallery UI has Thai parity', async () => {
  assert.equal((await render([])).trim(), '');
  assert.equal((await render([{ type: 'gallery_video', settings: {} }])).trim(), '');
  assert.match(await render([], 'en', true), /Add gallery/);
  const en = parse(await read('locales/en.default.json')).pimm_gallery;
  const th = parse(await read('locales/th.json')).pimm_gallery;
  assert.deepEqual(Object.keys(en).sort(), Object.keys(th).sort());
  const output = await render([videoBlock()], 'th');
  assert.match(output, /ชมการทำงานของ 30G/);
  assert.doesNotMatch(output, /MISSING:|Machine demonstration/);
});

test('changing video cannot silently retain unrelated native preview; hosted media takes priority', async () => {
  assert.doesNotMatch(await render([videoBlock('abcdefghijk')]), /data-gallery-preview/);
  const output = await render([videoBlock('SlCkqUcpZ_Y', {
    full_video: { sources: [{ format: 'mp4', url: 'https://cdn.test/full.mp4' }], preview_image: { url: 'https://cdn.test/full.jpg' } },
    preview_video: { sources: [{ format: 'mp4', url: 'https://cdn.test/clip.mp4' }], preview_image: { url: 'https://cdn.test/clip.jpg' } },
  })]);
  assert.match(output, /href="https:\/\/cdn.test\/full.mp4"/);
  assert.match(output, /data-src="https:\/\/cdn.test\/clip.mp4"/);
  assert.doesNotMatch(output, /youtube.com\/watch|pimm-gallery-20260903/);
});

test('captions remain escaped and 48 items fit alongside the two model records', async () => {
  const output = await render(Array.from({ length: 48 }, () => videoBlock('SlCkqUcpZ_Y', { title: '<script>alert(1)</script>' })));
  assert.equal((output.match(/data-gallery-item /g) ?? []).length, 48);
  assert.doesNotMatch(output, /<script>alert/);
  assert.match(output, /&lt;script&gt;/);
});

test('gallery uses compact equal-weight thumbnails for a growing media library', async () => {
  const css = await read('assets/maliev-pimm-gallery.css');
  assert.match(css, /grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/);
  assert.match(css, /@media \(min-width: 700px\)[\s\S]*?repeat\(3, minmax\(0, 1fr\)\)/);
  assert.match(css, /@media \(min-width: 1100px\)[\s\S]*?repeat\(4, minmax\(0, 1fr\)\)/);
  assert.match(css, /\.pimm-gallery__media[^}]*aspect-ratio:\s*4 \/ 3/);
  assert.doesNotMatch(css, /\.pimm-gallery__item:first-child/);
});

async function controller() {
  let Controller;
  const document = { hidden: false };
  vm.runInNewContext(await read('assets/maliev-pimm-gallery.js'), {
    HTMLElement: class {}, customElements: { get() {}, define(_name, value) { Controller = value; } }, document,
  });
  const element = new Controller();
  Object.assign(element, { isConnected: true, motion: { matches: false }, connection: { saveData: false }, dialog: { open: false } });
  return { element, document };
}

test('autoplay gates cover offscreen, hidden tab, reduced motion, data saving, modal, failure and removal', async () => {
  const { element, document } = await controller();
  const record = { visible: true, failed: false };
  assert.equal(element.canPreview(record), true);
  for (const [target, key, value] of [
    [record, 'visible', false], [record, 'failed', true], [document, 'hidden', true],
    [element.motion, 'matches', true], [element.connection, 'saveData', true], [element.dialog, 'open', true],
    [element, 'isConnected', false],
  ]) {
    const previous = target[key]; target[key] = value;
    assert.equal(element.canPreview(record), false, key);
    target[key] = previous;
  }
});

test('native short segments loop within bounds and normalize invalid input', async () => {
  const { element } = await controller();
  const record = { item: { dataset: { previewStart: '10', previewLength: '6' } }, video: { duration: 40, currentTime: 16 } };
  element.seekPreview(record); assert.equal(record.video.currentTime, 10);
  record.video.currentTime = 14; element.seekPreview(record); assert.equal(record.video.currentTime, 14);
  record.item.dataset.previewStart = '-40'; element.seekPreview(record, true); assert.equal(record.video.currentTime, 0);
  record.item.dataset.previewStart = '100'; element.seekPreview(record, true); assert.equal(record.video.currentTime, 39.75);
});

test('autoplay rejection retains a usable still instead of retrying endlessly', async () => {
  const { element } = await controller();
  const record = { visible: true, failed: false, video: {
    dataset: { src: 'clip.mp4' }, paused: true, hidden: true,
    getAttribute() { return null; }, play() { return Promise.reject(new Error('NotAllowedError')); }, pause() {},
  } };
  element.previews = [record];
  element.syncPreviews();
  await Promise.resolve(); await Promise.resolve();
  assert.equal(record.failed, true); assert.equal(record.video.hidden, true);
  assert.equal(element.canPreview(record), false);
});

test('six-second native preview assets match source provenance and checksums', async () => {
  const manifest = JSON.parse(await read('docs/pimm-gallery-media.json'));
  assert.equal(manifest.assets.length, 3);
  assert.equal(manifest.encoding.audioStreams, 0);
  assert.equal(manifest.encoding.durationSeconds, 6);
  for (const item of manifest.assets) {
    for (const asset of [item.video, item.poster]) {
      const bytes = await readFile(new URL(asset.path, root));
      assert.equal(bytes.length, asset.bytes);
      assert.equal(createHash('sha256').update(bytes).digest('hex'), asset.sha256);
    }
  }
});
