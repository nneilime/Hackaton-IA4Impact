// Risque de panne bloquante par équipement (module remplaçable).
//
// Panne bloquante : intervention « Dépannage » de gravité « Arrêt total ».
// Horizon : les 9 mois qui suivent la date de référence.
// Méthode : régression logistique écrite à la main (descente de gradient accélérée,
// déterministe, variables standardisées, pénalité L2, signes des coefficients
// contraints dans le sens des règles du métier), apprise sur des dates de référence
// passées empilées, chacune étiquetée par les pannes bloquantes des 9 mois suivants.

export const METHODE = {
  nom: 'Régression logistique sur les signaux de terrain',
  version: '1.0.0',
  resume:
    "Probabilité qu'un équipement ait une panne bloquante (dépannage en arrêt total) dans les 9 mois. "
    + "Modèle appris sur les années passées (situation au même jour de l'année, pannes des 9 mois suivants) "
    + "à partir de 10 indicateurs vérifiables : âge rapporté à la durée de vie prévue, dépannages et arrêts totaux "
    + 'sur 12 mois, dépannages des 3 derniers mois, remarques de fin de vie des techniciens, anomalies en visite '
    + "d'entretien, visites manquées, demandes des locataires, surface du logement, remplacement déjà commandé. "
    + 'Score = probabilité × 100, arrondi.',
};

/**
 * Seuils sur le score (0..100) : score ≥ visiter → « visiter », score ≥ surveiller → « surveiller ».
 * 30 : environ une chance sur trois de panne bloquante ; 6 : au-dessus du taux moyen du parc (≈ 6 %).
 */
export const SEUILS = { visiter: 30, surveiller: 6 };

const HORIZON_MOIS = 9;
const ITERATIONS = 400; // descente de gradient accélérée (Nesterov) : convergée bien avant
const PAS = 0.5;
const L2 = 0.001;
// Un fait n'est cité comme raison que s'il pèse assez : en logit et en part de la hausse du risque.
const CONTRIBUTION_MIN = 0.1;
const PART_MIN = 0.03;

const COMMENTAIRES_FIN_DE_VIE = new Set([
  'Usure avancée constatée, pièce à surveiller',
  "Traces de corrosion visibles sur l'appareil",
  'Nombreux redémarrages enregistrés',
  'Pièce de rechange difficile à obtenir',
  'Appareil vieillissant, remplacement à prévoir',
  'Réparation provisoire, fiabilité incertaine',
  'Panne irréparable, remplacement à commander',
  'Appareil hors service, réparation non rentable',
  'Défaillance majeure, appareil en fin de vie',
]);

// ---------------------------------------------------------------- dates

const MS_JOUR = 86400000;
const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
  'septembre', 'octobre', 'novembre', 'décembre'];

/** 'AAAA-MM-JJ…' → numéro de jour (entier). */
const jour = (s) => Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)) / MS_JOUR;
const dateIso = (j) => new Date(j * MS_JOUR).toISOString().slice(0, 10);

/** Ajoute n mois (n peut être négatif), en ramenant au dernier jour du mois si besoin. */
function ajouterMois(iso, n) {
  const a = +iso.slice(0, 4), m = +iso.slice(5, 7) - 1, j = +iso.slice(8, 10);
  const total = a * 12 + m + n;
  const an = Math.floor(total / 12), mois = total - an * 12;
  const dernier = new Date(Date.UTC(an, mois + 1, 0)).getUTCDate();
  return dateIso(Date.UTC(an, mois, Math.min(j, dernier)) / MS_JOUR);
}

/** '2025-11-12' → '12 novembre 2025' (« 1er » pour le premier du mois). */
function dateEnLettres(iso) {
  const j = +iso.slice(8, 10);
  return `${j === 1 ? '1er' : j} ${MOIS[+iso.slice(5, 7) - 1]} ${iso.slice(0, 4)}`;
}

const dateCourte = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;

function verifierDate(iso) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso) || dateIso(jour(iso)) !== iso) {
    throw new Error(`Date de référence invalide : ${iso} (attendu AAAA-MM-JJ)`);
  }
}

// ---------------------------------------------------------------- textes

const NBSP = ' ';
const pluriel = (n, un, plusieurs) => `${n}${NBSP}${n > 1 ? plusieurs : un}`;
const nombreFr = (x) => String(x).replace('.', ',');

