// MapLibre 6 loads its tile worker as a separate module. Vite's dev server injects its
// HMR client into anything served from node_modules, which breaks the worker, so we
// serve an untouched copy from public/ and point MapLibre at it (see MapView.tsx).
import { copyFileSync, mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const dist = dirname(require.resolve('maplibre-gl/dist/maplibre-gl.css'));
const out = join(root, 'public', 'vendor', 'maplibre');
mkdirSync(out, { recursive: true });
copyFileSync(join(dist, 'maplibre-gl-worker.mjs'), join(out, 'maplibre-gl-worker.mjs'));
