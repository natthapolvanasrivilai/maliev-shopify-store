import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../', import.meta.url);

test('desktop mega menus update their feature card from hover and keyboard focus', async () => {
  const [header, script, styles, panel, menuLink, serviceLink, group, assetManifest] = await Promise.all([
    readFile(new URL('sections/maliev-header.liquid', root), 'utf8'),
    readFile(new URL('assets/maliev-header.js', root), 'utf8'),
    readFile(new URL('assets/maliev-chrome.css', root), 'utf8'),
    readFile(new URL('snippets/maliev-mega-panel.liquid', root), 'utf8'),
    readFile(new URL('snippets/maliev-menu-link.liquid', root), 'utf8'),
    readFile(new URL('snippets/maliev-service-link.liquid', root), 'utf8'),
    readFile(new URL('sections/header-group.json', root), 'utf8'),
    readFile(new URL('assets/maliev-nav-preview-20260905.v1.json', root), 'utf8'),
  ]);

  assert.match(`${header}\n${panel}`, /data-mc-menu-feature/g);
  for (const snippet of [menuLink, serviceLink]) {
    assert.match(snippet, /data-mc-menu-preview/);
    assert.match(snippet, /data-preview-title=/);
    assert.match(snippet, /data-preview-description=/);
    assert.match(snippet, /data-preview-url=/);
    assert.match(snippet, /data-preview-image=/);
  }
  assert.match(script, /panel\.addEventListener\('pointerover'/);
  assert.match(script, /panel\.addEventListener\('focusin'/);
  assert.match(script, /panel\.addEventListener\('pointerleave', resetPreview/);
  assert.match(script, /featureImage\.setAttribute\('src', state\.image\)/);
  assert.match(script, /reducedMotionQuery\.matches/);
  assert.match(styles, /\.mc-menu-link--compact:is\(:hover, :focus-visible, \.is-preview-active\)/);
  const settings = JSON.parse(group.replace(/^\s*\/\*[\s\S]*?\*\/\s*/, '')).sections.header.blocks;
  const previewBlocks = Object.values(settings).filter(({ type }) =>
    ['menu_detail', 'manufacturing_service'].includes(type),
  );
  const subjectPresets = new Map();
  const presetSubjects = new Map();

  for (const block of previewBlocks) {
    const subject = block.settings.link_title ?? block.settings.title;
    const preset = block.settings.image_preset;
    assert.match(preset, /^nav-/);
    assert.equal(subjectPresets.get(subject) ?? preset, preset, `${subject} must use one consistent image`);
    assert.equal(presetSubjects.get(preset) ?? subject, subject, `${preset} must not be reused by another subject`);
    subjectPresets.set(subject, preset);
    presetSubjects.set(preset, subject);
  }

  assert.equal(subjectPresets.size, 17);
  assert.equal(presetSubjects.size, 17);
  assert.equal(settings['service-3d-printing'].settings.image_preset, 'nav-3d-printing');
  assert.equal(settings['service-cnc-machining'].settings.image_preset, 'nav-cnc');
  assert.equal(settings['service-3d-scanning'].settings.image_preset, 'nav-scanning');

  const manifest = JSON.parse(assetManifest);
  assert.equal(manifest.version, 'maliev-nav-preview.v1');
  assert.equal(manifest.assets.length, 17);
  assert.deepEqual(new Set(manifest.assets.map(({ preset }) => preset)), new Set(presetSubjects.keys()));

  const files = await Promise.all(
    manifest.assets.map(async ({ file }) => ({
      file,
      content: await readFile(new URL(`assets/${file}`, root)),
    })),
  );
  const hashes = files.map(({ content }) => createHash('sha256').update(content).digest('hex'));
  assert.equal(new Set(hashes).size, 17, 'every menu subject must have a distinct generated image');
  for (const { file, content } of files) {
    assert.ok(content.byteLength > 20_000, `${file} must contain a production-quality image`);
  }
});
