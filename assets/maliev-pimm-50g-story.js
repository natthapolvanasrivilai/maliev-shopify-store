(() => {
  const init = (page) => {
    if (page.dataset.ready === 'true') return;
    page.dataset.ready = 'true';

    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced || !('IntersectionObserver' in window)) return;

    const observer = new IntersectionObserver((entries, activeObserver) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const media = entry.target.matches('video') ? entry.target : entry.target.querySelector('video');
        if (media) media.play().catch(() => {});
        activeObserver.unobserve(entry.target);
      });
    }, { threshold: .25 });

    page.querySelectorAll('[data-pimm50-motion]').forEach((element) => observer.observe(element));
  };

  const start = (root = document) => root.querySelectorAll('[data-pimm50-page]').forEach(init);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => start(), { once: true });
  else start();
  document.addEventListener('shopify:section:load', (event) => start(event.target));
})();
