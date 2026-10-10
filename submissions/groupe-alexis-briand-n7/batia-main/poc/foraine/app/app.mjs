// Foraine — la carte est l'application : la file, les fiches et l'énergie se posent dessus.
import { creerCarte } from '/carte/carte.mjs';

// ── Outils ──────────────────────────────────────────────────────────
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const nb = (n) => new Intl.NumberFormat('fr-FR').format(n);
const euros = (n) => (n >= 1e6 ? `${nb(Math.round(n / 1e5) / 10)} M€` : `${nb(Math.round(n / 1000))} k€`);
const pl = (n, un, plusieurs) => `${nb(n)} ${n > 1 ? plusieurs : un}`;
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const sansAccent = (s) => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
const MOIS_LONGS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
const dateCourte = (iso) => { if (!iso) return ''; const [a, m, j] = iso.slice(0, 10).split('-'); return `${+j} ${MOIS[+m - 1]} ${a}`; };
// au-delà d'un trimestre, l'âge du relevé se montre
const ageReleve = (iso) => {
  const j = Math.floor((Date.now() - Date.parse(iso)) / 864e5);
  if (!(j > 92)) return '';
  const m = Math.round(j / 30.44);
  return m < 12 ? `${m} mois` : `${Math.floor(m / 12)} an${m >= 24 ? 's' : ''}`;
};
const dateLongue = (iso) => { if (!iso) return ''; const [a, m, j] = iso.slice(0, 10).split('-'); return `${+j === 1 ? '1er' : +j} ${MOIS_LONGS[+m - 1]} ${a}`; };
const etage = (n) => (n === 0 ? 'RDC' : n === 1 ? '1<sup>er</sup>' : `${n}<sup>e</sup>`);
const etageLong = (n) => (n === 0 ? 'rez-de-chaussée' : n === 1 ? '1<sup>er</sup> étage' : `${n}<sup>e</sup> étage`);
const numLogt = (id) => id.split('-').pop();
const bat = (id) => id.replace('BAT-', '');
const lettre = (rid) => rid.replace('RES-', '');
const telephone = () => matchMedia('(max-width: 760px)').matches;
const reduit = matchMedia('(prefers-reduced-motion: reduce)').matches;
const ICONE_X = '<svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg>';
const DPE = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
const COULEUR_DPE = { A: '#00845A', B: '#3F9E45', C: '#8DBB5A', D: '#E7D21B', E: '#EFA81C', F: '#E3742C', G: '#CF2A22' };
const TEXTE_DPE = { D: '#3a3200', E: '#3a2400' };
const etiquette = (l) => `<span class="etiquette" style="background:${COULEUR_DPE[l] || '#999'};color:${TEXTE_DPE[l] || '#fff'}">${esc(l)}</span>`;
const CHOIX = { visite: { mot: 'Visite', fait: 'Visite décidée', touche: 'v', aide: 'envoyer le prestataire' }, remplacer: { mot: 'Remplacer', fait: 'Remplacement décidé', touche: 'r', aide: 'préparer la commande' }, 'plus-tard': { mot: 'Plus tard', fait: 'Remis à plus tard', touche: 'p', aide: 'écarter pour l’instant' } };
const NIVEAU = { visiter: 'À visiter', surveiller: 'À surveiller', calme: 'Calme' };

// ── État ────────────────────────────────────────────────────────────
const S = {
  d: null, decisions: {}, lentille: 'pannes', onglet: 'visiter', residence: null, famille: '',
  sel: null, page: null, limite: 50, echelle: 'sudouest',
  seuil: localStorage.getItem('foraine.seuil') || 'E',
  feuille: 'basse',
};
const I = { equip: new Map(), logt: new Map(), res: new Map(), bat: new Map(), equipParLogt: new Map(), plan: new Map() };
const cache = new Map();
let carte = null;

async function api(url, opts) {
  const r = await fetch(url, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.erreur || `Erreur ${r.status}`);
  return j;
}

async function charger() {
  const d = await api('/api/etat');
  S.d = d; S.decisions = d.decisions || {};
  for (const m of Object.values(I)) m.clear();
  d.equipements.forEach((e) => { I.equip.set(e.id, e); if (e.l) { if (!I.equipParLogt.has(e.l)) I.equipParLogt.set(e.l, []); I.equipParLogt.get(e.l).push(e); } });
  d.logements.forEach((l) => I.logt.set(l.id, l));
  d.residences.forEach((r) => I.res.set(r.id, r));
  d.batiments.forEach((b) => I.bat.set(b.id, b));
  d.plan.forEach((o) => { if (!I.plan.has(o.r)) I.plan.set(o.r, []); I.plan.get(o.r).push(o); });
  cache.clear();
  const age = ageReleve(d.releve);
  // relevé ancien : son âge prend la place du nom, sur la même ligne
  $('.marque-nom small').innerHTML = age ? `<span class="date-releve">relevé au ${dateCourte(d.releve)} · </span><b class="vieux">il y a ${age}</b>` : `In'li Sud-Ouest · relevé au ${dateCourte(d.releve)}`;
}

// ── Lieux et comptes ────────────────────────────────────────────────
function lieu(e, { court = true } = {}) {
  const r = lettre(e.r);
  if (e.commun || !e.l) return `${r} · bât. ${bat(e.b)} · parties communes`;
  const l = I.logt.get(e.l);
  return `${r} · bât. ${bat(e.b)} · logt ${numLogt(e.l)}${l && court ? ` · ${etage(l.etage)}` : ''}`;
}
const decide = (e) => !!S.decisions[e.id];
function equipementsFiltres() {
  return S.d.equipements.filter((e) => (!S.residence || e.r === S.residence) && (!S.famille || e.famille === S.famille));
}
function comptes(liste) {
  const c = { visiter: 0, surveiller: 0, decide: 0 };
  for (const e of liste) { if (decide(e)) c.decide++; else if (e.niveau === 'visiter') c.visiter++; else if (e.niveau === 'surveiller') c.surveiller++; }
  return c;
}
const auDela = (lettreDpe) => DPE.indexOf(lettreDpe) >= DPE.indexOf(S.seuil);
const motsSeuil = () => (S.seuil === 'G' ? 'en G' : S.seuil === 'F' ? 'en F ou G' : `de ${S.seuil} à G`);

// Ce que la carte doit montrer, selon la lentille.
function residencesCarte() {
  return S.d.residences.map((r) => {
    if (S.lentille === 'energie') {
      const n = S.d.logements.filter((l) => l.r === r.id && auDela(l.dpe)).length;
      return { ...r, aVisiter: n, aSurveiller: 0, communsAVisiter: 0, alerte: n ? `<span class="rv-visiter">${nb(n)} ${motsSeuil()}</span>` : `aucun ${motsSeuil()}` };
    }
    const c = comptes(S.d.equipements.filter((e) => e.r === r.id));
    const morceaux = [];
    if (c.visiter) morceaux.push(`<span class="rv-visiter">${nb(c.visiter)} à visiter</span>`);
    if (c.surveiller) morceaux.push(`<span class="rv-surv">${nb(c.surveiller)} à surveiller</span>`);
    return { ...r, aVisiter: c.visiter, aSurveiller: c.surveiller, communsAVisiter: 0, alerte: morceaux.length ? morceaux.join('<span class="rv-sep"> · </span>') : 'rien à visiter' };
  });
}
function infoMetro() {
  if (S.lentille === 'energie') {
    const n = S.d.logements.filter((l) => auDela(l.dpe)).length;
    return { alerte: `${nb(n)} ${motsSeuil()}`, alerteLongue: `<span class="rv-visiter">${pl(n, 'logement', 'logements')} ${motsSeuil()}</span>` };
  }
  const c = comptes(S.d.equipements);
  return { alerte: `${nb(c.visiter)} à visiter`, alerteLongue: `<span class="rv-visiter">${pl(c.visiter, 'équipement', 'équipements')} à visiter</span><span class="rv-sep"> · </span><span class="rv-surv">${nb(c.surveiller)} à surveiller</span>` };
}
function majCarte() {
  if (!carte) return;
  carte.conteneur.classList.toggle('carte-energie', S.lentille === 'energie');
  carte.actualiser(residencesCarte(), infoMetro());
}

