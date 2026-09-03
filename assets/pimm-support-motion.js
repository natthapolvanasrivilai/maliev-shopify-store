(() => {
  if (customElements.get('pimm-support-motion')) return;
  class PimmSupportMotion extends HTMLElement {
    connectedCallback() {
      if (this.abort) return;
      this.abort = new AbortController();
      this.motion = matchMedia('(prefers-reduced-motion: reduce)');
      this.animations = new Set();
      const options = { signal: this.abort.signal };
      this.items = [...this.querySelectorAll('li')];
      for (const item of this.items) item.addEventListener('pointerenter', () => this.play(item), options);
      this.motion.addEventListener('change', () => this.stop(), options);
      document.addEventListener('visibilitychange', () => { if (document.hidden) this.stop(); }, options);
      if (typeof IntersectionObserver === 'function') {
        this.observer = new IntersectionObserver(entries => {
          this.visible = entries.some(entry => entry.isIntersecting);
          if (!this.visible) { this.stop(); return; }
          if (this.entered) return;
          this.entered = true;
          this.items.forEach((item, index) => this.play(item, index * 140));
        }, { threshold: .3 });
        this.observer.observe(this);
      } else this.visible = true;
    }
    play(item, delay = 0) {
      if (!this.visible || document.hidden || this.motion.matches) return;
      const part = item.querySelector('[data-support-motion]');
      if (!part?.animate) return;
      for (const animation of part.getAnimations()) animation.cancel();
      const poses = {
        book: [{ transform: 'perspective(80px) rotateY(-78deg)', opacity: .3 }, { transform: 'perspective(80px) rotateY(0deg)', opacity: 1 }],
        parts: [{ transform: 'translateY(-7px)', opacity: .3 }, { transform: 'translateY(0)', opacity: 1 }],
        team: [{ transform: 'translate(4px, 4px) scale(.7)', opacity: .3 }, { transform: 'translate(0, 0) scale(1)', opacity: 1 }],
      };
      const animation = part.animate(poses[part.dataset.supportMotion], { duration: delay ? 750 : 450, delay, easing: 'cubic-bezier(.16, 1, .3, 1)' });
      this.animations.add(animation);
      animation.finished.catch(() => {}).finally(() => this.animations.delete(animation));
    }
    stop() { for (const animation of this.animations) animation.cancel(); this.animations.clear(); }
    disconnectedCallback() { this.stop(); this.observer?.disconnect(); this.abort?.abort(); this.abort = null; }
  }
  customElements.define('pimm-support-motion', PimmSupportMotion);
})();