/** Durée en jours → « 18 ans et 7 mois », « 2 ans », « 5 mois » (liaison « et » par défaut). */
function dureeEnLettres(jours, liaison = ' et ') {
  const mois = Math.floor(jours / 30.4375);
  const ans = Math.floor(mois / 12), reste = mois % 12;
  if (ans === 0) return `${reste}${NBSP}mois`;
  const partAns = pluriel(ans, 'an', 'ans');
  return reste ? `${partAns}${liaison}${reste}${NBSP}mois` : partAns;
}

const minusculeInitiale = (s) => s.charAt(0).toLocaleLowerCase('fr') + s.slice(1);
/** Objet d'une demande cité dans une raison : minuscule initiale, espace insécable avant : ; ! ? */
const objetCite = (s) => minusculeInitiale(s.trim()).replace(/[ \t]+([:;!?])/g, `${NBSP}$1`);

// ---------------------------------------------------------------- demandes des locataires

const MOTIF_GAZ = /panne équipement individuel gaz/i;
const MOTIF_ELEC = /panne équipement individuel électrique/i;
const MOTIF_FROID = /température basse/i;
const OBJET_EAU_CHAUDE = /eau ti[eè]de|eau chaude|cumulus|ballon/i;
const OBJET_CHAUFFAGE = /chauffage|radiateur|froid|température/i;

/** Indique si une demande de locataire concerne ce type d'équipement. */
const DEMANDES_PAR_FAMILLE = {
  chaudiere_gaz_individuelle: (m) => MOTIF_GAZ.test(m) || MOTIF_FROID.test(m),
  pompe_a_chaleur: (m) => MOTIF_ELEC.test(m) || MOTIF_FROID.test(m),
  ballon_ecs_electrique: (m, o) => MOTIF_ELEC.test(m) && OBJET_EAU_CHAUDE.test(o),
  ballon_thermodynamique: (m, o) => MOTIF_ELEC.test(m) && OBJET_EAU_CHAUDE.test(o),
  convecteurs_electriques: (m, o) => (MOTIF_ELEC.test(m) && OBJET_CHAUFFAGE.test(o)) || MOTIF_FROID.test(m),
  panneaux_rayonnants: (m, o) => (MOTIF_ELEC.test(m) && OBJET_CHAUFFAGE.test(o)) || MOTIF_FROID.test(m),
  // Équipements de bâtiment : demandes de tous les locataires du bâtiment.
  chaufferie_collective: (m) => /chauffage collectif/i.test(m) || MOTIF_FROID.test(m),
  production_ecs_solaire: (m, o) => OBJET_EAU_CHAUDE.test(o),
  caisson_vmc: (m) => /vmc|ventilation/i.test(m),
  ascenseur: (m) => /ascenseur/i.test(m),
};

// ---------------------------------------------------------------- préparation des données

const CACHE = new WeakMap();

