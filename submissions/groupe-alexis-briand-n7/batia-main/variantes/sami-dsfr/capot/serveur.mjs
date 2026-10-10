// Sous le capot, seul : node capot/serveur.mjs   →   http://localhost:4861/capot/
// Sert la page, le module de carte de BâtIA (fond, polices), le relais et les enregistrements.
import { createServer } from 'node:http';
import { join, normalize, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { servirCapot, servirFichier } from './relais.mjs';

const RACINE = join(dirname(fileURLToPath(import.meta.url)), '..');
const PORT = Number(process.env.PORT) || 4861;

createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://x');
    if (await servirCapot(req, res, url)) return;
    const p = decodeURIComponent(url.pathname);
    if (p === '/') { res.writeHead(302, { Location: '/capot/' }); return res.end(); }
    if (p.startsWith('/carte/')) {
      const base = join(RACINE, 'carte');
      const chemin = normalize(join(base, p.slice('/carte'.length)));
      if (chemin.startsWith(base)) return servirFichier(req, res, chemin);
    }
    res.writeHead(404); res.end('Introuvable');
  } catch (err) {
    console.error(err);
    if (!res.headersSent) { res.writeHead(500); res.end(String(err.message || err)); }
  }
}).listen(PORT, '127.0.0.1', () => console.log(`Sous le capot : http://localhost:${PORT}/capot/`));
