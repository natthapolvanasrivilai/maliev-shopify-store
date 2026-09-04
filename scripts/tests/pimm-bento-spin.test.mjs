import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const root = new URL('../../', import.meta.url);
const source = await readFile(new URL('assets/pimm-bento-spin.js', root), 'utf8');

function target() {
  const listeners = new Map();
  return {
    listeners,
    addEventListener(name, callback, options = {}) {
      const entries = listeners.get(name) || [];
      entries.push({ callback, options }); listeners.set(name, entries);
      options.signal?.addEventListener('abort', () => entries.splice(entries.findIndex((entry) => entry.callback === callback), 1), { once: true });
    },
    dispatch(type, values = {}) {
      const event = { type, pointerId: 1, isPrimary: true, button: 0, clientX: 0, clientY: 0,
        preventDefault() { this.prevented = true; }, ...values };
      for (const { callback } of listeners.get(type) || []) callback(event);
      return event;
    },
  };
}

function harness({ reduced = false, saveData = false, observer = true, dataset = {}, poster = {} } = {}) {
  const images = [], observers = [], frames = new Map(), draws = [];
  let Controller, serial = 0;
  const motion = Object.assign(target(), { matches: reduced });
  const connection = Object.assign(target(), { saveData });
  class Element {
    constructor() {
      Object.assign(this, target());
      this.attributes = {}; this.dataset = {}; this.children = []; this.isConnected = true;
    }
    setAttribute(key, value) { this.attributes[key] = value; }
    append(...nodes) { for (const node of nodes) { node.parent = this; this.children.push(node); } }
    remove() { if (this.parent) this.parent.children = this.parent.children.filter((node) => node !== this); }
    querySelector() { return this.poster; }
    setPointerCapture(id) { this.capture = id; }
    hasPointerCapture(id) { return this.capture === id; }
    releasePointerCapture() { this.capture = null; }
    focus(options) { this.focusOptions = options; }
    getBoundingClientRect() { return { width: 600, height: 300 }; }
  }
  const document = Object.assign(target(), {
    hidden: false,
    createElement(tag) {
      assert.ok(['canvas', 'div', 'span'].includes(tag));
      const element = new Element(); element.tag = tag;
      if (tag === 'canvas') element.getContext = () => ({ drawImage(image) { draws.push(image.src); } });
      return element;
    },
  });
  vm.runInNewContext(source, {
    HTMLElement: Element, AbortController, document, navigator: { connection }, matchMedia: () => motion,
    Image: class { constructor() { images.push(this); } },
    requestAnimationFrame(callback) { frames.set(++serial, callback); return serial; },
    cancelAnimationFrame(id) { frames.delete(id); },
    IntersectionObserver: observer ? class {
      constructor(callback) { this.callback = callback; observers.push(this); }
      observe(element) { this.element = element; }
      disconnect() { this.disconnected = true; }
      intersect(isIntersecting) { this.callback([{ target: this.element, isIntersecting }]); }
    } : undefined,
    customElements: { get() {}, define(name, cls) { assert.equal(name, 'pimm-bento-spin'); Controller = cls; } },
  });
  const element = new Controller();
  element.dataset = { frameTemplate: '/proof/frame-{frame}.png', frameCount: '120', label: 'Rotate machine', valueTemplate: 'View {angle} degrees', ...dataset };
  element.poster = { width: 1300, height: 650, naturalWidth: 2400, naturalHeight: 1200,
    getAttribute(name) { return { width: '2400', height: '1200' }[name] ?? null; },
    alt: 'Machine', src: 'still.webp', ...poster };
  element.children.push(element.poster); element.connectedCallback();
  return {
    element, images, observers, draws, document, motion, connection, frames,
    show() { observers[0]?.intersect(true); },
    tick(time = 0) { const callbacks = [...frames.values()]; frames.clear(); for (const callback of callbacks) callback(time); },
    complete(image = images.find((item) => item.onload && !item.done)) { image.done = true; image.onload(); },
  };
}

function pointer(state, name, x, y = 0, extra = {}) {
  return state.element.handle.dispatch(name, { clientX: x, clientY: y, ...extra });
}