/** Index des données (calculés une fois par jeu de données). */
function preparer(donnees) {
  const cle = `${donnees.equipements.length}/${donnees.interventions.length}/${donnees.demandes.length}`;
  const deja = CACHE.get(donnees);
  if (deja && deja.cle === cle) return deja;

  const familles = new Map(donnees.familles.map((f) => [f.famille, f]));
  const logements = new Map(donnees.logements.map((l) => [l.logement_id, l]));
  const perimetre = donnees.equipements
    .filter((e) => e.dans_perimetre_prediction === 'Oui')
    .sort((a, b) => (a.equipement_id < b.equipement_id ? -1 : 1));

  const infos = new Map();
  for (const e of perimetre) {
    const lgt = e.logement_id ? logements.get(e.logement_id) : null;
    const surface = lgt ? parseFloat(lgt.surface_habitable_m2) : NaN;
    infos.set(e.equipement_id, {
      e,
      dureeVie: parseFloat(e.duree_vie_reference_ans) || parseFloat(familles.get(e.famille)?.duree_vie_reference_ans) || 20,
      surface: Number.isFinite(surface) ? surface : NaN,
      typologie: lgt?.typologie ?? '',
      concerne: DEMANDES_PAR_FAMILLE[e.famille] ?? (() => false),
      interventions: [],
      remplacements: [], // jours des remplacements
      arrets: [], // jours des pannes bloquantes
    });
  }

  // Interventions des équipements du périmètre ; visites d'entretien par logement.
  const triees = donnees.interventions
    .filter((i) => /^\d{4}-\d{2}-\d{2}/.test(i.date_intervention ?? ''))
    .sort((a, b) => (a.date_intervention < b.date_intervention ? -1
      : a.date_intervention > b.date_intervention ? 1
        : a.intervention_id < b.intervention_id ? -1 : 1));
  const visitesParJour = new Map(); // logement → Map(jour → manquée ?)
  let premiereIntervention = null;
  for (const i of triees) {
    const date = i.date_intervention.slice(0, 10);
    const j = jour(date);
    premiereIntervention ??= date;
    if (i.type_intervention === 'Entretien préventif' && i.logement_id) {
      let v = visitesParJour.get(i.logement_id);
      if (!v) visitesParJour.set(i.logement_id, (v = new Map()));
      const absent = i.resultat.startsWith('Logement absent');
      v.set(j, (v.get(j) ?? true) && absent); // jour manqué si aucune visite du jour n'a pu se faire
    }
    const info = infos.get(i.equipement_id);
    if (!info) continue;
    const it = {
      j, date, type: i.type_intervention, gravite: i.gravite, resultat: i.resultat,
      commentaire: i.commentaire_technicien,
    };
    info.interventions.push(it);
    if (it.type === 'Remplacement') info.remplacements.push(j);
    if (it.type === 'Dépannage' && it.gravite === 'Arrêt total') info.arrets.push(j);
  }
  const visites = new Map();
  for (const [lgt, v] of visitesParJour) {
    visites.set(lgt, [...v].map(([j, manquee]) => ({ j, manquee })).sort((a, b) => a.j - b.j));
  }

  // Demandes des locataires, par logement et par bâtiment.
  const parLogement = new Map(), parBatiment = new Map();
  let premiereDemande = null;
  const demandes = donnees.demandes
    .filter((d) => /^\d{4}-\d{2}-\d{2}/.test(d.date_creation ?? ''))
    .sort((a, b) => (a.date_creation < b.date_creation ? -1 : a.date_creation > b.date_creation ? 1
      : a.demande_id < b.demande_id ? -1 : 1));
  for (const d of demandes) {
    const date = d.date_creation.slice(0, 10);
    premiereDemande ??= date;
    const fiche = { j: jour(date), date, motif: d.motif ?? '', objet: d.objet ?? '' };
    for (const [index, cleIndex] of [[parLogement, d.logement_id], [parBatiment, d.batiment_id]]) {
      if (!cleIndex) continue;
      if (!index.has(cleIndex)) index.set(cleIndex, []);
      index.get(cleIndex).push(fiche);
    }
  }

  const prep = {
    cle, perimetre, infos, visites, parLogement, parBatiment,
    premiereIntervention, premiereDemande,
  };
  CACHE.set(donnees, prep);
  return prep;
}

/** Pose en vigueur à la date R (jour) : dernier remplacement ≤ R, sinon date_pose, sinon la pose précédente. */
function poseEnVigueur(info, R) {
  let pose = null;
  for (const j of info.remplacements) if (j <= R) pose = j;
  if (pose !== null) return pose;
  const actuelle = info.e.date_pose ? jour(info.e.date_pose) : null;
  if (actuelle !== null && actuelle <= R) return actuelle;
  const precedente = info.e.date_pose_precedente ? jour(info.e.date_pose_precedente) : null;
  if (precedente !== null && precedente <= R) return precedente;
  // Pose d'origine inconnue (plusieurs remplacements après R) : on suppose l'appareil en fin de durée de vie.
  return R - Math.round(info.dureeVie * 365.25);
}

const aUnePanneBloquante = (info, debut, fin) => info.arrets.some((j) => j > debut && j <= fin);

// ---------------------------------------------------------------- indicateurs

/**
 * Variables du modèle. `transformer` donne la valeur vue par la régression ;
 * `signe` contraint le coefficient (+1 : ne peut qu'augmenter le risque, -1 : que le baisser).
 */
