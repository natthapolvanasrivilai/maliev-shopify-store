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
engine.registerFilter(
  'money_with_currency',
  (value) => `<span class="money">THB ${Number(value).toFixed(2)}</span>`,
);
engine.registerFilter('strip_html', (value) => String(value).replace(/<[^>]*>/g, ''));
engine.registerFilter('stylesheet_tag', (value) => `<link href="${escapeHtml(value)}" rel="stylesheet" type="text/css" media="all">`);
engine.registerFilter('t', translate);

export const renderPimmCollectionSection = async (pimmProduct, context = {}) => {
  const source = (await readFile(sectionUrl, 'utf8')).replace(schemaBlock, '');

  return engine.parseAndRender(source, {
    canonical_url: 'https://shop.example.test/collections/pimm',
    collection: { handle: context.collectionHandle ?? 'เครื่องฉีดพลาสติก' },
    product: context.product,
    request: {
      origin: 'https://shop.example.test',
      page_type: context.pageType,
      path: context.path,
    },
    section: {
      id: 'contract-fixture',
      settings: {
        pimm_product: pimmProduct,
        support_url: context.supportUrl ?? '',
        factory_visit_url: context.factoryVisitUrl ?? '',
      },
    },
    shop: { name: 'MALIEV' },
    template: { suffix: context.templateSuffix },
  });
};

export const readModelRecords = (output) => {
  const payload = output.match(/<script type="application\/json" data-pimm-collection-models>([\s\S]*?)<\/script>/)?.[1];
  if (!payload) throw new Error('PIMM collection model payload was not rendered');
  return JSON.parse(payload);
};