// ── La zone que les panneaux prennent sur la carte ──────────────────
function zoneOccupee() {
  const H = innerHeight;
  if (telephone()) {
    const f = $('.panneau:not([hidden]).arrive, .fiche:not([hidden])');
    return { top: 70, right: 0, left: 0, bottom: f ? hauteurFeuille() : 0 };
  }
  const file = $('#file');
  const fiche = $('#fiche');
  const left = file.classList.contains('arrive') ? file.getBoundingClientRect().right + 8 : 0;
  const right = !fiche.hidden ? innerWidth - fiche.getBoundingClientRect().left + 8 : 0;
  return { top: 78, right, left, bottom: 58 + (H < 600 ? 0 : 0) };
}

// ── La file (lentille Pannes) ───────────────────────────────────────
function rendreFile() {
  const el = $('#file');
  if (S.lentille === 'energie') return rendreEnergie(el);
  const liste = equipementsFiltres();
  const c = comptes(liste);
  const familles = [...new Map(S.d.equipements.map((e) => [e.famille, e.libelle])).entries()].sort((a, b) => a[1].localeCompare(b[1], 'fr'));
  const visibles = liste.filter((e) => (S.onglet === 'decide' ? decide(e) : !decide(e) && e.niveau === S.onglet))
    .sort((a, b) => (S.onglet === 'decide' ? (S.decisions[b.id].le || '').localeCompare(S.decisions[a.id].le || '') : a.rang - b.rang));
  const gros = S.onglet === 'decide' ? c.decide : c[S.onglet];
  const mot = { visiter: 'à visiter', surveiller: 'à surveiller', decide: gros > 1 ? 'décidés' : 'décidé' }[S.onglet];
  const choisi = S.sel?.type === 'equipement' ? S.sel.id : null;
  const res = S.residence ? I.res.get(S.residence) : null;

  el.innerHTML = `
    <button class="poignee" type="button" aria-label="Agrandir ou réduire la file"></button>
    <div class="tete">
      <div class="compte"><b>${nb(gros)}</b><span>${mot}</span><small>${res ? esc(res.nom) : 'Métropole toulousaine'}<br>${pl(liste.length, 'équipement suivi', 'équipements suivis')}</small></div>
      <div class="onglets" role="tablist" aria-label="Niveau">
        ${['visiter', 'surveiller', 'decide'].map((o) => `<button type="button" role="tab" data-onglet="${o}" aria-selected="${S.onglet === o}">${{ visiter: 'À visiter', surveiller: 'À surveiller', decide: 'Décidé' }[o]} <span>${nb(c[o])}</span></button>`).join('')}
      </div>
    </div>
    <div class="filtres">
      ${res ? `<span class="pastille">Résidence ${esc(res.lettre)}<button type="button" data-retirer="residence" aria-label="Retirer le filtre ${esc(res.nom)}">${ICONE_X}</button></span>` : ''}
      <select class="filtre-famille" aria-label="Type d'équipement">
        <option value="">Tous les équipements</option>
        ${familles.map(([f, l]) => `<option value="${esc(f)}"${S.famille === f ? ' selected' : ''}>${esc(l)}</option>`).join('')}
      </select>
      ${S.onglet === 'decide' && c.decide ? '<a class="exporter" href="/api/export/decisions.csv" download aria-label="Exporter les décisions (CSV)">Exporter</a>' : ''}
    </div>
    <div class="defile">
      ${visibles.length ? `<ol class="lignes">${visibles.slice(0, S.limite).map((e) => ligne(e, choisi)).join('')}</ol>
      ${visibles.length > S.limite ? `<button class="plus" type="button" data-plus>Afficher ${nb(Math.min(50, visibles.length - S.limite))} de plus · ${nb(visibles.length - S.limite)} restants</button>` : ''}`
      : `<div class="vide">${S.onglet === 'decide' ? '<b>Rien de décidé</b>' : `<b>Rien ${mot}</b>${res ? esc(res.nom) : 'Ce filtre'} · ${pl(c.decide, 'décision prise', 'décisions prises')}`}</div>`}
      ${PIED_TEL}
    </div>`;
}

// au téléphone, la barre n'a que la loupe : Données et Méthode passent au pied de la liste
const PIED_TEL = '<nav class="pied-tel" aria-label="Pages"><a href="#/donnees">Données</a><a href="#/methode">Méthode</a></nav>';

function ligne(e, choisi) {
  const x = S.decisions[e.id];
  const r = e.raisons[0];
  return `<li class="ligne" data-id="${e.id}" data-niveau="${e.niveau}"${x ? ' data-decide' : ''} aria-current="${e.id === choisi}" tabindex="0">
    <span class="rang" aria-label="Rang ${e.rang}">${e.rang}</span>
    <span class="ligne-titre">${esc(e.libelle)}</span>
    <span class="ligne-indice">indice <b>${e.score}</b></span>
    <span class="ligne-lieu">${lieu(e)}</span>
    ${x ? `<span class="ligne-decision">${CHOIX[x.choix].fait} · ${dateCourte(x.le)}</span>` : r ? `<span class="ligne-raison">${esc(r.court || r.texte)}${e.raisons.length > 1 ? ` <em>+${e.raisons.length - 1}</em>` : ''}</span>` : ''}
  </li>`;
}

// ── La lentille Énergie ─────────────────────────────────────────────
function rendreEnergie(el) {
  const logts = S.d.logements;
  const n = logts.filter((l) => auDela(l.dpe)).length;
  const lignes = S.d.residences.map((r) => {
    const ls = S.d.logements.filter((l) => l.r === r.id);
    return { r, n: ls.filter((l) => auDela(l.dpe)).length, total: ls.length, ops: (I.plan.get(r.id) || []).filter((o) => o.gain > 0) };
  }).sort((a, b) => b.n - a.n || b.r.conso - a.r.conso);
  const choisi = S.sel?.type === 'residence' ? S.sel.id : S.residence;
  el.innerHTML = `
    <button class="poignee" type="button" aria-label="Agrandir ou réduire la liste"></button>
    <div class="tete">
      <div class="compte"><b>${nb(n)}</b><span>${n > 1 ? 'logements' : 'logement'} ${motsSeuil()}</span><small>sur ${nb(logts.length)}<br>${logts.length > 1 ? 'logements' : 'logement'}</small></div>
      <div class="echelle-dpe" role="radiogroup" aria-label="Seuil d'alerte DPE">
        ${DPE.map((l) => `<button type="button" role="radio" data-seuil="${l}" aria-checked="${S.seuil === l}" class="${auDela(l) ? 'au-dela' : ''}${S.seuil === l ? ' seuil' : ''}" title="Alerte à partir de ${l}">${l}</button>`).join('')}
      </div>
      <div class="legende-dpe"><span>Seuil d’alerte : ${S.seuil}</span></div>
    </div>
    <div class="defile">
      <ol class="res-energie">${lignes.map(({ r, n: k, total, ops }) => `
        <li data-res="${r.id}" aria-current="${r.id === choisi}" tabindex="0">
          <span class="lettre-res">${esc(r.lettre)}</span>
          <span class="ligne-titre">${esc(r.nom)} ${etiquette(r.dpe)}</span>
          <span class="compte-dpe"><b>${nb(k)}</b>sur ${nb(total)}</span>
          <span class="ligne-lieu">${nb(r.conso)} kWh/m²/an · ${esc(r.chauffage.replace(/ \(.*\)/, ''))}</span>
          <span class="dpe-barre" style="grid-column:2/4" aria-hidden="true">${repartition(S.d.logements.filter((l) => l.r === r.id))}</span>
          ${ops.length ? `<span class="ops">${pl(ops.length, 'opération à gain énergétique', 'opérations à gain énergétique')} · ${euros(ops.reduce((s, o) => s + o.cout, 0))}</span>` : ''}
        </li>`).join('')}
      </ol>
      ${PIED_TEL}
    </div>`;
}
function repartition(logts) {
  const n = logts.length || 1;
  return DPE.map((l) => { const k = logts.filter((x) => x.dpe === l).length; return k ? `<i style="width:${(k / n) * 100}%;background:${COULEUR_DPE[l]};opacity:${auDela(l) ? 1 : 0.35}" title="${l} : ${k}"></i>` : ''; }).join('');
}