const VARIABLES = [
  { code: 'age', groupe: 'age', signe: 1, transformer: (m) => Math.log(Math.max(m.rapportAge, 0.05)) },
  { code: 'depannages12m', groupe: 'depannages', signe: 1, transformer: (m) => Math.log1p(m.depannages12m) },
  { code: 'arrets12m', groupe: 'depannages', signe: 1, transformer: (m) => Math.log1p(m.arrets12m) },
  { code: 'depannages3m', groupe: 'recents', signe: 1, transformer: (m) => Math.log1p(m.depannages3m) },
  { code: 'commentaires18m', groupe: 'commentaires', signe: 1, transformer: (m) => Math.log1p(m.commentaires18m) },
  { code: 'anomalies18m', groupe: 'anomalies', signe: 1, transformer: (m) => Math.log1p(m.anomalies18m) },
  { code: 'visitesManquees', groupe: 'absences', signe: 1, transformer: (m) => m.partVisitesManquees },
  { code: 'demandes12m', groupe: 'demandes', signe: 1, transformer: (m) => Math.log1p(m.demandes12m) },
  { code: 'surface', groupe: 'surface', signe: 1, transformer: (m) => m.surface }, // NaN hors logement
  // Remplacement déjà commandé (« Remplacement nécessaire » non suivi d'une pose) : l'appareil va être changé.
  { code: 'remplacementCommande', groupe: null, signe: -1, transformer: (m) => (m.remplacementCommande ? 1 : 0) },
];

/** Mesure les faits d'un équipement à la date de référence (seules les données ≤ référence comptent). */
function mesurer(prep, info, refIso) {
  const R = jour(refIso);
  const pose = poseEnVigueur(info, R);
  const il12 = jour(ajouterMois(refIso, -12));
  const il3 = jour(ajouterMois(refIso, -3));
  const il18 = jour(ajouterMois(refIso, -18));

  const m = {
    pose, rapportAge: Math.max(0, R - pose) / 365.25 / info.dureeVie,
    depannages12m: 0, arrets12m: 0, depannages3m: 0, commentaires18m: 0, anomalies18m: 0,
    dernierDepannage: null, dernierCommentaire: null, dernierCommentaire18m: null,
    derniereAnomalie: null, remplacementCommande: null,
  };

  // Un remplacement remet l'appareil à neuf : seuls les faits postérieurs à la pose comptent.
  for (const it of info.interventions) {
    if (it.j > R) break;
    if (it.j <= pose) continue;
    const finDeVie = COMMENTAIRES_FIN_DE_VIE.has(it.commentaire);
    if (finDeVie) m.dernierCommentaire = it;
    if (it.type === 'Dépannage') {
      m.dernierDepannage = it;
      if (it.j > il12) {
        m.depannages12m++;
        if (it.gravite === 'Arrêt total') m.arrets12m++;
      }
      if (it.j > il3) m.depannages3m++;
      if (it.resultat === 'Remplacement nécessaire') m.remplacementCommande = it;
      // Remarques de fin de vie faites en dépannage (celles des visites sont comptées en anomalies).
      if (finDeVie && it.j > il18) { m.commentaires18m++; m.dernierCommentaire18m = it; }
    }
    if (it.type === 'Entretien préventif' && it.resultat === 'Anomalie constatée' && it.j > il18) {
      m.anomalies18m++;
      m.derniereAnomalie = it;
    }
  }

  // Visites d'entretien : habitude du logement, sur tout l'historique connu.
  if (info.e.logement_id) {
    const visites = prep.visites.get(info.e.logement_id) ?? [];
    m.visitesPrevues = 0; m.visitesManquees = 0;
    for (const v of visites) {
      if (v.j > R) break;
      m.visitesPrevues++;
      if (v.manquee) m.visitesManquees++;
    }
  } else {
    m.visitesPrevues = info.interventions.filter((it) => it.j <= R && it.type === 'Entretien préventif').length;
    m.visitesManquees = 0;
  }
  m.partVisitesManquees = m.visitesPrevues ? m.visitesManquees / m.visitesPrevues : 0;

  // Demandes des locataires liées à ce type d'équipement, depuis la pose et sur 12 mois.
  const source = info.e.logement_id ? prep.parLogement.get(info.e.logement_id) : prep.parBatiment.get(info.e.batiment_id);
  m.demandes = [];
  for (const d of source ?? []) {
    if (d.j > R) break;
    if (d.j > Math.max(il12, pose) && info.concerne(d.motif, d.objet)) m.demandes.push(d);
  }
  m.demandes12m = m.demandes.length;

  m.surface = info.surface;
  return m;
}

const vecteur = (m) => VARIABLES.map((v) => v.transformer(m));

