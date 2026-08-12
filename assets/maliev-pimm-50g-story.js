(() => {
  const init = (story) => {
    if (story.dataset.ready === 'true') return;
    story.dataset.ready = 'true';
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const chapters = [...story.querySelectorAll('[data-pimm50-chapter]')];
    const observer = new IntersectionObserver((entries) => entries.forEach((entry) => {
      entry.target.classList.toggle('is-active', entry.isIntersecting && entry.intersectionRatio > .55);
    }), { threshold: [.55] });
    chapters.forEach((chapter) => observer.observe(chapter));

    const video = story.querySelector('.pimm50-story__reveal-video');
    if (video) {
      if (reduced) video.pause();
      else video.addEventListener('ended', () => { video.pause(); video.classList.add('is-finished'); }, { once: true });
    }

    const rotator = story.querySelector('[data-pimm50-rotator]');
    if (!rotator) return;
    let origin = 0;
    let delta = 0;
    let dragging = false;
    const paint = () => {
      const clamped = Math.max(-90, Math.min(90, delta));
      rotator.style.setProperty('--pimm50-drag-x', `${clamped * .18}px`);
      rotator.style.setProperty('--pimm50-drag-rotate', `${clamped * .1}deg`);
    };
    rotator.addEventListener('pointerdown', (event) => { dragging = true; origin = event.clientX - delta; rotator.setPointerCapture(event.pointerId); rotator.classList.add('is-dragging'); });
    rotator.addEventListener('pointermove', (event) => { if (!dragging) return; delta = event.clientX - origin; paint(); });
    const release = () => { dragging = false; rotator.classList.remove('is-dragging'); };
    rotator.addEventListener('pointerup', release); rotator.addEventListener('pointercancel', release);
    rotator.addEventListener('keydown', (event) => { if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return; event.preventDefault(); delta += event.key === 'ArrowRight' ? 15 : -15; paint(); });
    if (!reduced) {
      const intro = new IntersectionObserver((entries) => { if (!entries.some((entry) => entry.isIntersecting)) return; rotator.animate([{transform:'translateX(0)'},{transform:'translateX(8px)'},{transform:'translateX(-8px)'},{transform:'translateX(0)'}], {duration:1400,easing:'ease-in-out'}); intro.disconnect(); }, {threshold:.7});
      intro.observe(rotator);
    }
  };
  const start = (root = document) => root.querySelectorAll('[data-pimm50-story]').forEach(init);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => start(), { once: true }); else start();
  document.addEventListener('shopify:section:load', (event) => start(event.target));
})();
