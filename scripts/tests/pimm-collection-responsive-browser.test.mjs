import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import test from 'node:test';

const previewUrl = process.env.PIMM_COLLECTION_PREVIEW_URL?.trim();
const evidenceDir = resolve(
  process.env.PIMM_COLLECTION_EVIDENCE_DIR?.trim()
    || '.codex-tmp/pimm-collection/browser-evidence',
);
const viewports = [[1536, 1024], [1440, 900], [1920, 720], [1920, 901], [1280, 800], [1280, 720], [1024, 768], [640, 360], [390, 844], [360, 800]];
const desktopMinimum = 990;
const inlineActionViewports = [[989, 800], [390, 844]];
const expectedActionLabels = {
  en: {
    factoryVisit: 'Book a factory visit',
    support: 'Contact machine support',
  },
  th: {
    factoryVisit: 'จองเข้าชมโรงงาน',
    support: 'ติดต่อฝ่ายบริการเครื่อง',
  },
};
const chromeCandidates = [
  process.env.PIMM_COLLECTION_CHROME_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
].filter(Boolean);

const delay = (milliseconds) => new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));

async function eventually(action, {
  timeout = 30_000,
  interval = 100,
  message = 'Condition was not met',
} = {}) {
  const started = Date.now();
  let lastError;
  let lastValue;
  while (Date.now() - started < timeout) {
    try {
      const value = await action();
      if (value) return value;
      lastValue = value;
    } catch (error) {
      lastError = error;
    }
    await delay(interval);
  }
  throw lastError ?? new Error(
    `${message} within ${timeout}ms (last value: ${JSON.stringify(lastValue)})`,
  );
}

class CdpSession {
  #id = 0;

  #pending = new Map();

  #listeners = new Map();

  static async connect(url) {
    const socket = new WebSocket(url);
    await new Promise((resolveOpen, reject) => {
      socket.addEventListener('open', resolveOpen, { once: true });
      socket.addEventListener('error', () => reject(new Error(`Chrome rejected ${url}`)), { once: true });
    });
    return new CdpSession(socket);
  }

  constructor(socket) {
    this.socket = socket;
    socket.addEventListener('message', (event) => {
      const message = JSON.parse(String(event.data));
      if (!message.id) {
        for (const listener of this.#listeners.get(message.method) ?? []) {
          listener(message.params ?? {});
        }
        return;
      }
      const pending = this.#pending.get(message.id);
      if (!pending) return;
      this.#pending.delete(message.id);
      if (message.error) pending.reject(new Error(`${message.error.message} (${message.error.code})`));
      else pending.resolve(message.result);
    });
    socket.addEventListener('close', () => {
      for (const pending of this.#pending.values()) {
        pending.reject(new Error('Chrome DevTools connection closed'));
      }
      this.#pending.clear();
    });
  }

