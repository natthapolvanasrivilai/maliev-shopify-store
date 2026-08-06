(() => {
  const initialized = new WeakSet();

  const setupCatalogue = (root) => {
    if (!root || initialized.has(root)) return;

    const track = root.querySelector('[data-mcat-track]');
    const cards = Array.from(root.querySelectorAll('[data-mcat-card]'));
    const previous = root.querySelector('[data-mcat-previous]');
    const next = root.querySelector('[data-mcat-next]');
    if (!track || cards.length === 0 || !previous || !next) return;
    initialized.add(root);

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const autoplayEnabled = root.dataset.autoplay === 'true';
    const interval = Number(root.dataset.interval) || 5000;
    let activeIndex = 0;
    let timer = null;
    const pauseReasons = new Set();
    let scrollFrame = null;

    const updateStatus = (index) => {
      const positions = getPositions();
      activeIndex = (index + positions.length) % positions.length;
    };

    const getPositions = () => {
      const maxLeft = Math.max(0, track.scrollWidth - track.clientWidth);
      if (maxLeft === 0 || cards.length < 2) return [0];

      const step = Math.max(1, cards[1].offsetLeft - cards[0].offsetLeft);
      const positions = [0];

      for (let left = step; left < maxLeft - 1; left += step) {
        positions.push(left);
      }

      if (positions[positions.length - 1] !== maxLeft) positions.push(maxLeft);
      return positions;
    };

    const goTo = (index, smooth = true) => {
      const positions = getPositions();
      const normalizedIndex = (index + positions.length) % positions.length;
      track.scrollTo({
        left: positions[normalizedIndex],
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
      if (!autoplayEnabled || reduceMotion.matches || pauseReasons.size > 0 || document.hidden || getPositions().length < 2) return;
      timer = window.setInterval(() => goTo(activeIndex + 1), interval);
    };

    const pauseForInteraction = (reason) => {
      pauseReasons.add(reason);
      stopTimer();
    };

    const resumeAfterInteraction = (reason) => {
      pauseReasons.delete(reason);
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

    root.addEventListener('pointerenter', (event) => {
      if (event.pointerType !== 'touch') pauseForInteraction('hover');
    });
    root.addEventListener('pointerleave', () => resumeAfterInteraction('hover'));
    track.addEventListener('pointerdown', () => pauseForInteraction('pointer'));
    track.addEventListener('pointerup', () => resumeAfterInteraction('pointer'));
    track.addEventListener('pointercancel', () => resumeAfterInteraction('pointer'));
    track.addEventListener('touchstart', () => pauseForInteraction('touch'), { passive: true });
    track.addEventListener('touchend', () => resumeAfterInteraction('touch'), { passive: true });
    track.addEventListener('touchcancel', () => resumeAfterInteraction('touch'), { passive: true });
    root.addEventListener('focusin', () => pauseForInteraction('focus'));
    root.addEventListener('focusout', (event) => {
      if (!root.contains(event.relatedTarget)) resumeAfterInteraction('focus');
    });

    track.addEventListener('scroll', () => {
      if (scrollFrame) window.cancelAnimationFrame(scrollFrame);
      scrollFrame = window.requestAnimationFrame(() => {
        const index = getPositions().reduce((closest, position, positionIndex) => {
          const distance = Math.abs(position - track.scrollLeft);
          return distance < closest.distance ? { index: positionIndex, distance } : closest;
        }, { index: 0, distance: Number.POSITIVE_INFINITY }).index;
        updateStatus(index);
      });
    }, { passive: true });

    document.addEventListener('visibilitychange', startTimer);
    reduceMotion.addEventListener('change', startTimer);

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
