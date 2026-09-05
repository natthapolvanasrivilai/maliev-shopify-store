/* MALIEV keynote scroll choreography.
   Progressive enhancement only: without this file (or with reduced motion)
   every section renders fully visible. The .mk-motion class on <html> is the
   single gate for hidden pre-reveal states in maliev-keynote.css. */
(function () {
  'use strict';

  if (window.__malievKeynoteInit) return;
  window.__malievKeynoteInit = true;

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  function initHomeHeader() {
    var header = document.querySelector('.mc-header--home');
    var hero = document.querySelector('.mkey--hero');
    if (!header || !hero) return;

    var frameRequested = false;

    function syncHeader() {
      frameRequested = false;
      var heroBottom = hero.getBoundingClientRect().bottom;
      header.classList.toggle('is-solid', heroBottom <= header.offsetHeight + 1);
    }

    function requestSync() {
      if (frameRequested) return;
      frameRequested = true;
      window.requestAnimationFrame(syncHeader);
    }

    syncHeader();
    window.addEventListener('scroll', requestSync, { passive: true });
    window.addEventListener('resize', requestSync);
  }

  function revealAll() {
    document.querySelectorAll('.mkey [data-mkr]').forEach(function (el) {
      el.classList.add('mk-in');
    });
  }

  /* Shopify's theme editor and local HMR can replace a section after this
     script has initialized. Newly inserted reveal targets must never inherit
     the hidden pre-reveal state without also being registered. Dynamic
     replacements are revealed immediately; initial page content keeps the
     normal IntersectionObserver choreography below. */
  function observeDynamicKeynoteContent() {
    if (!('MutationObserver' in window) || !document.body) return;

    var observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        mutation.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;

          if (node.matches && node.matches('.mkey [data-mkr]')) {
            node.classList.add('mk-in');
          }

          if (node.querySelectorAll) {
            node.querySelectorAll('.mkey [data-mkr]').forEach(function (el) {
              el.classList.add('mk-in');
            });
          }
        });
      });
    });

    observer.observe(document.body, { childList: true, subtree: true });
  }

  function init() {
    if (reduceMotion.matches || !('IntersectionObserver' in window)) {
      document.documentElement.classList.remove('mk-motion');
      return;
    }

    document.documentElement.classList.add('mk-motion');

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          var group = entry.target;
          var items = group.querySelectorAll('[data-mkr]');
          items.forEach(function (el, i) {
            if (!el.style.getPropertyValue('--mkr-i')) {
              el.style.setProperty('--mkr-i', String(i));
            }
            el.classList.add('mk-in');
          });
          observer.unobserve(group);
        });
      },
      { rootMargin: '0px 0px -12% 0px', threshold: 0.1 }
    );

    document.querySelectorAll('.mkey [data-mkr-group]').forEach(function (group) {
      var rect = group.getBoundingClientRect();
      if (rect.top < window.innerHeight && rect.bottom > 0) {
        /* Already on screen at load: reveal immediately, no observer pop-in. */
        group.querySelectorAll('[data-mkr]').forEach(function (el, i) {
          el.style.setProperty('--mkr-i', String(i));
          el.classList.add('mk-in');
        });
      } else {
        observer.observe(group);
      }
    });

    /* Safety net: if anything is still hidden after 6s (edge-case observer
       failure, prerender, background tab), reveal it. */
    window.setTimeout(revealAll, 6000);
  }

  reduceMotion.addEventListener('change', function () {
    if (reduceMotion.matches) {
      document.documentElement.classList.remove('mk-motion');
      revealAll();
    }
  });

  /* Pause chapter videos when reduced motion is requested.
     A video the user paused via the toggle stays paused. */
  function syncVideos() {
    document.querySelectorAll('.mkey video[autoplay]').forEach(function (video) {
      if (reduceMotion.matches) {
        video.pause();
      } else if (video.paused && !video.hasAttribute('data-user-paused')) {
        video.play().catch(function () {});
      }
    });
  }

  reduceMotion.addEventListener('change', syncVideos);

  /* User pause/play toggle on chapter videos (WCAG 2.2.2). */
  document.addEventListener('click', function (event) {
    var toggle = event.target.closest ? event.target.closest('.mkey__video-toggle') : null;
    if (!toggle) return;
    var video = toggle.parentElement.querySelector('video');
    if (!video) return;
    if (video.paused) {
      video.removeAttribute('data-user-paused');
      toggle.setAttribute('aria-pressed', 'false');
      video.play().catch(function () {});
    } else {
      video.setAttribute('data-user-paused', '');
      toggle.setAttribute('aria-pressed', 'true');
      video.pause();
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initHomeHeader();
      init();
      observeDynamicKeynoteContent();
      syncVideos();
    });
  } else {
    initHomeHeader();
    init();
    observeDynamicKeynoteContent();
    syncVideos();
  }
})();
