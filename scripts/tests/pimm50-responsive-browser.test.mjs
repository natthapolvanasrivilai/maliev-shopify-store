import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createHash, randomBytes } from 'node:crypto';
import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { connect as connectTcp } from 'node:net';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

const route = process.env.PIMM50_BROWSER_URL
  ?? 'http://127.0.0.1:9393/products/pneumatic-injection-molding-machine-50g';

const viewports = [
  [320, 568],
  [390, 844],
  [430, 932],
  [768, 1024],
  [820, 1180],
  [1024, 768],
  [1440, 900],
  [1920, 1080],
  [3840, 2160],
  [720, 540],
  [852, 393],
];
const screenshotDir = process.env.PIMM50_SCREENSHOT_DIR;
const screenshotViewports = [[820, 1180], [3840, 2160], [390, 844], [852, 393]];

const chromeCandidates = [
  process.env.PIMM50_CHROME_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
].filter(Boolean);

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function eventually(action, { timeout = 15_000, interval = 100 } = {}) {
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
  #pending = new Map();
  #listeners = new Map();

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
  }

  send(method, params = {}) {
    const id = ++this.#id;
    return new Promise((resolve, reject) => {
      this.#pending.set(id, { resolve, reject });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  async close() {
    await this.socket.close();
  }
}

const websocketGuid = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11';

function encodeClientFrame(value, opcode = 0x1) {
  const payload = Buffer.isBuffer(value) ? value : Buffer.from(String(value));
  const mask = randomBytes(4);
  let header;

  if (payload.length < 126) {
    header = Buffer.from([0x80 | opcode, 0x80 | payload.length]);
  } else if (payload.length <= 0xffff) {
    header = Buffer.alloc(4);
    header[0] = 0x80 | opcode;
    header[1] = 0x80 | 126;
    header.writeUInt16BE(payload.length, 2);
  } else {
    header = Buffer.alloc(10);
    header[0] = 0x80 | opcode;
    header[1] = 0x80 | 127;
    header.writeBigUInt64BE(BigInt(payload.length), 2);
  }

  const masked = Buffer.allocUnsafe(payload.length);
  for (let index = 0; index < payload.length; index += 1) masked[index] = payload[index] ^ mask[index % 4];
  return Buffer.concat([header, mask, masked]);
}

class BuiltinWebSocket {
  #buffer = Buffer.alloc(0);
  #closed;
  #fragments = [];
  #listeners = new Map();

  constructor(socket, initialData = Buffer.alloc(0)) {
    this.socket = socket;
    this.#closed = new Promise((resolve) => socket.once('close', resolve));
    socket.on('data', (chunk) => this.#receive(chunk));
    socket.on('error', (error) => this.#emit('error', { error }));
    socket.on('close', () => this.#emit('close', {}));
    if (initialData.length) this.#receive(initialData);
  }

  addEventListener(type, listener, options = {}) {
    const listeners = this.#listeners.get(type) ?? [];
    listeners.push({ listener, once: options.once === true });
    this.#listeners.set(type, listeners);
  }

  #emit(type, event) {
    const listeners = this.#listeners.get(type) ?? [];
    for (const entry of [...listeners]) {
      entry.listener(event);
      if (entry.once) listeners.splice(listeners.indexOf(entry), 1);
    }
  }

  #receive(chunk) {
    this.#buffer = Buffer.concat([this.#buffer, chunk]);
    while (this.#buffer.length >= 2) {
      const first = this.#buffer[0];
      const second = this.#buffer[1];
      const final = Boolean(first & 0x80);
      const opcode = first & 0x0f;
      const masked = Boolean(second & 0x80);
      let length = second & 0x7f;
      let offset = 2;

      if (length === 126) {
        if (this.#buffer.length < 4) return;
        length = this.#buffer.readUInt16BE(2);
        offset = 4;
      } else if (length === 127) {
        if (this.#buffer.length < 10) return;
        const extendedLength = this.#buffer.readBigUInt64BE(2);
        assert.ok(extendedLength <= BigInt(Number.MAX_SAFE_INTEGER), 'WebSocket frame exceeds the supported size');
        length = Number(extendedLength);
        offset = 10;
      }

      const maskLength = masked ? 4 : 0;
      if (this.#buffer.length < offset + maskLength + length) return;
      const mask = masked ? this.#buffer.subarray(offset, offset + 4) : undefined;
      offset += maskLength;
      const payload = Buffer.from(this.#buffer.subarray(offset, offset + length));
      this.#buffer = this.#buffer.subarray(offset + length);
      if (mask) for (let index = 0; index < payload.length; index += 1) payload[index] ^= mask[index % 4];

      if (opcode === 0x8) {
        this.socket.end();
        return;
      }
      if (opcode === 0x9) {
        this.socket.write(encodeClientFrame(payload, 0xA));
        continue;
      }
      if (opcode === 0xA) continue;
      if (opcode === 0x1) this.#fragments = [payload];
      else if (opcode === 0x0) this.#fragments.push(payload);
      else continue;

      if (final) {
        this.#emit('message', { data: Buffer.concat(this.#fragments).toString('utf8') });
        this.#fragments = [];
      }
    }
  }

  send(value) {
    this.socket.write(encodeClientFrame(value));
  }

  async close() {
    if (!this.socket.destroyed) {
      this.socket.write(encodeClientFrame(Buffer.alloc(0), 0x8));
      this.socket.end();
    }
    const closed = await Promise.race([
      this.#closed.then(() => true),
      delay(1_000).then(() => false),
    ]);
    if (!closed && !this.socket.destroyed) {
      this.socket.destroy();
      await Promise.race([this.#closed, delay(1_000)]);
    }
  }
}

async function connectSocket(url) {
  const endpoint = new URL(url);
  assert.equal(endpoint.protocol, 'ws:', 'The dependency-free CDP transport supports local ws:// endpoints');
  const key = randomBytes(16).toString('base64');
  const expectedAccept = createHash('sha1').update(`${key}${websocketGuid}`).digest('base64');
  const socket = connectTcp({ host: endpoint.hostname, port: Number(endpoint.port || 80) });
  await new Promise((resolve, reject) => {
    socket.once('connect', resolve);
    socket.once('error', reject);
  });
  socket.write([
    `GET ${endpoint.pathname}${endpoint.search} HTTP/1.1`,
    `Host: ${endpoint.host}`,
    'Connection: Upgrade',
    'Upgrade: websocket',
    'Sec-WebSocket-Version: 13',
    `Sec-WebSocket-Key: ${key}`,
    '\r\n',
  ].join('\r\n'));

  return new Promise((resolve, reject) => {
    let response = Buffer.alloc(0);
    const onError = (error) => reject(error);
    const onData = (chunk) => {
      response = Buffer.concat([response, chunk]);
      const boundary = response.indexOf('\r\n\r\n');
      if (boundary === -1) return;
      socket.off('data', onData);
      socket.off('error', onError);
      const headers = response.subarray(0, boundary).toString('utf8');
      const accept = headers.match(/^sec-websocket-accept:\s*(.+)$/im)?.[1]?.trim();
      if (!/^HTTP\/1\.1 101\b/.test(headers) || accept !== expectedAccept) {
        socket.destroy();
        reject(new Error(`Chrome rejected the WebSocket upgrade for ${url}`));
        return;
      }
      resolve(new BuiltinWebSocket(socket, response.subarray(boundary + 4)));
    };
    socket.on('data', onData);
    socket.once('error', onError);
  });
}

async function waitForBrowserExit(browser, timeout) {
  if (browser.exitCode !== null || browser.signalCode !== null) return true;
  return new Promise((resolve) => {
    const onExit = () => {
      clearTimeout(timer);
      resolve(true);
    };
    const timer = setTimeout(() => {
      browser.off('exit', onExit);
      resolve(false);
    }, timeout);
    browser.once('exit', onExit);
  });
}

async function stopBrowser(browser) {
  if (browser.exitCode !== null || browser.signalCode !== null) return;
  browser.kill();
  if (await waitForBrowserExit(browser, 5_000)) return;
  browser.kill('SIGKILL');
  await waitForBrowserExit(browser, 2_000);
}

const transientProfileRemovalErrors = new Set(['EBUSY', 'ENOTEMPTY', 'EPERM']);

async function removeTemporaryProfile(path, {
  initialDelay = 50,
  maxAttempts = 10,
  remove = rm,
  wait = delay,
} = {}) {
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      await remove(path, { force: true, recursive: true });
      return;
    } catch (error) {
      if (!transientProfileRemovalErrors.has(error?.code) || attempt === maxAttempts) throw error;
      await wait(Math.min(initialDelay * (2 ** (attempt - 1)), 1_000));
    }
  }
}

async function requestBrowserClose(session) {
  await Promise.race([
    session.send('Browser.close').catch(() => undefined),
    delay(2_000),
  ]);
}

async function launchBrowser() {
  const executable = chromeCandidates.find((candidate) => existsSync(candidate));
  assert.ok(executable, 'Chrome or Edge is required; set PIMM50_CHROME_PATH when installed elsewhere');

  const userDataDir = await mkdtemp(join(tmpdir(), 'pimm50-browser-'));
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
    '--no-first-run',
    '--no-default-browser-check',
    'about:blank',
  ], { stdio: 'ignore', windowsHide: true });

  try {
    const activePortFile = join(userDataDir, 'DevToolsActivePort');
    const port = await eventually(async () => {
      const [value] = (await readFile(activePortFile, 'utf8')).trim().split(/\r?\n/);
      return Number(value) || undefined;
    });

    const target = await eventually(async () => {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      const targets = await response.json();
      return targets.find((candidate) => candidate.type === 'page' && candidate.webSocketDebuggerUrl);
    });
    const session = new CdpSession(await connectSocket(target.webSocketDebuggerUrl));

    return {
      session,
      async close() {
        let cleanupError;
        const cleanup = async (action) => {
          try {
            await action();
          } catch (error) {
            cleanupError ??= error;
          }
        };
        await cleanup(() => requestBrowserClose(session));
        await cleanup(() => session.close());
        await cleanup(() => stopBrowser(browser));
        await cleanup(() => removeTemporaryProfile(userDataDir));
        if (cleanupError) {
          throw cleanupError;
        }
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

async function waitForPage(session) {
  await eventually(async () => evaluate(session, `document.readyState === 'complete' && Boolean(document.querySelector('[data-pimm50-page]'))`), {
    timeout: 30_000,
  });
  await eventually(async () => evaluate(session, `(() => {
    const hero = document.querySelector('#pimm50-hero img');
    return hero?.complete && hero.naturalWidth > 0;
  })()`), {
    timeout: 30_000,
  });
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

const viewportProbe = `(() => {
  const page = document.querySelector('[data-pimm50-page]');
  const html = document.documentElement;
  const body = document.body;
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
  };
  const rectOf = (element) => {
    const rect = element.getBoundingClientRect();
    return { bottom: rect.bottom, height: rect.height, left: rect.left, right: rect.right, top: rect.top, width: rect.width };
  };
  const inside = (inner, outer, tolerance = 1) => inner.left >= outer.left - tolerance
    && inner.right <= outer.right + tolerance
    && inner.top >= outer.top - tolerance
    && inner.bottom <= outer.bottom + tolerance;
  const intersects = (first, second) => Math.min(first.right, second.right) - Math.max(first.left, second.left) > 2
    && Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top) > 2;

  const semanticSelector = 'h1, h2, p, dt, dd, select, a, button';
  const semantic = [...page.querySelectorAll(semanticSelector)].filter(visible);
  const outsideSection = semantic.flatMap((element) => {
    const section = element.closest('section');
    if (!section) return [{ element: element.outerHTML.slice(0, 120), reason: 'no owning section' }];
    return inside(rectOf(element), rectOf(section)) ? [] : [{ element: element.outerHTML.slice(0, 120), section: section.id }];
  });

  const copy = [...page.querySelectorAll('h1, h2, p, dt, dd, label, select, a, button')].filter(visible);
  const media = [...page.querySelectorAll('[data-pimm50-media], .pimm50-comparison__stage img')].filter(visible);
  const collisions = copy.flatMap((copyElement) => {
    const section = copyElement.closest('section');
    return media.flatMap((mediaElement) => {
      if (mediaElement.closest('section') !== section) return [];
      return intersects(rectOf(copyElement), rectOf(mediaElement))
        ? [{ copy: copyElement.outerHTML.slice(0, 100), media: mediaElement.outerHTML.slice(0, 100), section: section.id }]
        : [];
    });
  });

  const flowElements = [...new Set([
    page,
    ...page.querySelectorAll('section, article, aside, div, figure, picture, [data-pimm50-motion], [data-pimm50-media]'),
  ])];
  const viewportProperties = new Map();
  const viewportUnit = /(?:^|[^a-z])(?:-?\\d*\\.?\\d+)?(?:dvh|svh|lvh|vh)(?:[^a-z]|$)/i;
  const properties = ['height', 'min-height', 'max-height'];
  const rememberViewportProperty = (element, property) => {
    const authored = viewportProperties.get(element) ?? new Set();
    authored.add(property);
    viewportProperties.set(element, authored);
  };
  const inspectRules = (rules) => {
    for (const rule of rules) {
      if (rule.selectorText && rule.style) {
        const authored = properties.filter((property) => viewportUnit.test(rule.style.getPropertyValue(property)));
        if (authored.length) {
          for (const element of flowElements) {
            try {
              if (element.matches(rule.selectorText)) authored.forEach((property) => rememberViewportProperty(element, property));
            } catch (_) {
              // Pseudo-element and vendor selectors do not target a real chapter wrapper.
            }
          }
        }
      }
      if (rule.cssRules) inspectRules(rule.cssRules);
    }
  };
  for (const sheet of document.styleSheets) {
    try {
      inspectRules(sheet.cssRules);
    } catch (_) {
      // Cross-origin app styles are outside the PIMM page boundary.
    }
  }
  for (const element of flowElements) {
    properties.forEach((property) => {
      if (viewportUnit.test(element.style.getPropertyValue(property))) rememberViewportProperty(element, property);
    });
  }

  const approximatelyViewport = (value) => Number.isFinite(Number.parseFloat(value))
    && Math.abs(Number.parseFloat(value) - innerHeight) <= Math.max(2, innerHeight * .005);
  const chapterLayerElements = new Set();
  const chapterLayers = flowElements.flatMap((element) => {
    const style = getComputedStyle(element);
    const rect = rectOf(element);
    const authored = [...(viewportProperties.get(element) ?? [])];
    const computedByProperty = {
      height: style.height,
      'max-height': style.maxHeight,
      'min-height': style.minHeight,
    };
    const viewportSized = authored.filter((property) => approximatelyViewport(computedByProperty[property]));
    const layerPosition = style.position === 'fixed'
      || (style.position === 'sticky' && (rect.height >= innerHeight * .5 || viewportSized.length > 0));
    const snapAligned = !['none', 'auto'].includes(style.scrollSnapAlign);
    if (!layerPosition && !viewportSized.length && !snapAligned) return [];
    chapterLayerElements.add(element);
    return [{
      authoredViewportProperties: viewportSized,
      className: String(element.className).slice(0, 120),
      height: rect.height,
      id: element.id,
      position: style.position,
      scrollSnapAlign: style.scrollSnapAlign,
      tag: element.tagName.toLowerCase(),
    }];
  });

  const sections = [...page.querySelectorAll(':scope > section')].map((section) => {
    const style = getComputedStyle(section);
    const rect = rectOf(section);
    return {
      height: rect.height,
      id: section.id,
      minHeight: style.minHeight,
      position: style.position,
      scrollSnapAlign: style.scrollSnapAlign,
      viewportFixedHeight: chapterLayerElements.has(section),
    };
  });

  const alphaMedia = [...page.querySelectorAll('img')].filter((image) => /pimm50|maliev-pimm-30g-alpha/.test(image.currentSrc || image.src));
  const objectFitFailures = alphaMedia.filter((image) => getComputedStyle(image).objectFit !== 'contain').map((image) => image.currentSrc || image.src);

  const authoritativeMedia = [
    ['hero', page.querySelector('.pimm50-hero__media'), [506, 250, 895, 1170, 1400, 1400]],
    ['purchase', page.querySelector('.pimm50-purchase__media'), [514, 250, 894, 1167, 1400, 1400]],
  ].map(([kind, stage, fallbackBounds]) => {
    const image = stage.querySelector('img');
    const authoredBounds = stage.dataset.pimm50AlphaBounds;
    const values = authoredBounds ? authoredBounds.split(/\\s+/).map(Number) : fallbackBounds;
    const stageRect = rectOf(stage);
    const imageRect = rectOf(image);
    const [left, top, right, bottom, canvasWidth, canvasHeight] = values;
    const opaque = {
      bottom: imageRect.top + imageRect.height * bottom / canvasHeight,
      left: imageRect.left + imageRect.width * left / canvasWidth,
      right: imageRect.left + imageRect.width * right / canvasWidth,
      top: imageRect.top + imageRect.height * top / canvasHeight,
    };
    const clipped = {
      bottom: Math.min(opaque.bottom, stageRect.bottom),
      left: Math.max(opaque.left, stageRect.left),
      right: Math.min(opaque.right, stageRect.right),
      top: Math.max(opaque.top, stageRect.top),
    };
    const opaqueArea = Math.max(0, opaque.right - opaque.left) * Math.max(0, opaque.bottom - opaque.top);
    const visibleArea = Math.max(0, clipped.right - clipped.left) * Math.max(0, clipped.bottom - clipped.top);
    const section = stage.closest('section');
    const counterpart = section.querySelector(kind === 'hero' ? '.pimm50-hero__copy' : '.pimm50-purchase__panel');
    const content = stage.closest('.pimm50-page__content');
    return {
      alphaHeight: opaque.bottom - opaque.top,
      alphaWidth: opaque.right - opaque.left,
      content: rectOf(content),
      counterpart: rectOf(counterpart),
      hasHook: stage.dataset.pimm50AuthoritativeMedia === kind,
      kind,
      stage: stageRect,
      validBounds: Boolean(authoredBounds) && values.length === 6 && values.every(Number.isFinite),
      visibleFraction: opaqueArea > 0 ? visibleArea / opaqueArea : 0,
    };
  });

  const purchase = document.querySelector('#pimm50-purchase');
  const purchaseControls = [...purchase.querySelectorAll('select, a, button')].filter(visible).map((element) => ({
    disabled: 'disabled' in element ? element.disabled : false,
    height: rectOf(element).height,
    label: (element.textContent || element.getAttribute('aria-label') || '').trim(),
    tag: element.tagName.toLowerCase(),
  }));
  const select = purchase.querySelector('[data-pimm50-variant-select]');
  const addButton = purchase.querySelector('[data-pimm50-add-button]');
  const selectedOption = select.selectedOptions[0];
  let variants = [];
  try {
    variants = JSON.parse(purchase.querySelector('[data-pimm50-variant-data]').textContent);
  } catch (_) {
    variants = [];
  }
  const selectedVariant = variants.find((variant) => String(variant.id) === select.value);
  const availabilityFailures = [];
  if (!selectedVariant) availabilityFailures.push('selected option is absent from serialized variants');
  else {
    if (selectedOption.disabled !== !selectedVariant.available) availabilityFailures.push('selected option disabled state disagrees with availability');
    if (addButton.disabled !== !selectedVariant.available) availabilityFailures.push('Add to cart disabled state disagrees with availability');
    if (select.form.elements.namedItem('id')?.value !== String(selectedVariant.id)) availabilityFailures.push('native id field disagrees with serialized variant');
  }

  const fixedObstructions = [...document.querySelectorAll('body *')].filter((element) => {
    if (page.contains(element) || !visible(element)) return false;
    const style = getComputedStyle(element);
    const rect = rectOf(element);
    return style.position === 'fixed' && rect.width * rect.height > innerWidth * innerHeight * 0.02;
  }).map((element) => ({ className: String(element.className).slice(0, 100), id: element.id, tag: element.tagName.toLowerCase() }));

  return {
    alphaCount: alphaMedia.length,
    authoritativeMedia,
    availabilityFailures,
    chapterLayers,
    clientWidth: html.clientWidth,
    collisions,
    fixedObstructions,
    objectFitFailures,
    outsideSection,
    purchaseControls,
    scrollSnap: {
      body: getComputedStyle(body).scrollSnapType,
      html: getComputedStyle(html).scrollSnapType,
      page: getComputedStyle(page).scrollSnapType,
    },
    scrollWidth: html.scrollWidth,
    selectedAvailability: selectedVariant?.available,
    sections,
  };
})()`;

const posterVisibilityProbe = `async () => {
  const page = document.querySelector('[data-pimm50-page]');
  const pictures = [...page.querySelectorAll('picture')];
  const intersect = (bounds, rect, axes = 'both') => ({
    bottom: axes === 'x' ? bounds.bottom : Math.min(bounds.bottom, rect.bottom),
    left: axes === 'y' ? bounds.left : Math.max(bounds.left, rect.left),
    right: axes === 'y' ? bounds.right : Math.min(bounds.right, rect.right),
    top: axes === 'x' ? bounds.top : Math.max(bounds.top, rect.top),
  });
  const widthOf = (bounds) => Math.max(0, bounds.right - bounds.left);
  const heightOf = (bounds) => Math.max(0, bounds.bottom - bounds.top);

  for (const image of page.querySelectorAll('picture img')) image.loading = 'eager';
  await Promise.all([...page.querySelectorAll('picture img')].map((image) => image.decode().catch(() => undefined)));

  const results = [];
  for (const picture of pictures) {
    const image = picture.querySelector('img');
    image.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));

    const imageRect = image.getBoundingClientRect();
    let clipped = { bottom: imageRect.bottom, left: imageRect.left, right: imageRect.right, top: imageRect.top };
    let effectiveOpacity = 1;
    let effectivelyVisible = true;
    const hiddenAncestors = [];

    for (let ancestor = image; ancestor && page.contains(ancestor); ancestor = ancestor.parentElement) {
      const style = getComputedStyle(ancestor);
      const opacity = Number.parseFloat(style.opacity);
      if (Number.isFinite(opacity)) effectiveOpacity *= opacity;
      if (ancestor.hidden || style.display === 'none' || ['hidden', 'collapse'].includes(style.visibility) || style.contentVisibility === 'hidden') {
        effectivelyVisible = false;
        hiddenAncestors.push(ancestor.tagName.toLowerCase() + (ancestor.id ? '#' + ancestor.id : ''));
      }
      if (style.display === 'contents') continue;
      const ancestorRect = ancestor.getBoundingClientRect();
      if (/(?:hidden|clip|auto|scroll)/.test(style.overflowX)) clipped = intersect(clipped, ancestorRect, 'x');
      if (/(?:hidden|clip|auto|scroll)/.test(style.overflowY)) clipped = intersect(clipped, ancestorRect, 'y');
    }
    effectivelyVisible = effectivelyVisible && effectiveOpacity > .01;
    const hasVisibleGeometry = widthOf(clipped) > 2 && heightOf(clipped) > 2;

    const viewportBounds = intersect(clipped, { bottom: innerHeight, left: 0, right: innerWidth, top: 0 });
    const samplePoints = widthOf(viewportBounds) > 2 && heightOf(viewportBounds) > 2
      ? [
        [.5, .5],
        [.25, .25],
        [.75, .25],
        [.25, .75],
        [.75, .75],
      ].map(([xRatio, yRatio]) => ({
        x: viewportBounds.left + widthOf(viewportBounds) * xRatio,
        y: viewportBounds.top + heightOf(viewportBounds) * yRatio,
      }))
      : [];
    const unoccluded = samplePoints.some(({ x, y }) => {
      const pageHit = document.elementsFromPoint(x, y).find((element) => page.contains(element));
      return pageHit === image || pageHit?.contains(image) || image.contains(pageHit);
    });

    results.push({
      complete: image.complete && image.naturalWidth > 0,
      effectiveOpacity,
      effectivelyVisible,
      hasVisibleGeometry,
      hiddenAncestors,
      height: imageRect.height,
      source: image.currentSrc || image.src,
      unoccluded,
      width: imageRect.width,
    });
  }
  return results;
}`;

test('temporary profile cleanup retries a transient Windows file lock', async () => {
  let attempts = 0;
  const waits = [];
  const remove = async () => {
    attempts += 1;
    if (attempts < 3) {
      const error = new Error('simulated cookie lock');
      error.code = 'EBUSY';
      throw error;
    }
  };

  await assert.doesNotReject(() => removeTemporaryProfile('simulated-profile', {
    remove,
    wait: async (milliseconds) => waits.push(milliseconds),
  }));
  assert.equal(attempts, 3);
  assert.deepEqual(waits, [50, 100]);
});

test('PIMM 50G browser matrix preserves normal flow and section geometry', { timeout: 240_000 }, async (t) => {
  const response = await fetch(route);
  assert.equal(response.status, 200, `Local Shopify preview must serve ${route}`);

  const browser = await launchBrowser();
  t.after(() => browser.close());
  const { session } = browser;
  const exceptions = [];
  const logEntries = [];
  const requestUrls = new Map();
  const failedRequests = [];

  session.on('Runtime.exceptionThrown', ({ exceptionDetails }) => exceptions.push(exceptionDetails));
  session.on('Log.entryAdded', ({ entry }) => logEntries.push(entry));
  session.on('Network.requestWillBeSent', ({ requestId, request }) => requestUrls.set(requestId, request.url));
  session.on('Network.loadingFailed', ({ requestId, errorText }) => failedRequests.push({ errorText, url: requestUrls.get(requestId) ?? '' }));

  await Promise.all([
    session.send('Log.enable'),
    session.send('Network.enable'),
    session.send('Page.enable'),
    session.send('Runtime.enable'),
  ]);
  await session.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
  await session.send('Page.navigate', { url: route });
  await waitForPage(session);

  await t.test('geometry probe rejects a descendant viewport chapter layer', async () => {
    await setViewport(session, 390, 844);
    await evaluate(session, `(() => {
      const page = document.querySelector('[data-pimm50-page]');
      const mutations = [
        ['pimm50-test-height-layer', 'height: 100vh'],
        ['pimm50-test-min-height-layer', 'min-height: 100svh'],
        ['pimm50-test-max-height-layer', 'max-height: 100dvh'],
      ];
      for (const [id, size] of mutations) {
        const mutation = document.createElement('div');
        mutation.id = id;
        mutation.style.cssText = 'position: fixed; inset: 0; pointer-events: none; ' + size;
        page.append(mutation);
      }
      return true;
    })()`);
    try {
      const evidence = await evaluate(session, viewportProbe);
      const layers = new Map(evidence.chapterLayers.map((layer) => [layer.id, layer]));
      assert.ok(layers.get('pimm50-test-height-layer')?.authoredViewportProperties.includes('height'));
      assert.ok(layers.get('pimm50-test-min-height-layer')?.authoredViewportProperties.includes('min-height'));
      assert.ok(layers.get('pimm50-test-max-height-layer')?.authoredViewportProperties.includes('max-height'));
    } finally {
      await evaluate(session, `(() => {
        for (const id of ['pimm50-test-height-layer', 'pimm50-test-min-height-layer', 'pimm50-test-max-height-layer']) {
          document.getElementById(id)?.remove();
        }
        return true;
      })()`);
    }
  });

  await t.test('availability probe rejects a selected-variant button mismatch', async () => {
    await setViewport(session, 390, 844);
    const originalDisabled = await evaluate(session, `(() => {
      const add = document.querySelector('[data-pimm50-add-button]');
      const select = document.querySelector('[data-pimm50-variant-select]');
      const variants = JSON.parse(document.querySelector('[data-pimm50-variant-data]').textContent);
      const selected = variants.find((variant) => String(variant.id) === select.value);
      const original = add.disabled;
      add.disabled = selected.available;
      return original;
    })()`);
    try {
      const evidence = await evaluate(session, viewportProbe);
      assert.ok(evidence.availabilityFailures.includes('Add to cart disabled state disagrees with availability'));
    } finally {
      await evaluate(session, `document.querySelector('[data-pimm50-add-button]').disabled = ${JSON.stringify(originalDisabled)}; true`);
    }
  });

  for (const [width, height] of viewports) {
    await t.test(`${width}x${height}`, async () => {
      await setViewport(session, width, height);
      await evaluate(session, 'window.scrollTo(0, 0); true');
      await delay(150);
      const before = await evaluate(session, 'window.scrollY');
      await session.send('Input.dispatchMouseEvent', {
        deltaX: 0,
        deltaY: 400,
        type: 'mouseWheel',
        x: Math.floor(width / 2),
        y: Math.floor(height / 2),
      });
      await delay(800);
      const after = await evaluate(session, 'window.scrollY');
      const scrollDelta = after - before;
      const evidence = await evaluate(session, viewportProbe);

      assert.ok(scrollDelta >= 300 && scrollDelta <= 500, `${width}x${height}: 400px wheel delta moved ${scrollDelta}px`);
      assert.equal(evidence.scrollWidth, evidence.clientWidth, `${width}x${height}: horizontal overflow`);
      assert.deepEqual(evidence.scrollSnap, { body: 'none', html: 'none', page: 'none' }, `${width}x${height}: scroll snapping must be disabled`);
      assert.deepEqual(evidence.outsideSection, [], `${width}x${height}: semantic content escaped its owning section`);
      assert.deepEqual(evidence.collisions, [], `${width}x${height}: page media obscures semantic copy`);
      assert.deepEqual(evidence.objectFitFailures, [], `${width}x${height}: transparent product media must use object-fit contain`);
      assert.ok(evidence.alphaCount >= 8, `${width}x${height}: expected all transparent product media`);
      assert.deepEqual(evidence.chapterLayers, [], `${width}x${height}: descendant creates viewport-fixed chapter behavior`);
      assert.deepEqual(evidence.sections.filter((section) => section.position === 'fixed' || section.viewportFixedHeight), [], `${width}x${height}: section is viewport-fixed`);
      assert.deepEqual(evidence.sections.filter((section) => !['none', 'auto'].includes(section.scrollSnapAlign)), [], `${width}x${height}: section has snap alignment`);
      assert.deepEqual(evidence.purchaseControls.filter((control) => control.height < 44), [], `${width}x${height}: purchase target is shorter than 44px`);
      assert.deepEqual(evidence.availabilityFailures, [], `${width}x${height}: selected variant availability and Add-to-cart state disagree`);
      console.log(`PIMM50_AUTH_MEDIA=${JSON.stringify({ viewport: `${width}x${height}`, media: evidence.authoritativeMedia.map(({ alphaHeight, alphaWidth, content, counterpart, hasHook, kind, stage, validBounds, visibleFraction }) => ({ alphaHeight, alphaWidth, contentWidth: content.width, counterpartWidth: counterpart.width, hasHook, kind, stageHeight: stage.height, stageWidth: stage.width, validBounds, visibleFraction })) })}`);

      assert.equal(evidence.authoritativeMedia.length, 2, `${width}x${height}: hero and purchase must expose authoritative-media geometry`);
      assert.deepEqual(evidence.authoritativeMedia.filter((entry) => !entry.hasHook), [], `${width}x${height}: authoritative media hooks are missing`);
      assert.deepEqual(evidence.authoritativeMedia.filter((entry) => !entry.validBounds), [], `${width}x${height}: authoritative alpha bounds must be valid`);
      assert.deepEqual(evidence.authoritativeMedia.filter((entry) => entry.visibleFraction < .999), [], `${width}x${height}: opaque authoritative media is clipped`);

      if ([768, 820].includes(width) && height > width) {
        for (const media of evidence.authoritativeMedia) {
          assert.ok(media.stage.bottom <= media.counterpart.top + 1, `${width}x${height}: ${media.kind} media must stack before its reading column`);
          assert.ok(media.stage.width >= media.content.width * .9, `${width}x${height}: ${media.kind} media must use the tablet media field`);
          assert.ok(media.alphaHeight >= width * .8, `${width}x${height}: ${media.kind} machine is not authoritative enough (${media.alphaHeight}px)`);
        }
      }

      if (width === 3840 && height === 2160) {
        for (const media of evidence.authoritativeMedia) {
          assert.ok(media.content.width > 1440 && media.content.width <= 1920, `4K ${media.kind} field must expand beyond the 1440px reading grid in a controlled way`);
          assert.ok(media.alphaHeight >= 900, `4K ${media.kind} machine is not authoritative enough (${media.alphaHeight}px)`);
          assert.ok(media.counterpart.width >= 440 && media.counterpart.width <= 680, `4K ${media.kind} reading column must remain restrained and readable`);
        }
      }

      console.log(JSON.stringify({
        viewport: `${width}x${height}`,
        scrollDelta,
        overflow: evidence.scrollWidth - evidence.clientWidth,
        collisions: evidence.collisions.length,
        controls: evidence.purchaseControls.map(({ height, tag }) => `${tag}:${height.toFixed(1)}`),
        externalObstructions: evidence.fixedObstructions,
      }));
    });
  }

  await t.test('reduced motion keeps poster-only media complete and visible', async () => {
    await session.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    await setViewport(session, 390, 844);
    const evidence = await evaluate(session, `(async () => {
      const page = document.querySelector('[data-pimm50-page]');
      const motion = [...page.querySelectorAll('[data-pimm50-motion]')];
      return {
        pictures: await (${posterVisibilityProbe})(),
        reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
        progress: motion.map((element) => ({
          className: element.className,
          section: element.closest('section')?.id,
          value: getComputedStyle(element).getPropertyValue('--p50-progress').trim(),
        })),
        videos: page.querySelectorAll('video').length,
      };
    })()`);

    assert.equal(evidence.reduced, true);
    assert.equal(evidence.videos, 0, 'Task 4 intentionally ships poster-only media; do not invent a video fallback');
    assert.ok(evidence.pictures.length >= 8);
    assert.deepEqual(evidence.pictures.filter((poster) => !poster.complete || !poster.effectivelyVisible || !poster.hasVisibleGeometry || !poster.unoccluded), [], 'Reduced-motion posters must remain effectively visible');
    assert.deepEqual(evidence.progress.filter((entry) => entry.value !== '1'), [], 'Reduced motion must reveal every motion target');
  });

  await t.test('poster probe rejects hidden ancestors and page-owned occlusion', async () => {
    await session.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    await setViewport(session, 390, 844);
    const originalStyle = await evaluate(session, `(() => {
      const picture = document.querySelector('#pimm50-hero picture');
      const original = picture.getAttribute('style');
      picture.style.opacity = '0';
      return original;
    })()`);
    try {
      const hidden = await evaluate(session, `(${posterVisibilityProbe})()`);
      assert.equal(hidden[0].effectivelyVisible, false);
      assert.equal(hidden[0].effectiveOpacity, 0);
    } finally {
      await evaluate(session, `(() => {
        const picture = document.querySelector('#pimm50-hero picture');
        const original = ${JSON.stringify(originalStyle)};
        if (original === null) picture.removeAttribute('style');
        else picture.setAttribute('style', original);
        return true;
      })()`);
    }

    const originalOcclusionStyle = await evaluate(session, `(() => {
      const picture = document.querySelector('#pimm50-hero picture');
      const overlay = document.createElement('span');
      overlay.id = 'pimm50-test-poster-occlusion';
      overlay.style.cssText = 'background: #fff; inset: 0; position: absolute; z-index: 1';
      const original = picture.getAttribute('style');
      picture.style.position = 'relative';
      picture.append(overlay);
      return original;
    })()`);
    try {
      const occluded = await evaluate(session, `(${posterVisibilityProbe})()`);
      assert.equal(occluded[0].unoccluded, false);
    } finally {
      await evaluate(session, `(() => {
        const overlay = document.querySelector('#pimm50-test-poster-occlusion');
        const picture = overlay?.parentElement;
        overlay?.remove();
        const original = ${JSON.stringify(originalOcclusionStyle)};
        if (picture && original === null) picture.removeAttribute('style');
        else if (picture) picture.setAttribute('style', original);
        return true;
      })()`);
    }
  });

  await t.test('keyboard order, yellow focus, and native variant submission stay aligned', async () => {
    await session.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
    await setViewport(session, 390, 844);
    const initial = await evaluate(session, `(() => {
      const page = document.querySelector('[data-pimm50-page]');
      const select = document.querySelector('[data-pimm50-variant-select]');
      const form = select.form;
      const factory = form.querySelector('a[href]');
      const add = form.querySelector('[data-pimm50-add-button]');
      const variants = JSON.parse(document.querySelector('[data-pimm50-variant-data]').textContent);
      const current = variants.find((variant) => String(variant.id) === select.value);
      const sequential = [...page.querySelectorAll('a[href], button, input, select, textarea, [tabindex]')].filter((element) => {
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return !element.disabled
          && !element.hidden
          && !element.closest('[inert]')
          && element.tabIndex >= 0
          && style.display !== 'none'
          && style.visibility !== 'hidden'
          && rect.width > 0
          && rect.height > 0;
      });
      const selectIndex = sequential.indexOf(select);
      const prior = sequential[selectIndex - 1];
      prior?.focus();
      const identify = (element) => {
        if (element === select) return 'select';
        if (element === factory) return 'factory';
        if (element === add) return 'add';
        return 'other';
      };
      return {
        action: form.action,
        addInsideForm: add.form === form,
        currentAvailable: current.available,
        currentButtonDisabled: add.disabled,
        factoryInsideForm: form.contains(factory),
        name: select.name,
        priorFocused: document.activeElement === prior,
        priorLabel: (prior?.textContent || prior?.getAttribute('aria-label') || '').trim(),
        priorTabIndex: prior?.tabIndex,
        selectTabIndex: select.tabIndex,
        selectedFormValue: new FormData(form).get('id'),
        selectedValue: select.value,
        sequentialOrder: sequential.slice(selectIndex, selectIndex + 3).map(identify),
      };
    })()`);

    assert.equal(initial.name, 'id');
    assert.equal(initial.addInsideForm, true);
    assert.equal(initial.factoryInsideForm, true);
    assert.match(initial.action, /\/cart\/add/);
    assert.equal(initial.selectedFormValue, initial.selectedValue);
    assert.equal(initial.currentButtonDisabled, !initial.currentAvailable);
    assert.equal(initial.priorFocused, true, 'Known prior sequential control must receive the starting focus');
    assert.ok(initial.priorTabIndex >= 0);
    assert.ok(initial.selectTabIndex >= 0);
    assert.deepEqual(initial.sequentialOrder, ['select', 'factory', 'add']);

    const focusEvidence = [];
    await dispatchTab(session);
    focusEvidence.push(await evaluate(session, `(() => {
      const element = document.activeElement;
      const style = getComputedStyle(element);
      return { border: style.borderColor, color: style.outlineColor, focusVisible: element.matches(':focus-visible'), selector: element.matches('[data-pimm50-variant-select]') ? 'select' : 'other', width: parseFloat(style.outlineWidth) };
    })()`));
    await dispatchTab(session);
    focusEvidence.push(await evaluate(session, `(() => {
      const element = document.activeElement;
      const style = getComputedStyle(element);
      return { border: style.borderColor, color: style.outlineColor, focusVisible: element.matches(':focus-visible'), selector: element.matches('.pimm50-purchase__form a[href]') ? 'factory' : 'other', width: parseFloat(style.outlineWidth) };
    })()`));
    await dispatchTab(session);
    focusEvidence.push(await evaluate(session, `(() => {
      const element = document.activeElement;
      const style = getComputedStyle(element);
      return { border: style.borderColor, color: style.outlineColor, focusVisible: element.matches(':focus-visible'), selector: element.matches('[data-pimm50-add-button]') ? 'add' : 'other', width: parseFloat(style.outlineWidth) };
    })()`));

    assert.deepEqual(focusEvidence.map((entry) => entry.selector), ['select', 'factory', 'add']);
    for (const entry of focusEvidence) {
      assert.equal(entry.focusVisible, true, `${entry.selector} must expose :focus-visible`);
      assert.equal(entry.color, 'rgb(16, 24, 32)', `${entry.selector} must expose a dark indicator with 3:1 contrast on pale surfaces`);
      assert.ok(entry.width >= 3, `${entry.selector} focus outline must be at least 3px`);
    }

    const updated = await evaluate(session, `(() => {
      const select = document.querySelector('[data-pimm50-variant-select]');
      const form = select.form;
      const variants = JSON.parse(document.querySelector('[data-pimm50-variant-data]').textContent);
      const current = variants.find((variant) => variant.available && String(variant.id) !== select.value)
        ?? variants.find((variant) => String(variant.id) === select.value);
      select.value = String(current.id);
      select.dispatchEvent(new Event('change', { bubbles: true }));
      const add = document.querySelector('[data-pimm50-add-button]');
      return {
        available: current.available,
        buttonDisabled: add.disabled,
        formValue: new FormData(form).get('id'),
        price: document.querySelector('[data-pimm50-variant-price]').textContent,
        selectedValue: select.value,
        title: document.querySelector('[data-pimm50-variant-title]').textContent,
        variant: current,
      };
    })()`);

    assert.equal(updated.formValue, updated.selectedValue);
    assert.equal(updated.selectedValue, String(updated.variant.id));
    assert.equal(updated.title, updated.variant.title);
    assert.equal(updated.price, updated.variant.price);
    assert.equal(updated.buttonDisabled, !updated.available);
  });

  await t.test('variant changes announce one polite atomic commerce status', async () => {
    await session.send('Page.reload', { ignoreCache: true });
    await waitForPage(session);
    await setViewport(session, 390, 844);
    const initial = await evaluate(session, `(() => {
      const status = document.querySelector('[data-pimm50-variant-status]');
      return status && {
        atomic: status.getAttribute('aria-atomic'),
        display: getComputedStyle(status).display,
        live: status.getAttribute('aria-live'),
        role: status.getAttribute('role'),
        text: status.textContent.trim(),
        visibility: getComputedStyle(status).visibility,
      };
    })()`);

    assert.ok(initial, 'Variant status region must exist without JavaScript-generated markup');
    assert.equal(initial.role, 'status');
    assert.equal(initial.live, 'polite');
    assert.equal(initial.atomic, 'true');
    assert.equal(initial.text, '', 'Initial page hydration must not announce unchanged commerce state');
    assert.notEqual(initial.display, 'none');
    assert.notEqual(initial.visibility, 'hidden');

    const announcement = await evaluate(session, `(async () => {
      const panel = document.querySelector('.pimm50-purchase__panel');
      const select = panel.querySelector('[data-pimm50-variant-select]');
      const status = panel.querySelector('[data-pimm50-variant-status]');
      const variants = JSON.parse(panel.querySelector('[data-pimm50-variant-data]').textContent);
      const target = variants.find((variant) => String(variant.id) !== select.value) ?? variants[0];
      let mutations = 0;
      const observer = new MutationObserver((records) => { mutations += records.length; });
      observer.observe(status, { characterData: true, childList: true, subtree: true });
      select.value = String(target.id);
      select.dispatchEvent(new Event('change', { bubbles: true }));
      await Promise.resolve();
      const firstMutationCount = mutations;
      const firstText = status.textContent.trim();
      select.dispatchEvent(new Event('change', { bubbles: true }));
      await Promise.resolve();
      observer.disconnect();
      return {
        availability: target.available ? panel.dataset.pimm50MadeToOrderLabel : panel.dataset.pimm50SoldOutLabel,
        duplicateMutationCount: mutations - firstMutationCount,
        firstMutationCount,
        firstText,
        price: target.price,
        title: target.title,
      };
    })()`);

    assert.ok(announcement.firstMutationCount > 0, 'A real variant change must update the status region');
    assert.match(announcement.firstText, new RegExp(announcement.title.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    assert.match(announcement.firstText, new RegExp(announcement.price.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    assert.match(announcement.firstText, new RegExp(announcement.availability.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    assert.equal(announcement.duplicateMutationCount, 0, 'Redispatching the unchanged selection must not create a duplicate announcement');
  });

  if (screenshotDir) {
    await t.test('capture final hero and purchase screenshots', async () => {
      await mkdir(screenshotDir, { recursive: true });
      for (const [width, height] of screenshotViewports) {
        await setViewport(session, width, height);
        for (const [name, scrollExpression] of [
          ['hero', 'window.scrollTo(0, 0); true'],
          ['purchase', "document.querySelector('#pimm50-purchase').scrollIntoView({ block: 'center' }); true"],
        ]) {
          await evaluate(session, scrollExpression);
          await delay(150);
          const capture = await session.send('Page.captureScreenshot', { captureBeyondViewport: false, format: 'png', fromSurface: true });
          await writeFile(join(screenshotDir, `pimm50-final-${width}x${height}-${name}.png`), Buffer.from(capture.data, 'base64'));
        }
      }
    });
  }

  const pageOwned = (url = '', text = '') => /maliev-pimm-50g-story|pimm50/i.test(`${url} ${text}`);
  const pageExceptions = exceptions.filter((entry) => pageOwned(entry.url ?? entry.stackTrace?.callFrames?.[0]?.url, entry.exception?.description ?? entry.text));
  const pageLogs = logEntries.filter((entry) => ['error', 'warning'].includes(entry.level) && pageOwned(entry.url, entry.text));
  const pageFailures = failedRequests.filter((entry) => pageOwned(entry.url, entry.errorText));
  assert.deepEqual(pageExceptions, [], 'PIMM 50G scripts must not throw page-owned exceptions');
  assert.deepEqual(pageLogs, [], 'PIMM 50G scripts must not log page-owned errors');
  assert.deepEqual(pageFailures, [], 'PIMM 50G assets must not fail to load');

  const externalErrors = [
    ...exceptions.map((entry) => ({ kind: 'exception', message: entry.exception?.description ?? entry.text, url: entry.url ?? entry.stackTrace?.callFrames?.[0]?.url ?? '' })),
    ...logEntries.filter((entry) => ['error', 'warning'].includes(entry.level)).map((entry) => ({ kind: entry.level, message: entry.text, url: entry.url ?? '' })),
  ].filter((entry) => !pageOwned(entry.url, entry.message));
  console.log(`PIMM50_EXTERNAL_BROWSER_ERRORS=${JSON.stringify(externalErrors)}`);
});
