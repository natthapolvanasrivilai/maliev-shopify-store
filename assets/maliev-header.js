(function () {
  'use strict';

  if (window.__malievHeaderNavigationInit) return;
  window.__malievHeaderNavigationInit = true;

  function initHeader(header) {
    if (!header || header.dataset.mcMegaReady === 'true') return;

    var groups = Array.prototype.slice.call(header.querySelectorAll('[data-mc-mega-menu]'));
    var backdrop = header.querySelector('[data-mc-mega-backdrop]');
    var mobileMenu = header.querySelector('.mc-mobile-menu');
    var mobileSummary = mobileMenu ? mobileMenu.querySelector(':scope > summary') : null;
    var mobileGroups = mobileMenu
      ? Array.prototype.slice.call(mobileMenu.querySelectorAll('.mc-mobile-nav__group'))
      : [];
    var searchDetails = header.querySelector('.mc-actions__search details');
    var localizationDetails = header.querySelector('.mc-localization');
    var pageRegions = Array.prototype.slice.call(document.querySelectorAll('#MainContent, .shopify-section-group-footer-group'));
    var localizationSelectSelector = '[data-header-localization-select]';
    var localizationSubmitting = false;
    var desktopQuery = window.matchMedia('(min-width: 1100px)');
    var reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    var controller = new AbortController();
    var listenerOptions = { signal: controller.signal };
    var overlaySentinel = null;
    var overlayToneObserver = null;
    var overlayFrameRequested = false;

    header.dataset.mcMegaReady = 'true';
    header.mcMegaAbortController = controller;

    function setExpanded(group, expanded) {
      var summary = group.querySelector(':scope > summary');
      if (summary) summary.setAttribute('aria-expanded', String(expanded));
    }

    function setPageInert(inert) {
      pageRegions.forEach(function (region) {
        if (inert) {
          region.setAttribute('inert', '');
        } else {
          region.removeAttribute('inert');
        }
      });
    }

    function syncMobileState() {
      var isOpen = Boolean(mobileMenu && mobileMenu.open && !desktopQuery.matches);
      if (mobileSummary) mobileSummary.setAttribute('aria-expanded', String(isOpen));
      document.body.classList.toggle('mc-mobile-menu-open', isOpen);
      setPageInert(isOpen);
    }

    function resetLocalization() {
      localizationSubmitting = false;

      header.querySelectorAll('[data-header-localization-form]').forEach(function (form) {
        form.dataset.submitting = 'false';
        form.removeAttribute('aria-busy');
        form.classList.remove('mc-localization__form--failed');

        var select = form.querySelector(localizationSelectSelector);
        if (select) select.removeAttribute('aria-disabled');

        var status = form.querySelector('[data-header-localization-status]');
        if (status) {
          status.hidden = true;
          status.textContent = '';
        }
      });
    }

    function syncHeaderState() {
      var hasOpenGroup = desktopQuery.matches && groups.some(function (group) {
        return group.open;
      });
      var hasOpenSearch = Boolean(searchDetails && searchDetails.open);
      var hasOpenLocalization = Boolean(localizationDetails && localizationDetails.open && desktopQuery.matches);
      var hasOpenMobileMenu = Boolean(mobileMenu && mobileMenu.open && !desktopQuery.matches);
      var hasOpenSurface = hasOpenGroup || hasOpenSearch || hasOpenLocalization || hasOpenMobileMenu;

      header.classList.toggle('is-mega-open', hasOpenGroup);
      header.classList.toggle('is-overlay-surface-open', hasOpenSurface);
      if (backdrop) backdrop.hidden = !hasOpenGroup;
    }

    function syncOverlayTone() {
      if (!header.hasAttribute('data-header-overlay')) return;

      var tone = overlaySentinel ? overlaySentinel.getAttribute('data-header-overlay-tone') : null;
      header.classList.toggle('is-overlay-bright', tone === 'bright');
    }

    function syncOverlayPosition() {
      overlayFrameRequested = false;
      if (!header.hasAttribute('data-header-overlay')) return;

      var isPastHero =
        !overlaySentinel ||
        document.documentElement.classList.contains('pimm30-footer-active') ||
        overlaySentinel.hasAttribute('data-header-overlay-complete') ||
        overlaySentinel.getBoundingClientRect().bottom <= header.offsetHeight + 1;
      header.classList.toggle('is-solid', isPastHero);
    }

    function requestOverlaySync() {
      if (overlayFrameRequested || !header.hasAttribute('data-header-overlay')) return;
      overlayFrameRequested = true;
      window.requestAnimationFrame(syncOverlayPosition);
    }

    function refreshOverlaySentinel() {
      if (!header.hasAttribute('data-header-overlay')) return;

      var selector = header.dataset.headerOverlaySentinelSelector || '[data-header-overlay-sentinel]';
      var nextSentinel = document.querySelector(selector);
      if (nextSentinel === overlaySentinel) {
        syncOverlayTone();
        requestOverlaySync();
        return;
      }

      if (overlayToneObserver) overlayToneObserver.disconnect();
      overlaySentinel = nextSentinel;

      if (overlaySentinel && 'MutationObserver' in window) {
        overlayToneObserver = new MutationObserver(function () {
          syncOverlayTone();
          requestOverlaySync();
        });
        overlayToneObserver.observe(overlaySentinel, {
          attributes: true,
          attributeFilter: ['data-header-overlay-tone', 'data-header-overlay-complete'],
        });
      }

      syncOverlayTone();
      syncOverlayPosition();
    }

    function closeGroup(group) {
      if (!group.open) return;
      group.open = false;
      group.classList.remove('mc-nav__group--switched');
      setExpanded(group, false);
    }

    function closeAll(except) {
      groups.forEach(function (group) {
        if (group !== except) closeGroup(group);
      });
      syncHeaderState();
    }

    function toggleDesktopGroup(group) {
      if (!desktopQuery.matches) return;

      if (group.open) {
        closeGroup(group);
        syncHeaderState();
        return;
      }

      var isSwitch = groups.some(function (candidate) {
        return candidate !== group && candidate.open;
      });

      group.classList.toggle('mc-nav__group--switched', isSwitch);
      group.open = true;
      setExpanded(group, true);
      closeAll(group);
    }

    function initMegaPreview(group) {
      var panel = group.querySelector('.mc-nav__panel');
      var feature = panel ? panel.querySelector('[data-mc-menu-feature]') : null;
      var featureLink = feature ? feature.querySelector('.mc-menu-link--featured') : null;
      var featureTitle = featureLink ? featureLink.querySelector('.mc-menu-link__title') : null;
      var featureDescription = featureLink ? featureLink.querySelector('.mc-menu-link__description') : null;
      var featureImage = featureLink ? featureLink.querySelector('.mc-menu-link__media img') : null;
      if (!panel || !feature || !featureLink || !featureTitle) return function () {};

      var defaultState = {
        title: featureTitle.textContent.trim(),
        description: featureDescription ? featureDescription.textContent.trim() : '',
        url: featureLink.getAttribute('href') || '',
        image: featureImage ? featureImage.getAttribute('src') || '' : '',
        imageSrcset: featureImage ? featureImage.getAttribute('srcset') || '' : '',
        imageSizes: featureImage ? featureImage.getAttribute('sizes') || '' : '',
      };
      var activeLink = null;
      var previewSequence = 0;
      var featureAnimation = null;

      function animateFeature() {
        if (reducedMotionQuery.matches || typeof featureLink.animate !== 'function') return;
        if (featureAnimation) featureAnimation.cancel();
        featureAnimation = featureLink.animate([
          { opacity: 0.72, transform: 'translateY(0.2rem)' },
          { opacity: 1, transform: 'translateY(0)' },
        ], {
          duration: 180,
          easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
        });
      }

      function setActiveLink(link) {
        if (activeLink === link) return;
        if (activeLink) activeLink.classList.remove('is-preview-active');
        activeLink = link;
        if (activeLink) activeLink.classList.add('is-preview-active');
      }

      function applyState(state, link) {
        featureLink.setAttribute('href', state.url);
        featureTitle.textContent = state.title;
        feature.setAttribute('aria-label', state.title);
        if (featureDescription) {
          featureDescription.textContent = state.description;
          featureDescription.hidden = !state.description;
        }
        setActiveLink(link);
        animateFeature();
      }

      function applyFeatureImage(state) {
        if (!featureImage) return;

        if (state.imageSrcset) featureImage.setAttribute('srcset', state.imageSrcset);
        else featureImage.removeAttribute('srcset');

        if (state.imageSizes) featureImage.setAttribute('sizes', state.imageSizes);
        else featureImage.removeAttribute('sizes');

        featureImage.setAttribute('src', state.image);
      }

      function showPreview(link) {
        if (!link || link === activeLink) return;
        var state = {
          title: link.dataset.previewTitle || link.textContent.trim(),
          description: link.dataset.previewDescription || '',
          url: link.dataset.previewUrl || link.getAttribute('href') || '',
          image: link.dataset.previewImage || '',
          imageSrcset: '',
          imageSizes: '',
        };
        var sequence = ++previewSequence;
        applyState(state, link);

        if (!featureImage || !state.image || state.image === featureImage.getAttribute('src')) return;
        var image = new Image();
        image.onload = function () {
          if (sequence !== previewSequence) return;
          applyFeatureImage(state);
        };
        image.src = state.image;
      }

      function resetPreview() {
        previewSequence += 1;
        applyState(defaultState, null);
        if (featureImage && defaultState.image) applyFeatureImage(defaultState);
      }

      panel.addEventListener('pointerover', function (event) {
        showPreview(event.target.closest('[data-mc-menu-preview]'));
      }, listenerOptions);
      panel.addEventListener('focusin', function (event) {
        showPreview(event.target.closest('[data-mc-menu-preview]'));
      }, listenerOptions);
      panel.addEventListener('pointerleave', resetPreview, listenerOptions);

      return resetPreview;
    }

    groups.forEach(function (group) {
      var summary = group.querySelector(':scope > summary');
      var resetPreview = initMegaPreview(group);
      setExpanded(group, group.open);

      summary.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        toggleDesktopGroup(group);
      }, listenerOptions);

      summary.addEventListener('click', function (event) {
        if (!desktopQuery.matches) return;
        event.preventDefault();
        toggleDesktopGroup(group);
      }, listenerOptions);

      group.addEventListener('toggle', function () {
        resetPreview();
        if (group.open) {
          closeAll(group);
          setExpanded(group, true);
        } else {
          setExpanded(group, false);
        }
        syncHeaderState();
      }, listenerOptions);
    });

    if (mobileMenu && mobileSummary) {
      mobileSummary.setAttribute('aria-expanded', String(mobileMenu.open));

      mobileMenu.addEventListener('toggle', function () {
        if (!mobileMenu.open) {
          mobileGroups.forEach(function (group) {
            group.open = false;
            setExpanded(group, false);
          });
        }
        syncMobileState();
        syncHeaderState();
      }, listenerOptions);

      mobileGroups.forEach(function (group) {
        setExpanded(group, group.open);
        group.addEventListener('toggle', function () {
          setExpanded(group, group.open);
        }, listenerOptions);
      });
    }

    if (searchDetails) {
      searchDetails.addEventListener('toggle', syncHeaderState, listenerOptions);
    }

    if (localizationDetails) {
      localizationDetails.addEventListener('toggle', syncHeaderState, listenerOptions);
    }

    header.addEventListener('change', function (event) {
      var select = event.target.closest(localizationSelectSelector);
      if (!select || select.value === select.dataset.initialValue) return;

      var form = select.form;
      if (!form || localizationSubmitting || form.dataset.submitting === 'true') return;

      localizationSubmitting = true;
      form.dataset.submitting = 'true';
      form.setAttribute('aria-busy', 'true');
      form.classList.remove('mc-localization__form--failed');
      select.setAttribute('aria-disabled', 'true');

      var status = form.querySelector('[data-header-localization-status]');
      if (status) {
        status.hidden = false;
        status.textContent = form.dataset.loadingLabel || '';
      }

      form.requestSubmit();

      window.setTimeout(function () {
        if (form.dataset.submitting !== 'true') return;

        resetLocalization();
        form.classList.add('mc-localization__form--failed');

        if (status) {
          var submitLabel = form.querySelector('.mc-localization__submit')?.textContent.trim() || '';
          status.hidden = false;
          status.textContent = [form.dataset.errorLabel, submitLabel].filter(Boolean).join('. ');
        }
      }, 15000);
    }, listenerOptions);

    window.addEventListener('pageshow', resetLocalization, listenerOptions);

    if (backdrop) {
      backdrop.addEventListener('click', function () {
        var openGroup = groups.find(function (group) {
          return group.open;
        });
        closeAll();
        if (openGroup) openGroup.querySelector(':scope > summary').focus();
      }, listenerOptions);
    }

    document.addEventListener('pointerdown', function (event) {
      var openGroup = groups.find(function (group) {
        return group.open;
      });
      if (!openGroup || openGroup.contains(event.target)) return;

      var targetGroup = event.target.closest('[data-mc-mega-menu]');
      if (targetGroup && groups.indexOf(targetGroup) !== -1) return;

      closeAll();
    }, listenerOptions);

    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Escape') return;
      if (mobileMenu && mobileMenu.open && !desktopQuery.matches) {
        mobileMenu.open = false;
        syncMobileState();
        mobileSummary.focus();
        return;
      }
      var openGroup = groups.find(function (group) {
        return group.open;
      });
      if (!openGroup) return;

      closeAll();
      openGroup.querySelector(':scope > summary').focus();
    }, listenerOptions);

    desktopQuery.addEventListener('change', function () {
      closeAll();
      if (mobileMenu && mobileMenu.open) mobileMenu.open = false;
      syncMobileState();
      syncHeaderState();
    }, listenerOptions);

    if (header.hasAttribute('data-header-overlay')) {
      window.addEventListener('scroll', requestOverlaySync, { passive: true, signal: controller.signal });
      window.addEventListener('resize', requestOverlaySync, listenerOptions);
      window.addEventListener('maliev:header-overlay-sync', requestOverlaySync, listenerOptions);
      document.addEventListener('shopify:section:load', refreshOverlaySentinel, listenerOptions);
      controller.signal.addEventListener('abort', function () {
        if (overlayToneObserver) overlayToneObserver.disconnect();
      }, { once: true });
      refreshOverlaySentinel();
    }

    syncMobileState();
    syncHeaderState();
    resetLocalization();
  }

  function initAllHeaders(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll('[data-maliev-header]').forEach(initHeader);
    if (scope.matches && scope.matches('[data-maliev-header]')) initHeader(scope);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initAllHeaders(document);
    });
  } else {
    initAllHeaders(document);
  }

  document.addEventListener('shopify:section:load', function (event) {
    initAllHeaders(event.target);
  });

  document.addEventListener('shopify:section:unload', function (event) {
    var header = event.target.matches && event.target.matches('[data-maliev-header]')
      ? event.target
      : event.target.querySelector('[data-maliev-header]');
    if (header && header.mcMegaAbortController) header.mcMegaAbortController.abort();
  });
})();
