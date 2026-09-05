import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
import { Liquid } from 'liquidjs';

const root = new URL('../../', import.meta.url);
const release = 'pimm-30g-hero-reveal-20260902-r01';

test('30G hero has one model-specific demo action; other model actions stay intact', async () => {
  const source = await readFile(new URL('snippets/pimm-hero-console.liquid', root), 'utf8');
  const actions = source.slice(source.indexOf('<div class="pimm-machine__actions">'), source.indexOf('  <figure'));
  const liquid = new Liquid();
  liquid.registerFilter('t', (key) => key);
  for (const model of ['30G', '50G']) {
    const html = await liquid.parseAndRender(actions, { section: { id: 'test', settings: { page_model: model } }, factory_visit_url: '/pages/contact' });
    assert.equal((html.match(/<a /g) || []).length, model === '30G' ? 1 : 2);
    assert.match(html, /href="\/pages\/contact"/);
    if (model === '30G') {
      assert.match(html, /hero.demo_cta/);
      assert.match(html, /aria-describedby="PimmDemoNote-test"/);
      assert.doesNotMatch(html, /purchase.heading|href="#PimmMachineQualification/);
      assert.match(html, /aria-hidden="true" focusable="false"/);
    } else {
      assert.match(html, /purchase.heading/);
    }
  }
});

test('30G demo copy is present in English and Thai and arrow respects reduced motion', async () => {
  for (const name of ['en.default', 'th']) {
    const locale = JSON.parse((await readFile(new URL(`locales/${name}.json`, root), 'utf8')).replace(/^\/\*[\s\S]*?\*\/\s*/, ''));
    assert.ok(locale.products.pimm_machine.hero.demo_cta.includes('30G'));
    assert.ok(locale.products.pimm_machine.hero.demo_note);
  }
  const css = await readFile(new URL('assets/maliev-pimm-30g-hero.css', root), 'utf8');
  assert.match(css, /demo-cta:focus-visible/);
  assert.match(css, /prefers-reduced-motion: reduce[\s\S]*demo-arrow \{ transition: none/);
});

test('hero release preserves 48 native frames, exact endpoint and master provenance', async () => {
  const manifest = JSON.parse(await readFile(new URL(`assets/${release}.json`, root)));
  assert.equal(manifest.proof, false);
  assert.equal(manifest.resolution_percentage, 100);
  assert.equal(manifest.samples, 128);
  assert.equal(manifest.provenance.master_sha256, '98577604BB25033B5A7229A66A14D12703E6636DF6B064F877DF7EFC6E65CEFA');
  assert.deepEqual(manifest.video, { width: 1440, height: 1920, r_frame_rate: '24/1', duration: '2.000000', nb_frames: '48' });
  assert.equal(manifest.frames.length, 48);
  assert.equal(manifest.frames[0].angle, -12);
  assert.equal(Math.abs(manifest.frames.at(-1).angle), 0);
  assert.equal(manifest.frames.at(-1).light, 1);
  for (const asset of manifest.outputs) {
    const bytes = await readFile(new URL(`assets/${asset.filename}`, root));
    assert.equal(createHash('sha256').update(bytes).digest('hex').toUpperCase(), asset.sha256);
  }
});

async function harness({ reduced = false, saveData = false, denied = false } = {}) {
  let Controller;
  class Element {
    constructor() { this.dataset = {}; }
    querySelector(selector) { return this.nodes[selector]; }
    closest() { return null; }
  }
  const motion = { matches: reduced, addEventListener() {} };
  const document = { hidden: false, addEventListener() {} };
  const events = {};
  const video = {
    dataset: { src: 'native.mp4' }, hidden: true, paused: true, currentTime: 0, plays: 0,
    addEventListener(name, cb) { events[name] = cb; },
    play() { this.plays++; this.paused = false; return denied ? Promise.reject(new Error('denied')) : Promise.resolve(); },
    pause() { this.paused = true; events.pause?.(); },
  };
  const poster = { decode: () => Promise.resolve(), getAttribute: () => 'rest.webp', dataset: { start: 'start.webp' } };
  const context = {
    HTMLElement: Element, AbortController, document, navigator: { connection: { saveData } },
    matchMedia: () => motion,
    IntersectionObserver: class { constructor(cb) { this.callback = cb; } observe() {} disconnect() {} },
    customElements: { get() {}, define(name, cls) { Controller = cls; } },
  };
  vm.runInNewContext(await readFile(new URL('assets/maliev-pimm-hero-reveal.js', root), 'utf8'), context);
  const el = new Controller(); el.nodes = { video, img: poster }; el.connectedCallback();
  return { el, video, events, document, motion };
}

test('plays once, pauses offscreen and never restarts after completion', async () => {
  const { el, video, events } = await harness();
  el.observer.callback([{ isIntersecting: true }]); assert.equal(video.plays, 1);
  events.playing(); assert.equal(video.hidden, false);
  el.observer.callback([{ isIntersecting: false }]); assert.equal(video.paused, true);
  el.observer.callback([{ isIntersecting: true }]); assert.equal(video.plays, 2);
  events.ended(); await Promise.resolve(); assert.equal(video.hidden, true);
  el.sync(); assert.equal(video.plays, 2);
  video.currentTime = 2;
  el.observer.callback([{ isIntersecting: false }]);
  el.observer.callback([{ isIntersecting: true }]);
  el.play(); assert.equal(video.plays, 2); assert.equal(video.currentTime, 2);
});

test('intro markup provides no replay button or native video controls', async () => {
  const source = await readFile(new URL('snippets/pimm-30g-hero-reveal.liquid', root), 'utf8');
  assert.doesNotMatch(source, /<button|data-replay|\bcontrols\b|\bloop\b/);
});

test('reduced motion and data saver never load the video', async () => {
  for (const options of [{ reduced: true }, { saveData: true }]) {
    const { el, video } = await harness(options); el.visible = true; el.sync();
    assert.equal(video.src, undefined); assert.equal(video.plays, 0);
  }
});

test('autoplay rejection leaves the bright still and usable page', async () => {
  const { el, video } = await harness({ denied: true }); el.visible = true; el.sync();
  await Promise.resolve(); await Promise.resolve();
  assert.equal(video.hidden, true); assert.equal(el.finished, true);
});

test('late playback event cannot override a reduced-motion fallback', async () => {
  const { el, video, motion, events } = await harness();
  el.visible = true; el.sync();
  motion.matches = true; el.fallback(); events.playing();
  assert.equal(video.hidden, true); assert.equal(video.paused, true);
});

test('hidden tab pauses the clip without restarting its timeline', async () => {
  const { el, video, document } = await harness();
  el.visible = true; el.sync(); video.currentTime = .8;
  document.hidden = true; el.sync(); assert.equal(video.paused, true);
  document.hidden = false; el.sync(); assert.equal(video.currentTime, .8);
});
