import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const stylesheets = [
  new URL('../../assets/base.css', import.meta.url),
  new URL('../../assets/template-giftcard.css', import.meta.url),
];

test('global styles do not hide empty div hosts that render through shadow DOM', async () => {
  for (const stylesheet of stylesheets) {
    const source = await readFile(stylesheet, 'utf8');

    assert.doesNotMatch(
      source,
      /(?:^|,)\s*div:empty\s*(?:,|\{)/m,
      `${stylesheet.pathname} must allow external shadow-DOM hosts to remain visible`,
    );
  }
});
