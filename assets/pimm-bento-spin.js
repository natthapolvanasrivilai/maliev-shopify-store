(() => {
  if (customElements.get('pimm-bento-spin')) return;

  // Native, numbered Blender views. The original image remains the failure fallback.
  class PimmBentoSpin extends HTMLElement {
    connectedCallback() {
      if (this.abort) return;
      this.poster = this.querySelector('img');
      this.count = Number(this.dataset.frameCount);
      if (!this.poster || !this.dataset.frameTemplate?.includes('{frame}') ||
          !Number.isInteger(this.count) || this.count < 2 || this.count > 720) return;
      this.abort = new AbortController();
      const session = this.abort;
      const options = { signal: session.signal };
      this.frame = this.frame ?? 0;
      this.visible = false;
      this.cache = new Map();
      this.pending = new Map();
      this.failed = new Set();
      this.motion = matchMedia('(prefers-reduced-motion: reduce)');
      this.connection = navigator.connection;
      this.canvas = document.createElement('canvas');
      const nativeSize = (attribute, natural, fallback) => {
        const declared = Number(this.poster.getAttribute(attribute));
        if (Number.isFinite(declared) && declared > 0) return Math.round(declared);
        if (Number.isFinite(natural) && natural > 0) return Math.round(natural);
        return fallback;
      };
      this.canvas.width = nativeSize('width', this.poster.naturalWidth, 2400);
      this.canvas.height = nativeSize('height', this.poster.naturalHeight, 1200);
      this.canvas.hidden = true;
      this.canvas.setAttribute('aria-hidden', 'true');
      this.context = this.canvas.getContext('2d', { alpha: false });
      if (!this.context) { this.abort = null; return; }
      this.handle = document.createElement('div');
      this.handle.className = 'pimm-bento-spin__handle';
      this.handle.tabIndex = 0;
      this.handle.setAttribute('role', 'slider');
      this.handle.setAttribute('aria-orientation', 'horizontal');
      this.handle.setAttribute('aria-valuemin', '0');
      this.handle.setAttribute('aria-valuemax', '359');
      this.handle.setAttribute('aria-label', this.dataset.label || this.poster.alt);
      if (this.dataset.describedby) this.handle.setAttribute('aria-describedby', this.dataset.describedby);
      this.updateValue();
      this.append(this.canvas, this.handle);
      this.handle.addEventListener('pointerdown', (event) => this.pointerDown(event), options);
      this.handle.addEventListener('pointermove', (event) => this.pointerMove(event), { ...options, passive: true });
      this.handle.addEventListener('pointerleave', (event) => {
        if (!this.drag?.axis) this.pointerEnd(event);
      }, options);
      for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) {
        this.handle.addEventListener(name, (event) => this.pointerEnd(event), options);
      }
      this.handle.addEventListener('keydown', (event) => this.keyDown(event), options);
      this.handle.addEventListener('focus', () => this.interact(), options);
      this.handle.addEventListener('dragstart', (event) => event.preventDefault(), options);
      const sync = () => this.sync();
      this.motion.addEventListener('change', sync, options);
      this.connection?.addEventListener?.('change', sync, options);
      document.addEventListener('visibilitychange', sync, options);
      if (typeof IntersectionObserver === 'function') {
        this.observer = new IntersectionObserver((entries) => {
          if (this.abort !== session) return;
          this.visible = entries.some((entry) => entry.target === this && entry.isIntersecting);
          this.sync();
        }, { threshold: 0 });
        this.observer.observe(this);
      } else {
        // Explicit interaction works without observation, but never auto-hints.
        this.visible = true;
      }
    }

    active() { return Boolean(this.abort && this.isConnected && this.visible && !document.hidden); }
    wrap(frame) { return ((frame % this.count) + this.count) % this.count; }
    updateValue() {
      const angle = Math.round(this.frame * 360 / this.count) % 360;
      this.handle.setAttribute('aria-valuenow', String(angle));
      this.handle.setAttribute('aria-valuetext', (this.dataset.valueTemplate || '{angle}°').replace('{angle}', angle));
    }

    sync() {
      if (!this.active()) { this.suspend(); return; }
      if (this.motion.matches || this.connection?.saveData) this.cancelHint(true);
      if (this.interacted) { this.requestFrame(this.frame); return; }
      if (!this.hintDone && this.observer && !this.motion.matches && !this.connection?.saveData) {
        this.hintFrames = [...new Set([0, 1, 2, this.count - 1, this.count - 2].map((frame) => this.wrap(frame)))];
        this.pump();
      }
    }

    requestFrame(frame) {
      this.frame = this.wrap(Math.round(frame));
      this.updateValue();
      if (!this.active()) return;
      const cached = this.cache.get(this.frame);
      if (cached) this.paint(this.frame, cached);
      if (this.failed.has(this.frame)) this.canvas.hidden = true;
      this.pump();
    }

    pump() {
      if (!this.active()) return;
      const candidates = this.interacted ? [this.frame, ...(!this.connection?.saveData ?
        [this.wrap(this.frame + 1), this.wrap(this.frame - 1)] : [])] : (this.hintFrames || []);
      for (const frame of candidates) {
        if (this.pending.size >= 2) break;
        if (this.cache.has(frame) || this.pending.has(frame) || this.failed.has(frame)) continue;
        this.load(frame);
      }
      if (!this.interacted && this.hintFrames?.every((frame) => this.cache.has(frame))) this.startHint();
    }

    load(frame) {
      const image = new Image();
      const session = this.abort;
      this.pending.set(frame, image);
      image.decoding = 'async';
      const current = () => this.abort === session && this.pending.get(frame) === image && this.active();
      image.onload = () => {
        if (!current()) return;
        this.pending.delete(frame);
        this.cache.set(frame, image);
        // Six decoded frames cap desktop memory near 66 MiB at 2400 × 1200.
        while (this.cache.size > 6) this.cache.delete(this.cache.keys().next().value);
        if (frame === this.frame && (this.interacted || this.hintRAF)) this.paint(frame, image);
        this.pump();
      };
      image.onerror = () => {
        if (!current()) return;
        this.pending.delete(frame);
        this.failed.add(frame);
        if (frame === this.frame) this.canvas.hidden = true;
        if (!this.interacted) this.cancelHint(true);
        this.pump();
      };
      image.src = this.dataset.frameTemplate.replace('{frame}', String(frame + 1).padStart(4, '0'));
    }

    paint(frame, image) {
      if (!this.active() || frame !== this.frame) return;
      try {
        this.context.drawImage(image, 0, 0, this.canvas.width, this.canvas.height);
        this.canvas.hidden = false;
        this.dataset.spinFrame = String(frame + 1);
        this.cache.delete(frame);
        this.cache.set(frame, image);
      } catch { this.canvas.hidden = true; }
    }

    startHint() {
      if (this.hintRAF || this.hintDone || this.interacted || !this.active()) return;
      this.hintDone = true;
      let start;
      const tick = (time) => {
        if (!this.active() || this.interacted || this.motion.matches || this.connection?.saveData) {
          this.cancelHint(true); return;
        }
        start ??= time;
        const progress = Math.min(1, (time - start) / 2400);
        // One native-view nudge in both directions, returning precisely to the still.
        const degrees = 6 * Math.sin(progress * 2 * Math.PI) * Math.sin(progress * Math.PI);
        this.requestFrame(degrees / 360 * this.count);
        if (progress < 1) this.hintRAF = requestAnimationFrame(tick);
        else { this.hintRAF = null; this.requestFrame(0); this.hintFrames = null; }
      };
      this.hintRAF = requestAnimationFrame(tick);
    }

    cancelHint(restore) {
      if (this.hintRAF) cancelAnimationFrame(this.hintRAF);
      this.hintRAF = null;
      this.hintFrames = null;
      if (restore && !this.interacted) {
        this.frame = 0;
        this.updateValue();
        this.canvas.hidden = true;
      }
    }

    interact() {
      this.interacted = true;
      this.hintDone = true;
      this.cancelHint(false);
    }

    pointerDown(event) {
      if (!this.active() || event.isPrimary === false || event.button !== 0 || this.drag) return;
      this.interact();
      this.drag = { id: event.pointerId, x: event.clientX, y: event.clientY, frame: this.frame, axis: null };
      // Capture is deferred until horizontal intent, leaving touch scrolling native.
    }

    pointerMove(event) {
      const drag = this.drag;
      if (!drag || drag.id !== event.pointerId) return;
      const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
      if (!drag.axis) {
        if (Math.max(Math.abs(dx), Math.abs(dy)) < 7) return;
        if (Math.abs(dy) > Math.abs(dx)) { this.drag = null; return; }
        drag.axis = 'x';
        this.handle.setPointerCapture(event.pointerId);
        this.handle.dataset.dragging = '';
        this.handle.focus({ preventScroll: true });
      }
      const width = Math.max(1, this.handle.getBoundingClientRect().width);
      this.nextFrame = drag.frame + dx / width * this.count;
      if (!this.dragRAF) this.dragRAF = requestAnimationFrame(() => {
        this.dragRAF = null;
        this.requestFrame(this.nextFrame);
      });
    }

    pointerEnd(event) {
      if (!this.drag || this.drag.id !== event.pointerId) return;
      const wasHorizontal = this.drag.axis === 'x';
      this.drag = null;
      delete this.handle.dataset.dragging;
      if (this.dragRAF) {
        cancelAnimationFrame(this.dragRAF); this.dragRAF = null;
        if (wasHorizontal && event.type === 'pointerup') this.requestFrame(this.nextFrame);
      }
      if (this.handle.hasPointerCapture(event.pointerId)) this.handle.releasePointerCapture(event.pointerId);
    }

    keyDown(event) {
      if (!this.active() || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const delta = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
      if (delta === undefined && event.key !== 'Home') return;
      event.preventDefault();
      this.interact();
      this.requestFrame(event.key === 'Home' ? 0 : this.frame + delta);
    }

    suspend() {
      this.cancelHint(true);
      if (this.dragRAF) cancelAnimationFrame(this.dragRAF);
      this.dragRAF = null;
      if (this.drag) this.pointerEnd({ pointerId: this.drag.id, type: 'pointercancel' });
      for (const image of this.pending.values()) {
        image.onload = null; image.onerror = null; image.src = '';
      }
      this.pending.clear();
      this.cache.clear();
    }

    disconnectedCallback() {
      if (!this.abort) return;
      this.visible = false;
      this.suspend();
      this.observer?.disconnect();
      this.abort?.abort();
      this.abort = null;
      this.canvas?.remove();
      this.handle?.remove();
    }
  }

  customElements.define('pimm-bento-spin', PimmBentoSpin);
})();