// ---------------------------------------------------------------- régression logistique

const sigmoide = (s) => (s >= 0 ? 1 / (1 + Math.exp(-s)) : Math.exp(s) / (1 + Math.exp(s)));

/** Apprend la régression sur des lignes X (tableaux de nombres, NaN = inconnu) et des étiquettes 0/1. */
function ajuster(X, y) {
  const n = X.length, p = VARIABLES.length;
  if (n === 0) throw new Error("Aucune donnée d'apprentissage");

  // Standardisation ; une valeur inconnue est remplacée par la moyenne (valeur centrée nulle).
  const moyennes = new Float64Array(p), ecarts = new Float64Array(p);
  for (let k = 0; k < p; k++) {
    let s = 0, s2 = 0, c = 0;
    for (const x of X) if (Number.isFinite(x[k])) { s += x[k]; s2 += x[k] * x[k]; c++; }
    moyennes[k] = c ? s / c : 0;
    const variance = c ? s2 / c - moyennes[k] ** 2 : 0;
    ecarts[k] = variance > 1e-12 ? Math.sqrt(variance) : 1;
  }
  const Z = new Float64Array(n * p);
  X.forEach((x, i) => {
    for (let k = 0; k < p; k++) Z[i * p + k] = Number.isFinite(x[k]) ? (x[k] - moyennes[k]) / ecarts[k] : 0;
  });

  // Descente de gradient accélérée (Nesterov), projetée sur les signes autorisés.
  const taux = y.reduce((s, v) => s + v, 0) / n;
  let w = new Float64Array(p + 1); // w[p] = constante
  w[p] = Math.log(Math.max(taux, 1e-6) / Math.max(1 - taux, 1e-6));
  let precedent = Float64Array.from(w);
  const g = new Float64Array(p + 1), v = new Float64Array(p + 1);
  for (let t = 1; t <= ITERATIONS; t++) {
    const elan = (t - 1) / (t + 2);
    for (let k = 0; k <= p; k++) v[k] = w[k] + elan * (w[k] - precedent[k]);
    g.fill(0);
    for (let i = 0; i < n; i++) {
      let s = v[p];
      const o = i * p;
      for (let k = 0; k < p; k++) s += v[k] * Z[o + k];
      const r = sigmoide(s) - y[i];
      for (let k = 0; k < p; k++) g[k] += r * Z[o + k];
      g[p] += r;
    }
    precedent = w;
    w = new Float64Array(p + 1);
    for (let k = 0; k <= p; k++) {
      const penalite = k < p ? L2 * v[k] : 0;
      let wk = v[k] - PAS * (g[k] / n + penalite);
      if (k < p && VARIABLES[k].signe > 0 && wk < 0) wk = 0;
      if (k < p && VARIABLES[k].signe < 0 && wk > 0) wk = 0;
      w[k] = wk;
    }
  }
  return { moyennes, ecarts, coefficients: w.subarray(0, p), constante: w[p], n, taux };
}

/** Contributions (centrées sur l'équipement moyen de l'apprentissage) et probabilité. */
function appliquer(modele, x) {
  const contributions = new Float64Array(VARIABLES.length);
  let s = modele.constante;
  for (let k = 0; k < VARIABLES.length; k++) {
    const z = Number.isFinite(x[k]) ? (x[k] - modele.moyennes[k]) / modele.ecarts[k] : 0;
    contributions[k] = modele.coefficients[k] * z;
    s += contributions[k];
  }
  return { probabilite: sigmoide(s), contributions };
}

/** Dates de référence d'apprentissage : même jour de l'année, étiquette connue à la date R. */
function referencesApprentissage(prep, refIso) {
  const refs = [];
  for (let k = 1; k < 100; k++) {
    const ref = ajouterMois(refIso, -12 * k);
    const historiqueComplet = ajouterMois(ref, -12) >= prep.premiereDemande
      && ajouterMois(ref, -18) >= prep.premiereIntervention;
    if (!historiqueComplet) break;
    if (ajouterMois(ref, HORIZON_MOIS) <= refIso) refs.push(ref);
  }
  return refs.reverse();
}

