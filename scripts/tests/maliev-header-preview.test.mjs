import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../', import.meta.url);

test('desktop mega menus update their feature card from hover and keyboard focus', async () => {
  const [header, script, styles, panel, menuLink, serviceLink, group] = await Promise.all([
    readFile(new URL('sections/maliev-header.liquid', root), 'utf8'),
    readFile(new URL('assets/maliev-header.js', root), 'utf8'),
    readFile(new URL('assets/maliev-chrome.css', root), 'utf8'),
    readFile(new URL('snippets/maliev-mega-panel.liquid', root), 'utf8'),
    readFile(new URL('snippets/maliev-menu-link.liquid', root), 'utf8'),
    readFile(new URL('snippets/maliev-service-link.liquid', root), 'utf8'),
    readFile(new URL('sections/header-group.json', root), 'utf8'),
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
  assert.equal(settings['service-3d-printing'].settings.image_preset, 'printed');
  assert.equal(settings['service-cnc-machining'].settings.image_preset, 'molds');
  assert.notEqual(settings['service-3d-scanning'].settings.image_preset, 'none');
});
