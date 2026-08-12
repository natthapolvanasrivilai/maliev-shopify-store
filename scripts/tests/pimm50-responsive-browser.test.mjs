import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
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

  close() {
    this.socket.close();
  }
}

async function connectSocket(url) {
  const socket = new WebSocket(url);
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true });
    socket.addEventListener('error', () => reject(new Error(`Unable to connect to ${url}`)), { once: true });
  });
  return socket;
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
      session.close();
      browser.kill();
      await new Promise((resolve) => browser.once('exit', resolve));
      await rm(userDataDir, { force: true, recursive: true });
    },
  };
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

  const sections = [...page.querySelectorAll(':scope > section')].map((section) => {
    const style = getComputedStyle(section);
    const rect = rectOf(section);
    return {
      height: rect.height,
      id: section.id,
      minHeight: style.minHeight,
      position: style.position,
      scrollSnapAlign: style.scrollSnapAlign,
      viewportFixedHeight: Math.abs(rect.height - innerHeight) < 0.5 && style.minHeight !== 'auto',
    };
  });

  const alphaMedia = [...page.querySelectorAll('img')].filter((image) => /pimm50|maliev-pimm-30g-alpha/.test(image.currentSrc || image.src));
  const objectFitFailures = alphaMedia.filter((image) => getComputedStyle(image).objectFit !== 'contain').map((image) => image.currentSrc || image.src);

  const purchase = document.querySelector('#pimm50-purchase');
  const purchaseControls = [...purchase.querySelectorAll('select, a, button')].filter(visible).map((element) => ({
    disabled: 'disabled' in element ? element.disabled : false,
    height: rectOf(element).height,
    label: (element.textContent || element.getAttribute('aria-label') || '').trim(),
    tag: element.tagName.toLowerCase(),
  }));

  const fixedObstructions = [...document.querySelectorAll('body *')].filter((element) => {
    if (page.contains(element) || !visible(element)) return false;
    const style = getComputedStyle(element);
    const rect = rectOf(element);
    return style.position === 'fixed' && rect.width * rect.height > innerWidth * innerHeight * 0.02;
  }).map((element) => ({ className: String(element.className).slice(0, 100), id: element.id, tag: element.tagName.toLowerCase() }));

  return {
    alphaCount: alphaMedia.length,
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
    sections,
  };
})()`;

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
      assert.deepEqual(evidence.sections.filter((section) => section.position === 'fixed' || section.viewportFixedHeight), [], `${width}x${height}: section is viewport-fixed`);
      assert.deepEqual(evidence.sections.filter((section) => !['none', 'auto'].includes(section.scrollSnapAlign)), [], `${width}x${height}: section has snap alignment`);
      assert.deepEqual(evidence.purchaseControls.filter((control) => control.height < 44), [], `${width}x${height}: purchase target is shorter than 44px`);

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
      const pictures = [...page.querySelectorAll('picture')];
      const motion = [...page.querySelectorAll('[data-pimm50-motion]')];
      for (const image of page.querySelectorAll('picture img')) image.loading = 'eager';
      await Promise.all([...page.querySelectorAll('picture img')].map((image) => image.decode().catch(() => undefined)));
      return {
        pictures: pictures.map((picture) => {
          const image = picture.querySelector('img');
          const rect = image.getBoundingClientRect();
          const style = getComputedStyle(image);
          return { complete: image.complete && image.naturalWidth > 0, display: style.display, height: rect.height, visibility: style.visibility };
        }),
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
    assert.deepEqual(evidence.pictures.filter((poster) => !poster.complete || poster.display === 'none' || poster.visibility === 'hidden' || poster.height <= 0), []);
    assert.deepEqual(evidence.progress.filter((entry) => entry.value !== '1'), [], 'Reduced motion must reveal every motion target');
  });

  await t.test('keyboard order, yellow focus, and native variant submission stay aligned', async () => {
    await session.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
    await setViewport(session, 390, 844);
    const initial = await evaluate(session, `(() => {
      const select = document.querySelector('[data-pimm50-variant-select]');
      const form = select.form;
      const factory = form.querySelector('a[href]');
      const add = form.querySelector('[data-pimm50-add-button]');
      const variants = JSON.parse(document.querySelector('[data-pimm50-variant-data]').textContent);
      const current = variants.find((variant) => String(variant.id) === select.value);
      const next = variants.find((variant) => variant.available && String(variant.id) !== select.value) ?? current;
      select.focus();
      return {
        action: form.action,
        addInsideForm: add.form === form,
        currentAvailable: current.available,
        currentButtonDisabled: add.disabled,
        factoryInsideForm: form.contains(factory),
        focus: document.activeElement === select,
        name: select.name,
        next,
        selectedFormValue: new FormData(form).get('id'),
        selectedValue: select.value,
      };
    })()`);

    assert.equal(initial.name, 'id');
    assert.equal(initial.addInsideForm, true);
    assert.equal(initial.factoryInsideForm, true);
    assert.match(initial.action, /\/cart\/add/);
    assert.equal(initial.selectedFormValue, initial.selectedValue);
    assert.equal(initial.currentButtonDisabled, !initial.currentAvailable);
    assert.equal(initial.focus, true);

    const focusEvidence = [];
    focusEvidence.push(await evaluate(session, `(() => {
      const element = document.activeElement;
      const style = getComputedStyle(element);
      return { color: style.outlineColor, focusVisible: element.matches(':focus-visible'), selector: element.matches('[data-pimm50-variant-select]') ? 'select' : 'other', width: parseFloat(style.outlineWidth) };
    })()`));
    await dispatchTab(session);
    focusEvidence.push(await evaluate(session, `(() => {
      const element = document.activeElement;
      const style = getComputedStyle(element);
      return { color: style.outlineColor, focusVisible: element.matches(':focus-visible'), selector: element.matches('.pimm50-purchase__form a[href]') ? 'factory' : 'other', width: parseFloat(style.outlineWidth) };
    })()`));
    await dispatchTab(session);
    focusEvidence.push(await evaluate(session, `(() => {
      const element = document.activeElement;
      const style = getComputedStyle(element);
      return { color: style.outlineColor, focusVisible: element.matches(':focus-visible'), selector: element.matches('[data-pimm50-add-button]') ? 'add' : 'other', width: parseFloat(style.outlineWidth) };
    })()`));

    assert.deepEqual(focusEvidence.map((entry) => entry.selector), ['select', 'factory', 'add']);
    for (const entry of focusEvidence) {
      assert.equal(entry.focusVisible, true, `${entry.selector} must expose :focus-visible`);
      assert.equal(entry.color, 'rgb(255, 210, 28)', `${entry.selector} must use MALIEV focus yellow`);
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