function apprendre(prep, refs) {
  const X = [], y = [];
  for (const ref of refs) {
    const debut = jour(ref), fin = jour(ajouterMois(ref, HORIZON_MOIS));
    for (const info of prep.infos.values()) {
      X.push(vecteur(mesurer(prep, info, ref)));
      y.push(aUnePanneBloquante(info, debut, fin) ? 1 : 0);
    }
  }
  return { ...ajuster(X, y), references: refs };
}

// ---------------------------------------------------------------- raisons

// Ligne courte (file d'attente) : même fait que le texte complet, sans phrase.
const COURT_MAX = 48;
const MOIS_ABREGES = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];

/** '2025-12-05' → '5 déc. 2025'. */
function dateAbregee(iso) {
  const j = +iso.slice(8, 10);
  return `${j === 1 ? '1er' : j} ${MOIS_ABREGES[+iso.slice(5, 7) - 1]} ${iso.slice(0, 4)}`;
}

/** Coupe une ligne trop longue au dernier mot entier et ajoute « … ». */
function abreger(s, max = COURT_MAX) {
  if (s.length <= max) return s;
  const coupe = s.slice(0, max - 1);
  const espace = Math.max(coupe.lastIndexOf(' '), coupe.lastIndexOf(NBSP));
  return `${(espace > 0 ? coupe.slice(0, espace) : coupe).replace(/[\s,;:·«]+$/u, '')}…`;
}

/** « tête : a, b, c » en gardant autant d'éléments que la ligne courte le permet. */
function listeCourte(tete, elements) {
  if (elements.length === 0) return abreger(tete);
  for (let k = elements.length; k >= 1; k--) {
    const ligne = `${tete}${NBSP}: ${elements.slice(0, k).join(', ')}${k < elements.length ? ', …' : ''}`;
    if (ligne.length <= COURT_MAX) return ligne;
  }
  return abreger(`${tete}${NBSP}: ${elements[0]}`);
}

const entreGuillemets = (s) => `«${NBSP}${s}${NBSP}»`;

/** Remarque du technicien citée en ligne courte : première proposition (avant la virgule) et date. */
function remarqueCourte(it) {
  const date = dateAbregee(it.date);
  const place = COURT_MAX - date.length - ' · '.length - 4; // 4 = guillemets et leurs espaces
  return `${entreGuillemets(abreger(it.commentaire.split(',')[0].trim(), place))} · ${date}`;
}