  send(method, params = {}) {
    const id = ++this.#id;
    return new Promise((resolveSend, reject) => {
      this.#pending.set(id, { resolve: resolveSend, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  on(method, listener) {
    const listeners = this.#listeners.get(method) ?? new Set();
    listeners.add(listener);
    this.#listeners.set(method, listeners);
    return () => listeners.delete(listener);
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

function createBrowserDiagnostics(session) {
  let entries = [];
  let navigation = 'before navigation';
  let navigationRetryCount = 0;

  // Shopify injects immutable third-party/preview failures on localhost:
  // Shop Pay cannot frame shop.app under its production frame-ancestors policy, and
  // BUCKS dereferences absent production currency data inside its injected app SDK.
  // The preview shell also requests unauthenticated /cart.js and parses its fixed
  // "The access..." denial response as JSON. Shopify's preview telemetry exporter
  // may also reject local synthetic metrics/logs with a fixed 503/OpenTelemetry pair.
  // Finally, its hashed origin-trials bootstrap is emitted as HTTP on localhost,
  // producing one exact CORS/ERR_FAILED pair before application code executes.
  // The preview asset URLs also leave the owner-approved Latin/Thai preload hints
  // unconsumed; only those two exact font warning signatures are exempted.
  // All exemptions are restricted to /products_preview and exact source signatures.
  const isImmutableShopifyPreviewNoise = (entry) => {
    let isPreviewRoute = false;
    try {
      isPreviewRoute = new URL(navigation).pathname.endsWith('/products_preview');
    } catch {
      return false;
    }
    if (!isPreviewRoute) return false;
    if (entry.level === 'warning') {
      return entry.kind === 'browser log'
        && /^The resource http:\/\/127\.0\.0\.1:\d+\/cdn\/shop\/t\/\d+\/assets\/(?:IBMPlexSans-Regular-Latin1|IBMPlexSansThai-Regular)\.woff2\?v=\d+ was preloaded using link preload but not used within a few seconds from the window's load event\. Please make sure it has an appropriate `as` value and it is preloaded intentionally\.\nSource: http:\/\/127\.0\.0\.1:\d+\/(?:th\/)?products_preview\?/.test(entry.text);
    }
    if (entry.level !== 'error') return false;
    return (
      entry.kind === 'browser log'
        && /^Framing 'https:\/\/shop\.app\/' violates the following Content Security Policy directive: "frame-ancestors 'self' https:\/\/shop\.app https:\/\/admin\.shopify\.com"\. The request has been blocked\./.test(entry.text)
    ) || (
      entry.kind === 'browser log'
        && entry.text.trim() === `Framing 'https://shop.app/' violates the following Content Security Policy directive: "frame-ancestors https://10b918-e4.myshopify.com https://10b918-e4.account.myshopify.com https://maliev-manufacturing.myshopify.com https://shop.maliev.com https://shop-account.maliev.com https://shopify.com". The request has been blocked.`
    ) || (
      entry.kind === 'runtime exception'
        && /^TypeError: Cannot read properties of null \(reading '0'\)[\s\S]+127\.0\.0\.1:\d+\/apps\/buckscc\/sdk\.min\.js:2:/.test(entry.text)
    ) || (
      entry.kind === 'browser log'
        && /^Failed to load resource: the server responded with a status of 401 \(Unauthorized\)\nSource: http:\/\/127\.0\.0\.1:\d+\/(?:th\/)?cart\.js$/.test(entry.text)
    ) || (
      entry.kind === 'runtime exception'
        && /^Uncaught \(in promise\) SyntaxError: Unexpected token 'T', "The access"\.\.\. is not valid JSON\nhttp:\/\/127\.0\.0\.1:\d+\/(?:th\/)?products_preview\?/.test(entry.text)
    ) || (
      entry.kind === 'browser log'
        && /^Failed to load resource: the server responded with a status of 503 \(\)\nSource: https:\/\/otlp-http-production\.shopifysvc\.com\/v1\/(?:metrics|logs)$/.test(entry.text)
    ) || (
      entry.kind === 'runtime exception'
        && /^OpenTelemetryClientError: Server did not accept data[\s\S]+127\.0\.0\.1:\d+\/cdn\/shopifycloud\/shop-js\/modules\/v2\/chunk\.utils_[A-Za-z0-9_-]+\.esm\.js:1:/.test(entry.text)
    ) || (
      entry.kind === 'browser log'
        && /^Access to script at 'http:\/\/cdn\.shopify\.com\/shopifycloud\/storefront\/assets\/storefront\/origin_trials-[A-Fa-f0-9]+\.js' from origin 'http:\/\/127\.0\.0\.1:\d+' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present on the requested resource\.\nSource: http:\/\/127\.0\.0\.1:\d+\/(?:th\/)?products_preview\?/.test(entry.text)
    ) || (
      entry.kind === 'browser log'
        && /^Failed to load resource: net::ERR_FAILED\nSource: http:\/\/cdn\.shopify\.com\/shopifycloud\/storefront\/assets\/storefront\/origin_trials-[A-Fa-f0-9]+\.js$/.test(entry.text)
    );
  };

  const record = (kind, level, textValue) => {
    if (!['warning', 'error', 'assert'].includes(level)) return;
    entries.push({ kind, level, text: String(textValue || '(no message)') });
  };
  session.on('Runtime.exceptionThrown', ({ exceptionDetails }) => {
    const stack = exceptionDetails?.stackTrace?.callFrames
      ?.map((frame) => `${frame.functionName || '(anonymous)'} at ${frame.url}:${frame.lineNumber + 1}:${frame.columnNumber + 1}`)
      .join('\n');
    record(
      'runtime exception',
      'error',
      [exceptionDetails?.exception?.description
        || exceptionDetails?.text
        || 'Uncaught runtime exception', exceptionDetails?.url, stack]
        .filter(Boolean)
        .join('\n'),
    );
  });
  session.on('Runtime.consoleAPICalled', ({ type, args = [] }) => {
    record(
      'console',
      type,
      args.map((argument) => argument.value
        ?? argument.unserializableValue
        ?? argument.description
        ?? '').join(' '),
    );
  });
  session.on('Log.entryAdded', ({ entry }) => {
    record(
      'browser log',
      entry?.level,
      [entry?.text, entry?.url ? `Source: ${entry.url}` : ''].filter(Boolean).join('\n'),
    );
  });

  return {
    begin(nextNavigation) {
      assert.deepEqual(entries, [], `Unasserted browser diagnostics before ${nextNavigation}`);
      navigation = nextNavigation;
    },
    async assertClean(context = navigation) {
      await delay(120);
      const observed = entries;
      entries = [];
      const unexpected = observed.filter((entry) => !isImmutableShopifyPreviewNoise(entry));
      assert.deepEqual(
        unexpected,
        [],
        `${context} emitted unexpected runtime, console, or browser-log warnings/errors`,
      );
    },
    recordNavigationRetry() {
      navigationRetryCount += 1;
    },
    get navigationRetryCount() {
      return navigationRetryCount;
    },
  };
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
  assert.ok(
    executable,
    'Chrome or Edge is required; set PIMM_COLLECTION_CHROME_PATH when installed elsewhere',
  );
  const userDataDir = await mkdtemp(join(tmpdir(), 'pimm-collection-browser-'));
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
      const [value] = (await readFile(join(userDataDir, 'DevToolsActivePort'), 'utf8'))
        .trim()
        .split(/\r?\n/);
      return Number(value) || undefined;
    });
    const target = await eventually(async () => {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      return (await response.json()).find(
        (candidate) => candidate.type === 'page' && candidate.webSocketDebuggerUrl,
      );
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

async function setViewport(session, width, height, mobile = false) {
  await session.send('Emulation.setDeviceMetricsOverride', {
    deviceScaleFactor: 1,
    height,
    mobile,
    screenHeight: height,
    screenWidth: width,
    width,
  });
  await delay(100);
}

async function assertNoStorefrontFailureSurface(session, url) {
  const failure = await evaluate(session, `(() => {
    const overlaySelectors = [
      'vite-error-overlay',
      '#webpack-dev-server-client-overlay',
      '[data-nextjs-dialog-overlay]',
      '#shopify-error-page',
      '.shopify-error-page',
      '[data-testid="error-boundary"]',
    ];
    const overlay = overlaySelectors.find((selector) => document.querySelector(selector));
    const text = document.body?.innerText?.slice(0, 12000) ?? '';
    const textPatterns = [
      /Liquid error:/i,
      /Application error: a client-side exception/i,
      /There was a problem loading this website/i,
      /This page is (?:not available|unavailable)/i,
      /(?:500 Internal Server Error|502 Bad Gateway|503 Service Unavailable)/i,
      /Shopify CLI (?:error|failed)/i,
    ];
    const textPattern = textPatterns.find((pattern) => pattern.test(text));
    return overlay
      ? { kind: 'overlay', detail: overlay }
      : textPattern
        ? { kind: 'page', detail: String(textPattern) }
        : null;
  })()`);
  assert.equal(failure, null, `${url} rendered a storefront/framework failure surface`);
}

async function navigate(session, url, diagnostics) {
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    diagnostics.begin(`${url} (attempt ${attempt})`);
    const result = await session.send('Page.navigate', { url });
    if (result.errorText) throw new Error(`Navigation failed for ${url}: ${result.errorText}`);
    try {
      await eventually(() => evaluate(session, `document.readyState === 'complete'`), {
        message: 'Collection preview did not finish loading',
      });
      break;
    } catch (error) {
      if (attempt === 2) throw error;
      await session.send('Page.stopLoading');
      await diagnostics.assertClean(`${url} timed-out navigation attempt ${attempt}`);
      diagnostics.recordNavigationRetry();
    }
  }
  await assertNoStorefrontFailureSurface(session, url);
  await eventually(() => evaluate(
    session,
    `Boolean(document.querySelector('[data-pimm-collection-comparison][data-contract-valid="true"]'))`,
  ), { message: 'Valid dedicated PIMM collection did not render' });
  await eventually(() => evaluate(
    session,
    `customElements.get('pimm-collection-comparison')
      && document.querySelector('[data-pimm-collection-comparison]')?.activeModel === '30G'`,
  ), { message: 'PIMM collection controller did not initialize' });
  await evaluate(session, `(async () => {
    if (!document.fonts) return true;
    await document.fonts.load('400 16px "IBM Plex Sans"', 'MALIEV collection');
    await document.fonts.ready;
    return true;
  })()`);
  await assertNoStorefrontFailureSurface(session, url);
}

async function navigateWithoutJavaScript(session, url, diagnostics) {
  diagnostics.begin(`${url} (JavaScript disabled)`);
  const result = await session.send('Page.navigate', { url });
  if (result.errorText) throw new Error(`Navigation failed for ${url}: ${result.errorText}`);
  await eventually(() => evaluate(session, `document.readyState === 'complete'`), {
    message: 'No-JavaScript collection preview did not finish loading',
  });
  await assertNoStorefrontFailureSurface(session, url);
  await eventually(() => evaluate(
    session,
    `Boolean(document.querySelector('[data-pimm-collection-comparison][data-contract-valid="true"]'))`,
  ), { message: 'No-JavaScript dedicated PIMM collection did not render' });
}

function thaiUrlFrom(value) {
  const url = new URL(value);
  if (!url.pathname.startsWith('/th/')) {
    url.pathname = `/th${url.pathname.startsWith('/') ? '' : '/'}${url.pathname}`;
  }
  return url.href;
}

async function suppressCookieConsent(session) {
  await evaluate(session, `(() => {
    for (const selector of [
      '#shopify-pc__banner',
      '#shopify-privacy-banner',
      '[data-shopify-privacy-banner]',
    ]) {
      document.querySelectorAll(selector).forEach((node) => {
        node.style.display = 'none';
        node.setAttribute('aria-hidden', 'true');
      });
    }
    return true;
  })()`);
}

async function decodeCollectionImages(session) {
  await evaluate(session, `(async () => {
    const images = [...document.querySelectorAll(
      '[data-pimm-collection-frame] img',
    )];
    for (const image of images) {
      image.loading = 'eager';
      image.scrollIntoView({ block: 'center' });
      if (!image.complete || image.naturalWidth === 0) {
        await new Promise((resolveImage) => {
          image.addEventListener('load', resolveImage, { once: true });
          image.addEventListener('error', resolveImage, { once: true });
        });
      }
      if (typeof image.decode === 'function') await image.decode().catch(() => {});
    }
    scrollTo(0, 0);
    return images.length;
  })()`);
  await delay(180);
}

async function captureFullPageScreenshot(session, path) {
  const { contentSize } = await session.send('Page.getLayoutMetrics');
  const capture = await session.send('Page.captureScreenshot', {
    captureBeyondViewport: true,
    clip: {
      x: 0,
      y: 0,
      width: Math.ceil(contentSize.width),
      height: Math.ceil(contentSize.height),
      scale: 1,
    },
    format: 'png',
    fromSurface: true,
  });
  await writeFile(path, Buffer.from(capture.data, 'base64'));
}

const geometryProbe = `(() => {
  const root = document.querySelector('[data-pimm-collection-comparison]');
  const cards = [...root.querySelectorAll('[data-pimm-collection-card]')];
  const [card30, card50] = cards;
  const frontImages = cards.map((card) => card.querySelector(
    '[data-pimm-collection-frame="front"] img',
  ));
  const machineImages = [...root.querySelectorAll('[data-pimm-collection-frame] img')];
  const controls = [...root.querySelectorAll(
    '.pimm-collection__card-actions :is(a, button), '
      + '.pimm-collection__dossier-actions a, '
      + '.pimm-collection__dossier > a[data-pimm-dossier-configure]',
  )].filter((control) => control.getClientRects().length > 0);
  const dossier = root.querySelector('.pimm-collection__dossier--desktop');
  const inlineDossier = root.querySelector(
    '[data-pimm-collection-inline-dossier].is-active:not([hidden])',
  );
  const card30Rect = card30.getBoundingClientRect();
  const card50Rect = card50.getBoundingClientRect();
  const dossierRect = dossier.getBoundingClientRect();
  const inlineRect = inlineDossier?.getBoundingClientRect();
  const visibleDossierRect = innerWidth >= ${desktopMinimum}
    ? dossierRect
    : inlineRect;
  const dossierHeading = innerWidth >= ${desktopMinimum}
    ? dossier.querySelector('[data-pimm-dossier-model]')
    : inlineDossier?.querySelector('[data-pimm-dossier-model]');
  const dossierPrice = innerWidth >= ${desktopMinimum}
    ? dossier.querySelector('[data-pimm-dossier-price]')
    : inlineDossier?.querySelector('[data-pimm-dossier-price]');
  const dossierHeadingStyle = dossierHeading ? getComputedStyle(dossierHeading) : null;
  return {
    h1Count: document.querySelectorAll('h1').length,
    cardCount: cards.length,
    imagesReady: machineImages.length === 2
      && machineImages.every((image) => image.complete
        && image.naturalWidth === 1440
        && image.naturalHeight === 1920),
    horizontalOverflow: document.documentElement.scrollWidth - innerWidth <= 1,
    machineImagesTransformed: machineImages.some(
      (image) => getComputedStyle(image).transform !== 'none',
    ),
    frontFramesDistinct: frontImages.length === 2
      && new Set(frontImages.map((image) => new URL(image.currentSrc).pathname)).size === 2,
    controlsAtLeast44px: controls.length > 0
      && controls.every((control) => {
        const rect = control.getBoundingClientRect();
        return rect.width >= 44 && rect.height >= 44;
      }),
    cardsSideBySide: Math.abs(card30Rect.top - card50Rect.top) <= 2
      && card30Rect.right <= card50Rect.left + 1,
    dossierToRight: dossierRect.left >= Math.max(card30Rect.right, card50Rect.right) - 1,
    dossierReachable: dossierRect.height > 0
      && dossierRect.height <= innerHeight
      && ((innerWidth >= 1280 && innerHeight >= 720)
        ? dossierRect.bottom <= innerHeight
        : getComputedStyle(dossier).overflowY === 'auto'),
    mobileOrder: card30Rect.top < card50Rect.top
      && card50Rect.bottom <= (inlineRect?.top ?? -1) + 1,
    genericGridAbsent: !document.querySelector(
      '#product-grid, .mc-catalog-grid, .facets-container, collection-filters-form',
    ),
    dossierHeadingVisible: dossierHeading?.textContent.trim() === '30G'
      && dossierHeading.getBoundingClientRect().height >= 40
      && dossierHeadingStyle?.display !== 'none'
      && dossierHeadingStyle?.visibility === 'visible'
      && Number(dossierHeadingStyle?.opacity) > 0
      && dossierHeadingStyle?.color === 'rgb(255, 255, 255)',
    dossierHeadingDiagnostic: dossierHeading ? {
      text: dossierHeading.textContent.trim(),
      height: dossierHeading.getBoundingClientRect().height,
      display: dossierHeadingStyle.display,
      visibility: dossierHeadingStyle.visibility,
      opacity: dossierHeadingStyle.opacity,
      color: dossierHeadingStyle.color,
      fontSize: dossierHeadingStyle.fontSize,
    } : null,
    dossierPriceHasLiteralMarkup: /[<>]/.test(dossierPrice?.textContent ?? ''),
    shortDesktopContentContained: innerWidth < 1280 || innerHeight < 720
      || [...dossier.querySelectorAll('a,dd,p,h2')].every(element =>
        element.getBoundingClientRect().bottom <= dossier.getBoundingClientRect().bottom),
    machineFooterClearance: innerWidth < 1280 || innerHeight < 720 || cards.every(card => {
      const media = card.querySelector('.pimm-collection__media').getBoundingClientRect();
      const price = card.querySelector('[data-pimm-card-price]').getBoundingClientRect();
      const actions = card.querySelector('.pimm-collection__card-actions').getBoundingClientRect();
      const image = card.querySelector('img');
      // r02 native front and extreme-angle renders end the machine at 84% height.
      // Pin the release too: an older, tighter-framed poster invalidates this guide.
      return image.currentSrc.includes('motion-20260902-r02')
        && image.naturalWidth === 1440 && image.naturalHeight === 1920
        && Math.abs(media.height - (card.getBoundingClientRect().height - 2)) <= 1
        && price.top >= media.top + media.height * 0.84 + 8
        && actions.top >= price.bottom + 4
        && actions.bottom <= media.bottom - 8;
    }),
    dossierActionHierarchy: innerWidth < 1280 || innerHeight < 720 || (() => {
      const list = dossier.querySelector('dl').getBoundingClientRect();
      const price = dossier.querySelector('[data-pimm-dossier-price]').parentElement.getBoundingClientRect();
      const actions = dossier.querySelector('.pimm-collection__dossier-actions');
      const primary = actions.querySelector('[data-pimm-dossier-configure]').getBoundingClientRect();
      const secondary = [...actions.querySelectorAll('a:not([data-pimm-dossier-configure])')];
      return Math.abs(price.width - list.width) <= 1
        && Math.abs(primary.width - list.width) <= 1
        && primary.top >= list.bottom
        && secondary.every(link => link.getBoundingClientRect().top >= primary.bottom + 4
          && getComputedStyle(link).backgroundColor === 'rgba(0, 0, 0, 0)'
          && getComputedStyle(link).borderTopStyle === 'solid')
        && Math.abs(actions.getBoundingClientRect().bottom
          - (dossierRect.bottom - parseFloat(getComputedStyle(dossier).paddingBottom))) <= 1;
    })(),
    localizedPrices: [...root.querySelectorAll('[data-pimm-card-price], [data-pimm-dossier-price]')]
      .every(price => {
        const model = price.closest('[data-model]').dataset.model;
        const unit = document.documentElement.lang.startsWith('th') ? 'บาท' : 'THB';
        return price.textContent.trim() === (model === '30G' ? '120,000 ' : '170,000 ') + unit;
      }),
    distinctTypeRoles: getComputedStyle(root.querySelector('h1')).fontFamily.startsWith('"PIMM Chakra Petch"')
      && getComputedStyle(root.querySelector('.pimm-collection__card-copy h2')).fontFamily.startsWith('Antonio')
      && document.fonts.check('600 20px "PIMM Chakra Petch"')
      && document.fonts.check('600 20px Antonio'),
    proportionalPrices: [...root.querySelectorAll('[data-pimm-card-price], [data-pimm-dossier-price]')]
      .every(price => {
        const style = getComputedStyle(price);
        return style.fontFamily.startsWith('"IBM Plex Sans"')
          && style.fontWeight === '600'
          && style.fontVariantNumeric.includes('proportional-nums');
      }),
    activeModel: root.activeModel,
    committedModel: root.committedModel,
    visibleDossierModel: visibleDossierRect?.height > 0
      ? (innerWidth >= ${desktopMinimum} ? dossier.dataset.model : inlineDossier.dataset.model)
      : null,
  };
})()`;

async function assertGeometry(session, language, width, height) {
  const probe = await evaluate(session, geometryProbe);
  const context = `${language} ${width}x${height}`;
  assert.equal(probe.h1Count, 1, `${context} H1 count`);
  assert.equal(probe.cardCount, 2, `${context} card count`);
  assert.equal(probe.imagesReady, true, `${context} image readiness`);
  assert.equal(probe.horizontalOverflow, true, `${context} horizontal overflow`);
  assert.equal(probe.machineImagesTransformed, false, `${context} machine image transforms`);
  assert.equal(probe.frontFramesDistinct, true, `${context} front-frame uniqueness`);
  assert.equal(probe.controlsAtLeast44px, true, `${context} control target size`);
  assert.equal(probe.genericGridAbsent, true, `${context} generic collection grid`);
  assert.equal(
    probe.dossierHeadingVisible,
    true,
    `${context} dossier heading visibility ${JSON.stringify(probe.dossierHeadingDiagnostic)}`,
  );
  assert.equal(probe.dossierPriceHasLiteralMarkup, false, `${context} dossier price markup`);
  assert.equal(probe.proportionalPrices, true, `${context} proportional semibold price typography`);
  assert.equal(probe.shortDesktopContentContained, true, `${context} dossier content remains inside its panel`);
  assert.equal(probe.machineFooterClearance, true, `${context} full-height r02 render clears price and buttons`);
  assert.equal(probe.dossierActionHierarchy, true, `${context} dossier price and bottom support hierarchy`);
  assert.equal(probe.localizedPrices, true, `${context} trailing localized currency without redundant decimals`);
  assert.equal(probe.distinctTypeRoles, true, `${context} loaded model and heading font roles`);
  assert.equal(probe.activeModel, '30G', `${context} initial active model`);
  assert.equal(probe.committedModel, '30G', `${context} initial committed model`);
  assert.equal(probe.visibleDossierModel, '30G', `${context} initial dossier`);

  if (width >= desktopMinimum) {
    assert.equal(probe.cardsSideBySide, true, `${context} card columns`);
    assert.equal(probe.dossierToRight, true, `${context} dossier position`);
    assert.equal(probe.dossierReachable, true, `${context} dossier reachability`);
  }
  if (width <= 749) assert.equal(probe.mobileOrder, true, `${context} mobile document order`);
}

async function dispatchTouchTap(session, selector) {
  await evaluate(session, `(() => {
    const target = document.querySelector(${JSON.stringify(selector)});
    if (!target) throw new Error('Touch target was not found');
    target.scrollIntoView({ block: 'center', inline: 'center' });
    return true;
  })()`);
  await delay(180);
  const point = await evaluate(session, `(() => {
    const target = document.querySelector(${JSON.stringify(selector)});
    const rect = target.getBoundingClientRect();
    if (rect.width < 44 || rect.height < 44) {
      throw new Error('Touch target is smaller than 44px');
    }
    return {
      x: rect.left + (rect.width / 2),
      y: rect.top + (rect.height / 2),
    };
  })()`);
  await session.send('Input.dispatchTouchEvent', {
    type: 'touchStart',
    touchPoints: [{
      id: 0,
      x: point.x,
      y: point.y,
      radiusX: 1,
      radiusY: 1,
      force: 1,
    }],
  });
  await session.send('Input.dispatchTouchEvent', {
    type: 'touchEnd',
    touchPoints: [],
  });
}

async function mobileTouchProbe(session, diagnostics, language, url) {
  await session.send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }],
  });
  await session.send('Emulation.setTouchEmulationEnabled', {
    enabled: true,
    maxTouchPoints: 1,
  });
  await setViewport(session, 390, 844, true);
  await navigate(session, url, diagnostics);
  await suppressCookieConsent(session);
  await headerProbe(session, `${language} mobile touch`);

