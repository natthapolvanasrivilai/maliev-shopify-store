import { readFile } from 'node:fs/promises';
import { Liquid } from 'liquidjs';

const sectionUrl = new URL('../../../sections/maliev-pimm-collection.liquid', import.meta.url);
const schemaBlock = /{% schema %}[\s\S]*?{% endschema %}/;

const escapeHtml = (value) => String(value ?? '')
  .replaceAll('&', '&amp;')
  .replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;')
  .replaceAll('"', '&quot;')
  .replaceAll("'", '&#39;');

const translate = (key, parameters = {}) => {
  if (key === 'products.pimm_collection.configuration_error') return 'PIMM_CONFIGURATION_ERROR';
  if (key === 'products.pimm_machine.purchase.lead_time') return `${parameters.days} days`;
  return key;
};

const engine = new Liquid({
  strictFilters: true,
  strictVariables: false,
});

engine.registerFilter('asset_url', (value) => `/assets/${value}`);
engine.registerFilter('escape', escapeHtml);
engine.registerFilter('json', (value) => JSON.stringify(value));
engine.registerFilter('money_with_currency', (value) => `THB ${Number(value).toFixed(2)}`);
engine.registerFilter('t', translate);

export const renderPimmCollectionSection = async (pimmProduct) => {
  const source = (await readFile(sectionUrl, 'utf8')).replace(schemaBlock, '');

  return engine.parseAndRender(source, {
    canonical_url: 'https://shop.example.test/collections/pimm',
    request: { origin: 'https://shop.example.test' },
    section: {
      id: 'contract-fixture',
      settings: {
        pimm_product: pimmProduct,
        support_url: '',
        factory_visit_url: '',
      },
    },
    shop: { name: 'MALIEV' },
  });
};

export const readModelRecords = (output) => {
  const payload = output.match(/<script type="application\/json" data-pimm-collection-models>([\s\S]*?)<\/script>/)?.[1];
  if (!payload) throw new Error('PIMM collection model payload was not rendered');
  return JSON.parse(payload);
};
