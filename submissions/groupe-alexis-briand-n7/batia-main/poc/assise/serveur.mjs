// Assise — serveur local, sans dépendance. Lancement : node serveur.mjs
// Les données restent sur cette machine : aucun appel sortant n'est fait par ce serveur.
import { createServer } from 'node:http';
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync, statSync, createReadStream } from 'node:fs';
import { join, normalize, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';
import { chargerTables, FICHIERS } from './app/lib/chargement.mjs';
import { evaluerRisques, POIDS, SEUILS, HORIZON_MOIS, dateLongue } from './app/lib/risque.js';
import { eprouver } from './app/lib/epreuve.js';
import { lireCsv, ecrireCsv } from './app/lib/csv.js';

const RACINE = dirname(fileURLToPath(import.meta.url));
const APP = join(RACINE, 'app');
const KIT = join(RACINE, 'donnees', 'kit-batia', 'donnees');
const LOCAL = process.env.ETAT_LOCAL || join(RACINE, 'etat-local');
const IMPORTS = join(LOCAL, 'imports');
const FICHIER_DECISIONS = join(LOCAL, 'decisions.json');
const PORT = Number(process.env.PORT || 4321);
const HOTE = process.argv.includes('--reseau') ? '0.0.0.0' : '127.0.0.1';

// Positions fictives : les résidences du kit n'ont pas d'adresse. Elles sont placées
// comme des secteurs (cercles de plusieurs centaines de mètres), jamais sur un immeuble.
const POSITIONS = {
  'RES-A': [43.646, 1.392], 'RES-B': [43.668, 1.447], 'RES-C': [43.618, 1.486], 'RES-D': [43.566, 1.398],
  'RES-E': [43.584, 1.522], 'RES-F': [43.652, 1.503], 'RES-G': [43.574, 1.452], 'RES-H': [43.617, 1.346],
};

let etat, index;

function dossiersDeDonnees() {
  const imports = existsSync(IMPORTS) ? readdirSync(IMPORTS).filter((d) => statSync(join(IMPORTS, d)).isDirectory()).sort().reverse().map((d) => join(IMPORTS, d)) : [];
  return [...imports, KIT];
}

function lireDecisions() {
  try { return JSON.parse(readFileSync(FICHIER_DECISIONS, 'utf8')); } catch { return {}; }
}

function calculer() {
  const t0 = Date.now();
  const { tables, sources } = chargerTables(dossiersDeDonnees());
  const dateDonnees = tables.interventions.reduce((m, it) => (it.date_intervention > m ? it.date_intervention : m), '').slice(0, 10);
  // Fin d'horizon : dernier jour du 9ᵉ mois qui suit la date des données (31/12/2025 → 30/09/2026).
  const finDe = (iso) => { const d = new Date(Date.parse(iso) + 86400000); d.setUTCMonth(d.getUTCMonth() + HORIZON_MOIS); return new Date(d - 86400000).toISOString().slice(0, 10); };
  const finHorizon = finDe(dateDonnees);
  const risques = evaluerRisques(tables, dateDonnees);
  const unAn = new Date(Date.parse(dateDonnees) - 365 * 86400000).toISOString().slice(0, 10);
  const avant = (d) => { const x = new Date(dateDonnees); x.setUTCFullYear(x.getUTCFullYear() - 1); return x.toISOString().slice(0, 10); };
  const refDate = avant();
  const epreuve = eprouver(tables, { dateReference: refDate, debut: new Date(Date.parse(refDate) + 86400000).toISOString().slice(0, 10), fin: finDe(refDate) });

  const familles = new Map(tables.familles.map((f) => [f.famille, f]));
  const prestataires = new Map(tables.prestataires.map((p) => [p.prestataire_id, p]));
  const logementsParId = new Map(tables.logements.map((l) => [l.logement_id, l]));

  const demandesParLogement = new Map();
  for (const d of tables.demandes) {
    const cle = d.logement_id || d.batiment_id;
    if (!demandesParLogement.has(cle)) demandesParLogement.set(cle, []);
    demandesParLogement.get(cle).push(d);
  }
  const interventionsParLieu = new Map();
  const interventionsParEquipement = new Map();
  for (const it of tables.interventions) {
    const cle = it.logement_id || it.batiment_id;
    if (!interventionsParLieu.has(cle)) interventionsParLieu.set(cle, []);
    interventionsParLieu.get(cle).push(it);
    if (!interventionsParEquipement.has(it.equipement_id)) interventionsParEquipement.set(it.equipement_id, []);
    interventionsParEquipement.get(it.equipement_id).push(it);
  }

  const equipements = [];
  const tousEquipements = new Map();
  for (const e of tables.equipements) {
    const f = familles.get(e.famille) || {};
    const lgt = logementsParId.get(e.logement_id);
    const base = {
      id: e.equipement_id, famille: e.famille, libelle: e.libelle_famille, rattachement: e.niveau_rattachement,
      residence: e.residence_id, batiment: e.batiment_id, logement: e.logement_id || null, etage: lgt ? Number(lgt.etage) : null,
      pose: e.date_pose, vieRef: Number(e.duree_vie_reference_ans), contrat: e.sous_contrat_entretien === 'Oui',
      prestataire: e.prestataire_id, coutMin: Number(f.cout_remplacement_min_ttc) || null, coutMax: Number(f.cout_remplacement_max_ttc) || null,
      suivi: e.dans_perimetre_prediction === 'Oui',
    };
    const r = risques.get(e.equipement_id);
    if (r) Object.assign(base, { score: r.score, niveau: r.niveau, raisons: r.raisons, mesures: r.mesures });
    tousEquipements.set(e.equipement_id, base);
    if (r) equipements.push(base);
  }
  equipements.sort((a, b) => b.score - a.score || b.mesures.age / b.vieRef - a.mesures.age / a.vieRef);
  equipements.forEach((e, i) => (e.rang = i + 1));

  const risqueParLogement = new Map();
  for (const e of equipements) if (e.logement) {
    const r = risqueParLogement.get(e.logement);
    if (!r || r.score < e.score) risqueParLogement.set(e.logement, { score: e.score, niveau: e.niveau });
  }
  const risqueParBatiment = new Map();
  for (const e of equipements) {
    const r = risqueParBatiment.get(e.batiment) || { prioritaire: 0, surveiller: 0 };
    if (e.niveau !== 'calme') r[e.niveau]++;
    risqueParBatiment.set(e.batiment, r);
  }

  const logements = tables.logements.map((l) => {
    const dem = demandesParLogement.get(l.logement_id) || [];
    const dem12 = dem.filter((d) => d.date_creation.slice(0, 10) > unAn);
    const r = risqueParLogement.get(l.logement_id);
    return {
      id: l.logement_id, batiment: l.batiment_id, residence: l.residence_id, typologie: l.typologie, surface: Number(l.surface_habitable_m2),
      etage: Number(l.etage), statut: l.statut_occupation,
      dpe: l.dpe_etiquette_globale, dpeEnergie: l.dpe_etiquette_energie, dpeGes: l.dpe_etiquette_ges, conso: Number(l.dpe_conso_ep_kwh_m2_an), ges: Number(l.dpe_ges_kgco2_m2_an), dpeDate: l.dpe_date, dpeMethode: l.dpe_methode,
      demandes: dem.length, demandes12m: dem12.length, rouvertes12m: dem12.filter((d) => d.demande_reouverte === 'Oui').length,
      score: r ? r.score : null, niveau: r ? r.niveau : null,
    };
  });

  const residences = tables.residences.map((r) => {
    const eq = equipements.filter((e) => e.residence === r.residence_id);
    const lg = logements.filter((l) => l.residence === r.residence_id);
    return {
      id: r.residence_id, nom: r.nom, lettre: r.residence_id.slice(-1), annee: Number(r.annee_construction), logements: Number(r.nb_logements), batiments: Number(r.nb_batiments),
      ascenseur: r.ascenseur === 'Oui', energie: r.energie_chauffage, chauffage: r.generateur_chauffage, ecs: r.production_ecs, ventilation: r.ventilation,
      dpe: r.etiquette_dpe_majoritaire, conso: Number(r.conso_ep_moyenne_kwh_m2_an), localisation: r.localisation, position: POSITIONS[r.residence_id] || null,
      suivis: eq.length, prioritaire: eq.filter((e) => e.niveau === 'prioritaire').length, surveiller: eq.filter((e) => e.niveau === 'surveiller').length,
      logementsARisque: new Set(eq.filter((e) => e.niveau === 'prioritaire' && e.logement).map((e) => e.logement)).size,
      demandes12m: lg.reduce((s, l) => s + l.demandes12m, 0) + (tables.demandes.filter((d) => d.residence_id === r.residence_id && !d.logement_id && d.date_creation.slice(0, 10) > unAn).length),
    };
  });
  const batiments = tables.batiments.map((b) => ({ id: b.batiment_id, residence: b.residence_id, niveaux: Number(b.nb_niveaux), logements: Number(b.nb_logements), ascenseur: b.ascenseur === 'Oui', ...(risqueParBatiment.get(b.batiment_id) || { prioritaire: 0, surveiller: 0 }) }));

  const importes = Object.entries(sources).filter(([, d]) => d !== KIT).map(([k]) => FICHIERS[k]);
  etat = {
    meta: {
      dateDonnees, dateDonneesTexte: dateLongue(dateDonnees), finHorizon, finHorizonTexte: dateLongue(finHorizon), horizonMois: HORIZON_MOIS,
      trimestre: `T${Math.floor(Number(dateDonnees.slice(5, 7)) / 3.01) + 1} ${dateDonnees.slice(0, 4)}`,
      importes, calculeLe: new Date().toISOString(), dureeCalculMs: Date.now() - t0,
      logements: logements.length, suivis: equipements.length,
    },
    methode: { poids: POIDS, seuils: SEUILS, epreuve },
    residences, batiments, logements, equipements,
    prestataires: tables.prestataires.map((p) => ({ id: p.prestataire_id, nom: p.nom, domaine: p.domaine, contrat: p.type_contrat })),
    plan: tables.plan.map((o) => ({ id: o.operation_id, residence: o.residence_id, type: o.type_operation, perimetre: o.perimetre, annee: Number(o.annee_souhaitee), cout: Number(o.cout_estime_ttc), gain: Number(o.gain_conso_ep_estime_kwh_m2_an), logements: Number(o.nb_logements_concernes), inscription: o.date_inscription_demande, origine: o.origine_demande, statut: o.statut, rang: Number(o.rang_actuel_chronologique) })),
    seuilsDpe: tables.seuilsDpe,
  };
  index = { tables, demandesParLogement, interventionsParLieu, interventionsParEquipement, tousEquipements, prestataires, logementsParId };
  console.log(`Données au ${dateDonnees} — ${equipements.length} équipements suivis, calcul en ${etat.meta.dureeCalculMs} ms`);
}

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.woff2': 'font/woff2', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.ico': 'image/x-icon', '.pbf': 'application/x-protobuf', '.pmtiles': 'application/octet-stream' };

