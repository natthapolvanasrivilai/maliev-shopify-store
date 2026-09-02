import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const controllerUrl = new URL('../../assets/maliev-pimm-collection.js', import.meta.url);

const records = [
  {
    id: 30,
    model: '30G',
    url: '/products/pimm?variant=30',
    fullPrice: '฿120,000.00 THB',
    available: true,
    leadTime: '30 days',
    specifications: {
      shotCapacityG: 30,
      maxMeltTemperatureC: 300,
      moldEnvelopeMm: { width: 240, height: 240, depth: 150 },
      maxAirPressureMpa: 0.7,
    },
  },
  {
    id: 50,
    model: '50G',
    url: '/products/pimm?variant=50',
    fullPrice: '฿170,000.00 THB',
    available: false,
    leadTime: '45 days',
    specifications: {
      shotCapacityG: 50,
      maxMeltTemperatureC: 300,
      moldEnvelopeMm: { width: 300, height: 300, depth: 200 },
      maxAirPressureMpa: 0.7,
    },
  },
];

class FakeClassList {
  constructor(names = []) {
    this.values = new Set(names);
  }

  add(...names) {
    names.forEach((name) => this.values.add(name));
  }

  remove(...names) {
    names.forEach((name) => this.values.delete(name));
  }

  toggle(name, force) {
    const shouldAdd = force ?? !this.values.has(name);
    if (shouldAdd) this.values.add(name);
    else this.values.delete(name);
    return shouldAdd;
  }

  contains(name) {
    return this.values.has(name);
  }
}

class FakeNode {
  constructor({ dataset = {}, textContent = '', classes = [] } = {}) {
    this.dataset = { ...dataset };
    this.classList = new FakeClassList(classes);
    this.attributes = new Map();
    this.listeners = new Map();
    this.nodes = new Map();
    this.hidden = false;
    this.href = '';
    this._textContent = textContent;
    this.textWrites = 0;
  }

  get textContent() {
    return this._textContent;
  }

  set textContent(value) {
    this._textContent = String(value);
    this.textWrites += 1;
  }

  addEventListener(type, listener, options = {}) {
    const entries = this.listeners.get(type) ?? [];
    const entry = { listener, active: true };
    entries.push(entry);
    this.listeners.set(type, entries);
    options.signal?.addEventListener('abort', () => { entry.active = false; }, { once: true });
  }

  dispatch(type, event = {}) {
    for (const entry of this.listeners.get(type) ?? []) {
      if (entry.active) entry.listener({ currentTarget: this, target: this, ...event });
    }
  }

