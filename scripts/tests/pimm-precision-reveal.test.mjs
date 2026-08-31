import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const controllerUrl = new URL('../../assets/maliev-pimm-machine.js', import.meta.url);
const validPayload = JSON.stringify([
  { id: 1, model: '30G' },
  { id: 2, model: '50G' },
]);

async function loadController({ reducedMotion = false } = {}) {
  const source = await readFile(controllerUrl, 'utf8');
  const observers = [];
  let Controller;

  class FakeHTMLElement {
    constructor() {
      this.classList = {
        values: new Set(),
        add: (...names) => names.forEach((name) => this.classList.values.add(name)),
        contains: (name) => this.classList.values.has(name),
      };
    }

    addEventListener() {}
  }

  class FakeIntersectionObserver {
    constructor(callback, options) {
      this.callback = callback;
      this.options = options;
      this.targets = [];
      this.disconnected = false;
      observers.push(this);
    }

    observe(target) {
      this.targets.push(target);
    }

    unobserve(target) {
      this.targets = this.targets.filter((candidate) => candidate !== target);
    }

    disconnect() {
      this.disconnected = true;
      this.targets = [];
    }
  }

  const window = {
    IntersectionObserver: FakeIntersectionObserver,
    matchMedia: () => ({ matches: reducedMotion }),
    setTimeout,
    clearTimeout,
  };

  vm.runInNewContext(source, {
    HTMLElement: FakeHTMLElement,
    URL,
    cancelAnimationFrame: () => {},
    customElements: {
      get: () => undefined,
      define: (_name, constructor) => { Controller = constructor; },
    },
    requestAnimationFrame: (callback) => { callback(); return 1; },
    window,
  });

  return { Controller, observers };
}

function createChapter({ hiddenStory = false } = {}) {
  return {
    dataset: {},
    closest: (selector) => selector === '[data-pimm-story-model][hidden]' && hiddenStory ? {} : null,
  };
}

function createProduct(Controller, chapters) {
  const product = new Controller();
  product.querySelector = (selector) => selector === '[data-pimm-variant-data]'
    ? { dataset: { pimmInvalidMessage: 'Unavailable' }, textContent: validPayload }
    : null;
  product.querySelectorAll = (selector) => {
    if (selector === '[data-pimm-reveal]') return chapters;
    if (selector === '[data-pimm-media-model]') return [];
    return [];
  };
  return product;
}

test('precision reveal activates visible story chapters and leaves hidden model stories untouched', async () => {
  const { Controller, observers } = await loadController();
  const visibleChapter = createChapter();
  const hiddenChapter = createChapter({ hiddenStory: true });
  const product = createProduct(Controller, [visibleChapter, hiddenChapter]);

  product.connectedCallback();

  assert.equal(product.classList.contains('pimm-motion-ready'), true);
  assert.equal(observers.length, 1);
  assert.equal(visibleChapter.dataset.pimmRevealState, 'pending');
  assert.equal(hiddenChapter.dataset.pimmRevealState, undefined);

  observers[0].callback([{ target: visibleChapter, isIntersecting: true }]);

  assert.equal(visibleChapter.dataset.pimmRevealState, 'visible');
});

test('precision reveal remains completely static when reduced motion is requested', async () => {
  const { Controller, observers } = await loadController({ reducedMotion: true });
  const chapter = createChapter();
  const product = createProduct(Controller, [chapter]);

  product.connectedCallback();

  assert.equal(product.classList.contains('pimm-motion-ready'), false);
  assert.equal(observers.length, 0);
  assert.equal(chapter.dataset.pimmRevealState, undefined);
});

test('precision reveal releases its observer when Shopify removes the section', async () => {
  const { Controller, observers } = await loadController();
  const product = createProduct(Controller, [createChapter()]);
  product.connectedCallback();

  product.disconnectedCallback();

  assert.equal(observers[0].disconnected, true);
});