/** Pour chaque groupe d'indicateurs : phrase complète (fiche) et ligne courte (file). */
const TEXTES = {
  age: (m, info) => {
    const jours = jour(m.refIso) - m.pose;
    const duree = dureeEnLettres(jours, ' ');
    return {
      texte: `${dureeEnLettres(jours)} de service pour ${pluriel(info.dureeVie, 'an', 'ans')} prévus`,
      court: jours < 365.25
        ? `${duree} pour ${pluriel(info.dureeVie, 'an', 'ans')} prévus`
        : `${duree} pour ${info.dureeVie} prévus`,
    };
  },
  depannages: (m) => {
    const n = m.depannages12m, k = m.arrets12m;
    const base = `${pluriel(n, 'dépannage', 'dépannages')} en 12${NBSP}mois`;
    let texte = base;
    if (k === n && k > 0) texte = n === 1 ? `${base}, en arrêt total` : `${base}, tous en arrêt total`;
    else if (k > 0) texte = `${base}, dont ${pluriel(k, 'arrêt total', 'arrêts totaux')}`;
    return { texte, court: texte };
  },
  recents: (m) => {
    const n = m.depannages3m, d = m.dernierDepannage.date;
    return n === 1
      ? { texte: `1${NBSP}dépannage ces 3 derniers mois, le ${dateEnLettres(d)}`, court: `1${NBSP}dépannage en 3${NBSP}mois · ${dateAbregee(d)}` }
      : {
        texte: `${n}${NBSP}dépannages ces 3 derniers mois, le dernier le ${dateEnLettres(d)}`,
        court: `${n}${NBSP}dépannages en 3${NBSP}mois · dernier ${dateAbregee(d)}`,
      };
  },
  commentaires: (m) => {
    const c = m.dernierCommentaire18m, autres = m.commentaires18m - 1;
    const suite = autres > 0
      ? ` (et ${autres}${NBSP}autre${autres > 1 ? 's' : ''} signe${autres > 1 ? 's' : ''} en 18${NBSP}mois)`
      : '';
    return {
      texte: `Noté ${entreGuillemets(c.commentaire)} le ${dateEnLettres(c.date)}${suite}`,
      court: remarqueCourte(c),
    };
  },
  anomalies: (m) => {
    const a = m.derniereAnomalie;
    const note = a.commentaire ? `${NBSP}: ${entreGuillemets(a.commentaire)}` : '';
    return m.anomalies18m === 1
      ? {
        texte: `Anomalie constatée à la visite d'entretien du ${dateEnLettres(a.date)}${note}`,
        court: `Anomalie en visite · ${dateAbregee(a.date)}`,
      }
      : {
        texte: `${m.anomalies18m}${NBSP}anomalies constatées aux visites d'entretien en 18${NBSP}mois, la dernière le ${dateEnLettres(a.date)}${note}`,
        court: `${m.anomalies18m}${NBSP}anomalies en visite · dernière ${dateAbregee(a.date)}`,
      };
  },
  absences: (m) => {
    const k = m.visitesManquees, s = k > 1 ? 's' : '';
    return {
      texte: `Logement absent à ${k}${NBSP}visite${s} d'entretien sur ${m.visitesPrevues}`,
      court: `${k}${NBSP}visite${s} manquée${s} sur ${m.visitesPrevues}`,
    };
  },
  demandes: (m, info) => {
    const objets = [...new Set(m.demandes.map((d) => objetCite(d.objet)).filter(Boolean))];
    const n = m.demandes12m;
    const [qui, quiCourt] = info.e.logement_id
      ? [`${pluriel(n, 'demande', 'demandes')} du locataire`, pluriel(n, 'demande', 'demandes')]
      : [`${pluriel(n, 'signalement', 'signalements')} des locataires du bâtiment`, pluriel(n, 'signalement', 'signalements')];
    return {
      texte: `${qui} en 12${NBSP}mois${objets.length ? `${NBSP}: ${objets.join(', ')}` : ''}`,
      court: listeCourte(`${quiCourt} en 12${NBSP}mois`, objets),
    };
  },
  surface: (m, info) => {
    const texte = `Grand logement${NBSP}: ${nombreFr(m.surface)}${NBSP}m²${info.typologie ? ` (${info.typologie})` : ''}`;
    return { texte, court: texte };
  },
};

function construireRaisons(modele, contributions, m, info) {
  const parGroupe = new Map();
  VARIABLES.forEach((v, k) => {
    if (!v.groupe || contributions[k] <= 0) return;
    parGroupe.set(v.groupe, (parGroupe.get(v.groupe) ?? 0) + contributions[k]);
  });
  const hausse = [...parGroupe.values()].reduce((s, c) => s + c, 0);
  const retenues = [...parGroupe].filter(([, c]) => c >= CONTRIBUTION_MIN && c >= PART_MIN * hausse);
  const total = retenues.reduce((s, [, c]) => s + c, 0);
  return retenues
    .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))
    .map(([code, c]) => {
      const { texte, court } = TEXTES[code](m, info);
      return { code, texte, court: abreger(court), poids: Math.round((c / total) * 1000) / 1000 };
    });
}

// ---------------------------------------------------------------- interface

const niveauDuScore = (score) => (score >= SEUILS.visiter ? 'visiter' : score >= SEUILS.surveiller ? 'surveiller' : 'calme');

/**
 * Risque de panne bloquante dans les 9 mois pour chaque équipement du périmètre.
 * Renvoie une Map equipement_id → { score, probabilite, niveau, raisons, faits },
 * rangée par probabilité décroissante. score = probabilité × 100 arrondi (0..100).
 */
