// Enregistre d'avance toutes les réponses de la chaîne pour les cinq immeubles candidats : le filet de secours.
// node capot/enregistrer.mjs [slug…]   →   capot/enregistrements/<slug>.json, photos/<slug>.jpg, tuiles/z/x/y.jpg
// Débits respectés : un appel à la fois, une pause entre deux immeubles (BDNB : 120 appels par minute au plus).
import { mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { ETAPES, assemblerFiche } from './sources.mjs';
import { antennes2g } from './relais.mjs';

const ICI = dirname(fileURLToPath(import.meta.url));
const DOSSIER = join(ICI, 'enregistrements');
export const CANDIDATS = [
  { slug: 'embouchure', saisie: "34 boulevard de l'Embouchure, Toulouse", cles: ['embouchure'] },
  { slug: 'rosette', saisie: '19 rue Rosette, Toulouse', cles: ['rosette'] },
  { slug: 'periole', saisie: '134 rue de Périole, Toulouse', cles: ['periole'] },
  { slug: 'rouergue', saisie: '47 allée du Rouergue, Colomiers', cles: ['rouergue'] },
  { slug: 'jean-jaures', saisie: '78 allées Jean-Jaurès, Toulouse', cles: ['jean jaures', 'jean-jaures', 'jaures'] },
];
const pause = (ms) => new Promise((ok) => setTimeout(ok, ms));
const UA = { 'User-Agent': 'BatIA-sous-le-capot/1.0 (prototype hackathon; donnees publiques)' };

async function enregistrer(c) {
  const appels = [];
  const appeler = async (url, opts = {}) => {
    const t0 = Date.now();
    let statut = 0, corps = null;
    if (opts.local) {
      const u = new URL(url, 'http://x');
      corps = antennes2g(+u.searchParams.get('lon'), +u.searchParams.get('lat'));
      statut = 200;
      await pause(120);
    } else {
      try {
        const r = await fetch(url, { headers: UA, signal: AbortSignal.timeout(opts.sansEnregistrement ? 2500 : 15000) });
        statut = r.status;
        corps = await r.json();
      } catch (err) { statut = 0; corps = null; console.log('   échec', opts.etape, String(err.message || err).slice(0, 60)); }
    }
    const duree = Date.now() - t0;
    const ok = statut >= 200 && statut < 300 && corps && (!opts.valide || opts.valide(corps));
    const vide = !ok && statut >= 200 && statut < 300 && corps; // la source répond, mais n'a rien ici
    // Une rue sans photo est une vraie réponse : on la garde, pour la rejouer telle quelle sans réseau.
    if ((ok || (vide && opts.etape === 'photo')) && !opts.sansEnregistrement) appels.push({ etape: opts.etape, url, duree_ms: duree, statut, corps });
    console.log(`   ${opts.etape.padEnd(14)} ${String(statut).padEnd(4)} ${duree} ms`);
    if (!ok) throw Object.assign(new Error(`${opts.etape} : ${statut}`), { vide });
    return corps;
  };
  const ctx = { saisie: c.saisie };
  const lues = [];
  for (const e of ETAPES) {
    try { await e.lancer(ctx, appeler); lues.push({ nom: e.source, date_lecture: new Date().toISOString().slice(0, 10) }); }
    catch (err) { console.log('   étape manquée', e.id, err.message); }
    await pause(250);
  }
  // La photo de rue, copiée pour marcher sans réseau.
  let photo = null;
  if (ctx.photo?.url) {
    try {
      const r = await fetch(ctx.photo.url, { headers: UA, signal: AbortSignal.timeout(20000) });
      if (r.ok) { mkdirSync(join(DOSSIER, 'photos'), { recursive: true }); photo = `photos/${c.slug}.jpg`; writeFileSync(join(DOSSIER, photo), Buffer.from(await r.arrayBuffer())); }
    } catch (err) { console.log('   photo non copiée', err.message); }
  }
  // Les tuiles de l'orthophoto de l'IGN autour de l'immeuble, du zoom 14 au zoom 18.
  let tuiles = 0;
  if (ctx.pointBatiment) {
    const [lon, lat] = ctx.pointBatiment;
    for (let z = 14; z <= 18; z++) {
      const n = 2 ** z;
      const tx = ((lon + 180) / 360) * n;
      const ty = ((1 - Math.log(Math.tan((lat * Math.PI) / 180) + 1 / Math.cos((lat * Math.PI) / 180)) / Math.PI) / 2) * n;
      const rx = z >= 17 ? 3 : 2, ry = z >= 17 ? 2 : 2;
      for (let x = Math.floor(tx) - rx; x <= Math.floor(tx) + rx; x++) for (let y = Math.floor(ty) - ry; y <= Math.floor(ty) + ry; y++) {
        const f = join(DOSSIER, 'tuiles', String(z), String(x), `${y}.jpg`);
        if (existsSync(f)) continue;
        try {
          const r = await fetch(`https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&TILEMATRIXSET=PM&FORMAT=image/jpeg&TILEMATRIX=${z}&TILEROW=${y}&TILECOL=${x}`, { headers: UA, signal: AbortSignal.timeout(10000) });
          if (!r.ok) continue;
          mkdirSync(dirname(f), { recursive: true });
          writeFileSync(f, Buffer.from(await r.arrayBuffer()));
          tuiles++;
        } catch {}
      }
    }
  }
  const fiche = assemblerFiche(ctx, lues);
  writeFileSync(join(DOSSIER, `${c.slug}.json`), JSON.stringify({ slug: c.slug, saisie: c.saisie, adresse: ctx.adresse, ban: ctx.ban, enregistre_le: new Date().toISOString(), photo, appels, fiche }, null, 1));
  return { slug: c.slug, saisie: c.saisie, adresse: ctx.adresse, ban: ctx.ban, cles: c.cles, photo };
}

mkdirSync(DOSSIER, { recursive: true });
const choisis = process.argv.slice(2);
const index = [];
for (const c of CANDIDATS) {
  if (choisis.length && !choisis.includes(c.slug)) continue;
  console.log('→', c.saisie);
  index.push(await enregistrer(c));
  await pause(1500);
}
if (!choisis.length) writeFileSync(join(DOSSIER, 'index.json'), JSON.stringify(index, null, 1));
console.log('fini');
