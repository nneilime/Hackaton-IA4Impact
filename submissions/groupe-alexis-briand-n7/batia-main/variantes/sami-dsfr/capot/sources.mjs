// Sous le capot — la chaîne « adresse → fiche de l'immeuble », source publique après source publique.
// Le même code tourne dans le navigateur (démonstration) et dans Node (enregistrements du filet de secours).
// Chaque étape reçoit le contexte des précédentes et une fonction appeler(url, options) qui choisit
// le direct, le relais local ou l'enregistrement. Rien ici ne lit les données du kit.

import { etiquetteImmeuble, phrase2G, ARRET_2G } from '../reel/regles.mjs'; // la règle commune de BâtIA (reel/regles.mjs)
export const AUJOURDHUI = '2026-10-10';

// Calendrier d'extinction de la 2G : celui de toute l'application (reel/regles.mjs), une seule source de dates.
export const EXTINCTION_2G = { Orange: ARRET_2G.orange, SFR: ARRET_2G.sfr, 'Bouygues Telecom': ARRET_2G.bouygues };

const enc = encodeURIComponent;
const MOIS = ['janv.', 'févr.', 'mars', 'avril', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
export const dateCourte = (iso, annee = true) => {
  if (!iso) return '';
  const [a, m, j] = iso.slice(0, 10).split('-').map(Number);
  return `${j === 1 ? '1er' : j} ${MOIS[m - 1]}${annee ? ' ' + a : ''}`;
};
export const nombre = (n, dec = 0) => new Intl.NumberFormat('fr-FR', { maximumFractionDigits: dec, minimumFractionDigits: dec }).format(n);

// Une source qui répond, mais sans rien pour cet immeuble : ce qu'on affiche à la place, et pourquoi.
export class Introuvable extends Error { constructor(message, valeur) { super(message); this.valeur = valeur; } }

// Distance (m) et cap (degrés depuis le nord) entre deux points [lon, lat].
export function distance([x1, y1], [x2, y2]) {
  const R = 6371000, r = Math.PI / 180;
  const dl = (y2 - y1) * r, dg = (x2 - x1) * r;
  const a = Math.sin(dl / 2) ** 2 + Math.cos(y1 * r) * Math.cos(y2 * r) * Math.sin(dg / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}
export function cap([x1, y1], [x2, y2]) {
  const r = Math.PI / 180;
  const y = Math.sin((x2 - x1) * r) * Math.cos(y2 * r);
  const x = Math.cos(y1 * r) * Math.sin(y2 * r) - Math.sin(y1 * r) * Math.cos(y2 * r) * Math.cos((x2 - x1) * r);
  return (Math.atan2(y, x) / r + 360) % 360;
}

// « Chaudière gaz standard 2001-2015 », « VMC SF Auto réglable de 1982 à 2000 », « … après 2015 », « … avant 1948 »
export function periode(libelle) {
  if (!libelle) return null;
  let m;
  if ((m = /(\d{4})\s*(?:-|à)\s*(\d{4})/.exec(libelle))) return [+m[1], +m[2]];
  if ((m = /apr[eè]s\s*(\d{4})/i.exec(libelle))) return [+m[1] + 1, +AUJOURDHUI.slice(0, 4)];
  if ((m = /avant\s*(\d{4})/i.exec(libelle))) return [null, +m[1] - 1];
  return null;
}
const sansPeriode = (libelle) => (libelle || '').replace(/\s*(de\s*)?\d{4}\s*(-|à)\s*\d{4}/, '').replace(/\s*(après|avant)\s*\d{4}/i, '').replace(/\s*«[^»]*»/, '').trim();

function mode(liste) {
  const n = new Map();
  for (const x of liste) if (x) n.set(x, (n.get(x) || 0) + 1);
  return [...n.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
}

const IGN = 'IGN';

export const ETAPES = [
  {
    id: 'adresse', titre: 'Adresse', source: 'IGN · Géoplateforme', url: 'https://adresse.data.gouv.fr/', licence: 'Licence Ouverte 2.0',
    async lancer(ctx, appeler) {
      const j = await appeler(`https://data.geopf.fr/geocodage/search?q=${enc(ctx.saisie)}&limit=1&index=address`, { etape: 'adresse', valide: (j) => j.features?.length });
      const f = j.features[0], p = f.properties;
      if (p.type !== 'housenumber') throw new Introuvable('Ce numéro n’existe pas : seule la rue est connue.');
      Object.assign(ctx, { ban: p.id, position: f.geometry.coordinates, commune: p.city, insee: p.citycode, departement: p.depcode || String(p.context || '').split(',')[0], adresse: p.label, voie: p.name, cp: p.postcode });
      // Géorisques passe par le relais local et part tout de suite : sa réponse (ou son silence) est connue avant sa ligne.
      const [x, y] = ctx.position;
      ctx.solEnAvance = appeler(`https://georisques.gouv.fr/api/v1/rga?latlon=${x.toFixed(6)},${y.toFixed(6)}`, { etape: 'sol', relais: true, sansEnregistrement: true, valide: (j) => j && (j.exposition || j.codeExposition != null) }).catch(() => null);
      return { valeur: p.name, sous: `${p.postcode} ${p.city}` };
    },
  },
  {
    id: 'batiment', titre: 'Bâtiment', source: 'RNB', url: 'https://rnb.beta.gouv.fr/', licence: 'Licence Ouverte 2.0',
    async lancer(ctx, appeler) {
      const j = await appeler(`https://rnb-api.beta.gouv.fr/api/alpha/buildings/address/?cle_interop_ban=${enc(ctx.ban)}`, { etape: 'batiment', valide: (j) => j.results?.length });
      const b = j.results.find((x) => x.status === 'constructed') || j.results[0];
      ctx.rnb = b.rnb_id;
      ctx.contour = b.shape?.type?.endsWith('Polygon') ? b.shape : null;
      ctx.pointBatiment = b.point?.coordinates || ctx.position;
      return { valeur: ctx.contour ? 'contour officiel' : 'repéré', sous: `identifiant national ${b.rnb_id.replace(/(.{4})(.{4})(.{4})/, '$1-$2-$3')}` };
    },
  },
  {
    id: 'fiche', titre: 'Immeuble', source: 'BDNB', url: 'https://bdnb.io/', licence: 'Licence Ouverte 2.0',
    async lancer(ctx, appeler) {
      let groupe = null;
      try {
        const rel = await appeler(`https://api.bdnb.io/v1/bdnb/donnees/rel_batiment_groupe_adresse?cle_interop_adr=eq.${enc(ctx.ban)}&select=batiment_groupe_id&limit=1`, { etape: 'fiche-lien', valide: (j) => j.length });
        groupe = rel[0].batiment_groupe_id;
      } catch {
        const rel = await appeler(`https://api.bdnb.io/v1/bdnb/donnees/batiment_construction?rnb_id=eq.${enc(ctx.rnb)}&select=batiment_groupe_id&limit=1`, { etape: 'fiche-lien-rnb', valide: (j) => j.length });
        groupe = rel[0].batiment_groupe_id;
      }
      const champs = 'batiment_groupe_id,annee_construction,nb_log,nb_niveau,hauteur_mean,classe_bilan_dpe,conso_5_usages_ep_m2,type_generateur_chauffage,type_generateur_chauffage_anciennete,type_installation_chauffage,type_energie_chauffage,type_generateur_ecs,type_ventilation,alea_argile,l_denomination_proprietaire,l_cle_interop_adr,surface_emprise_sol';
      const j = await appeler(`https://api.bdnb.io/v1/bdnb/donnees/batiment_groupe_complet?batiment_groupe_id=eq.${enc(groupe)}&select=${champs}&limit=1`, { etape: 'fiche', valide: (j) => j.length });
      const b = j[0];
      ctx.bdnb = b;
      const morceaux = [b.annee_construction && `${b.annee_construction}`, b.nb_log && `${nombre(b.nb_log)} logements`, b.nb_niveau && `${b.nb_niveau} niveaux`].filter(Boolean);
      // Le propriétaire n'est publié que s'il est une personne morale. Une société civile immobilière est souvent
      // une affaire de famille : son nom ne s'affiche pas, on reste à l'échelle de l'immeuble.
      const nomProprietaire = (b.l_denomination_proprietaire || [])[0];
      const familial = /^(S\.?C\.?I\.?|SC|SOCIETE CIVILE)\b/i.test(String(nomProprietaire || '').trim());
      const proprietaire = familial ? null : nomProprietaire;
      const sous = proprietaire ? `propriétaire : ${proprietaire}` : familial ? 'propriétaire : une société civile (nom non affiché)' : 'propriétaire non publié (particulier)';
      return { valeur: morceaux.join(' · ') || 'fiche trouvée', sous, proprietaire };
    },
  },
  {
    id: 'hauteur', titre: 'Hauteur', source: 'IGN · LiDAR HD', url: 'https://geoservices.ign.fr/lidarhd', licence: 'Licence Ouverte 2.0',
    async lancer(ctx, appeler) {
      const [x, y] = ctx.pointBatiment;
      const j = await appeler(`https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json?lon=${x.toFixed(6)}&lat=${y.toFixed(6)}&resource=ign_lidar_hd_mnx_mono_wld&zonly=false&measures=true`, { etape: 'hauteur', valide: (j) => j.elevations?.length });
      const mesures = j.elevations[0].measures || [];
      const sol = mesures.find((m) => /MNT/.test(m.title))?.z, dessus = mesures.find((m) => /MNS/.test(m.title))?.z;
      const h = sol != null && dessus != null ? dessus - sol : null;
      // Le laser vise un seul point : s'il tombe sur une partie basse (cour, socle), la hauteur ne colle pas aux niveaux.
      const niveaux = ctx.bdnb?.nb_niveau;
      const plausible = (v) => v != null && v > 2.5 && (!niveaux || v >= niveaux * 2.2);
      if (plausible(h)) { ctx.hauteur = h; return { valeur: `${nombre(h, 1)} m`, sous: 'mesurée au laser, depuis un avion' }; }
      if (plausible(ctx.bdnb?.hauteur_mean)) { ctx.hauteur = ctx.bdnb.hauteur_mean; return { valeur: `${nombre(ctx.hauteur)} m`, sous: 'hauteur moyenne relevée par la BDNB', source: 'BDNB' }; }
      if (niveaux) { ctx.hauteur = niveaux * 3; return { valeur: `environ ${nombre(ctx.hauteur)} m`, sous: `estimée : ${niveaux} niveaux de 3 m`, source: 'BDNB' }; }
      throw new Introuvable('aucun relevé laser ici', 'non mesurée');
    },
  },
  {
    id: 'dpe', titre: 'Chauffage', source: 'ADEME · DPE', url: 'https://observatoire-dpe-audit.ademe.fr/', licence: 'Licence Ouverte 2.0',
    async lancer(ctx, appeler) {
      const cles = [...new Set([ctx.ban, ...(ctx.bdnb?.l_cle_interop_adr || [])])].slice(0, 8);
      const qs = `identifiant_ban:(${cles.map((c) => `"${c}"`).join(' OR ')})`;
      // Jamais le complément d'adresse (étage, porte) : on ne demande que les champs de l'immeuble.
      const sel = 'etiquette_dpe,date_etablissement_dpe,type_generateur_chauffage_principal,type_generateur_n1_ecs_n1,type_ventilation,type_installation_chauffage,type_energie_principale_chauffage,conso_5_usages_par_m2_ep';
      const j = await appeler(`https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/lines?size=100&qs=${enc(qs)}&select=${sel}&sort=-date_etablissement_dpe`, { etape: 'dpe', valide: (j) => j.results?.length });
      const dpe = j.results.map((d) => ({ date: d.date_etablissement_dpe, etiquette: d.etiquette_dpe, generateur_chauffage: d.type_generateur_chauffage_principal, ecs: d.type_generateur_n1_ecs_n1, ventilation: d.type_ventilation, installation: d.type_installation_chauffage, energie: d.type_energie_principale_chauffage, conso: d.conso_5_usages_par_m2_ep }));
      ctx.dpe = dpe;
      ctx.dpeTotal = j.total ?? dpe.length;
      const generateur = mode(dpe.map((d) => d.generateur_chauffage));
      // l'étiquette suit la règle de toute l'application : celle de la carte si l'immeuble est au parc d'In'li
      const e = etiquetteImmeuble(ctx.connu || { dpe });
      const etiquette = e?.lettre || null;
      ctx.etiquette = etiquette;
      const per = periode(generateur);
      const installation = mode(dpe.map((d) => d.installation));
      const nom = sansPeriode(generateur).replace(/^Effet joule.*$/i, 'Radiateurs électriques').replace(/\s*NFC\b.*$/, '').replace(/^Chaudière/, 'Chaudières').replace(/^Pompe/, 'Pompes');
      const an = +AUJOURDHUI.slice(0, 4);
      const recent = per && per[1] >= an;
      const quand = per ? (recent ? `d’après ${per[0] - 1}` : per[0] ? `${per[0]}\u2011${per[1]}` : `d’avant ${per[1] + 1}`) : '';
      const age = !per ? null : recent ? `moins de ${an - per[0] + 1} ans` : per[0] ? `${an - per[1]} à ${an - per[0]} ans` : `plus de ${an - per[1]} ans`;
      return {
        valeur: [nom, quand].filter(Boolean).join(' ') || 'chauffage non décrit',
        sous: [age && `posées il y a ${age}`, installation && (installation === 'individuel' ? 'une par logement' : installation), e && `étiquette ${e.lettre} ${e.texte}`].filter(Boolean).join(' · '),
        etiquette,
      };
    },
  },
  {
    id: 'antenne', titre: 'Réseau 2G', source: 'ARCEP · Orange', url: 'https://www.arcep.fr/cartes-et-donnees/nos-cartes/cartes-fin-2g-3g.html', licence: 'Licence Ouverte 2.0', relais: true,
    async lancer(ctx, appeler) {
      const [x, y] = ctx.position;
      const j = await appeler(`/capot/anfr?lon=${x.toFixed(5)}&lat=${y.toFixed(5)}`, { etape: 'antenne', local: true, valide: (j) => j.operateurs });
      const dep = String(ctx.departement || '').padStart(2, '0');
      const op = j.operateurs;
      const orangeDate = EXTINCTION_2G.Orange[+dep] || EXTINCTION_2G.Orange[dep];
      const orangeEteinte = orangeDate && orangeDate <= AUJOURDHUI && (!op.Orange || op.Orange.distance_m > 1500);
      const restants = Object.entries(op).filter(([, v]) => v && v.distance_m < 3000);
      const proche = restants.sort((a, b) => a[1].distance_m - b[1].distance_m)[0];
      const prochaine = [EXTINCTION_2G.SFR, EXTINCTION_2G['Bouygues Telecom']].filter((d) => d > AUJOURDHUI).sort()[0];
      ctx.antenne2g = { distance_m: proche ? Math.round(proche[1].distance_m) : null, extinction_prevue: orangeEteinte ? orangeDate : prochaine, eteinte: orangeEteinte ? `Orange, ${dateCourte(orangeDate)}` : null, export: j.export };
      // la phrase de toute l'application (reel/regles.mjs), coupée en deux : « Fin de la 2G en 2026 » puis les dates
      const [tete, dates] = phrase2G(dep, ctx.insee).split(' : ');
      return { valeur: tete, sous: dates, source: 'ARCEP · Orange', alerte: /depuis/.test(dates) };
    },
  },
  {
    id: 'sol', titre: 'Sol', source: 'Géorisques', url: 'https://www.georisques.gouv.fr/', licence: 'Licence Ouverte 2.0', relais: true,
    async lancer(ctx, appeler) {
      const NIVEAUX = { 3: 'Fort', 2: 'Moyen', 1: 'Faible', 0: 'Nul' };
      let argile = null, source = 'Géorisques';
      const j = await ctx.solEnAvance;
      if (j) argile = j.exposition ? j.exposition.replace(/^Exposition\s*/i, '').replace(/^./, (c) => c.toUpperCase()) : NIVEAUX[j.codeExposition];
      // Géorisques ne répond pas (hors de France, ou coupure) : l'aléa argile du BRGM est aussi recopié dans la BDNB.
      else if (ctx.bdnb?.alea_argile) { argile = ctx.bdnb.alea_argile; source = 'BDNB · BRGM'; }
      if (!argile) throw new Introuvable('aléa argile non publié ici', 'non renseigné');
      ctx.argile = argile;
      const fort = /fort/i.test(argile);
      return { valeur: `argile : aléa ${argile.toLowerCase()}`, sous: fort ? 'fissures possibles après une sécheresse' : 'retrait-gonflement des sols', source, alerte: fort };
    },
  },
  {
    id: 'eau', titre: 'Eau', source: 'Hub’Eau', url: 'https://hubeau.eaufrance.fr/', licence: 'Licence Ouverte 2.0',
    async lancer(ctx, appeler) {
      // Hub'Eau range Paris, Lyon et Marseille sous la commune entière, pas sous l'arrondissement.
      const i = String(ctx.insee || '');
      const commune = /^751\d\d$/.test(i) ? '75056' : /^6938\d$/.test(i) ? '69123' : /^132\d\d$/.test(i) ? '13055' : i;
      let j;
      try { j = await appeler(`https://hubeau.eaufrance.fr/api/v1/qualite_eau_potable/resultats_dis?code_commune=${enc(commune)}&code_parametre_se=TH&size=20&sort=desc&fields=resultat_numerique,date_prelevement`, { etape: 'eau', valide: (j) => j.data?.length }); }
      catch (err) { if (err.vide) throw new Introuvable('aucun relevé de dureté pour la commune', 'pas de relevé'); throw err; }
      const valeurs = j.data.filter((d) => d.resultat_numerique != null).map((d) => d.resultat_numerique).sort((a, b) => a - b);
      const med = valeurs[Math.floor(valeurs.length / 2)];
      ctx.durete = med;
      const dernier = j.data[0]?.date_prelevement;
      const mot = med >= 30 ? 'très calcaire' : med >= 20 ? 'calcaire' : med >= 10 ? 'peu calcaire' : 'très douce';
      return { valeur: mot, sous: `dureté ${nombre(med, 0)} °f (degrés français) · relevé du ${dateCourte(dernier)}` };
    },
  },
  {
    id: 'photo', titre: 'Façade', source: 'Panoramax', url: 'https://panoramax.fr/', licence: 'Licence Ouverte 2.0', image: true,
    async lancer(ctx, appeler) {
      const [x, y] = ctx.pointBatiment;
      const bbox = [x - 0.0011, y - 0.0008, x + 0.0011, y + 0.0008].map((v) => v.toFixed(5)).join(',');
      let j;
      try { j = await appeler(`https://api.panoramax.xyz/api/search?bbox=${bbox}&limit=60`, { etape: 'photo', valide: (j) => j.features?.length }); }
      catch (err) { if (err.vide) throw new Introuvable('aucune photo de rue autour de l’immeuble', 'pas encore photographiée'); throw err; }
      const candidates = [];
      for (const f of j.features) {
        const p = f.properties, pos = f.geometry.coordinates;
        const d = distance(pos, ctx.pointBatiment), c = cap(pos, ctx.pointBatiment);
        const fov = p['pers:interior_orientation']?.field_of_view || 70;
        const az = p['view:azimuth'] ?? 0;
        const ecart = Math.abs(((c - az + 540) % 360) - 180);
        if (fov < 360 && ecart > fov / 2 - 8) continue;
        if (d < 10 || d > 90) continue;
        const age = (Date.parse(AUJOURDHUI) - Date.parse(p.datetime)) / 864e5 / 365;
        // Une prise de vue proche du point d'adresse est dans la bonne rue, face à l'entrée.
        const entree = distance(pos, ctx.position);
        candidates.push({ f, d, c, fov, az, note: Math.abs(d - 32) + age * 4 + entree * 0.5 + (fov < 360 ? ecart / 2 : 0) });
      }
      candidates.sort((a, b) => a.note - b.note);
      const k = candidates[0];
      if (!k) throw new Introuvable('aucune photo de rue tournée vers l’immeuble', 'pas encore photographiée');
      const p = k.f.properties;
      const licence = (k.f.links || []).find((l) => l.rel === 'license')?.title?.match(/\(([^)]+)\)/)?.[1] || 'voir la photo';
      const auteur = String(p['geovisio:producer'] || 'contributeur Panoramax').replace(/_/g, ' ').replace(/\btopo\b/i, '').trim().replace(/(^|\s)\S/g, (c) => c.toUpperCase()).replace(/Metropole/, 'Métropole');
      ctx.photo = { id: k.f.id, url: k.f.assets?.sd?.href, date: p.datetime?.slice(0, 10), auteur, licence, fov: k.fov, azimut: k.az, cap: k.c, distance: k.d, position: k.f.geometry.coordinates };
      return { valeur: `photo du ${dateCourte(ctx.photo.date)}`, sous: `${auteur.replace(/^./, (c) => c.toUpperCase())} · ${licence}` };
    },
  },
];

// La fiche commune (recherche/reel-contrat.md), assemblée à partir du contexte.
export function assemblerFiche(ctx, lues) {
  const b = ctx.bdnb || {};
  const generateur = ctx.dpe ? mode(ctx.dpe.map((d) => d.generateur_chauffage)) : null;
  const ecs = ctx.dpe ? mode(ctx.dpe.map((d) => d.ecs)) : null;
  const ventilation = ctx.dpe ? mode(ctx.dpe.map((d) => d.ventilation)) : b.type_ventilation || null;
  const installation = ctx.dpe ? mode(ctx.dpe.map((d) => d.installation)) : b.type_installation_chauffage;
  const conso = ctx.dpe?.map((d) => d.conso).filter((v) => v > 0).sort((a, c) => a - c);
  return {
    id_bdnb: b.batiment_groupe_id || null, id_rnb: ctx.rnb || null, adresse: ctx.adresse || null, commune: ctx.commune || null, position: ctx.position || null,
    code_commune: ctx.insee || null, departement: ctx.departement || null,
    annee_construction: b.annee_construction ?? null, nb_logements: b.nb_log ?? null, nb_niveaux: b.nb_niveau ?? null, hauteur_m: ctx.hauteur != null ? Math.round(ctx.hauteur * 10) / 10 : b.hauteur_mean ?? null,
    etiquette_dpe: ctx.etiquette || b.classe_bilan_dpe || null, conso_kwhep_m2_an: conso?.length ? Math.round(conso[Math.floor(conso.length / 2)]) : b.conso_5_usages_ep_m2 ?? null,
    chauffage: { collectif: installation ? installation !== 'individuel' : null, energie: ctx.dpe ? mode(ctx.dpe.map((d) => d.energie)) : b.type_energie_chauffage || null, generateur: generateur || b.type_generateur_chauffage || null, periode_generateur: periode(generateur) },
    eau_chaude: { generateur: ecs, periode_generateur: periode(ecs) },
    ventilation,
    dpe: (ctx.dpe || []).map(({ date, etiquette, generateur_chauffage }) => ({ date, etiquette, generateur_chauffage })),
    risques: { argile: ctx.argile || b.alea_argile || null, inondation: ctx.inondation ?? null },
    antenne_2g: ctx.antenne2g ? { distance_m: ctx.antenne2g.distance_m, extinction_prevue: ctx.antenne2g.extinction_prevue } : null,
    durete_eau_f: ctx.durete ?? null,
    sources: lues,
  };
}