// ── Les fiches ──────────────────────────────────────────────────────
async function rendreFiche() {
  const el = $('#fiche');
  if (!S.sel) { el.hidden = true; document.body.classList.add('sans-fiche'); majTerritoire(); return; }
  el.hidden = false; document.body.classList.remove('sans-fiche');
  majTerritoire();
  const { type, id } = S.sel;
  const cle = `${type}/${id}`;
  if (!cache.has(cle) && type !== 'residence') {
    el.innerHTML = `<button class="poignee" type="button" aria-label="Agrandir ou réduire la fiche"></button><button class="fermer" type="button" data-fermer-fiche aria-label="Fermer la fiche">${ICONE_X}</button><div class="tete"><h2>…</h2></div>`;
    try { cache.set(cle, await api(`/api/${type}/${encodeURIComponent(id)}`)); } catch (err) { el.innerHTML += `<div class="vide"><b>Introuvable</b>${esc(err.message)}</div>`; return; }
    if (!S.sel || `${S.sel.type}/${S.sel.id}` !== cle) return;
  }
  const html = type === 'equipement' ? ficheEquipement(cache.get(cle)) : type === 'logement' ? ficheLogement(cache.get(cle)) : ficheResidence(I.res.get(id));
  const defile = $('.defile', el)?.scrollTop;
  el.innerHTML = `<button class="poignee" type="button" aria-label="Agrandir ou réduire la fiche"></button><button class="fermer" type="button" data-fermer-fiche aria-label="Fermer la fiche">${ICONE_X}</button>${html}`;
  if (S.garderDefilement && defile) $('.defile', el).scrollTop = defile;
  S.garderDefilement = false;
}

function ficheEquipement({ equipement: e0, interventions, demandes, brut }) {
  const e = I.equip.get(e0.id) || e0;
  const x = S.decisions[e.id];
  const f = e.faits || {};
  const l = e.l ? I.logt.get(e.l) : null;
  const res = I.res.get(e.r);
  const max = Math.max(...e.raisons.map((r) => r.poids), 0.0001);
  const histoire = melanger(interventions, demandes.filter((dm) => pertinente(dm, e)));
  return `
    <div class="tete">
      <h2>${esc(e.libelle)}</h2>
      <div class="fil"><button type="button" data-aller="residence/${e.r}">${esc(res.nom)}</button><span class="sep">›</span><span>Bât. ${bat(e.b)}</span>${l ? `<span class="sep">›</span><button type="button" data-aller="logement/${l.id}">Logement ${numLogt(l.id)}</button><span>· ${etageLong(l.etage)}</span>` : '<span class="sep">›</span><span>parties communes</span>'}</div>
      <div class="etat"><span class="niveau" data-niveau="${e.niveau}"${x ? ' data-decide' : ''}>${x ? 'Décidé' : NIVEAU[e.niveau]}</span><span>indice <b>${e.score}</b> · rang ${nb(e.rang)} sur ${nb(S.d.equipements.length)}</span></div>
      ${x ? `<div class="decide"><div><b>${CHOIX[x.choix].fait}</b><br><span>le ${dateLongue(x.le)}${x.note ? ` · ${esc(x.note)}` : ''}</span></div><button type="button" data-annuler="${e.id}">Annuler</button></div>
             ${suivant(e) ? `<button class="plus" style="margin:8px 0 2px;width:100%" type="button" data-aller="equipement/${suivant(e).id}">Suivant : ${esc(suivant(e).libelle)} · ${lieu(suivant(e))}</button>` : ''}`
        : `<div class="decisions" role="group" aria-label="Décider">${Object.entries(CHOIX).map(([k, c]) => `<button type="button" data-decider="${k}" title="${c.aide} (touche ${c.touche.toUpperCase()})">${c.mot}<small>${c.aide}</small></button>`).join('')}</div>
           <input class="note" type="text" maxlength="300" placeholder="Note pour la décision (facultatif)" aria-label="Note pour la décision">`}
    </div>
    <div class="defile">
      ${e.raisons.length ? `<section class="bloc"><h3>Pourquoi</h3><ul class="raisons">${e.raisons.map((r) => `<li><span class="poids" aria-hidden="true"><i style="width:${Math.max(8, (r.poids / max) * 100)}%"></i></span><span>${esc(r.texte)}</span></li>`).join('')}</ul></section>` : ''}
      <section class="bloc"><h3>Faits</h3><dl class="faits">
        <dt>Posé le</dt><dd>${dateLongue(f.datePose || brut.datePose)}${brut.origineDatePose ? `<br><small style="color:var(--encre-3)">${esc(brut.origineDatePose)}</small>` : ''}</dd>
        ${f.ageAns != null ? `<dt>Âge</dt><dd>${nb(f.ageAns)} ans · durée de vie prévue ${nb(f.dureeVieAns)} ans</dd>` : ''}
        <dt>Dépannages</dt><dd>${pl(f.depannages12m || 0, 'en 12 mois', 'en 12 mois')}${f.arrets12m ? ` · dont ${pl(f.arrets12m, 'arrêt total', 'arrêts totaux')}` : ''}${f.dernierDepannage ? `<br><small style="color:var(--encre-3)">dernier le ${dateLongue(f.dernierDepannage)}</small>` : ''}</dd>
        ${f.visitesPrevues ? `<dt>Visites</dt><dd>${f.visitesManquees ? `${nb(f.visitesManquees)} manquée${f.visitesManquees > 1 ? 's' : ''} sur ${nb(f.visitesPrevues)}` : `${nb(f.visitesPrevues)} réalisée${f.visitesPrevues > 1 ? 's' : ''}, aucune manquée`}</dd>` : ''}
        <dt>Contrat</dt><dd>${e.contrat === 'Oui' ? 'Sous contrat d’entretien' : 'Hors contrat'}${e.prestataire ? ` · ${esc(e.prestataire)}` : ''}</dd>
        ${l ? `<dt>Logement</dt><dd>${esc(l.typo)} · ${nb(l.surface)} m² · ${esc(l.statut.toLowerCase())} · ${pl(l.d12, 'demande', 'demandes')} en 12 mois</dd>` : ''}
      </dl></section>
      <section class="bloc"><h3>Historique <span>${pl(histoire.length, 'événement', 'événements')}</span></h3>${listeHistoire(histoire, 12, 'equipement')}</section>
    </div>`;
}
// Les demandes du locataire qui touchent ce type d'équipement (chauffage, eau chaude) : les autres restent dans la fiche du logement.
function pertinente(dm, e) {
  const t = sansAccent(`${dm.motif} ${dm.objet} ${dm.texte}`);
  if (/chaudiere|pompe|chaufferie|convecteur|panneaux/.test(e.famille)) return /chauff|radiateur|chaudiere|froid|temperature|pompe|eau chaude|tiede/.test(t);
  if (/ballon|ecs/.test(e.famille)) return /eau chaude|tiede|ballon|chauffe.eau|cumulus/.test(t);
  if (/ascenseur/.test(e.famille)) return /ascenseur/.test(t);
  if (/vmc/.test(e.famille)) return /vmc|ventilation|condensation|humidite/.test(t);
  return false;
}
function suivant(e) {
  const liste = equipementsFiltres().filter((x) => !decide(x) && x.niveau === e.niveau && x.rang > e.rang).sort((a, b) => a.rang - b.rang);
  return liste[0] || null;
}
function melanger(interventions, demandes) {
  return [
    ...interventions.map((i) => ({ ...i, sorte: i.type === 'Remplacement' ? 'remplacement' : i.gravite === 'Arrêt total' ? 'arret' : i.type === 'Dépannage' ? 'depannage' : 'entretien' })),
    ...demandes.map((dm) => ({ ...dm, sorte: 'demande' })),
  ].sort((a, b) => b.date.localeCompare(a.date));
}
function listeHistoire(items, n, cle) {
  if (!items.length) return '<p class="vide" style="padding:0 0 12px">Aucun événement.</p>';
  const ouvert = S.histoireOuverte === cle;
  const vus = ouvert ? items : items.slice(0, n);
  return `<ol class="histoire">${vus.map((h) => {
    if (h.sorte === 'demande') return `<li data-sorte="demande"><span class="quand">${dateCourte(h.date)} · demande du locataire · ${esc((h.priorite || '').split(' - ')[0])}</span><span class="quoi">${esc(h.motif.charAt(0).toUpperCase() + h.motif.slice(1))}</span>${h.texte ? `<q>${esc(h.texte)}</q>` : ''}</li>`;
    const quoi = h.type === 'Entretien préventif' ? (h.resultat === 'Visite réalisée - RAS' ? 'Entretien · RAS' : h.resultat.startsWith('Logement absent') ? 'Entretien · logement absent' : `Entretien · ${h.resultat.toLowerCase()}`) : h.type === 'Remplacement' ? 'Remplacement' : `Dépannage${h.gravite ? ` · ${h.gravite.toLowerCase()}` : ''}`;
    const libelle = h.equipementLibelle ? `${esc(h.equipementLibelle)} · ` : '';
    return `<li data-sorte="${h.sorte}"><span class="quand">${dateCourte(h.date)} · ${libelle}${esc(h.prestataire || '')}</span><span class="quoi${h.sorte === 'arret' ? ' arret' : ''}">${esc(quoi)}</span>${h.symptome ? `<span class="detail"> — ${esc(h.symptome)}</span>` : ''}${h.commentaire && !/^Entretien annuel réalisé$/.test(h.commentaire) ? `<q>${esc(h.commentaire)}</q>` : ''}</li>`;
  }).join('')}</ol>${items.length > n && !ouvert ? `<button class="plus" style="margin:0 0 14px;width:100%" type="button" data-histoire="${cle}">Tout afficher · ${nb(items.length)}</button>` : ''}`;
}