  const selector = '[data-pimm-collection-card][data-model="50G"] [data-pimm-collection-select]';
  await evaluate(session, `(() => {
    const root = document.querySelector('[data-pimm-collection-comparison]');
    const announcement = root.querySelector('[data-pimm-collection-announcement]');
    const changes = [];
    const observer = new MutationObserver(() => changes.push(announcement.textContent.trim()));
    observer.observe(announcement, { childList: true, characterData: true, subtree: true });
    window.__pimmMobileTouchProbe = { changes, observer };
    return true;
  })()`);
  await dispatchTouchTap(session, selector);
  await eventually(() => evaluate(
    session,
    `document.querySelector('[data-pimm-collection-comparison]')?.committedModel === '50G'`,
  ), { message: `${language} real mobile touch did not commit 50G` });
  await delay(80);
  const result = await evaluate(session, `(() => {
    const root = document.querySelector('[data-pimm-collection-comparison]');
    const probe = window.__pimmMobileTouchProbe;
    probe.observer.disconnect();
    delete window.__pimmMobileTouchProbe;
    return {
      active: root.activeModel,
      committed: root.committedModel,
      announcement: root.querySelector('[data-pimm-collection-announcement]').textContent.trim(),
      announcementChanges: probe.changes,
      mediaOpacities: [...root.querySelectorAll('.pimm-collection__media')]
        .map(media => Number(getComputedStyle(media).opacity)),
      current: root.querySelector('[data-pimm-collection-card][data-model="50G"]')
        .getAttribute('aria-current'),
    };
  })()`);
  assert.equal(result.active, '50G', `${language} touch active model`);
  assert.equal(result.committed, '50G', `${language} touch committed model`);
  assert.equal(result.current, 'true', `${language} touch aria-current`);
  assert.deepEqual(result.mediaOpacities, [1, 1], `${language} touch has no sticky hover recession`);
  assert.match(result.announcement, /50G/, `${language} touch announcement`);
  assert.equal(result.announcementChanges.length, 1, `${language} touch announcement count`);
  await diagnostics.assertClean(`${language} 390x844 real mobile touch`);
}

