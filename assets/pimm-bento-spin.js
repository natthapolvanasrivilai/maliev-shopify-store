(() => {
  if (customElements.get('pimm-bento-spin')) return;

  // Native, numbered Blender views. The original image remains the failure fallback.
  class PimmBentoSpin extends HTMLElement {
    connectedCallback() {
      if (this.abort) return;
      this.poster = this.querySelector('img');
      this.count = Number(this.dataset.frameCount);
      this.frameTemplate = this.dataset.frameTemplate || this.dataset.frameSource?.replace('r00-f0001', 'r{row}-f{frame}');
      if (!this.poster || !this.frameTemplate?.includes('{frame}') ||
          !Number.isInteger(this.count) || this.count < 2 || this.count > 720) return;
      this.rows = this.dataset.rowCount === undefined ? 1 : Number(this.dataset.rowCount);
      this.defaultRow = this.dataset.defaultRow === undefined ? Math.floor(this.rows / 2) : Number(this.dataset.defaultRow);
      this.rowStep = this.dataset.rowStep === undefined ? 2 : Number(this.dataset.rowStep);
      if (!Number.isInteger(this.rows) || this.rows < 1 || this.rows > 31 ||
          !Number.isInteger(this.defaultRow) || this.defaultRow < 0 || this.defaultRow >= this.rows ||
          !Number.isFinite(this.rowStep) || this.rowStep <= 0 ||
          (this.rows > 1 && !this.frameTemplate.includes('{row}'))) return;
      this.abort = new AbortController();
      const session = this.abort;
      const options = { signal: session.signal };
      this.frame = this.frame ?? 0;
      this.row = this.row ?? this.defaultRow;
      this.visible = false;
      this.cache = new Map();
      this.pending = new Map();
      this.failed = new Set();
      this.cacheLimit = 6;
      this.paintedKey = null;
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
      this.handle.setAttribute('role', this.rows > 1 ? 'group' : 'slider');
      if (this.rows > 1) {
        this.handle.dataset.twoAxis = '';
        if (this.dataset.roleDescription) this.handle.setAttribute('aria-roledescription', this.dataset.roleDescription);
        this.status = document.createElement('span');
        this.status.className = 'pimm-bento-spin__status';
        this.status.setAttribute('role', 'status');
        this.status.setAttribute('aria-live', 'polite');
        this.status.setAttribute('aria-atomic', 'true');
        this.handle.append(this.status);
      } else {
        this.handle.setAttribute('aria-orientation', 'horizontal');
        this.handle.setAttribute('aria-valuemin', '0');
        this.handle.setAttribute('aria-valuemax', '359');
      }
      this.handle.setAttribute('aria-label', this.dataset.label || this.poster.alt);
      if (this.dataset.describedby) this.handle.setAttribute('aria-describedby', this.dataset.describedby);
      this.hint = document.createElement('span');
      this.hint.className = 'pimm-bento-spin__hint';
      this.hint.setAttribute('aria-hidden', 'true');
      this.hint.textContent = '↔ 360° ↕';
      this.updateValue();
      this.append(this.canvas, this.hint, this.handle);
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
    viewKey(frame = this.frame, row = this.row) { return row * this.count + frame; }
    updateValue() {
      const angle = Math.round(this.frame * 360 / this.count) % 360;
      const tilt = (this.row - this.defaultRow) * this.rowStep;
      const value = (this.dataset.valueTemplate || (this.rows > 1 ? '{angle}° / {tilt}°' : '{angle}°'))
        .replace('{angle}', angle).replace('{tilt}', tilt);
      if (this.rows > 1) {
        // A two-axis view is not an ARIA slider. Status reports both coordinates.
        if (this.interacted || !this.status.textContent) this.status.textContent = value;
      } else {
        this.handle.setAttribute('aria-valuenow', String(angle));
        this.handle.setAttribute('aria-valuetext', value);
      }
    }

    sync() {
      if (!this.active()) { this.suspend(); return; }
      if (this.motion.matches || this.connection?.saveData) this.cancelHint(true);
      if (this.interacted) { this.requestFrame(this.frame); return; }
      if (!this.hintDone && this.observer && !this.motion.matches && !this.connection?.saveData) {
        this.hintFrames = [...new Set([0, 1, 2, this.count - 1, this.count - 2].map((frame) => this.viewKey(this.wrap(frame), this.defaultRow)))];
        this.pump();
      }
    }

    requestFrame(frame, row = this.row) {
      this.frame = this.wrap(Math.round(frame));
      this.row = Math.max(0, Math.min(this.rows - 1, Math.round(row)));
      this.updateValue();
      if (!this.active()) return;
      const key = this.viewKey();
      const cached = this.cache.get(key);
      if (cached) this.paint(key, cached);
      else this.paintNearby();
      if (this.failed.has(key)) this.canvas.hidden = true;
      this.pump();
    }

    pump() {
      if (!this.active()) return;
      const warm = this.interacted || (this.hintDone && this.cacheLimit > 6 && !this.motion.matches && !this.connection?.saveData);
      const candidates = warm ? this.nearbyViews() : (this.hintFrames || []);
      for (const frame of candidates) {
        if (this.pending.size >= (this.cacheLimit > 6 && !this.connection?.saveData ? 4 : 2)) break;
        if (this.cache.has(frame) || this.pending.has(frame) || this.failed.has(frame)) continue;
        this.load(frame);
      }
      if (!this.interacted && this.hintFrames?.every((frame) => this.cache.has(frame))) this.startHint();
    }

    nearbyViews() {
      const candidates = [this.viewKey()];
      if (this.connection?.saveData) return candidates;
      const radius = this.cacheLimit > 6 ? 8 : 1;
      for (let distance = 1; distance <= radius; distance++) {
        candidates.push(this.viewKey(this.wrap(this.frame + distance)), this.viewKey(this.wrap(this.frame - distance)));
        if (distance <= 2 && this.cacheLimit > 6) {
          for (const row of [this.row + distance, this.row - distance]) {
            if (row < 0 || row >= this.rows) continue;
            for (let offset = -4; offset <= 4; offset++) candidates.push(this.viewKey(this.wrap(this.frame + offset), row));
          }
        }
      }
      // The working set fits the cache; otherwise eviction would endlessly refetch it.
      return [...new Set(candidates)].slice(0, this.cacheLimit);
    }

    load(frame) {
      const image = new Image();
      const session = this.abort;
      this.pending.set(frame, image);
      image.decoding = 'async';
      const current = () => this.abort === session && this.pending.get(frame) === image && this.active();
      const ready = () => {
        if (!current()) return;
        this.pending.delete(frame);
        // Budget decoded pixels, not compressed bytes. Small web frames can retain
        // a useful two-axis neighborhood without retaining all 840 views.
        const pixels = (image.naturalWidth || this.canvas.width) * (image.naturalHeight || this.canvas.height);
        this.cacheLimit = Math.max(5, Math.min(96, Math.floor(64 * 1024 * 1024 / (pixels * 4))));
        this.cache.set(frame, image);
        while (this.cache.size > this.cacheLimit) this.cache.delete(this.cache.keys().next().value);
        if (frame === this.viewKey() && (this.interacted || this.hintRAF)) this.paint(frame, image);
        else this.paintNearby();
        this.pump();
      };
      const failed = () => {
        if (!current()) return;
        this.pending.delete(frame);
        this.failed.add(frame);
        if (frame === this.viewKey()) this.canvas.hidden = true;
        if (!this.interacted) this.cancelHint(true);
        this.pump();
      };
      image.onload = () => {
        if (!current()) return;
        if (typeof image.decode === 'function') image.decode().then(ready, failed);
        else ready();
      };
      image.onerror = failed;
      image.src = this.frameTemplate
        .replace('{frame}', String(frame % this.count + 1).padStart(4, '0'))
        .replace('{row}', String(Math.floor(frame / this.count)).padStart(2, '0'));
    }

    paintNearby() {
      // During a fast gesture, show the closest already-decoded native view
      // instead of freezing until the exact target arrives. Never approximate keys.
      if (!this.drag?.axis || this.cache.has(this.viewKey())) return;
      let nearest, score = Infinity;
      for (const [key, image] of this.cache) {
        const rowDistance = Math.abs(Math.floor(key / this.count) - this.row);
        const distance = Math.abs(key % this.count - this.frame);
        const yawDistance = Math.min(distance, this.count - distance);
        if (rowDistance > 1 || yawDistance > 8) continue;
        const candidate = yawDistance + rowDistance * 4;
        if (candidate < score) { score = candidate; nearest = [key, image]; }
      }
      if (nearest) this.paint(...nearest, true);
    }

    paint(frame, image, nearby = false) {
      if (!this.active() || (frame !== this.viewKey() && !(nearby && this.drag?.axis))) return;
      if (this.paintedKey === frame && !this.canvas.hidden) return;
      try {
        this.context.drawImage(image, 0, 0, this.canvas.width, this.canvas.height);
        this.canvas.hidden = false;
        this.paintedKey = frame;
        this.dataset.spinFrame = String(frame % this.count + 1);
        if (this.rows > 1) this.dataset.spinRow = String(Math.floor(frame / this.count));
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
        this.row = this.defaultRow;
        this.updateValue();
        this.canvas.hidden = true;
      }
    }

    interact() {
      this.interacted = true;
      this.hintDone = true;
      if (this.hint) this.hint.hidden = true;
      this.cancelHint(false);
    }

    pointerDown(event) {
      if (!this.active() || event.isPrimary === false || event.button !== 0 || this.drag) return;
      this.interact();
      this.drag = { id: event.pointerId, x: event.clientX, y: event.clientY, frame: this.frame, row: this.row, axis: null };
      // One-axis mode leaves vertical scrolling native; two-axis captures only this hit area.
    }

    pointerMove(event) {
      const drag = this.drag;
      if (!drag || drag.id !== event.pointerId) return;
      const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
      if (!drag.axis) {
        if (Math.max(Math.abs(dx), Math.abs(dy)) < 7) return;
        if (this.rows === 1 && Math.abs(dy) > Math.abs(dx)) { this.drag = null; return; }
        drag.axis = this.rows > 1 ? 'xy' : 'x';
        this.handle.setPointerCapture(event.pointerId);
        this.handle.dataset.dragging = '';
        this.handle.focus({ preventScroll: true });
        drag.bounds = this.handle.getBoundingClientRect();
      }
      const bounds = drag.bounds;
      const width = Math.max(1, bounds.width);
      // Yaw and pitch use different camera ordering; map each axis independently.
      this.nextFrame = drag.frame - dx / width * this.count;
      this.nextRow = this.rows > 1 ? drag.row - dy / Math.max(1, bounds.height) * (this.rows - 1) : drag.row;
      if (!this.dragRAF) this.dragRAF = requestAnimationFrame(() => {
        this.dragRAF = null;
        this.requestFrame(this.nextFrame, this.nextRow);
      });
    }

    pointerEnd(event) {
      if (!this.drag || this.drag.id !== event.pointerId) return;
      const wasDragging = Boolean(this.drag.axis);
      this.drag = null;
      delete this.handle.dataset.dragging;
      if (this.dragRAF) {
        cancelAnimationFrame(this.dragRAF); this.dragRAF = null;
        if (wasDragging && event.type === 'pointerup') this.requestFrame(this.nextFrame, this.nextRow);
      }
      if (this.handle.hasPointerCapture(event.pointerId)) this.handle.releasePointerCapture(event.pointerId);
      if (wasDragging && event.type === 'pointerup') this.requestFrame(this.frame, this.row);
    }

    keyDown(event) {
      if (!this.active() || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const delta = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
      const rowDelta = this.rows > 1 ? { ArrowUp: 1, ArrowDown: -1 }[event.key] : undefined;
      if (delta === undefined && rowDelta === undefined && event.key !== 'Home') return;
      event.preventDefault();
      this.interact();
      this.requestFrame(event.key === 'Home' ? 0 : this.frame + (delta || 0),
        event.key === 'Home' ? this.defaultRow : this.row + (rowDelta || 0));
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
      this.hint?.remove();
      this.handle?.remove();
    }
  }

  customElements.define('pimm-bento-spin', PimmBentoSpin);
})();
