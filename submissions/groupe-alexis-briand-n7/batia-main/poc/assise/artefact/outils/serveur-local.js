// Assise, copie en ligne : le serveur local (serveur.mjs) est rejoué dans le navigateur.
// Les tables du kit sont lues depuis donnees/, les décisions restent dans ce navigateur.
import { evaluerRisques, POIDS, SEUILS, HORIZON_MOIS, dateLongue } from './lib/risque.js';
import { eprouver } from './lib/epreuve.js';
import { lireCsv, ecrireCsv } from './lib/csv.js';

const FICHIERS = {
  residences: '01_residences.csv', batiments: '02_batiments.csv', logements: '03_logements.csv', equipements: '04_equipements.csv',
  demandes: '05_demandes_locataires.csv', interventions: '06_interventions.csv', commandes: '07_commandes.csv', plan: '08_plan_investissement.csv',
  prestataires: '09_prestataires.csv', familles: '10_ref_familles_equipements.csv', seuilsDpe: '10_ref_seuils_dpe.csv',
};
const POSITIONS = {
  'RES-A': [43.646, 1.392], 'RES-B': [43.668, 1.447], 'RES-C': [43.618, 1.486], 'RES-D': [43.566, 1.398],
  'RES-E': [43.584, 1.522], 'RES-F': [43.652, 1.503], 'RES-G': [43.574, 1.452], 'RES-H': [43.617, 1.346],
};
const BASE = new URL('.', import.meta.url).href;
const fetchReseau = window.fetch.bind(window);
const kit = {};
let importes = {};
let etat, index;

let decisionsMemoire = {};
function lireDecisions() { try { return JSON.parse(localStorage.getItem('assise.decisions') || '{}'); } catch { return decisionsMemoire; } }
function ecrireDecisions(d) { decisionsMemoire = d; try { localStorage.setItem('assise.decisions', JSON.stringify(d)); } catch { /* navigation privée */ } }

function chargerTables() {
  const tables = {}, sources = {};
  for (const [cle, nom] of Object.entries(FICHIERS)) {
    tables[cle] = lireCsv(importes[nom] ?? kit[nom]);
    sources[cle] = importes[nom] ? 'import' : 'kit';
  }
  return { tables, sources };
}

function calculer() {
  const t0 = Date.now();
  const { tables, sources } = chargerTables();
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

  const importesNoms = Object.entries(sources).filter(([, d]) => d !== 'kit').map(([k]) => FICHIERS[k]);
  etat = {
    meta: {
      dateDonnees, dateDonneesTexte: dateLongue(dateDonnees), finHorizon, finHorizonTexte: dateLongue(finHorizon), horizonMois: HORIZON_MOIS,
      trimestre: `T${Math.floor(Number(dateDonnees.slice(5, 7)) / 3.01) + 1} ${dateDonnees.slice(0, 4)}`,
      importes: importesNoms, calculeLe: new Date().toISOString(), dureeCalculMs: Date.now() - t0,
      logements: logements.length, suivis: equipements.length,
    },
    methode: { poids: POIDS, seuils: SEUILS, epreuve },
    residences, batiments, logements, equipements,
    prestataires: tables.prestataires.map((p) => ({ id: p.prestataire_id, nom: p.nom, domaine: p.domaine, contrat: p.type_contrat })),
    plan: tables.plan.map((o) => ({ id: o.operation_id, residence: o.residence_id, type: o.type_operation, perimetre: o.perimetre, annee: Number(o.annee_souhaitee), cout: Number(o.cout_estime_ttc), gain: Number(o.gain_conso_ep_estime_kwh_m2_an), logements: Number(o.nb_logements_concernes), inscription: o.date_inscription_demande, origine: o.origine_demande, statut: o.statut, rang: Number(o.rang_actuel_chronologique) })),
    seuilsDpe: tables.seuilsDpe,
  };
  index = { tables, demandesParLogement, interventionsParLieu, interventionsParEquipement, tousEquipements, prestataires, logementsParId };
  console.info(`Données au ${dateDonnees} — ${equipements.length} équipements suivis, calcul en ${etat.meta.dureeCalculMs} ms`);
}

const libelleDecision = { remplacer: 'Remplacer', diagnostiquer: 'Faire diagnostiquer', surveiller: 'Surveiller', ecarter: 'Écarter' };

function lieuTexte(e) {
  const l = e.logement ? index.logementsParId.get(e.logement) : null;
  return l ? `Résidence ${e.residence.slice(-1)}, bâtiment ${e.batiment.slice(4)}, logement ${e.logement.slice(-3)}` : `Résidence ${e.residence.slice(-1)}, bâtiment ${e.batiment.slice(4)} (parties communes)`;
}


function json(corps, status = 200) { return new Response(JSON.stringify(corps), { status, headers: { 'Content-Type': 'application/json; charset=utf-8' } }); }