async function inlineSupportActionProbe(session, diagnostics, language) {
  const labels = expectedActionLabels[language];
  for (const [width, height] of inlineActionViewports) {
    await setViewport(session, width, height, width < 500);
    const result = await evaluate(session, `(() => {
      const root = document.querySelector('[data-pimm-collection-comparison]');
      const desktop = root.querySelector('.pimm-collection__dossier--desktop');
      const inline = [...root.querySelectorAll('[data-pimm-collection-inline-dossier]')];
      const active = inline.find((dossier) => !dossier.hidden && dossier.classList.contains('is-active'));
      const inactive = inline.find((dossier) => dossier !== active);
      const links = [...active.querySelectorAll('.pimm-collection__dossier-actions a')];
      const actions = links.slice(1).map((link) => {
        const url = new URL(link.href);
        link.focus({ preventScroll: true });
        return {
          color: getComputedStyle(link).color,
          focused: document.activeElement === link,
          hash: url.hash,
          label: link.textContent.trim(),
          pathname: url.pathname,
          search: url.search,
          visible: link.getClientRects().length > 0,
        };
      });
      return {
        actions,
        activeModel: active?.dataset.model,
        committedModel: root.committedModel,
        activeVisible: active?.getClientRects().length > 0,
        cardTabindexes: [...root.querySelectorAll('[data-pimm-collection-card]')]
          .map((card) => card.getAttribute('tabindex')),
        compareControls: [...root.querySelectorAll('[data-pimm-collection-select]')]
          .map((button) => ({ disabled: button.disabled, hidden: button.hidden })),
        desktopHidden: getComputedStyle(desktop).display === 'none',
        inactiveHidden: inactive?.hidden && inactive.getClientRects().length === 0,
      };
    })()`);
    const context = `${language} ${width}x${height} inline support actions`;
    assert.equal(result.activeModel, result.committedModel, `${context} active dossier`);
    assert.equal(result.activeVisible, true, `${context} active dossier visibility`);
    assert.equal(result.desktopHidden, true, `${context} desktop dossier hidden`);
    assert.equal(result.inactiveHidden, true, `${context} inactive dossier hidden`);
    assert.deepEqual(result.cardTabindexes, ['0', '0'], `${context} enhanced card focusability`);
    assert.ok(result.compareControls.every(({ disabled, hidden }) => !disabled && !hidden), `${context} compare controls`);
    assert.deepEqual(result.actions, [
      {
        color: 'rgb(255, 255, 255)',
        focused: true,
        hash: '#ContactVisitTitle',
        label: labels.factoryVisit,
        pathname: '/pages/contact',
        search: '?intent=demo',
        visible: true,
      },
      {
        color: 'rgb(255, 255, 255)',
        focused: true,
        hash: '#ContactForm',
        label: labels.support,
        pathname: '/pages/contact',
        search: '?intent=general',
        visible: true,
      },
    ], `${context} exact actions`);
    await diagnostics.assertClean(context);
  }
}

