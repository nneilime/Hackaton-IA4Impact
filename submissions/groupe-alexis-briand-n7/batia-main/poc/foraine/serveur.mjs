// Foraine — serveur local : l'application, la carte, et les données calculées sur cette machine.
// Lancement : node serveur.mjs   →   http://localhost:4720
// Option --reseau : écoute aussi sur le réseau local, pour ouvrir Foraine depuis un téléphone.
import { createServer } from 'node:http';
import { createReadStream, existsSync, statSync, readFileSync, writeFileSync, mkdirSync, readdirSync } from 'node:fs';
import { join, normalize, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';
import { chargerDonnees, dateDuReleve, lireCsv } from './risque/donnees.mjs';
import { evaluerRisques, validerDansLePasse, METHODE, SEUILS } from './risque/risque.mjs';

const RACINE = dirname(fileURLToPath(import.meta.url));
const DONNEES = join(RACINE, 'donnees/kit-batia/donnees');
const IMPORTS = join(RACINE, 'imports');
const ETAT = join(RACINE, 'etat');
const FICHIER_DECISIONS = join(ETAT, 'decisions.json');
const PORT = Number(process.env.PORT) || 4720;
const HOTE = process.argv.includes('--reseau') ? '0.0.0.0' : '127.0.0.1';
const TYPES = { '.html': 'text/html; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.woff2': 'font/woff2', '.pbf': 'application/x-protobuf', '.pmtiles': 'application/octet-stream', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' };

// Positions fictives des résidences (module de carte) : des secteurs, jamais un immeuble réel.
const { RESIDENCES: POSITIONS } = await import('./carte/demo/residences.mjs');

// ── Calcul ──────────────────────────────────────────────────────────
let etat = null;
function calculer() {
  const t0 = Date.now();
  const imports = existsSync(IMPORTS) ? readdirSync(IMPORTS).filter((f) => f.endsWith('.csv')).sort().map((f) => join(IMPORTS, f)) : [];
  const d = chargerDonnees(DONNEES, { imports });
  const releve = dateDuReleve(d);
  const risques = evaluerRisques(d, { dateReference: releve });
  const ilYAUnAn = decaler(releve, -12);

  const parLogement = groupe(d.demandes, 'logement_id');
  const parEquipement = groupe(d.interventions, 'equipement_id');
  const famille = Object.fromEntries(d.familles.map((f) => [f.famille, f]));
  const prestataire = Object.fromEntries(d.prestataires.map((p) => [p.prestataire_id, p]));

  const residences = d.residences.map((r) => {
    const pos = POSITIONS.find((p) => p.id === r.residence_id);
    return {
      id: r.residence_id, nom: r.nom, lettre: r.residence_id.replace('RES-', ''), position: pos?.position,
      logements: +r.nb_logements, batiments: +r.nb_batiments, annee: +r.annee_construction, surface: +r.surface_habitable_totale_m2,
      ascenseur: r.ascenseur, energie: r.energie_chauffage, chauffage: r.generateur_chauffage, typeChauffage: r.type_chauffage, ecs: r.production_ecs, ventilation: r.ventilation,
      dpe: r.etiquette_dpe_majoritaire, conso: +r.conso_ep_moyenne_kwh_m2_an, ges: +r.ges_moyen_kgco2_m2_an,
    };
  });
  const batiments = d.batiments.map((b) => ({ id: b.batiment_id, r: b.residence_id, niveaux: +b.nb_niveaux, logements: +b.nb_logements, ascenseur: b.ascenseur }));
  const logements = d.logements.map((l) => {
    const dem = parLogement.get(l.logement_id) || [];
    return {
      id: l.logement_id, b: l.batiment_id, r: l.residence_id, typo: l.typologie, surface: +l.surface_habitable_m2, etage: +l.etage,
      dpe: l.dpe_etiquette_globale, dpeEnergie: l.dpe_etiquette_energie, dpeGes: l.dpe_etiquette_ges, conso: +l.dpe_conso_ep_kwh_m2_an, ges: +l.dpe_ges_kgco2_m2_an,
      dpeDate: l.dpe_date, dpeMethode: l.dpe_methode, statut: l.statut_occupation,
      d12: dem.filter((x) => x.date_creation.slice(0, 10) > ilYAUnAn).length, dTot: dem.length,
    };
  });
  const equipements = [];
  for (const e of d.equipements) {
    const r = risques.get(e.equipement_id);
    if (!r) continue;
    equipements.push({
      id: e.equipement_id, famille: e.famille, libelle: e.libelle_famille, commun: e.niveau_rattachement !== 'Logement',
      r: e.residence_id, b: e.batiment_id, l: e.logement_id || null,
      score: r.score, probabilite: r.probabilite, niveau: r.niveau, raisons: r.raisons.slice(0, 5).map((x) => ({ texte: x.texte, court: x.court, poids: x.poids, code: x.code })), faits: r.faits,
      contrat: e.sous_contrat_entretien, prestataire: prestataire[e.prestataire_id]?.nom || null,
    });
  }
  equipements.sort((a, b) => b.score - a.score || a.id.localeCompare(b.id));
  equipements.forEach((e, i) => { e.rang = i + 1; });

  const autres = d.equipements.filter((e) => !risques.has(e.equipement_id));
  etat = {
    d, parLogement, parEquipement, famille, prestataire, autres,
    public: {
      releve, calculeLe: new Date().toISOString(), methode: METHODE, seuils: SEUILS, imports: imports.map((f) => f.split('/').pop()),
      residences, batiments, logements, equipements,
      plan: d.plan.map((o) => ({ id: o.operation_id, r: o.residence_id, type: o.type_operation, perimetre: o.perimetre, annee: +o.annee_souhaitee, cout: +o.cout_estime_ttc, gain: +o.gain_conso_ep_estime_kwh_m2_an, logements: +o.nb_logements_concernes, origine: o.origine_demande, statut: o.statut, rang: +o.rang_actuel_chronologique, inscrite: o.date_inscription_demande })),
      seuilsDpe: d.seuilsDpe,
    },
    validation: null,
  };
  console.log(`Calcul : ${equipements.length} équipements évalués au ${releve} en ${Date.now() - t0} ms`);
}

function validation() {
  if (!etat.validation) {
    try { etat.validation = validerDansLePasse(etat.d); } catch (err) { console.warn('[validation]', err); etat.validation = { erreur: String(err.message || err) }; }
  }
  return etat.validation;
}

// ── Décisions : enregistrées sur cette machine, partagées entre l'ordinateur et le téléphone ──
function lireDecisions() {
  try { return JSON.parse(readFileSync(FICHIER_DECISIONS, 'utf8')); } catch { return {}; }
}
function ecrireDecisions(dec) {
  mkdirSync(ETAT, { recursive: true });
  writeFileSync(FICHIER_DECISIONS, JSON.stringify(dec, null, 2));
}

// ── Utilitaires ─────────────────────────────────────────────────────
function groupe(liste, cle) {
  const m = new Map();
  for (const x of liste) { const k = x[cle]; if (!k) continue; if (!m.has(k)) m.set(k, []); m.get(k).push(x); }
  return m;
}
function decaler(dateIso, mois) {
  const [a, m, j] = dateIso.split('-').map(Number);
  const d = new Date(Date.UTC(a, m - 1 + mois, j));
  return d.toISOString().slice(0, 10);
}
function json(req, res, objet, code = 200) {
  const corps = Buffer.from(JSON.stringify(objet));
  const gz = /\bgzip\b/.test(req.headers['accept-encoding'] || '') && corps.length > 2048;
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...(gz ? { 'Content-Encoding': 'gzip' } : {}) });
  res.end(gz ? gzipSync(corps) : corps);
}
function lireCorps(req, max = 20e6) {
  return new Promise((ok, ko) => {
    const morceaux = []; let n = 0;
    req.on('data', (c) => { n += c.length; if (n > max) { ko(new Error('trop gros')); req.destroy(); } else morceaux.push(c); });
    req.on('end', () => ok(Buffer.concat(morceaux).toString('utf8')));
    req.on('error', ko);
  });
}
const csvCellule = (v) => { const s = v == null ? '' : String(v); return /[;"\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
const csv = (lignes) => '﻿' + lignes.map((l) => l.map(csvCellule).join(';')).join('\r\n') + '\r\n';
const libelleLogement = (id) => (id ? id.replace(/^LGT-/, '').replace(/^([A-H]\d+)-/, '$1 · ') : '');

function detailLogement(id) {
  const p = etat.public;
  const l = p.logements.find((x) => x.id === id);
  if (!l) return null;
  const demandes = (etat.parLogement.get(id) || []).slice().sort((a, b) => b.date_creation.localeCompare(a.date_creation))
    .map((x) => ({ id: x.demande_id, date: x.date_creation, cloture: x.date_cloture, motif: x.motif, objet: x.objet, texte: x.texte_demande, priorite: x.priorite, canal: x.canal, reouverte: x.demande_reouverte, delai: x.delai_resolution_h }));
  const equipements = p.equipements.filter((e) => e.l === id);
  const autres = etat.autres.filter((e) => e.logement_id === id).map((e) => ({ id: e.equipement_id, libelle: e.libelle_famille, datePose: e.date_pose }));
  const ids = new Set([...equipements.map((e) => e.id), ...autres.map((e) => e.id)]);
  const interventions = [];
  for (const eid of ids) for (const x of etat.parEquipement.get(eid) || []) interventions.push(intervention(x));
  interventions.sort((a, b) => b.date.localeCompare(a.date));
  return { logement: l, demandes, equipements, autres, interventions };
}
function intervention(x) {
  return { id: x.intervention_id, date: x.date_intervention, equipement: x.equipement_id, type: x.type_intervention, symptome: x.symptome, gravite: x.gravite, resultat: x.resultat, commentaire: x.commentaire_technicien, prestataire: etat.prestataire[x.prestataire_id]?.nom || x.prestataire_id, demande: x.demande_id_liee };
}
function detailEquipement(id) {
  const e = etat.public.equipements.find((x) => x.id === id);
  if (!e) return null;
  const interventions = (etat.parEquipement.get(id) || []).map(intervention).sort((a, b) => b.date.localeCompare(a.date));
  const demandes = e.l ? (etat.parLogement.get(e.l) || []).slice().sort((a, b) => b.date_creation.localeCompare(a.date_creation))
    .map((x) => ({ id: x.demande_id, date: x.date_creation, motif: x.motif, objet: x.objet, texte: x.texte_demande, priorite: x.priorite })) : [];
  const brut = etat.d.equipements.find((x) => x.equipement_id === id);
  return { equipement: e, interventions, demandes, brut: { datePose: brut.date_pose, origineDatePose: brut.origine_date_pose, remplacements: +brut.nb_remplacements_2018_2025, visiteAnnuelle: brut.visite_annuelle_prevue, codeMetier: brut.code_metier } };
}

// ── Serveur ─────────────────────────────────────────────────────────
calculer();

createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://x');
    let p = decodeURIComponent(url.pathname);

    if (p === '/api/etat') return json(req, res, { ...etat.public, decisions: lireDecisions() });
    if (p === '/api/validation') return json(req, res, validation());
    let m;
    if ((m = /^\/api\/logement\/([\w-]+)$/.exec(p))) { const r = detailLogement(m[1]); return r ? json(req, res, r) : json(req, res, { erreur: 'introuvable' }, 404); }
    if ((m = /^\/api\/equipement\/([\w-]+)$/.exec(p))) { const r = detailEquipement(m[1]); return r ? json(req, res, r) : json(req, res, { erreur: 'introuvable' }, 404); }

    if (p === '/api/decision' && req.method === 'POST') {
      const { id, choix, note } = JSON.parse(await lireCorps(req, 1e5));
      if (!etat.public.equipements.some((e) => e.id === id) || !['visite', 'remplacer', 'plus-tard'].includes(choix)) return json(req, res, { erreur: 'décision invalide' }, 400);
      const dec = lireDecisions();
      dec[id] = { choix, note: (note || '').slice(0, 500), le: new Date().toISOString() };
      ecrireDecisions(dec);
      return json(req, res, { decisions: dec });
    }
    if ((m = /^\/api\/decision\/([\w-]+)$/.exec(p)) && req.method === 'DELETE') {
      const dec = lireDecisions();
      delete dec[m[1]];
      ecrireDecisions(dec);
      return json(req, res, { decisions: dec });
    }

    if (p === '/api/import' && req.method === 'POST') {
      const texte = await lireCorps(req);
      const nom = String(req.headers['x-nom-fichier'] || 'trimestre.csv').replace(/[^\w.-]/g, '_').slice(0, 80);
      const lignes = lireCsv(texte);
      const colonnes = Object.keys(lignes[0] || {});
      const attendu = { interventions: ['intervention_id', 'date_intervention', 'equipement_id', 'type_intervention', 'gravite'], demandes: ['demande_id', 'date_creation', 'logement_id', 'motif'] };
      const table = Object.keys(attendu).find((t) => attendu[t].every((c) => colonnes.includes(c)));
      if (!table) return json(req, res, { erreur: 'Colonnes non reconnues : il faut le format de 05_demandes_locataires ou de 06_interventions.' }, 400);
      mkdirSync(IMPORTS, { recursive: true });
      const avant = etat.public.releve;
      writeFileSync(join(IMPORTS, `${new Date().toISOString().replace(/[:.]/g, '-')}-${nom.endsWith('.csv') ? nom : nom + '.csv'}`), texte);
      calculer();
      return json(req, res, { table, lignes: lignes.length, avant, releve: etat.public.releve });
    }

    if (p === '/api/export/file.csv' || p === '/api/export/decisions.csv') {
      const dec = lireDecisions();
      const seulementDecides = p.endsWith('decisions.csv');
      const choixMot = { visite: 'Visite', remplacer: 'Remplacer', 'plus-tard': 'Plus tard' };
      const niveauMot = { visiter: 'À visiter', surveiller: 'À surveiller', calme: 'Calme' };
      const lignes = [['Rang', 'Résidence', 'Bâtiment', 'Logement', 'Équipement', 'Identifiant', 'Niveau', 'Indice', 'Raisons', 'Décision', 'Décidé le', 'Note']];
      for (const e of etat.public.equipements) {
        const x = dec[e.id];
        if (seulementDecides ? !x : e.niveau === 'calme' && !x) continue;
        lignes.push([e.rang, e.r.replace('RES-', 'Résidence '), e.b.replace('BAT-', ''), libelleLogement(e.l), e.libelle, e.id, niveauMot[e.niveau], e.score, e.raisons.map((r) => r.texte).join(' | '), x ? choixMot[x.choix] : '', x ? x.le.slice(0, 10) : '', x?.note || '']);
      }
      res.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': `attachment; filename="foraine-${seulementDecides ? `decisions-${new Date().toISOString().slice(0, 10)}` : `file-${etat.public.releve}`}.csv"` });
      return res.end(csv(lignes));
    }
    if (p === '/api/export/scores.csv') {
      const lignes = ['equipement_id,score_risque', ...etat.public.equipements.slice().sort((a, b) => a.id.localeCompare(b.id)).map((e) => `${e.id},${Number(e.probabilite ?? e.score / 100).toFixed(4)}`)];
      res.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': `attachment; filename="scores-risque-${etat.public.releve}.csv"` });
      return res.end(lignes.join('\n') + '\n');
    }

    // Fichiers statiques : l'application à la racine, la carte sous /carte/
    if (p === '/') p = '/index.html';
    let base = join(RACINE, 'app');
    if (p.startsWith('/carte/')) { base = join(RACINE, 'carte'); p = p.slice('/carte'.length); }
    const chemin = normalize(join(base, p));
    if (!chemin.startsWith(base) || !existsSync(chemin) || statSync(chemin).isDirectory()) { res.writeHead(404); return res.end('Introuvable'); }
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
  } catch (err) {
    console.error(err);
    if (!res.headersSent) json(req, res, { erreur: String(err.message || err) }, 500);
  }
}).listen(PORT, HOTE, () => console.log(`Foraine : http://localhost:${PORT}${HOTE === '0.0.0.0' ? '  (ouvert sur le réseau local)' : ''}`));
