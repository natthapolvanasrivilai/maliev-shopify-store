(() => {
  const STORY_SELECTOR = '[data-pimm30-story]';

  const initialiseStory = (story) => {
    if (story.dataset.pimm30Ready === 'true') return;
    story.dataset.pimm30Ready = 'true';
    story.classList.add('is-enhanced');

    const chapters = Array.from(story.querySelectorAll('[data-pimm30-chapter]'));
    const layers = Array.from(story.querySelectorAll('[data-pimm30-layer]'));
    const navigation = Array.from(story.querySelectorAll('[data-pimm30-nav]'));
    const controls = story.querySelector('[data-pimm30-controls]');
    const pauseButton = story.querySelector('[data-pimm30-pause]');
    const pauseLabel = story.querySelector('[data-pimm30-pause-label]');
    const replayButton = story.querySelector('[data-pimm30-replay]');
    const liveStatus = story.querySelector('[data-pimm30-status]');
    const hero = story.querySelector('[data-header-overlay-sentinel]');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const desktopMedia = window.matchMedia('(min-width: 750px)');
    const saveData = Boolean(navigator.connection && navigator.connection.saveData);
    const staticExperience = reducedMotion.matches || saveData;
    const pauseText = story.dataset.pimm30PauseLabel || 'Pause animation';
    const resumeText = story.dataset.pimm30ResumeLabel || 'Resume animation';
    const lightMilestone = Number.parseInt(story.dataset.pimm30LightMilestone || '3250', 10);
    let activeChapterId = chapters[0]?.dataset.pimm30Chapter || '';
    let heroLightTimer = 0;
    let userPaused = false;
    let snapFrame = 0;

    if (!chapters.length || !layers.length) return;

    const updateSnapEligibility = () => {
      window.cancelAnimationFrame(snapFrame);
      snapFrame = window.requestAnimationFrame(() => {
        const viewportHeight = window.innerHeight;
        const chaptersFitViewport = chapters.every((chapter) => chapter.scrollHeight <= viewportHeight + 1);
        story.classList.toggle('is-snap-ready', !staticExperience && chaptersFitViewport);
      });
    };

    const setHeroTone = (tone) => {
      if (!hero) return;
      hero.dataset.headerOverlayTone = tone;
      story.dataset.heroTone = tone;
    };

    const clearHeroTimer = () => {
      if (!heroLightTimer) return;
      window.clearTimeout(heroLightTimer);
      heroLightTimer = 0;
    };

    const activeLayer = () => layers.find((layer) => layer.dataset.pimm30Layer === activeChapterId);

    const visibleVideo = (layer) => {
      if (!layer || staticExperience || layer.classList.contains('is-video-failed')) return null;
      const preferredClass = desktopMedia.matches ? '.pimm30-stage__video--desktop' : '.pimm30-stage__video--mobile';
      return layer.querySelector(preferredClass) || layer.querySelector('.pimm30-stage__video--all-devices');
    };

    const updateControls = () => {
      const video = visibleVideo(activeLayer());
      if (!controls) return;
      controls.hidden = !video;
      if (pauseButton) pauseButton.setAttribute('aria-pressed', String(userPaused));
      if (pauseLabel) pauseLabel.textContent = userPaused ? resumeText : pauseText;
    };

    const pauseAllVideos = (exceptVideo = null) => {
      story.querySelectorAll('[data-pimm30-video]').forEach((video) => {
        if (video !== exceptVideo) {
          video.pause();
          video.classList.remove('is-playing');
        }
      });
    };

    const scheduleHeroLight = () => {
      clearHeroTimer();
      if (activeChapterId !== 'pimm30-overview') return;
      setHeroTone('dark');
      heroLightTimer = window.setTimeout(() => setHeroTone('bright'), Math.max(0, lightMilestone));
    };

    const playActiveVideo = () => {
      const layer = activeLayer();
      const video = visibleVideo(layer);
      pauseAllVideos(video);
      updateControls();

      if (!video || userPaused) {
        if (activeChapterId === 'pimm30-overview') setHeroTone('bright');
        return;
      }

      const playPromise = video.play();
      if (playPromise && typeof playPromise.then === 'function') {
        playPromise
          .then(() => {
            video.classList.add('is-playing');
            if (activeChapterId === 'pimm30-overview') scheduleHeroLight();
          })
          .catch(() => {
            layer.classList.add('is-video-failed');
            if (activeChapterId === 'pimm30-overview') setHeroTone('bright');
            updateControls();
          });
      }
    };

    const activateChapter = (chapterId, announce = false) => {
      if (!chapterId) return;
      activeChapterId = chapterId;
      story.dataset.activeChapter = chapterId;
      if (hero) {
        if (chapterId === 'pimm30-overview') hero.removeAttribute('data-header-overlay-complete');
        else hero.setAttribute('data-header-overlay-complete', '');
      }

      layers.forEach((layer) => {
        const active = layer.dataset.pimm30Layer === chapterId;
        layer.classList.toggle('is-active', active);
        layer.setAttribute('aria-hidden', String(!active));
      });

      navigation.forEach((link) => {
        if (link.dataset.pimm30Nav === chapterId) link.setAttribute('aria-current', 'true');
        else link.removeAttribute('aria-current');
      });

      if (chapterId !== 'pimm30-overview') {
        clearHeroTimer();
        setHeroTone('bright');
      }

      playActiveVideo();

      if (announce && liveStatus) {
        const currentLink = navigation.find((link) => link.dataset.pimm30Nav === chapterId);
        liveStatus.textContent = currentLink?.textContent.trim() || '';
      }
    };

    layers.forEach((layer) => {
      layer.querySelectorAll('[data-pimm30-video]').forEach((video) => {
        video.addEventListener('ended', () => {
          video.classList.remove('is-playing');
          if (layer.dataset.pimm30Layer === 'pimm30-overview') setHeroTone('bright');
          updateControls();
        });
        video.addEventListener('error', () => {
          layer.classList.add('is-video-failed');
          video.classList.remove('is-playing');
          if (layer.dataset.pimm30Layer === 'pimm30-overview') setHeroTone('bright');
          updateControls();
        });
      });
    });

    if (staticExperience) {
      story.classList.add('is-static');
      setHeroTone('bright');
    }

    if ('IntersectionObserver' in window) {
      const chapterObserver = new IntersectionObserver(
        (entries) => {
          const visible = entries
            .filter((entry) => entry.isIntersecting)
            .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
          if (visible) activateChapter(visible.target.dataset.pimm30Chapter, false);
        },
        { rootMargin: '-30% 0px -45%', threshold: [0, 0.15, 0.35, 0.55] }
      );
      chapters.forEach((chapter) => chapterObserver.observe(chapter));

      const storyObserver = new IntersectionObserver(
        ([entry]) => story.classList.toggle('is-in-view', entry.isIntersecting),
        { threshold: 0.01 }
      );
      storyObserver.observe(story);
    }

    pauseButton?.addEventListener('click', () => {
      userPaused = !userPaused;
      if (userPaused) {
        clearHeroTimer();
        pauseAllVideos();
      } else {
        playActiveVideo();
      }
      updateControls();
    });

    navigation.forEach((link) => {
      link.addEventListener('click', () => {
        const chapterId = link.dataset.pimm30Nav;
        activateChapter(chapterId, true);
      });
    });

    replayButton?.addEventListener('click', () => {
      const video = visibleVideo(activeLayer());
      if (!video) return;
      userPaused = false;
      video.load();
      playActiveVideo();
      updateControls();
    });

    desktopMedia.addEventListener('change', () => playActiveVideo());
    reducedMotion.addEventListener('change', () => window.location.reload());
    window.addEventListener('resize', updateSnapEligibility, { passive: true });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) pauseAllVideos();
      else playActiveVideo();
    });

    const hashChapter = chapters.find((chapter) => `#${chapter.id}` === window.location.hash);
    activateChapter(hashChapter?.dataset.pimm30Chapter || activeChapterId);
    updateSnapEligibility();

    if ('ResizeObserver' in window) {
      const chapterSizeObserver = new ResizeObserver(updateSnapEligibility);
      chapters.forEach((chapter) => chapterSizeObserver.observe(chapter));
    }
  };

  const initialiseAllStories = (scope = document) => {
    scope.querySelectorAll(STORY_SELECTOR).forEach(initialiseStory);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initialiseAllStories(), { once: true });
  } else {
    initialiseAllStories();
  }

  document.addEventListener('shopify:section:load', (event) => initialiseAllStories(event.target));
})();
