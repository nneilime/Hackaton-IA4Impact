// Chargement des tables du kit depuis le disque (côté serveur et outils).
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { lireCsv } from './csv.js';

export const FICHIERS = {
  residences: '01_residences.csv',
  batiments: '02_batiments.csv',
  logements: '03_logements.csv',
  equipements: '04_equipements.csv',
  demandes: '05_demandes_locataires.csv',
  interventions: '06_interventions.csv',
  commandes: '07_commandes.csv',
  plan: '08_plan_investissement.csv',
  prestataires: '09_prestataires.csv',
  familles: '10_ref_familles_equipements.csv',
  seuilsDpe: '10_ref_seuils_dpe.csv',
};

// Chaque fichier est pris dans le dossier d'import le plus récent qui le contient,
// sinon dans le dossier d'origine du kit.
export function chargerTables(dossiers) {
  const tables = {}, sources = {};
  for (const [cle, nom] of Object.entries(FICHIERS)) {
    const dossier = dossiers.find((d) => existsSync(join(d, nom)));
    if (!dossier) throw new Error(`Fichier introuvable : ${nom}`);
    tables[cle] = lireCsv(readFileSync(join(dossier, nom), 'utf8'));
    sources[cle] = dossier;
  }
  return { tables, sources };
}
