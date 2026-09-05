import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { createPreviewServer } from './local-preview-router.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const server = createPreviewServer({ key: process.env.PIMM_PREVIEW_KEY });
server.on('error', (error) => {
  console.error(`Cannot start local preview: ${error.code ?? 'server error'}`);
  process.exitCode = 1;
});
server.listen(9494, '127.0.0.1', () => {
  console.log('Local navigation preview: http://127.0.0.1:9494 (production unchanged)');
  const childEnv = { ...process.env };
  delete childEnv.PIMM_PREVIEW_KEY;
  const child = spawn(process.execPath, [
    resolve(root, 'node_modules/@shopify/cli/bin/run.js'), 'theme', 'dev',
    '--store', '10b918-e4.myshopify.com', '--port', '9495', '--path', root,
  ], { cwd: root, env: childEnv, stdio: 'inherit', windowsHide: true });
  child.on('error', () => { console.error('Cannot start Shopify development server.'); server.close(); process.exitCode = 1; });
  child.on('exit', (code) => { server.close(); process.exitCode = code ?? 1; });
  for (const signal of ['SIGINT', 'SIGTERM']) {
    process.on(signal, () => { child.kill(); server.close(); });
  }
});