function envoyer(res, code, corps, type = 'application/json; charset=utf-8', entetes = {}) {
  res.writeHead(code, { 'Content-Type': type, 'Cache-Control': 'no-store', ...entetes });
  res.end(typeof corps === 'string' || Buffer.isBuffer(corps) ? corps : JSON.stringify(corps));
}

function lireCorps(req) {
  return new Promise((ok, ko) => {
    let taille = 0; const morceaux = [];
    req.on('data', (c) => { taille += c.length; if (taille > 80e6) { ko(new Error('Fichier trop volumineux')); req.destroy(); } else morceaux.push(c); });
    req.on('end', () => ok(Buffer.concat(morceaux).toString('utf8')));
    req.on('error', ko);
  });
}

const libelleDecision = { remplacer: 'Remplacer', diagnostiquer: 'Faire diagnostiquer', surveiller: 'Surveiller', ecarter: 'Écarter' };

function lieuTexte(e) {
  const l = e.logement ? index.logementsParId.get(e.logement) : null;
  return l ? `Résidence ${e.residence.slice(-1)}, bâtiment ${e.batiment.slice(4)}, logement ${e.logement.slice(-3)}` : `Résidence ${e.residence.slice(-1)}, bâtiment ${e.batiment.slice(4)} (parties communes)`;
}

