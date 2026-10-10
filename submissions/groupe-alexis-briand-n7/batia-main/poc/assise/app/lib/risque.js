// ─────────────────────────────────────────────────────────────────────────────
// Module de risque — remplaçable.
//
// Contrat (le seul que le reste de l'application connaît) :
//   evaluerRisques(tables, dateReference) → Map(equipement_id → {
//     score:   entier de 0 à 100 (plus il est haut, plus une panne bloquante est probable),
//     niveau:  'prioritaire' | 'surveiller' | 'calme',
//     raisons: [{ type, points, texte }]   (triées, la plus lourde d'abord),
//     mesures: { … valeurs brutes utiles à l'affichage … }
//   })
//
// tables : { equipements, interventions, demandes, logements } (lignes CSV du kit).
// dateReference : 'AAAA-MM-JJ'. Seul l'historique antérieur ou égal à cette date est lu,
// ce qui permet de rejouer la méthode dans le passé sans fuite d'information.
//
// Méthode : une somme de points, chaque point a une raison lisible. Les ingrédients
// suivent les règles de fabrication documentées dans l'onglet HYPOTHESES du kit :
// usure croissante avec l'âge (Weibull), vie raccourcie par les visites manquées et
// les grands logements, signaux faibles 10 à 20 mois avant une fin de vie.
// ─────────────────────────────────────────────────────────────────────────────

export const HORIZON_MOIS = 9;

export const POIDS = {
  usure: 40,               // maximum pour l'âge rapporté à la durée de vie retenue
  remplacementDemande: 12, // un technicien a conclu « remplacement nécessaire », rien remplacé depuis
  depannage12m: 6,         // par dépannage sur les 12 derniers mois (3 au plus)
  arretTotal12m: 5,        // en plus, par arrêt total sur les 12 derniers mois (2 au plus)
  signalTechnicien: 9,     // par commentaire d'usure sur les 18 derniers mois (3 au plus)
  anomalieVisite: 7,       // par anomalie constatée en visite sur les 18 derniers mois (2 au plus)
  demandeLocataire: 4,     // par demande du locataire liée, sur les 12 derniers mois (3 au plus)
};

export const SEUILS = { prioritaire: 45, surveiller: 22 };

export const COMMENTAIRES_USURE = new Set([
  'Usure avancée constatée, pièce à surveiller',
  'Appareil vieillissant, remplacement à prévoir',
  'Réparation provisoire, fiabilité incertaine',
  'Pièce de rechange difficile à obtenir',
  'Nombreux redémarrages enregistrés',
  "Traces de corrosion visibles sur l'appareil",
]);

// Motifs de demandes qui concernent chaque famille d'équipement.
const MOTIFS = {
  gaz: 'panne équipement individuel gaz (chauffe eau/chaudière, radiateur)',
  elec: 'Panne équipement individuel électrique (chauffe eau, radiateur)',
  froid: 'Température basse dans le logement',
  chaufferie: 'Absence de chauffage collectif',
  ascenseur: "Signalement d'une panne Ascenseur",
  vmc: 'VMC bruyante / Dysfonctionnement',
};
const MOTIFS_PAR_FAMILLE = {
  chaudiere_gaz_individuelle: [MOTIFS.gaz, MOTIFS.froid],
  pompe_a_chaleur: [MOTIFS.elec, MOTIFS.froid],
  ballon_thermodynamique: [MOTIFS.elec],
  ballon_ecs_electrique: [MOTIFS.elec],
  convecteurs_electriques: [MOTIFS.elec, MOTIFS.froid],
  panneaux_rayonnants: [MOTIFS.elec, MOTIFS.froid],
  chaufferie_collective: [MOTIFS.chaufferie, MOTIFS.froid],
  caisson_vmc: [MOTIFS.vmc],
  ascenseur: [MOTIFS.ascenseur],
  production_ecs_solaire: [],
};

const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
export function dateLongue(iso) {
  if (!iso) return '';
  const [a, m, j] = iso.slice(0, 10).split('-').map(Number);
  return `${j === 1 ? '1ᵉʳ' : j} ${MOIS[m - 1]} ${a}`;
}
const JOUR = 86400000;
const jours = (a, b) => (Date.parse(b) - Date.parse(a)) / JOUR;
const decaler = (iso, nbJours) => new Date(Date.parse(iso) + nbJours * JOUR).toISOString().slice(0, 10);
const pluriel = (n, un, plusieurs) => `${n} ${n > 1 ? plusieurs : un}`;
const arrondi = (x) => Math.round(x);

// Probabilité de fin de vie dans l'horizon, sachant qu'on a tenu jusqu'à l'âge a
// (loi de Weibull de forme k, d'échelle égale à la durée de vie retenue).
function probaFinDeVie(age, vie, horizonAns, k = 3.5) {
  const x0 = Math.pow(Math.max(age, 0) / vie, k);
  const x1 = Math.pow((Math.max(age, 0) + horizonAns) / vie, k);
  return 1 - Math.exp(x0 - x1);
}