  activeListenerCount() {
    return [...this.listeners.values()].flat().filter(({ active }) => active).length;
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  querySelector(selector) {
    return this.nodes.get(selector) ?? null;
  }

  querySelectorAll(selector) {
    return this.nodes.get(selector) ?? [];
  }

  contains(candidate) {
    return candidate === this || candidate?.ownerCard === this;
  }
}

const dossierValues = {
  '30G': {
    recommendation: 'Compact workshop work',
    compare: 'Compared with 50G',
    availability: 'Made to order',
    shotCapacity: '30 g',
    moldEnvelope: '240 × 240 × 150 mm',
    meltTemperature: '300 °C',
    airPressure: '0.7 MPa',
    configure: 'View 30G machine',
  },
  '50G': {
    recommendation: 'Extended-capacity work',
    compare: 'Compared with 30G',
    availability: 'Out of stock',
    shotCapacity: '50 g',
    moldEnvelope: '300 × 300 × 200 mm',
    meltTemperature: '300 °C',
    airPressure: '0.7 MPa',
    configure: 'View 50G machine',
  },
};

function createDossier(model, { inline = false, productPath = '/products/pimm' } = {}) {
  const values = dossierValues[model];
  const dossier = new FakeNode({
    dataset: { model, ...(inline ? { pimmCollectionInlineDossier: '' } : {}) },
    classes: inline && model === '30G' ? ['is-active'] : [],
  });
  const configure = new FakeNode({ textContent: values.configure });
  configure.href = `${productPath}?variant=${model === '30G' ? 30 : 50}`;
  configure.setAttribute('href', configure.href);
  dossier.nodes = new Map([
    ['[data-pimm-dossier-model]', new FakeNode({ textContent: model })],
    ['[data-pimm-dossier-recommendation]', new FakeNode({ textContent: values.recommendation })],
    ['[data-pimm-dossier-compare]', new FakeNode({ textContent: values.compare })],
    ['[data-pimm-dossier-price]', new FakeNode({ textContent: records.find((record) => record.model === model).fullPrice })],
    ['[data-pimm-dossier-availability]', new FakeNode({ textContent: values.availability })],
    ['[data-pimm-dossier-lead-time]', new FakeNode({ textContent: records.find((record) => record.model === model).leadTime })],
    ['[data-pimm-dossier-shot-capacity]', new FakeNode({ textContent: values.shotCapacity })],
    ['[data-pimm-dossier-mold-envelope]', new FakeNode({ textContent: values.moldEnvelope })],
    ['[data-pimm-dossier-melt-temperature]', new FakeNode({ textContent: values.meltTemperature })],
    ['[data-pimm-dossier-air-pressure]', new FakeNode({ textContent: values.airPressure })],
    ['[data-pimm-dossier-configure]', configure],
  ]);
  return dossier;
}

function createCard(model) {
  const card = new FakeNode({
    dataset: { model },
    classes: model === '30G' ? ['is-active'] : [],
  });
  card.setAttribute('aria-current', model === '30G' ? 'true' : 'false');
  const configure = new FakeNode({ textContent: `View ${model} machine` });
  configure.href = `/products/pimm?variant=${model === '30G' ? 30 : 50}`;
  configure.setAttribute('href', configure.href);
  const select = new FakeNode({ textContent: `Compare ${model}` });
  select.hidden = true;
  select.disabled = true;
  const frames = ['front', 'left', 'right'].map((angle) => {
    const frame = new FakeNode({
      dataset: { pimmCollectionFrame: angle },
      classes: angle === 'front' ? ['is-active'] : [],
    });
    frame.hidden = angle !== 'front';
    frame.setAttribute('aria-hidden', angle === 'front' ? 'false' : 'true');
    return frame;
  });
  card.nodes.set('[data-pimm-collection-frame]', frames);
  card.nodes.set('img[loading="lazy"]', []);
  card.nodes.set('[data-pimm-collection-select]', select);
  card.nodes.set('.pimm-collection__card-actions a', configure);
  const video = new FakeNode();
  video.currentTime = 0;
  video.paused = true;
  video.play = () => { video.paused = false; return Promise.resolve(); };
  video.pause = () => { video.paused = true; };
  card.nodes.set('[data-pimm-collection-video]', video);
  return card;
}

async function loadController({
  reducedMotion = false,
  pageUrl = 'https://shop.maliev.com/collections/pimm',
} = {}) {
  const source = await readFile(controllerUrl, 'utf8');
  let Controller;
  let nextTimerId = 1;
  const timers = [];
  const window = {
    location: new URL(pageUrl),
    matchMedia: () => ({ matches: reducedMotion }),
    setTimeout(callback, delay) {
      const timer = { id: nextTimerId++, callback, delay, active: true };
      timers.push(timer);
      return timer.id;
    },
    clearTimeout(id) {
      const timer = timers.find((candidate) => candidate.id === id);
      if (timer) timer.active = false;
    },
  };

  vm.runInNewContext(source, {
    AbortController,
    HTMLElement: class {},
    URL,
    customElements: {
      get: () => undefined,
      define: (_name, constructor) => { Controller = constructor; },
    },
    window,
  });

  return {
    Controller,
    timers,
    runDelay(delay) {
      const timer = timers.find((candidate) => candidate.active && candidate.delay === delay);
      assert.ok(timer, `expected active timer at ${delay}ms`);
      timer.active = false;
      timer.callback();
    },
    activeTimerCount: () => timers.filter(({ active }) => active).length,
  };
}

function createComparison(Controller, {
  payload = JSON.stringify(records),
  productPath = '/products/pimm',
} = {}) {
  const comparison = new Controller();
  comparison.dataset = {
    availableLabel: 'Made to order',
    unavailableLabel: 'Out of stock',
  };
  const cards = [createCard('30G'), createCard('50G')];
  const inlineDossiers = [
    createDossier('30G', { inline: true, productPath }),
    createDossier('50G', { inline: true, productPath }),
  ];
  const desktopDossier = createDossier('30G', { productPath });
  const dossiers = [...inlineDossiers, desktopDossier];
  const announcement = new FakeNode({ dataset: { announcementTemplate: 'Now comparing __MODEL__' } });
  const payloadNode = new FakeNode({ textContent: payload });

  comparison.querySelector = (selector) => ({
    '[data-pimm-collection-models]': payloadNode,
    '[data-pimm-collection-announcement]': announcement,
  })[selector] ?? null;
  comparison.querySelectorAll = (selector) => ({
    '[data-pimm-collection-card]': cards,
    '[data-pimm-collection-dossier]': dossiers,
    '[data-pimm-collection-inline-dossier]': inlineDossiers,
  })[selector] ?? [];

  return { comparison, cards, inlineDossiers, desktopDossier, announcement, payloadNode };
}

const visibleFrame = (card) => card.querySelectorAll('[data-pimm-collection-frame]')
  .find((frame) => !frame.hidden)?.dataset.pimmCollectionFrame;

test('30G is committed initially and a preview does not overwrite the committed model', async () => {
  const { Controller } = await loadController();
  const { comparison } = createComparison(Controller);

  comparison.connectedCallback();
  assert.equal(comparison.committedModel, '30G');
  comparison.previewModel('50G');
  assert.equal(comparison.activeModel, '50G');
  assert.equal(comparison.committedModel, '30G');
  comparison.restoreCommittedModel();
  assert.equal(comparison.activeModel, '30G');
});

test('valid enhancement alone makes cards and compare controls interactive', async () => {
  const { Controller } = await loadController();
  const { comparison, cards } = createComparison(Controller);

  comparison.connectedCallback();

  for (const card of cards) {
    const select = card.querySelector('[data-pimm-collection-select]');
    assert.equal(card.getAttribute('tabindex'), '0');
    assert.equal(select.hidden, false);
    assert.equal(select.disabled, false);
  }
});

test('committing 50G updates aria state, both dossier instances, and one announcement', async () => {
  const { Controller } = await loadController();
  const { comparison, cards, inlineDossiers, desktopDossier, announcement } = createComparison(Controller);
  inlineDossiers[1].querySelector('[data-pimm-dossier-availability]').textContent = 'Made to order';
  comparison.connectedCallback();
  announcement.textWrites = 0;

  comparison.commitModel('50G');

  assert.equal(comparison.committedModel, '50G');
  assert.equal(cards[1].getAttribute('aria-current'), 'true');
  assert.equal(cards[1].classList.contains('is-active'), true);
  assert.equal(cards[0].getAttribute('aria-current'), 'false');
  assert.equal(inlineDossiers[0].hidden, true);
  assert.equal(inlineDossiers[1].hidden, false);
  assert.equal(desktopDossier.querySelector('[data-pimm-dossier-model]').textContent, '50G');
  assert.equal(desktopDossier.querySelector('[data-pimm-dossier-price]').textContent, '฿170,000.00 THB');
  assert.equal(desktopDossier.querySelector('[data-pimm-dossier-availability]').textContent, 'Out of stock');
  assert.equal(desktopDossier.querySelector('[data-pimm-dossier-configure]').href, '/products/pimm?variant=50');
  assert.equal(announcement.textContent, 'Now comparing 50G');
  assert.equal(announcement.textWrites, 1);
});

test('pointer preview restores the committed model while click commits and plays one sequence', async () => {
  const { Controller, activeTimerCount } = await loadController();
  const { comparison, cards } = createComparison(Controller);
  comparison.connectedCallback();

  cards[1].dispatch('pointerenter', { pointerType: 'mouse' });
  assert.equal(comparison.activeModel, '50G');
  assert.equal(comparison.committedModel, '30G');
  cards[1].dispatch('pointerleave', { pointerType: 'mouse' });
  assert.equal(comparison.activeModel, '30G');

  cards[1].dispatch('click');
  assert.equal(comparison.committedModel, '50G');
  assert.equal(activeTimerCount(), 0);
  assert.equal(cards[1].querySelector('[data-pimm-collection-video]').paused, false);
});

test('native video playback starts at front, resets on exit, and never schedules still swaps', async () => {
  const { Controller, activeTimerCount } = await loadController();
  const { comparison, cards } = createComparison(Controller);
  comparison.connectedCallback();

  comparison.playSequence(cards[0]);
  const video = cards[0].querySelector('[data-pimm-collection-video]');
  assert.equal(video.paused, false);
  video.currentTime = 1.5;
  comparison.playSequence(cards[0]);
  assert.equal(video.currentTime, 0);
  comparison.stopSequence(cards[0]);
  assert.equal(video.paused, true);
  assert.equal(video.currentTime, 0);
  assert.equal(visibleFrame(cards[0]), 'front');
  assert.equal(activeTimerCount(), 0);
});

test('reduced motion never schedules angle playback', async () => {
  const { Controller, timers } = await loadController({ reducedMotion: true });
  const { comparison, cards } = createComparison(Controller);
  comparison.connectedCallback();

  comparison.playSequence(cards[0]);

  assert.equal(timers.length, 0);
  assert.equal(cards[0].querySelector('[data-pimm-collection-video]').paused, true);
  assert.equal(visibleFrame(cards[0]), 'front');
});

test('ended and failed video restore the poster, rejected playback is handled', async () => {
  const { Controller } = await loadController();
  const { comparison, cards } = createComparison(Controller);
  comparison.connectedCallback();
  const video = cards[0].querySelector('[data-pimm-collection-video]');
  comparison.playSequence(cards[0]);
  await Promise.resolve();
  assert.equal(video.classList.contains('is-playing'), true);
  video.dispatch('ended');
  assert.equal(video.classList.contains('is-playing'), false);
  assert.equal(video.paused, true);
  comparison.playSequence(cards[0]);
  video.dispatch('error');
  await Promise.resolve();
  assert.equal(video.classList.contains('is-playing'), false);
  video.play = () => Promise.reject(new Error('blocked'));
  comparison.playSequence(cards[0]);
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(video.classList.contains('is-playing'), false);
});

test('invalid records preserve the server fallback and attach no playback listeners', async () => {
  const { Controller } = await loadController();
  const { comparison, cards } = createComparison(Controller, { payload: '{invalid' });

  comparison.connectedCallback();

  assert.equal(cards[0].classList.contains('is-active'), true);
  assert.equal(cards[0].getAttribute('aria-current'), 'true');
  assert.equal(cards.reduce((count, card) => count + card.activeListenerCount(), 0), 0);
  assert.equal(comparison.committedModel, undefined);
  for (const card of cards) {
    const configure = card.querySelector('.pimm-collection__card-actions a');
    const select = card.querySelector('[data-pimm-collection-select]');
    assert.equal(card.getAttribute('tabindex'), null);
    assert.equal(select.hidden, true);
    assert.equal(select.disabled, true);
    assert.equal(configure.getAttribute('href'), `/products/pimm?variant=${card.dataset.model === '30G' ? 30 : 50}`);
  }
});

test('strict record validation rejects incomplete, duplicate, and unbound model records', async (context) => {
  const malformedPayloads = [
    ['missing model record', records.slice(0, 1)],
    ['duplicate model identity', [records[0], { ...records[1], model: '30G' }]],
    ['missing governed specifications', [{ ...records[0], specifications: null }, records[1]]],
    ['variant URL does not match the record id', [{ ...records[0], url: '/products/pimm?variant=999' }, records[1]]],
    ['nonpositive governed specification', [
      {
        ...records[0],
        specifications: { ...records[0].specifications, shotCapacityG: 0 },
      },
      records[1],
    ]],
  ];

  for (const [name, payload] of malformedPayloads) {
    await context.test(name, async () => {
      const { Controller } = await loadController();
      const { comparison, cards } = createComparison(Controller, { payload: JSON.stringify(payload) });

      comparison.connectedCallback();

      assert.equal(comparison.committedModel, undefined);
      assert.equal(cards[0].getAttribute('aria-current'), 'true');
      assert.equal(cards.reduce((count, card) => count + card.activeListenerCount(), 0), 0);
    });
  }
});

test('routing validation rejects untrusted origins schemes and paths without binding listeners', async (context) => {
  const unsafeCases = [
    {
      name: 'cross-origin https URL',
      payload: [{ ...records[0], url: 'https://example.com/products/pimm?variant=30' }, records[1]],
    },
    {
      name: 'non-product collection path',
      payload: [{ ...records[0], url: '/collections/pimm?variant=30' }, records[1]],
    },
    {
      name: 'javascript scheme',
      payload: [{ ...records[0], url: 'javascript:alert(1)?variant=30' }, records[1]],
    },
    {
      name: 'localized path does not match the canonical server path',
      pageUrl: 'https://shop.maliev.com/th/collections/pimm',
      productPath: '/th/products/pimm',
      payload: records,
    },
  ];

  for (const {
    name,
    payload,
    pageUrl = 'https://shop.maliev.com/collections/pimm',
    productPath = '/products/pimm',
  } of unsafeCases) {
    await context.test(name, async () => {
      const { Controller } = await loadController({ pageUrl });
      const { comparison, cards } = createComparison(Controller, {
        payload: JSON.stringify(payload),
        productPath,
      });

      comparison.connectedCallback();

      assert.equal(comparison.committedModel, undefined);
      assert.equal(cards[0].getAttribute('aria-current'), 'true');
      assert.equal(cards.reduce((count, card) => count + card.activeListenerCount(), 0), 0);
    });
  }
});

test('localized same-origin product URLs bind but dossier routing keeps the trusted server href', async () => {
  const pageUrl = 'https://shop.maliev.com/th/collections/pimm';
  const productPath = '/th/products/pimm';
  const localizedRecords = records.map((record) => ({
    ...record,
    url: `https://shop.maliev.com${productPath}?variant=${record.id}`,
  }));
  const { Controller } = await loadController({ pageUrl });
  const { comparison, cards, desktopDossier } = createComparison(Controller, {
    payload: JSON.stringify(localizedRecords),
    productPath,
  });

  comparison.connectedCallback();
  comparison.commitModel('50G');

  assert.equal(comparison.committedModel, '50G');
  assert.ok(cards.every((card) => card.activeListenerCount() > 0));
  assert.equal(
    desktopDossier.querySelector('[data-pimm-dossier-configure]').href,
    '/th/products/pimm?variant=50',
  );
});

test('disconnect clears timers and aborts all listeners', async () => {
  const { Controller, activeTimerCount } = await loadController();
  const { comparison, cards } = createComparison(Controller);
  comparison.connectedCallback();
  const controller = comparison.controller;
  comparison.playSequence(cards[0]);

  comparison.disconnectedCallback();

  assert.equal(activeTimerCount(), 0);
  assert.equal(controller.signal.aborted, true);
  assert.equal(cards.reduce((count, card) => count + card.activeListenerCount(), 0), 0);
  assert.equal(visibleFrame(cards[0]), 'front');
  for (const card of cards) {
    const select = card.querySelector('[data-pimm-collection-select]');
    assert.equal(card.getAttribute('tabindex'), null);
    assert.equal(select.hidden, true);
    assert.equal(select.disabled, true);
  }
});

test('preview navigation retains its key and locale for both cards and all dossiers across reconnects', async () => {
  const key = '0123456789abcdef0123456789abcdef';
  for (const prefix of ['', '/th']) {
    const { Controller } = await loadController({
      pageUrl: `https://shop.maliev.com${prefix}/products_preview?preview_key=${key}&view=pimm-collection-preview&variant=30&cb=ignored#details`,
    });
    const { comparison, cards, inlineDossiers, desktopDossier } = createComparison(Controller);
    comparison.dataset.previewNavigation = 'true';
    for (let connection = 0; connection < 2; connection += 1) {
      comparison.connectedCallback();
      assert.equal(comparison.committedModel, '30G');
      for (const [index, model] of ['30G', '50G'].entries()) {
        const expected = `${prefix}/products_preview?preview_key=${key}&view=pimm-configurator&variant=${index === 0 ? 30 : 50}`;
        assert.equal(cards[index].querySelector('.pimm-collection__card-actions a').href, expected);
        assert.equal(inlineDossiers[index].querySelector('[data-pimm-dossier-configure]').href, expected);
        comparison.commitModel(model);
        assert.equal(desktopDossier.querySelector('[data-pimm-dossier-configure]').href, expected);
      }
      comparison.disconnectedCallback();
      assert.equal(inlineDossiers[0].querySelector('[data-pimm-dossier-configure]').href, '/products/pimm?variant=30');
    }
  }
});

test('preview keys never leak into public, foreign, malformed or untrusted navigation', async () => {
  const key = '0123456789abcdef0123456789abcdef';
  for (const [path, enabled] of [
    [`/collections/pimm?preview_key=${key}&view=pimm-collection-preview`, true],
    [`/products_preview?preview_key=${key}&view=pimm-collection-preview`, false],
    ['/products_preview?view=pimm-collection-preview', true],
    [`/products_preview?preview_key=${key}&preview_key=other&view=pimm-collection-preview`, true],
    ['/products_preview?preview_key=bad&view=pimm-collection-preview', true],
    [`/products_preview?preview_key=${key}&view=pimm-configurator`, true],
    [`/products_preview?preview_key=${key}&view=pimm-collection-preview&view=other`, true],
    [`/other/products_preview?preview_key=${key}&view=pimm-collection-preview`, true],
  ]) {
    const { Controller } = await loadController({ pageUrl: `https://shop.maliev.com${path}` });
    const { comparison, cards, desktopDossier } = createComparison(Controller);
    comparison.dataset.previewNavigation = String(enabled);
    comparison.connectedCallback();
    comparison.commitModel('50G');
    assert.equal(cards[0].querySelector('.pimm-collection__card-actions a').href, '/products/pimm?variant=30');
    assert.equal(desktopDossier.querySelector('[data-pimm-dossier-configure]').href, '/products/pimm?variant=50');
  }
  const { Controller } = await loadController({ pageUrl: `https://shop.maliev.com/products_preview?preview_key=${key}&view=pimm-collection-preview` });
  const { comparison, cards } = createComparison(Controller, {
    payload: JSON.stringify([{ ...records[0], url: 'https://evil.example/products/pimm?variant=30' }, records[1]]),
  });
  comparison.dataset.previewNavigation = 'true';
  comparison.connectedCallback();
  assert.equal(comparison.committedModel, undefined);
  assert.equal(cards[0].querySelector('.pimm-collection__card-actions a').href, '/products/pimm?variant=30');
});

test('configurator view is the only optional trusted product query and must match the server route', async () => {
  const { Controller } = await loadController();
  for (const view of ['pimm-configurator', 'other', '', 'pimm-configurator&view=pimm-configurator']) {
    const { comparison, inlineDossiers } = createComparison(Controller, {
      payload: JSON.stringify(records.map(record => ({ ...record, url: `${record.url}&view=${view}` }))),
    });
    for (const dossier of inlineDossiers) {
      const anchor = dossier.querySelector('[data-pimm-dossier-configure]');
      anchor.href += `&view=${view}`;
      anchor.setAttribute('href', anchor.href);
    }
    comparison.connectedCallback();
    assert.equal(comparison.committedModel, view === 'pimm-configurator' ? '30G' : undefined);
  }
  const { comparison } = createComparison(Controller, {
    payload: JSON.stringify(records.map(record => ({ ...record, url: `${record.url}&view=pimm-configurator` }))),
  });
  comparison.connectedCallback();
  assert.equal(comparison.committedModel, undefined);
});

test('reconnect restores the 30G fallback before rejecting a newly invalid payload', async () => {
  const { Controller } = await loadController();
  const { comparison, cards, payloadNode } = createComparison(Controller);
  comparison.connectedCallback();
  comparison.commitModel('50G');
  payloadNode.textContent = '{invalid';

  comparison.connectedCallback();

  assert.equal(cards[0].getAttribute('aria-current'), 'true');
  assert.equal(cards[0].classList.contains('is-active'), true);
  assert.equal(cards[1].getAttribute('aria-current'), 'false');
  assert.equal(cards.reduce((count, card) => count + card.activeListenerCount(), 0), 0);
  assert.equal(comparison.committedModel, undefined);
  for (const card of cards) {
    const select = card.querySelector('[data-pimm-collection-select]');
    assert.equal(card.getAttribute('tabindex'), null);
    assert.equal(select.hidden, true);
    assert.equal(select.disabled, true);
  }
});
