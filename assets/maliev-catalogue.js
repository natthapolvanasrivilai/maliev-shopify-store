(() => {
  const initialized = new WeakSet();

  const setupCatalogue = (root) => {
    if (!root || initialized.has(root)) return;

    const track = root.querySelector('[data-mcat-track]');
    const cards = Array.from(root.querySelectorAll('[data-mcat-card]'));
    const previous = root.querySelector('[data-mcat-previous]');
    const next = root.querySelector('[data-mcat-next]');
    const toggle = root.querySelector('[data-mcat-toggle]');
    const current = root.querySelector('[data-mcat-current]');
    const progress = root.querySelector('[data-mcat-progress]');

    if (!track || cards.length === 0 || !previous || !next || !toggle) return;
    initialized.add(root);

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const autoplayEnabled = root.dataset.autoplay === 'true';
    const interval = Number(root.dataset.interval) || 3000;
    let activeIndex = 0;
    let timer = null;
    let userPaused = !autoplayEnabled || reduceMotion.matches;
    let interactionPaused = false;
    let scrollFrame = null;

    const setToggleState = () => {
      toggle.setAttribute('aria-pressed', String(userPaused));
      toggle.setAttribute('aria-label', userPaused ? 'Play catalogue rotation' : 'Pause catalogue rotation');
    };

    const updateStatus = (index) => {
      activeIndex = (index + cards.length) % cards.length;
      if (current) current.textContent = String(activeIndex + 1).padStart(2, '0');
      if (progress) progress.style.setProperty('--mcat-progress', String((activeIndex + 1) / cards.length));
    };

    const goTo = (index, smooth = true) => {
      const normalizedIndex = (index + cards.length) % cards.length;
      const card = cards[normalizedIndex];
      const left = card.offsetLeft - track.offsetLeft;
      track.scrollTo({
        left,
        behavior: smooth && !reduceMotion.matches ? 'smooth' : 'auto'
      });
      updateStatus(normalizedIndex);
    };

    const stopTimer = () => {
      if (timer) window.clearInterval(timer);
      timer = null;
    };

    const startTimer = () => {
      stopTimer();
      if (userPaused || interactionPaused || document.hidden || cards.length < 2) return;
      timer = window.setInterval(() => goTo(activeIndex + 1), interval);
    };

    const pauseForInteraction = () => {
      interactionPaused = true;
      stopTimer();
    };

    const resumeAfterInteraction = () => {
      interactionPaused = false;
      startTimer();
    };

    previous.addEventListener('click', () => {
      goTo(activeIndex - 1);
      startTimer();
    });

    next.addEventListener('click', () => {
      goTo(activeIndex + 1);
      startTimer();
    });

    toggle.addEventListener('click', () => {
      userPaused = !userPaused;
      setToggleState();
      startTimer();
    });

    track.addEventListener('pointerenter', pauseForInteraction);
    track.addEventListener('pointerleave', resumeAfterInteraction);
    track.addEventListener('touchstart', pauseForInteraction, { passive: true });
    track.addEventListener('touchend', resumeAfterInteraction, { passive: true });
    root.addEventListener('focusin', pauseForInteraction);
    root.addEventListener('focusout', (event) => {
      if (!root.contains(event.relatedTarget)) resumeAfterInteraction();
    });

    track.addEventListener('scroll', () => {
      if (scrollFrame) window.cancelAnimationFrame(scrollFrame);
      scrollFrame = window.requestAnimationFrame(() => {
        const index = cards.reduce((closest, card, cardIndex) => {
          const distance = Math.abs((card.offsetLeft - track.offsetLeft) - track.scrollLeft);
          return distance < closest.distance ? { index: cardIndex, distance } : closest;
        }, { index: 0, distance: Number.POSITIVE_INFINITY }).index;
        updateStatus(index);
      });
    }, { passive: true });

    document.addEventListener('visibilitychange', startTimer);
    reduceMotion.addEventListener('change', (event) => {
      userPaused = event.matches || !autoplayEnabled;
      setToggleState();
      startTimer();
    });

    setToggleState();
    updateStatus(0);
    startTimer();
  };

  const setupAll = (scope = document) => {
    scope.querySelectorAll('[data-maliev-catalogue]').forEach(setupCatalogue);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setupAll());
  } else {
    setupAll();
  }

  document.addEventListener('shopify:section:load', (event) => setupAll(event.target));
})();