export function evaluerRisques(tables, dateReference) {
  const fin = dateReference;
  const il12 = decaler(fin, -365);
  const il18 = decaler(fin, -548);

  const parEquipement = new Map();
  for (const it of tables.interventions) {
    if (!it.equipement_id || it.date_intervention.slice(0, 10) > fin) continue;
    if (!parEquipement.has(it.equipement_id)) parEquipement.set(it.equipement_id, []);
    parEquipement.get(it.equipement_id).push(it);
  }
  const demandesParId = new Map();
  const demandesParLieu = new Map();
  for (const d of tables.demandes) {
    if (d.date_creation.slice(0, 10) > fin) continue;
    demandesParId.set(d.demande_id, d);
    const lieu = d.logement_id || d.batiment_id;
    if (!demandesParLieu.has(lieu)) demandesParLieu.set(lieu, []);
    demandesParLieu.get(lieu).push(d);
  }
  const logements = new Map(tables.logements.map((l) => [l.logement_id, l]));

  const resultats = new Map();
  for (const e of tables.equipements) {
    if (e.dans_perimetre_prediction !== 'Oui') continue;
    const histo = (parEquipement.get(e.equipement_id) || []).sort((a, b) => a.date_intervention.localeCompare(b.date_intervention));
    const raisons = [];

    // ── Date de pose connue à la date de référence
    let pose = e.date_pose;
    if (pose > fin) pose = e.date_pose_precedente || e.date_pose;
    for (const it of histo) if (it.type_intervention === 'Remplacement' && it.date_intervention.slice(0, 10) > pose) pose = it.date_intervention.slice(0, 10);
    const age = Math.max(0, jours(pose, fin) / 365.25);
    const vieRef = Number(e.duree_vie_reference_ans);

    // ── Durée de vie retenue : visites manquées (jusqu'à −30 %) et grands logements
    const visites = histo.filter((it) => it.type_intervention === 'Entretien préventif');
    const absences = visites.filter((it) => it.resultat.startsWith('Logement absent')).length;
    const tauxAbsence = visites.length ? absences / visites.length : 0;
    const lgt = logements.get(e.logement_id);
    const surface = lgt ? Number(lgt.surface_habitable_m2) : 0;
    const grand = surface >= 85;
    const facteur = (1 - 0.3 * tauxAbsence) * (grand ? 0.93 : 1);
    const vieRetenue = vieRef * facteur;

    // ── 1. Usure
    const pFin = probaFinDeVie(age, vieRetenue, HORIZON_MOIS / 12);
    const ptsUsure = POIDS.usure * Math.min(1, pFin / 0.3);
    const ageTxt = age < 1 ? 'moins d\'un an' : pluriel(arrondi(age), 'an', 'ans');
    if (ptsUsure >= 2) {
      const ageDec = age < 1 ? ageTxt : `${String(Math.round(age * 10) / 10).replace('.', ',')} ans`;
      const texte = facteur < 0.99
        ? `En service depuis ${ageDec}, pour une durée de vie retenue de ${pluriel(arrondi(vieRetenue), 'an', 'ans')} (${vieRef} prévus)`
        : `En service depuis ${ageDec}, pour une durée de vie prévue de ${vieRef} ans`;
      raisons.push({ type: 'usure', points: ptsUsure, texte });
    }
    if (absences >= 2 && tauxAbsence >= 0.3) {
      raisons.push({ type: 'absences', points: 0, texte: `Locataire absent à ${absences} visites d'entretien sur ${visites.length} : durée de vie ramenée de ${vieRef} à ${arrondi(vieRetenue)} ans` });
    } else if (grand && ptsUsure >= 2) {
      raisons.push({ type: 'usage', points: 0, texte: `Grand logement (${lgt.typologie}, ${arrondi(surface)} m²) : usage plus intense, durée de vie retenue ${arrondi(vieRetenue)} ans` });
    }

    // ── 2. Remplacement demandé et non fait
    const depuisPose = histo.filter((it) => it.date_intervention.slice(0, 10) > pose);
    const demandeRempl = depuisPose.filter((it) => it.resultat === 'Remplacement nécessaire').pop();
    if (demandeRempl) {
      raisons.push({ type: 'remplacement', points: POIDS.remplacementDemande, texte: `Le ${dateLongue(demandeRempl.date_intervention)}, le technicien a conclu « remplacement nécessaire » ; aucun remplacement depuis` });
    }

    // ── 3. Dépannages récents
    const dep12 = depuisPose.filter((it) => it.type_intervention === 'Dépannage' && it.date_intervention.slice(0, 10) > il12);
    if (dep12.length) {
      const arrets = dep12.filter((it) => it.gravite === 'Arrêt total').length;
      const pts = POIDS.depannage12m * Math.min(3, dep12.length) + POIDS.arretTotal12m * Math.min(2, arrets);
      const dernier = dep12[dep12.length - 1];
      raisons.push({ type: 'depannages', points: pts, texte: `${pluriel(dep12.length, 'dépannage', 'dépannages')} en 12 mois${arrets ? ` dont ${pluriel(arrets, 'arrêt total', 'arrêts totaux')}` : ''} — le dernier le ${dateLongue(dernier.date_intervention)} (${dernier.symptome.toLowerCase()})` });
    }

    // ── 4. Ce que les techniciens ont écrit
    const signaux = depuisPose.filter((it) => COMMENTAIRES_USURE.has(it.commentaire_technicien) && it.date_intervention.slice(0, 10) > il18);
    if (signaux.length) {
      const s = signaux[signaux.length - 1];
      raisons.push({ type: 'signal', points: POIDS.signalTechnicien * Math.min(3, signaux.length), texte: `Noté par le technicien le ${dateLongue(s.date_intervention)} : « ${s.commentaire_technicien} »${signaux.length > 1 ? ` (et ${pluriel(signaux.length - 1, 'autre signal', 'autres signaux')} depuis 18 mois)` : ''}` });
    }

    // ── 5. Anomalies en visite d'entretien
    const anomalies = depuisPose.filter((it) => it.resultat === 'Anomalie constatée' && it.date_intervention.slice(0, 10) > il18);
    if (anomalies.length) {
      const a = anomalies[anomalies.length - 1];
      raisons.push({ type: 'anomalie', points: POIDS.anomalieVisite * Math.min(2, anomalies.length), texte: anomalies.length > 1 ? `${anomalies.length} anomalies constatées en visite d'entretien depuis 18 mois, la dernière le ${dateLongue(a.date_intervention)}` : `Anomalie constatée à la visite d'entretien du ${dateLongue(a.date_intervention)}` });
    }

    // ── 6. Ce que le locataire a signalé
    const ids = new Set();
    for (const it of depuisPose) if (it.demande_id_liee) ids.add(it.demande_id_liee);
    const motifs = MOTIFS_PAR_FAMILLE[e.famille] || [];
    const lieu = e.logement_id || e.batiment_id;
    for (const d of demandesParLieu.get(lieu) || []) if (motifs.includes(d.motif)) ids.add(d.demande_id);
    const dem12 = [...ids].map((id) => demandesParId.get(id)).filter((d) => d && d.date_creation.slice(0, 10) > il12 && d.date_creation.slice(0, 10) > pose);
    if (dem12.length) {
      const motsCles = ['tiède', 'toujours', 'revient', 'froid', 'encore'];
      const cite = dem12.map((d) => d.texte_demande).find((t) => motsCles.some((m) => t.toLowerCase().includes(m)));
      raisons.push({ type: 'locataire', points: POIDS.demandeLocataire * Math.min(3, dem12.length), texte: `${pluriel(dem12.length, 'demande', 'demandes')} du locataire en 12 mois${cite ? ` : « ${cite.length > 90 ? cite.slice(0, 88).trim() + '…' : cite} »` : ''}` });
    }

    const brut = raisons.reduce((s, r) => s + r.points, 0);
    const score = Math.max(0, Math.min(100, Math.round(brut)));
    const niveau = score >= SEUILS.prioritaire ? 'prioritaire' : score >= SEUILS.surveiller ? 'surveiller' : 'calme';
    raisons.sort((a, b) => b.points - a.points);
    resultats.set(e.equipement_id, {
      score, niveau,
      raisons: raisons.map((r) => ({ ...r, points: Math.round(r.points) })),
      mesures: { pose, age: Math.round(age * 10) / 10, vieRef, vieRetenue: Math.round(vieRetenue * 10) / 10, tauxAbsence: Math.round(tauxAbsence * 100), depannages12m: dep12.length, signaux18m: signaux.length },
    });
  }
  return resultats;
}

// Règle de comparaison du kit : l'âge rapporté à la durée de vie de référence, seul.
export function scoreAgeSeul(tables, dateReference) {
  const res = new Map();
  const rempl = new Map();
  for (const it of tables.interventions) {
    if (it.type_intervention === 'Remplacement' && it.date_intervention.slice(0, 10) <= dateReference) {
      const d = it.date_intervention.slice(0, 10);
      if (!rempl.has(it.equipement_id) || rempl.get(it.equipement_id) < d) rempl.set(it.equipement_id, d);
    }
  }
  for (const e of tables.equipements) {
    if (e.dans_perimetre_prediction !== 'Oui') continue;
    let pose = e.date_pose;
    if (pose > dateReference) pose = e.date_pose_precedente || e.date_pose;
    const r = rempl.get(e.equipement_id);
    if (r && r > pose) pose = r;
    res.set(e.equipement_id, jours(pose, dateReference) / 365.25 / Number(e.duree_vie_reference_ans));
  }
  return res;
}