const serveur = createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const p = decodeURIComponent(url.pathname);
  try {
    if (p === '/api/etat') {
      // ~1,3 Mo de JSON : compressé pour le téléphone
      const corps = JSON.stringify({ ...etat, decisions: lireDecisions() });
      if (/\bgzip\b/.test(req.headers['accept-encoding'] || '')) return envoyer(res, 200, gzipSync(corps), 'application/json; charset=utf-8', { 'Content-Encoding': 'gzip' });
      return envoyer(res, 200, corps);
    }

    if (p.startsWith('/api/logement/')) {
      const id = p.split('/').pop();
      const l = index.logementsParId.get(id);
      if (!l) return envoyer(res, 404, { erreur: 'Logement inconnu' });
      const demandes = (index.demandesParLogement.get(id) || []).slice().sort((a, b) => b.date_creation.localeCompare(a.date_creation))
        .map((d) => ({ id: d.demande_id, date: d.date_creation, cloture: d.date_cloture, canal: d.canal, motif: d.motif, objet: d.objet, texte: d.texte_demande, priorite: d.priorite, rouverte: d.demande_reouverte === 'Oui', delai: Number(d.delai_resolution_h) }));
      const interventions = (index.interventionsParLieu.get(id) || []).slice().sort((a, b) => b.date_intervention.localeCompare(a.date_intervention))
        .map((it) => ({ id: it.intervention_id, date: it.date_intervention, equipement: it.equipement_id, type: it.type_intervention, symptome: it.symptome, gravite: it.gravite, resultat: it.resultat, commentaire: it.commentaire_technicien, prestataire: it.prestataire_id, demande: it.demande_id_liee }));
      const equipements = [...index.tousEquipements.values()].filter((e) => e.logement === id);
      return envoyer(res, 200, { demandes, interventions, equipements });
    }

    if (p.startsWith('/api/equipement/')) {
      const id = p.split('/').pop();
      const e = index.tousEquipements.get(id);
      if (!e) return envoyer(res, 404, { erreur: 'Équipement inconnu' });
      const interventions = (index.interventionsParEquipement.get(id) || []).slice().sort((a, b) => b.date_intervention.localeCompare(a.date_intervention))
        .map((it) => ({ id: it.intervention_id, date: it.date_intervention, type: it.type_intervention, symptome: it.symptome, gravite: it.gravite, resultat: it.resultat, commentaire: it.commentaire_technicien, demande: it.demande_id_liee }));
      return envoyer(res, 200, { interventions });
    }

    if (p === '/api/decision' && req.method === 'POST') {
      const { equipement, decision, note, auteur } = JSON.parse(await lireCorps(req));
      if (!index.tousEquipements.has(equipement)) return envoyer(res, 400, { erreur: 'Équipement inconnu' });
      const decisions = lireDecisions();
      if (!decision) delete decisions[equipement];
      else if (!libelleDecision[decision]) return envoyer(res, 400, { erreur: 'Décision inconnue' });
      else decisions[equipement] = { decision, note: String(note || '').slice(0, 1000), auteur: String(auteur || '').slice(0, 60), date: new Date().toISOString() };
      mkdirSync(LOCAL, { recursive: true });
      writeFileSync(FICHIER_DECISIONS, JSON.stringify(decisions, null, 1));
      return envoyer(res, 200, { decisions });
    }

    if (p === '/api/import' && req.method === 'POST') {
      const { fichiers } = JSON.parse(await lireCorps(req));
      const attendus = new Map(Object.values(FICHIERS).map((n) => [n, Object.keys(lireCsv(readFileSync(join(KIT, n), 'utf8').split('\n').slice(0, 2).join('\n'))[0])]));
      const retenus = [], refuses = [];
      for (const [nom, contenu] of Object.entries(fichiers || {})) {
        if (!attendus.has(nom)) { refuses.push({ nom, raison: 'nom de fichier non reconnu' }); continue; }
        const lignes = lireCsv(contenu);
        const manquantes = attendus.get(nom).filter((c) => !(lignes[0] && c in lignes[0]));
        if (!lignes.length || manquantes.length) { refuses.push({ nom, raison: manquantes.length ? `colonnes manquantes : ${manquantes.join(', ')}` : 'fichier vide' }); continue; }
        retenus.push({ nom, contenu, lignes: lignes.length });
      }
      if (!retenus.length) return envoyer(res, 400, { erreur: 'Aucun fichier exploitable', refuses });
      const dossier = join(IMPORTS, new Date().toISOString().replace(/[:.]/g, '-'));
      mkdirSync(dossier, { recursive: true });
      for (const f of retenus) writeFileSync(join(dossier, f.nom), f.contenu);
      try { calculer(); } catch (err) {
        writeFileSync(join(dossier, 'REFUSE.txt'), String(err));
        const { renameSync } = await import('node:fs'); renameSync(dossier, dossier + '-refuse');
        calculer();
        return envoyer(res, 400, { erreur: `Import annulé : ${err.message}`, refuses });
      }
      return envoyer(res, 200, { retenus: retenus.map(({ nom, lignes }) => ({ nom, lignes })), refuses, meta: etat.meta });
    }

    if (p === '/export/risques.csv') {
      const decisions = lireDecisions();
      const lignes = etat.equipements.map((e) => ({
        rang: e.rang, equipement_id: e.id, score_risque: e.score, niveau: { prioritaire: 'Prioritaire', surveiller: 'À surveiller', calme: 'Sans alerte' }[e.niveau],
        equipement: e.libelle, lieu: lieuTexte(e), prestataire: index.prestataires.get(e.prestataire)?.nom || e.prestataire,
        raisons: e.raisons.map((r) => r.texte).join(' | '), decision: libelleDecision[decisions[e.id]?.decision] || '', note: decisions[e.id]?.note || '',
      }));
      return envoyer(res, 200, '﻿' + ecrireCsv(lignes, ['rang', 'equipement_id', 'score_risque', 'niveau', 'equipement', 'lieu', 'prestataire', 'raisons', 'decision', 'note']), 'text/csv; charset=utf-8', { 'Content-Disposition': `attachment; filename="assise-risques-${etat.meta.dateDonnees}.csv"` });
    }

    if (p === '/export/decisions.csv') {
      const decisions = lireDecisions();
      const filtre = url.searchParams.get('prestataire');
      const lignes = Object.entries(decisions).map(([id, d]) => ({ e: index.tousEquipements.get(id), d })).filter(({ e, d }) => e && (!filtre || e.prestataire === filtre) && d.decision !== 'ecarter')
        .sort((a, b) => (b.e.score ?? 0) - (a.e.score ?? 0))
        .map(({ e, d }) => {
          const faits = (e.raisons || []).filter((r) => r.points > 0);
          const motifs = [...faits.filter((r) => r.type !== 'usure'), ...faits.filter((r) => r.type === 'usure')].slice(0, 2).map((r) => r.texte).join(' / ');
          return {
            decision: libelleDecision[d.decision], equipement: e.libelle, equipement_id: e.id, lieu: lieuTexte(e),
            etage: e.etage == null ? 'parties communes' : e.etage === 0 ? 'rez-de-chaussée' : `${e.etage === 1 ? '1er' : e.etage + 'e'} étage`,
            prestataire: index.prestataires.get(e.prestataire)?.nom || e.prestataire, cout_reference_ttc: e.coutMin ? `${e.coutMin} à ${e.coutMax} €` : '',
            motifs, note: d.note, decide_le: d.date.slice(0, 10).split('-').reverse().join('/'), par: d.auteur,
          };
        });
      // la liste d'un prestataire est un bon de travail : sans notre coût de référence ; séparateur « ; » pour un tableur français
      const colonnes = filtre
        ? ['equipement_id', 'decision', 'equipement', 'lieu', 'etage', 'motifs', 'note', 'decide_le', 'par']
        : ['equipement_id', 'decision', 'equipement', 'lieu', 'etage', 'prestataire', 'cout_reference_ttc', 'motifs', 'note', 'decide_le', 'par'];
      const noms = { equipement_id: 'Référence', decision: 'Décision', equipement: 'Équipement', lieu: 'Lieu', etage: 'Étage', prestataire: 'Prestataire', cout_reference_ttc: 'Coût de référence TTC', motifs: 'Constats', note: 'Note', decide_le: 'Décidé le', par: 'Par' };
      const nomFichier = filtre ? 'assise-' + (index.prestataires.get(filtre)?.nom || filtre).replace(' (fictif)', '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^A-Za-z0-9]+/g, '-').toLowerCase() : 'assise-decisions';
      return envoyer(res, 200, '﻿' + ecrireCsv(lignes, colonnes, { sep: ';', entetes: colonnes.map((c) => noms[c]) }), 'text/csv; charset=utf-8', { 'Content-Disposition': `attachment; filename="${nomFichier}.csv"` });
    }

    if (p === '/export/scores.csv') {
      return envoyer(res, 200, ecrireCsv(etat.equipements.map((e) => ({ equipement_id: e.id, score_risque: e.score })), ['equipement_id', 'score_risque']), 'text/csv; charset=utf-8', { 'Content-Disposition': 'attachment; filename="scores_risque.csv"' });
    }

    // Fichiers de l'application
    const chemin = normalize(join(APP, p === '/' ? 'index.html' : p));
    if (!chemin.startsWith(APP) || !existsSync(chemin) || statSync(chemin).isDirectory()) {
      if (!extname(p)) return envoyer(res, 200, readFileSync(join(APP, 'index.html')), TYPES['.html']);
      return envoyer(res, 404, 'Introuvable', 'text/plain; charset=utf-8');
    }
    // fond de carte local : lu par plages (Range), sans charger l'archive entière
    const plage = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range || '');
    if (plage && (plage[1] || plage[2])) {
      const taille = statSync(chemin).size;
      const debut = plage[1] ? Number(plage[1]) : Math.max(0, taille - Number(plage[2]));
      const fin = plage[1] && plage[2] ? Math.min(Number(plage[2]), taille - 1) : taille - 1;
      if (debut >= taille || debut > fin) { res.writeHead(416, { 'Content-Range': `bytes */${taille}` }); return res.end(); }
      res.writeHead(206, { 'Content-Type': TYPES[extname(chemin)] || 'application/octet-stream', 'Content-Length': fin - debut + 1, 'Content-Range': `bytes ${debut}-${fin}/${taille}`, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-cache' });
      return createReadStream(chemin, { start: debut, end: fin }).pipe(res);
    }
    return envoyer(res, 200, readFileSync(chemin), TYPES[extname(chemin)] || 'application/octet-stream');
  } catch (err) {
    console.error(err);
    return envoyer(res, 500, { erreur: err.message });
  }
});

calculer();
serveur.listen(PORT, HOTE, () => {
  console.log(`\n  Assise est prête : http://localhost:${PORT}\n`);
  if (HOTE === '0.0.0.0') console.log('  (accessible depuis les autres appareils du réseau local, pour le téléphone)\n');
});