function ficheLogement({ logement: l, demandes, equipements, autres, interventions }) {
  const res = I.res.get(l.r);
  const libelles = new Map([...equipements.map((e) => [e.id, e.libelle]), ...autres.map((a) => [a.id, a.libelle])]);
  const histoire = melanger(interventions.filter((i) => i.type !== 'Entretien préventif' || i.resultat !== 'Visite réalisée - RAS').map((i) => ({ ...i, equipementLibelle: libelles.get(i.equipement) })), []);
  const motifs = new Map();
  demandes.slice(0, 50).forEach((dm) => motifs.set(dm.motif, (motifs.get(dm.motif) || 0) + 1));
  const eqs = equipements.map((e) => I.equip.get(e.id) || e).sort((a, b) => a.rang - b.rang);
  return `
    <div class="tete">
      <h2>Logement ${numLogt(l.id)}</h2>
      <div class="fil"><button type="button" data-aller="residence/${l.r}">${esc(res.nom)}</button><span class="sep">›</span><span>Bât. ${bat(l.b)} · ${etageLong(l.etage)}</span></div>
      <div class="etat"><span>${esc(l.typo)} · ${nb(l.surface)} m² · ${esc(l.statut.toLowerCase())}</span><span>${etiquette(l.dpe)} ${nb(l.conso)} kWh/m²/an</span>${auDela(l.dpe) ? `<span class="alerte-dpe">Alerte DPE ≥ ${S.seuil}</span>` : ''}</div>
      <div class="chiffres"><div class="c-visiter"><b>${nb(l.d12)}</b><span>${l.d12 > 1 ? 'demandes' : 'demande'} en 12 mois</span></div><div><b>${nb(l.dTot)}</b><span>depuis 2019</span></div></div>
    </div>
    <div class="defile">
      <section class="bloc"><h3>Équipements</h3><ul class="equip">
        ${eqs.map((e) => `<li data-aller="equipement/${e.id}" data-niveau="${decide(e) ? 'decide' : e.niveau}"${decide(e) ? ' data-decide' : ''}><span class="rang">${e.rang}</span><span>${esc(e.libelle)}</span><small>${decide(e) ? CHOIX[S.decisions[e.id].choix].fait : NIVEAU[e.niveau]}${e.raisons[0] ? ` · ${esc(e.raisons[0].texte)}` : ''}</small><span class="ligne-indice">indice <b>${e.score}</b></span></li>`).join('')}
        ${autres.map((a) => `<li class="inerte"><span class="rang" style="background:none;box-shadow:none">—</span><span>${esc(a.libelle)}</span><small>posé le ${dateCourte(a.datePose)} · hors calcul de risque</small></li>`).join('')}
      </ul></section>
      <section class="bloc"><h3>Demandes du locataire <span>${pl(demandes.length, 'demande', 'demandes')}</span></h3>${listeHistoire(demandes.map((dm) => ({ ...dm, sorte: 'demande' })), 8, 'demandes')}</section>
      <section class="bloc"><h3>Interventions <span>hors entretiens sans suite</span></h3>${listeHistoire(histoire, 10, 'interventions')}</section>
    </div>`;
}

