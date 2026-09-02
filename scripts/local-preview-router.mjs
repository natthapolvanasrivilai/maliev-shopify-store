import http from 'node:http';
import net from 'node:net';

const models = { '30G': '54823758627095', '50G': '54823758659863' };
const handles = {
  'pneumatic-injection-molding-machine': '30G',
  'pneumatic-injection-molding-machine-50g': '50G',
  'pimm-pneumatic-injection-molding-machine-development': '30G',
};

export function previewDestination(path, key) {
  if (!path.startsWith('/') || path.startsWith('//')) return null;
  let url;
  let pathname;
  try {
    url = new URL(path, 'http://127.0.0.1');
    pathname = decodeURIComponent(url.pathname);
  } catch { return null; }
  const locale = pathname.match(/^\/(en|th)(?=\/)/)?.[0] ?? '';
  const route = pathname.slice(locale.length).replace(/\/$/, '');
  const isCollection = route === '/collections/เครื่องฉีดพลาสติก';
  const product = route.match(/^(?:\/collections\/[^/]+)?\/products\/([^/]+)$/)?.[1];
  if (!isCollection && !Object.hasOwn(handles, product ?? '')) return null;
  const requestedVariant = url.searchParams.get('variant');
  const variant = Object.values(models).includes(requestedVariant)
    ? requestedVariant : models[handles[product] ?? '30G'];
  const query = new URLSearchParams({
    preview_key: key,
    view: isCollection ? 'pimm-collection-preview' : 'pimm-configurator',
    variant,
  });
  return `${locale}/products_preview?${query}`;
}

export function createPreviewServer({ key, upstreamPort = 9495 }) {
  if (!/^[a-zA-Z0-9_-]{16,128}$/.test(key ?? '')) {
    throw new Error('Set a valid PIMM_PREVIEW_KEY in the ignored .env.local-preview file.');
  }
  if (!Number.isInteger(upstreamPort) || upstreamPort < 1 || upstreamPort > 65535) {
    throw new Error('Invalid local upstream port.');
  }
  const localHost = (host) => /^(127\.0\.0\.1|localhost)(:\d+)?$/.test(host ?? '');
  const server = http.createServer((req, res) => {
    if (!localHost(req.headers.host)) {
      res.writeHead(403).end('Local preview only');
      return;
    }
    const destination = ['GET', 'HEAD'].includes(req.method)
      ? previewDestination(req.url, key) : null;
    if (destination) {
      res.writeHead(302, { location: destination, 'cache-control': 'no-store', 'referrer-policy': 'same-origin' }).end();
      return;
    }
    const upstream = http.request({
      hostname: '127.0.0.1', port: upstreamPort,
      path: req.url, method: req.method,
      headers: { ...req.headers, host: `127.0.0.1:${upstreamPort}`, 'accept-encoding': 'identity' },
    }, (response) => {
      const headers = { ...response.headers };
      const upstreamOrigin = `http://127.0.0.1:${upstreamPort}`;
      const publicOrigin = `http://${req.headers.host}`;
      const rewrite = value => value.replaceAll(upstreamOrigin, publicOrigin);
      if (headers.location) headers.location = rewrite(headers.location);
      const contentType = headers['content-type'] ?? '';
      if (/text\/|javascript|json/.test(contentType) && !contentType.includes('text/event-stream') && !headers['content-encoding']) {
        const chunks = [];
        response.on('data', chunk => chunks.push(chunk));
        response.on('end', () => {
          const body = Buffer.from(rewrite(Buffer.concat(chunks).toString('utf8')));
          delete headers['transfer-encoding'];
          delete headers.etag;
          headers['content-length'] = body.length;
          headers['cache-control'] = 'no-store';
          res.writeHead(response.statusCode, headers).end(body);
        });
      } else {
        res.writeHead(response.statusCode, headers);
        response.pipe(res);
      }
    });
    upstream.on('error', () => {
      if (!res.headersSent) res.writeHead(502, { 'cache-control': 'no-store' });
      res.end('Local Shopify preview is starting or unavailable.');
    });
    req.on('aborted', () => upstream.destroy());
    res.on('close', () => upstream.destroy());
    req.pipe(upstream);
  });
  server.on('upgrade', (req, socket, head) => {
    if (!localHost(req.headers.host)) { socket.destroy(); return; }
    const upstream = net.connect(upstreamPort, '127.0.0.1', () => {
      upstream.write(`${req.method} ${req.url} HTTP/${req.httpVersion}\r\n`);
      for (let i = 0; i < req.rawHeaders.length; i += 2) {
        const value = req.rawHeaders[i].toLowerCase() === 'host' ? `127.0.0.1:${upstreamPort}` : req.rawHeaders[i + 1];
        upstream.write(`${req.rawHeaders[i]}: ${value}\r\n`);
      }
      upstream.write('\r\n');
      if (head.length) upstream.write(head);
      socket.pipe(upstream).pipe(socket);
    });
    upstream.on('error', () => socket.destroy());
    socket.on('error', () => upstream.destroy());
    socket.on('close', () => upstream.destroy());
  });
  return server;
}
