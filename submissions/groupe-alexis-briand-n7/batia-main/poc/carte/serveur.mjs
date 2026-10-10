// Serveur de démonstration de la carte : fichiers statiques de ce dossier, avec lecture par plages (Range) pour les .pmtiles.
// Lancement : node carte/serveur.mjs   →   http://localhost:4600/demo/
import { createServer } from 'node:http';
import { createReadStream, existsSync, statSync } from 'node:fs';
import { join, normalize, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const RACINE = dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT) || 4600;
const HOTE = process.argv.includes('--reseau') ? '0.0.0.0' : '127.0.0.1';
const TYPES = { '.html': 'text/html; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.woff2': 'font/woff2', '.pbf': 'application/x-protobuf', '.pmtiles': 'application/octet-stream', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml' };

createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (p === '/') { res.writeHead(302, { Location: '/demo/' }); return res.end(); }
  if (p.endsWith('/')) p += 'index.html';
  const chemin = normalize(join(RACINE, p));
  if (!chemin.startsWith(RACINE) || !existsSync(chemin) || statSync(chemin).isDirectory()) { res.writeHead(404); return res.end('Introuvable'); }
  const taille = statSync(chemin).size;
  const type = TYPES[extname(chemin)] || 'application/octet-stream';
  const plage = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range || '');
  if (plage && (plage[1] || plage[2])) {
    const debut = plage[1] ? Number(plage[1]) : Math.max(0, taille - Number(plage[2]));
    const fin = plage[1] && plage[2] ? Math.min(Number(plage[2]), taille - 1) : taille - 1;
    if (debut >= taille || debut > fin) { res.writeHead(416, { 'Content-Range': `bytes */${taille}` }); return res.end(); }
    res.writeHead(206, { 'Content-Type': type, 'Content-Length': fin - debut + 1, 'Content-Range': `bytes ${debut}-${fin}/${taille}`, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-cache' });
    return createReadStream(chemin, { start: debut, end: fin }).pipe(res);
  }
  res.writeHead(200, { 'Content-Type': type, 'Content-Length': taille, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-cache' });
  createReadStream(chemin).pipe(res);
}).listen(PORT, HOTE, () => console.log(`Carte d'Assise : http://localhost:${PORT}/demo/`));