function ficheResidence(r) {
  const eqs = S.d.equipements.filter((e) => e.r === r.id);
  const c = comptes(eqs);
  const logts = S.d.logements.filter((l) => l.r === r.id);
  const ops = (I.plan.get(r.id) || []).slice().sort((a, b) => a.annee - b.annee || a.rang - b.rang);
  const bats = S.d.batiments.filter((b) => b.r === r.id);
  const d12 = logts.reduce((s, l) => s + l.d12, 0);
  const auDelaListe = logts.filter((l) => auDela(l.dpe)).sort((a, b) => b.conso - a.conso);
  const energie = S.lentille === 'energie';
  const aVisiter = eqs.filter((e) => e.niveau === 'visiter' && !decide(e)).sort((a, b) => a.rang - b.rang);
  const blocVisiter = aVisiter.length ? `<section class="bloc bloc-visiter"><h3>À visiter <span>${nb(aVisiter.length)}</span></h3><ol class="lignes">${aVisiter.map((e) => ligne(e, null)).join('')}</ol></section>` : '';
  const blocBats = `<section class="bloc"><h3>Bâtiments</h3><ul class="equip">${bats.map((b) => {
    const cb = comptes(eqs.filter((e) => e.b === b.id));
    return `<li class="inerte"><span class="lettre-res" style="width:44px;height:24px;font-size:14px;grid-row:1/3">${esc(bat(b.id))}</span><span>${pl(b.logements, 'logement', 'logements')} · ${pl(b.niveaux, 'niveau', 'niveaux')}${b.ascenseur === 'Oui' ? ' · ascenseur' : ''}</span><small>${cb.visiter ? `<b style="color:var(--brique-cuite)">${nb(cb.visiter)} à visiter</b> · ` : ''}${nb(cb.surveiller)} à surveiller${cb.decide ? ` · ${pl(cb.decide, 'décidé', 'décidés')}` : ''}</small></li>`;
  }).join('')}</ul></section>`;
  const blocOps = `<section class="bloc"><h3>Opérations envisagées <span>plan hypothétique</span></h3>${ops.length ? ops.map((o) => `<div class="op"><b>${esc(o.type)}</b><span>${o.annee} · ${euros(o.cout)}</span><small>${esc(o.perimetre)}${o.gain ? ` · −${nb(o.gain)} kWh/m²/an` : ''} · ${esc(o.origine)}</small></div>`).join('') : '<p class="vide" style="padding:0 0 12px">Aucune.</p>'}</section>`;
  const blocDpe = `<section class="bloc"><h3>Étiquettes DPE <span>${nb(r.conso)} kWh/m²/an en moyenne</span></h3>
      <div class="dpe-barre" style="height:16px">${repartition(logts)}</div>
      <div class="legende-dpe" style="margin-bottom:12px">${DPE.map((l) => { const k = logts.filter((x) => x.dpe === l).length; return `<span>${l} ${k}</span>`; }).join('')}</div>
      ${auDelaListe.length ? `<ul class="equip">${auDelaListe.slice(0, S.histoireOuverte === 'dpe' ? 999 : 8).map((l) => `<li data-aller="logement/${l.id}"><span class="rang" style="background:${COULEUR_DPE[l.dpe]};color:${TEXTE_DPE[l.dpe] || '#fff'};box-shadow:none">${l.dpe}</span><span>Logement ${numLogt(l.id)} · bât. ${bat(l.b)}</span><small>${esc(l.typo)} · ${nb(l.surface)} m² · ${etageLong(l.etage)}</small><span class="ligne-indice"><b>${nb(l.conso)}</b> kWh</span></li>`).join('')}</ul>
      ${auDelaListe.length > 8 && S.histoireOuverte !== 'dpe' ? `<button class="plus" style="margin:0 0 14px;width:100%" type="button" data-histoire="dpe">Tout afficher · ${nb(auDelaListe.length)}</button>` : ''}` : ''}
    </section>`;
  return `
    <div class="tete">
      <h2>${esc(r.nom)}</h2>
      <div class="fil"><span>${r.annee} · ${pl(r.logements, 'logement', 'logements')} · ${pl(r.batiments, 'bâtiment', 'bâtiments')}${r.ascenseur === 'Oui' ? ' · ascenseurs' : ''}</span></div>
      <div class="fil" style="color:var(--encre-3);margin-top:2px"><span>${esc(r.chauffage)} · ${etiquette(r.dpe)} majoritaire</span></div>
      ${energie
        ? `<div class="chiffres"><div class="c-energie"><b>${nb(auDelaListe.length)}</b><span>${auDelaListe.length > 1 ? 'logements' : 'logement'} ${motsSeuil()}</span></div><div><b>${nb(ops.filter((o) => o.gain > 0).length)}</b><span>opérations à gain énergétique</span></div></div>`
        : `<div class="chiffres"><div class="c-visiter"><b>${nb(c.visiter)}</b><span>à visiter</span></div><div class="c-surveiller"><b>${nb(c.surveiller)}</b><span>à surveiller</span></div><div><b>${nb(c.decide)}</b><span>${c.decide > 1 ? 'décidés' : 'décidé'}</span></div><div><b>${nb(d12)}</b><span>${d12 > 1 ? 'demandes' : 'demande'} en 12 mois</span></div></div>`}
    </div>
    <div class="defile">${energie ? blocDpe + blocOps + blocBats : blocVisiter + blocBats + blocDpe + blocOps}</div>`;
}

// ── Le territoire : ce qui est raccordé, ce qui reste à raccorder ──
function majTerritoire() {
  const el = $('#territoire');
  const montre = !telephone() && (S.echelle === 'france' || S.echelle === 'sudouest') && !S.sel && S.d;
  el.classList.toggle('cache', !montre);
  document.body.classList.toggle('sans-territoire', !montre);
  if (!S.d || el.dataset.rempli) return;
  el.dataset.rempli = '1';
  const raccordes = S.d.logements.length;
  const PARC = 6300;
  const briques = Math.round(PARC / 100);
  const posees = Math.round(raccordes / 100);
  const parRang = 21;
  const rangs = Math.ceil(briques / parRang);
  let html = '';
  for (let r = 0; r < rangs; r++) {
    const debut = (rangs - 1 - r) * parRang;
    html += `<div class="mur" style="${r % 2 ? 'margin-left:2.4%;margin-right:-2.4%' : ''}">${Array.from({ length: parRang }, (_, i) => `<i class="${debut + i < posees ? 'pose' : ''}"></i>`).join('')}</div>`;
  }
  el.innerHTML = `
    <h3>Parc In'li Sud-Ouest <span>${nb(raccordes)} / ≈ ${nb(PARC)} logements</span></h3>
    <div aria-hidden="true" style="margin-bottom:10px">${html}</div>
    <ul class="dpts">
      <li class="raccorde"><b>Haute-Garonne · 31</b><span>${pl(S.d.residences.length, 'résidence', 'résidences')} · ${nb(raccordes)} logements</span></li>
      ${[['Gironde', 33], ['Hérault', 34], ['Landes', 40], ['Pyrénées-Atlantiques', 64]].map(([n, c]) => `<li><b>${n} · ${c}</b><a href="#/donnees">à raccorder</a></li>`).join('')}
    </ul>`;
}

// ── Les pages à part ────────────────────────────────────────────────
async function rendrePage() {
  const el = $('#page');
  if (!S.page) { el.hidden = true; return; }
  el.hidden = false;
  const corps = $('.page-corps', el);
  corps.innerHTML = `<button class="fermer" type="button" data-fermer aria-label="Fermer">${ICONE_X}</button>` + (S.page === 'methode' ? await pageMethode() : pageDonnees());
  corps.focus();
}