async function noJavaScriptFallbackProbe(session, diagnostics, language, url) {
  await session.send('Emulation.setScriptExecutionDisabled', { value: true });
  try {
    await setViewport(session, 989, 800);
    await navigateWithoutJavaScript(session, url, diagnostics);
    for (const [width, height] of inlineActionViewports) {
      await setViewport(session, width, height, width < 500);
      const result = await evaluate(session, `(() => {
        const root = document.querySelector('[data-pimm-collection-comparison]');
        const cards = [...root.querySelectorAll('[data-pimm-collection-card]')];
        const links = cards.map((card) => card.querySelector('.pimm-collection__card-actions a'));
        const compareControls = cards.map((card) => card.querySelector('[data-pimm-collection-select]'));
        return {
          controllerDefined: Boolean(customElements.get('pimm-collection-comparison')),
          cardTabindexes: cards.map((card) => card.getAttribute('tabindex')),
          compareControls: compareControls.map((button) => ({
            disabled: button.disabled,
            hidden: button.hidden,
            visible: button.getClientRects().length > 0,
          })),
          canonicalLinks: links.map((link) => {
            link.focus({ preventScroll: true });
            return {
              focused: document.activeElement === link,
              variant: new URL(link.href).searchParams.get('variant'),
              visible: link.getClientRects().length > 0,
            };
          }),
        };
      })()`);
      const context = `${language} ${width}x${height} no-JavaScript fallback`;
      assert.equal(result.controllerDefined, false, `${context} controller absence`);
      assert.deepEqual(result.cardTabindexes, [null, null], `${context} card tab order`);
      assert.ok(result.compareControls.every(({ disabled, hidden, visible }) => disabled && hidden && !visible), `${context} compare controls`);
      assert.deepEqual(result.canonicalLinks.map(({ variant }) => variant), ['54823758627095', '54823758659863'], `${context} canonical variants`);
      assert.ok(result.canonicalLinks.every(({ focused, visible }) => focused && visible), `${context} canonical link keyboard use`);
      await diagnostics.assertClean(context);
    }
  } finally {
    await session.send('Emulation.setScriptExecutionDisabled', { value: false });
  }
}

async function interactionProbe(session, language) {
  const preview = await evaluate(session, `(() => {
    const root = document.querySelector('[data-pimm-collection-comparison]');
    const card = root.querySelector('[data-pimm-collection-card][data-model="50G"]');
    card.dispatchEvent(new PointerEvent('pointerenter', { pointerType: 'mouse' }));
    return {
      active: root.activeModel,
      committed: root.committedModel,
      current: card.getAttribute('aria-current'),
    };
  })()`);
  assert.deepEqual(preview, { active: '50G', committed: '30G', current: 'true' });

  const restoredAfterHover = await evaluate(session, `(() => {
    const root = document.querySelector('[data-pimm-collection-comparison]');
    root.querySelector('[data-pimm-collection-card][data-model="50G"]')
      .dispatchEvent(new PointerEvent('pointerleave', { pointerType: 'mouse' }));
    return { active: root.activeModel, committed: root.committedModel };
  })()`);
  assert.deepEqual(restoredAfterHover, { active: '30G', committed: '30G' });

  const focusPreview = await evaluate(session, `(async () => {
    const root = document.querySelector('[data-pimm-collection-comparison]');
    const card = root.querySelector('[data-pimm-collection-card][data-model="50G"]');
    window.focus();
    card.focus({ preventScroll: true });
    await new Promise((resolveFrame) => requestAnimationFrame(resolveFrame));
    return {
      active: root.activeModel,
      committed: root.committedModel,
      focused: document.activeElement === card,
    };
  })()`);
  assert.deepEqual(focusPreview, { active: '50G', committed: '30G', focused: true });

  const restoredAfterFocus = await evaluate(session, `(() => {
    const root = document.querySelector('[data-pimm-collection-comparison]');
    root.querySelector('[data-pimm-collection-card][data-model="50G"]').blur();
    return { active: root.activeModel, committed: root.committedModel };
  })()`);
  assert.deepEqual(restoredAfterFocus, { active: '30G', committed: '30G' });

  const committed = await evaluate(session, `(async () => {
    const root = document.querySelector('[data-pimm-collection-comparison]');
    const card = root.querySelector('[data-pimm-collection-card][data-model="50G"]');
    const announcement = root.querySelector('[data-pimm-collection-announcement]');
    const payload = JSON.parse(root.querySelector('[data-pimm-collection-models]').textContent);
    const changes = [];
    const observer = new MutationObserver(() => changes.push(announcement.textContent.trim()));
    observer.observe(announcement, { childList: true, characterData: true, subtree: true });
    const video = card.querySelector('[data-pimm-collection-video]');
    const beforeFrames = video.getVideoPlaybackQuality().totalVideoFrames;
    const finished = new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Video failed to finish')), 15000);
      video.addEventListener('ended', () => { clearTimeout(timeout); resolve(); }, {once:true});
    });
    card.querySelector('[data-pimm-collection-select]').click();
    await finished;
    observer.disconnect();
    const decodedFrames = video.getVideoPlaybackQuality().totalVideoFrames - beforeFrames;
    await new Promise((resolveWait) => setTimeout(resolveWait, 350));
    const visibleDossier = innerWidth >= ${desktopMinimum}
      ? root.querySelector('.pimm-collection__dossier--desktop')
      : root.querySelector('[data-pimm-collection-inline-dossier].is-active:not([hidden])');
    const links = [...root.querySelectorAll(
      '[data-pimm-collection-card] .pimm-collection__card-actions a',
    )].map((anchor) => ({
      href: anchor.href,
      variant: new URL(anchor.href).searchParams.get('variant'),
    }));
    return {
      active: root.activeModel,
      committed: root.committedModel,
      announcement: announcement.textContent.trim(),
      announcementChanges: changes,
      dossierModel: visibleDossier.dataset.model,
      dossierPrice: visibleDossier.querySelector('[data-pimm-dossier-price]').textContent.trim(),
      dossierLeadTime: visibleDossier.querySelector('[data-pimm-dossier-lead-time]').textContent.trim(),
      expectedPrice: payload.find((record) => record.model === '50G').fullPrice,
      expectedLeadTime: payload.find((record) => record.model === '50G').leadTime,
      links,
      decodedFrames,
      paused: video.paused,
      loop: video.loop,
      finalFrame: card.querySelector('[data-pimm-collection-frame]:not([hidden])')
        ?.dataset.pimmCollectionFrame,
      transformed: [...card.querySelectorAll('img')]
        .some((image) => getComputedStyle(image).transform !== 'none'),
    };
  })()`);

  assert.equal(committed.active, '50G', `${language} committed active model`);
  assert.equal(committed.committed, '50G', `${language} committed state`);
  assert.equal(committed.dossierModel, '50G', `${language} dossier model`);
  assert.equal(committed.dossierPrice, committed.expectedPrice, `${language} dossier price`);
  assert.equal(committed.dossierPrice, language === 'th' ? '170,000 บาท' : '170,000 THB', `${language} localized committed price`);
  assert.equal(committed.dossierLeadTime, committed.expectedLeadTime, `${language} dossier lead time`);
  assert.equal(committed.announcementChanges.length, 1, `${language} announcement count`);
  assert.match(committed.announcement, /50G/, `${language} localized announcement`);
  assert.equal(committed.links.length, 2, `${language} configurator links`);
  assert.ok(committed.links.every(({ variant }) => /^\d+$/.test(variant)), `${language} numeric variants`);
  assert.notEqual(committed.links[0].variant, committed.links[1].variant, `${language} distinct variants`);
  assert.ok(committed.decodedFrames >= 60, `${language} continuous decoded motion`);
  assert.equal(committed.finalFrame, 'front', `${language} final playback frame`);
  assert.equal(committed.paused, true, `${language} finite playback`);
  assert.equal(committed.loop, false, `${language} no looping`);
  assert.equal(committed.transformed, false, `${language} playback image transform`);
}

