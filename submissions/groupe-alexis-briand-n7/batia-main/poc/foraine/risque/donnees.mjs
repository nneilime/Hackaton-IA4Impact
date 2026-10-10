// Chargement des fichiers CSV du kit BatIA (aucune dépendance externe).
// Toutes les valeurs restent des chaînes, telles qu'elles figurent dans les fichiers.

import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

// Nom de la table renvoyée → préfixe du fichier CSV dans le dossier.
const FICHIERS = {
  residences: '01_residences',
  batiments: '02_batiments',
  logements: '03_logements',
  equipements: '04_equipements',
  demandes: '05_demandes_locataires',
  interventions: '06_interventions',
  commandes: '07_commandes',
  plan: '08_plan_investissement',
  prestataires: '09_prestataires',
  familles: '10_ref_familles_equipements',
  codesMetiers: '10_ref_codes_metiers',
  motifs: '10_ref_motifs_demandes',
  seuilsDpe: '10_ref_seuils_dpe',
};

// Tables qui peuvent recevoir un trimestre importé, avec leur identifiant.
const TABLES_IMPORTABLES = { demandes: 'demande_id', interventions: 'intervention_id' };

/**
 * Lit un texte CSV (séparateur virgule, guillemets doubles, "" pour un guillemet,
 * virgules et sauts de ligne possibles entre guillemets, fins de ligne LF ou CRLF).
 * Renvoie un tableau d'objets indexés par l'en-tête ; la liste des colonnes est
 * disponible dans la propriété non énumérable `colonnes` du tableau.
 */
const GUILLEMET = 34, VIRGULE = 44, LF = 10, CR = 13;
const finDeChamp = (c) => c === VIRGULE || c === LF || c === CR;

export function lireCsv(texte) {
  if (texte.charCodeAt(0) === 0xfeff) texte = texte.slice(1); // BOM UTF-8
  const lignes = [];
  let ligne = [];
  const n = texte.length;
  let i = 0;

  // Lecture champ par champ, par tranches (bien plus rapide que caractère par caractère).
  while (i < n) {
    let valeur;
    if (texte.charCodeAt(i) === GUILLEMET) {
      valeur = '';
      let debut = i + 1;
      for (;;) {
        const q = texte.indexOf('"', debut);
        if (q === -1) { valeur += texte.slice(debut); i = n; break; } // guillemet jamais refermé
        valeur += texte.slice(debut, q);
        if (texte.charCodeAt(q + 1) === GUILLEMET) { valeur += '"'; debut = q + 2; continue; }
        i = q + 1;
        break;
      }
      // Caractères parasites après le guillemet fermant : conservés tels quels.
      let j = i;
      while (j < n && !finDeChamp(texte.charCodeAt(j))) j++;
      if (j > i) valeur += texte.slice(i, j);
      i = j;
    } else {
      let j = i;
      while (j < n && !finDeChamp(texte.charCodeAt(j))) j++;
      valeur = texte.slice(i, j);
      i = j;
    }
    ligne.push(valeur);

    if (i >= n) break;
    const c = texte.charCodeAt(i);
    if (c === VIRGULE) {
      i++;
      if (i === n) ligne.push(''); // virgule finale : dernier champ vide
      continue;
    }
    lignes.push(ligne); // fin de ligne (LF ou CRLF)
    ligne = [];
    i += (c === CR && texte.charCodeAt(i + 1) === LF) ? 2 : 1;
  }
  if (ligne.length > 0) lignes.push(ligne);

  // Lignes entièrement vides ignorées (fin de fichier, lignes blanches).
  const utiles = lignes.filter((l) => !(l.length === 1 && l[0] === ''));
  const colonnes = (utiles.shift() ?? []).map((c) => c.trim());
  const objets = utiles.map((valeurs) => {
    const objet = {};
    colonnes.forEach((col, k) => { objet[col] = valeurs[k] ?? ''; });
    return objet;
  });
  Object.defineProperty(objets, 'colonnes', { value: colonnes, enumerable: false });
  return objets;
}

function lireFichier(chemin) {
  return lireCsv(readFileSync(chemin, 'utf8'));
}

// Retrouve le fichier « préfixe.csv » dans le dossier (insensible à la casse de l'extension).
function trouverFichier(dossier, prefixe, contenu) {
  const nom = contenu.find((f) => f.toLowerCase() === `${prefixe.toLowerCase()}.csv`);
  if (!nom) throw new Error(`Fichier ${prefixe}.csv introuvable dans ${dossier}`);
  return join(dossier, nom);
}

// Même jeu de colonnes, quel que soit leur ordre.
const memeColonnes = (a, b) => a.length === b.length && a.every((c) => b.includes(c));

/**
 * Charge toutes les tables du dossier, puis ajoute les trimestres importés
 * (fichiers au format de 05_demandes_locataires ou 06_interventions).
 */
export function chargerDonnees(dossier, { imports = [] } = {}) {
  const contenu = readdirSync(dossier);
  const donnees = {};
  for (const [table, prefixe] of Object.entries(FICHIERS)) {
    donnees[table] = lireFichier(trouverFichier(dossier, prefixe, contenu));
  }

  for (const chemin of imports) {
    const lignes = lireFichier(chemin);
    const table = Object.keys(TABLES_IMPORTABLES)
      .find((t) => memeColonnes(lignes.colonnes, donnees[t].colonnes));
    if (!table) {
      throw new Error(`Import ${chemin} : en-tête différent de 05_demandes_locataires et de 06_interventions`);
    }
    const cle = TABLES_IMPORTABLES[table];
    const connus = new Set(donnees[table].map((l) => l[cle]));
    for (const l of lignes) {
      if (!l[cle] || connus.has(l[cle])) continue; // identifiant déjà présent : ignoré
      connus.add(l[cle]);
      donnees[table].push(l);
    }
  }
  return donnees;
}

/** Date la plus récente des interventions et des demandes (AAAA-MM-JJ), ou null. */
export function dateDuReleve(donnees) {
  let max = '';
  for (const i of donnees.interventions) {
    const d = (i.date_intervention ?? '').slice(0, 10);
    if (d > max) max = d;
  }
  for (const d of donnees.demandes) {
    const j = (d.date_creation ?? '').slice(0, 10);
    if (j > max) max = j;
  }
  return max || null;
}
