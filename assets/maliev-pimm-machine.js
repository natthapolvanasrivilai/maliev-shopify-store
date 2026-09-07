(() => {
  if (customElements.get('pimm-machine-product')) return;

  class PimmMachineProduct extends HTMLElement {
    connectedCallback() {
      if (this.controllerConnected) return;
      this.controllerConnected = true;

      const payload = this.querySelector('[data-pimm-variant-data]');
      this.invalidMessage = payload?.dataset.pimmInvalidMessage || '';

      try {
        this.variants = JSON.parse(payload?.textContent || '[]');
      } catch (_error) {
        this.variants = [];
      }

      this.payloadContractValid = this.hasExactPayloadContract(this.variants);
      this.decodedHeroModels = new Set();
      this.mediaTransitionToken = 0;
      this.mediaTransitionFrame = 0;
      this.mediaTransitionTimer = 0;
      this.selectedMediaModel = [...this.querySelectorAll('[data-pimm-media-model]')].find(
        (group) => !group.hidden && group.ariaHidden !== 'true',
      )?.dataset.pimmMediaModel || '';
      this.addEventListener('change', (event) => {
        if (event.target.matches('[data-pimm-model-radio]')) {
          this.selectVariant(Number(event.target.value));
        }
      });

      this.initializePrecisionReveal();
      if (!this.payloadContractValid) this.failClosed();
    }

    disconnectedCallback() {
      this.revealObserver?.disconnect();
    }

    initializePrecisionReveal() {
      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (reducedMotion || typeof window.IntersectionObserver !== 'function') return;

      this.revealObserver = new window.IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.dataset.pimmRevealState = 'visible';
          this.revealObserver.unobserve(entry.target);
        });
      }, {
        rootMargin: '0px 0px -12% 0px',
        threshold: 0.18,
      });

      this.classList.add('pimm-motion-ready');
      this.observeVisibleStoryChapters();
    }

    observeVisibleStoryChapters() {
      if (!this.revealObserver) return;

      this.querySelectorAll('[data-pimm-reveal]').forEach((chapter) => {
        if (chapter.closest('[data-pimm-story-model][hidden]')) return;
        if (chapter.dataset.pimmRevealState === 'visible') return;
        chapter.dataset.pimmRevealState = 'pending';
        this.revealObserver.observe(chapter);
      });
    }

    hasExactPayloadContract(variants) {
      const pageModel = this.dataset.pageModel;
      if (Array.isArray(variants) && variants.length === 1 && (pageModel === '30G' || pageModel === '50G')) {
        return variants[0]?.model === pageModel
          && Number.isInteger(variants[0]?.id)
          && variants[0].id > 0;
      }
      return (
        Array.isArray(variants) &&
        variants.length === 2 &&
        variants[0]?.model === '30G' &&
        variants[1]?.model === '50G' &&
        Number.isInteger(variants[0]?.id) &&
        Number.isInteger(variants[1]?.id) &&
        variants[0].id > 0 &&
        variants[1].id > 0 &&
        variants[0].id !== variants[1].id
      );
    }

    hasValidRecordContract(variant) {
      const specifications = variant?.specifications;
      const mold = specifications?.mold_envelope_mm;
      const expectedStoryAssetSet = variant?.model === '30G'
        ? 'pimm-master-20260901-r05-30g'
        : variant?.model === '50G'
          ? 'pimm-master-20260901-r05-50g'
          : '';

      return (
        this.payloadContractValid &&
        variant?.contractValid === true &&
        (variant.model === '30G' || variant.model === '50G') &&
        variant.storyAssetSet === expectedStoryAssetSet &&
        typeof variant.fullPrice === 'string' &&
        typeof variant.leadTime === 'string' &&
        typeof variant.statusText === 'string' &&
        typeof variant.announcementText === 'string' &&
        variant.announcementText.length > 0 &&
        typeof variant.available === 'boolean' &&
        specifications?.schema_version === 1 &&
        specifications.model === variant.model &&
        specifications.shot_capacity_g > 0 &&
        specifications.max_melt_temperature_c > 0 &&
        specifications.max_air_pressure_mpa > 0 &&
        mold?.width > 0 &&
        mold.height > 0 &&
        mold.depth > 0
      );
    }

    isMediaItem(item, width, height) {
      return (
        typeof item?.src === 'string' &&
        item.src.length > 0 &&
        typeof item.alt === 'string' &&
        item.alt.length > 0 &&
        item.width === width &&
        item.height === height
      );
    }

    resolveMedia(variant) {
      const source = variant?.media;
      const hero = source?.hero;
      if (!this.isMediaItem(hero, 1800, 2200)) return null;

      const resolved = { hero: { ...hero } };
      for (const slot of ['overview', 'engineering', 'tooling']) {
        const item = source?.[slot];
        const missing = !item || !item.src || !item.alt;
        if (missing) {
          resolved[slot] = { ...hero };
        } else if (this.isMediaItem(item, 2400, 1800)) {
          resolved[slot] = { ...item };
        } else {
          return null;
        }
      }
      return resolved;
    }

    selectVariant(variantId) {
      const variant = this.variants.find((candidate) => candidate.id === variantId);
      if (!variant) {
        this.failClosed();
        return;
      }

      const contractValid = this.hasValidRecordContract(variant);
      this.querySelectorAll('[data-pimm-model-radio]').forEach((radio) => {
        radio.checked = Number(radio.value) === variant.id;
      });

      const selectedModel = this.querySelector('[data-pimm-selected-model]');
      if (selectedModel) selectedModel.textContent = variant.model;

      this.querySelectorAll('[data-pimm-model-value]').forEach((node) => {
        const field = node.dataset.pimmModelValue;
        node.textContent = contractValid ? String(variant[field] ?? '') : this.invalidMessage;
      });

      const status = this.querySelector('[data-pimm-variant-status]');
      const announcement = contractValid ? variant.announcementText : this.invalidMessage;
      if (status && status.textContent.trim() !== announcement) status.textContent = announcement;

      this.applyMedia(variant, contractValid);
      this.showOnlyStory(contractValid ? variant.model : '');
      if (contractValid) this.decodeSelectedHero(variant.model);
      this.updateUrl(variant.id);
    }

    applyMedia(variant, contractValid) {
      if (!contractValid) {
        this.stopMediaTransition('');
        this.selectedMediaModel = '';
        this.updateSpecifications(variant, false);
        return;
      }

      this.transitionMediaTo(variant.model);

      this.updateSpecifications(variant, contractValid);
    }

    transitionMediaTo(model) {
      const previousModel = this.selectedMediaModel;
      this.stopMediaTransition(previousModel);

      if (!previousModel || previousModel === model || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        this.showOnlyMedia(model);
        this.selectedMediaModel = model;
        return;
      }

      const token = ++this.mediaTransitionToken;
      this.querySelectorAll('[data-pimm-media-model]').forEach((group) => {
        const isIncoming = group.dataset.pimmMediaModel === model;
        const isOutgoing = group.dataset.pimmMediaModel === previousModel;
        if (isIncoming) {
          group.hidden = false;
          group.ariaHidden = 'false';
          group.inert = false;
          group.dataset.pimmMediaState = 'entering';
        } else if (isOutgoing) {
          group.hidden = false;
          group.ariaHidden = 'true';
          group.inert = true;
          group.dataset.pimmMediaState = 'exiting';
        } else {
          group.hidden = true;
          group.ariaHidden = 'true';
          group.inert = true;
          delete group.dataset.pimmMediaState;
        }
      });

      this.mediaTransitionFrame = requestAnimationFrame(() => {
        if (token !== this.mediaTransitionToken) return;
        this.querySelectorAll('[data-pimm-media-model]').forEach((group) => {
          if (group.dataset.pimmMediaModel === model) delete group.dataset.pimmMediaState;
        });
      });
      this.mediaTransitionTimer = window.setTimeout(() => {
        if (token !== this.mediaTransitionToken) return;
        this.showOnlyMedia(model);
        this.mediaTransitionTimer = 0;
      }, 180);
      this.selectedMediaModel = model;
    }

    stopMediaTransition(settleModel) {
      this.mediaTransitionToken += 1;
      if (this.mediaTransitionFrame) cancelAnimationFrame(this.mediaTransitionFrame);
      if (this.mediaTransitionTimer) window.clearTimeout(this.mediaTransitionTimer);
      this.mediaTransitionFrame = 0;
      this.mediaTransitionTimer = 0;
      this.showOnlyMedia(settleModel);
    }

    showOnlyMedia(model) {
      this.querySelectorAll('[data-pimm-media-model]').forEach((group) => {
        const hidden = !model || group.dataset.pimmMediaModel !== model;
        group.hidden = hidden;
        group.ariaHidden = String(hidden);
        group.inert = hidden;
        delete group.dataset.pimmMediaState;
      });
    }

    showOnlyStory(model) {
      this.querySelectorAll('[data-pimm-story-model]').forEach((story) => {
        const hidden = !model || story.dataset.pimmStoryModel !== model;
        story.hidden = hidden;
        story.ariaHidden = String(hidden);
        story.inert = hidden;
      });
      this.observeVisibleStoryChapters();
    }

    updateSpecifications(variant, contractValid) {
      const specifications = variant?.specifications;
      const mold = specifications?.mold_envelope_mm;
      const values = contractValid
        ? {
            shot_capacity_g: [String(specifications.shot_capacity_g), `${specifications.shot_capacity_g} g`],
            max_melt_temperature_c: [
              String(specifications.max_melt_temperature_c),
              `${specifications.max_melt_temperature_c} °C`,
            ],
            mold_envelope: [
              `${mold.width} × ${mold.height} × ${mold.depth}`,
              `${mold.width} × ${mold.height} × ${mold.depth} mm`,
            ],
            max_air_pressure_mpa: [
              String(specifications.max_air_pressure_mpa),
              `${specifications.max_air_pressure_mpa} MPa`,
            ],
          }
        : {};

      this.querySelectorAll('[data-pimm-spec]').forEach((node) => {
        const value = values[node.dataset.pimmSpec];
        node.textContent = value?.[0] ?? this.invalidMessage;
        node.ariaLabel = value?.[1] ?? this.invalidMessage;
      });

      this.querySelectorAll('[data-pimm-spec-unit]').forEach((unit) => {
        unit.hidden = !contractValid;
        unit.ariaHidden = 'true';
      });
    }

    decodeSelectedHero(model) {
      if (this.decodedHeroModels.has(model)) return;

      const hero = [...this.querySelectorAll('[data-pimm-media-model]')].find(
        (group) =>
          group.dataset.pimmMediaModel === model &&
          group.dataset.pimmMediaSlot === 'hero' &&
          !group.hidden,
      );
      const image = hero?.querySelector('img');
      if (typeof image?.decode !== 'function') return;

      this.decodedHeroModels.add(model);
      const decoding = image.decode();
      if (typeof decoding?.catch === 'function') decoding.catch(() => {});
    }

    updateUrl(variantId) {
      const url = new URL(window.location.href);
      url.searchParams.set('variant', String(variantId));
      window.history.replaceState({}, '', url);
    }

    failClosed() {
      const status = this.querySelector('[data-pimm-variant-status]');
      if (status) status.textContent = this.invalidMessage;

      this.applyMedia({ model: '', specifications: {} }, false);
    }
  }

  customElements.define('pimm-machine-product', PimmMachineProduct);
})();
