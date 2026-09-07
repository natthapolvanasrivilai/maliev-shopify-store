(() => {
  if (customElements.get('pimm-demo-invitation')) return;

  class PimmDemoInvitation extends HTMLElement {
    connectedCallback() {
      if (this.abort) return;
      this.abort = new AbortController();
      this.animations = new Set();
      this.motion = matchMedia('(prefers-reduced-motion: reduce)');
      const options = { signal: this.abort.signal };
      this.addEventListener('focusin', () => { this.entered = true; this.stop(); }, options);
      this.motion.addEventListener('change', () => this.stop(), options);
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) this.stop();
        else if (this.visible) this.enter();
      }, options);
      if (typeof IntersectionObserver !== 'function') return;
      this.observer = new IntersectionObserver(entries => {
        this.visible = entries.some(entry => entry.isIntersecting);
        if (this.visible) this.enter();
        else this.stop();
      }, { threshold: .25 });
      this.observer.observe(this);
    }

    enter() {
      if (this.entered || document.hidden) return;
      this.entered = true;
      if (this.motion.matches) return;
      const moments = [
        ['h2', [{ clipPath: 'inset(0 0 88% 0)', transform: 'translateY(24px)' }, { clipPath: 'inset(0 0 0% 0)', transform: 'translateY(0)' }], 0, 950],
        ['.pimm-machine__purchase-copy > p', [{ opacity: .25, transform: 'translateY(12px)' }, { opacity: 1, transform: 'translateY(0)' }], 120, 650],
        ['.pimm-machine__purchase-action', [{ opacity: .3, transform: 'translateY(20px)' }, { opacity: 1, transform: 'translateY(0)' }], 220, 750],
      ];
      for (const [selector, frames, delay, duration] of moments) {
        const node = this.querySelector(selector);
        if (!node?.animate) continue;
        const animation = node.animate(frames, { duration, delay, easing: 'cubic-bezier(.16, 1, .3, 1)' });
        this.animations.add(animation);
        animation.finished.catch(() => {}).finally(() => this.animations.delete(animation));
      }
    }

    stop() {
      for (const animation of this.animations) animation.cancel();
      this.animations.clear();
    }

    disconnectedCallback() {
      this.stop();
      this.observer?.disconnect();
      this.abort?.abort();
      this.abort = null;
    }
  }

  customElements.define('pimm-demo-invitation', PimmDemoInvitation);
})();
