(() => {
  if (customElements.get('pimm-hero-reveal')) return;
  class PimmHeroReveal extends HTMLElement {
    connectedCallback() {
      if (this.abort) return;
      this.abort = new AbortController();
      const options = { signal: this.abort.signal };
      this.video = this.querySelector('video');
      this.poster = this.querySelector('img');
      this.motion = matchMedia('(prefers-reduced-motion: reduce)');
      this.started = false;
      this.finished = false;
      this.visible = false;
      this.restSource ||= this.poster.getAttribute('src');
      if (!this.motion.matches && !navigator.connection?.saveData) this.poster.src = this.poster.dataset.start;
      this.video.addEventListener('playing', () => {
        if (this.finished || this.motion.matches) { this.fallback(); return; }
        this.video.hidden = false;
        this.dataset.playing = 'true';
        if (!this.headlineSettled) {
          this.headlineSettled = true;
          this.closest('[data-pimm-hero]')?.classList.add('pimm-hero-arrived');
        }
      }, options);
      this.video.addEventListener('pause', () => {
        this.dataset.playing = 'false';
      }, options);
      this.video.addEventListener('ended', () => {
        this.finished = true;
        this.dataset.playing = 'false';
        this.poster.src = this.restSource;
        // The still is the exact final native frame. Keep video until decoding finishes.
        this.poster.decode().then(() => {
          if (this.finished) this.video.hidden = true;
        }).catch(() => {});
      }, options);
      this.video.addEventListener('error', () => this.fallback(), options);
      this.motion.addEventListener('change', () => {
        if (this.motion.matches) this.fallback();
      }, options);
      document.addEventListener('visibilitychange', () => this.sync(), options);
      if (typeof IntersectionObserver !== 'function') { this.fallback(); return; }
      this.observer = new IntersectionObserver(([entry]) => {
        this.visible = entry.isIntersecting;
        this.sync();
      }, { threshold: .2 });
      this.observer.observe(this);
    }
    sync() {
      if (this.motion.matches || navigator.connection?.saveData) return;
      if (!this.visible || document.hidden) { this.video.pause(); return; }
      if (this.finished) return;
      this.play();
    }
    play() {
      if (this.finished) return;
      if (!this.started) {
        this.started = true;
        this.video.src = this.video.dataset.src;
      }
      this.video.play().catch(() => this.fallback());
    }
    fallback() {
      this.finished = true;
      this.video.pause();
      this.video.hidden = true;
      this.poster.src = this.restSource;
      this.dataset.playing = 'false';
    }
    disconnectedCallback() {
      this.video?.pause();
      this.observer?.disconnect();
      this.abort?.abort();
      this.abort = null;
    }
  }
  customElements.define('pimm-hero-reveal', PimmHeroReveal);
})();
