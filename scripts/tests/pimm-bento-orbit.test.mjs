import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const root = new URL('../../', import.meta.url);
const source = await readFile(new URL('assets/pimm-bento-orbit.js', root), 'utf8');

function eventTarget() {
  const listeners = new Map();
  return {
    addEventListener(name, callback, { signal } = {}) {
      const callbacks = listeners.get(name) ?? new Set();
      callbacks.add(callback); listeners.set(name, callbacks);
      signal?.addEventListener('abort', () => callbacks.delete(callback), { once: true });
    },
    dispatch(name) { for (const callback of listeners.get(name) ?? []) callback(); },
    count(name) { return listeners.get(name)?.size ?? 0; },
  };
}

function harness({ reduced = false, saveData = false, hidden = false, observer = true, play } = {}) {
  let Controller;
  const videos = [], observers = [];
  const motion = Object.assign(eventTarget(), { matches: reduced });
  const connection = Object.assign(eventTarget(), { saveData });
  const poster = { src: 'static.webp', width: 2400, height: 1200, alt: 'Localized controls' };
  class Element {
    constructor() { this.dataset = { orbitSrc: 'orbit.mp4' }; this.children = [poster]; this.isConnected = true; }
    querySelector() { return poster; }
    append(node) { if (!this.children.includes(node)) this.children.push(node); node.parent = this; }
  }
  const document = Object.assign(eventTarget(), {
    hidden,
    createElement(tag) {
      assert.equal(tag, 'video');
      const video = {
        dataset: {}, attributes: {}, paused: true, plays: 0, loads: 0,
        setAttribute(name, value) { this.attributes[name] = value; },
        removeAttribute(name) { delete this[name]; },
        remove() { if (this.parent) this.parent.children = this.parent.children.filter((node) => node !== this); this.parent = null; },
        play() { this.plays++; this.paused = false; return play ? play() : Promise.resolve(); },
        pause() { this.paused = true; this.onpause?.(); },
        load() { this.loads++; },
      };
      videos.push(video); return video;
    },
  });
  vm.runInNewContext(source, {
    HTMLElement: Element, AbortController, document,
    navigator: { connection }, matchMedia: () => motion,
    IntersectionObserver: observer ? class {
      constructor(callback) { this.callback = callback; observers.push(this); }
      observe(target) { this.target = target; }
      disconnect() { this.disconnected = true; }
      intersect(isIntersecting) { this.callback([{ target: this.target, isIntersecting }]); }
    } : undefined,
    customElements: { get() {}, define(name, cls) { assert.equal(name, 'pimm-bento-orbit'); Controller = cls; } },
  });
  const element = new Controller(); element.connectedCallback();
  return { element, poster, videos, observers, motion, connection, document };
}

