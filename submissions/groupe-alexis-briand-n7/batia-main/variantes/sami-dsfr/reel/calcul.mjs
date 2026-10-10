// BâtIA · données réelles — le calcul de risque sur données publiques.
// Module sans dépendance, pour le navigateur et pour Node. Forme fixée par recherche/reel-contrat.md :
//   evaluer(fiche) → { niveau, libelle, points, raisons, manque }
//
// Ce calcul estime une EXPOSITION au risque de panne à partir de faits publics (âge des générateurs lu dans les DPE,
// sol, eau, réseaux). Aucune donnée publique de pannes réelles n'existe : il n'a jamais été vérifié sur des pannes,
// et aucune mesure de performance n'en est tirée. Les points servent à trier et à expliquer, jamais à être affichés.
// Aucun chiffre du kit fictif (moteur/BAREME.md) n'est repris ici : seules sa forme (points et raisons) l'est.

export const ANNEE = 2026; // année de référence des âges (démonstration du 10 octobre 2026)
export const AUJOURDHUI = '2026-10-10';

// Durées de vie de référence : sources publiques citées, lues le 9 octobre 2026 (recherche/donnees-publiques/fiches/10).
export const DUREES = {
  chaudiere: { ans: 15, source: 'Grille de vétusté de Lyon Métropole Habitat (chaudière, 15 ans)' },
  chaudiere_collective: { ans: 22, source: 'Durée conventionnelle CEE des générateurs collectifs (fiches BAR-TH-165 et BAR-TH-179, 22 ans)' },
  pac: { ans: 17, source: 'Durée conventionnelle CEE des pompes à chaleur (fiches BAR-TH-171 et BAR-TH-129, 17 ans)' },
  convecteur: { ans: 12, source: 'Grille de vétusté de Lyon Métropole Habitat (convecteurs électriques, 12 ans)' },
  ballon: { ans: 10, source: 'Grille de vétusté de Lyon Métropole Habitat (ballon d’eau chaude, 10 ans)' },
  thermodynamique: { ans: 17, source: 'Durée conventionnelle CEE du chauffe-eau thermodynamique (fiche BAR-TH-148, 17 ans)' },
  vmc: { ans: 17, source: 'Durée conventionnelle CEE des ventilations (fiches BAR-TH-125, 127 et 155, 17 ans)' },
  reseau_chaleur: { ans: 30, source: 'Durée conventionnelle CEE du raccordement à un réseau de chaleur (fiche BAR-TH-137, 30 ans)' },
};

// L'étiquette d'un immeuble et l'arrêt de la 2G se disent d'une seule façon partout : regles.mjs.
import { etiquetteImmeuble, phrase2G } from './regles.mjs';

export const NIVEAUX = [
  { niveau: 'urgence', libelle: 'Urgent', min: 70 },
  { niveau: 'alerte', libelle: 'Alerte', min: 48 },
  { niveau: 'vigilance', libelle: 'Vigilance', min: 30 },
  { niveau: 'surveiller', libelle: 'À surveiller', min: 15 },
  { niveau: 'calme', libelle: 'Calme', min: -Infinity },
];
export const LIBELLES = Object.fromEntries(NIVEAUX.map((n) => [n.niveau, n.libelle]));

const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
const dateCourte = (iso) => { const [a, m, j] = String(iso).slice(0, 10).split('-'); return `${+j === 1 ? '1er' : +j} ${MOIS[+m - 1]} ${a}`; };
const sansAccent = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

/** Lit une période dans un libellé de DPE : « … 2001-2015 » → [2001, 2015] ; « après 2015 » → [2016, null] ; « avant 1991 » → [null, 1990]. */
export function periode(libelle) {
  const s = sansAccent(libelle);
  let m = s.match(/(\d{4})\s*[-–]\s*(\d{4})/) || s.match(/(?:entre|de)\s+(\d{4})\s+(?:et|a)\s+(\d{4})/);
  if (m) return [+m[1], +m[2]];
  if ((m = s.match(/apres\s+(\d{4})/))) return [+m[1] + 1, null];
  if ((m = s.match(/avant\s+(\d{4})/))) return [null, +m[1] - 1];
  return null;
}