export function evaluerRisques(donnees, { dateReference = '2025-12-31' } = {}) {
  verifierDate(dateReference);
  const prep = preparer(donnees);
  const refs = referencesApprentissage(prep, dateReference);
  if (refs.length === 0) {
    throw new Error(`Pas assez d'historique avant le ${dateCourte(dateReference)} pour apprendre le modèle`);
  }
  const modele = apprendre(prep, refs);

  const lignes = [];
  for (const info of prep.infos.values()) {
    const m = mesurer(prep, info, dateReference);
    m.refIso = dateReference;
    const { probabilite, contributions } = appliquer(modele, vecteur(m));
    const score = Math.round(probabilite * 100);
    lignes.push([info.e.equipement_id, {
      score,
      probabilite,
      niveau: niveauDuScore(score),
      raisons: construireRaisons(modele, contributions, m, info),
      faits: {
        datePose: dateIso(m.pose),
        ageAns: Math.round(m.rapportAge * info.dureeVie * 10) / 10,
        dureeVieAns: info.dureeVie,
        depannages12m: m.depannages12m,
        arrets12m: m.arrets12m,
        dernierDepannage: m.dernierDepannage?.date ?? null,
        visitesManquees: m.visitesManquees,
        visitesPrevues: m.visitesPrevues,
        demandes12m: m.demandes12m,
        dernierCommentaire: m.dernierCommentaire?.commentaire ?? null,
        dateDernierCommentaire: m.dernierCommentaire?.date ?? null,
        remplacementCommande: m.remplacementCommande?.date ?? null, // date du « Remplacement nécessaire » en attente
      },
    }]);
  }
  lignes.sort((a, b) => b[1].probabilite - a[1].probabilite || (a[0] < b[0] ? -1 : 1));
  return new Map(lignes);
}

/** Méthode de comparaison : rapport âge / durée de vie de référence à la date donnée. */
export function scoreAgeSeul(donnees, dateReference = '2025-12-31') {
  verifierDate(dateReference);
  const prep = preparer(donnees);
  const R = jour(dateReference);
  const resultat = new Map();
  for (const [id, info] of prep.infos) {
    resultat.set(id, Math.max(0, R - poseEnVigueur(info, R)) / 365.25 / info.dureeVie);
  }
  return resultat;
}

/** AUC par la statistique de Mann-Whitney (rangs moyens en cas d'égalité). */
function auc(scores, etiquettes) {
  const ordre = scores.map((s, i) => [s, etiquettes[i]]).sort((a, b) => a[0] - b[0]);
  let sommeRangsPositifs = 0, positifs = 0;
  for (let i = 0; i < ordre.length;) {
    let j = i;
    while (j + 1 < ordre.length && ordre[j + 1][0] === ordre[i][0]) j++;
    const rangMoyen = (i + j) / 2 + 1;
    for (let k = i; k <= j; k++) if (ordre[k][1]) { sommeRangsPositifs += rangMoyen; positifs++; }
    i = j + 1;
  }
  const negatifs = ordre.length - positifs;
  if (!positifs || !negatifs) return null;
  return (sommeRangsPositifs - (positifs * (positifs + 1)) / 2) / (positifs * negatifs);
}

/** Nombre de pannes réelles parmi les n premiers d'un classement (égalités départagées par identifiant). */
function captures(classement, pannes, n) {
  return classement.slice(0, n).filter((id) => pannes.has(id)).length;
}

/**
 * Validation dans le passé : modèle appris uniquement avec les données connues au 31/12/2024
 * (références 2020 à 2023), testé sur les pannes bloquantes du 01/01/2025 au 30/09/2025.
 */
export function validerDansLePasse(donnees) {
  const dateTest = '2024-12-31';
  const fin = ajouterMois(dateTest, HORIZON_MOIS);
  const prep = preparer(donnees);
  const risques = evaluerRisques(donnees, { dateReference: dateTest });
  const ages = scoreAgeSeul(donnees, dateTest);

  const pannes = new Set();
  for (const [id, info] of prep.infos) if (aUnePanneBloquante(info, jour(dateTest), jour(fin))) pannes.add(id);

  const ids = [...prep.infos.keys()];
  const etiquettes = ids.map((id) => pannes.has(id));
  const classementMethode = [...risques.keys()]; // déjà rangé par probabilité décroissante
  const classementAge = [...ids].sort((a, b) => ages.get(b) - ages.get(a) || (a < b ? -1 : 1));
  const nVisiter = [...risques.values()].filter((r) => r.niveau === 'visiter').length;

  return {
    dateTest,
    horizon: `${dateCourte(dateIso(jour(dateTest) + 1))} → ${dateCourte(fin)}`,
    references: referencesApprentissage(prep, dateTest),
    equipements: ids.length,
    pannes: pannes.size,
    auc: {
      methode: auc(ids.map((id) => risques.get(id).probabilite), etiquettes),
      ageSeul: auc(ids.map((id) => ages.get(id)), etiquettes),
    },
    top: [50, 100, nVisiter].map((n) => ({
      n,
      methode: captures(classementMethode, pannes, n),
      ageSeul: captures(classementAge, pannes, n),
    })),
  };
}