test('bento preserves four native stills without motion controls or removed video-still tiles', async () => {
  const story = await readFile(new URL('snippets/pimm-30g-product-story.liquid', root), 'utf8');
  assert.equal((story.match(/<img /g) ?? []).length, 4);
  assert.doesNotMatch(story, /<button|<video|pimm-bento__tile--(?:parts|workshop)/);
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', root), 'utf8');
  assert.match(css, /@media \(prefers-reduced-motion: reduce\) \{\s*[^}]*pimm-bento-orbit \[data-orbit-video\] \{ display: none;/);
  assert.match(css, /\[data-orbit-video\]\[hidden\] \{ display: none;/);
  assert.match(css, /pimm-bento__tile--controls video \{ object-position: 55% center;/);
});

test('autoplays muted inline looping video in view, showing only when playback starts', () => {
  const { element, videos, observers, poster } = harness();
  assert.equal(videos.length, 0); observers[0].intersect(true);
  const video = videos[0];
  assert.equal(video.src, 'orbit.mp4'); assert.equal(video.plays, 1);
  assert.equal(video.hidden, true); assert.equal(element.children[0], poster);
  video.onplaying(); assert.equal(video.hidden, false);
  assert.equal(poster.src, 'static.webp'); assert.equal(poster.alt, 'Localized controls');
  for (const property of ['muted', 'defaultMuted', 'autoplay', 'loop', 'playsInline', 'disablePictureInPicture']) assert.equal(video[property], true);
  assert.equal(video.controls, false); assert.equal(video.preload, 'none'); assert.equal(video.tabIndex, -1);
  assert.equal(video.attributes['aria-hidden'], 'true');
  assert.equal(video.width, 2400); assert.equal(video.height, 1200);
  observers[0].intersect(true); assert.equal(videos.length, 1); assert.equal(video.plays, 1);
});

test('offscreen video is paused and unloaded, then automatically restarts on return', () => {
  const { element, videos, observers, poster } = harness();
  observers[0].intersect(true); videos[0].onplaying(); observers[0].intersect(false);
  assert.deepEqual(element.children, [poster]); assert.equal(videos[0].src, undefined);
  assert.equal(videos[0].paused, true); assert.equal(videos[0].loads, 1);
  observers[0].intersect(true); videos[1].onplaying();
  assert.equal(element.children.length, 2); assert.equal(videos[1].hidden, false);
});

test('reduced motion, data saving and hidden documents never request video initially', () => {
  for (const options of [{ reduced: true }, { saveData: true }, { hidden: true }]) {
    const { videos, observers } = harness(options);
    observers[0].intersect(true); assert.equal(videos.length, 0);
  }
});

test('live preference and tab changes restore the still and resume only when permitted', () => {
  for (const [target, property, event] of [
    ['motion', 'matches', 'change'], ['connection', 'saveData', 'change'], ['document', 'hidden', 'visibilitychange'],
  ]) {
    const state = harness(); state.observers[0].intersect(true); state.videos[0].onplaying();
    state[target][property] = true; state[target].dispatch(event);
    assert.deepEqual(state.element.children, [state.poster]); assert.equal(state.videos[0].src, undefined);
    state[target][property] = false; state[target].dispatch(event);
    assert.equal(state.videos.length, 2); assert.equal(state.videos[1].hidden, true);
    state.videos[1].onplaying(); assert.equal(state.videos[1].hidden, false);
  }
});

test('buffering or unexpected pause shows the still until playback resumes', () => {
  const state = harness(); state.observers[0].intersect(true);
  const video = state.videos[0]; video.onplaying();
  video.onwaiting(); assert.equal(video.hidden, true);
  video.onplaying(); assert.equal(video.hidden, false);
  video.pause(); assert.equal(video.hidden, true);
});

test('stale playing and rejection callbacks cannot expose or terminate a newer player', async () => {
  let reject, calls = 0;
  const state = harness({ play: () => ++calls === 1 ? new Promise((resolve, fail) => { reject = fail; }) : Promise.resolve() });
  state.observers[0].intersect(true);
  const stalePlaying = state.videos[0].onplaying;
  state.motion.matches = true; state.motion.dispatch('change');
  stalePlaying(); assert.equal(state.videos[0].hidden, true);
  state.motion.matches = false; state.motion.dispatch('change'); state.videos[1].onplaying();
  reject(new Error('old play interrupted')); await Promise.resolve();
  assert.deepEqual(state.element.children, [state.poster, state.videos[1]]);
  assert.equal(state.videos[1].hidden, false); assert.equal(state.element.failed, false);
});

test('network errors, play rejection and synchronous play failure leave static without retry loops', async () => {
  for (const failure of ['network', 'reject', 'throw']) {
    const state = harness({ play: failure === 'reject' ? () => Promise.reject(new Error('denied')) :
      failure === 'throw' ? () => { throw new Error('unsupported'); } : undefined });
    state.observers[0].intersect(true);
    if (failure === 'network') state.videos[0].onerror();
    await Promise.resolve();
    assert.deepEqual(state.element.children, [state.poster]); assert.equal(state.videos[0].src, undefined);
    state.observers[0].intersect(false); state.observers[0].intersect(true); assert.equal(state.videos.length, 1);
  }
});

test('disconnect cancels playback/listeners and reconnects without stale observer effects', () => {
  const state = harness(); state.observers[0].intersect(true);
  const stalePlaying = state.videos[0].onplaying;
  state.element.isConnected = false; state.element.disconnectedCallback();
  assert.equal(state.observers[0].disconnected, true);
  assert.equal(state.motion.count('change'), 0); assert.equal(state.connection.count('change'), 0);
  assert.equal(state.document.count('visibilitychange'), 0); assert.equal(state.videos[0].src, undefined);
  stalePlaying(); assert.deepEqual(state.element.children, [state.poster]);
  state.element.isConnected = true; state.element.connectedCallback(); state.element.connectedCallback();
  assert.equal(state.motion.count('change'), 1); assert.equal(state.observers.length, 2);
  state.observers[0].intersect(true); assert.equal(state.videos.length, 1);
  state.observers[1].intersect(true); state.videos[1].onplaying(); assert.equal(state.element.children.length, 2);
});

test('missing observation support leaves progressive static image unchanged', () => {
  const { videos, element, poster } = harness({ observer: false });
  assert.equal(videos.length, 0); assert.deepEqual(element.children, [poster]);
});