/** Famille d'un générateur, d'après son libellé (DPE ou BDNB). */
export function famille(libelle, collectif = false) {
  const s = sansAccent(libelle);
  if (!s) return null;
  if (/reseau de chaleur|reseau urbain/.test(s)) return 'reseau_chaleur';
  if (/thermodynamique/.test(s)) return 'thermodynamique';
  if (/pac|pompe a chaleur/.test(s)) return 'pac';
  if (/chaudiere/.test(s)) return collectif ? 'chaudiere_collective' : 'chaudiere';
  if (/ballon|cumulus|chauffe-eau|accumulateur/.test(s)) return 'ballon';
  if (/convecteur|panneau rayonnant|radiateur electrique|emetteur|electrique/.test(s)) return 'convecteur';
  return null;
}

// Mots courts du métier pour un générateur : « chaudières gaz standard », « ballons électriques »…
function nommer(libelle, collectif) {
  const s = sansAccent(libelle);
  const pluriel = !collectif;
  let n;
  if (/chaudiere/.test(s)) {
    const energie = /gaz/.test(s) ? ' gaz' : /fioul/.test(s) ? ' fioul' : /bois|biomasse/.test(s) ? ' bois' : '';
    const type = /condensation/.test(s) ? ' à condensation' : /basse temperature/.test(s) ? ' basse température' : /standard|classique/.test(s) ? ' standard' : '';
    n = `${pluriel ? 'Chaudières' : 'Chaudière collective'}${energie}${type}`;
  } else if (/thermodynamique/.test(s)) n = pluriel ? 'Chauffe-eau thermodynamiques' : 'Chauffe-eau thermodynamique collectif';
  else if (/pac|pompe a chaleur/.test(s)) n = pluriel ? 'Pompes à chaleur' : 'Pompe à chaleur collective';
  else if (/ballon|cumulus|chauffe-eau/.test(s)) n = pluriel ? 'Ballons électriques' : 'Ballon collectif';
  else if (/convecteur|electrique/.test(s)) n = 'Convecteurs électriques';
  else if (/reseau de chaleur|reseau urbain/.test(s)) n = 'Réseau de chaleur';
  else n = String(libelle).split(/\s+\d{4}|\s+(avant|apres|après)\s/)[0];
  return n;
}

// Âge d'un équipement rapporté à sa durée de vie de référence : les points montent quand même le plus récent
// de la période a pu dépasser sa durée, et moins quand seuls les plus anciens l'ont dépassée.
function pointsAge(per, duree, poids) {
  if (!per) return null;
  const [a, b] = per;
  const ageMin = b ? ANNEE - b : 0;           // le plus jeune possible
  const ageMax = a ? ANNEE - a : ageMin + 25; // le plus vieux possible (borne ouverte « avant … » : au moins 25 ans de plus)
  // « après 1982 » : l'appareil peut avoir un an comme quarante ; seul le doute compte, et peu
  if (!b) return ageMax >= duree ? { points: Math.round(poids * 0.3), ouvert: true, ageMin, ageMax } : { points: 0, ageMin, ageMax };
  if (ageMin >= duree) return { points: poids, tous: true, ageMin, ageMax };
  if (ageMax >= duree) {
    const part = (ageMax - duree) / Math.max(1, ageMax - ageMin); // part de la période au-delà de la durée
    return { points: Math.round(poids * (0.45 + 0.35 * part)), tous: false, ageMin, ageMax };
  }
  if (ageMax >= duree * 0.75) return { points: Math.round(poids * 0.22), proche: true, ageMin, ageMax };
  return { points: 0, ageMin, ageMax };
}

const pose = ([a, b]) => (a && b ? `${a}-${b}` : b ? `d’avant ${b + 1}` : `posée après ${a - 1}`);
function age(r, ans) {
  if (r.tous) return `au moins ${r.ageMin} ans pour ${ans} prévus`;
  if (r.ouvert) return `peut-être plus de ${ans} ans`;
  if (r.proche) return `bientôt ${ans} ans`;
  return `jusqu’à ${r.ageMax} ans pour ${ans} prévus`;
}

function raisonEquipement(eq, { role, collectif, poids, durete, liste, cle }) {
  if (!eq || !eq.generateur) return null;
  const per = eq.periode_generateur || periode(eq.generateur);
  const fam = famille(eq.generateur, collectif);
  const ref = DUREES[fam];
  if (!per || !ref) return null;
  const r = pointsAge(per, ref.ans, poids);
  if (!r || r.points <= 0) return null;
  const nom = nommer(eq.generateur, collectif);
  const texte = `${nom} ${pose(per)} : ${age(r, ref.ans)}`;
  // l'eau dure entartre ballons et échangeurs : l'âge pèse plus lourd
  let points = r.points;
  if (durete != null && durete >= 25 && (role === 'eau_chaude' || fam === 'chaudiere')) points = Math.round(points * 1.15);
  // les DPE d'un même immeuble se contredisent souvent : on dit sur combien d'entre eux la période repose
  const dpe = (liste || []).filter((d) => d[cle]);
  const memes = dpe.filter((d) => d[cle] === eq.generateur).length;
  const appui = dpe.length >= 2 && memes ? `${nom} dans ${memes} DPE sur ${dpe.length} · ADEME` : 'DPE ADEME';
  return { texte, points, source: `${appui} ; ${ref.source}`, court: role };
}

