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
      this.addEventListener('change', (event) => {
        if (event.target.matches('[data-pimm-model-radio]')) {
          this.selectVariant(Number(event.target.value));
        }
      });

      if (!this.payloadContractValid) this.failClosed();
    }

    hasExactPayloadContract(variants) {
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
      const media = variant?.media;

      return (
        this.payloadContractValid &&
        variant?.contractValid === true &&
        (variant.model === '30G' || variant.model === '50G') &&
        typeof variant.depositPrice === 'string' &&
        typeof variant.fullPrice === 'string' &&
        typeof variant.leadTime === 'string' &&
        typeof variant.statusText === 'string' &&
        typeof variant.available === 'boolean' &&
        specifications?.schema_version === 1 &&
        specifications.model === variant.model &&
        specifications.shot_capacity_g > 0 &&
        specifications.max_melt_temperature_c > 0 &&
        specifications.max_air_pressure_mpa > 0 &&
        mold?.width > 0 &&
        mold.height > 0 &&
        mold.depth > 0 &&
        ['hero', 'overview', 'engineering', 'tooling'].every((slot) => {
          const item = media?.[slot];
          return (
            typeof item?.src === 'string' &&
            item.src.length > 0 &&
            typeof item.alt === 'string' &&
            item.alt.length > 0
          );
        })
      );
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
      if (status) status.textContent = contractValid ? variant.statusText : this.invalidMessage;

      const deposit = this.querySelector('[data-pimm-deposit-action]');
      if (deposit) deposit.disabled = !contractValid || !variant.available;

      this.applyMedia(variant, contractValid);
      if (contractValid) this.decodeSelectedHero(variant.model);
      this.updateUrl(variant.id);
    }

    applyMedia(variant, contractValid) {
      this.querySelectorAll('[data-pimm-media-model]').forEach((group) => {
        const hidden = !contractValid || group.dataset.pimmMediaModel !== variant.model;
        group.hidden = hidden;
        group.ariaHidden = String(hidden);
      });

      this.updateSpecifications(variant, contractValid);
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
      const deposit = this.querySelector('[data-pimm-deposit-action]');
      if (deposit) deposit.disabled = true;

      const status = this.querySelector('[data-pimm-variant-status]');
      if (status) status.textContent = this.invalidMessage;

      this.applyMedia({ model: '', specifications: {} }, false);
    }
  }

  customElements.define('pimm-machine-product', PimmMachineProduct);
})();