test('progressive still and localized keyboard slider have no controls buttons', () => {
  const state = harness();
  assert.equal(state.images.length, 0);
  assert.equal(state.element.canvas.hidden, true);
  assert.equal(state.element.children[0].src, 'still.webp');
  assert.equal(state.element.handle.attributes.role, 'slider');
  assert.equal(state.element.handle.attributes['aria-label'], 'Rotate machine');
  assert.equal(state.element.handle.attributes['aria-valuetext'], 'View 0 degrees');
  assert.equal(state.element.handle.tabIndex, 0);
  assert.equal(state.element.hintLabel.textContent, 'Drag to rotate');
  assert.equal(state.element.hintIcon.className, 'pimm-bento-spin__hint-icon');
  assert.match(state.element.hintIcon.innerHTML, /pimm-bento-spin__cube-scene/);
  assert.match(state.element.hintIcon.innerHTML, /pimm-bento-spin__cube-face--front/);
  assert.match(state.element.hintIcon.innerHTML, /pimm-bento-spin__cube-face--back/);
  assert.match(state.element.hintIcon.innerHTML, /pimm-bento-spin__cube-face--bottom/);
  assert.match(state.element.hintIcon.innerHTML, /pimm-bento-spin__hint-orbit/);
  assert.equal(state.element.hint.children[0], state.element.hintIcon);
  assert.equal(state.element.hint.children[1], state.element.hintLabel);
  assert.equal(state.element.hint.attributes['aria-hidden'], 'true');
  assert.equal(state.element.hint.hidden, undefined);
  assert.doesNotMatch(source, /createElement\(['"]button/);
});

test('interaction badge stays available on focus and hides permanently after pointer or keyboard input', () => {
  const focused = harness({ reduced: true, dataset: twoAxis }); focused.show();
  focused.element.handle.dispatch('focus');
  assert.equal(focused.element.hint.hidden, undefined);
  for (const interaction of ['pointer', 'keyboard']) {
    const state = harness({ reduced: true, dataset: twoAxis }); state.show();
    if (interaction === 'pointer') pointer(state, 'pointerdown', 100, 100);
    if (interaction === 'keyboard') state.element.handle.dispatch('keydown', { key: 'ArrowRight' });
    assert.equal(state.element.hint.hidden, true, `${interaction} leaves hint visible`);
    state.element.sync();
    assert.equal(state.element.hint.hidden, true, `${interaction} restores hint`);
  }
});

test('canvas preserves declared native resolution independently of CSS-rendered image dimensions', () => {
  const state = harness({ poster: { width: 700, height: 350 } });
  assert.equal(state.element.canvas.width, 2400); assert.equal(state.element.canvas.height, 1200);
  const natural = harness({ poster: { getAttribute: () => null, naturalWidth: 1800, naturalHeight: 900 } });
  assert.equal(natural.element.canvas.width, 1800); assert.equal(natural.element.canvas.height, 900);
  const invalid = harness({ poster: { getAttribute: () => 'Infinity', naturalWidth: 0, naturalHeight: NaN } });
  assert.equal(invalid.element.canvas.width, 2400); assert.equal(invalid.element.canvas.height, 1200);
});

test('leaving before horizontal intent clears the pending pointer gesture', () => {
  const state = harness({ reduced: true }); state.show();
  pointer(state, 'pointerdown', 100); pointer(state, 'pointermove', 103);
  pointer(state, 'pointerleave', 103); assert.equal(state.element.drag, null);
  pointer(state, 'pointerdown', 100); pointer(state, 'pointermove', 150);
  pointer(state, 'pointerleave', 150); assert.ok(state.element.drag, 'captured horizontal drag can continue outside');
});

test('horizontal drag rotates in both directions and wraps the full 360 range', () => {
  const state = harness({ reduced: true }); state.show();
  pointer(state, 'pointerdown', 100); pointer(state, 'pointermove', 160); state.tick();
  assert.equal(state.element.frame, 108);
  assert.equal(state.element.handle.attributes['aria-valuenow'], '324');
  pointer(state, 'pointerup', 160);
  pointer(state, 'pointerdown', 100); pointer(state, 'pointermove', -20); state.tick();
  assert.equal(state.element.frame, 12);
  pointer(state, 'pointerup', -20);
  pointer(state, 'pointerdown', 0); pointer(state, 'pointermove', 600); state.tick();
  assert.equal(state.element.frame, 12);
  assert.ok(state.images.length <= 2, 'two loads, not a flood during drag');
  assert.equal(state.element.handle.focusOptions.preventScroll, true);
});

test('vertical gestures retain native scrolling, pointermove is passive, and CSS permits pan-y', async () => {
  const state = harness({ reduced: true }); state.show();
  const down = pointer(state, 'pointerdown', 100);
  const move = pointer(state, 'pointermove', 102, 25);
  assert.equal(down.prevented, undefined); assert.equal(move.prevented, undefined);
  assert.equal(state.element.drag, null); assert.equal(state.element.handle.capture, undefined);
  assert.equal(state.images.length, 0); assert.equal(state.frames.size, 0);
  assert.equal(state.element.handle.listeners.get('pointermove')[0].options.passive, true);
  const css = await readFile(new URL('assets/pimm-bento-spin.css', root), 'utf8');
  assert.match(css, /touch-action: pan-y pinch-zoom/);
  assert.match(css, /--spin-hit-left, 45%/);
  assert.match(css, /:focus-visible/);
});

test('keys wrap, Home restores front, and modifiers or vertical arrows do not swallow scroll', () => {
  const state = harness({ reduced: true }); state.show();
  const handle = state.element.handle;
  assert.equal(handle.dispatch('keydown', { key: 'ArrowLeft' }).prevented, true);
  assert.equal(state.element.frame, 119);
  assert.equal(handle.attributes['aria-valuenow'], '357');
  handle.dispatch('keydown', { key: 'ArrowRight' }); assert.equal(state.element.frame, 0);
  handle.dispatch('keydown', { key: 'ArrowLeft' }); handle.dispatch('keydown', { key: 'Home' });
  assert.equal(state.element.frame, 0);
  for (const extra of [{ key: 'ArrowDown' }, { key: 'ArrowRight', ctrlKey: true }, { key: 'ArrowLeft', shiftKey: true }]) {
    assert.equal(handle.dispatch('keydown', extra).prevented, undefined);
    assert.equal(state.element.frame, 0);
  }
});

test('reduced motion and save-data suppress hints but explicit dragging remains enabled', () => {
  for (const preferences of [{ reduced: true }, { saveData: true }]) {
    const state = harness(preferences); state.show();
    assert.equal(state.images.length, 0); assert.equal(state.frames.size, 0);
    pointer(state, 'pointerdown', 0); pointer(state, 'pointermove', 50); state.tick();
    assert.equal(state.element.frame, 110);
    assert.ok(state.images.length > 0);
    if (preferences.saveData) assert.equal(state.images.length, 1);
    state.complete(); assert.equal(state.element.canvas.hidden, false);
  }
});

test('one subtle hint loads only five native frames, returns front, and never repeats', () => {
  const state = harness(); state.show();
  assert.equal(state.images.length, 2);
  for (let index = 0; index < 5; index++) state.complete();
  assert.equal(state.images.length, 5); assert.equal(state.frames.size, 1);
  state.tick(0); state.tick(600);
  assert.ok(state.element.frame <= 2 || state.element.frame >= 118);
  state.tick(1800); state.tick(2400);
  assert.equal(state.element.frame, 0); assert.equal(state.frames.size, 0);
  state.observers[0].intersect(false); state.show();
  assert.equal(state.images.length, 5); assert.equal(state.frames.size, 0);
});

test('interaction immediately cancels hint and does not autorotate after release', () => {
  const state = harness(); state.show();
  for (let index = 0; index < 5; index++) state.complete();
  state.tick(0); state.tick(600);
  pointer(state, 'pointerdown', 100);
  assert.equal(state.frames.size, 0);
  pointer(state, 'pointermove', 150); state.tick(); pointer(state, 'pointerup', 150);
  const selected = state.element.frame; state.tick(10000);
  assert.equal(state.element.frame, selected); assert.equal(state.frames.size, 0);
});

test('keyboard focus reveals the badge while pointer cancellation never leaves a drag running', () => {
  const state = harness(); state.show();
  for (let index = 0; index < 5; index++) state.complete();
  state.element.handle.dispatch('focus');
  assert.equal(state.frames.size, 1);
  assert.equal(state.element.hint.hidden, undefined);
  pointer(state, 'pointerdown', 100); pointer(state, 'pointermove', 150);
  assert.equal(state.frames.size, 1);
  pointer(state, 'pointercancel', 150);
  assert.equal(state.frames.size, 0); assert.equal(state.element.drag, null);
  assert.equal(state.element.handle.capture, null);
  assert.equal(state.element.handle.dataset.dragging, undefined);
});

test('live reduced-motion and visibility changes cancel automatic work', () => {
  const state = harness(); state.show();
  for (let index = 0; index < 5; index++) state.complete();
  state.tick(0); state.tick(600);
  state.motion.matches = true; state.motion.dispatch('change');
  assert.equal(state.frames.size, 0); assert.equal(state.element.canvas.hidden, true);
  assert.equal(state.element.frame, 0);
  state.element.handle.dispatch('keydown', { key: 'ArrowRight' });
  state.document.hidden = true; state.document.dispatch('visibilitychange');
  assert.equal(state.element.pending.size, 0); assert.equal(state.element.cache.size, 0);
  state.element.handle.dispatch('keydown', { key: 'ArrowRight' });
  assert.equal(state.element.frame, 1);
});

test('out-of-order image loads cannot paint a stale direction and errors preserve still', () => {
  const state = harness({ reduced: true }); state.show();
  const handle = state.element.handle;
  handle.dispatch('keydown', { key: 'ArrowRight' });
  handle.dispatch('keydown', { key: 'ArrowLeft' });
  state.complete(state.images[0]); assert.equal(state.draws.length, 0);
  const zero = state.images.find((image) => image.src.endsWith('0001.png'));
  assert.ok(zero); state.complete(zero); assert.equal(state.element.canvas.hidden, false);
  handle.dispatch('keydown', { key: 'ArrowLeft' });
  state.complete(state.images[1]);
  const last = state.images.find((image) => image.src.endsWith('0120.png'));
  last.onerror(); assert.equal(state.element.canvas.hidden, true);
  const count = state.images.length; state.element.pump();
  assert.equal(state.images.length, count, 'failed frame is not retried repeatedly');
});

test('offscreen/disconnect cancels loads and stale callbacks cannot paint after reconnect', () => {
  const state = harness({ reduced: true }); state.show();
  state.element.handle.dispatch('keydown', { key: 'ArrowRight' });
  const image = state.images[0], staleLoad = image.onload, staleError = image.onerror;
  state.observers[0].intersect(false);
  assert.equal(image.src, ''); assert.equal(state.element.pending.size, 0);
  staleLoad(); staleError(); assert.equal(state.draws.length, 0);
  state.element.isConnected = false; state.element.disconnectedCallback();
  assert.equal(state.element.children.length, 1);
  state.element.isConnected = true; state.element.connectedCallback();
  state.observers[0].intersect(true); assert.equal(state.element.visible, false);
  state.observers[1].intersect(true); staleLoad(); assert.equal(state.draws.length, 0);
  assert.equal(state.element.children.length, 4);
});

test('decoded cache remains bounded during repeated requests', () => {
  const state = harness({ reduced: true, saveData: true }); state.show();
  for (let frame = 1; frame <= 20; frame++) {
    state.element.handle.dispatch('keydown', { key: 'ArrowRight' }); state.complete();
    assert.ok(state.element.cache.size <= 6); assert.ok(state.element.pending.size <= 2);
  }
});

test('unsupported configuration stays a plain image and safely disconnects', () => {
  const state = harness({ dataset: { frameCount: 'bad' } });
  state.element.disconnectedCallback();
  assert.equal(state.element.children.length, 1); assert.equal(state.images.length, 0);
});

test('Shopify asset source expands to the numbered two-axis frame template', () => {
  const state = harness({
    reduced: true,
    dataset: {
      frameTemplate: undefined,
      frameSource: '/assets/pimm-bento-configuration-r00-f0001.webp?v=1',
      rowCount: '7',
      defaultRow: '3',
      rowStep: '2',
    },
  });
  state.show();
  state.element.handle.dispatch('keydown', { key: 'ArrowUp' });
  assert.equal(state.images[0].src, '/assets/pimm-bento-configuration-r04-f0001.webp?v=1');
});

const twoAxis = {
  frameTemplate: '/configuration/row-{row}/frame-{frame}.png', rowCount: '7', defaultRow: '3', rowStep: '2',
  roleDescription: '3D viewer', valueTemplate: 'Rotation {angle} degrees, tilt {tilt} degrees',
};

test('two-axis diagonal drag updates yaw and pitch simultaneously with the exact row URL', () => {
  const state = harness({ reduced: true, saveData: true, dataset: twoAxis }); state.show();
  pointer(state, 'pointerdown', 100, 100); pointer(state, 'pointermove', 160, 50); state.tick();
  assert.equal(state.element.frame, 108); assert.equal(state.element.row, 4);
  assert.equal(state.images[0].src, '/configuration/row-04/frame-0109.png');
  state.complete();
  assert.equal(state.element.dataset.spinFrame, '109'); assert.equal(state.element.dataset.spinRow, '4');
  pointer(state, 'pointerup', 160, 50); state.tick(9999);
  assert.equal(state.element.frame, 108); assert.equal(state.element.row, 4);
  assert.equal(state.frames.size, 0, 'release holds both axes');
});

test('mouse and touch drag map yaw and pitch independently in both directions', () => {
  for (const pointerType of ['mouse', 'touch']) {
    for (const direction of [-1, 1]) {
      const state = harness({ reduced: true, dataset: twoAxis }); state.show();
      pointer(state, 'pointerdown', 100, 100, { pointerType });
      pointer(state, 'pointermove', 100 + direction * 60, 100 + direction * 50, { pointerType });
      state.tick();
      assert.equal(state.element.frame, direction === 1 ? 108 : 12);
      assert.equal(state.element.row, 3 - direction);
      pointer(state, 'pointermove', 100, 100, { pointerType }); state.tick();
      assert.equal(state.element.frame, 0);
      assert.equal(state.element.row, 3, 'returning the hand restores the starting orientation');
    }
  }
});

test('two-axis pitch clamps at endpoints while yaw continues to wrap', () => {
  const state = harness({ reduced: true, dataset: twoAxis }); state.show();
  pointer(state, 'pointerdown', 100, 100); pointer(state, 'pointermove', 700, -500); state.tick();
  assert.equal(state.element.frame, 0); assert.equal(state.element.row, 6);
  pointer(state, 'pointerup', 700, -500);
  pointer(state, 'pointerdown', 100, 100); pointer(state, 'pointermove', 40, 1200); state.tick();
  assert.equal(state.element.frame, 12); assert.equal(state.element.row, 0);
});

test('two-axis keyboard exposes both coordinates without invalid slider ARIA', () => {
  const state = harness({ reduced: true, dataset: twoAxis }); state.show();
  const { handle, status } = state.element;
  assert.equal(handle.attributes.role, 'group');
  assert.equal(handle.attributes['aria-roledescription'], '3D viewer');
  assert.equal(handle.attributes['aria-valuenow'], undefined);
  assert.equal(status.attributes['aria-live'], 'polite');
  assert.equal(status.textContent, 'Rotation 0 degrees, tilt 0 degrees');
  assert.equal(handle.dispatch('keydown', { key: 'ArrowUp' }).prevented, true);
  handle.dispatch('keydown', { key: 'ArrowLeft' });
  assert.equal(status.textContent, 'Rotation 357 degrees, tilt 2 degrees');
  for (let step = 0; step < 8; step++) handle.dispatch('keydown', { key: 'ArrowDown' });
  assert.equal(state.element.row, 0); assert.equal(state.element.frame, 119);
  assert.equal(status.textContent, 'Rotation 357 degrees, tilt -6 degrees');
  handle.dispatch('keydown', { key: 'Home' });
  assert.equal(state.element.row, 3); assert.equal(state.element.frame, 0);
});

test('two-axis touch area owns vertical gestures, without changing single-axis pan-y', async () => {
  const state = harness({ reduced: true, dataset: twoAxis }); state.show();
  assert.equal(state.element.handle.dataset.twoAxis, '');
  pointer(state, 'pointerdown', 100, 100, { pointerType: 'touch' });
  pointer(state, 'pointermove', 100, 50, { pointerType: 'touch' }); state.tick();
  assert.equal(state.element.row, 4); assert.equal(state.element.frame, 0);
  assert.equal(state.element.handle.capture, 1);
  const legacy = harness({ reduced: true }); legacy.show();
  assert.equal(legacy.element.handle.dataset.twoAxis, undefined);
  const css = await readFile(new URL('assets/pimm-bento-spin.css', root), 'utf8');
  assert.match(css, /\.pimm-bento-spin__handle\[data-two-axis\] \{ touch-action: none;/);
  assert.match(css, /touch-action: pan-y pinch-zoom;/);
  assert.match(css, /\.pimm-bento-spin__hint \{/);
  assert.match(css, /\.pimm-bento-spin__hint\[hidden\] \{ display: none; \}/);
  assert.match(css, /top: clamp\(16px, 3vw, 28px\)/);
  assert.match(css, /pimm-bento-spin:hover \.pimm-bento-spin__hint/);
  assert.match(css, /pimm-bento-spin:hover \.pimm-bento-spin__hint-icon[\s\S]*?translate3d\(-110px, 0, 0\)/);
  assert.match(css, /@keyframes pimm-spin-hint-cube/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)[\s\S]*?animation: none !important/);
});

test('two-axis reduced motion and save-data allow deliberate movement but no automatic hint', () => {
  for (const preferences of [{ reduced: true }, { saveData: true }]) {
    const state = harness({ ...preferences, dataset: twoAxis }); state.show();
    assert.equal(state.images.length, 0); assert.equal(state.frames.size, 0);
    state.element.handle.dispatch('keydown', { key: 'ArrowUp' });
    assert.equal(state.element.row, 4); assert.ok(state.images.length > 0);
    state.complete(); assert.equal(state.element.canvas.hidden, false);
  }
});

test('two-axis stale rows never paint and automatic hint stays at the default pitch', () => {
  const state = harness({ reduced: true, saveData: true, dataset: twoAxis }); state.show();
  state.element.handle.dispatch('keydown', { key: 'ArrowUp' });
  state.element.handle.dispatch('keydown', { key: 'ArrowDown' });
  state.complete(state.images[0]); assert.equal(state.draws.length, 0);
  state.complete(state.images[1]); assert.equal(state.draws[0], '/configuration/row-03/frame-0001.png');
  const hint = harness({ dataset: twoAxis }); hint.show();
  for (let index = 0; index < 5; index++) hint.complete();
  assert.ok(hint.images.every((image) => image.src.includes('/row-03/')));
  hint.tick(0); hint.tick(600); hint.tick(2400);
  assert.equal(hint.element.row, 3); assert.equal(hint.element.frame, 0);
});

test('invalid row configurations stay a safe static image', () => {
  for (const dataset of [{ ...twoAxis, rowCount: '7.5' }, { ...twoAxis, defaultRow: '7' },
    { ...twoAxis, rowStep: '0' }, { ...twoAxis, frameTemplate: '/frame-{frame}.png' }]) {
    const state = harness({ dataset }); state.element.disconnectedCallback();
    assert.equal(state.images.length, 0); assert.equal(state.element.children.length, 1);
  }
});

test('web-sized decoded frames warm both axes within a pixel budget', () => {
  const state = harness({ reduced: true, dataset: twoAxis }); state.show();
  state.element.handle.dispatch('keydown', { key: 'ArrowRight' });
  state.images[0].naturalWidth = 600; state.images[0].naturalHeight = 300;
  state.complete(state.images[0]);
  assert.equal(state.element.cacheLimit, 93);
  const candidates = state.element.nearbyViews();
  assert.ok(candidates.includes(state.element.viewKey(1, 2)));
  assert.ok(candidates.includes(state.element.viewKey(1, 4)));
  assert.ok(candidates.includes(state.element.viewKey(9, 3)));
  assert.ok(candidates.length <= state.element.cacheLimit);
  assert.equal(state.element.pending.size, 4);
});

test('image decode finishes before a frame is exposed and stale decoded frames are ignored', async () => {
  const state = harness({ reduced: true, saveData: true }); state.show();
  state.element.handle.dispatch('keydown', { key: 'ArrowRight' });
  let finish;
  state.images[0].decode = () => new Promise(resolve => { finish = resolve; });
  state.complete(); assert.equal(state.draws.length, 0);
  state.element.handle.dispatch('keydown', { key: 'ArrowRight' });
  finish(); await Promise.resolve(); await Promise.resolve();
  assert.equal(state.draws.length, 0);
  state.complete(state.images[1]); assert.equal(state.draws.length, 1);
  state.element.requestFrame(state.element.frame);
  assert.equal(state.draws.length, 1, 'unchanged view does not repaint');
});

test('dragging can display nearby native views but release resolves the exact angle', () => {
  const state = harness({ reduced: true, saveData: true }); state.show();
  state.element.handle.dispatch('keydown', { key: 'ArrowRight' }); state.complete();
  pointer(state, 'pointerdown', 100); pointer(state, 'pointermove', 85); state.tick();
  assert.equal(state.element.frame, 4);
  assert.equal(state.element.dataset.spinFrame, '2', 'nearby decoded view stays useful during drag');
  pointer(state, 'pointerup', 85); state.complete();
  assert.equal(state.element.dataset.spinFrame, '5', 'exact requested view wins after loading');
});
