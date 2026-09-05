(() => {
  if (customElements.get('pimm-machine-gallery')) return;

  class PimmMachineGallery extends HTMLElement {
    connectedCallback() {
      this.abort = new AbortController();
      const options = { signal: this.abort.signal };
      this.items = [...this.querySelectorAll('[data-gallery-item]')];
      if (!this.items.length) return;
      this.dialog = this.querySelector('dialog');
      this.stage = this.querySelector('[data-gallery-stage]');
      this.motion = matchMedia('(prefers-reduced-motion: reduce)');
      this.connection = navigator.connection;
      this.activeIndex = 0;
      this.previews = this.items.flatMap(item => {
        const video = item.querySelector('[data-gallery-preview]');
        if (!video) return [];
        const record = { item, video, visible: false, failed: false };
        video.muted = true;
        video.addEventListener('loadedmetadata', () => this.seekPreview(record, true), options);
        video.addEventListener('timeupdate', () => this.seekPreview(record), options);
        video.addEventListener('playing', () => {
          if (this.canPreview(record)) video.hidden = false;
          else { video.pause(); video.hidden = true; }
        }, options);
        video.addEventListener('error', () => {
          record.failed = true;
          video.hidden = true;
          this.syncPreviews();
        }, options);
        return [record];
      });

      this.observer = new IntersectionObserver(entries => {
        for (const entry of entries) {
          const record = this.previews.find(preview => preview.video.parentElement === entry.target);
          if (record) record.visible = entry.isIntersecting && entry.intersectionRatio >= .25;
        }
        this.syncPreviews();
      }, { threshold: [0, .25] });
      this.previews.forEach(record => this.observer.observe(record.video.parentElement));
      document.addEventListener('visibilitychange', () => this.syncPreviews(), options);
      this.motion.addEventListener('change', () => this.syncPreviews(), options);
      this.connection?.addEventListener('change', () => this.syncPreviews(), options);
      if (typeof this.dialog.showModal === 'function') {
        this.items.forEach((item, index) => {
          const link = item.querySelector('[data-gallery-open]');
          link.setAttribute('aria-haspopup', 'dialog');
          link.addEventListener('click', event => {
            if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            this.open(index, link);
          }, options);
        });
        const browse = this.querySelector('[data-gallery-browse]');
        browse.hidden = false;
        browse.addEventListener('click', () => this.open(0, browse), options);
      }
      this.querySelector('[data-gallery-close]').addEventListener('click', () => this.dialog.close(), options);
      this.querySelector('[data-gallery-previous]').addEventListener('click', () => this.show(this.activeIndex - 1), options);
      this.querySelector('[data-gallery-next]').addEventListener('click', () => this.show(this.activeIndex + 1), options);
      this.dialog.addEventListener('close', () => {
        this.clearStage();
        this.syncPreviews();
        this.returnFocus?.focus({ preventScroll: true });
      }, options);
      this.dialog.addEventListener('click', event => {
        if (event.target !== this.dialog) return;
        const rect = this.dialog.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) this.dialog.close();
      }, options);
      this.dialog.addEventListener('keydown', event => {
        if (event.key === 'Tab') {
          const stops = [...this.dialog.querySelectorAll('button:not([disabled]), a[href], video[controls], iframe')];
          const first = stops[0];
          const last = stops.at(-1);
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault(); last?.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault(); first?.focus();
          }
          return;
        }
        if (['VIDEO', 'IFRAME', 'INPUT', 'TEXTAREA'].includes(event.target.tagName)) return;
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
          event.preventDefault();
          this.show(this.activeIndex + (event.key === 'ArrowRight' ? 1 : -1));
        }
      }, options);
      this.syncPreviews();
    }

    canPreview(record) {
      return this.isConnected && record.visible && !record.failed && !document.hidden &&
        !this.motion.matches && !this.connection?.saveData && !this.dialog.open;
    }

    seekPreview(record, initial = false) {
      const { video, item } = record;
      if (!Number.isFinite(video.duration) || video.duration <= 0) return;
      const start = Math.min(Math.max(0, Number(item.dataset.previewStart) || 0), Math.max(0, video.duration - .25));
      const length = Math.min(15, Math.max(3, Number(item.dataset.previewLength) || 6));
      const end = Math.min(video.duration - .04, start + length);
      if (initial || video.currentTime < start || video.currentTime >= end) video.currentTime = start;
    }

    syncPreviews() {
      for (const record of this.previews) {
        const { video } = record;
        if (!this.canPreview(record)) {
          video.pause();
          if (this.motion.matches || this.connection?.saveData) video.hidden = true;
          continue;
        }
        if (!video.getAttribute('src')) video.src = video.dataset.src;
        if (record.pending || !video.paused) continue;
        record.pending = true;
        video.play().catch(error => {
          record.failed = error.name !== 'AbortError';
          video.hidden = true;
        }).finally(() => {
          record.pending = false;
          if (!record.failed && video.paused && this.canPreview(record)) this.syncPreviews();
        });
      }
    }

    open(index, trigger) {
      this.returnFocus = trigger;
      this.dialog.showModal();
      this.syncPreviews();
      this.show(index);
    }

    clearStage() {
      this.stage.querySelector('video')?.pause();
      this.stage.replaceChildren();
    }

    show(index) {
      this.activeIndex = (index + this.items.length) % this.items.length;
      const item = this.items[this.activeIndex];
      const link = item.querySelector('[data-gallery-open]');
      const title = item.dataset.title;
      this.clearStage();
      this.querySelector('[data-gallery-title]').textContent = title;
      this.querySelector('[data-gallery-position]').textContent = `${this.activeIndex + 1} / ${this.items.length}`;
      this.querySelector('[data-gallery-source]').href = link.href;
      this.querySelector('[data-gallery-previous]').disabled = this.items.length < 2;
      this.querySelector('[data-gallery-next]').disabled = this.items.length < 2;
      let media;
      if (item.dataset.kind === 'image') {
        media = new Image();
        media.alt = title;
        media.src = link.href;
      } else if (/^[\w-]{11}$/.test(item.dataset.videoId)) {
        media = document.createElement('iframe');
        const url = new URL(`https://www.youtube-nocookie.com/embed/${item.dataset.videoId}`);
        url.search = new URLSearchParams({ autoplay: '1', playsinline: '1', rel: '0', origin: location.origin });
        media.src = url.href;
        media.title = title;
        media.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
        media.allowFullscreen = true;
        media.referrerPolicy = 'strict-origin-when-cross-origin';
      } else {
        media = document.createElement('video');
        media.src = link.href;
        media.controls = true;
        media.playsInline = true;
        media.setAttribute('aria-label', title);
        media.autoplay = true;
      }
      this.stage.append(media);
    }

    disconnectedCallback() {
      this.abort?.abort();
      this.observer?.disconnect();
      this.previews?.forEach(({ video }) => { video.pause(); video.removeAttribute('src'); video.load(); });
      if (this.dialog?.open) this.dialog.close();
      if (this.stage) this.clearStage();
    }
  }
  customElements.define('pimm-machine-gallery', PimmMachineGallery);
})();
