(() => {
  const selector = '[data-footer-localization-select]';

  document.addEventListener('change', (event) => {
    const select = event.target.closest(selector);

    if (!select || select.value === select.dataset.initialValue) return;

    const form = select.form;

    if (!form || form.dataset.submitting === 'true') return;

    form.dataset.submitting = 'true';
    form.setAttribute('aria-busy', 'true');
    form.requestSubmit();
  });
})();
