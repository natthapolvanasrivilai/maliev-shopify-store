(function () {
  'use strict';

  if (window.__malievHeaderNavigationInit) return;
  window.__malievHeaderNavigationInit = true;

  function initHeader(header) {
    if (!header || header.dataset.mcMegaReady === 'true') return;

    var groups = Array.prototype.slice.call(header.querySelectorAll('[data-mc-mega-menu]'));
    var backdrop = header.querySelector('[data-mc-mega-backdrop]');
    var desktopQuery = window.matchMedia('(min-width: 990px)');
    var controller = new AbortController();
    var listenerOptions = { signal: controller.signal };

    if (!groups.length || !backdrop) return;

    header.dataset.mcMegaReady = 'true';
    header.mcMegaAbortController = controller;

    function setExpanded(group, expanded) {
      var summary = group.querySelector(':scope > summary');
      if (summary) summary.setAttribute('aria-expanded', String(expanded));
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
      var openGroup = groups.find(function (group) {
        return group.open;
      });
      if (!openGroup) return;

      closeAll();
      openGroup.querySelector(':scope > summary').focus();
    }, listenerOptions);

    desktopQuery.addEventListener('change', function () {
      closeAll();
    }, listenerOptions);
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
