import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import test from 'node:test';

const previewUrl = process.env.PIMM_UNIFIED_PREVIEW_URL?.trim();
const evidenceDir = resolve(process.env.PIMM_UNIFIED_EVIDENCE_DIR?.trim() || '.codex-tmp/pimm-unified-product/browser-evidence');
const viewports = [[1440, 900], [1280, 800], [1024, 768], [390, 844], [360, 800]];
const models = ['30G', '50G'];
const chromeCandidates = [
  process.env.PIMM_UNIFIED_CHROME_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
].filter(Boolean);

const delay = (milliseconds) => new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));

async function eventually(action, { timeout = 30_000, interval = 100, message = 'Condition was not met' } = {}) {
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
  throw lastError ?? new Error(`${message} within ${timeout}ms (last value: ${JSON.stringify(lastValue)})`);
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
      for (const pending of this.#pending.values()) pending.reject(new Error('Chrome DevTools connection closed'));
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
    await Promise.race([new Promise((resolveClose) => this.socket.addEventListener('close', resolveClose, { once: true })), delay(1_000)]);
  }
}

async function stopBrowser(browser) {
  if (browser.exitCode !== null || browser.signalCode !== null) return;
  browser.kill();
  const exited = await Promise.race([new Promise((resolveExit) => browser.once('exit', () => resolveExit(true))), delay(5_000).then(() => false)]);
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
    '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${userDataDir}`,
    '--disable-background-networking', '--disable-component-update', '--disable-default-apps',
    '--disable-extensions', '--disable-features=Translate,MediaRouter', '--disable-sync',
    '--hide-scrollbars', '--mute-audio', '--no-default-browser-check', '--no-first-run', 'about:blank',
  ], { stdio: 'ignore', windowsHide: true });

  try {
    const port = await eventually(async () => {
      const [value] = (await readFile(join(userDataDir, 'DevToolsActivePort'), 'utf8')).trim().split(/\r?\n/);
      return Number(value) || undefined;
    });
    const target = await eventually(async () => {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`);
      return (await response.json()).find((candidate) => candidate.type === 'page' && candidate.webSocketDebuggerUrl);
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
  const response = await session.send('Runtime.evaluate', { awaitPromise: true, expression, returnByValue: true, userGesture: true });
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.exception?.description ?? response.exceptionDetails.text);
  return response.result.value;
}

async function setViewport(session, width, height) {
  await session.send('Emulation.setDeviceMetricsOverride', { deviceScaleFactor: 1, height, mobile: false, screenHeight: height, screenWidth: width, width });
  await delay(100);
}

async function navigate(session, url) {
  const result = await session.send('Page.navigate', { url });
  if (result.errorText) throw new Error(`Navigation failed for ${url}: ${result.errorText}`);
  await eventually(() => evaluate(session, `document.readyState !== 'loading'`), { message: 'Preview document did not become DOM-ready' });
  await eventually(() => evaluate(session, `Boolean(document.querySelector('[data-pimm-machine-product]'))`), { message: 'PIMM product root did not render' });
  await eventually(() => evaluate(session, `(() => { const image = document.querySelector('[data-pimm-media-model]:not([hidden]) img'); return image?.complete && image.naturalWidth > 0; })()`), { message: 'Selected PIMM hero image did not load' });
}

function thaiUrlFrom(value) {
  const url = new URL(value);
  if (!url.pathname.startsWith('/th/')) url.pathname = `/th${url.pathname.startsWith('/') ? '' : '/'}${url.pathname}`;
  return url.href;
}

async function captureScreenshot(session, path) {
  const capture = await session.send('Page.captureScreenshot', { captureBeyondViewport: false, format: 'png', fromSurface: true });
  await writeFile(path, Buffer.from(capture.data, 'base64'));
}

async function suppressCookieConsent(session) {
  await evaluate(session, `(() => {
    for (const selector of ['#shopify-pc__banner', '#shopify-privacy-banner', '[data-shopify-privacy-banner]']) {
      document.querySelectorAll(selector).forEach((node) => { node.style.display = 'none'; node.setAttribute('aria-hidden', 'true'); });
    }
    return true;
  })()`);
}

const geometryProbe = (model) => `(() => {
  const root = document.querySelector('[data-pimm-machine-product]');
  const visibleStory = document.querySelector('[data-pimm-story-model="${model}"]:not([hidden])');
  const hero = document.querySelector('[data-pimm-media-model="${model}"]:not([hidden])');
  const selected = document.querySelector('[data-pimm-selected-model]')?.textContent.trim();
  const otherStories = [...document.querySelectorAll('[data-pimm-story-model]')].filter((node) => node.dataset.pimmStoryModel !== '${model}');
  const otherHeroes = [...document.querySelectorAll('[data-pimm-media-model]')].filter((node) => node.dataset.pimmMediaModel !== '${model}');
  const images = [...hero.querySelectorAll('img'), ...visibleStory.querySelectorAll('img')];
  const title = root.querySelector('h1');
  const titleRange = document.createRange();
  titleRange.selectNodeContents(title);
  const titleRect = titleRange.getBoundingClientRect();
  const heroStageRect = hero.getBoundingClientRect();
  const overlaps = [...visibleStory.querySelectorAll('.pimm-story__chapter')].map((chapter) => {
    const media = chapter.querySelector('.pimm-story__media')?.getBoundingClientRect();
    const copy = chapter.querySelector('.pimm-story__copy')?.getBoundingClientRect();
    if (!media || !copy) return false;
    return media.left < copy.right && media.right > copy.left && media.top < copy.bottom && media.bottom > copy.top;
  });
  const fullMachines = [hero, ...visibleStory.querySelectorAll('[data-pimm-full-machine]')].map((owner) => {
    const image = owner.querySelector('img');
    const ownerRect = owner.getBoundingClientRect();
    const imageRect = image.getBoundingClientRect();
    return {
      physicalGroundContact: owner.hasAttribute('data-pimm-physical-ground-contact'),
      ownerTop: ownerRect.top,
      ownerBottom: ownerRect.bottom,
      imageTop: imageRect.top,
      imageBottom: imageRect.bottom,
      stageHeight: ownerRect.height,
      imageHeight: imageRect.height,
      source: image.currentSrc.split('/').pop()?.split('?')[0],
      transform: getComputedStyle(image).transform,
      objectFit: getComputedStyle(image).objectFit,
    };
  });
  return {
    fullMachines,
    h1Count: root.querySelectorAll('h1').length,
    imagesReady: images.every((image) => image.complete && image.naturalWidth > 0 && image.naturalHeight > 0),
    oldAssetPresent: /(?:(?:pimm30-|pimm50-|pimm-(?:machine|editorial)-|maliev-pimm-)[^'"\\s)]+\\.(?:png|webp|webm|mp4))/.test(document.documentElement.innerHTML),
    otherHeroesHidden: otherHeroes.every((node) => node.hidden && node.inert && node.getAttribute('aria-hidden') === 'true'),
    otherStoriesHidden: otherStories.every((node) => node.hidden && node.inert && node.getAttribute('aria-hidden') === 'true'),
    overflowX: document.documentElement.scrollWidth - innerWidth,
    titleRight: titleRect.right,
    titleFontSize: getComputedStyle(title).fontSize,
    heroStageLeft: heroStageRect.left,
    titleOverlapsStage: innerWidth > 749 && titleRect.right > heroStageRect.left + 1,
    overlaps,
    selected,
    storyModel: visibleStory?.dataset.pimmStoryModel,
    status: root.querySelector('[data-pimm-variant-status]')?.textContent.trim(),
    url: location.href,
  };
})()`;

test('missing preview URL is an intentional browser-matrix skip', { skip: Boolean(previewUrl) }, () => {
  assert.equal(previewUrl, undefined);
});

test('unified PIMM preview passes selected-story responsive and grounding acceptance', {
  skip: previewUrl ? false : 'PIMM_UNIFIED_PREVIEW_URL is not set',
  timeout: 180_000,
}, async () => {
  await mkdir(evidenceDir, { recursive: true });
  const browser = await launchBrowser();
  const { session } = browser;
  try {
    await session.send('Page.enable');
    await session.send('Runtime.enable');
    for (const [language, url] of [['en', previewUrl], ['th', thaiUrlFrom(previewUrl)]]) {
      for (const [width, height] of viewports) {
        await setViewport(session, width, height);
        await navigate(session, url);
        await suppressCookieConsent(session);
        for (const model of models) {
          await evaluate(session, `(() => {
            const radio = [...document.querySelectorAll('[data-pimm-model-radio]')].find((node) => node.dataset.model === '${model}');
            if (!radio) return false;
            radio.click();
            return true;
          })()`);
          await eventually(() => evaluate(session, `document.querySelector('[data-pimm-selected-model]')?.textContent.trim() === '${model}'`));
          await eventually(() => evaluate(session, `(() => { const image = document.querySelector('[data-pimm-media-model="${model}"]:not([hidden]) img'); return image?.complete && image.naturalWidth > 0; })()`));
          await evaluate(session, `(async () => {
            const story = document.querySelector('[data-pimm-story-model="${model}"]:not([hidden])');
            for (const image of story.querySelectorAll('img')) {
              image.scrollIntoView({ block: 'center' });
              if (!image.complete || image.naturalWidth === 0) {
                await new Promise((resolve) => {
                  image.addEventListener('load', resolve, { once: true });
                  image.addEventListener('error', resolve, { once: true });
                });
              }
              if (typeof image.decode === 'function') await image.decode().catch(() => {});
            }
            scrollTo(0, 0);
            return true;
          })()`);
          await delay(220);
          const probe = await evaluate(session, geometryProbe(model));
          assert.equal(probe.h1Count, 1, `${language} ${width}x${height} ${model} H1 count`);
          assert.equal(probe.selected, model);
          assert.equal(probe.storyModel, model);
          assert.equal(probe.imagesReady, true, `${language} ${width}x${height} ${model} images`);
          assert.equal(probe.otherHeroesHidden, true, `${language} ${width}x${height} ${model} inactive hero`);
          assert.equal(probe.otherStoriesHidden, true, `${language} ${width}x${height} ${model} inactive story`);
          assert.equal(probe.oldAssetPresent, false);
          assert.ok(probe.overflowX <= 1, `${language} ${width}x${height} ${model} overflow ${probe.overflowX}px`);
          assert.equal(probe.titleOverlapsStage, false, `${language} ${width}x${height} ${model} title ${probe.titleRight}px at ${probe.titleFontSize} overlaps hero at ${probe.heroStageLeft}px`);
          assert.ok(probe.overlaps.every((value) => value === false), `${language} ${width}x${height} ${model} chapter overlap`);
          assert.ok(probe.status.length > 0, `${language} ${width}x${height} ${model} status`);
          for (const machine of probe.fullMachines) {
            assert.equal(machine.physicalGroundContact, true, `${language} ${width}x${height} ${model} ${machine.source} physical contact marker`);
            assert.match(machine.source, /^pimm-master-20260901-r05-(?:30g|50g)-(?:hero|configuration)\.webp$/, `${language} ${width}x${height} ${model} source`);
            assert.equal(machine.transform, 'none', `${language} ${width}x${height} ${model} ${machine.source} transform`);
            assert.equal(machine.objectFit, 'cover', `${language} ${width}x${height} ${model} ${machine.source} object fit`);
            assert.ok(machine.imageHeight >= machine.stageHeight * .5, `${language} ${width}x${height} ${model} ${machine.source} is undersized`);
          }
          await captureScreenshot(session, join(evidenceDir, `${language}-${width}x${height}-${model.toLowerCase()}.png`));
          await evaluate(session, `(() => {
            document.querySelector('[data-pimm-story-model="${model}"]:not([hidden]) [data-pimm-full-machine]')?.scrollIntoView({ block: 'center' });
            return true;
          })()`);
          await delay(120);
          await captureScreenshot(session, join(evidenceDir, `${language}-${width}x${height}-${model.toLowerCase()}-ground.png`));
          await evaluate(session, `scrollTo(0, 0)`);
        }
      }
    }

    await setViewport(session, 720, 800);
    await session.send('Emulation.setPageScaleFactor', { pageScaleFactor: 2 });
    const zoomOverflow = await evaluate(session, `document.documentElement.scrollWidth - innerWidth`);
    assert.ok(zoomOverflow <= 1, `200% zoom overflow ${zoomOverflow}px`);
    await session.send('Emulation.setPageScaleFactor', { pageScaleFactor: 1 });

    await session.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    const reduced = await evaluate(session, `getComputedStyle(document.querySelector('[data-pimm-media-model]:not([hidden])')).transitionDuration`);
    assert.equal(reduced, '0s');
  } finally {
    await browser.close();
  }
});