async function machineNavigationProbe(session, diagnostics, language, url) {
  for (const [width, height, source] of [[1280, 800, 'card'], [390, 844, 'dossier']]) {
    await setViewport(session, width, height);
    await navigate(session, url, diagnostics);
    await suppressCookieConsent(session);
    for (const [model, variant] of [['30G', '54823758627095'], ['50G', '54823758659863']]) {
      const selector = source === 'card'
        ? `[data-pimm-collection-card][data-model="${model}"] .pimm-collection__card-actions a`
        : `[data-pimm-collection-inline-dossier][data-model="${model}"] [data-pimm-dossier-configure]`;
      await evaluate(session, `document.querySelector('[data-pimm-collection-comparison]').commitModel(${JSON.stringify(model)})`);
      const links = await evaluate(session, `(() => [...document.querySelectorAll('.pimm-collection__card-actions a, [data-pimm-dossier-configure]')].map(a => {
        const target = new URL(a.href);
        return { path: target.pathname, view: target.searchParams.get('view'), keyMatches: target.searchParams.get('preview_key') === new URL(location.href).searchParams.get('preview_key') };
      }))()`);
      assert.ok(links.every(link => link.path === new URL(url).pathname && link.view === 'pimm-configurator' && link.keyMatches), `${language} every card/dossier route preserves preview`);
      const history = await session.send('Page.getNavigationHistory');
      const entryId = history.entries[history.currentIndex].id;
      await evaluate(session, `document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block: 'center', behavior: 'instant'})`);
      const point = await eventually(() => evaluate(session, `(() => {
        const anchor = document.querySelector(${JSON.stringify(selector)});
        const r = anchor.getBoundingClientRect();
        const point = {x:r.x+r.width/2, y:r.y+r.height/2};
        return anchor.contains(document.elementFromPoint(point.x, point.y)) ? point : false;
      })()`), { message: `${language} ${source} ${model} CTA is unobstructed before clicking` });
      await diagnostics.assertClean(`${language} ${source} ${model} collection before click`);
      diagnostics.begin(await evaluate(session, `document.querySelector(${JSON.stringify(selector)}).href`));
      await session.send('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point });
      await session.send('Input.dispatchMouseEvent', { type: 'mousePressed', button: 'left', clickCount: 1, ...point });
      await session.send('Input.dispatchMouseEvent', { type: 'mouseReleased', button: 'left', clickCount: 1, ...point });
      await eventually(() => evaluate(session, `(() => {
        const root = document.querySelector('pimm-machine-product');
        return root?.payloadContractValid
          && root.selectedMediaModel === ${JSON.stringify(model)}
          && document.querySelector('[data-pimm-model-radio]:checked')?.value === ${JSON.stringify(variant)};
      })()`), { message: `${language} ${source} ${model} opens the working configurator` }).catch(async error => {
        const state = await evaluate(session, `({readyState:document.readyState, valid:document.querySelector('pimm-machine-product')?.payloadContractValid, path:location.pathname, view:new URL(location.href).searchParams.get('view'), variant:new URL(location.href).searchParams.get('variant'), checked:document.querySelector('[data-pimm-model-radio]:checked')?.value, model:document.querySelector('pimm-machine-product')?.selectedMediaModel})`);
        throw new Error(`${error.message}; destination state: ${JSON.stringify(state)}`, { cause: error });
      });
      await assertNoStorefrontFailureSurface(session, `${language} ${source} ${model} destination`);
      const destination = await evaluate(session, `({pathname:location.pathname, variant:new URL(location.href).searchParams.get('variant'), view:new URL(location.href).searchParams.get('view'), language:document.documentElement.lang})`);
      assert.equal(destination.pathname, new URL(url).pathname);
      assert.equal(destination.variant, variant);
      assert.equal(destination.view, 'pimm-configurator');
      assert.ok(destination.language.startsWith(language));
      await diagnostics.assertClean(`${language} ${source} ${model} destination`);
      diagnostics.begin(url);
      await session.send('Page.navigateToHistoryEntry', { entryId });
      await eventually(() => evaluate(session, `document.readyState === 'complete' && new URL(location.href).searchParams.get('view') === 'pimm-collection-preview' && !!document.querySelector('[data-pimm-collection-comparison]')?.recordByModel`), { message: 'Browser back restores the enhanced comparison' });
      await diagnostics.assertClean(`${language} browser back`);
    }
  }
}

async function ctaColorProbe(session, language) {
  const selector = '.pimm-collection__card-actions :is(a, button), .pimm-collection__dossier-actions a';
  const snapshot = (index) => `(() => {
    const button = document.querySelectorAll(${JSON.stringify(selector)})[${index}];
    const style = getComputedStyle(button);
    const rect = button.getBoundingClientRect();
    return { background: style.backgroundColor, color: style.color, border: style.borderTopColor,
      outline: style.outlineStyle, duration: style.transitionDuration,
      height: rect.height, width: rect.width, x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
  })()`;
  for (const [width, height] of [[1280, 720], [390, 844]]) {
    await setViewport(session, width, height);
    await evaluate(session, 'document.activeElement?.blur(); scrollTo(0, 0)');
    const buttons = await evaluate(session, `(() => [...document.querySelectorAll(${JSON.stringify(selector)})]
      .map((button, index) => ({ index, visible: !!button.getClientRects().length,
        primary: button.matches('.pimm-collection__card-actions a') }))
      .filter(button => button.visible))()`);
    assert.equal(buttons.length, 7, `${language} ${width} all seven CTA roles`);
    for (const { index, primary } of buttons) {
      const context = `${language} ${width} CTA ${index}`;
      await evaluate(session, `document.activeElement?.blur(); document.querySelectorAll(${JSON.stringify(selector)})[${index}].scrollIntoView({block: 'center'})`);
      await session.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 1, y: 1 });
      await delay(250);
      const initial = await evaluate(session, snapshot(index));
      assert.equal(initial.background, primary ? 'rgb(17, 19, 21)' : 'rgba(0, 0, 0, 0)', `${context} default role`);
      assert.ok(initial.height >= 44 && initial.width >= 44, `${context} target size`);
      await session.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: initial.x, y: initial.y });
      await delay(250);
      const hovered = await evaluate(session, snapshot(index));
      assert.equal(hovered.background, 'rgb(8, 121, 201)', `${context} blue hover`);
      assert.equal(hovered.border, hovered.background, `${context} blue border`);
      assert.equal(hovered.color, 'rgb(255, 255, 255)', `${context} white hover label`);
      assert.equal(hovered.height, initial.height, `${context} no hover shift`);
      // WCAG contrast computed from the actual browser-resolved hover color.
      const channels = hovered.background.match(/\d+/g).map(Number).map(value => value / 255)
        .map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
      const luminance = channels.reduce((sum, value, i) => sum + value * [0.2126, 0.7152, 0.0722][i], 0);
      assert.ok(1.05 / (luminance + 0.05) >= 4.5, `${context} AA label contrast`);
      await session.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 1, y: 1 });
      await session.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
      await session.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
      await evaluate(session, `document.querySelectorAll(${JSON.stringify(selector)})[${index}].focus()`);
      await delay(250);
      const focused = await evaluate(session, snapshot(index));
      assert.equal(focused.background, hovered.background, `${context} keyboard blue state`);
      assert.equal(focused.outline, 'solid', `${context} keyboard outline`);
    }
    await session.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    for (const { index } of buttons) {
      assert.equal((await evaluate(session, snapshot(index))).duration, '0s', `${language} ${width} CTA reduced motion`);
    }
    await captureFullPageScreenshot(session, join(evidenceDir, `${language}-cta-focus-${width}.png`));
    await session.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
    await evaluate(session, 'document.activeElement?.blur(); scrollTo(0, 0)');
  }
  await setViewport(session, 1280, 800);
}

