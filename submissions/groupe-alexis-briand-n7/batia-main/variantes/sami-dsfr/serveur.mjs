// BâtIA — serveur local : l'application, la carte, et les données calculées sur cette machine.
// Lancement : node serveur.mjs   →   http://localhost:4860
// Option --reseau : écoute aussi sur le réseau local, pour ouvrir BâtIA depuis un téléphone.
import { createServer } from 'node:http';
import { createReadStream, existsSync, statSync, readFileSync, writeFileSync, mkdirSync, readdirSync, renameSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { createHash, timingSafeEqual } from 'node:crypto';
import { join, normalize, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';
import { chargerDonnees, dateDuReleve, lireCsv, reconnaitreTable, TABLES } from './risque/donnees.mjs';
import { evaluerRisques, validerDansLePasse, METHODE, SEUILS } from './risque/risque.mjs';
import { servirCapot } from './capot/relais.mjs'; // Sous le capot : la page, son relais et ses enregistrements (capot/)

const RACINE = dirname(fileURLToPath(import.meta.url));
const DONNEES = join(RACINE, 'donnees/kit-batia/donnees');
const SUR_VERCEL = !!process.env.VERCEL;
const IMPORTS = SUR_VERCEL ? '/tmp/batia/imports' : join(RACINE, 'imports');
const ETAT = SUR_VERCEL ? '/tmp/batia/etat' : join(RACINE, 'etat');
const FICHIER_DECISIONS = join(ETAT, 'decisions.json');
const FICHIER_RENOVATIONS = join(ETAT, 'renovations.json');
const PORT = Number(process.env.PORT) || 4860;
const MDP = process.env.BATIA_MDP || '';
const JETON = MDP ? createHash('sha256').update(`batia:${MDP}`).digest('hex') : '';
const LIBRE = /^\/(connexion\.html|connexion\.mjs|garde\.js|palette\.css|carte\/vendor\/polices\/.*|api\/connexion|favicon\.ico)$/;
function jetonValide(req) {
  const m = /(?:^|;\s*)batia=([0-9a-f]{64})/.exec(req.headers.cookie || '');
  return !!m && m[1].length === JETON.length && timingSafeEqual(Buffer.from(m[1]), Buffer.from(JETON));
}
const HOTE = process.argv.includes('--reseau') ? '0.0.0.0' : '127.0.0.1';
// En-têtes de sécurité posés sur toutes les réponses. La carte (MapLibre) a besoin de blob: pour ses fils de calcul
// et de data:/blob: pour ses images ; « Sous le capot » interroge des services publics en https et montre leurs photos.
const SECURITE = {
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'SAMEORIGIN',
  'Referrer-Policy': 'no-referrer',
  'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; connect-src 'self' https:; worker-src 'self' blob:; font-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'",
};
// Méthodes acceptées : la lecture partout, l'écriture seulement sur les routes qui enregistrent.
const ECRITURES = [
  [/^\/api\/(decision|renovation|import|connexion)$/, 'POST'],
  [/^\/api\/(decision|renovation)\/[\w-]+$/, 'DELETE'],
];
const TYPES = { '.html': 'text/html; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.woff2': 'font/woff2', '.pbf': 'application/x-protobuf', '.pmtiles': 'application/octet-stream', '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ico': 'image/x-icon' };

// Les livrables rendus au jury : les catégories de pannes (défi 1) et le calendrier des rénovations (défi 2).
// Ils remplacent les indices de risque/ pour l'ordre de la file et les catégories ; risque/ garde les faits de la fiche.
const LIVRABLES = join(RACINE, 'livrables');
const BANDES = { 'Urgence': 'urgence', 'Alerte': 'alerte', 'Vigilance': 'vigilance', 'À surveiller': 'surveiller', 'Calme': 'calme', 'Rien à signaler': 'ras' };
const SEUIL_VISITE = 45; // moteur/BAREME.md : les visites commencent à 45 points
function lireRaisons(texte) {
  return (texte || '').split(' ; ').map((t) => { const m = /^(.*) \(([+-]\d+)\)$/.exec(t.trim()); return m ? { texte: m[1], poids: +m[2] } : { texte: t.trim(), poids: 0 }; }).filter((r) => r.texte);
}
const DETAIL_RECALCULE = join(ETAT, 'defi1', 'detail.csv');
function ecrireCsv(chemin, lignes) {
  const cols = lignes.colonnes;
  const champ = (v) => { const t = String(v ?? ''); return /[",\n\r]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t; };
  writeFileSync(chemin, [cols.join(','), ...lignes.map((l) => cols.map((c) => champ(l[c])).join(','))].join('\n') + '\n');
}
function rescorer(d, releve) {
  const fusion = join(ETAT, 'fusion');
  mkdirSync(fusion, { recursive: true });
  for (const t of ['residences', 'logements', 'equipements', 'demandes', 'interventions']) ecrireCsv(join(fusion, `${TABLES.find((x) => x.table === t).prefixe}.csv`), d[t]);
  const avant = lireDefi1();
  const r = spawnSync('python3', ['-E', '-P', join(RACINE, 'outils', 'rescorer.py'), fusion, releve || '2025-12-31', DETAIL_RECALCULE], { encoding: 'utf8', timeout: 120000 });
  if (r.status !== 0) {
    console.warn('[rescorer]', (r.stderr || r.error?.message || '').trim().split('\n').pop());
    if (existsSync(DETAIL_RECALCULE)) rmSync(DETAIL_RECALCULE);
    return { recalcules: false, erreur: 'Le moteur Python n’a pas pu recalculer les scores, ceux du livrable restent affichés.' };
  }
  const apres = lireDefi1();
  let bandes = 0, nouveaux = 0;
  for (const [id, v] of apres) { const a = avant?.get(id); if (!a) nouveaux++; else if (a.bande !== v.bande) bandes++; }
  return { recalcules: true, dateRef: releve, equipements: apres.size, changementsBande: bandes, nouveaux };
}
function lireDefi1(livrableSeulement = false) {
  const chemin = !livrableSeulement && existsSync(DETAIL_RECALCULE) ? DETAIL_RECALCULE : join(LIVRABLES, 'defi1/detail_2026.csv');
  const lignes = lireCsv(readFileSync(chemin, 'utf8'));
  return new Map(lignes.map((l) => [l.equipement_id, {
    rang: +l.rang, points: +l.points, bande: BANDES[l.bande] || 'ras', observe: l.pannes_observees_2025 || '',
    raisons: lireRaisons(l.raisons), autres: lireRaisons(l.autres_situations),
  }]));
}
function lireDefi2() {
  const lire = (f) => lireCsv(readFileSync(join(LIVRABLES, 'defi2', f), 'utf8'));
  const classement = new Map(lire('classement_operations.csv').map((o) => [o.operation_id, o]));
  const plans = Object.fromEntries(lire('plans_comparaison.csv').map((p) => [p.plan, p]));
  const effet = (p) => ({ g2028: +p.G_1er_janvier_2028, f2028: +p.F_1er_janvier_2028, e2034: +p.E_1er_janvier_2034, mwh2028: +p.mwhep_economises_par_an_2028, infractions: +p.logements_annees_en_infraction_2027_2035, loyersPerdus: +p.loyers_perdus_estimes_eur });
  const operations = lire('plan_recommande.csv').map((o) => {
    const c = classement.get(o.operation_id) || {};
    return {
      id: o.operation_id, r: o.residence_id, type: o.type_operation, cout: +o.cout_estime_ttc, souhaitee: +o.annee_souhaitee, debut: +o.annee_debut_recommandee,
      duree: +o.annees_de_travaux, coutParAn: +o.cout_par_an, ecart: +o.ecart_vs_souhait, rang: +o.rang_base,
      criteres: { reglementaire: +c.c_reg || 0, energie: +c.c_energy || 0, maintenance: +c.c_maint || 0, locataires: +c.c_tenant || 0, finDeVie: +c.c_eol || 0 },
      pannesParAn: c.pannes_attendues_par_an_defi1 ? +c.pannes_attendues_par_an_defi1 : null,
    };
  });
  return { plafond: 1500000, operations, recommande: effet(plans.monetise_1000_eur_par_point), actuel: effet(plans.fifo_avec_remplissage) };
}

// Positions fictives des résidences (module de carte) : des secteurs, jamais un immeuble réel.
const { RESIDENCES: POSITIONS } = await import('./carte/demo/residences.mjs');

// ── Calcul ──────────────────────────────────────────────────────────
let etat = null;
function calculer() {
  const t0 = Date.now();
  const imports = existsSync(IMPORTS) ? readdirSync(IMPORTS).filter((f) => f.endsWith('.csv') || statSync(join(IMPORTS, f)).isDirectory()).sort().map((f) => join(IMPORTS, f)) : [];
  const d = chargerDonnees(DONNEES, { imports });
  const releve = dateDuReleve(d);
  const scores = imports.length ? rescorer(d, releve) : { recalcules: false };
  const risques = evaluerRisques(d, { dateReference: releve });
  const ilYAUnAn = decaler(releve, -12);

  const parLogement = groupe(d.demandes, 'logement_id');
  const parEquipement = groupe(d.interventions, 'equipement_id');
  const famille = Object.fromEntries(d.familles.map((f) => [f.famille, f]));
  const coutFamille = (f) => famille[f] && famille[f].cout_remplacement_min_ttc ? [+famille[f].cout_remplacement_min_ttc, +famille[f].cout_remplacement_max_ttc] : null;
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
  const defi1 = lireDefi1();
  const equipements = [];
  for (const e of d.equipements) {
    const r = risques.get(e.equipement_id);
    if (!r) continue;
    const L = defi1.get(e.equipement_id);
    // à visiter dès 45 points ; à surveiller : le reste de Vigilance et la bande À surveiller
    const niveau = L ? (L.points >= SEUIL_VISITE ? 'visiter' : L.bande === 'vigilance' || L.bande === 'surveiller' ? 'surveiller' : 'calme') : 'calme';
    equipements.push({
      id: e.equipement_id, famille: e.famille, libelle: e.libelle_famille, commun: e.niveau_rattachement !== 'Logement',
      r: e.residence_id, b: e.batiment_id, l: e.logement_id || null,
      niveau, bande: L?.bande || 'ras', rangLivrable: L?.rang ?? 1e9, observe: L?.observe || '',
      raisons: L ? L.raisons : [], autres: L ? L.autres : [], points: L ? L.points : null, cout: coutFamille(e.famille), faits: r.faits,
      contrat: e.sous_contrat_entretien, prestataire: prestataire[e.prestataire_id]?.nom || null,
    });
  }
  equipements.sort((a, b) => a.rangLivrable - b.rangLivrable || a.id.localeCompare(b.id));
  equipements.forEach((e, i) => { e.rang = i + 1; delete e.rangLivrable; });

  const autres = d.equipements.filter((e) => !risques.has(e.equipement_id));
  etat = {
    d, parLogement, parEquipement, famille, prestataire, autres,
    public: {
      releve, calculeLe: new Date().toISOString(), methode: METHODE, seuils: SEUILS, imports: imports.map((f) => f.split('/').pop()), journalImports: d.journal, scores,
      residences, batiments, logements, equipements,
      plan: d.plan.map((o) => ({ id: o.operation_id, r: o.residence_id, type: o.type_operation, perimetre: o.perimetre, annee: +o.annee_souhaitee, cout: +o.cout_estime_ttc, gain: +o.gain_conso_ep_estime_kwh_m2_an, logements: +o.nb_logements_concernes, origine: o.origine_demande, statut: o.statut, rang: +o.rang_actuel_chronologique, inscrite: o.date_inscription_demande })),
      seuilsDpe: d.seuilsDpe,
      renovations: lireDefi2(),
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
// Rénovations : lancer ou reporter une opération de l'année se décide ici, à la main, et s'annule.
function lireChoixRenovations() {
  try { return JSON.parse(readFileSync(FICHIER_RENOVATIONS, 'utf8')); } catch { return {}; }
}
function ecrireChoixRenovations(c) {
  mkdirSync(ETAT, { recursive: true });
  writeFileSync(FICHIER_RENOVATIONS, JSON.stringify(c, null, 2));
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
class Refus extends Error { constructor(code, message) { super(message); this.code = code; } }
// Lit le corps d'une requête. Au-delà de max octets, le reste est lu sans être gardé, puis la requête est refusée (413) :
// couper la connexion laisserait le navigateur sans réponse.
function corpsDejaLu(req) {
  if (req.body === undefined || req.body === null) return null;
  if (Buffer.isBuffer(req.body)) return req.body;
  if (typeof req.body === 'string') return Buffer.from(req.body, 'utf8');
  return Buffer.from(JSON.stringify(req.body), 'utf8');
}
function lireCorpsBrut(req, max = 20e6) {
  const deja = corpsDejaLu(req);
  if (deja) return deja.length > max ? Promise.reject(new Refus(413, 'Trop volumineux.')) : Promise.resolve(deja);
  return new Promise((ok, ko) => {
    const morceaux = []; let n = 0;
    req.on('data', (c) => { n += c.length; if (n <= max) morceaux.push(c); });
    req.on('end', () => (n > max ? ko(new Refus(413, 'Trop volumineux.')) : ok(Buffer.concat(morceaux))));
    req.on('error', ko);
  });
}
function lireCorps(req, max = 20e6) {
  const deja = corpsDejaLu(req);
  if (deja) return deja.length > max ? Promise.reject(new Refus(413, 'Trop volumineux.')) : Promise.resolve(deja.toString('utf8'));
  return new Promise((ok, ko) => {
    const morceaux = []; let n = 0;
    req.on('data', (c) => { n += c.length; if (n <= max) morceaux.push(c); });
    req.on('end', () => (n > max ? ko(new Refus(413, 'Trop volumineux.')) : ok(Buffer.concat(morceaux).toString('utf8'))));
    req.on('error', ko);
  });
}
async function lireJson(req, max) {
  const texte = await lireCorps(req, max);
  try { const o = JSON.parse(texte); if (o && typeof o === 'object' && !Array.isArray(o)) return o; } catch {}
  throw new Refus(400, 'Requête invalide.');
}
const csvCellule = (v) => {
  let s = v == null ? '' : String(v);
  if (typeof v === 'string' && /^[=+\-@\t\r]/.test(s)) s = `'${s}`; // un tableur ne lit jamais une note comme une formule
  return /[;"\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};
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
// Un import qui empêche le calcul est écarté (renommé en .rejete), puis on recalcule sans lui : le serveur démarre toujours.
function demarrer() {
  for (;;) {
    try { return calculer(); } catch (err) {
      const fautif = /^Import (.+\.csv) :/.exec(err.message)?.[1];
      if (!fautif || !existsSync(fautif)) throw err;
      renameSync(fautif, `${fautif}.rejete`);
      console.warn(`Import écarté : ${fautif.split('/').pop()} (${err.message.split(' : ').pop()})`);
    }
  }
}
demarrer();

export async function traiter(req, res) {
  try {
    const url = new URL(req.url, 'http://x');
    let p = decodeURIComponent(url.pathname);
    for (const [cle, valeur] of Object.entries(SECURITE)) res.setHeader(cle, valeur);
    const ecriture = ECRITURES.find(([motif]) => motif.test(p))?.[1];
    if (!['GET', 'HEAD', ecriture].includes(req.method)) {
      res.writeHead(405, { Allow: ['GET', 'HEAD', ecriture].filter(Boolean).join(', '), 'Content-Type': 'text/plain; charset=utf-8' });
      return res.end('Méthode non acceptée');
    }

    if (p === '/api/connexion' && req.method === 'POST') {
      const { motdepasse } = await lireJson(req, 1e4);
      if (!MDP) return json(req, res, { ok: true, protege: false });
      const donne = createHash('sha256').update(`batia:${String(motdepasse || '')}`).digest('hex');
      if (!timingSafeEqual(Buffer.from(donne), Buffer.from(JETON))) return json(req, res, { erreur: 'Mot de passe incorrect.' }, 401);
      const https = (req.headers['x-forwarded-proto'] || '') === 'https';
      res.setHeader('Set-Cookie', `batia=${JETON}; Path=/; Max-Age=43200; HttpOnly; SameSite=Lax${https ? '; Secure' : ''}`);
      return json(req, res, { ok: true, protege: true });
    }
    if (MDP && !LIBRE.test(p) && !jetonValide(req)) {
      if (p.startsWith('/api/')) return json(req, res, { erreur: 'Connexion requise.' }, 401);
      if (p === '/' || p.endsWith('.html') || p.endsWith('/') || /text\/html/.test(req.headers.accept || '')) { res.writeHead(302, { Location: `/connexion.html?suite=${encodeURIComponent(req.url)}` }); return res.end(); }
      res.writeHead(401, { 'Content-Type': 'text/plain; charset=utf-8' }); return res.end('Connexion requise');
    }
    if (await servirCapot(req, res, url)) return;
    if (p === '/api/etat') return json(req, res, { ...etat.public, decisions: lireDecisions(), choixRenovations: lireChoixRenovations() });
    if (p === '/api/renovation' && req.method === 'POST') {
      const { id, choix } = await lireJson(req, 1e4);
      if (!etat.public.renovations.operations.some((o) => o.id === id) || !['lancer', 'reporter'].includes(choix)) return json(req, res, { erreur: 'choix invalide' }, 400);
      const c = lireChoixRenovations();
      c[id] = { choix, le: new Date().toISOString() };
      ecrireChoixRenovations(c);
      return json(req, res, { choixRenovations: c });
    }
    if (p === '/api/validation') return json(req, res, validation());
    let m;
    if ((m = /^\/api\/logement\/([\w-]+)$/.exec(p))) { const r = detailLogement(m[1]); return r ? json(req, res, r) : json(req, res, { erreur: 'introuvable' }, 404); }
    if ((m = /^\/api\/equipement\/([\w-]+)$/.exec(p))) { const r = detailEquipement(m[1]); return r ? json(req, res, r) : json(req, res, { erreur: 'introuvable' }, 404); }

    if (p === '/api/decision' && req.method === 'POST') {
      const { id, choix, note, retour } = await lireJson(req, 1e5);
      if (!etat.public.equipements.some((e) => e.id === id) || !['visite', 'remplacer', 'plus-tard'].includes(choix) || (retour && !['confirme', 'infirme'].includes(retour))) return json(req, res, { erreur: 'décision invalide' }, 400);
      const dec = lireDecisions();
      const avant = dec[id];
      dec[id] = { choix, note: (note || '').slice(0, 500), le: avant && avant.choix === choix ? avant.le : new Date().toISOString(), ...(retour ? { retour, retourLe: new Date().toISOString() } : {}) };
      ecrireDecisions(dec);
      return json(req, res, { decisions: dec });
    }
    if ((m = /^\/api\/renovation\/([\w-]+)$/.exec(p)) && req.method === 'DELETE') {
      const c = lireChoixRenovations();
      delete c[m[1]];
      ecrireChoixRenovations(c);
      return json(req, res, { choixRenovations: c });
    }
    if ((m = /^\/api\/decision\/([\w-]+)$/.exec(p)) && req.method === 'DELETE') {
      const dec = lireDecisions();
      delete dec[m[1]];
      ecrireDecisions(dec);
      return json(req, res, { decisions: dec });
    }

    if (p === '/api/import' && req.method === 'POST') {
      const brut = await lireCorpsBrut(req);
      const nom = String(req.headers['x-nom-fichier'] || 'import').replace(/[^\w.-]/g, '_').slice(0, 80);
      const horodatage = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      const dossier = join(IMPORTS, `${horodatage}-${nom.replace(/\.(xlsx|xlsm|csv)$/i, '')}`);
      mkdirSync(dossier, { recursive: true });
      const classeur = /\.xls[xm]$/i.test(nom) || brut.subarray(0, 2).toString() === 'PK';
      const feuilles = [];
      if (classeur) {
        const chemin = join(dossier, 'classeur.xlsx');
        writeFileSync(chemin, brut);
        const r = spawnSync('python3', ['-E', '-P', join(RACINE, 'outils', 'classeur_vers_csv.py'), chemin, join(dossier, 'feuilles')], { encoding: 'utf8', timeout: 120000 });
        if (r.status !== 0) { rmSync(dossier, { recursive: true, force: true }); return json(req, res, { erreur: 'Classeur illisible : il faut Python 3 avec openpyxl sur cette machine, ou un export CSV.' }, 400); }
        for (const f of r.stdout.trim().split('\n').filter(Boolean)) feuilles.push({ nom: f, chemin: join(dossier, 'feuilles', `${f}.csv`) });
      } else {
        const chemin = join(dossier, 'brut.csv');
        writeFileSync(chemin, brut.toString('utf8').replace(/^\uFEFF/, ''));
        feuilles.push({ nom: nom.replace(/\.csv$/i, ''), chemin });
      }
      const reconnues = [], ignorees = [];
      for (const f of feuilles) {
        const lignes = lireCsv(readFileSync(f.chemin, 'utf8'));
        const t = reconnaitreTable(lignes.colonnes || [], etat.d);
        if (!t) { ignorees.push({ feuille: f.nom, raison: 'colonnes inconnues' }); continue; }
        if (t.proche) { ignorees.push({ feuille: f.nom, raison: `ressemble à ${t.proche.prefixe}, colonnes manquantes : ${t.proche.manquantes.join(', ')}` }); continue; }
        if (!lignes.length) { ignorees.push({ feuille: f.nom, raison: 'aucune ligne' }); continue; }
        writeFileSync(join(dossier, `${t.prefixe}.csv`), readFileSync(f.chemin));
        reconnues.push({ feuille: f.nom, table: t.table, prefixe: t.prefixe, lignes: lignes.length, extra: t.extra, manquantes: t.manquantes });
      }
      if (!reconnues.length) { rmSync(dossier, { recursive: true, force: true }); return json(req, res, { erreur: 'Aucune feuille reconnue.', ignorees }, 400); }
      const avant = etat.public.releve;
      const precedent = etat;
      try { calculer(); } catch (err) {
        renameSync(dossier, `${dossier}.rejete`);
        etat = precedent;
        console.warn('[import refusé]', err.message);
        return json(req, res, { erreur: `Import refusé : ${err.message}` }, 400);
      }
      const journal = etat.d.journal.filter((j) => j.import === dossier.split('/').pop());
      const sansPosition = etat.public.residences.filter((r) => !r.position).map((r) => r.nom);
      return json(req, res, { tables: journal.map((j) => { const r = reconnues.find((x) => x.prefixe === j.prefixe); return { ...j, feuille: r?.feuille || j.fichier, manquantes: r?.manquantes || [], extra: r?.extra || [] }; }), ignorees, avant, releve: etat.public.releve, scores: etat.public.scores, sansPosition });
    }

    if (p === '/api/export/file.csv' || p === '/api/export/decisions.csv') {
      const dec = lireDecisions();
      const seulementDecides = p.endsWith('decisions.csv');
      const choixMot = { visite: 'Visite', remplacer: 'Remplacer', 'plus-tard': 'Plus tard' };
      const niveauMot = { visiter: 'À visiter', surveiller: 'À surveiller', calme: 'Calme' };
      const bandeMot = { urgence: 'Urgent', alerte: 'Alerte', vigilance: 'Vigilance', surveiller: 'À surveiller', calme: 'Calme', ras: 'Rien à signaler' };
      const lignes = [['Rang', 'Résidence', 'Bâtiment', 'Logement', 'Équipement', 'Identifiant', 'Niveau', 'Catégorie', 'Raisons', 'Décision', 'Décidé le', 'Note']];
      for (const e of etat.public.equipements) {
        const x = dec[e.id];
        if (seulementDecides ? !x : e.niveau === 'calme' && !x) continue;
        lignes.push([e.rang, e.r.replace('RES-', 'Résidence '), e.b.replace('BAT-', ''), libelleLogement(e.l), e.libelle, e.id, niveauMot[e.niveau], bandeMot[e.bande], e.raisons.map((r) => r.texte).join(' | '), x ? choixMot[x.choix] : '', x ? x.le.slice(0, 10) : '', x?.note || '']);
      }
      res.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': `attachment; filename="batia-${seulementDecides ? `decisions-${new Date().toISOString().slice(0, 10)}` : `file-${etat.public.releve}`}.csv"` });
      return res.end(csv(lignes));
    }
    if (p === '/api/export/scores.csv') {
      res.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': 'attachment; filename="score_risque_2026.csv"' });
      return res.end(readFileSync(join(LIVRABLES, 'defi1/score_risque_2026.csv')));
    }
    if (p === '/api/export/plan.csv') {
      res.writeHead(200, { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': 'attachment; filename="plan_recommande.csv"' });
      return res.end(readFileSync(join(LIVRABLES, 'defi2/plan_recommande.csv')));
    }

    // Fichiers statiques : l'application à la racine, la carte sous /carte/, les données réelles sous /reel/
    // (reel/REEL.md), le rejeu sous /rejeu/ (rejeu/REJEU.md) ; « Sous le capot » est servi plus haut (capot/relais.mjs)
    if (p === '/') p = '/index.html';
    let base = join(RACINE, 'app');
    if (p.startsWith('/carte/')) { base = join(RACINE, 'carte'); p = p.slice('/carte'.length); }
    else if (p.startsWith('/reel/') && !/^\/reel\/(cache|outils)\//.test(p)) { base = join(RACINE, 'reel'); p = p.slice('/reel'.length); }
    else if (p.startsWith('/rejeu/') && !p.endsWith('.py')) { base = join(RACINE, 'rejeu'); p = p.slice('/rejeu'.length); }
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
    if (err instanceof Refus) { if (!res.headersSent) json(req, res, { erreur: err.message }, err.code); return; }
    console.error(err);
    if (!res.headersSent) json(req, res, { erreur: String(err.message || err) }, 500);
  }
}

if (!SUR_VERCEL) createServer(traiter).listen(PORT, HOTE, () => console.log(`BâtIA : http://localhost:${PORT}${HOTE === '0.0.0.0' ? '  (ouvert sur le réseau local)' : ''}${MDP ? '  (mot de passe demandé)' : ''}`));
