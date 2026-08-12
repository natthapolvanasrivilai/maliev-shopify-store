(() => {
  const init = (story) => {
    if (story.dataset.ready === 'true') return;
    story.dataset.ready = 'true';

    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const chapters = [...story.querySelectorAll('[data-pimm50-chapter]')];
    const railLinks = [...story.querySelectorAll('.pimm50-story__rail a')];
    const railById = new Map(railLinks.map((link) => [link.hash.slice(1), link]));

    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting || entry.intersectionRatio < .55) return;
        chapters.forEach((chapter) => chapter.classList.toggle('is-active', chapter === entry.target));
        railLinks.forEach((link) => {
          const active = link === railById.get(entry.target.id);
          link.classList.toggle('is-active', active);
          if (active) link.setAttribute('aria-current', 'true');
          else link.removeAttribute('aria-current');
        });
      });
    }, { threshold: [.55] });

    chapters.forEach((chapter) => observer.observe(chapter));

    const video = story.querySelector('[data-pimm50-reveal-video]');
    if (!video) return;
    if (reduced) video.pause();
    else video.addEventListener('ended', () => {
      video.pause();
      video.classList.add('is-finished');
    }, { once: true });
  };

  const start = (root = document) => root.querySelectorAll('[data-pimm50-story]').forEach(init);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => start(), { once: true });
  else start();
  document.addEventListener('shopify:section:load', (event) => start(event.target));
})();