async function cinematicFocusProbe(session, language) {
  await evaluate(session, 'scrollTo(0, 0); document.activeElement?.blur()');
  await session.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 1, y: 1 });
  const snapshot = `(() => [...document.querySelectorAll('[data-pimm-collection-card]')].map(card => {
    const rect = card.getBoundingClientRect();
    const media = card.querySelector('.pimm-collection__media');
    return {
      x: rect.x, y: rect.y, width: rect.width, height: rect.height,
      transform: getComputedStyle(card).transform,
      border: getComputedStyle(card).borderTopColor,
      shadow: getComputedStyle(card).boxShadow,
      opacity: Number(getComputedStyle(media).opacity),
      transition: getComputedStyle(media).transitionDuration,
      title: getComputedStyle(card.querySelector('h2')).color,
      price: getComputedStyle(card.querySelector('[data-pimm-card-price]')).color,
      copy: getComputedStyle(card.querySelector('.pimm-collection__model-designation')).color,
      outline: getComputedStyle(card).outlineStyle,
      paused: card.querySelector('video').paused,
    };
  }))()`;
  await delay(500);
  const initial = await evaluate(session, snapshot);
  assert.deepEqual(initial.map(card => card.opacity), [1, 1]);
  for (const index of [0, 1]) {
    const card = initial[index];
    await session.send('Input.dispatchMouseEvent', {
      type: 'mouseMoved', x: card.x + card.width / 2, y: card.y + card.height / 2,
    });
    await delay(600);
    const hovered = await evaluate(session, snapshot);
    assert.equal(hovered[index].opacity, 1, `${language} active render unchanged`);
    assert.equal(hovered[1 - index].opacity, 0.68, `${language} sibling recedes`);
    assert.equal(hovered[index].paused, false, `${language} real rotation plays`);
    assert.notEqual(hovered[index].title, hovered[1 - index].title);
    assert.notEqual(hovered[index].price, hovered[1 - index].price);
    hovered.forEach((state, i) => {
      for (const key of ['x', 'y', 'width', 'height', 'copy']) assert.equal(state[key], initial[i][key]);
      assert.equal(state.transform, 'none');
      assert.equal(state.shadow, 'none');
      assert.equal(state.border, 'rgba(0, 0, 0, 0)');
    });
    await captureFullPageScreenshot(session, join(evidenceDir, `${language}-cinematic-${index}.png`));
  }
  await session.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 1, y: 1 });
  await delay(500);
  assert.deepEqual((await evaluate(session, snapshot)).map(card => card.opacity), [1, 1]);
  await session.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
  await session.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
  await evaluate(session, `document.querySelector('[data-pimm-collection-card]').focus()`);
  await delay(500);
  const focused = await evaluate(session, snapshot);
  assert.equal(focused[0].outline, 'solid', `${language} visible keyboard focus retained`);
  assert.deepEqual(focused.map(card => card.opacity), [1, 0.68]);
  await session.send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-motion', value: 'reduce' }],
  });
  await eventually(async () => {
    const reduced = await evaluate(session, snapshot);
    return reduced.every(card => card.transition === '0s' && card.paused);
  }, { message: `${language} reduced motion stops both clips and emphasis transitions` });
  await evaluate(session, 'document.activeElement?.blur()');
  await session.send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }],
  });
}

async function headerProbe(session, language) {
  await evaluate(session, 'scrollTo(0, 0)');
  await delay(320);
  const top = await evaluate(session, `(() => {
    const header = document.querySelector('[data-maliev-header]');
    return {
      overlay: header.classList.contains('mc-header--overlay'),
      solid: header.classList.contains('is-solid'),
      bright: header.classList.contains('is-overlay-bright'),
      background: getComputedStyle(header).backgroundColor,
    };
  })()`);
  assert.equal(top.overlay, true, `${language} overlay header`);
  assert.equal(top.solid, false, `${language} top header state`);
  assert.equal(top.bright, true, `${language} first-paint header tone`);
  assert.equal(top.background, 'rgba(0, 0, 0, 0)', `${language} transparent header`);
  if (await evaluate(session, 'document.documentElement.scrollHeight <= innerHeight + 1')) return;

  await evaluate(session, `(() => {
    const sentinel = document.querySelector('[data-header-overlay-sentinel]');
    scrollTo(0, sentinel.getBoundingClientRect().bottom + scrollY + 20);
    return true;
  })()`);
  await eventually(() => evaluate(
    session,
    `document.querySelector('[data-maliev-header]')?.classList.contains('is-solid')`,
  ), { message: `${language} header did not become solid after the bounded sentinel` });
  await delay(280);
  const solid = await evaluate(session, `(() => {
    const header = document.querySelector('[data-maliev-header]');
    return {
      background: getComputedStyle(header).backgroundColor,
      solid: header.classList.contains('is-solid'),
    };
  })()`);
  assert.equal(solid.solid, true, `${language} solid header state`);
  assert.equal(solid.background, 'rgb(255, 255, 255)', `${language} solid white header`);
  await evaluate(session, 'scrollTo(0, 0)');
}