const fenetrePassee = () => Date.now() > Date.parse(`${+S.d.releve.slice(0, 4) + 1}-10-01`);
async function pageMethode() {
  let v = null;
  try { v = await api('/api/validation'); } catch { v = null; }
  const sv = S.d.seuils || {};
  const pct = (x) => `${nb(Math.round(x * 1000) / 10)} %`;
  const val = v && !v.erreur && v.auc ? `
    <p>Pour vérifier la méthode, on la fait tourner comme si l'on était le ${dateLongue(v.dateTest)}, sans rien savoir de la suite, puis on compare son classement aux arrêts totaux réellement survenus du ${dateLongue(`${+v.dateTest.slice(0, 4) + 1}-01-01`)} au ${dateLongue(`${+v.dateTest.slice(0, 4) + 1}-09-30`)} : ${pl(v.pannes, 'équipement', 'équipements')} sur ${nb(v.equipements)} en ont eu un.</p>
    <table><thead><tr><th></th><th>Foraine</th><th>Âge seul</th></tr></thead><tbody>
      ${(v.top || []).map((t, i) => `<tr><td>Arrêts totaux parmi les ${nb(t.n)} premiers${i === 2 ? ' (le niveau « à visiter » de ce jour-là)' : ''}</td><td class="n">${nb(t.methode)}</td><td class="n">${nb(t.ageSeul)}</td></tr>`).join('')}
      <tr><td>Probabilité qu'un équipement tombé en panne soit classé devant un équipement resté sain (AUC)</td><td class="n">${pct(v.auc.methode)}</td><td class="n">${pct(v.auc.ageSeul)}</td></tr>
    </tbody></table>
    <p>« Âge seul » classe les équipements par leur âge rapporté à leur durée de vie de référence : c'est la méthode de comparaison du défi.</p>` : '<p>La validation n’a pas pu être calculée.</p>';
  return `
    <h1 id="page-titre">Méthode</h1>
    <p class="chapeau">L'indice classe les équipements selon le risque d'un arrêt total dans les neuf mois qui suivent le dernier relevé. Il ne décide de rien : il range, et chaque rang vient avec ses raisons.</p>
    ${fenetrePassee() ? `<p class="alerte-page">La fenêtre de ce calcul, du 1<sup>er</sup> janvier au 30 septembre ${+S.d.releve.slice(0, 4) + 1}, est passée. Importer les trimestres suivants (page Données) remet les indices à jour.</p>` : ''}
    <h2>Ce que le calcul regarde</h2>
    <ul>
      <li>l'âge de l'équipement rapporté à sa durée de vie de référence ;</li>
      <li>les dépannages des douze derniers mois et des trois derniers, et les arrêts totaux ;</li>
      <li>les commentaires de fin de vie notés par les techniciens (« usure avancée », « pièce de rechange difficile à obtenir »…) et les anomalies relevées en visite, depuis la dernière pose ;</li>
      <li>les visites d'entretien manquées parce que le logement était absent ;</li>
      <li>les demandes du locataire qui touchent cet équipement (eau tiède, pas de chauffage…) ;</li>
      <li>la surface du logement, et un remplacement déjà demandé par un technicien mais pas encore posé.</li>
    </ul>
    <p>Chaque critère pèse d'un poids appris sur les années passées : pour chaque 31 décembre de 2020 à 2024, on regarde quels équipements ont eu un arrêt total dans les neuf mois suivants (régression logistique). Les raisons affichées sont les critères qui pèsent le plus pour cet équipement, avec les faits datés qui les fondent. L'indice va de 0 à 100\u00A0; ce n'est pas un pourcentage de chances, il sert à ranger.</p>
    <h2>Ce qu'il a donné sur 2025</h2>
    ${val}
    <h2>Les niveaux</h2>
    <p><b>À visiter</b> : indice de ${nb(sv.visiter)} ou plus. <b>À surveiller</b> : de ${nb(sv.surveiller)} à ${nb(sv.visiter - 1)}. En dessous, rien n'est signalé. Les deux seuils se règlent dans <code>risque/risque.mjs</code>.</p>
    <h2>Les données</h2>
    <p>Le jeu de données fictif du défi BâtIA : 8 résidences de la métropole toulousaine, 1 100 logements, ${nb(S.d.equipements.length)} équipements suivis, leurs interventions depuis 2018 et les demandes des locataires depuis février 2019, jusqu'au ${dateLongue(S.d.releve)}. Les positions des résidences sur la carte sont fictives : des secteurs, sans adresse. Le plan d'investissement est hypothétique.</p>
    <p>Tout est calculé sur cette machine ; aucune donnée n'est envoyée à un service en ligne. Les décisions sont enregistrées sur cette machine, dans <code>etat/decisions.json</code>.</p>
    <h2>Les limites</h2>
    <p>Les données suivent des règles de fabrication connues ; une méthode les retrouve en partie. La mesure ci-dessus vaut pour ces données fictives : sur les données réelles d'In'li, elle serait à refaire avant toute confiance. Le calcul est isolé dans un module remplaçable (<code>risque/risque.mjs</code>) qui rend, pour chaque équipement, un indice et ses raisons.</p>`;
}

function pageDonnees() {
  const d = S.d;
  const nbDec = Object.keys(S.decisions).length;
  return `
    <h1 id="page-titre">Données</h1>
    <p class="chapeau">Relevé au ${dateLongue(d.releve)}${ageReleve(d.releve) ? `, il y a ${ageReleve(d.releve)}` : ''}${d.imports?.length ? ` · ${pl(d.imports.length, 'trimestre importé', 'trimestres importés')}` : ''}</p>
    <table><tbody>
      <tr><td>Résidences</td><td class="n">${nb(d.residences.length)}</td></tr>
      <tr><td>Logements</td><td class="n">${nb(d.logements.length)}</td></tr>
      <tr><td>Équipements suivis</td><td class="n">${nb(d.equipements.length)}</td></tr>
      <tr><td>Décisions prises</td><td class="n">${nb(nbDec)}</td></tr>
    </tbody></table>
    <h2>Importer un trimestre</h2>
    <p>Interventions ou demandes du trimestre, au format CSV des fichiers actuels (mêmes colonnes que <code>06_interventions</code> ou <code>05_demandes_locataires</code>). Les indices sont recalculés.</p>
    <div class="actions"><label class="bouton plein"><input type="file" accept=".csv,text/csv" data-importer hidden>Choisir un fichier CSV</label></div>
    <p class="retour-import" id="retour-import" role="status"></p>
    <h2>Exporter</h2>
    <div class="actions">
      <a class="bouton" href="/api/export/decisions.csv" download>Décisions · ${nb(nbDec)}</a>
      <a class="bouton" href="/api/export/file.csv" download>File à visiter et à surveiller</a>
      <a class="bouton" href="/api/export/scores.csv" download>Indices au format du défi</a>
    </div>
    <h2>Raccorder un département</h2>
    <p>Gironde, Hérault, Landes et Pyrénées-Atlantiques se raccordent avec les mêmes fichiers : résidences, bâtiments, logements, équipements, interventions, demandes. Chaque résidence reçoit une position de secteur sur la carte.</p>`;
}

