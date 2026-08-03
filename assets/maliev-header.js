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
    var pageRegions = Array.prototype.slice.call(document.querySelectorAll('#MainContent, .shopify-section-group-footer-group'));
    var desktopQuery = window.matchMedia('(min-width: 1100px)');
    var controller = new AbortController();
    var listenerOptions = { signal: controller.signal };

    if (!groups.length || !backdrop) return;

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

    function syncHeaderState() {
      var hasOpenGroup = desktopQuery.matches && groups.some(function (group) {
        return group.open;
      });

      header.classList.toggle('is-mega-open', hasOpenGroup);
      backdrop.hidden = !hasOpenGroup;
    }

    function closeGroup(group) {
      if (!group.open) return;
      group.open = false;
      setExpanded(group, false);
    }

    function closeAll(except) {
      groups.forEach(function (group) {
        if (group !== except) closeGroup(group);
      });
      syncHeaderState();
    }

    groups.forEach(function (group) {
      var summary = group.querySelector(':scope > summary');
      setExpanded(group, group.open);

      summary.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        group.open = !group.open;
      }, listenerOptions);

      group.addEventListener('toggle', function () {
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
      }, listenerOptions);

      mobileGroups.forEach(function (group) {
        setExpanded(group, group.open);
        group.addEventListener('toggle', function () {
          setExpanded(group, group.open);
        }, listenerOptions);
      });
    }

    backdrop.addEventListener('click', function () {
      var openGroup = groups.find(function (group) {
        return group.open;
      });
      closeAll();
      if (openGroup) openGroup.querySelector(':scope > summary').focus();
    }, listenerOptions);

    document.addEventListener('pointerdown', function (event) {
      var openGroup = groups.find(function (group) {
        return group.open;
      });
      if (!openGroup || openGroup.contains(event.target)) return;
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
    }, listenerOptions);

    syncMobileState();
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
