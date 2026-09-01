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

function createDossier(model, { inline = false } = {}) {
  const values = dossierValues[model];
  const dossier = new FakeNode({
    dataset: { model, ...(inline ? { pimmCollectionInlineDossier: '' } : {}) },
    classes: inline && model === '30G' ? ['is-active'] : [],
  });
  const configure = new FakeNode({ textContent: values.configure });
  configure.href = `/products/pimm?variant=${model === '30G' ? 30 : 50}`;
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
  return card;
}

async function loadController({ reducedMotion = false } = {}) {
  const source = await readFile(controllerUrl, 'utf8');
  let Controller;
  let nextTimerId = 1;
  const timers = [];
  const window = {
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

function createComparison(Controller, { payload = JSON.stringify(records) } = {}) {
  const comparison = new Controller();
  comparison.dataset = {
    availableLabel: 'Made to order',
    unavailableLabel: 'Out of stock',
  };
  const cards = [createCard('30G'), createCard('50G')];
  const inlineDossiers = [createDossier('30G', { inline: true }), createDossier('50G', { inline: true })];
  const desktopDossier = createDossier('30G');
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
  assert.equal(activeTimerCount(), 5);
});

test('physical frame playback is exact, non-looping, and replaces overlapping timers', async () => {
  const { Controller, runDelay, activeTimerCount } = await loadController();
  const { comparison, cards } = createComparison(Controller);
  comparison.connectedCallback();

  comparison.playSequence(cards[0]);
  assert.equal(activeTimerCount(), 5);
  comparison.playSequence(cards[0]);
  assert.equal(activeTimerCount(), 5);
  runDelay(0);
  assert.equal(visibleFrame(cards[0]), 'front');
  runDelay(180);
  assert.equal(visibleFrame(cards[0]), 'left');
  runDelay(360);
  assert.equal(visibleFrame(cards[0]), 'front');
  runDelay(540);
  assert.equal(visibleFrame(cards[0]), 'right');
  runDelay(720);
  assert.equal(visibleFrame(cards[0]), 'front');
  assert.equal(activeTimerCount(), 0);
});

test('reduced motion never schedules angle playback', async () => {
  const { Controller, timers } = await loadController({ reducedMotion: true });
  const { comparison, cards } = createComparison(Controller);
  comparison.connectedCallback();

  comparison.playSequence(cards[0]);

  assert.equal(timers.length, 0);
  assert.equal(visibleFrame(cards[0]), 'front');
});

test('invalid records preserve the server fallback and attach no playback listeners', async () => {
  const { Controller } = await loadController();
  const { comparison, cards } = createComparison(Controller, { payload: '{invalid' });

  comparison.connectedCallback();

  assert.equal(cards[0].classList.contains('is-active'), true);
  assert.equal(cards[0].getAttribute('aria-current'), 'true');
  assert.equal(cards.reduce((count, card) => count + card.activeListenerCount(), 0), 0);
  assert.equal(comparison.committedModel, undefined);
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
});
