import assert from 'node:assert/strict';
import test from 'node:test';
import http from 'node:http';
import { once } from 'node:events';
import { createPreviewServer, previewDestination } from '../local-preview-router.mjs';

const key = 'local-test-preview-key-only';
const collection = '/collections/เครื่องฉีดพลาสติก';
const cases = [
  [collection, '', 'pimm-collection-preview', '54823758627095'],
  [encodeURI(collection), '', 'pimm-collection-preview', '54823758627095'],
  [`/th${encodeURI(collection)}`, '/th', 'pimm-collection-preview', '54823758627095'],
  ['/en/products/pneumatic-injection-molding-machine', '/en', 'pimm-configurator', '54823758627095'],
  ['/products/pneumatic-injection-molding-machine-50g', '', 'pimm-configurator', '54823758659863'],
  ['/th/products/pneumatic-injection-molding-machine-50g?variant=53037201096983', '/th', 'pimm-configurator', '54823758659863'],
  ['/products/pneumatic-injection-molding-machine?variant=50038784229655', '', 'pimm-configurator', '54823758627095'],
  ['/products/pimm-pneumatic-injection-molding-machine-development?variant=54823758659863', '', 'pimm-configurator', '54823758659863'],
  [`${collection}/products/pneumatic-injection-molding-machine-50g`, '', 'pimm-configurator', '54823758659863'],
];
for (const [path, locale, view, variant] of cases) {
  test(`normal route selects correct preview: ${path}`, () => {
    const result = new URL(previewDestination(path, key), 'http://127.0.0.1:9494');
    assert.equal(result.pathname, `${locale}/products_preview`);
    assert.equal(result.searchParams.get('preview_key'), key);
    assert.equal(result.searchParams.get('view'), view);
    assert.equal(result.searchParams.get('variant'), variant);
  });
}

test('unrelated, API, malformed and existing preview paths are never redirected', () => {
  for (const path of ['/', '/collections', '/collections/molds', '/products/other', '/cart/add.js',
    '/products/pneumatic-injection-molding-machine.js', '/products_preview?view=pimm-configurator',
    '/th/products_preview?view=pimm-collection-preview', '//evil.example/products/pneumatic-injection-molding-machine',
    'https://evil.example/products/pneumatic-injection-molding-machine', '/products/%ZZ']) {
    assert.equal(previewDestination(path, key), null, path);
  }
});

test('caller cannot supply preview credentials or another view', () => {
  const result = new URL(previewDestination(`${collection}?preview_key=attacker&view=old&variant=999`, key), 'http://localhost');
  assert.equal(result.searchParams.get('preview_key'), key);
  assert.equal(result.searchParams.get('view'), 'pimm-collection-preview');
  assert.equal(result.searchParams.get('variant'), '54823758627095');
});

test('HTTP router redirects document requests but preserves unrelated and write requests', async (t) => {
  const upstream = http.createServer(async (req, res) => {
    let body = '';
    for await (const chunk of req) body += chunk;
    res.writeHead(201, { 'content-type': 'application/json', 'set-cookie': 'preview=ok; Path=/' });
    res.end(JSON.stringify({ path: req.url, method: req.method, body }));
  }).listen(0, '127.0.0.1');
  await once(upstream, 'listening');
  t.after(() => upstream.close());
  const server = createPreviewServer({ key, upstreamPort: upstream.address().port }).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => server.close());
  const base = `http://127.0.0.1:${server.address().port}`;
  for (const method of ['GET', 'HEAD']) {
    const response = await fetch(`${base}${encodeURI(collection)}`, { method, redirect: 'manual' });
    assert.equal(response.status, 302);
    assert.equal(response.headers.get('cache-control'), 'no-store');
    assert.match(response.headers.get('location'), /^\/products_preview\?/);
  }
  for (const [method, path, body] of [['GET', '/collections', undefined], ['GET', '/assets/theme.css?x=1', undefined],
    ['GET', '/th/products_preview?view=pimm-configurator', undefined], ['POST', '/cart/add.js', 'id=30'],
    ['POST', encodeURI(collection), 'body']]) {
    const response = await fetch(`${base}${path}`, { method, body, redirect: 'manual' });
    assert.equal(response.status, 201);
    assert.equal(response.headers.get('set-cookie'), 'preview=ok; Path=/');
    assert.deepEqual(await response.json(), { path, method, body: body ?? '' });
  }
  const denied = await new Promise((resolve, reject) => {
    http.get(base, { headers: { host: 'shop.maliev.com' } }, async response => {
      let body = '';
      for await (const chunk of response) body += chunk;
      resolve({ status: response.statusCode, body });
    }).on('error', reject);
  });
  assert.equal(denied.status, 403);
  assert.doesNotMatch(denied.body, new RegExp(key));
});

