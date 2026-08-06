(() => {
  const selector = '[data-footer-localization-select]';
  const disclosureSelector = '[data-footer-disclosure]';
  const mobileQuery = window.matchMedia('(max-width: 640px)');
  let localizationSubmitting = false;

  const syncDisclosures = () => {
    document.querySelectorAll(disclosureSelector).forEach((disclosure) => {
      disclosure.open = !mobileQuery.matches;

      const summary = disclosure.querySelector('summary');
      if (summary) summary.tabIndex = mobileQuery.matches ? 0 : -1;
    });
  };

  const resetLocalization = () => {
    localizationSubmitting = false;

    document.querySelectorAll('[data-footer-localization-form]').forEach((form) => {
      form.dataset.submitting = 'false';
      form.removeAttribute('aria-busy');
      form.classList.remove('mc-footer__localization-form--failed');

      const status = form.querySelector('[data-footer-localization-status]');
      if (status) {
        status.hidden = true;
        status.textContent = '';
      }
    });

    document.querySelectorAll(selector).forEach((select) => select.removeAttribute('aria-disabled'));
    document.querySelector('.mc-footer__localization')?.classList.remove('mc-footer__localization--busy');
  };

  syncDisclosures();
  mobileQuery.addEventListener('change', syncDisclosures);
  document.addEventListener('shopify:section:load', syncDisclosures);
  window.addEventListener('pageshow', resetLocalization);

  document.addEventListener('change', (event) => {
    const select = event.target.closest(selector);

    if (!select || select.value === select.dataset.initialValue) return;

    const form = select.form;

    if (!form || localizationSubmitting || form.dataset.submitting === 'true') return;

    localizationSubmitting = true;
    form.dataset.submitting = 'true';
    form.setAttribute('aria-busy', 'true');
    form.classList.remove('mc-footer__localization-form--failed');

    const localization = form.closest('.mc-footer__localization');
    localization?.classList.add('mc-footer__localization--busy');
    localization?.querySelectorAll(selector).forEach((localizationSelect) => localizationSelect.setAttribute('aria-disabled', 'true'));

    const status = form.querySelector('[data-footer-localization-status]');
    if (status) {
      status.hidden = false;
      status.textContent = form.dataset.loadingLabel || '';
    }

    form.requestSubmit();

    window.setTimeout(() => {
      if (form.dataset.submitting !== 'true') return;

      resetLocalization();
      form.classList.add('mc-footer__localization-form--failed');

      if (status) {
        const submitLabel = form.querySelector('.mc-footer__localization-submit')?.textContent.trim() || '';
        status.hidden = false;
        status.textContent = [form.dataset.errorLabel, submitLabel].filter(Boolean).join('. ');
      }
    }, 15000);
  });
})();
