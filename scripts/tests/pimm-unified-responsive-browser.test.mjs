import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import test from 'node:test';

const previewUrl = process.env.PIMM_UNIFIED_PREVIEW_URL?.trim();
const evidenceDir = resolve(
  process.env.PIMM_UNIFIED_EVIDENCE_DIR?.trim()
    || '.codex-tmp/pimm-unified-product/browser-evidence',
);
const viewports = [
  [1440, 900],
  [1236, 1032],
  [1280, 800],
  [1024, 768],
  [768, 1024],
  [390, 844],
  [360, 800],
  [320, 800],
];
const models = ['30G', '50G'];
const expectedMarket = {
  en: {
    status: 'Made to order',
    unavailable: 'Currently unavailable',
    alt: {
      '30G': {
        hero: 'MALIEV 30G pneumatic injection molding machine, front view',
        overview: 'MALIEV 30G pneumatic injection molding machine, three-quarter view',
        engineering: 'MALIEV 30G controls and pneumatic engineering detail',
        tooling: 'MALIEV 30G mold tooling area, front detail',
      },
      '50G': {
        hero: 'MALIEV 50G pneumatic injection molding machine, front view',
        overview: 'MALIEV 50G pneumatic injection molding machine, three-quarter view',
        engineering: 'MALIEV 50G controls and pneumatic engineering detail',
        tooling: 'MALIEV 50G mold tooling area, front detail',
      },
    },
  },
  th: {
    status: 'ผลิตตามคำสั่งซื้อ',
    unavailable: 'ยังไม่พร้อมให้สั่งซื้อในขณะนี้',
    alt: {
      '30G': {
        hero: 'เครื่องฉีดพลาสติกระบบลม MALIEV รุ่น 30G มุมมองด้านหน้า',
        overview: 'เครื่องฉีดพลาสติกระบบลม MALIEV รุ่น 30G มุมมองสามส่วนสี่',
        engineering: 'รายละเอียดชุดควบคุมและระบบนิวเมติกของ MALIEV รุ่น 30G',
        tooling: 'รายละเอียดพื้นที่ติดตั้งแม่พิมพ์ด้านหน้าของ MALIEV รุ่น 30G',
      },
      '50G': {
        hero: 'เครื่องฉีดพลาสติกระบบลม MALIEV รุ่น 50G มุมมองด้านหน้า',
        overview: 'เครื่องฉีดพลาสติกระบบลม MALIEV รุ่น 50G มุมมองสามส่วนสี่',
        engineering: 'รายละเอียดชุดควบคุมและระบบนิวเมติกของ MALIEV รุ่น 50G',
        tooling: 'รายละเอียดพื้นที่ติดตั้งแม่พิมพ์ด้านหน้าของ MALIEV รุ่น 50G',
      },
    },
  },
  models: {
    '30G': {
      fullPrice: '฿105,930.00 THB',
      specifications: {
        schema_version: 1,
        model: '30G',
        shot_capacity_g: 30,
        max_melt_temperature_c: 300,
        mold_envelope_mm: { width: 240, height: 240, depth: 150 },
        max_air_pressure_mpa: 0.7,
      },
      media: {
        hero: { filename: 'pimm-machine-30g-hero-front.webp', width: 1800, height: 2200 },
        overview: { filename: 'pimm-machine-30g-overview-three-quarter.webp', width: 2400, height: 1800 },
        engineering: { filename: 'pimm-machine-30g-engineering-controls.webp', width: 2400, height: 1800 },
        tooling: { filename: 'pimm-machine-30g-tooling-front-detail.webp', width: 2400, height: 1800 },
      },
    },
    '50G': {
      fullPrice: '฿170,000.00 THB',
      specifications: {
        schema_version: 1,
        model: '50G',
        shot_capacity_g: 50,
        max_melt_temperature_c: 350,
        mold_envelope_mm: { width: 240, height: 240, depth: 100 },
        max_air_pressure_mpa: 0.7,
      },
      media: {
        hero: { filename: 'pimm-machine-50g-hero-front.webp', width: 1800, height: 2200 },
        overview: { filename: 'pimm-machine-50g-overview-three-quarter.webp', width: 2400, height: 1800 },
        engineering: { filename: 'pimm-machine-50g-engineering-controls.webp', width: 2400, height: 1800 },
        tooling: { filename: 'pimm-machine-50g-tooling-front-detail.webp', width: 2400, height: 1800 },
      },
    },
  },
};
const failureFixtures = ['unavailable-50g', 'malformed-specifications', 'missing-engineering-image'];
const chromeCandidates = [
  process.env.PIMM_UNIFIED_CHROME_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
].filter(Boolean);

const delay = (milliseconds) => new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));

async function eventually(action, { timeout = 30_000, interval = 100 } = {}) {
  const started = Date.now();
  let lastError;
  while (Date.now() - started < timeout) {
    try {
      const value = await action();
      if (value) return value;
    } catch (error) {
      lastError = error;
    }
    await delay(interval);
  }
  throw lastError ?? new Error(`Condition was not met within ${timeout}ms`);
}

class CdpSession {
  #id = 0;
  #listeners = new Map();
  #pending = new Map();

  static async connect(url) {
    const socket = new WebSocket(url);
    await new Promise((resolveOpen, reject) => {
      socket.addEventListener('open', resolveOpen, { once: true });
      socket.addEventListener('error', () => reject(new Error(`Chrome rejected the DevTools connection for ${url}`)), { once: true });
    });
    return new CdpSession(socket);
  }

