// Sous le capot — la part serveur : la page, le relais vers les services qui refusent le navigateur,
// les antennes 2G de l'ANFR (qui n'a pas d'interface de requête) et les enregistrements du filet de secours.
// Branché dans BâtIA (serveur.mjs) et dans le serveur autonome (capot/serveur.mjs).
import { createReadStream, existsSync, statSync, readFileSync } from 'node:fs';
import { join, normalize, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ICI = dirname(fileURLToPath(import.meta.url));
const TYPES = { '.html': 'text/html; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.woff2': 'font/woff2', '.pbf': 'application/x-protobuf', '.pmtiles': 'application/octet-stream', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.webm': 'video/webm' };

// Seuls ces services passent par le relais : jamais une adresse quelconque.
const AUTORISES = new Set(['georisques.gouv.fr', 'www.georisques.gouv.fr', 'data.geopf.fr', 'rnb-api.beta.gouv.fr', 'api.bdnb.io', 'data.ademe.fr', 'hubeau.eaufrance.fr', 'api.panoramax.xyz', 'panoramax.ign.fr']);

let antennes = null;
export function antennes2g(lon, lat) {
  if (!antennes) antennes = JSON.parse(readFileSync(join(ICI, 'donnees/antennes-2g.json'), 'utf8'));
  const r = Math.PI / 180, kx = Math.cos(lat * r) * 111320, ky = 110540;
  const operateurs = { Orange: null, SFR: null, 'Bouygues Telecom': null };
  for (const [la, lo, op] of antennes.stations) {
    const dx = (lo - lon) * kx, dy = (la - lat) * ky;
    if (Math.abs(dx) > 60000 || Math.abs(dy) > 60000) continue;
    const d = Math.hypot(dx, dy);
    if (!operateurs[op] || d < operateurs[op].distance_m) operateurs[op] = { distance_m: Math.round(d) };
  }
  return { export: antennes.export, source: antennes.source, operateurs };
}

export function servirFichier(req, res, chemin) {
  if (!existsSync(chemin) || statSync(chemin).isDirectory()) { res.writeHead(404); return res.end('Introuvable'); }
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
}

// Répond à tout ce qui commence par /capot ; renvoie false sinon.
export async function servirCapot(req, res, url) {
  const p = decodeURIComponent(url.pathname);
  if (p !== '/capot' && !p.startsWith('/capot/')) return false;
  if (p === '/capot') { res.writeHead(302, { Location: '/capot/' }); res.end(); return true; }

  if (p === '/capot/anfr') {
    const corps = JSON.stringify(antennes2g(Number(url.searchParams.get('lon')), Number(url.searchParams.get('lat'))));
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
    res.end(corps);
    return true;
  }

  if (p === '/capot/relais') {
    let cible;
    try { cible = new URL(url.searchParams.get('u')); } catch { res.writeHead(400); res.end('adresse invalide'); return true; }
    if (cible.protocol !== 'https:' || !AUTORISES.has(cible.hostname)) { res.writeHead(403); res.end('service non autorisé'); return true; }
    try {
      const r = await fetch(cible, { signal: AbortSignal.timeout(6000), headers: { 'User-Agent': 'BatIA-sous-le-capot/1.0 (prototype hackathon; donnees publiques)' } });
      const corps = Buffer.from(await r.arrayBuffer());
      res.writeHead(r.status, { 'Content-Type': r.headers.get('content-type') || 'application/octet-stream', 'Cache-Control': 'no-store' });
      res.end(corps);
    } catch (err) {
      res.writeHead(504, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ erreur: String(err.message || err) }));
    }
    return true;
  }

  let rel = p.slice('/capot'.length);
  if (rel === '/' || rel === '') rel = '/index.html';
  const chemin = normalize(join(ICI, rel));
  if (!chemin.startsWith(ICI)) { res.writeHead(403); res.end(); return true; }
  servirFichier(req, res, chemin);
  return true;
}
