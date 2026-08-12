(() => {
  const revealAll = (elements) => elements.forEach((element) => element.classList.add('is-in-view'));

  const init = (page) => {
    if (page.dataset.ready === 'true') return;
    page.dataset.ready = 'true';

    const motionElements = [...page.querySelectorAll('[data-pimm50-motion]')];
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reducedMotion || !('IntersectionObserver' in window)) {
      revealAll(motionElements);
      return;
    }

    const observer = new IntersectionObserver((entries, activeObserver) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('is-in-view');
        activeObserver.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -8%', threshold: .12 });

    motionElements.forEach((element) => observer.observe(element));
  };

  const start = (root = document) => root.querySelectorAll('[data-pimm50-page]').forEach(init);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => start(), { once: true });
  } else {
    start();
  }

  document.addEventListener('shopify:section:load', (event) => start(event.target));
})();
