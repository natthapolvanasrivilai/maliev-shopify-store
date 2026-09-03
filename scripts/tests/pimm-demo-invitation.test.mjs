import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import { Liquid } from 'liquidjs';

const root = new URL('../../', import.meta.url);

async function harness({ reduced = false, observer = true, animate = true } = {}) {
  let Controller;
  const plays = [];
  const listeners = {};
  const motion = { matches: reduced, addEventListener: (name, fn) => { listeners.motion = fn; } };
  const document = { hidden: false, addEventListener: (name, fn) => { listeners[name] = fn; } };
  class Element {
    addEventListener(name, fn) { listeners[name] = fn; }
    querySelector(selector) {
      return animate ? { animate: (frames, options) => {
        const animation = { frames, options, selector, finished: new Promise(() => {}), cancelled: false,
          cancel() { this.cancelled = true; } };
        plays.push(animation);
        return animation;
      } } : {};
    }
  }
  const context = { HTMLElement: Element, AbortController, document, matchMedia: () => motion,
    customElements: { get() {}, define(name, cls) { Controller = cls; } },
    IntersectionObserver: observer ? class {
      constructor(callback) { this.callback = callback; }
      observe() {}
      disconnect() { this.disconnected = true; }
    } : undefined,
  };
  vm.runInNewContext(await readFile(new URL('assets/pimm-demo-invitation.js', root), 'utf8'), context);
  const element = new Controller(); element.connectedCallback();
  return { element, plays, document, motion, listeners };
}

test('plays one authored entrance and does not replay on viewport re-entry', async () => {
  const { element, plays } = await harness();
  element.observer.callback([{ isIntersecting: true }]);
  assert.equal(plays.length, 3);
  assert.equal(plays[0].selector, 'h2');
  assert.equal(plays[0].options.duration, 950);
  assert.ok(plays[0].frames[0].clipPath);
  element.observer.callback([{ isIntersecting: false }]);
  assert.ok(plays.every(animation => animation.cancelled));
  element.observer.callback([{ isIntersecting: true }]);
  assert.equal(plays.length, 3);
});

test('reduced motion is static and a live preference change cancels all motion', async () => {
  const staticCase = await harness({ reduced: true });
  staticCase.element.observer.callback([{ isIntersecting: true }]);
  assert.equal(staticCase.plays.length, 0);
  const active = await harness();
  active.element.observer.callback([{ isIntersecting: true }]);
  active.motion.matches = true; active.listeners.motion();
  assert.ok(active.plays.every(animation => animation.cancelled));
});

test('hidden tabs delay first entrance and cancel an active entrance', async () => {
  const { element, plays, document, listeners } = await harness();
  document.hidden = true;
  element.observer.callback([{ isIntersecting: true }]);
  assert.equal(plays.length, 0);
  document.hidden = false; listeners.visibilitychange();
  assert.equal(plays.length, 3);
  document.hidden = true; listeners.visibilitychange();
  assert.ok(plays.every(animation => animation.cancelled));
});

test('keyboard focus immediately settles the action and prevents later entrance', async () => {
  const { element, plays, listeners } = await harness();
  element.observer.callback([{ isIntersecting: true }]);
  listeners.focusin();
  assert.ok(plays.every(animation => animation.cancelled));
  element.enter();
  assert.equal(plays.length, 3);
});

test('missing animation APIs leave static content and teardown cancels listeners', async () => {
  const noObserver = await harness({ observer: false });
  assert.equal(noObserver.plays.length, 0);
  noObserver.element.disconnectedCallback();
  const noAnimation = await harness({ animate: false });
  noAnimation.element.observer.callback([{ isIntersecting: true }]);
  assert.equal(noAnimation.plays.length, 0);
  const active = await harness();
  active.element.observer.callback([{ isIntersecting: true }]);
  const signal = active.element.abort.signal;
  active.element.disconnectedCallback();
  assert.ok(signal.aborted);
  assert.ok(active.element.observer.disconnected);
  assert.ok(active.plays.every(animation => animation.cancelled));
});

test('Liquid preserves route, statuses and copy while enhancing only 30G', async () => {
  const source = (await readFile(new URL('snippets/pimm-purchase-qualification.liquid', root), 'utf8'))
    .replace(/{% doc %}[\s\S]*?{% enddoc %}/, '');
  const liquid = new Liquid();
  liquid.registerFilter('t', key => key);
  for (const pageModel of ['30G', '50G']) {
    for (const [valid, available, status] of [[true, true, 'made_to_order'], [true, false, 'out_of_stock'], [false, true, 'unavailable']]) {
      const html = await liquid.parseAndRender(source, {
        section: { id: 'test', settings: { page_model: pageModel, factory_visit_url: '' } },
        routes: { root_url: '/th' }, model_contract_valid: valid, selected_variant: { available },
      });
      assert.match(html, /href="\/th\/pages\/contact"/);
      assert.match(html, new RegExp(`status.${status}`));
      assert.match(html, /purchase.heading/);
      assert.match(html, /purchase.body/);
      assert.equal((html.match(/<a /g) || []).length, 1);
      assert.equal(html.includes('<pimm-demo-invitation>'), pageModel === '30G');
      assert.equal(html.includes('pimm-invitation-arrow'), pageModel === '30G');
    }
  }
  const html = await liquid.parseAndRender(source, {
    section: { id: 'test', settings: { page_model: '30G', factory_visit_url: '/pages/visit' } },
    routes: { root_url: '/' },
  });
  assert.match(html, /href="\/pages\/visit"/);
  const translated = await liquid.parseAndRender(source, {
    section: { id: 'test', settings: { page_model: '30G' } },
    pages: { contact: { url: '/th/pages/ติดต่อ' } }, routes: { root_url: '/th' },
  });
  assert.match(translated, /href="\/th\/pages\/ติดต่อ"/);
  for (const rootUrl of ['/', '/th/', '/th']) {
    const output = await liquid.parseAndRender(source, {
      section: { id: 'test', settings: { page_model: '30G' } }, routes: { root_url: rootUrl },
    });
    assert.match(output, new RegExp(`href="${rootUrl.startsWith('/th') ? '/th' : ''}/pages/contact"`));
  }
});

test('styles keep static content visible with focus and reduced-motion fallbacks', async () => {
  const styles = await readFile(new URL('assets/maliev-pimm-30g-hero.css', root), 'utf8');
  const target = styles.slice(styles.indexOf('.pimm-machine[data-page-model="30G"] .pimm-machine__purchase {'), styles.indexOf('.pimm-machine[data-page-model="30G"] pimm-hero-reveal'));
  assert.doesNotMatch(target, /opacity:\s*0|visibility:\s*hidden/);
  assert.match(target, /focus-visible/);
  assert.match(target, /prefers-reduced-motion: reduce/);
  assert.match(target, /max-width: 749px/);
});
