(() => {
  if (customElements.get('pimm-cinematic-hero')) return;
  customElements.define('pimm-cinematic-hero', class extends HTMLElement {
    connectedCallback() {
      if (this.abort) return;
      this.abort = new AbortController();
      const options = { signal: this.abort.signal };
      this.videos = [...this.querySelectorAll('video')];
      this.motion = matchMedia('(prefers-reduced-motion: reduce)');
      // Select once per connection; resizing must not restart a playing shot.
      // The portrait render is composed for phone widths. Near-square tablets
      // use the landscape source so cover does not remove its top and bottom.
      this.portrait = matchMedia('(max-width: 749px)').matches;
      this.index = 0;
      this.visible = false;
      this.failed = false;
      this.alphaChecked = false;
      delete this.dataset.started;
      this.videos.forEach(video => video.classList.remove('is-current'));
      this.videos.forEach((video, index) => {
        video.addEventListener('playing', () => {
          if (!this.allowed() || index !== this.index) { video.pause(); return; }
          // Some decoders play VP9 without alpha. Keep the transparent still there.
          if (!this.alphaChecked && typeof document.createElement === 'function') {
            this.alphaChecked = true;
            try {
              const canvas = document.createElement('canvas');
              canvas.width = canvas.height = 1;
              const context = canvas.getContext('2d', {willReadFrequently:true});
              context.drawImage(video, 0, 0, 1, 1, 0, 0, 1, 1);
              if (context.getImageData(0, 0, 1, 1).data[3] > 0) { this.failed = true; this.sync(); return; }
            } catch { this.failed = true; this.sync(); return; }
          }
          this.videos.forEach(item => item.classList.toggle('is-current', item === video));
          this.dataset.started = 'true';
          this.closest('[data-pimm-hero]').dataset.cinematicPlaying = 'true';
          this.prepare((index + 1) % this.videos.length);
        }, options);
        video.addEventListener('ended', () => {
          if (index !== this.index) return;
          this.index = (index + 1) % this.videos.length;
          this.videos[this.index].currentTime = 0;
          this.sync();
        }, options);
        video.addEventListener('error', () => { this.failed = true; this.sync(); }, options);
      });
      this.motion.addEventListener('change', () => this.sync(), options);
      document.addEventListener('visibilitychange', () => this.sync(), options);
      if (!('IntersectionObserver' in window)) return;
      this.observer = new IntersectionObserver(([entry]) => { this.visible = entry.isIntersecting; this.sync(); }, {threshold:.15});
      this.observer.observe(this);
    }
    allowed() { return !this.failed && !this.motion.matches && !navigator.connection?.saveData && this.visible && !document.hidden; }
    prepare(index) {
      const video = this.videos[index];
      if (!video.getAttribute('src')) {
        video.src = (this.portrait ? video.dataset.srcPortrait : video.dataset.srcLandscape) || video.dataset.src;
        video.load();
      }
      return video;
    }
    sync() {
      if (!this.abort) return;
      if (!this.allowed()) {
        this.videos.forEach(video => video.pause());
        this.closest('[data-pimm-hero]').dataset.cinematicPlaying = 'false';
        if (this.failed || this.motion.matches || navigator.connection?.saveData) {
          delete this.dataset.started;
          this.videos.forEach(video => video.classList.remove('is-current'));
        }
        return;
      }
      this.prepare(this.index).play().catch(() => { this.failed = true; this.sync(); });
    }
    disconnectedCallback() {
      this.videos?.forEach(video => { video.pause(); video.removeAttribute('src'); video.load(); });
      this.observer?.disconnect();
      this.abort?.abort();
      this.abort = null;
    }
  });
})();
