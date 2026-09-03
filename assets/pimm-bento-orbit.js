(() => {
  if (customElements.get('pimm-bento-orbit')) return;

  // A native Blender camera orbit enhances an always-present, accessible still.
  // Native video decoding runs only in view; the still is never hidden or replaced.
  class PimmBentoOrbit extends HTMLElement {
    connectedCallback() {
      if (this.abort) return;
      this.poster = this.querySelector('img');
      if (!this.poster || !this.dataset.orbitSrc || typeof matchMedia !== 'function' ||
          typeof IntersectionObserver !== 'function') return;
      this.abort = new AbortController();
      const session = this.abort;
      const options = { signal: this.abort.signal };
      this.motion = matchMedia('(prefers-reduced-motion: reduce)');
      this.connection = navigator.connection;
      this.visible = false;
      this.failed = false;
      const sync = () => this.sync();
      this.motion.addEventListener('change', sync, options);
      this.connection?.addEventListener?.('change', sync, options);
      document.addEventListener('visibilitychange', sync, options);
      this.observer = new IntersectionObserver((entries) => {
        if (this.abort !== session) return;
        this.visible = entries.some((entry) => entry.target === this && entry.isIntersecting);
        this.sync();
      }, { threshold: 0 });
      this.observer.observe(this);
    }

    shouldAnimate() {
      return Boolean(this.abort && this.isConnected && this.visible && !this.failed &&
        !this.motion.matches && !this.connection?.saveData && !document.hidden);
    }

    sync() {
      if (!this.shouldAnimate()) { this.stop(); return; }
      if (this.orbit) return;

      const orbit = document.createElement('video');
      this.orbit = orbit;
      orbit.width = this.poster.width;
      orbit.height = this.poster.height;
      orbit.muted = true;
      orbit.defaultMuted = true;
      orbit.autoplay = true;
      orbit.loop = true;
      orbit.playsInline = true;
      orbit.controls = false;
      orbit.disablePictureInPicture = true;
      orbit.preload = 'none';
      orbit.hidden = true;
      orbit.tabIndex = -1;
      orbit.setAttribute('muted', '');
      orbit.setAttribute('playsinline', '');
      orbit.setAttribute('aria-hidden', 'true');
      orbit.dataset.orbitVideo = '';
      const isCurrent = () => this.orbit === orbit && this.shouldAnimate();
      const fail = () => {
        if (this.orbit !== orbit) return;
        this.failed = true;
        this.stop();
      };
      orbit.onerror = fail;
      orbit.onplaying = () => {
        if (!isCurrent()) return;
        orbit.hidden = false;
      };
      const showStill = () => { orbit.hidden = true; };
      orbit.onwaiting = showStill;
      orbit.onpause = showStill;
      // Only the playing event exposes decoded frames; buffering/rejection leaves the still.
      this.append(orbit);
      try {
        orbit.src = this.dataset.orbitSrc;
        const playback = orbit.play();
        playback?.catch(fail);
      } catch { fail(); }
    }

    stop() {
      const orbit = this.orbit;
      this.orbit = null;
      if (!orbit) return;
      orbit.onplaying = null;
      orbit.onerror = null;
      orbit.onwaiting = null;
      orbit.onpause = null;
      orbit.hidden = true;
      orbit.pause();
      orbit.remove();
      orbit.removeAttribute('src');
      orbit.load();
    }

    disconnectedCallback() {
      this.visible = false;
      this.observer?.disconnect();
      this.abort?.abort();
      this.abort = null;
      this.stop();
    }
  }

  customElements.define('pimm-bento-orbit', PimmBentoOrbit);
})();
