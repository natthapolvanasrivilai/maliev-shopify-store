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
    const overlaySentinel = story;
    const footerStart = document.querySelector('.shopify-section-group-footer-group');
    const variantSelect = story.querySelector('[data-pimm30-variant]');
    const variantInput = story.querySelector('[data-pimm30-variant-id]');
    const variantTitle = story.querySelector('[data-pimm30-variant-title]');
    const price = story.querySelector('[data-pimm30-price]');
    const availability = story.querySelector('[data-pimm30-availability]');
    const addButton = story.querySelector('[data-pimm30-add]');
    const addLabel = story.querySelector('[data-pimm30-add-label]');
    const capacityCounter = story.querySelector('[data-pimm30-capacity-count]');
    const capacityNumber = story.querySelector('[data-pimm30-capacity-number]');
    const capacityFinal = Number(capacityCounter?.dataset.pimm30CapacityFinal || 30);
    const lightMilestone = Number(story.dataset.pimm30LightMilestone || 3500) / 1000;
    const consentRevealDelay = 900;
    const saveData = Boolean(navigator.connection && navigator.connection.saveData);
    const designMode = Boolean(window.Shopify && window.Shopify.designMode);
    const reduced = REDUCED_MOTION.matches || saveData || designMode;
    const hashChapter = chapters.find((chapter) => chapter.id && `#${chapter.id}` === window.location.hash);
    let activeId = (hashChapter || chapters[0]) ? (hashChapter || chapters[0]).dataset.pimm30Chapter : '';
    let activeVideo = null;
    let consentRevealTimer = 0;
    let heroHasPlayed = reduced || activeId !== 'pimm30-overview';
    let capacityCountHasPlayed = reduced || activeId !== 'pimm30-overview';
    let capacityCountFrame = 0;

    story.classList.toggle('is-reduced-motion', reduced);
    story.classList.toggle('is-static', designMode);

    function revealConsentAfterHero() {
      if (document.documentElement.classList.contains('pimm30-consent-ready')) return;
      if (reduced) {
        document.documentElement.classList.add('pimm30-consent-ready');
        return;
      }
      if (consentRevealTimer) return;
      consentRevealTimer = window.setTimeout(() => {
        consentRevealTimer = 0;
        document.documentElement.classList.add('pimm30-consent-ready');
      }, consentRevealDelay);
    }

    function setCapacityCount(value) {
      if (capacityNumber) capacityNumber.textContent = String(Math.max(0, Math.min(capacityFinal, Math.round(value))));
    }

    function completeCapacityCount() {
      if (capacityCountFrame) window.clearTimeout(capacityCountFrame);
      capacityCountFrame = 0;
      capacityCountHasPlayed = true;
      setCapacityCount(capacityFinal);
    }

    function startCapacityCount() {
      if (!capacityNumber || capacityCountHasPlayed) return;
      if (reduced || activeId !== 'pimm30-overview') {
        completeCapacityCount();
        return;
      }

      capacityCountHasPlayed = true;
      const startedAt = Date.now();
      const duration = 1200;
      const tick = () => {
        const now = Date.now();
        const progress = Math.min(1, (now - startedAt) / duration);
        const eased = 1 - Math.pow(1 - progress, 3);
        setCapacityCount(capacityFinal * eased);
        if (progress < 1) {
          capacityCountFrame = window.setTimeout(tick, 16);
        } else {
          capacityCountFrame = 0;
          setCapacityCount(capacityFinal);
        }
      };
      capacityCountFrame = window.setTimeout(tick, 16);
    }

    function setHeroTone(bright) {
      story.classList.toggle('is-hero-bright', bright);
      story.dataset.pimm30HeroTone = bright ? 'bright' : 'dark';
      overlaySentinel.setAttribute('data-header-overlay-tone', activeId === 'pimm30-next_model' ? 'dark' : bright ? 'bright' : 'dark');
      if (bright) {
        revealConsentAfterHero();
        startCapacityCount();
      }
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

      if (activeId === 'pimm30-overview' && heroHasPlayed) {
        resetVideo(video);
        setHeroTone(true);
        return;
      }

      if (restart) resetVideo(video);
      video.classList.add('is-playing');
      video.play().catch(() => {
        layer.classList.add('is-video-failed');
        video.classList.remove('is-playing', 'is-paused');
        if (activeId === 'pimm30-overview') {
          heroHasPlayed = true;
          setHeroTone(true);
        }
      });
    }

    function activate(chapterId, restartVideo = true) {
      if (!layers.has(chapterId)) return;
      const previousId = activeId;
      activeId = chapterId;
      story.dataset.activeChapter = chapterId;

      if (previousId === 'pimm30-overview' && chapterId !== 'pimm30-overview') {
        heroHasPlayed = true;
        completeCapacityCount();
        setHeroTone(true);
      }

      overlaySentinel.setAttribute(
        'data-header-overlay-tone',
        chapterId === 'pimm30-next_model' ? 'dark' : story.classList.contains('is-hero-bright') ? 'bright' : 'dark'
      );

      layers.forEach((layer, id) => {
        const active = id === chapterId;
        layer.classList.toggle('is-active', active);
        layer.setAttribute('aria-hidden', String(!active));
        if (!active) {
          const video = visibleVideo(layer);
          if (video) resetVideo(video);
        }
      });

      if (chapterId !== 'pimm30-overview') setHeroTone(true);
      playActiveVideo(restartVideo);
    }

    story.querySelectorAll('[data-pimm30-video]').forEach((video) => {
      video.addEventListener('timeupdate', () => {
        if (video !== activeVideo || activeId !== 'pimm30-overview' || heroHasPlayed) return;
        setHeroTone(video.currentTime >= lightMilestone);
      });
      video.addEventListener('ended', () => {
        video.classList.remove('is-playing', 'is-paused');
        if (activeId === 'pimm30-overview') {
          heroHasPlayed = true;
          setHeroTone(true);
        }
      });
      video.addEventListener('error', () => {
        const layer = video.closest('[data-pimm30-layer]');
        if (layer) layer.classList.add('is-video-failed');
        if (layer && layer.dataset.pimm30Layer === 'pimm30-overview') {
          heroHasPlayed = true;
          setHeroTone(true);
        }
      });
    });

    if (!designMode) {
      let chapterFrame = 0;
      let pendingChapterId = '';
      let pendingChapterFrame = 0;
      let pendingChapterToken = 0;
      const selectVisibleChapter = () => {
        chapterFrame = 0;
        if (pendingChapterId) return;

        // Keep the stage on the current chapter until the next chapter has
        // reached the top of the viewport. Switching at the midpoint leaves
        // the old chapter copy over the new media during a free scroll.
        const nextChapter = chapters.find((chapter) => {
          const rect = chapter.getBoundingClientRect();
          return rect.top <= 8 && rect.bottom > 8;
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
      const setFooterActive = (active) => {
        const wasActive = document.documentElement.classList.contains('pimm30-footer-active');
        document.documentElement.classList.toggle('pimm30-footer-active', active);
        const changed = wasActive !== active;
        if (changed) window.dispatchEvent(new CustomEvent('maliev:header-overlay-sync'));
      };

      if (footerStart && 'IntersectionObserver' in window) {
        const footerObserver = new IntersectionObserver(([entry]) => {
          setFooterActive(entry.intersectionRatio > 0);
        }, { threshold: [0, 0.001] });
        footerObserver.observe(footerStart);
      }

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

      const settleChapterTransition = (chapter, chapterId, token, startedAt) => {
        if (token !== pendingChapterToken || pendingChapterId !== chapterId) return;

        const distanceFromTop = Math.abs(chapter.getBoundingClientRect().top);
        const timedOut = performance.now() - startedAt >= 1400;
        if (distanceFromTop <= 8 || timedOut) {
          pendingChapterFrame = 0;
          pendingChapterId = '';
          gestureLocked = false;

          // If the browser interrupted smooth scrolling, let the regular
          // selector choose the chapter actually under the viewport instead
          // of switching the stage to a destination that was never reached.
          if (distanceFromTop <= 8) activate(chapterId, true);
          queueChapterSelection();
          return;
        }

        pendingChapterFrame = window.requestAnimationFrame((now) =>
          settleChapterTransition(chapter, chapterId, token, startedAt || now)
        );
      };

      const navigateToChapter = (chapter) => {
        const chapterId = chapter?.dataset.pimm30Chapter;
        if (!chapterId) return;

        pendingChapterToken += 1;
        const token = pendingChapterToken;
        const startedAt = performance.now();
        pendingChapterId = chapterId;
        chapter.scrollIntoView({ behavior: 'smooth', block: 'start' });
        if (pendingChapterFrame) window.cancelAnimationFrame(pendingChapterFrame);
        pendingChapterFrame = window.requestAnimationFrame((now) =>
          settleChapterTransition(chapter, chapterId, token, startedAt || now)
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
          if (!direction || nextIndex < 0) return;

          if (direction > 0 && nextIndex >= chapters.length && footerStart) {
            event.preventDefault();
            if (gestureLocked) return;

            gestureLocked = true;
            setFooterActive(true);
            footerStart.scrollIntoView({ behavior: 'smooth', block: 'start' });
            window.clearTimeout(gestureUnlockTimer);
            gestureUnlockTimer = window.setTimeout(() => {
              gestureLocked = false;
            }, 900);
            return;
          }

          if (nextIndex >= chapters.length) return;

          event.preventDefault();
          if (gestureLocked || pendingChapterId) return;

          gestureLocked = true;
          navigateToChapter(chapters[nextIndex]);
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

    const initialHeroVideo = visibleVideo(layers.get('pimm30-overview'));
    if (reduced || !initialHeroVideo || activeId !== 'pimm30-overview') {
      heroHasPlayed = true;
      completeCapacityCount();
      setHeroTone(true);
    } else {
      setCapacityCount(0);
      setHeroTone(false);
    }
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