  constructor(socket) {
    this.socket = socket;
    socket.addEventListener('message', (event) => {
      const message = JSON.parse(String(event.data));
      if (message.id) {
        const pending = this.#pending.get(message.id);
        if (!pending) return;
        this.#pending.delete(message.id);
        if (message.error) pending.reject(new Error(`${message.error.message} (${message.error.code})`));
        else pending.resolve(message.result);
        return;
      }
      for (const listener of this.#listeners.get(message.method) ?? []) listener(message.params);
    });
    socket.addEventListener('close', () => {
      for (const pending of this.#pending.values()) pending.reject(new Error('Chrome DevTools connection closed'));
      this.#pending.clear();
    });
  }

  on(method, listener) {
    const listeners = this.#listeners.get(method) ?? [];
    listeners.push(listener);
    this.#listeners.set(method, listeners);
    return () => {
      const current = this.#listeners.get(method) ?? [];
      this.#listeners.set(method, current.filter((candidate) => candidate !== listener));
    };
  }

  send(method, params = {}) {
    const id = ++this.#id;
    return new Promise((resolveSend, reject) => {
      this.#pending.set(id, { resolve: resolveSend, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  async close() {
    if (this.socket.readyState >= WebSocket.CLOSING) return;
    this.socket.close();
    await Promise.race([
      new Promise((resolveClose) => this.socket.addEventListener('close', resolveClose, { once: true })),
      delay(1_000),
    ]);
  }
}

async function stopBrowser(browser) {
  if (browser.exitCode !== null || browser.signalCode !== null) return;
  browser.kill();
  const exited = await Promise.race([
    new Promise((resolveExit) => browser.once('exit', () => resolveExit(true))),
    delay(5_000).then(() => false),
  ]);
  if (!exited) browser.kill('SIGKILL');
}

async function removeTemporaryProfile(path) {
  for (let attempt = 1; attempt <= 10; attempt += 1) {
    try {
      await rm(path, { force: true, recursive: true });
      return;
    } catch (error) {
      if (!['EBUSY', 'ENOTEMPTY', 'EPERM'].includes(error?.code) || attempt === 10) throw error;
      await delay(Math.min(50 * (2 ** (attempt - 1)), 1_000));
    }
  }
}

async function launchBrowser() {
  const executable = chromeCandidates.find((candidate) => existsSync(candidate));
  assert.ok(executable, 'Chrome or Edge is required; set PIMM_UNIFIED_CHROME_PATH when installed elsewhere');

  const userDataDir = await mkdtemp(join(tmpdir(), 'pimm-unified-browser-'));
  const browser = spawn(executable, [
    '--headless=new',
    '--remote-debugging-port=0',
    `--user-data-dir=${userDataDir}`,
    '--disable-background-networking',
    '--disable-component-update',
    '--disable-default-apps',
    '--disable-extensions',
    '--disable-features=Translate,MediaRouter',
    '--disable-sync',
    '--hide-scrollbars',
    '--mute-audio',
    '--no-default-browser-check',
    '--no-first-run',
    'about:blank',
  ], { stdio: 'ignore', windowsHide: true });

  try {
    const port = await eventually(async () => {
      const [value] = (await readFile(join(userDataDir, 'DevToolsActivePort'), 'utf8')).trim().split(/\r?\n/);
      return Number(value) || undefined;
    });
    const target = await eventually(async () => {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      const candidates = await response.json();
      return candidates.find((candidate) => candidate.type === 'page' && candidate.webSocketDebuggerUrl);
    });
    const session = await CdpSession.connect(target.webSocketDebuggerUrl);
    return {
      session,
      async close() {
        await Promise.race([session.send('Browser.close').catch(() => undefined), delay(2_000)]);
        await session.close().catch(() => undefined);
        await stopBrowser(browser);
        await removeTemporaryProfile(userDataDir);
      },
    };
  } catch (error) {
    await stopBrowser(browser);
    await removeTemporaryProfile(userDataDir);
    throw error;
  }
}

async function evaluate(session, expression) {
  const response = await session.send('Runtime.evaluate', {
    awaitPromise: true,
    expression,
    returnByValue: true,
    userGesture: true,
  });
  if (response.exceptionDetails) {
    throw new Error(response.exceptionDetails.exception?.description ?? response.exceptionDetails.text);
  }
  return response.result.value;
}

async function setViewport(session, width, height) {
  await session.send('Emulation.setDeviceMetricsOverride', {
    deviceScaleFactor: 1,
    height,
    mobile: false,
    screenHeight: height,
    screenWidth: width,
    width,
  });
  await delay(100);
}

async function dispatchTab(session) {
  await session.send('Input.dispatchKeyEvent', {
    code: 'Tab',
    key: 'Tab',
    nativeVirtualKeyCode: 9,
    type: 'rawKeyDown',
    windowsVirtualKeyCode: 9,
  });
  await session.send('Input.dispatchKeyEvent', {
    code: 'Tab',
    key: 'Tab',
    nativeVirtualKeyCode: 9,
    type: 'keyUp',
    windowsVirtualKeyCode: 9,
  });
  await delay(50);
}

async function dispatchEscape(session) {
  await session.send('Input.dispatchKeyEvent', {
    code: 'Escape',
    key: 'Escape',
    nativeVirtualKeyCode: 27,
    type: 'rawKeyDown',
    windowsVirtualKeyCode: 27,
  });
  await session.send('Input.dispatchKeyEvent', {
    code: 'Escape',
    key: 'Escape',
    nativeVirtualKeyCode: 27,
    type: 'keyUp',
    windowsVirtualKeyCode: 27,
  });
  await delay(50);
}

async function waitForPage(session) {
  await eventually(() => evaluate(session, `document.readyState === 'complete'`));
  const diagnosis = await evaluate(session, `(() => ({
    hasMachine: Boolean(document.querySelector('[data-pimm-machine-product]')),
    href: location.href,
    status: document.body?.innerText?.slice(0, 240) || '',
    title: document.title,
  }))()`);
  assert.equal(
    diagnosis.hasMachine,
    true,
    `Unified PIMM root missing after navigation to ${diagnosis.href}; title=${JSON.stringify(diagnosis.title)} body=${JSON.stringify(diagnosis.status)}`,
  );
  await eventually(() => evaluate(session, `(() => {
    const image = document.querySelector('[data-pimm-media-model]:not([hidden])[data-pimm-media-slot="hero"] img');
    return image?.complete && image.naturalWidth > 0;
  })()`));
}

async function navigate(session, url) {
  const result = await session.send('Page.navigate', { url });
  if (result.errorText) throw new Error(`Navigation failed for ${url}: ${result.errorText}`);
  await waitForPage(session);
}

function withAlternateView(value) {
  const url = new URL(value);
  url.searchParams.set('view', 'pimm-configurator');
  return url.href;
}

function thaiUrlFrom(value) {
  const url = new URL(value);
  if (!url.pathname.startsWith('/th/')) url.pathname = `/th${url.pathname.startsWith('/') ? '' : '/'}${url.pathname}`;
  return url.href;
}

async function captureScreenshot(session, path) {
  const capture = await session.send('Page.captureScreenshot', {
    captureBeyondViewport: false,
    format: 'png',
    fromSurface: true,
  });
  await writeFile(path, Buffer.from(capture.data, 'base64'));
}

async function suppressCookieConsentForEvidence(session) {
  return evaluate(session, `(() => {
    const selectors = [
      '#shopify-pc__banner',
      '#shopify-privacy-banner',
      '.shopify-pc__banner__dialog',
      '[data-shopify-privacy-banner]',
      'shopify-privacy-banner',
    ];
    const hidden = new Set();
    const hide = (node) => {
      if (!(node instanceof HTMLElement) || hidden.has(node)) return;
      node.style.setProperty('display', 'none', 'important');
      node.setAttribute('aria-hidden', 'true');
      node.setAttribute('data-pimm-evidence-suppressed', 'true');
      hidden.add(node);
    };
    for (const selector of selectors) document.querySelectorAll(selector).forEach(hide);
    for (const host of document.querySelectorAll('*')) {
      if (!host.shadowRoot) continue;
      for (const selector of selectors) host.shadowRoot.querySelectorAll(selector).forEach(hide);
      if (/privacy|cookie/i.test(host.localName) && /consent|cookie|privacy/i.test(host.shadowRoot.textContent || '')) hide(host);
    }
    return hidden.size;
  })()`);
}

async function captureElementScreenshot(session, path, selector) {
  const clip = await evaluate(session, `(async () => {
    const element = document.querySelector(${JSON.stringify(selector)});
    if (!element) return null;
    element.scrollIntoView({ block: 'center', inline: 'nearest' });
    await new Promise((resolveFrame) => requestAnimationFrame(() => requestAnimationFrame(resolveFrame)));
    const rect = element.getBoundingClientRect();
    return {
      x: Math.max(0, rect.left + scrollX),
      y: Math.max(0, rect.top + scrollY),
      width: Math.min(document.documentElement.scrollWidth, rect.width),
      height: rect.height,
      scale: 1,
    };
  })()`);
  assert.ok(clip && clip.width > 0 && clip.height > 0, `Screenshot target ${selector} must have geometry`);
  const capture = await session.send('Page.captureScreenshot', {
    captureBeyondViewport: true,
    clip,
    format: 'png',
    fromSurface: true,
  });
  await writeFile(path, Buffer.from(capture.data, 'base64'));
}

const decodeEntities = (value) => value
  .replaceAll('&quot;', '"')
  .replaceAll('&#39;', "'")
  .replaceAll('&amp;', '&')
  .replaceAll('&lt;', '<')
  .replaceAll('&gt;', '>');

function applyFailureFixture(html, fixture) {
  const payloadPattern = /(<script[^>]*data-pimm-variant-data[^>]*>)([\s\S]*?)(<\/script>)/;
  const match = html.match(payloadPattern);
  assert.ok(match, `Fixture ${fixture} could not find the variant payload`);
  const variants = JSON.parse(match[2]);
  const target = variants.find((variant) => variant.model === '50G');
  assert.ok(target, `Fixture ${fixture} requires a 50G record`);
  const invalidMessage = decodeEntities(
    html.match(/data-pimm-invalid-message="([^"]*)"/)?.[1] || 'Unavailable',
  );

  if (fixture === 'unavailable-50g') {
    target.available = false;
    const thai = /<html[^>]+lang=["']th(?:-|["'])/i.test(html);
    target.statusText = thai ? 'ยังไม่พร้อมให้สั่งซื้อในขณะนี้' : 'Currently unavailable';
    target.announcementText = target.statusText;
  } else if (fixture === 'malformed-specifications') {
    target.specifications.model = '30G';
    target.statusText = invalidMessage;
    target.announcementText = invalidMessage;
  } else if (fixture === 'missing-engineering-image') {
    target.media.engineering.src = '';
  } else {
    throw new Error(`Unsupported PIMM fixture ${fixture}`);
  }

  return html.replace(payloadPattern, `$1${JSON.stringify(variants)}$3`);
}

async function navigateWithFixture(session, url, fixture) {
  let transformed = false;
  let fixtureError;
  const off = session.on('Fetch.requestPaused', (params) => {
    void (async () => {
      try {
        const isHtmlResponse = params.resourceType === 'Document'
          && params.responseStatusCode === 200
          && !transformed;
        if (!isHtmlResponse) {
          await session.send('Fetch.continueResponse', { requestId: params.requestId });
          return;
        }
        const body = await session.send('Fetch.getResponseBody', { requestId: params.requestId });
        const source = Buffer.from(body.body, body.base64Encoded ? 'base64' : 'utf8').toString('utf8');
        if (!source.includes('data-pimm-variant-data')) {
          await session.send('Fetch.continueResponse', { requestId: params.requestId });
          return;
        }
        const updated = applyFailureFixture(source, fixture);
        const headers = (params.responseHeaders ?? [])
          .filter(({ name }) => !/^(?:content-encoding|content-length)$/i.test(name));
        headers.push({ name: 'content-length', value: String(Buffer.byteLength(updated)) });
        transformed = true;
        await session.send('Fetch.fulfillRequest', {
          body: Buffer.from(updated).toString('base64'),
          requestId: params.requestId,
          responseCode: 200,
          responseHeaders: headers,
        });
      } catch (error) {
        fixtureError ??= error;
        await session.send('Fetch.failRequest', { requestId: params.requestId, errorReason: 'Failed' }).catch(() => undefined);
      }
    })();
  });

  await session.send('Fetch.enable', { patterns: [{ requestStage: 'Response', resourceType: 'Document', urlPattern: '*' }] });
  try {
    await navigate(session, url);
    if (fixtureError) throw fixtureError;
    assert.equal(transformed, true, `Fixture ${fixture} did not intercept the unified product document`);
  } finally {
    off();
    await session.send('Fetch.disable').catch(() => undefined);
  }
}

const pageProbe = `(() => {
  const machine = document.querySelector('[data-pimm-machine-product]');
  const factory = document.querySelector('[data-pimm-book-visit]');
  const radios = [...document.querySelectorAll('[data-pimm-model-radio]')];
  const status = document.querySelector('[data-pimm-variant-status]');
  const purchase = document.querySelector('[data-pimm-purchase-qualification]');
  const purchaseRect = purchase?.getBoundingClientRect();
  const payload = document.querySelector('[data-pimm-variant-data]');
  return {
    bentoCount: document.querySelectorAll('[data-pimm-engineering-bento]').length,
    editorialCount: document.querySelectorAll('[data-pimm-editorial]').length,
    editorialChapterCount: document.querySelectorAll('[data-pimm-editorial-chapter]').length,
    demoActionCount: machine?.querySelectorAll('[data-pimm-book-visit]').length ?? 0,
    h1Count: machine?.querySelectorAll('h1').length ?? 0,
    liveRegion: status && {
      atomic: status.getAttribute('aria-atomic'),
      live: status.getAttribute('aria-live'),
      role: status.getAttribute('role'),
      text: status.textContent.trim(),
    },
    noOverflow: document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth,
    purchaseFullBleed: Boolean(purchaseRect && Math.abs(purchaseRect.left) <= 1 && Math.abs(purchaseRect.right - innerWidth) <= 1),
    purchaseRect: purchaseRect && { left: purchaseRect.left, right: purchaseRect.right, width: purchaseRect.width },
    paymentActionCount: machine?.querySelectorAll('[data-pimm-deposit-action], button[type="submit"], product-form').length ?? 0,
    taxContext: {
      country: payload?.dataset.pimmCountry,
      currency: payload?.dataset.pimmCurrency,
      taxesIncluded: payload?.dataset.pimmTaxesIncluded,
    },
    overflowEvidence: {
      body: document.body.scrollWidth,
      html: document.documentElement.scrollWidth,
      innerWidth,
      offenders: [...document.body.querySelectorAll('*')].flatMap((element) => {
        const rect = element.getBoundingClientRect();
        if (rect.left >= -1 && rect.right <= innerWidth + 1) return [];
        const style = getComputedStyle(element);
        if (style.display === 'none' || style.visibility === 'hidden' || rect.width === 0) return [];
        return [{
          className: String(element.className).slice(0, 100),
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          tag: element.tagName,
          width: Math.round(rect.width),
        }];
      }).slice(0, 12),
    },
    radioModels: radios.map((radio) => radio.dataset.model),
    radioNames: radios.map((radio) => radio.name),
    radioValues: radios.map((radio) => radio.value),
  };
})()`;

const editorialGeometryProbe = `(async () => {
  const editorial = document.querySelector('[data-pimm-editorial]');
  editorial?.scrollIntoView({ block: 'start' });
  const images = [...(editorial?.querySelectorAll('img') || [])];
  for (const image of images) {
    image.loading = 'eager';
    image.scrollIntoView({ block: 'center' });
    await image.decode?.().catch(() => undefined);
  }
  const overlaps = (a, b) => Boolean(
    a && b && a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top
  );
  return {
    editorialOverflowX: editorial ? editorial.scrollWidth - editorial.clientWidth : null,
    files: images.map((image) => new URL(image.currentSrc || image.src, location.href).pathname.split('/').pop()),
    chapters: [...(editorial?.querySelectorAll('[data-pimm-editorial-chapter]') || [])].map((chapter) => {
      const figure = chapter.querySelector('figure');
      const image = chapter.querySelector('img');
      const copy = chapter.querySelector('.pimm-machine__editorial-copy');
      const caption = chapter.querySelector('figcaption');
      const figureRect = figure?.getBoundingClientRect();
      const imageRect = image?.getBoundingClientRect();
      const copyRect = copy?.getBoundingClientRect();
      return {
        captionTruncated: Boolean(caption && (caption.scrollHeight > caption.clientHeight + 1 || caption.scrollWidth > caption.clientWidth + 1)),
        chapter: chapter.dataset.pimmEditorialChapter,
        imageContained: Boolean(figureRect && imageRect
          && imageRect.left >= figureRect.left - 1
          && imageRect.right <= figureRect.right + 1
          && imageRect.top >= figureRect.top - 1
          && imageRect.bottom <= figureRect.bottom + 1),
        intrinsic: image ? [image.naturalWidth, image.naturalHeight] : null,
        loaded: Boolean(image?.complete && image.naturalWidth > 0),
        overlap: overlaps(imageRect, copyRect),
        renderedRatio: imageRect ? imageRect.width / imageRect.height : null,
      };
    }),
    overflowX: Math.max(
      document.documentElement.scrollWidth - document.documentElement.clientWidth,
      document.body.scrollWidth - document.documentElement.clientWidth,
    ),
  };
})()`;

const consoleGeometryProbe = `(() => {
  const rect = (selector) => {
    const value = document.querySelector(selector)?.getBoundingClientRect();
    return value ? {
      bottom: value.bottom,
      height: value.height,
      left: value.left,
      right: value.right,
      top: value.top,
      width: value.width,
    } : null;
  };
  const overlaps = (a, b) => Boolean(
    a && b && a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top
  );
  const decision = rect('.pimm-machine__hero-decision');
  const actions = rect('.pimm-machine__hero-actions');
  const stage = rect('.pimm-machine__hero-stage');
  const evidence = rect('.pimm-machine__hero-evidence');
  const hero = rect('[data-pimm-hero-console]');
  const header = rect('.mc-header-section > header')
    || rect('.mc-header-section .header')
    || rect('.mc-header-section')
    || rect('[id$="__header"]');
  const qualification = rect('[data-pimm-qualification-strip]');
  const title = document.querySelector('.pimm-machine__hero-title-group h1');
  const evidenceHeading = document.querySelector('.pimm-machine__hero-evidence > h2');
  const titleRange = title ? document.createRange() : null;
  titleRange?.selectNodeContents(title);
  const selectedHero = document.querySelector('[data-pimm-media-model]:not([hidden])[data-pimm-media-slot="hero"] img');
  const image = selectedHero?.getBoundingClientRect();
  return {
    actions,
    decision,
    evidence,
    header,
    hero,
    image: image ? {
      bottom: image.bottom,
      height: image.height,
      left: image.left,
      right: image.right,
      top: image.top,
      width: image.width,
    } : null,
    imageHasArea: Boolean(image && image.width > 0 && image.height > 0),
    naturalSize: selectedHero ? [selectedHero.naturalWidth, selectedHero.naturalHeight] : null,
    overlaps: {
      actionsEvidence: overlaps(actions, evidence),
      decisionStage: overlaps(decision, stage),
      evidenceQualification: overlaps(evidence, qualification),
      stageEvidence: overlaps(stage, evidence),
    },
    qualification,
    stage,
    typography: {
      evidenceHeadingFontSize: evidenceHeading ? parseFloat(getComputedStyle(evidenceHeading).fontSize) : null,
      titleFontSize: title ? parseFloat(getComputedStyle(title).fontSize) : null,
      titleLineCount: titleRange ? [...titleRange.getClientRects()].filter((value) => value.width > 0).length : 0,
      titleTop: title?.getBoundingClientRect().top ?? null,
      titleWordBreak: title ? getComputedStyle(title).wordBreak : null,
    },
    visibleFactCount: [...document.querySelectorAll('.pimm-machine__hero-facts [data-pimm-spec]')]
      .filter((node) => node.getClientRects().length > 0).length,
    overflowX: Math.max(
      document.documentElement.scrollWidth - document.documentElement.clientWidth,
      document.body.scrollWidth - document.documentElement.clientWidth,
    ),
  };
})()`;

const selectedStateProbe = (model) => `(async () => {
  const radio = document.querySelector('[data-pimm-model-radio][data-model=${JSON.stringify(model)}]');
  if (radio.checked) {
    const other = [...document.querySelectorAll('[data-pimm-model-radio]')].find((candidate) => candidate !== radio);
    other?.click();
    await new Promise((resolveFrame) => requestAnimationFrame(() => requestAnimationFrame(resolveFrame)));
  }
  radio.click();
  await new Promise((resolveFrame) => requestAnimationFrame(() => requestAnimationFrame(resolveFrame)));
  await new Promise((resolveTransition) => setTimeout(resolveTransition, 220));
  const selectedGroups = [...document.querySelectorAll('[data-pimm-media-model=${JSON.stringify(model)}]:not([hidden])')];
  const selectedImages = selectedGroups.map((group) => group.querySelector('img')).filter(Boolean);
  for (const group of selectedGroups) {
    group.scrollIntoView({ block: 'center', inline: 'nearest' });
    await new Promise((resolveFrame) => requestAnimationFrame(() => requestAnimationFrame(resolveFrame)));
  }
  const imagesReady = await new Promise((resolveReady) => {
    const started = performance.now();
    const check = () => {
      if (selectedImages.every((image) => image.complete && image.naturalWidth > 0)) return resolveReady(true);
      if (performance.now() - started >= 5000) return resolveReady(false);
      setTimeout(check, 100);
    };
    check();
  });
  const payload = JSON.parse(document.querySelector('[data-pimm-variant-data]').textContent);
  const record = payload.find((variant) => variant.model === ${JSON.stringify(model)});
  const values = Object.fromEntries([...document.querySelectorAll('[data-pimm-model-value]')].map((node) => [node.dataset.pimmModelValue, node.textContent.trim()]));
  const specifications = Object.fromEntries([...document.querySelectorAll('[data-pimm-spec]')].map((node) => [node.dataset.pimmSpec, node.textContent.trim()]));
  const status = document.querySelector('[data-pimm-variant-status]');
  const factory = document.querySelector('[data-pimm-book-visit]');
  return {
    checked: radio.checked,
    factoryHref: factory.href,
    invalidMessage: document.querySelector('[data-pimm-variant-data]').dataset.pimmInvalidMessage,
    imagesReady,
    media: selectedGroups.map((group) => {
      const image = group.querySelector('img');
      const slot = group.dataset.pimmMediaSlot || image?.dataset.pimmMediaSlot;
      const pathname = image?.currentSrc ? new URL(image.currentSrc, location.href).pathname : '';
      return {
        alt: image?.alt,
        complete: image?.complete,
        filename: pathname.split('/').pop(),
        height: Number(image?.getAttribute('height')),
        naturalWidth: image?.naturalWidth,
        slot,
        width: Number(image?.getAttribute('width')),
      };
    }).sort((a, b) => ['hero', 'overview', 'engineering', 'tooling'].indexOf(a.slot) - ['hero', 'overview', 'engineering', 'tooling'].indexOf(b.slot)),
    otherVisibleMedia: document.querySelectorAll('[data-pimm-media-model]:not([data-pimm-media-model=${JSON.stringify(model)}]):not([hidden])').length,
    record,
    selected: document.querySelector('[data-pimm-selected-model]').textContent.trim(),
    specifications,
    status: status.textContent.trim(),
    url: location.href,
    values,
    visibleMedia: document.querySelectorAll('[data-pimm-media-model=${JSON.stringify(model)}]:not([hidden])').length,
  };
})()`;

test('missing preview URL is an intentional browser-matrix skip', { skip: Boolean(previewUrl) }, () => {
  assert.equal(previewUrl, undefined);
});

test('unified PIMM Draft preview passes responsive browser acceptance', {
  skip: previewUrl ? false : 'PIMM_UNIFIED_PREVIEW_URL is not set',
  timeout: 300_000,
}, async (t) => {
  const browser = await launchBrowser();
  const { session } = browser;
  const consoleErrors = [];
  const exceptions = [];
  const marketEvidence = [];

  session.on('Runtime.consoleAPICalled', (entry) => {
    if (entry.type === 'error') consoleErrors.push({
      message: entry.args.map((argument) => argument.value ?? argument.description).join(' '),
      url: entry.stackTrace?.callFrames?.[0]?.url ?? '',
    });
  });
  session.on('Runtime.exceptionThrown', (entry) => exceptions.push({
    message: entry.exceptionDetails.exception?.description ?? entry.exceptionDetails.text,
    url: entry.exceptionDetails.url ?? entry.exceptionDetails.stackTrace?.callFrames?.[0]?.url ?? '',
  }));

  try {
    await Promise.all([
      session.send('Page.enable'),
      session.send('Runtime.enable'),
      session.send('Network.enable'),
    ]);
    await mkdir(evidenceDir, { recursive: true });

    const englishPreview = withAlternateView(previewUrl);
    await navigate(session, englishPreview);
    const finalEnglishPreview = await evaluate(session, 'location.href');
    const languageUrls = {
      en: finalEnglishPreview,
      th: thaiUrlFrom(finalEnglishPreview),
    };

    for (const [language, url] of Object.entries(languageUrls)) {
      await t.test(`${language} responsive and model matrix`, async () => {
        await navigate(session, url);
        for (const [width, height] of viewports) {
          await setViewport(session, width, height);
          await evaluate(session, `(async () => {
            document.querySelector('[data-pimm-model-radio][data-model="30G"]')?.click();
            await new Promise((resolveTransition) => setTimeout(resolveTransition, 220));
            return true;
          })()`);
          const probe = await evaluate(session, pageProbe);
          assert.equal(probe.bentoCount, 1);
          assert.equal(probe.editorialCount, 1);
          assert.equal(probe.editorialChapterCount, 4);
          assert.equal(probe.h1Count, 1);
          assert.equal(
            probe.noOverflow,
            true,
            `${language} ${width}x${height} must not overflow: ${JSON.stringify(probe.overflowEvidence)}`,
          );
          assert.equal(probe.demoActionCount, 2);
          assert.equal(probe.paymentActionCount, 0);
          assert.equal(
            probe.purchaseFullBleed,
            true,
            `${language} ${width}x${height} purchase must remain full bleed: ${JSON.stringify(probe.purchaseRect)}`,
          );
          assert.deepEqual(probe.radioModels, models);
          assert.deepEqual(probe.radioNames, ['pimm-model', 'pimm-model']);
          assert.equal(new Set(probe.radioValues).size, 2);
          assert.deepEqual(probe.liveRegion, {
            atomic: 'true',
            live: 'polite',
            role: 'status',
            text: expectedMarket[language].status,
          });
          assert.deepEqual(probe.taxContext, { country: 'TH', currency: 'THB', taxesIncluded: 'true' });

          for (const model of models) {
            const state = await evaluate(session, selectedStateProbe(model));
            await evaluate(session, 'scrollTo(0, 0); true');
            const consoleGeometry = await evaluate(session, consoleGeometryProbe);
            const expectedModel = expectedMarket.models[model];
            const expectedAlt = expectedMarket[language].alt[model];
            const expectedAnnouncement = expectedMarket[language].status;
            const expectedMedia = Object.entries(expectedModel.media).map(([slot, media]) => ({
              alt: expectedAlt[slot],
              filename: media.filename,
              height: media.height,
              slot,
              width: media.width,
            }));
            assert.equal(state.checked, true);
            assert.equal(consoleGeometry.overlaps.decisionStage, false);
            assert.equal(consoleGeometry.overlaps.stageEvidence, false);
            assert.equal(
              consoleGeometry.overlaps.actionsEvidence,
              false,
              `${language} ${model} ${width}x${height} hero actions must not overlap evidence`,
            );
            assert.equal(
              consoleGeometry.overlaps.evidenceQualification,
              false,
              `${language} ${model} ${width}x${height} evidence must not overlap qualification`,
            );
            assert.equal(consoleGeometry.imageHasArea, true);
            assert.deepEqual(consoleGeometry.naturalSize, [1800, 2200]);
            assert.equal(consoleGeometry.visibleFactCount, 4);
            assert.ok(
              consoleGeometry.typography.titleLineCount <= 5,
              `${language} ${model} ${width}x${height} title typography ${JSON.stringify(consoleGeometry.typography)}`,
            );
            assert.equal(
              consoleGeometry.typography.titleWordBreak,
              'normal',
              `${language} ${model} ${width}x${height} title must not split words`,
            );
            assert.ok(
              consoleGeometry.typography.evidenceHeadingFontSize <= 22,
              `${language} ${model} ${width}x${height} evidence heading is ${consoleGeometry.typography.evidenceHeadingFontSize}px`,
            );
            assert.ok(
              !consoleGeometry.header
                || consoleGeometry.typography.titleTop >= consoleGeometry.header.bottom - 1,
              `${language} ${model} ${width}x${height} title must clear the transparent header: ${JSON.stringify({ header: consoleGeometry.header, titleTop: consoleGeometry.typography.titleTop })}`,
            );
            assert.ok(
              consoleGeometry.qualification.top >= consoleGeometry.hero.top - 1
                && consoleGeometry.qualification.bottom <= consoleGeometry.hero.bottom + 1,
              `${language} ${model} ${width}x${height} qualification must remain inside the first-screen hero`,
            );
            if (width >= 990 && width <= 1100) {
              assert.ok(
                consoleGeometry.evidence.top >= consoleGeometry.decision.bottom - 1,
                `${language} ${model} ${width}x${height} tablet evidence must sit below the decision panel`,
              );
            }
            assert.ok(
              consoleGeometry.overflowX <= 1,
              `${language} ${model} ${width}x${height} console must not overflow horizontally`,
            );
            if (width <= 749) {
              assert.ok(
                consoleGeometry.image.top >= consoleGeometry.stage.top - 1
                  && consoleGeometry.image.bottom <= consoleGeometry.stage.bottom + 1
                  && consoleGeometry.image.left >= consoleGeometry.stage.left - 1
                  && consoleGeometry.image.right <= consoleGeometry.stage.right + 1,
                `${language} ${model} ${width}x${height} mobile hero must contain the complete machine render: ${JSON.stringify({ image: consoleGeometry.image, stage: consoleGeometry.stage })}`,
              );
            }
            assert.equal(state.selected, model);
            assert.match(state.url, new RegExp(`[?&]variant=${state.record.id}(?:&|$)`));
            assert.equal(state.visibleMedia, 4);
            assert.equal(state.otherVisibleMedia, 0);
            assert.equal(state.imagesReady, true);
            assert.deepEqual(
              state.media.map(({ alt, filename, height, slot, width }) => ({ alt, filename, height, slot, width })),
              expectedMedia,
            );
            assert.deepEqual(
              state.media.map(({ complete, naturalWidth }) => ({ complete, loaded: naturalWidth > 0 })),
              Array.from({ length: 4 }, () => ({ complete: true, loaded: true })),
            );
            assert.equal(state.values.fullPrice, expectedModel.fullPrice);
            assert.equal(state.record.fullPrice, expectedModel.fullPrice);
            assert.equal(state.values.leadTime, state.record.leadTime);
            assert.equal(state.record.available, true);
            assert.equal(state.record.contractValid, true);
            assert.equal(state.status, expectedAnnouncement);
            assert.equal(state.record.statusText, expectedMarket[language].status);
            assert.equal(state.record.announcementText, expectedAnnouncement);
            assert.ok(state.factoryHref);
            assert.deepEqual(state.record.specifications, expectedModel.specifications);
            assert.deepEqual(state.specifications, {
              shot_capacity_g: String(expectedModel.specifications.shot_capacity_g),
              max_melt_temperature_c: String(expectedModel.specifications.max_melt_temperature_c),
              mold_envelope: [
                expectedModel.specifications.mold_envelope_mm.width,
                expectedModel.specifications.mold_envelope_mm.height,
                expectedModel.specifications.mold_envelope_mm.depth,
              ].join(' × '),
              max_air_pressure_mpa: String(expectedModel.specifications.max_air_pressure_mpa),
            });

            assert.deepEqual(
              Object.fromEntries(Object.entries(state.record.media).map(([slot, media]) => [slot, {
                alt: media.alt,
                filename: new URL(media.src, state.url).pathname.split('/').pop(),
                height: media.height,
                width: media.width,
              }])),
              Object.fromEntries(Object.entries(expectedModel.media).map(([slot, media]) => [slot, {
                alt: expectedAlt[slot],
                filename: media.filename,
                height: media.height,
                width: media.width,
              }])),
            );

            marketEvidence.push({
              language,
              model,
              viewport: `${width}x${height}`,
              taxContext: probe.taxContext,
              fullPrice: state.values.fullPrice,
              status: state.status,
              specifications: state.specifications,
              media: state.media,
            });
            await evaluate(session, 'scrollTo(0, 0); true');
            await suppressCookieConsentForEvidence(session);
            await captureScreenshot(session, join(evidenceDir, `pimm-unified-${language}-${width}x${height}-hero-${model.toLowerCase()}.png`));
            if (width === 390) {
              await captureElementScreenshot(
                session,
                join(evidenceDir, `pimm-unified-${language}-purchase-${model.toLowerCase()}.png`),
                '[data-pimm-purchase-qualification]',
              );
            }
          }

          const editorialState = await evaluate(session, editorialGeometryProbe);
          assert.deepEqual(editorialState.files, [
            'pimm-editorial-30g-architectural-daylight.webp',
            'pimm-editorial-50g-modern-workshop.webp',
            'pimm-editorial-50g-dark-engineering.webp',
            'pimm-editorial-30g-process-still-life.webp',
          ]);
          assert.equal(editorialState.overflowX <= 1, true, `${language} ${width}x${height} editorial overflow`);
          assert.deepEqual(
            editorialState.chapters.map(({ chapter, intrinsic }) => [chapter, intrinsic]),
            [
              ['architectural', [2560, 1440]],
              ['workshop', [2560, 1440]],
              ['engineering', [2560, 1440]],
              ['process', [1800, 2250]],
            ],
          );
          for (const chapter of editorialState.chapters) {
            assert.equal(chapter.loaded, true, `${language} ${width}x${height} ${chapter.chapter} must load`);
            assert.equal(chapter.imageContained, true, `${language} ${width}x${height} ${chapter.chapter} must not clip`);
            assert.equal(chapter.overlap, false, `${language} ${width}x${height} ${chapter.chapter} image/copy overlap`);
            assert.equal(chapter.captionTruncated, false, `${language} ${width}x${height} ${chapter.chapter} caption truncation`);
            const [naturalWidth, naturalHeight] = chapter.intrinsic;
            assert.ok(Math.abs(chapter.renderedRatio - (naturalWidth / naturalHeight)) < 0.01);
          }
        }
      });
    }

    await t.test('model media performs one bounded accessible crossfade and rapid switches settle latest', async () => {
      await navigate(session, languageUrls.en);
      await setViewport(session, 1440, 1000);
      const transition = await evaluate(session, `(async () => {
        const radio30 = document.querySelector('[data-pimm-model-radio][data-model="30G"]');
        const radio50 = document.querySelector('[data-pimm-model-radio][data-model="50G"]');
        radio30.click();
        await new Promise((resolveTransition) => setTimeout(resolveTransition, 220));
        radio50.focus();
        radio50.click();
        await new Promise((resolveFrame) => requestAnimationFrame(resolveFrame));
        await new Promise((resolveFrame) => requestAnimationFrame(resolveFrame));
        await new Promise((resolveTransition) => setTimeout(resolveTransition, 50));
        const snapshot = (model) => [...document.querySelectorAll('[data-pimm-media-model="' + model + '"]')].map((group) => ({
          ariaHidden: group.getAttribute('aria-hidden'),
          hidden: group.hidden,
          inert: group.inert,
          opacity: getComputedStyle(group).opacity,
          pointerEvents: getComputedStyle(group).pointerEvents,
          state: group.dataset.pimmMediaState || '',
        }));
        const during = { active: document.activeElement === radio50, incoming: snapshot('50G'), outgoing: snapshot('30G') };
        await new Promise((resolveTransition) => setTimeout(resolveTransition, 220));
        const after = { incoming: snapshot('50G'), outgoing: snapshot('30G') };
        radio30.click();
        await new Promise((resolveFrame) => requestAnimationFrame(resolveFrame));
        radio50.click();
        await new Promise((resolveTransition) => setTimeout(resolveTransition, 220));
        const rapid = { incoming: snapshot('50G'), outgoing: snapshot('30G') };
        return { after, during, rapid };
      })()`);
      assert.equal(transition.during.active, true);
      assert.ok(transition.during.incoming.every((group) => !group.hidden && group.ariaHidden === 'false' && !group.inert));
      assert.ok(
        transition.during.outgoing.every((group) => !group.hidden && group.ariaHidden === 'true' && group.inert && Number(group.opacity) > 0 && Number(group.opacity) < 1 && group.pointerEvents === 'none' && group.state === 'exiting'),
        JSON.stringify(transition.during.outgoing),
      );
      for (const settled of [transition.after, transition.rapid]) {
        assert.ok(settled.incoming.every((group) => !group.hidden && group.ariaHidden === 'false' && !group.inert && group.state === ''));
        assert.ok(settled.outgoing.every((group) => group.hidden && group.ariaHidden === 'true' && group.inert && group.state === ''));
      }
    });

    await t.test('desktop and mobile header interactions preserve viewport containment and focus', async () => {
      await navigate(session, languageUrls.en);
      await setViewport(session, 1440, 1000);
      const desktopOpen = await evaluate(session, `(() => {
        const group = document.querySelector('[data-mc-mega-menu]');
        const summary = group?.querySelector(':scope > summary');
        summary?.click();
        const panel = group?.querySelector('.mc-nav__panel');
        const rect = panel?.getBoundingClientRect();
        return {
          bodyWidth: document.body.scrollWidth,
          expanded: summary?.getAttribute('aria-expanded'),
          htmlWidth: document.documentElement.scrollWidth,
          innerWidth,
          open: group?.open,
          panel: rect && { left: rect.left, right: rect.right, width: rect.width },
        };
      })()`);
      assert.equal(desktopOpen.open, true);
      assert.equal(desktopOpen.expanded, 'true');
      assert.deepEqual(desktopOpen.panel, { left: 0, right: 1440, width: 1440 });
      assert.equal(desktopOpen.bodyWidth, desktopOpen.innerWidth);
      assert.equal(desktopOpen.htmlWidth, desktopOpen.innerWidth);
      await dispatchEscape(session);
      const desktopClosed = await evaluate(session, `(() => {
        const group = document.querySelector('[data-mc-mega-menu]');
        const summary = group?.querySelector(':scope > summary');
        return { active: document.activeElement === summary, expanded: summary?.getAttribute('aria-expanded'), open: group?.open };
      })()`);
      assert.deepEqual(desktopClosed, { active: true, expanded: 'false', open: false });

      await setViewport(session, 390, 844);
      const mobileOpen = await evaluate(session, `(async () => {
        const menu = document.querySelector('.mc-mobile-menu');
        const summary = menu?.querySelector(':scope > summary');
        summary?.click();
        await new Promise((resolveFrame) => requestAnimationFrame(() => requestAnimationFrame(resolveFrame)));
        const panel = menu?.querySelector('.mc-mobile-menu__panel');
        const rect = panel?.getBoundingClientRect();
        return {
          bodyClass: document.body.classList.contains('mc-mobile-menu-open'),
          bodyWidth: document.body.scrollWidth,
          expanded: summary?.getAttribute('aria-expanded'),
          htmlWidth: document.documentElement.scrollWidth,
          inert: document.querySelector('#MainContent')?.hasAttribute('inert'),
          innerWidth,
          open: menu?.open,
          panel: rect && { left: rect.left, right: rect.right, width: rect.width },
        };
      })()`);
      assert.equal(mobileOpen.open, true);
      assert.equal(mobileOpen.expanded, 'true');
      assert.equal(mobileOpen.bodyClass, true);
      assert.equal(mobileOpen.inert, true);
      assert.deepEqual(mobileOpen.panel, { left: 0, right: 390, width: 390 });
      assert.equal(mobileOpen.bodyWidth, mobileOpen.innerWidth);
      assert.equal(mobileOpen.htmlWidth, mobileOpen.innerWidth);
      await dispatchEscape(session);
      const mobileClosed = await evaluate(session, `(() => {
        const menu = document.querySelector('.mc-mobile-menu');
        const summary = menu?.querySelector(':scope > summary');
        return {
          active: document.activeElement === summary,
          bodyClass: document.body.classList.contains('mc-mobile-menu-open'),
          expanded: summary?.getAttribute('aria-expanded'),
          inert: document.querySelector('#MainContent')?.hasAttribute('inert'),
          open: menu?.open,
        };
      })()`);
      assert.deepEqual(mobileClosed, { active: true, bodyClass: false, expanded: 'false', inert: false, open: false });
    });

    await t.test('keyboard focus and reduced motion remain explicit', async () => {
      await navigate(session, languageUrls.en);
      await setViewport(session, 390, 844);
      const focusSetup = await evaluate(session, `(() => {
        const radio = document.querySelector('[data-pimm-model-radio]:checked');
        document.body.setAttribute('tabindex', '-1');
        document.body.focus();
        document.body.removeAttribute('tabindex');
        const style = radio ? getComputedStyle(radio) : null;
        return {
          checked: radio?.checked,
          disabled: radio?.disabled,
          display: style?.display,
          originFocused: document.activeElement === document.body,
          rects: radio?.getClientRects().length,
          tabIndex: radio?.tabIndex,
          targetFound: Boolean(radio),
          visibility: style?.visibility,
        };
      })()`);
      assert.equal(focusSetup.targetFound, true);
      assert.equal(focusSetup.originFocused, true);
      let focus;
      for (let attempt = 0; attempt < 40; attempt += 1) {
        await dispatchTab(session);
        focus = await evaluate(session, `(() => {
          const radio = document.querySelector('[data-pimm-model-radio]:checked');
          const label = radio.closest('label');
          const style = getComputedStyle(label);
          return {
            active: document.activeElement === radio,
            activeId: document.activeElement?.id || '',
            activeTag: document.activeElement?.tagName || '',
            color: style.outlineColor,
            focusVisible: radio.matches(':focus-visible'),
            width: parseFloat(style.outlineWidth),
          };
        })()`);
        if (focus.active) break;
      }
      assert.equal(focus.active, true, JSON.stringify({ focus, focusSetup }));
      assert.equal(focus.focusVisible, true);
      assert.equal(focus.color, 'rgb(255, 210, 28)');
      assert.ok(focus.width >= 3);

      await session.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
      const motion = await evaluate(session, `(() => {
        const radio30 = document.querySelector('[data-pimm-model-radio][data-model="30G"]');
        const radio50 = document.querySelector('[data-pimm-model-radio][data-model="50G"]');
        radio30.click();
        radio50.click();
        const media = document.querySelector('[data-pimm-media-model]:not([hidden])');
        const descendants = [media, ...media.querySelectorAll('*')];
        return {
          groups: [...document.querySelectorAll('[data-pimm-media-model]')].map((group) => ({
            ariaHidden: group.getAttribute('aria-hidden'),
            hidden: group.hidden,
            inert: group.inert,
            model: group.dataset.pimmMediaModel,
            state: group.dataset.pimmMediaState || '',
          })),
          styles: descendants.map((node) => {
          const style = getComputedStyle(node);
          return { animation: style.animationName, duration: style.transitionDuration, transform: style.transform };
          }),
        };
      })()`);
      assert.deepEqual(motion.groups.filter((group) => !group.hidden).map((group) => group.model), ['50G', '50G', '50G', '50G']);
      assert.ok(motion.groups.filter((group) => group.model === '50G').every((group) => group.ariaHidden === 'false' && !group.inert && group.state === ''));
      assert.ok(motion.groups.filter((group) => group.model === '30G').every((group) => group.hidden && group.ariaHidden === 'true' && group.inert && group.state === ''));
      assert.deepEqual(motion.styles.filter((entry) => entry.animation !== 'none'), []);
      assert.deepEqual(motion.styles.filter((entry) => !entry.duration.split(',').every((duration) => Number.parseFloat(duration) === 0)), []);
      assert.deepEqual(motion.styles.filter((entry) => entry.transform !== 'none'), []);
      await session.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
    });

    await t.test('390px flow remains usable at 200 percent browser zoom', async () => {
      await setViewport(session, 195, 422);
      await navigate(session, languageUrls.en);
      await suppressCookieConsentForEvidence(session);
      const zoom = await evaluate(session, `(() => {
        const decision = document.querySelector('.pimm-machine__hero-decision');
        const stage = document.querySelector('.pimm-machine__hero-stage');
        const titleGroup = document.querySelector('.pimm-machine__hero-title-group');
        const selector = document.querySelector('[data-pimm-model-selector]');
        const actions = document.querySelector('.pimm-machine__hero-actions');
        const evidence = document.querySelector('.pimm-machine__hero-evidence');
        const qualification = document.querySelector('[data-pimm-qualification-strip]');
        const machine = document.querySelector('[data-pimm-machine-product]');
        const title = document.querySelector('.pimm-machine__hero-title-group h1');
        const titleRange = title ? document.createRange() : null;
        titleRange?.selectNodeContents(title);
        const visible = (selector) => Boolean(document.querySelector(selector)?.getClientRects().length);
        return {
          controls: {
            modelSelector: visible('[data-pimm-model-selector]'),
            visit: visible('[data-pimm-book-visit]'),
          },
          visualOrder: {
            stageBeforeSelector: stage && selector && stage.getBoundingClientRect().bottom <= selector.getBoundingClientRect().top + 1,
            selectorBeforeActions: selector && actions && selector.getBoundingClientRect().bottom <= actions.getBoundingClientRect().top + 1,
            actionsBeforeTitle: actions && titleGroup && actions.getBoundingClientRect().bottom <= titleGroup.getBoundingClientRect().top + 1,
          },
          order: [
            decision?.compareDocumentPosition(stage) & Node.DOCUMENT_POSITION_FOLLOWING,
            stage?.compareDocumentPosition(evidence) & Node.DOCUMENT_POSITION_FOLLOWING,
            evidence?.compareDocumentPosition(qualification) & Node.DOCUMENT_POSITION_FOLLOWING,
          ].map(Boolean),
          overflowOffenders: [...(machine?.querySelectorAll('*') || [])]
            .map((node) => ({
              className: typeof node.className === 'string' ? node.className : '',
              right: node.getBoundingClientRect().right,
              tag: node.tagName,
              width: node.getBoundingClientRect().width,
            }))
            .filter((entry) => entry.right > document.documentElement.clientWidth + 1)
            .sort((a, b) => b.right - a.right)
            .slice(0, 8),
          overflowX: machine ? machine.scrollWidth - machine.clientWidth : null,
          titleLineCount: titleRange ? [...titleRange.getClientRects()].filter((value) => value.width > 0).length : 0,
        };
      })()`);
      assert.deepEqual(zoom.order, [true, true, true]);
      assert.deepEqual(zoom.controls, {
        modelSelector: true,
        visit: true,
      });
      assert.deepEqual(zoom.visualOrder, {
        stageBeforeSelector: true,
        selectorBeforeActions: true,
        actionsBeforeTitle: true,
      });
      assert.ok(zoom.overflowX <= 1, `200% zoom flow ${JSON.stringify(zoom)}`);
      assert.ok(zoom.titleLineCount <= 5, `200% zoom title ${JSON.stringify(zoom)}`);
      const editorialZoom = await evaluate(session, editorialGeometryProbe);
      assert.ok(editorialZoom.editorialOverflowX <= 1, `200% editorial overflow ${JSON.stringify(editorialZoom)}`);
      assert.equal(editorialZoom.chapters.length, 4);
      for (const chapter of editorialZoom.chapters) {
        assert.equal(chapter.imageContained, true, `200% ${chapter.chapter} image clipping`);
        assert.equal(chapter.overlap, false, `200% ${chapter.chapter} image/copy overlap`);
        assert.equal(chapter.captionTruncated, false, `200% ${chapter.chapter} caption truncation`);
      }
      await evaluate(session, `(() => {
        document.querySelector('[data-pimm-machine-product]')?.scrollIntoView({ block: 'start' });
        return true;
      })()`);
      await suppressCookieConsentForEvidence(session);
      await captureScreenshot(session, join(evidenceDir, 'pimm-unified-en-390x844-at-200-percent.png'));
    });

    for (const [language, url] of Object.entries(languageUrls)) {
      for (const fixture of failureFixtures) {
        await t.test(`${language} ${fixture} fails closed without model leakage`, async () => {
          await navigateWithFixture(session, url, fixture);
          await setViewport(session, 390, 844);
          const state = await evaluate(session, selectedStateProbe('50G'));
          assert.equal(state.checked, true);
          assert.equal(state.selected, '50G');
          assert.ok(state.factoryHref);
          assert.equal(state.otherVisibleMedia, 0);
          if (fixture === 'unavailable-50g') {
            assert.equal(state.visibleMedia, 4);
            assert.equal(state.specifications.shot_capacity_g, '50');
            assert.equal(
              state.status,
              expectedMarket[language].unavailable,
            );
          } else if (fixture === 'malformed-specifications') {
            assert.equal(state.visibleMedia, 0);
            assert.equal(state.specifications.shot_capacity_g, state.invalidMessage);
            assert.equal(state.status, state.invalidMessage);
          } else {
            const hero = expectedMarket.models['50G'].media.hero;
            const engineering = state.media.find((media) => media.slot === 'engineering');
            assert.equal(state.visibleMedia, 4);
            assert.equal(state.specifications.shot_capacity_g, '50');
            assert.equal(
              state.status,
              expectedMarket[language].status,
            );
            assert.deepEqual(
              { alt: engineering.alt, filename: engineering.filename, height: engineering.height, width: engineering.width },
              { alt: expectedMarket[language].alt['50G'].hero, filename: hero.filename, height: hero.height, width: hero.width },
            );
          }
          await suppressCookieConsentForEvidence(session);
          await captureElementScreenshot(
            session,
            join(evidenceDir, `pimm-unified-${language}-failure-${fixture}.png`),
            '[data-pimm-purchase-qualification]',
          );
        });
      }
    }

    const pageOwned = (entry) => /maliev-pimm-machine(?:\.js|\.css)?|pimm-machine-product/i.test(`${entry.url} ${entry.message}`);
    const pageConsoleErrors = consoleErrors.filter(pageOwned);
    const pageExceptions = exceptions.filter(pageOwned);
    assert.deepEqual(pageConsoleErrors, [], 'Unified PIMM-owned scripts must not emit console.error');
    assert.deepEqual(pageExceptions, [], 'Unified PIMM-owned scripts must not throw uncaught exceptions');
    const externalErrors = [...consoleErrors, ...exceptions].filter((entry) => !pageOwned(entry));
    await writeFile(join(evidenceDir, 'external-browser-errors.json'), `${JSON.stringify(externalErrors, null, 2)}\n`);
    await writeFile(join(evidenceDir, 'market-context.json'), `${JSON.stringify(marketEvidence, null, 2)}\n`);
    console.log(`PIMM_UNIFIED_EXTERNAL_BROWSER_ERRORS=${JSON.stringify(externalErrors)}`);
    console.log(`PIMM_UNIFIED_BROWSER_EVIDENCE=${evidenceDir}`);
    console.log(`PIMM_UNIFIED_LANGUAGE_URLS=${JSON.stringify(languageUrls)}`);
  } finally {
    await browser.close();
  }
});
