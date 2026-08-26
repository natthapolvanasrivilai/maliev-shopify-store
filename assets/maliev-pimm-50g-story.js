(() => {
  const motionDependencies = {
    'pneumatic-flow': 'capacity-media',
    'melt-proof': 'melt-media',
    'heating-readouts': 'heating-media',
    'mold-dimension': 'mold-media',
    'comparison-facts': 'comparison-machines',
    'purchase-panel': 'purchase-media',
  };

  const completeMotionTarget = (element) => {
    if (element.dataset.pimm50MotionState === 'complete') return;
    element.dataset.pimm50MotionState = 'complete';
    element.dispatchEvent(new CustomEvent('pimm50:motioncomplete', {
      bubbles: true,
      detail: { role: element.dataset.pimm50Motion },
    }));
  };

  const transitionMilliseconds = (style) => {
    const parseTime = (value) => value.trim().endsWith('ms')
      ? Number.parseFloat(value)
      : Number.parseFloat(value) * 1_000;
    const durations = style.transitionDuration.split(',').map(parseTime);
    const delays = style.transitionDelay.split(',').map(parseTime);
    return Math.max(0, ...durations.map((duration, index) => duration + delays[index % delays.length]));
  };

  const transitionPropertyMilliseconds = (style, propertyName) => {
    const parseTime = (value) => value.trim().endsWith('ms')
      ? Number.parseFloat(value)
      : Number.parseFloat(value) * 1_000;
    const properties = style.transitionProperty.split(',').map((value) => value.trim());
    const durations = style.transitionDuration.split(',').map(parseTime);
    const delays = style.transitionDelay.split(',').map(parseTime);
    const propertyIndex = Math.max(0, properties.findIndex((property) => property === propertyName || property === 'all'));
    return durations[propertyIndex % durations.length] + delays[propertyIndex % delays.length];
  };

  const maximumTransitionMilliseconds = (element) => Math.max(0, ...[element, ...element.querySelectorAll('*')].flatMap((target) => [
    transitionMilliseconds(getComputedStyle(target)),
    transitionMilliseconds(getComputedStyle(target, '::before')),
    transitionMilliseconds(getComputedStyle(target, '::after')),
  ]));

  const revealMotionTarget = (element, { immediate = false } = {}) => {
    if (element.dataset.pimm50MotionState) return;

    if (immediate) {
      element.classList.add('is-in-view');
      completeMotionTarget(element);
      return;
    }

    let fallbackTimer;
    let expectedDuration = 0;
    const cleanup = () => {
      element.removeEventListener('transitionend', onTransitionEnd);
      window.clearTimeout(fallbackTimer);
    };
    const finish = () => {
      cleanup();
      completeMotionTarget(element);
    };
    const onTransitionEnd = (event) => {
      const style = getComputedStyle(event.target, event.pseudoElement || null);
      if (transitionPropertyMilliseconds(style, event.propertyName) >= expectedDuration - 1) finish();
    };

    element.addEventListener('transitionend', onTransitionEnd);
    element.dataset.pimm50MotionState = 'running';
    element.classList.add('is-in-view');
    expectedDuration = maximumTransitionMilliseconds(element);
    if (expectedDuration <= 0) {
      finish();
      return;
    }
    fallbackTimer = window.setTimeout(finish, Math.min(expectedDuration + 100, 900));
  };

  const revealAll = (elements) => elements.forEach((element) => revealMotionTarget(element, { immediate: true }));

  const revealWhenReady = (element, page) => {
    const dependencyRole = motionDependencies[element.dataset.pimm50Motion];
    if (!dependencyRole) {
      revealMotionTarget(element);
      return;
    }

    const dependency = page.querySelector(`[data-pimm50-motion="${dependencyRole}"]`);
    if (!dependency || dependency.dataset.pimm50MotionState === 'complete') {
      revealMotionTarget(element);
      return;
    }

    dependency.addEventListener('pimm50:motioncomplete', () => revealMotionTarget(element), { once: true });
    revealMotionTarget(dependency);
  };

  const initCommerce = (page) => {
    const panel = page.querySelector('.pimm50-purchase__panel');
    const select = panel?.querySelector('[data-pimm50-variant-select]');
    const variantData = panel?.querySelector('[data-pimm50-variant-data]');
    const variantTitle = panel?.querySelector('[data-pimm50-variant-title]');
    const variantPrice = panel?.querySelector('[data-pimm50-variant-price]');
    const availability = panel?.querySelector('[data-pimm50-availability]');
    const status = panel?.querySelector('[data-pimm50-variant-status]');
    const addButton = panel?.querySelector('[data-pimm50-add-button]');

    if (!panel || !select || !variantData || !variantTitle || !variantPrice || !availability || !addButton) return;

    let variants;
    try {
      variants = JSON.parse(variantData.textContent);
    } catch (_) {
      return;
    }

    const variantsById = new Map(variants.map((variant) => [String(variant.id), variant]));
    let renderedVariantId;
    const updateVariant = ({ announce = false } = {}) => {
      const variant = variantsById.get(select.value);
      if (!variant) return;

      const variantId = String(variant.id);
      const changed = renderedVariantId !== variantId;
      const availabilityLabel = variant.available ? panel.dataset.pimm50MadeToOrderLabel : panel.dataset.pimm50SoldOutLabel;

      variantTitle.textContent = variant.title;
      variantPrice.textContent = variant.price;
      availability.textContent = availabilityLabel;
      availability.classList.toggle('is-unavailable', !variant.available);
      addButton.disabled = !variant.available;
      addButton.textContent = variant.available ? panel.dataset.pimm50AddToCartLabel : panel.dataset.pimm50SoldOutLabel;

      if (announce && changed && status) {
        status.textContent = `${variant.title}. ${variant.price}. ${availabilityLabel}`;
      }
      renderedVariantId = variantId;
    };

    select.addEventListener('change', () => updateVariant({ announce: true }));
    updateVariant();
  };

  const init = (page) => {
    if (page.dataset.ready === 'true') return;
    page.dataset.ready = 'true';
    initCommerce(page);

    const motionElements = [...page.querySelectorAll('[data-pimm50-motion]')];
    const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reducedMotion || !('IntersectionObserver' in window)) {
      revealAll(motionElements);
      return;
    }

    const observer = new IntersectionObserver((entries, activeObserver) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        revealWhenReady(entry.target, page);
        activeObserver.unobserve(entry.target);
      });
    }, { rootMargin: '0px 0px -8%', threshold: .12 });

    motionElements.forEach((element) => observer.observe(element));
  };

  const start = (root = document) => root.querySelectorAll('[data-pimm50-page]').forEach(init);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => start(), { once: true });
  } else {
    start();
  }

  document.addEventListener('shopify:section:load', (event) => start(event.target));
})();
