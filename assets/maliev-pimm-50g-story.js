(() => {
  const revealAll = (elements) => elements.forEach((element) => element.classList.add('is-in-view'));

  const initCommerce = (page) => {
    const panel = page.querySelector('.pimm50-purchase__panel');
    const select = panel?.querySelector('[data-pimm50-variant-select]');
    const variantData = panel?.querySelector('[data-pimm50-variant-data]');
    const variantTitle = panel?.querySelector('[data-pimm50-variant-title]');
    const variantPrice = panel?.querySelector('[data-pimm50-variant-price]');
    const availability = panel?.querySelector('[data-pimm50-availability]');
    const addButton = panel?.querySelector('[data-pimm50-add-button]');

    if (!panel || !select || !variantData || !variantTitle || !variantPrice || !availability || !addButton) return;

    let variants;
    try {
      variants = JSON.parse(variantData.textContent);
    } catch (_) {
      return;
    }

    const variantsById = new Map(variants.map((variant) => [String(variant.id), variant]));
    const updateVariant = () => {
      const variant = variantsById.get(select.value);
      if (!variant) return;

      variantTitle.textContent = variant.title;
      variantPrice.textContent = variant.price;
      availability.textContent = variant.available ? panel.dataset.pimm50MadeToOrderLabel : panel.dataset.pimm50SoldOutLabel;
      availability.classList.toggle('is-unavailable', !variant.available);
      addButton.disabled = !variant.available;
      addButton.textContent = variant.available ? panel.dataset.pimm50AddToCartLabel : panel.dataset.pimm50SoldOutLabel;
    };

    select.addEventListener('change', updateVariant);
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
        entry.target.classList.add('is-in-view');
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
