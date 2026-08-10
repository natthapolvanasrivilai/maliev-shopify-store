(() => {
  const STORY_SELECTOR = '[data-pimm30-story]';
  const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)');
  function visibleVideo(layer) {
    if (!layer) return null;
    // Portrait assets fill tall media regions; landscape windows use the wide
    // assets so the machine remains large without cropping. Keep this selector
    // in lockstep with the CSS art-direction and Liquid <picture> breakpoint.
    const mobile = window.matchMedia('(max-width: 539px), (orientation: portrait)').matches;
    const preferredSelector = mobile
      ? '.pimm30-stage__video--mobile, .pimm30-stage__video--all-devices'
      : '.pimm30-stage__video--desktop, .pimm30-stage__video--all-devices';
    return layer.querySelector(preferredSelector);
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
    const specCounters = [...story.querySelectorAll('[data-pimm30-spec-count]')].map((counter) => ({
      number: counter.querySelector('[data-pimm30-spec-number]'),
      final: Number(counter.dataset.pimm30SpecFinal || 0),
      decimals: Number(counter.dataset.pimm30SpecDecimals || 0),
    }));
    const consentRevealDelay = 900;
    const saveData = Boolean(navigator.connection && navigator.connection.saveData);
    const designMode = Boolean(window.Shopify && window.Shopify.designMode);
    // The local Shopify dev preview is the debugging surface. Codex's embedded
    // browser can advertise prefers-reduced-motion even when the developer is
    // actively inspecting motion. Keep the real accessibility preference on
    // hosted storefronts, but allow the local preview to exercise full motion.
    const localDebugPreview = /^(localhost|127\.0\.0\.1)$/.test(window.location.hostname)
      && window.location.port === '9393';
    const reduced = !localDebugPreview && (REDUCED_MOTION.matches || saveData || designMode);
    const requestedCtaVariant = new URLSearchParams(window.location.search).get('cta_variant');
    const ctaVariants = ['compact', 'editorial', 'dual'];
    const ctaVariant = ctaVariants.includes(requestedCtaVariant) ? requestedCtaVariant : 'compact';
    story.classList.remove(...ctaVariants.map((variant) => `pimm30-cta-variant--${variant}`));
    story.classList.add(`pimm30-cta-variant--${ctaVariant}`);
    story.classList.toggle('is-debug-motion', localDebugPreview);
    const hashChapter = chapters.find((chapter) => chapter.id && `#${chapter.id}` === window.location.hash);
    let activeId = (hashChapter || chapters[0]) ? (hashChapter || chapters[0]).dataset.pimm30Chapter : '';
    let activeVideo = null;
    let consentRevealTimer = 0;
    let heroHasPlayed = reduced || activeId !== 'pimm30-overview';
    let specCountHasPlayed = reduced || activeId !== 'pimm30-overview';
    let specCountFrame = 0;
    let responsiveVideoFrame = 0;

    story.classList.toggle('is-reduced-motion', reduced);
    // Theme-editor previews are intentionally static on the hosted storefront,
    // but the local Shopify dev preview is the motion-debugging surface. Do not
    // let the editor flag silence videos when inspecting the presentation at
    // localhost:9393.
    story.classList.toggle('is-static', designMode && !localDebugPreview);

    function revealHeroPoster() {
      story.classList.remove('is-hero-pending');
    }

    function setHeroComplete(complete) {
      story.classList.toggle('is-hero-complete', complete);
      story.classList.toggle('is-hero-sequencing', !complete);
    }

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

    function setSpecCounts(progress) {
      const boundedProgress = Math.max(0, Math.min(1, progress));
      specCounters.forEach((counter) => {
        if (!counter.number) return;
        const value = counter.final * boundedProgress;
        counter.number.textContent = counter.decimals > 0
          ? value.toFixed(counter.decimals)
          : String(Math.round(value));
      });
    }

    function completeSpecCounts() {
      if (specCountFrame) window.clearTimeout(specCountFrame);
      specCountFrame = 0;
      specCountHasPlayed = true;
      setSpecCounts(1);
    }

    function startSpecCounts() {
      if (!specCounters.length || specCountHasPlayed) return;
      if (reduced || activeId !== 'pimm30-overview') {
        completeSpecCounts();
        return;
      }

      specCountHasPlayed = true;
      const startedAt = Date.now();
      const duration = 1200;
      const tick = () => {
        const now = Date.now();
        const progress = Math.min(1, (now - startedAt) / duration);
        const eased = 1 - Math.pow(1 - progress, 3);
        setSpecCounts(eased);
        if (progress < 1) {
          specCountFrame = window.setTimeout(tick, 16);
        } else {
          specCountFrame = 0;
          setSpecCounts(1);
        }
      };
      specCountFrame = window.setTimeout(tick, 16);
    }

    function setHeroTone(bright) {
      story.classList.toggle('is-hero-bright', bright);
      story.classList.toggle('is-hero-dark', !bright);
      story.dataset.pimm30HeroTone = bright ? 'bright' : 'dark';
      overlaySentinel.setAttribute(
        'data-header-overlay-tone',
        activeId === 'pimm30-next_model' ? 'dark' : bright ? 'bright' : 'dark'
      );
      if (bright) {
        revealConsentAfterHero();
        startSpecCounts();
      }
    }

    function resetVideo(video) {
      if (!video) return;
      video.pause();
      video.classList.remove('is-playing', 'is-paused');
      const layer = video.closest('[data-pimm30-layer]');
      if (layer) layer.classList.remove('has-active-video');
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

      if (layer.matches('[data-pimm30-turntable]')) {
        if (restart) resetVideo(video);

        const holdInteractiveFrame = () => {
          const interactiveFrame = (65 / 24 + 101 / 24) / 2;
          const revealFrame = () => {
            const settleFrame = () => {
              video.pause();
              video.classList.remove('is-playing');
              video.classList.add('is-paused');
              layer.classList.add('has-active-video', 'is-turntable-ready');
            };

            // Chromium does not reliably paint a programmatically sought frame
            // until the media pipeline has advanced once. Keep the poster in
            // place during that single muted frame so the handoff cannot flash.
            video.play()
              .then(() => window.requestAnimationFrame(settleFrame))
              .catch(settleFrame);
          };

          if (Math.abs(video.currentTime - interactiveFrame) < 1 / 48) {
            revealFrame();
            return;
          }

          video.addEventListener('seeked', revealFrame, { once: true });
          video.currentTime = (65 / 24 + 101 / 24) / 2;
        };

        if (video.readyState >= 1) {
          holdInteractiveFrame();
        } else {
          video.addEventListener('loadedmetadata', holdInteractiveFrame, { once: true });
          video.load();
        }
        return;
      }

      if (activeId === 'pimm30-overview' && heroHasPlayed) {
        resetVideo(video);
        revealHeroPoster();
        setHeroComplete(true);
        setHeroTone(true);
        return;
      }

      if (restart) resetVideo(video);
      video.classList.add('is-playing');
      video.play()
        .then(() => {
          if (activeVideo === video && !video.paused) layer.classList.add('has-active-video');
        })
        .catch(() => {
          layer.classList.add('is-video-failed');
          layer.classList.remove('has-active-video');
          video.classList.remove('is-playing', 'is-paused');
          if (activeId === 'pimm30-overview') {
            heroHasPlayed = true;
            revealHeroPoster();
            setHeroComplete(true);
            setHeroTone(true);
          }
        });
    }

    function syncResponsiveVideo() {
      responsiveVideoFrame = 0;
      const nextVideo = visibleVideo(layers.get(activeId));
      if (nextVideo === activeVideo) return;

      resetVideo(activeVideo);
      playActiveVideo(true);
    }

    function queueResponsiveVideoSync() {
      if (responsiveVideoFrame) return;
      responsiveVideoFrame = window.requestAnimationFrame(syncResponsiveVideo);
    }

    function activate(chapterId, restartVideo = true) {
      if (!layers.has(chapterId)) return;
      const previousId = activeId;
      activeId = chapterId;
      story.dataset.activeChapter = chapterId;

      if (previousId === 'pimm30-overview' && chapterId !== 'pimm30-overview') {
        heroHasPlayed = true;
        revealHeroPoster();
        setHeroComplete(true);
        completeSpecCounts();
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
        if (layer.matches('[data-pimm30-turntable]')) layer.tabIndex = active ? 0 : -1;
        if (!active) {
          const video = visibleVideo(layer);
          if (video) resetVideo(video);
        }
      });

      if (chapterId !== 'pimm30-overview') setHeroTone(true);
      playActiveVideo(restartVideo);
    }

    story.querySelectorAll('[data-pimm30-video]').forEach((video) => {
      video.addEventListener('ended', () => {
        const layer = video.closest('[data-pimm30-layer]');
        const holdsFinalFrame = layer && (
          layer.matches('[data-pimm30-turntable]') ||
          layer.dataset.pimm30Layer === 'pimm30-overview'
        );
        if (holdsFinalFrame) {
          video.classList.remove('is-playing');
          video.classList.add('is-paused');
          layer.classList.add('has-active-video');
          if (layer.matches('[data-pimm30-turntable]')) {
            video.currentTime = (65 / 24 + 101 / 24) / 2;
            layer.classList.add('is-turntable-ready');
          }
        } else {
          video.classList.remove('is-playing', 'is-paused');
          if (layer) layer.classList.remove('has-active-video');
        }
        if (activeId === 'pimm30-overview') {
          heroHasPlayed = true;
          revealHeroPoster();
          setHeroComplete(true);
          setHeroTone(true);
        }
      });
      video.addEventListener('error', () => {
        const layer = video.closest('[data-pimm30-layer]');
        resetVideo(video);
        if (layer) {
          layer.classList.add('is-video-failed');
          layer.classList.remove('has-active-video');
        }
        if (layer && layer.dataset.pimm30Layer === 'pimm30-overview') {
          heroHasPlayed = true;
          revealHeroPoster();
          setHeroComplete(true);
          setHeroTone(true);
        }
      });
    });

    window.addEventListener('resize', queueResponsiveVideoSync, { passive: true });

    story.querySelectorAll('[data-pimm30-turntable]').forEach((turntable) => {
      const video = visibleVideo(turntable);
      if (!video) return;

      let dragging = false;
      let dragStartX = 0;
      let dragStartProgress = 0.5;
      let rotationProgress = 0.5;
      let pendingTime = null;
      let scrubFrame = 0;
      let seekableSourcePromise = null;
      const rotationStartTime = 65 / 24;
      const rotationEndTime = 101 / 24;

      const prepareSeekableVideo = () => {
        if (video.currentSrc.startsWith('blob:')) return Promise.resolve(true);
        if (seekableSourcePromise) return seekableSourcePromise;

        const sourceUrl = video.currentSrc || video.querySelector('source')?.src;
        if (!sourceUrl) return Promise.resolve(false);

        seekableSourcePromise = fetch(sourceUrl, { cache: 'force-cache' })
          .then((response) => {
            if (!response.ok) throw new Error(`Turntable media request failed: ${response.status}`);
            return response.blob();
          })
          .then((blob) => URL.createObjectURL(blob))
          .then((objectUrl) => new Promise((resolve) => {
            const resumeTime = video.currentTime;
            const resumePlayback = !video.paused && !video.ended;
            const handleMetadata = () => {
              const finalFrameTime = Math.max(0, video.duration - 1 / 24);
              video.currentTime = Math.min(resumeTime, finalFrameTime);
              turntable.dataset.pimm30Seekable = 'true';
              if (resumePlayback) video.play().catch(() => {});
              resolve(true);
            };

            video.addEventListener('loadedmetadata', handleMetadata, { once: true });
            video.src = objectUrl;
            video.load();
            window.addEventListener('pagehide', () => URL.revokeObjectURL(objectUrl), { once: true });
          }))
          .catch(() => {
            turntable.dataset.pimm30Seekable = 'false';
            return false;
          });

        return seekableSourcePromise;
      };

      const progressPerPixel = () => 1 / Math.max(turntable.clientWidth, 720);

      const showInteractiveFrame = () => {
        video.pause();
        video.classList.remove('is-playing');
        video.classList.add('is-paused');
        turntable.classList.add('has-active-video', 'is-turntable-ready', 'is-dragging');
      };

      const applyScrub = () => {
        scrubFrame = 0;
        if (pendingTime === null) return;
        const nextTime = pendingTime;
        pendingTime = null;
        if (Math.abs(video.currentTime - nextTime) >= 1 / 48) video.currentTime = nextTime;
      };

      const queueScrub = (nextProgress) => {
        if (!Number.isFinite(video.duration) || video.duration <= 0) return;
        rotationProgress = Math.max(0, Math.min(1, nextProgress));
        pendingTime = rotationStartTime + rotationProgress * (rotationEndTime - rotationStartTime);
        if (!scrubFrame) scrubFrame = window.requestAnimationFrame(applyScrub);
      };

      turntable.addEventListener('pointerdown', (event) => {
        if (event.pointerType === 'mouse' && event.button !== 0) return;
        dragging = true;
        dragStartX = event.clientX;
        dragStartProgress = rotationProgress;
        turntable.setPointerCapture(event.pointerId);
        showInteractiveFrame();
      });

      turntable.addEventListener('pointermove', (event) => {
        if (!dragging) return;
        // PointerEvent coalescing keeps high-refresh touch and mouse drags
        // smooth without adding a second render loop. Fall back for browsers
        // that do not expose getCoalescedEvents().
        const coalesced = typeof event.getCoalescedEvents === 'function'
          ? event.getCoalescedEvents()
          : [];
        const point = coalesced.length ? coalesced[coalesced.length - 1] : event;
        queueScrub(dragStartProgress - (point.clientX - dragStartX) * progressPerPixel());
      });

      const stopDragging = (event) => {
        if (!dragging) return;
        dragging = false;
        if (scrubFrame) {
          window.cancelAnimationFrame(scrubFrame);
          applyScrub();
        }
        turntable.classList.remove('is-dragging');
        if (turntable.hasPointerCapture(event.pointerId)) turntable.releasePointerCapture(event.pointerId);
      };
      turntable.addEventListener('pointerup', stopDragging);
      turntable.addEventListener('pointercancel', stopDragging);

      turntable.addEventListener('keydown', (event) => {
        if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
        event.preventDefault();
        showInteractiveFrame();
        queueScrub(rotationProgress + (event.key === 'ArrowRight' ? 0.04 : -0.04));
        if (scrubFrame) {
          window.cancelAnimationFrame(scrubFrame);
          applyScrub();
        }
        turntable.classList.remove('is-dragging');
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
            ? availability.dataset.madeToOrder || 'Made to order'
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
      revealHeroPoster();
      setHeroComplete(true);
      completeSpecCounts();
      setHeroTone(true);
    } else {
      setSpecCounts(0);
      setHeroComplete(false);
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