test('missing credentials fail closed and offline upstream reports a safe error', async (t) => {
  assert.throws(() => createPreviewServer({}), /PIMM_PREVIEW_KEY/);
  assert.throws(() => createPreviewServer({ key: '\r\ninvalid' }), /PIMM_PREVIEW_KEY/);
  const reserved = http.createServer().listen(0, '127.0.0.1');
  await once(reserved, 'listening');
  const port = reserved.address().port;
  await new Promise(resolve => reserved.close(resolve));
  const server = createPreviewServer({ key, upstreamPort: port }).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => server.close());
  const result = await fetch(`http://127.0.0.1:${server.address().port}/`);
  assert.equal(result.status, 502);
  assert.doesNotMatch(await result.text(), new RegExp(key));
});

test('upstream host and generated links stay on their respective sides of the proxy', async (t) => {
  const upstream = http.createServer((req, res) => {
    const origin = `http://127.0.0.1:${upstream.address().port}`;
    assert.equal(req.headers.host, new URL(origin).host);
    assert.equal(req.headers['accept-encoding'], 'identity');
    res.writeHead(200, { 'content-type': 'text/html', location: `${origin}/collections` });
    res.end(`<a href="${origin}/products/pneumatic-injection-molding-machine">Machine</a>`);
  }).listen(0, '127.0.0.1');
  await once(upstream, 'listening');
  t.after(() => upstream.close());
  const server = createPreviewServer({ key, upstreamPort: upstream.address().port }).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => server.close());
  const origin = `http://127.0.0.1:${server.address().port}`;
  const response = await fetch(origin);
  assert.equal(response.headers.get('location'), `${origin}/collections`);
  assert.equal(await response.text(), `<a href="${origin}/products/pneumatic-injection-molding-machine">Machine</a>`);
});

test('live local entry routes render new pages in both languages', {
  skip: process.env.PIMM_LOCAL_ROUTE_ACCEPTANCE !== '1', timeout: 90_000,
}, async () => {
  for (const locale of ['', '/th']) {
    for (const [route, marker, view, variant] of [
      [encodeURI(collection), 'data-pimm-collection-comparison', 'pimm-collection-preview', '54823758627095'],
      ['/products/pneumatic-injection-molding-machine', 'data-pimm-machine-product', 'pimm-configurator', '54823758627095'],
      ['/products/pneumatic-injection-molding-machine-50g', 'data-pimm-machine-product', 'pimm-configurator', '54823758659863'],
    ]) {
      const response = await fetch(`http://127.0.0.1:9494${locale}${route}`);
      assert.equal(response.status, 200);
      const url = new URL(response.url);
      assert.equal(url.pathname, `${locale}/products_preview`);
      assert.equal(url.searchParams.get('view'), view);
      assert.equal(url.searchParams.get('variant'), variant);
      const html = await response.text();
      assert.ok(html.includes(marker));
      assert.match(html, locale ? /<html[^>]+lang="th"/ : /<html[^>]+lang="en"/);
      assert.ok(!html.includes('http://127.0.0.1:9495'));
    }
  }
});

test('hot-reload event streams reach the browser without waiting for response end', { timeout: 5000 }, async (t) => {
  const upstream = http.createServer((req, res) => {
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    res.write('data: ready\n\n');
  }).listen(0, '127.0.0.1');
  await once(upstream, 'listening');
  t.after(() => { upstream.closeAllConnections(); upstream.close(); });
  const server = createPreviewServer({ key, upstreamPort: upstream.address().port }).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => { server.closeAllConnections(); server.close(); });
  const controller = new AbortController();
  t.after(() => controller.abort());
  const response = await fetch(`http://127.0.0.1:${server.address().port}/hot-reload`, { signal: controller.signal });
  const result = await response.body.getReader().read();
  assert.equal(new TextDecoder().decode(result.value), 'data: ready\n\n');
  controller.abort();
});
