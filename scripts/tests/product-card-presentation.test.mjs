import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../', import.meta.url);

test('collection product cards use edge-to-edge scheme-aware media', async () => {
  const styles = await readFile(new URL('assets/maliev-commerce.css', root), 'utf8');

  assert.match(styles, /\.mc-product-card--catalog\s*\{[\s\S]*background: rgb\(var\(--color-background\)\);[\s\S]*color: rgb\(var\(--color-foreground\)\);/);
  assert.match(styles, /\.mc-product-card--catalog \.mc-product-card__media\s*\{[\s\S]*background: rgb\(var\(--color-background\)\);/);
  assert.match(styles, /\.mc-product-card--catalog :where\([^)]+\)\s*\{[\s\S]*color: rgba\(var\(--color-foreground\), 0\.7\);/);
  assert.match(styles, /\.mc-product-card--catalog \.mc-product-card__badge\s*\{[\s\S]*background: rgb\(var\(--color-background\)\);[\s\S]*color: rgb\(var\(--color-foreground\)\);/);
  assert.match(styles, /\.mc-product-card--catalog \.mc-product-card__image,[\s\S]*object-fit: cover;[\s\S]*padding: 0;/);
});

test('collection sale prices lead with the actual price and demote the comparison', async () => {
  const [card, price, styles] = await Promise.all([
    readFile(new URL('snippets/card-product.liquid', root), 'utf8'),
    readFile(new URL('snippets/price.liquid', root), 'utf8'),
    readFile(new URL('assets/maliev-commerce.css', root), 'utf8'),
  ]);

  assert.match(card, /render 'price'[\s\S]*price_context: catalog_layout/);
  assert.match(price, /if price_context[\s\S]*mc-price__sale-row--current[\s\S]*sale_price[\s\S]*mc-price__current[\s\S]*mc-price__sale-row--compare[\s\S]*regular_price[\s\S]*mc-price__compare/);
  assert.match(styles, /\.mc-product-card--catalog \.mc-price__sale-row--current \.mc-price__current\s*\{[\s\S]*font-size: 1\.75rem;[\s\S]*font-weight: 600;/);
  assert.match(styles, /\.mc-product-card--catalog \.mc-price__sale-row--compare\s*\{[\s\S]*font-size: 1\.2rem;/);
});
