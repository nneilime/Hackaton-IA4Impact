#!/usr/bin/env node
// Vérification du module de risque : node risque/verifier.mjs [dossier des CSV] [import.csv ...]

import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { chargerDonnees, dateDuReleve } from './donnees.mjs';
import { METHODE, SEUILS, evaluerRisques, validerDansLePasse } from './risque.mjs';

const ici = dirname(fileURLToPath(import.meta.url));
const dossier = process.argv[2] ?? join(ici, '..', 'donnees', 'kit-batia', 'donnees');
const imports = process.argv.slice(3);

const debut = performance.now();
const donnees = chargerDonnees(dossier, { imports });
const tChargement = performance.now() - debut;
const dateReference = dateDuReleve(donnees);

const t0 = performance.now();
const risques = evaluerRisques(donnees, { dateReference });
const tCalcul = performance.now() - t0;

console.log(`${METHODE.nom} (v${METHODE.version})`);
console.log(METHODE.resume);
console.log(`\nDonnées : ${dossier}${imports.length ? ` + ${imports.length} import(s)` : ''}`);
console.log(`Date du relevé : ${dateReference}`);
console.log(`Chargement : ${tChargement.toFixed(0)} ms — evaluerRisques : ${tCalcul.toFixed(0)} ms`);

const comptes = { visiter: 0, surveiller: 0, calme: 0 };
for (const r of risques.values()) comptes[r.niveau]++;
console.log(`\nSeuils sur le score : visiter ≥ ${SEUILS.visiter}, surveiller ≥ ${SEUILS.surveiller}`);
console.log(`Équipements : ${risques.size} — visiter ${comptes.visiter}, surveiller ${comptes.surveiller}, calme ${comptes.calme}`);

console.log('\n10 premiers équipements :');
let rang = 0;
for (const [id, r] of risques) {
  if (++rang > 10) break;
  const f = r.faits;
  console.log(`\n${rang}. ${id} — score ${r.score} (${(r.probabilite * 100).toFixed(1)} %) — ${r.niveau}`);
  console.log(`   posé le ${f.datePose}, ${f.ageAns} ans / ${f.dureeVieAns} ans prévus ; ${f.depannages12m} dépannages et ${f.arrets12m} arrêts totaux sur 12 mois ; `
    + `visites manquées ${f.visitesManquees}/${f.visitesPrevues} ; demandes ${f.demandes12m}`);
  for (const raison of r.raisons) console.log(`   - [${raison.poids.toFixed(3)}] ${raison.texte}\n       court : ${raison.court}`);
}

const t1 = performance.now();
const v = validerDansLePasse(donnees);
const tValidation = performance.now() - t1;
console.log(`\nValidation dans le passé (${tValidation.toFixed(0)} ms) : modèle appris sur ${v.references.join(', ')}, testé au ${v.dateTest}`);
console.log(`Horizon ${v.horizon} : ${v.pannes} équipements en panne bloquante sur ${v.equipements}`);
console.log(`AUC : méthode ${v.auc.methode.toFixed(4)} — âge seul ${v.auc.ageSeul.toFixed(4)}`);
for (const t of v.top) {
  const hasard = (t.n * v.pannes) / v.equipements;
  console.log(`Top ${t.n} : méthode ${t.methode} pannes — âge seul ${t.ageSeul} — au hasard ≈ ${hasard.toFixed(1)}`);
}
console.log(`\nTemps total : ${(performance.now() - debut).toFixed(0)} ms`);