async function repondre(chemin, init) {
  const url = new URL(chemin, 'http://local');
  const p = decodeURIComponent(url.pathname);
  const corps = () => JSON.parse(init?.body || '{}');
  if (p === '/api/etat') return json({ ...etat, decisions: lireDecisions() });
  if (p.startsWith('/api/logement/')) {
    const id = p.split('/').pop();
    const l = index.logementsParId.get(id);
    if (!l) return json({ erreur: 'Logement inconnu' }, 404);
    const demandes = (index.demandesParLogement.get(id) || []).slice().sort((a, b) => b.date_creation.localeCompare(a.date_creation))
      .map((d) => ({ id: d.demande_id, date: d.date_creation, cloture: d.date_cloture, canal: d.canal, motif: d.motif, objet: d.objet, texte: d.texte_demande, priorite: d.priorite, rouverte: d.demande_reouverte === 'Oui', delai: Number(d.delai_resolution_h) }));
    const interventions = (index.interventionsParLieu.get(id) || []).slice().sort((a, b) => b.date_intervention.localeCompare(a.date_intervention))
      .map((it) => ({ id: it.intervention_id, date: it.date_intervention, equipement: it.equipement_id, type: it.type_intervention, symptome: it.symptome, gravite: it.gravite, resultat: it.resultat, commentaire: it.commentaire_technicien, prestataire: it.prestataire_id, demande: it.demande_id_liee }));
    const equipements = [...index.tousEquipements.values()].filter((e) => e.logement === id);
    return json({ demandes, interventions, equipements });
  }
  if (p.startsWith('/api/equipement/')) {
    const id = p.split('/').pop();
    const e = index.tousEquipements.get(id);
    if (!e) return json({ erreur: 'Équipement inconnu' }, 404);
    const interventions = (index.interventionsParEquipement.get(id) || []).slice().sort((a, b) => b.date_intervention.localeCompare(a.date_intervention))
      .map((it) => ({ id: it.intervention_id, date: it.date_intervention, type: it.type_intervention, symptome: it.symptome, gravite: it.gravite, resultat: it.resultat, commentaire: it.commentaire_technicien, demande: it.demande_id_liee }));
    return json({ interventions });
  }
  if (p === '/api/decision') {
    const { equipement, decision, note, auteur } = corps();
    if (!index.tousEquipements.has(equipement)) return json({ erreur: 'Équipement inconnu' }, 400);
    const decisions = lireDecisions();
    if (!decision) delete decisions[equipement];
    else if (!libelleDecision[decision]) return json({ erreur: 'Décision inconnue' }, 400);
    else decisions[equipement] = { decision, note: String(note || '').slice(0, 1000), auteur: String(auteur || '').slice(0, 60), date: new Date().toISOString() };
    ecrireDecisions(decisions);
    return json({ decisions });
  }
  if (p === '/api/import') {
    // Import tenu en mémoire le temps de la visite : rien n'est envoyé ni gardé.
    const { fichiers } = corps();
    const attendus = new Map(Object.values(FICHIERS).map((n) => [n, Object.keys(lireCsv(kit[n].split('\n').slice(0, 2).join('\n'))[0])]));
    const retenus = [], refuses = [];
    for (const [nom, contenu] of Object.entries(fichiers || {})) {
      if (!attendus.has(nom)) { refuses.push({ nom, raison: 'nom de fichier non reconnu' }); continue; }
      const lignes = lireCsv(contenu);
      const manquantes = attendus.get(nom).filter((c) => !(lignes[0] && c in lignes[0]));
      if (!lignes.length || manquantes.length) { refuses.push({ nom, raison: manquantes.length ? `colonnes manquantes : ${manquantes.join(', ')}` : 'fichier vide' }); continue; }
      retenus.push({ nom, contenu, lignes: lignes.length });
    }
    if (!retenus.length) return json({ erreur: 'Aucun fichier exploitable', refuses }, 400);
    const avant = importes;
    importes = { ...importes, ...Object.fromEntries(retenus.map((f) => [f.nom, f.contenu])) };
    try { calculer(); } catch (err) { importes = avant; calculer(); return json({ erreur: `Import annulé : ${err.message}`, refuses }, 400); }
    return json({ retenus: retenus.map(({ nom, lignes }) => ({ nom, lignes })), refuses, meta: etat.meta });
  }
  return json({ erreur: 'Introuvable' }, 404);
}

// Exports : le téléchargement est bloqué dans cette page, le tableau est copié pour être collé dans un tableur.
function exporter(chemin) {
  const url = new URL(chemin, 'http://local');
  const p = decodeURIComponent(url.pathname);
  const res = null; const envoyer = (_r, _c, corps) => corps;
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

  return null;
}
function annoncer(texte) {
  const a = document.getElementById('annonce'); if (!a) return;
  a.textContent = texte; a.classList.add('visible');
  clearTimeout(annoncer.t); annoncer.t = setTimeout(() => a.classList.remove('visible'), 3200);
}
document.addEventListener('click', (ev) => {
  const a = ev.target.closest?.('a[href^="/export/"]');
  if (!a) return;
  ev.preventDefault(); ev.stopPropagation();
  const csv = etat && exporter(a.getAttribute('href'));
  if (!csv) return annoncer('Tableau indisponible.');
  const texte = csv.replace(/^﻿/, '');
  try {
    navigator.clipboard.writeText(texte).then(() => annoncer('Tableau copié : à coller dans un tableur.'), () => annoncer('Copie refusée par le navigateur.'));
  } catch { annoncer('Copie refusée par le navigateur.'); }
}, true);

const pret = Promise.all(Object.values(FICHIERS).map(async (n) => {
  const r = await fetchReseau(BASE + 'donnees/' + n);
  if (!r.ok) throw new Error(`Fichier introuvable : ${n}`);
  kit[n] = await r.text();
})).then(calculer);

window.fetch = async (entree, init) => {
  if (typeof entree === 'string' && entree.startsWith('/api/')) { await pret; return repondre(entree, init); }
  return fetchReseau(entree, init);
};