/**
 * fiche : voir recherche/reel-contrat.md. Chaque champ peut manquer.
 * Retour : { niveau, libelle, points, raisons (au plus quatre, de la plus lourde à la plus légère), manque }
 */
export function evaluer(fiche = {}) {
  const f = fiche || {};
  const raisons = [];
  const manque = [];
  const collectif = !!f.chauffage?.collectif;
  const logts = +f.nb_logements || 0;

  // 1. Chauffage : l'âge des générateurs, lu dans les libellés des DPE.
  const rc = raisonEquipement(f.chauffage, { role: 'chauffage', collectif, poids: collectif ? 46 : 40, durete: f.durete_eau_f, liste: f.dpe, cle: 'generateur_chauffage' });
  if (rc) {
    // une chaudière collective qui tombe, c'est tout l'immeuble sans chauffage
    if (collectif && logts >= 10) rc.texte += ` · ${logts} logements desservis`;
    raisons.push(rc);
  } else if (!f.chauffage?.generateur) manque.push('âge du chauffage');

  // 2. Eau chaude : quand elle n'est pas produite par la même chaudière.
  const memeGenerateur = f.eau_chaude?.generateur && f.chauffage?.generateur && sansAccent(f.eau_chaude.generateur) === sansAccent(f.chauffage.generateur);
  if (!memeGenerateur) {
    const re = raisonEquipement(f.eau_chaude, { role: 'eau_chaude', collectif: false, poids: 26, durete: f.durete_eau_f, liste: f.dpe, cle: 'generateur_ecs' });
    if (re) raisons.push(re);
    else if (!f.eau_chaude?.generateur) manque.push('âge de l’eau chaude');
  }

  // 3. Ventilation : la période se lit aussi dans le libellé (« VMC SF Auto réglable de 1982 à 2000 »).
  if (f.ventilation) {
    const per = periode(f.ventilation);
    const r = per && pointsAge(per, DUREES.vmc.ans, 16);
    if (r && r.points > 0) raisons.push({ texte: `Ventilation ${pose(per)} : ${age(r, DUREES.vmc.ans)}`, points: r.points, source: `DPE ADEME ; ${DUREES.vmc.source}`, court: 'ventilation' });
  } else manque.push('ventilation');

  // 4. Dureté de l'eau : à âge égal, un ballon s'entartre plus vite dans une eau dure.
  if (f.durete_eau_f != null) {
    const d = +f.durete_eau_f;
    if (d >= 25) raisons.push({ texte: `Eau très dure (${Math.round(d)} °f) : tartre dans les ballons et échangeurs`, points: d >= 30 ? 10 : 7, source: 'Hub’Eau, contrôle sanitaire de l’eau potable', court: 'eau' });
    else if (d < 8) raisons.push({ texte: `Eau très douce (${Math.round(d)} °f) : canalisations plus exposées à la corrosion`, points: 4, source: 'Hub’Eau, contrôle sanitaire de l’eau potable', court: 'eau' });
  } else manque.push('dureté de l’eau');

  // 5. 2G : les téléalarmes d'ascenseur et transmetteurs de chaufferie sur carte SIM 2G peuvent se taire sans panne.
  const ascenseurProbable = (+f.nb_niveaux || 0) >= 5 || (+f.hauteur_m || 0) >= 15;
  if (ascenseurProbable) {
    const dpt = f.departement || String(f.code_commune || f.id_commune || '').slice(0, 2);
    const texte = phrase2G(dpt, f.code_commune);
    if (texte) {
      raisons.push({
        texte,
        points: (+f.nb_niveaux || 0) >= 7 ? 14 : 11,
        source: `Calendrier d’arrêt de la 2G (ARCEP, Orange) ; ascenseur probable d’après ${f.nb_niveaux ? `${f.nb_niveaux} niveaux` : `${f.hauteur_m} m`} (BDNB) : téléalarme à vérifier`,
        court: '2g',
      });
    }
  }

  // 6. Sol argileux : retrait-gonflement, fissures après les sécheresses.
  const argile = sansAccent(f.risques?.argile);
  if (argile) {
    if (/fort/.test(argile)) raisons.push({ texte: 'Sol argileux, aléa fort : fissures après sécheresse', points: 10, source: 'BDNB, aléa retrait-gonflement des argiles (BRGM)', court: 'argile' });
    else if (/moyen/.test(argile)) raisons.push({ texte: 'Sol argileux, aléa moyen', points: 5, source: 'BDNB, aléa retrait-gonflement des argiles (BRGM)', court: 'argile' });
  } else manque.push('risque argile');

  // 7. Inondation : arrêtés de catastrophe naturelle de la commune, plan de prévention.
  const ino = f.risques?.inondation;
  if (ino && typeof ino === 'object') {
    const n = ino.arretes == null ? null : +ino.arretes;
    // le nom du plan, tel que le GPU l'écrit (« Lez_Mosson », « Bassin de risque 3 _ MONTPELLIER »), reste dans la source
    const plan = (ino.ppr_noms || []).map((x) => String(x).replace(/_/g, ' ').replace(/\s+/g, ' ').trim()).filter(Boolean).pop();
    if (ino.ppr) raisons.push({ texte: 'Plan de prévention des risques : sous-sols et locaux techniques exposés', points: 6, source: `Géoportail de l’urbanisme, servitude PM1 au point du bâtiment${plan ? ` (${plan})` : ''}`, court: 'inondation' });
    else if (n >= 3) raisons.push({ texte: `Commune inondable : ${n} arrêtés de catastrophe naturelle`, points: 5, source: 'Géorisques, base GASPAR', court: 'inondation' });
    if (n == null && !ino.ppr) manque.push('arrêtés de catastrophe naturelle');
  } else if (ino == null) manque.push('risque inondation');

  // 8. Énergie : une étiquette F ou G bloque la relocation (loi Climat et résilience : G depuis 2025, F en 2028).
  // L'étiquette de l'immeuble : la plus fréquente parmi ses DPE de l'ADEME (regles.mjs).
  const e = etiquetteImmeuble(f);
  if (e?.lettre === 'G') raisons.push({ texte: 'Étiquette G : interdite à la location depuis le 1er janv. 2025', points: 18, source: `Étiquette G ${e.texte} ; loi Climat et résilience`, court: 'energie' });
  else if (e?.lettre === 'F') raisons.push({ texte: 'Étiquette F : interdite à la location au 1er janv. 2028', points: 12, source: `Étiquette F ${e.texte} ; loi Climat et résilience`, court: 'energie' });
  else if (!e) manque.push('étiquette DPE');

  // 9. Bâti : avant 1975, réseaux d'eau et colonnes d'origine probables (première réglementation thermique en 1974).
  const an = +f.annee_construction || 0;
  if (an && an < 1975) raisons.push({ texte: `Construit en ${an} : colonnes et réseaux d’origine probables`, points: an < 1949 ? 8 : 5, source: 'BDNB (fichiers fonciers)', court: 'bati' });
  else if (!an) manque.push('année de construction');

  // un remplacement récent, daté par deux DPE successifs, rassure
  // seulement en chauffage collectif : en individuel, deux DPE successifs décrivent souvent deux logements différents
  const recent = collectif ? (f.remplacements || []).filter((x) => (x.entre?.[1] || '') >= `${ANNEE - 3}`) : [];
  if (recent.length) raisons.push({ texte: `Générateur remplacé entre ${dateCourte(recent[0].entre[0])} et ${dateCourte(recent[0].entre[1])}`, points: -8, source: 'DPE ADEME, deux diagnostics successifs', court: 'remplace' });

  const points = Math.round(raisons.reduce((s, r) => s + r.points, 0));
  const n = NIVEAUX.find((x) => points >= x.min);
  const triees = raisons.filter((r) => r.points > 0).sort((a, b) => b.points - a.points);
  const rassurantes = raisons.filter((r) => r.points < 0);
  return {
    niveau: n.niveau,
    libelle: n.libelle,
    points,
    raisons: [...triees.slice(0, 4 - Math.min(1, rassurantes.length)), ...rassurantes.slice(0, 1)].map(({ texte, points: p, source }) => ({ texte, points: p, source })),
    manque,
  };
}
