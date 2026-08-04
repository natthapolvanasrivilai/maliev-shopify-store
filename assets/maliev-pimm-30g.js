(() => {
  const STORY_SELECTOR = '[data-pimm30-story]';
  const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)');

  function visibleVideo(layer) {
    if (!layer) return null;
    const mobile = window.matchMedia('(max-width: 749px)').matches;
    return layer.querySelector(
      mobile
        ? '.pimm30-stage__video--mobile, .pimm30-stage__video--all-devices'
        : '.pimm30-stage__video--desktop, .pimm30-stage__video--all-devices'
    );
  }

  function initStory(story) {
    if (story.dataset.pimm30Ready === 'true') return;
    story.dataset.pimm30Ready = 'true';

    const chapters = [...story.querySelectorAll('[data-pimm30-chapter]')];
    const layers = new Map(
      [...story.querySelectorAll('[data-pimm30-layer]')].map((layer) => [layer.dataset.pimm30Layer, layer])
    );
    const hero = story.querySelector('[data-header-overlay-sentinel]');
    const variantSelect = story.querySelector('[data-pimm30-variant]');
    const variantInput = story.querySelector('[data-pimm30-variant-id]');
    const variantTitle = story.querySelector('[data-pimm30-variant-title]');
    const price = story.querySelector('[data-pimm30-price]');
    const availability = story.querySelector('[data-pimm30-availability]');
    const addButton = story.querySelector('[data-pimm30-add]');
    const addLabel = story.querySelector('[data-pimm30-add-label]');
    const lightMilestone = Number(story.dataset.pimm30LightMilestone || 3500) / 1000;
    const saveData = Boolean(navigator.connection && navigator.connection.saveData);
    const designMode = Boolean(window.Shopify && window.Shopify.designMode);
    const reduced = REDUCED_MOTION.matches || saveData || designMode;
    let activeId = chapters[0] ? chapters[0].dataset.pimm30Chapter : '';
    let activeVideo = null;

    story.classList.toggle('is-reduced-motion', reduced);
    story.classList.toggle('is-static', designMode);

    function setHeroTone(bright) {
      story.classList.toggle('is-hero-bright', bright);
      story.dataset.pimm30HeroTone = bright ? 'bright' : 'dark';
      if (hero) hero.setAttribute('data-header-overlay-tone', bright ? 'bright' : 'dark');
    }

    function resetVideo(video) {
      if (!video) return;
      video.pause();
      video.classList.remove('is-playing', 'is-paused');
      try {
        video.currentTime = 0;
      } catch (_error) {
        // Some browsers reject seeking before metadata is ready. The poster remains valid.
      }
    }

    function playActiveVideo(restart = true) {
      const layer = layers.get(activeId);
      const video = visibleVideo(layer);
      activeVideo = video;
      if (!video || reduced) return;

      if (restart) resetVideo(video);
      video.classList.add('is-playing');
      video.play().catch(() => {
        layer.classList.add('is-video-failed');
        video.classList.remove('is-playing', 'is-paused');
        if (activeId === 'pimm30-overview') setHeroTone(true);
      });
    }

    function activate(chapterId, restartVideo = true) {
      if (!layers.has(chapterId)) return;
      activeId = chapterId;
      story.dataset.activeChapter = chapterId;

      layers.forEach((layer, id) => {
        const active = id === chapterId;
        layer.classList.toggle('is-active', active);
        layer.setAttribute('aria-hidden', String(!active));
        if (!active) {
          const video = visibleVideo(layer);
          if (video) resetVideo(video);
        }
      });

      if (hero) {
        if (chapterId === 'pimm30-overview') hero.removeAttribute('data-header-overlay-complete');
        else hero.setAttribute('data-header-overlay-complete', '');
      }

      if (chapterId !== 'pimm30-overview') setHeroTone(true);
      playActiveVideo(restartVideo);
    }

    story.querySelectorAll('[data-pimm30-video]').forEach((video) => {
      video.addEventListener('timeupdate', () => {
        if (video !== activeVideo || activeId !== 'pimm30-overview') return;
        setHeroTone(video.currentTime >= lightMilestone);
      });
      video.addEventListener('ended', () => {
        video.classList.remove('is-playing', 'is-paused');
        if (activeId === 'pimm30-overview') setHeroTone(true);
      });
      video.addEventListener('error', () => {
        const layer = video.closest('[data-pimm30-layer]');
        if (layer) layer.classList.add('is-video-failed');
        if (layer && layer.dataset.pimm30Layer === 'pimm30-overview') setHeroTone(true);
      });
    });

    if (!designMode) {
      let chapterFrame = 0;
      const selectVisibleChapter = () => {
        chapterFrame = 0;
        const marker = window.innerHeight * 0.5;
        const nextChapter = chapters.find((chapter) => {
          const rect = chapter.getBoundingClientRect();
          return rect.top <= marker && rect.bottom > marker;
        });
        const nextId = nextChapter && nextChapter.dataset.pimm30Chapter;
        if (nextId && nextId !== activeId) activate(nextId, true);
      };
      const queueChapterSelection = () => {
        if (chapterFrame) return;
        chapterFrame = window.requestAnimationFrame(selectVisibleChapter);
      };
      window.addEventListener('scroll', queueChapterSelection, { passive: true });
      window.addEventListener('resize', queueChapterSelection, { passive: true });

      const snapViewport = window.matchMedia('(min-height: 720px)');
      let gestureLocked = false;
      let gestureUnlockTimer = 0;

      const activeChapterIndex = () => {
        const currentIndex = chapters.findIndex((chapter) => chapter.dataset.pimm30Chapter === activeId);
        if (currentIndex >= 0) return currentIndex;
        const marker = window.innerHeight * 0.5;
        return Math.max(
          0,
          chapters.findIndex((chapter) => {
            const rect = chapter.getBoundingClientRect();
            return rect.top <= marker && rect.bottom > marker;
          })
        );
      };

      story.addEventListener(
        'wheel',
        (event) => {
          if (reduced || !snapViewport.matches || Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;

          const index = activeChapterIndex();
          const currentChapter = chapters[index];
          if (!currentChapter || currentChapter.scrollHeight > window.innerHeight + 2) return;

          const direction = Math.sign(event.deltaY);
          const nextIndex = index + direction;
          if (!direction || nextIndex < 0 || nextIndex >= chapters.length) return;

          event.preventDefault();
          if (gestureLocked) return;

          gestureLocked = true;
          activate(chapters[nextIndex].dataset.pimm30Chapter, true);
          chapters[nextIndex].scrollIntoView({ behavior: 'smooth', block: 'start' });
          window.clearTimeout(gestureUnlockTimer);
          gestureUnlockTimer = window.setTimeout(() => {
            gestureLocked = false;
          }, 900);
        },
        { passive: false }
      );
    }

    if (variantSelect) {
      variantSelect.addEventListener('change', () => {
        const option = variantSelect.selectedOptions[0];
        const availableNow = option.dataset.available === 'true';
        if (variantInput) variantInput.value = option.value;
        if (variantTitle) variantTitle.textContent = option.textContent.split(' — ')[0];
        if (price) price.textContent = option.dataset.price || '';
        if (availability) {
          availability.textContent = availableNow
            ? window.variantStrings?.available || 'In stock'
            : window.variantStrings?.soldOut || 'Out of stock';
          availability.classList.toggle('is-unavailable', !availableNow);
        }
        if (addButton) addButton.disabled = !availableNow;
        if (addLabel) {
          addLabel.textContent = availableNow
            ? window.variantStrings?.addToCart || 'Add to cart'
            : window.variantStrings?.soldOut || 'Sold out';
        }
      });
    }

    const activeHeroVideo = visibleVideo(layers.get(activeId));
    if (reduced || !activeHeroVideo) setHeroTone(true);
    else setHeroTone(false);
    activate(activeId, true);
  }

  function initAll(scope = document) {
    scope.querySelectorAll(STORY_SELECTOR).forEach(initStory);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initAll());
  } else {
    initAll();
  }

  document.addEventListener('shopify:section:load', (event) => initAll(event.target));
})();