async function reducedMotionProbe(session, diagnostics) {
  await session.send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-motion', value: 'reduce' }],
  });
  await session.send('Emulation.setTouchEmulationEnabled', {
    enabled: true,
    maxTouchPoints: 1,
  });
  await setViewport(session, 390, 844, true);
  await navigate(session, previewUrl, diagnostics);
  await suppressCookieConsent(session);
  await evaluate(session, `(() => {
    const root = document.querySelector('[data-pimm-collection-comparison]');
    const card = root.querySelector('[data-pimm-collection-card][data-model="50G"]');
    const observed = [];
    const observer = new MutationObserver(() => {
      observed.push(card.querySelector('[data-pimm-collection-frame]:not([hidden])')
        ?.dataset.pimmCollectionFrame);
    });
    observer.observe(card, { attributes: true, attributeFilter: ['hidden'], subtree: true });
    window.__pimmReducedMotionTouchProbe = { card, observed, observer };
    return true;
  })()`);
  await dispatchTouchTap(
    session,
    '[data-pimm-collection-card][data-model="50G"] [data-pimm-collection-select]',
  );
  await delay(900);
  const reduced = await evaluate(session, `(() => {
    const root = document.querySelector('[data-pimm-collection-comparison]');
    const probe = window.__pimmReducedMotionTouchProbe;
    probe.observer.disconnect();
    delete window.__pimmReducedMotionTouchProbe;
    return {
      active: root.activeModel,
      committed: root.committedModel,
      frame: probe.card.querySelector('[data-pimm-collection-frame]:not([hidden])')
        ?.dataset.pimmCollectionFrame,
      observed: probe.observed,
      videoPaused: probe.card.querySelector('video').paused,
      videoTime: probe.card.querySelector('video').currentTime,
      cardTransition: getComputedStyle(probe.card).transitionDuration,
    };
  })()`);
  assert.equal(reduced.active, '50G');
  assert.equal(reduced.committed, '50G');
  assert.equal(reduced.frame, 'front');
  assert.equal(reduced.videoPaused, true);
  assert.equal(reduced.videoTime, 0);
  assert.ok(reduced.observed.every((frame) => frame === 'front'));
  assert.equal(new Set(reduced.observed).size <= 1, true);
  assert.match(reduced.cardTransition, /(?:^|, )0s(?:,|$)/);
  await diagnostics.assertClean('EN 390x844 reduced-motion real mobile touch');
  await session.send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }],
  });
}

async function lifecycleProbe(session, diagnostics) {
  await navigate(session, previewUrl, diagnostics);
  const lifecycle = await evaluate(session, `(async () => {
    const root = document.querySelector('[data-pimm-collection-comparison]');
    root.querySelector('[data-pimm-collection-card][data-model="50G"]')
      .querySelector('[data-pimm-collection-select]').click();
    const parent = root.parentNode;
    root.remove();
    parent.appendChild(root);
    parent.dispatchEvent(new CustomEvent('shopify:section:load', { bubbles: true }));
    await Promise.resolve();
    const reset = { active: root.activeModel, committed: root.committedModel };
    root.querySelector('[data-pimm-collection-card][data-model="50G"]')
      .querySelector('[data-pimm-collection-select]').click();
    return {
      reset,
      activeAfterClick: root.activeModel,
      committedAfterClick: root.committedModel,
    };
  })()`);
  assert.deepEqual(lifecycle.reset, { active: '30G', committed: '30G' });
  assert.equal(lifecycle.activeAfterClick, '50G');
  assert.equal(lifecycle.committedAfterClick, '50G');
  await diagnostics.assertClean('EN section reconnect lifecycle');
}

test('missing preview URL is an intentional PIMM collection browser-matrix skip', {
  skip: Boolean(previewUrl),
}, () => {
  assert.equal(previewUrl, undefined);
});

test('dedicated PIMM collection passes responsive, interaction, and localization acceptance', {
  skip: previewUrl ? false : 'PIMM_COLLECTION_PREVIEW_URL is not set',
  timeout: 240_000,
}, async (context) => {
  await mkdir(evidenceDir, { recursive: true });
  const browser = await launchBrowser();
  const { session } = browser;
  const diagnostics = createBrowserDiagnostics(session);
  try {
    await session.send('Page.enable');
    await session.send('Runtime.enable');
    await session.send('Log.enable');
    await session.send('Page.bringToFront');
    for (const [language, url] of [['en', previewUrl], ['th', thaiUrlFrom(previewUrl)]]) {
      await session.send('Emulation.setEmulatedMedia', {
        features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }],
      });
      await setViewport(session, viewports[0][0], viewports[0][1]);
      await navigate(session, url, diagnostics);
      await suppressCookieConsent(session);
      await decodeCollectionImages(session);
      for (const [width, height] of viewports) {
        await setViewport(session, width, height);
        await evaluate(session, 'scrollTo(0, 0)');
        await assertGeometry(session, language, width, height);
        await captureFullPageScreenshot(
          session,
          join(evidenceDir, `${language}-${width}x${height}.png`),
        );
        await diagnostics.assertClean(`${language} ${width}x${height} matrix`);
      }
      // Let Chrome finish its preload-use window before replacing the document;
      // otherwise navigating away early creates a false late warning on the next locale.
      await delay(4_000);
      await diagnostics.assertClean(`${language} settled preview diagnostics`);
      await setViewport(session, 1280, 800);
      if (language === 'th') {
        const thaiLabels = await evaluate(session, `(() => ({
          lang: document.documentElement.lang,
          dossierLabels: [...document.querySelectorAll(
            '.pimm-collection__dossier--desktop dt',
          )].map((node) => node.textContent.trim()),
        }))()`);
        assert.match(thaiLabels.lang, /^th(?:-|$)/i);
        assert.ok(thaiLabels.dossierLabels.length >= 7);
        assert.ok(thaiLabels.dossierLabels.every((label) => /[\u0E00-\u0E7F]/.test(label)));
      }
      await interactionProbe(session, language);
      await cinematicFocusProbe(session, language);
      await ctaColorProbe(session, language);
      await headerProbe(session, `${language} desktop`);
      await inlineSupportActionProbe(session, diagnostics, language);
      await diagnostics.assertClean(`${language} desktop interaction and header`);
    }

    await machineNavigationProbe(session, diagnostics, 'en', previewUrl);
    await machineNavigationProbe(session, diagnostics, 'th', thaiUrlFrom(previewUrl));
    await noJavaScriptFallbackProbe(session, diagnostics, 'en', previewUrl);
    await noJavaScriptFallbackProbe(session, diagnostics, 'th', thaiUrlFrom(previewUrl));

    await mobileTouchProbe(session, diagnostics, 'en', previewUrl);
    await mobileTouchProbe(session, diagnostics, 'th', thaiUrlFrom(previewUrl));

    await reducedMotionProbe(session, diagnostics);
    await session.send('Emulation.setTouchEmulationEnabled', { enabled: false });
    await setViewport(session, 1280, 800);
    await lifecycleProbe(session, diagnostics);
    context.diagnostic(`bounded navigation retries: ${diagnostics.navigationRetryCount}`);
  } finally {
    await browser.close();
  }
});