// ── Navigation : l'adresse dit ce qui est ouvert ─────────────────────
function lireAdresse() {
  const h = decodeURIComponent(location.hash.replace(/^#\/?/, ''));
  const [type, id] = h.split('/');
  S.page = type === 'methode' || type === 'donnees' ? type : null;
  if (S.page) return;
  if (['equipement', 'logement', 'residence'].includes(type) && id) S.sel = { type, id };
  else S.sel = null;
}
function aller(chemin, { remplacer = false } = {}) {
  const h = `#/${chemin}`;
  if (location.hash === h) return appliquer();
  if (remplacer) history.replaceState(null, '', h); else history.pushState(null, '', h);
  appliquer();
}
let dernierSel = null;
async function appliquer() {
  const avant = S.page;
  lireAdresse();
  if (S.page) { await rendrePage(); return; }
  if (avant) $('#page').hidden = true;
  const sel = S.sel ? `${S.sel.type}/${S.sel.id}` : null;
  if (S.sel?.type === 'residence') S.residence = S.sel.id;
  // un équipement ouvert d'ailleurs (recherche, fiche logement) : la file se règle pour le montrer
  if (S.sel?.type === 'equipement' && sel !== dernierSel) {
    const e = I.equip.get(S.sel.id);
    if (e) {
      const onglet = decide(e) ? 'decide' : e.niveau !== 'calme' ? e.niveau : null;
      if (onglet && onglet !== S.onglet && !(S.onglet === 'decide' && decide(e))) { S.onglet = onglet; S.limite = 50; }
      if (S.residence && S.residence !== e.r) S.residence = null;
      if (S.famille && S.famille !== e.famille) S.famille = '';
      const pos = equipementsFiltres().filter((x) => (S.onglet === 'decide' ? decide(x) : !decide(x) && x.niveau === S.onglet)).findIndex((x) => x.id === e.id);
      if (pos >= S.limite) S.limite = Math.ceil((pos + 1) / 50) * 50;
    }
  }
  if (sel !== dernierSel) S.histoireOuverte = null;
  rendreFile();
  await rendreFiche();
  if (telephone() && S.sel && S.feuille === 'basse') poserFeuille('mi');
  if (sel !== dernierSel && carte) {
    const rid = S.sel ? (S.sel.type === 'residence' ? S.sel.id : S.sel.type === 'logement' ? I.logt.get(S.sel.id)?.r : I.equip.get(S.sel.id)?.r) : S.residence;
    carte.choisir(rid || null);
    if (S.sel && rid) setTimeout(() => carte.allerVers(rid, { zoom: S.sel.type === 'residence' ? 12.5 : 13.3 }), 30);
  }
  dernierSel = sel;
  const actif = $('.ligne[aria-current="true"], .res-energie li[aria-current="true"]');
  if (actif) actif.scrollIntoView({ block: 'nearest' });
}

// ── Décider ─────────────────────────────────────────────────────────
async function decider(id, choix) {
  const note = $('#fiche .note')?.value || '';
  try {
    const r = await api('/api/decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, choix, note }) });
    S.decisions = r.decisions;
  } catch (err) { annoncer(err.message); return; }
  const e = I.equip.get(id);
  annoncer(`${CHOIX[choix].fait} · ${e.libelle}, ${lieu(e)}`, { annuler: id });
  S.garderDefilement = true;
  rendreFile(); await rendreFiche(); majCarte();
}
async function annuler(id) {
  try { S.decisions = (await api(`/api/decision/${encodeURIComponent(id)}`, { method: 'DELETE' })).decisions; } catch (err) { annoncer(err.message); return; }
  annoncer('Décision annulée');
  S.garderDefilement = true;
  rendreFile(); await rendreFiche(); majCarte();
}
let minuterie = null;
function annoncer(texte, { annuler: id } = {}) {
  const el = $('#annonce');
  el.innerHTML = `<span>${texte}</span>${id ? `<button type="button" data-annuler="${id}">Annuler</button>` : ''}`;
  el.classList.add('visible');
  clearTimeout(minuterie);
  minuterie = setTimeout(() => el.classList.remove('visible'), id ? 6000 : 2600);
}

// ── Recherche ───────────────────────────────────────────────────────
let index = [];
function indexer() {
  index = [
    ...S.d.residences.map((r) => ({ type: 'Résidence', titre: r.nom, sous: `${pl(r.logements, 'logement', 'logements')}`, cle: sansAccent(`${r.nom} ${r.lettre} ${r.id}`), aller: `residence/${r.id}`, ordre: 0 })),
    ...S.d.logements.map((l) => ({ type: 'Logement', titre: `Logement ${numLogt(l.id)} · bât. ${bat(l.b)}`, sous: `${I.res.get(l.r).nom} · ${l.typo}`, cle: sansAccent(`${l.id} ${l.id.replace('LGT-', '')} ${bat(l.b)} ${numLogt(l.id)} logement`), aller: `logement/${l.id}`, ordre: 1 })),
    ...S.d.equipements.map((e) => ({ type: 'Équipement', titre: e.libelle, sous: lieu(e).replace(/<[^>]+>/g, ''), cle: sansAccent(`${e.id} ${e.libelle} ${lieu(e)}`), aller: `equipement/${e.id}`, ordre: 2, rang: e.rang })),
  ];
}
function chercher(q) {
  const mots = sansAccent(q).replace(/[·,]/g, ' ').split(/\s+/).filter(Boolean);
  if (!mots.length) return [];
  return index.filter((x) => mots.every((m) => x.cle.includes(m))).sort((a, b) => a.ordre - b.ordre || (a.rang || 0) - (b.rang || 0)).slice(0, 9);
}
function majSuggestions() {
  const input = $('#recherche');
  const ul = $('#suggestions');
  const res = chercher(input.value);
  ul.hidden = !res.length && !input.value;
  input.setAttribute('aria-expanded', String(!ul.hidden));
  ul.innerHTML = res.length ? res.map((x, i) => `<li role="option" data-aller="${x.aller}" aria-selected="${i === 0}"><span class="sug-type">${x.type}</span><span>${esc(x.titre)}</span><span class="sug-sous">${esc(x.sous)}</span></li>`).join('') : input.value ? '<li aria-disabled="true"><span class="sug-type">Aucun</span><span>Pas de résultat</span></li>' : '';
}

// ── La feuille du téléphone ─────────────────────────────────────────
function hauteurFeuille() {
  const H = innerHeight;
  return { basse: Math.min(210, H * 0.32), mi: H * 0.5, haute: H - 74 }[S.feuille] || H * 0.5;
}
function poserFeuille(etat) {
  S.feuille = etat;
  document.body.style.setProperty('--feuille', `${hauteurFeuille()}px`);
}
function brancherFeuille() {
  let depart = null, h0 = 0, parPoignee = false;
  // on tire la feuille par sa poignée ou par son en-tête (hors boutons et liens)
  document.addEventListener('pointerdown', (ev) => {
    if (!telephone()) return;
    const p = ev.target.closest('.poignee');
    const tete = !p && ev.target.closest('.panneau .tete');
    if (!p && (!tete || ev.target.closest('button, a, select, input, [data-aller]'))) return;
    depart = ev.clientY; h0 = hauteurFeuille(); parPoignee = !!p;
    document.body.classList.add('glisse');
    (p || tete).setPointerCapture(ev.pointerId);
  });
  document.addEventListener('pointercancel', () => { if (depart == null) return; depart = null; document.body.classList.remove('glisse'); poserFeuille(S.feuille); });
  document.addEventListener('pointermove', (ev) => {
    if (depart == null) return;
    const h = Math.max(90, Math.min(innerHeight - 60, h0 + (depart - ev.clientY)));
    document.body.style.setProperty('--feuille', `${h}px`);
  });
  document.addEventListener('pointerup', (ev) => {
    if (depart == null) return;
    const dy = depart - ev.clientY;
    depart = null;
    document.body.classList.remove('glisse');
    const ordre = ['basse', 'mi', 'haute'];
    const i = ordre.indexOf(S.feuille);
    if (Math.abs(dy) < 8) poserFeuille(parPoignee ? ordre[(i + 1) % 3 === 0 ? 0 : i + 1] : S.feuille);
    else poserFeuille(ordre[Math.max(0, Math.min(2, i + (dy > 0 ? 1 : -1) * (Math.abs(dy) > innerHeight * 0.28 ? 2 : 1)))]);
  });
}

// ── Les gestes ──────────────────────────────────────────────────────
let calme = 0;
function brancher() {
  document.addEventListener('click', async (ev) => {
    const t = ev.target;
    const lien = t.closest('[data-aller]');
    if (lien && !lien.matches('[aria-disabled]')) { ev.preventDefault(); $('#recherche').value = ''; $('#suggestions').hidden = true; document.body.classList.remove('cherche'); return aller(lien.dataset.aller); }
    const ligneEl = t.closest('.ligne');
    if (ligneEl) return aller(`equipement/${ligneEl.dataset.id}`);
    const resEl = t.closest('.res-energie li');
    if (resEl) return aller(`residence/${resEl.dataset.res}`);
    const onglet = t.closest('[data-onglet]');
    if (onglet) { S.onglet = onglet.dataset.onglet; S.limite = 50; rendreFile(); $('#file .defile').scrollTop = 0; return; }
    const lentille = t.closest('[data-lentille]');
    if (lentille) return changerLentille(lentille.dataset.lentille);
    const seuil = t.closest('[data-seuil]');
    if (seuil) { S.seuil = seuil.dataset.seuil; localStorage.setItem('foraine.seuil', S.seuil); rendreFile(); majCarte(); if (S.sel) { S.garderDefilement = true; await rendreFiche(); } return; }
    if (t.closest('[data-retirer="residence"]')) { S.residence = null; if (S.sel?.type === 'residence') return aller(''); carte.choisir(S.sel ? (I.equip.get(S.sel.id)?.r || I.logt.get(S.sel.id)?.r || null) : null); rendreFile(); return; }
    if (t.closest('[data-plus]')) { S.limite += 50; const y = $('#file .defile').scrollTop; rendreFile(); $('#file .defile').scrollTop = y; return; }
    if (t.closest('[data-fermer-fiche]')) return fermerFiche();
    if (t.closest('[data-fermer]')) return fermerPage();
    const dec = t.closest('[data-decider]');
    const ann = t.closest('[data-annuler]');
    // un double clic ne décide pas puis n'annule pas dans la foulée
    if ((dec || ann) && (ev.detail > 1 || Date.now() < calme)) return;
    if (dec || ann) calme = Date.now() + 600;
    if (dec && S.sel?.type === 'equipement') return decider(S.sel.id, dec.dataset.decider);
    if (ann) { $('#annonce').classList.remove('visible'); return annuler(ann.dataset.annuler); }
    const hist = t.closest('[data-histoire]');
    if (hist) { S.histoireOuverte = hist.dataset.histoire; S.garderDefilement = true; return rendreFiche(); }
    const ech = t.closest('[data-echelle]');
    if (ech) return carte?.allerA(ech.dataset.echelle);
    if (t.closest('.outils') && telephone() && !document.body.classList.contains('cherche')) { document.body.classList.add('cherche'); $('#recherche').focus(); return; }
  });
  document.addEventListener('change', async (ev) => {
    if (ev.target.matches('.filtre-famille')) { S.famille = ev.target.value; S.limite = 50; rendreFile(); return; }
    if (ev.target.matches('[data-importer]')) return importer(ev.target.files[0]);
  });
  // survoler une ligne fait battre la brique de sa résidence
  let survol = null;
  document.addEventListener('pointerover', (ev) => {
    const el = ev.target.closest('.ligne, .res-energie li, .equip li[data-aller]');
    const rid = el ? (el.dataset.id ? I.equip.get(el.dataset.id)?.r : el.dataset.res || null) : null;
    if (rid === survol) return;
    survol = rid;
    carte?.signaler(rid);
  });
  const input = $('#recherche');
  input.addEventListener('input', majSuggestions);
  input.addEventListener('focus', majSuggestions);
  input.addEventListener('blur', () => setTimeout(() => { $('#suggestions').hidden = true; input.setAttribute('aria-expanded', 'false'); if (!input.value) document.body.classList.remove('cherche'); }, 160));
  input.addEventListener('keydown', (ev) => {
    const items = $$('#suggestions li[data-aller]');
    const i = items.findIndex((x) => x.getAttribute('aria-selected') === 'true');
    if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
      ev.preventDefault();
      const j = Math.max(0, Math.min(items.length - 1, i + (ev.key === 'ArrowDown' ? 1 : -1)));
      items.forEach((x, k) => x.setAttribute('aria-selected', String(k === j)));
    } else if (ev.key === 'Enter' && items[Math.max(0, i)]) {
      ev.preventDefault();
      const cible = items[Math.max(0, i)].dataset.aller;
      input.value = ''; input.blur(); document.body.classList.remove('cherche');
      aller(cible);
    } else if (ev.key === 'Escape') { input.value = ''; input.blur(); }
  });
  document.addEventListener('keydown', (ev) => {
    if (ev.target.matches('input, select, textarea')) return;
    if (ev.key === '/') { ev.preventDefault(); input.focus(); return; }
    if (ev.key === 'Escape') { if (S.page) fermerPage(); else if (S.sel) fermerFiche(); return; }
    if (ev.key === 'Enter' && ev.target.matches('.ligne, .res-energie li')) { ev.target.click(); return; }
    if (S.lentille === 'pannes' && ['ArrowDown', 'ArrowUp', 'j', 'k'].includes(ev.key)) {
      const lignes = $$('#file .ligne');
      if (!lignes.length) return;
      ev.preventDefault();
      const i = lignes.findIndex((x) => x.getAttribute('aria-current') === 'true');
      const j = i < 0 ? 0 : Math.max(0, Math.min(lignes.length - 1, i + (ev.key === 'ArrowDown' || ev.key === 'j' ? 1 : -1)));
      aller(`equipement/${lignes[j].dataset.id}`, { remplacer: S.sel?.type === 'equipement' });
      return;
    }
    if (S.sel?.type === 'equipement' && !S.decisions[S.sel.id]) {
      const k = Object.entries(CHOIX).find(([, c]) => c.touche === ev.key.toLowerCase());
      if (k) decider(S.sel.id, k[0]);
    }
  });
  addEventListener('popstate', appliquer);
  addEventListener('resize', () => { if (telephone()) poserFeuille(S.feuille); majTerritoire(); });
}
function fermerFiche() {
  if (S.sel?.type === 'residence') S.residence = S.sel.id;
  aller('');
  carte?.choisir(S.residence);
}
function fermerPage() {
  S.page = null; $('#page').hidden = true;
  history.pushState(null, '', S.sel ? `#/${S.sel.type}/${S.sel.id}` : '#/');
}
async function changerLentille(l) {
  if (S.lentille === l) return;
  S.lentille = l;
  document.body.classList.toggle('energie', l === 'energie');
  $$('[data-lentille]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.lentille === l)));
  if (S.sel?.type === 'equipement' && l === 'energie') {
    const e = I.equip.get(S.sel.id);
    aller(e?.l ? `logement/${e.l}` : `residence/${e.r}`, { remplacer: true });
  } else { rendreFile(); await rendreFiche(); }
  majCarte();
  setTimeout(() => { const d = $('#file .defile'); if (d) d.scrollTop = 0; }, 120);
}
async function importer(fichier) {
  if (!fichier) return;
  const retour = $('#retour-import');
  retour.textContent = 'Import en cours…';
  try {
    const r = await api('/api/import', { method: 'POST', headers: { 'Content-Type': 'text/csv', 'X-Nom-Fichier': fichier.name }, body: await fichier.text() });
    await charger(); indexer(); rendreFile(); majCarte(); await rendreFiche();
    retour.textContent = `${pl(r.lignes, 'ligne importée', 'lignes importées')} (${r.table}) · relevé au ${dateLongue(r.releve)}`;
  } catch (err) { retour.textContent = err.message; }
}

// ── Démarrage ───────────────────────────────────────────────────────
async function demarrer() {
  await charger();
  indexer();
  brancher();
  brancherFeuille();
  if (telephone()) poserFeuille('basse');
  lireAdresse();
  const lienDirect = !!S.sel || !!S.page;
  rendreFile();
  majTerritoire();
  const el = $('#carte');
  el.addEventListener('carte:residence', (e) => aller(`residence/${e.detail.id}`));
  el.addEventListener('carte:echelle', (e) => {
    S.echelle = e.detail.echelle;
    $$('[data-echelle]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.echelle === S.echelle)));
    majTerritoire();
  });
  el.addEventListener('carte:survol', (e) => {
    $$('.ligne').forEach((x) => x.classList.toggle('meme-residence', !!e.detail.id && I.equip.get(x.dataset.id)?.r === e.detail.id));
  });
  carte = await creerCarte(el, { residences: residencesCarte(), echelle: S.sel ? 'toulouse' : 'sudouest', depuis: lienDirect || reduit ? null : 'france', molette: true, zoneOccupee });
  window.foraine = { carte, S };
  majCarte();
  S.echelle = carte.echelle;
  $$('[data-echelle]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.echelle === S.echelle)));
  // la carte se pose d'abord ; ce qu'il faut décider arrive juste après
  setTimeout(() => {
    $('#file').classList.add('arrive');
    document.body.classList.add('pret');
    appliquer();
  }, lienDirect || reduit ? 0 : 1400);
}
demarrer().catch((err) => {
  console.error(err);
  document.body.insertAdjacentHTML('beforeend', `<div class="page"><article class="page-corps"><h1>Foraine ne démarre pas</h1><p>${esc(err.message)}</p></article></div>`);
});
