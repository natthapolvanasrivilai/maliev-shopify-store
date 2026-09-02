(() => {
  const ELEMENT_NAME = 'pimm-collection-comparison';
  const MODELS = ['30G', '50G'];

  const isPositiveNumber = (value) => Number.isFinite(value) && value > 0;
  const isNonEmptyString = (value) => typeof value === 'string' && value.trim().length > 0;
  const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

  class PimmCollectionComparison extends HTMLElement {
    connectedCallback() {
      this.releaseRuntime();
      this.restoreFallback();
      this.records = null;
      this.recordByModel = null;
      this.presentations = null;
      this.activeModel = undefined;
      this.committedModel = undefined;
      this.controller = new AbortController();
      this.reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

      const presentations = this.capturePresentations();
      if (!presentations
        || !isNonEmptyString(this.dataset.availableLabel)
        || !isNonEmptyString(this.dataset.unavailableLabel)) return;

      const records = this.parseRecords();
      if (!this.hasExactRecordContract(records, presentations)) return;

      this.records = records;
      this.recordByModel = new Map(records.map((record) => [record.model, record]));
      this.presentations = presentations;
      this.bindNavigation();
      this.committedModel = '30G';
      this.applyModel('30G', false);
      this.setEnhancedState(true);
      this.bindCards();
    }

    disconnectedCallback() {
      this.releaseRuntime();
      this.restoreFallback();
      this.controller = null;
    }

    parseRecords() {
      const payload = this.querySelector('[data-pimm-collection-models]');
      if (!payload) return null;

      try {
        return JSON.parse(payload.textContent);
      } catch (_error) {
        return null;
      }
    }

    hasExactRecordContract(records, presentations) {
      if (!Array.isArray(records) || records.length !== MODELS.length) return false;
      if (new Set(records.map((record) => record?.model)).size !== MODELS.length) return false;
      if (!MODELS.every((model) => records.some((record) => record?.model === model))) return false;

      return records.every((record) => {
        if (!isObject(record)) return false;
        if (!Number.isSafeInteger(record.id) || record.id <= 0) return false;
        if (!MODELS.includes(record.model)) return false;
        if (!isNonEmptyString(record.url) || !isNonEmptyString(record.fullPrice)) return false;
        if (typeof record.available !== 'boolean' || !isNonEmptyString(record.leadTime)) return false;

        const trustedRoute = presentations.get(record.model)?.trustedRoute;
        if (!trustedRoute || trustedRoute.variantId !== record.id) return false;

        let url;
        try {
          url = new URL(record.url, window.location.href);
        } catch (_error) {
          return false;
        }
        if (!this.isSafeHttpUrl(url)
          || url.origin !== trustedRoute.origin
          || this.normalizePath(url.pathname) !== trustedRoute.pathname
          || (url.searchParams.get('view') || '') !== trustedRoute.view
          || !this.hasExactVariantQuery(url, record.id)) return false;

        const specifications = record.specifications;
        const envelope = specifications?.moldEnvelopeMm;
        return isObject(specifications)
          && isPositiveNumber(specifications.shotCapacityG)
          && isPositiveNumber(specifications.maxMeltTemperatureC)
          && isObject(envelope)
          && isPositiveNumber(envelope.width)
          && isPositiveNumber(envelope.height)
          && isPositiveNumber(envelope.depth)
          && isPositiveNumber(specifications.maxAirPressureMpa);
      });
    }

    capturePresentations() {
      const dossiers = [...this.querySelectorAll('[data-pimm-collection-inline-dossier]')];
      if (dossiers.length !== MODELS.length) return null;

      const presentations = new Map();
      for (const dossier of dossiers) {
        const model = dossier.dataset.model;
        if (!MODELS.includes(model) || presentations.has(model)) return null;

        const configure = dossier.querySelector('[data-pimm-dossier-configure]');
        const trustedRoute = this.readTrustedRoute(configure);
        const presentation = {
          recommendation: this.readText(dossier, '[data-pimm-dossier-recommendation]'),
          compare: this.readText(dossier, '[data-pimm-dossier-compare]'),
          shotCapacityUnit: this.readMeasurementUnit(dossier, '[data-pimm-dossier-shot-capacity]'),
          moldEnvelopeUnit: this.readEnvelopeUnit(dossier, '[data-pimm-dossier-mold-envelope]'),
          meltTemperatureUnit: this.readMeasurementUnit(dossier, '[data-pimm-dossier-melt-temperature]'),
          airPressureUnit: this.readMeasurementUnit(dossier, '[data-pimm-dossier-air-pressure]'),
          configure: configure?.textContent?.trim() ?? '',
          trustedRoute,
        };
        if (!trustedRoute
          || Object.entries(presentation)
            .filter(([key]) => key !== 'trustedRoute')
            .some(([, value]) => !isNonEmptyString(value))) return null;
        presentations.set(model, presentation);
      }

      return MODELS.every((model) => presentations.has(model)) ? presentations : null;
    }

    readText(root, selector) {
      return root.querySelector(selector)?.textContent?.trim() ?? '';
    }

    readMeasurementUnit(root, selector) {
      return this.readText(root, selector).replace(/^[-+\d.,]+\s*/, '').trim();
    }

    readEnvelopeUnit(root, selector) {
      return this.readText(root, selector)
        .replace(/^[-+\d.,]+\s*[×x]\s*[-+\d.,]+\s*[×x]\s*[-+\d.,]+\s*/i, '')
        .trim();
    }

    readTrustedRoute(anchor) {
      const href = anchor?.getAttribute?.('href') || anchor?.href;
      if (!isNonEmptyString(href)) return null;

      let url;
      try {
        url = new URL(href, window.location.href);
      } catch (_error) {
        return null;
      }

      const currentUrl = new URL(window.location.href);
      if (!this.isSafeHttpUrl(url)
        || url.origin !== currentUrl.origin
        || !/(?:^|\/)products\/[^/]+\/?$/.test(url.pathname)
        || !this.hasExactVariantQuery(url)) return null;

      return {
        href,
        origin: url.origin,
        pathname: this.normalizePath(url.pathname),
        variantId: Number(url.searchParams.get('variant')),
        view: url.searchParams.get('view') || '',
      };
    }

    isSafeHttpUrl(url) {
      return (url.protocol === 'http:' || url.protocol === 'https:')
        && url.username === ''
        && url.password === ''
        && url.hash === '';
    }

    hasExactVariantQuery(url, expectedId = null) {
      const entries = [...url.searchParams.entries()];
      if (url.searchParams.getAll('variant').length !== 1
        || entries.some(([key]) => key !== 'variant' && key !== 'view')
        || url.searchParams.getAll('view').length > 1
        || (url.searchParams.has('view') && url.searchParams.get('view') !== 'pimm-configurator')) return false;
      const variantId = Number(url.searchParams.get('variant'));
      if (!Number.isSafeInteger(variantId) || variantId <= 0) return false;
      return expectedId === null || variantId === expectedId;
    }

    normalizePath(pathname) {
      return pathname.length > 1 ? pathname.replace(/\/$/, '') : pathname;
    }

    navigationHref(route) {
      const current = new URL(window.location.href);
      current.hash = '';
      const keys = current.searchParams.getAll('preview_key');
      if (this.dataset.previewNavigation !== 'true'
        || !this.isSafeHttpUrl(current)
        || !/^\/(?:[a-z]{2}(?:-[a-z0-9]{2,8})?\/)?products_preview\/?$/i.test(current.pathname)
        || current.searchParams.getAll('view').length !== 1
        || current.searchParams.get('view') !== 'pimm-collection-preview'
        || keys.length !== 1 || !/^[a-z0-9_-]{16,128}$/i.test(keys[0])) return route.href;

      const target = new URL(current.pathname, current.origin);
      target.searchParams.set('preview_key', keys[0]);
      target.searchParams.set('view', 'pimm-configurator');
      target.searchParams.set('variant', String(route.variantId));
      return target.pathname + target.search;
    }

    setNavigationHref(anchor, route) {
      if (!anchor) return;
      this.originalNavigation ??= new Map();
      if (!this.originalNavigation.has(anchor)) {
        this.originalNavigation.set(anchor, anchor.getAttribute('href') || anchor.href);
      }
      anchor.href = this.navigationHref(route);
    }

    bindNavigation() {
      for (const card of this.querySelectorAll('[data-pimm-collection-card]')) {
        const route = this.presentations.get(card.dataset.model)?.trustedRoute;
        if (route) this.setNavigationHref(card.querySelector('.pimm-collection__card-actions a'), route);
      }
      for (const dossier of this.querySelectorAll('[data-pimm-collection-inline-dossier]')) {
        const route = this.presentations.get(dossier.dataset.model)?.trustedRoute;
        if (route) this.setNavigationHref(dossier.querySelector('[data-pimm-dossier-configure]'), route);
      }
    }

    bindCards() {
      for (const card of this.querySelectorAll('[data-pimm-collection-card]')) {
        const model = card.dataset.model;
        if (!this.recordByModel.has(model)) continue;
        const signal = this.controller.signal;
        const video = card.querySelector('[data-pimm-collection-video]');
        video?.addEventListener('ended', () => this.stopSequence(card), { signal });
        video?.addEventListener('error', () => this.stopSequence(card), { signal });

        card.addEventListener('pointerenter', (event) => {
          if (event.pointerType === 'touch') return;
          this.previewModel(model);
          this.playSequence(card);
        }, { signal });

        card.addEventListener('pointerleave', (event) => {
          if (event.pointerType === 'touch') return;
          this.restoreCommittedModel();
          this.stopSequence(card, true);
        }, { signal });

        card.addEventListener('focusin', () => {
          this.previewModel(model);
          this.playSequence(card);
        }, { signal });

        card.addEventListener('focusout', (event) => {
          if (card.contains(event.relatedTarget)) return;
          this.restoreCommittedModel();
          this.stopSequence(card, true);
        }, { signal });

        card.addEventListener('click', () => {
          this.commitModel(model);
          this.playSequence(card);
        }, { signal });
      }
      this.reduceMotion?.addEventListener?.('change', () => {
        if (this.reduceMotion.matches) {
          for (const card of this.querySelectorAll('[data-pimm-collection-card]')) this.stopSequence(card);
        }
      }, { signal: this.controller.signal });
    }

    setEnhancedState(enhanced) {
      for (const card of this.querySelectorAll('[data-pimm-collection-card]')) {
        if (enhanced) card.setAttribute('tabindex', '0');
        else card.removeAttribute('tabindex');

        const select = card.querySelector('[data-pimm-collection-select]');
        if (!select) continue;
        select.hidden = !enhanced;
        select.disabled = !enhanced;
      }
    }

    restoreFallback() {
      if (this.recordByModel?.has('30G') && this.presentations?.has('30G')) {
        this.committedModel = '30G';
        this.applyModel('30G', false);
      } else {
        for (const card of this.querySelectorAll?.('[data-pimm-collection-card]') ?? []) {
          const active = card.dataset.model === '30G';
          card.classList.toggle('is-active', active);
          card.setAttribute('aria-current', active ? 'true' : 'false');
        }
        for (const dossier of this.querySelectorAll?.('[data-pimm-collection-inline-dossier]') ?? []) {
          const active = dossier.dataset.model === '30G';
          dossier.classList.toggle('is-active', active);
          dossier.hidden = !active;
        }
      }
      this.setEnhancedState(false);
      for (const [anchor, href] of this.originalNavigation ?? []) anchor.href = href;
      this.originalNavigation?.clear();
    }

    commitModel(model, announce = true) {
      if (!this.recordByModel?.has(model)) return;
      this.committedModel = model;
      this.applyModel(model, announce);
    }

    previewModel(model) {
      if (!this.recordByModel?.has(model)) return;
      this.applyModel(model, false);
    }

    restoreCommittedModel() {
      if (!this.committedModel) return;
      this.applyModel(this.committedModel, false);
    }

    applyModel(model, announce = false) {
      const record = this.recordByModel?.get(model);
      const presentation = this.presentations?.get(model);
      if (!record || !presentation) return;
      this.activeModel = model;

      for (const card of this.querySelectorAll('[data-pimm-collection-card]')) {
        const active = card.dataset.model === model;
        card.classList.toggle('is-active', active);
        card.setAttribute('aria-current', active ? 'true' : 'false');
      }

      for (const dossier of this.querySelectorAll('[data-pimm-collection-dossier]')) {
        const inline = Object.hasOwn(dossier.dataset, 'pimmCollectionInlineDossier');
        if (inline) {
          const active = dossier.dataset.model === model;
          dossier.classList.toggle('is-active', active);
          dossier.hidden = !active;
          if (!active) continue;
        } else {
          dossier.dataset.model = model;
        }
        this.updateDossier(dossier, record, presentation);
      }

      if (announce) this.announceModel(model);
    }

    updateDossier(dossier, record, presentation) {
      this.writeText(dossier, '[data-pimm-dossier-model]', record.model);
      this.writeText(dossier, '[data-pimm-dossier-recommendation]', presentation.recommendation);
      this.writeText(dossier, '[data-pimm-dossier-compare]', presentation.compare);
      this.writeText(dossier, '[data-pimm-dossier-price]', record.fullPrice);
      this.writeText(
        dossier,
        '[data-pimm-dossier-availability]',
        record.available ? this.dataset.availableLabel : this.dataset.unavailableLabel,
      );
      this.writeText(dossier, '[data-pimm-dossier-lead-time]', record.leadTime);
      this.writeText(dossier, '[data-pimm-dossier-shot-capacity]', `${record.specifications.shotCapacityG} ${presentation.shotCapacityUnit}`);
      this.writeText(
        dossier,
        '[data-pimm-dossier-mold-envelope]',
        `${record.specifications.moldEnvelopeMm.width} × ${record.specifications.moldEnvelopeMm.height} × ${record.specifications.moldEnvelopeMm.depth} ${presentation.moldEnvelopeUnit}`,
      );
      this.writeText(dossier, '[data-pimm-dossier-melt-temperature]', `${record.specifications.maxMeltTemperatureC} ${presentation.meltTemperatureUnit}`);
      this.writeText(dossier, '[data-pimm-dossier-air-pressure]', `${record.specifications.maxAirPressureMpa} ${presentation.airPressureUnit}`);

      const configure = dossier.querySelector('[data-pimm-dossier-configure]');
      if (configure) {
        this.setNavigationHref(configure, presentation.trustedRoute);
        configure.textContent = presentation.configure;
      }
    }

    writeText(root, selector, value) {
      const target = root.querySelector(selector);
      if (target) target.textContent = value;
    }

    announceModel(model) {
      const announcement = this.querySelector('[data-pimm-collection-announcement]');
      const template = announcement?.dataset.announcementTemplate;
      if (!announcement || !isNonEmptyString(template)) return;
      announcement.textContent = template.replace('__MODEL__', model);
    }

    playSequence(card) {
      this.stopSequence(card, true);
      if (this.reduceMotion?.matches) return;
      const video = card.querySelector('[data-pimm-collection-video]');
      if (!video) return;
      video.muted = true;
      video.loop = false;
      const attempt = {};
      video.pimmPlaybackAttempt = attempt;
      video.play()?.then(() => {
        if (video.pimmPlaybackAttempt === attempt && !video.paused) video.classList.add('is-playing');
      }).catch(() => {
        if (video.pimmPlaybackAttempt === attempt) this.stopSequence(card);
      });
    }

    stopSequence(card, reset = true) {
      const video = card.querySelector('[data-pimm-collection-video]');
      if (video) {
        video.pimmPlaybackAttempt = null;
        video.pause();
        video.classList.remove('is-playing');
        if (reset) {
          try { video.currentTime = 0; } catch (_) { /* Metadata may not have arrived. */ }
        }
      }
      if (reset) this.exposeFrame(card, 'front');
    }

    exposeFrame(card, requestedFrame) {
      const frames = [...card.querySelectorAll('[data-pimm-collection-frame]')];
      const target = frames.find((frame) => frame.dataset.pimmCollectionFrame === requestedFrame)
        ?? frames.find((frame) => frame.dataset.pimmCollectionFrame === 'front');
      if (!target) return;

      for (const frame of frames) {
        const active = frame === target;
        frame.hidden = !active;
        frame.setAttribute('aria-hidden', active ? 'false' : 'true');
        frame.classList.toggle('is-active', active);
      }
    }

    releaseRuntime() {
      this.controller?.abort();
      for (const card of this.querySelectorAll?.('[data-pimm-collection-card]') ?? []) {
        this.stopSequence(card, true);
      }
    }
  }

  if (!customElements.get(ELEMENT_NAME)) {
    customElements.define(ELEMENT_NAME, PimmCollectionComparison);
  }
})();
