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
const viewports = [[1536, 1024], [1280, 800], [1024, 768], [390, 844], [360, 800]];
const desktopMinimum = 990;
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
      if (!message.id) return;
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

async function navigate(session, url) {
  const result = await session.send('Page.navigate', { url });
  if (result.errorText) throw new Error(`Navigation failed for ${url}: ${result.errorText}`);
  await eventually(() => evaluate(session, `document.readyState === 'complete'`), {
    message: 'Collection preview did not finish loading',
  });
  await eventually(() => evaluate(
    session,
    `Boolean(document.querySelector('[data-pimm-collection-comparison][data-contract-valid="true"]'))`,
  ), { message: 'Valid dedicated PIMM collection did not render' });
  await eventually(() => evaluate(
    session,
    `customElements.get('pimm-collection-comparison')
      && document.querySelector('[data-pimm-collection-comparison]')?.activeModel === '30G'`,
  ), { message: 'PIMM collection controller did not initialize' });
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
    imagesReady: machineImages.length === 6
      && machineImages.every((image) => image.complete
        && image.naturalWidth === 1200
        && image.naturalHeight === 1600),
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
      && getComputedStyle(dossier).overflowY === 'auto',
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
    const observedFrames = [];
    const recordFrame = () => {
      const active = card.querySelector('[data-pimm-collection-frame]:not([hidden])');
      if (active) observedFrames.push(active.dataset.pimmCollectionFrame);
    };
    const frameObserver = new MutationObserver(recordFrame);
    frameObserver.observe(card, {
      attributes: true,
      attributeFilter: ['hidden'],
      subtree: true,
    });
    card.querySelector('[data-pimm-collection-select]').click();
    await new Promise((resolveWait) => setTimeout(resolveWait, 1_050));
    observer.disconnect();
    frameObserver.disconnect();
    recordFrame();
    const changesAtFinish = observedFrames.length;
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
      observedFrames,
      changesAtFinish,
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
  assert.equal(committed.dossierLeadTime, committed.expectedLeadTime, `${language} dossier lead time`);
  assert.equal(committed.announcementChanges.length, 1, `${language} announcement count`);
  assert.match(committed.announcement, /50G/, `${language} localized announcement`);
  assert.equal(committed.links.length, 2, `${language} configurator links`);
  assert.ok(committed.links.every(({ variant }) => /^\d+$/.test(variant)), `${language} numeric variants`);
  assert.notEqual(committed.links[0].variant, committed.links[1].variant, `${language} distinct variants`);
  assert.ok(committed.observedFrames.includes('left'), `${language} left playback frame`);
  assert.ok(committed.observedFrames.includes('right'), `${language} right playback frame`);
  assert.equal(committed.finalFrame, 'front', `${language} final playback frame`);
  assert.equal(committed.observedFrames.length, committed.changesAtFinish, `${language} finite playback`);
  assert.equal(committed.transformed, false, `${language} playback image transform`);
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

async function reducedMotionProbe(session) {
  await session.send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-motion', value: 'reduce' }],
  });
  await navigate(session, previewUrl);
  await suppressCookieConsent(session);
  const reduced = await evaluate(session, `(async () => {
    const root = document.querySelector('[data-pimm-collection-comparison]');
    const card = root.querySelector('[data-pimm-collection-card][data-model="50G"]');
    const observed = [];
    const observer = new MutationObserver(() => {
      observed.push(card.querySelector('[data-pimm-collection-frame]:not([hidden])')
        ?.dataset.pimmCollectionFrame);
    });
    observer.observe(card, { attributes: true, attributeFilter: ['hidden'], subtree: true });
    card.dispatchEvent(new PointerEvent('pointerenter', { pointerType: 'mouse' }));
    await new Promise((resolveWait) => setTimeout(resolveWait, 900));
    observer.disconnect();
    return {
      active: root.activeModel,
      frame: card.querySelector('[data-pimm-collection-frame]:not([hidden])')
        ?.dataset.pimmCollectionFrame,
      observed,
      cardTransition: getComputedStyle(card).transitionDuration,
    };
  })()`);
  assert.equal(reduced.active, '50G');
  assert.equal(reduced.frame, 'front');
  assert.ok(reduced.observed.every((frame) => frame === 'front'));
  assert.equal(new Set(reduced.observed).size <= 1, true);
  assert.match(reduced.cardTransition, /(?:^|, )0s(?:,|$)/);
  await session.send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }],
  });
}

async function lifecycleProbe(session) {
  await navigate(session, previewUrl);
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
}

test('missing preview URL is an intentional PIMM collection browser-matrix skip', {
  skip: Boolean(previewUrl),
}, () => {
  assert.equal(previewUrl, undefined);
});

test('dedicated PIMM collection passes responsive, interaction, and localization acceptance', {
  skip: previewUrl ? false : 'PIMM_COLLECTION_PREVIEW_URL is not set',
  timeout: 240_000,
}, async () => {
  await mkdir(evidenceDir, { recursive: true });
  const browser = await launchBrowser();
  const { session } = browser;
  try {
    await session.send('Page.enable');
    await session.send('Runtime.enable');
    await session.send('Page.bringToFront');
    for (const [language, url] of [['en', previewUrl], ['th', thaiUrlFrom(previewUrl)]]) {
      for (const [width, height] of viewports) {
        await session.send('Emulation.setEmulatedMedia', {
          features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }],
        });
        await setViewport(session, width, height);
        await navigate(session, url);
        await suppressCookieConsent(session);
        await decodeCollectionImages(session);
        await assertGeometry(session, language, width, height);
        await captureFullPageScreenshot(
          session,
          join(evidenceDir, `${language}-${width}x${height}.png`),
        );
      }
    }

    await setViewport(session, 1280, 800);
    await navigate(session, previewUrl);
    await suppressCookieConsent(session);
    await interactionProbe(session, 'en');
    await headerProbe(session, 'en');

    await navigate(session, thaiUrlFrom(previewUrl));
    await suppressCookieConsent(session);
    const thaiLabels = await evaluate(session, `(() => ({
      lang: document.documentElement.lang,
      dossierLabels: [...document.querySelectorAll(
        '.pimm-collection__dossier--desktop dt',
      )].map((node) => node.textContent.trim()),
    }))()`);
    assert.match(thaiLabels.lang, /^th(?:-|$)/i);
    assert.ok(thaiLabels.dossierLabels.length >= 7);
    assert.ok(thaiLabels.dossierLabels.every((label) => /[\u0E00-\u0E7F]/.test(label)));
    await interactionProbe(session, 'th');
    await headerProbe(session, 'th');

    await reducedMotionProbe(session);
    await lifecycleProbe(session);
  } finally {
    await browser.close();
  }
});
