// Assise — interface. Une question par écran (voir UX.md).
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const nb = (n) => Number(n).toLocaleString('fr-FR');
const euros = (n) => `${nb(Math.round(n))} €`;
const pl = (n, un, plusieurs) => `${nb(n)} ${n > 1 ? plusieurs : un}`;
const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
const MOIS_C = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
const dateLongue = (iso) => { if (!iso) return ''; const [a, m, j] = iso.slice(0, 10).split('-').map(Number); return `${j === 1 ? '1ᵉʳ' : j} ${MOIS[m - 1]} ${a}`; };
const dateCourte = (iso) => { if (!iso) return ''; const [a, m, j] = iso.slice(0, 10).split('-').map(Number); return `${j === 1 ? '1ᵉʳ' : j} ${MOIS_C[m - 1]} ${a}`; };
// L'échéance se lit depuis aujourd'hui : une fois la date passée, on la rapporte au relevé des données.
const echeance = () => (new Date().toISOString().slice(0, 10) <= E.meta.finHorizon ? `d'ici le ${E.meta.finHorizonTexte}` : 'dans les neuf mois suivant le dernier relevé');
// Trimestres écoulés depuis celui des données : le geste qui suit est l'import.
const aImporter = () => { const q = (d) => d.getUTCFullYear() * 4 + Math.floor(d.getUTCMonth() / 3); return Math.max(0, q(new Date()) - q(new Date(E.meta.dateDonnees + 'T12:00:00Z')) - 1); };
const etageTexte = (n) => (n == null ? '' : n === 0 ? 'rez-de-chaussée' : n === 1 ? '1ᵉʳ étage' : `${n}ᵉ étage`);
const NIVEAUX = { prioritaire: 'Prioritaire', surveiller: 'À surveiller', calme: 'Sans alerte' };
const DECISIONS = { remplacer: 'Remplacer', diagnostiquer: 'Faire diagnostiquer', surveiller: 'Surveiller', ecarter: 'Écarter' };
const DECISIONS_PASSE = { remplacer: 'Remplacement décidé', diagnostiquer: 'Diagnostic demandé', surveiller: 'À revoir au prochain trimestre', ecarter: 'Écarté' };
const lirePref = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const ecrirePref = (k, v) => { try { localStorage.setItem(k, v); } catch { /* navigation privée */ } };

let E = null;          // état calculé par le serveur
let decisions = {};
const parId = {};      // index
const vue = { onglet: 'decider', residence: '', famille: '', seuilDpe: lirePref('assise.seuilDpe', 'E'), zoom: null, carteVue: false };

// ── Données ────────────────────────────────────────────────────────────────
async function charger() {
  const r = await fetch('/api/etat');
  E = await r.json();
  decisions = E.decisions || {};
  parId.res = Object.fromEntries(E.residences.map((x) => [x.id, x]));
  parId.bat = Object.fromEntries(E.batiments.map((x) => [x.id, x]));
  parId.lgt = Object.fromEntries(E.logements.map((x) => [x.id, x]));
  parId.eqp = Object.fromEntries(E.equipements.map((x) => [x.id, x]));
  parId.pre = Object.fromEntries(E.prestataires.map((x) => [x.id, x]));
}

const numLogement = (id) => id.replace(/^LGT-/, '');
const nomBat = (id) => id.replace(/^BAT-/, '');
function lieu(e, { court = false } = {}) {
  const r = `Résidence ${e.residence.slice(-1)}`;
  if (!e.logement) return `${r} · bâtiment ${nomBat(e.batiment)} · parties communes`;
  const l = parId.lgt[e.logement];
  return `${r} · bâtiment ${nomBat(e.batiment)} · logement ${e.logement.slice(-3)}${court || !l ? '' : ` · ${etageTexte(l.etage)}`}`;
}
const nomPrestataire = (id) => (parId.pre[id]?.nom || id || '').replace(' (fictif)', '');

// ── Rendu commun ───────────────────────────────────────────────────────────
const niveau = (n) => `<span class="niveau" data-niveau="${n}">${NIVEAUX[n]}</span>`;

function rangEquipement(e, { rang = true } = {}) {
  const d = decisions[e.id];
  const raisons = e.raisons.filter((r) => r.points > 0);
  // les faits (pannes, remplacement demandé, signalements) avant l'âge : c'est ce qui convainc
  const montrees = [...raisons.filter((r) => r.type !== 'usure'), ...raisons.filter((r) => r.type === 'usure')].slice(0, 2);
  const autres = raisons.length - montrees.length;
  return `<li><button class="assise" data-niveau="${e.niveau}" data-eqp="${e.id}" type="button">
    <span class="assise-rang" aria-hidden="true">${rang ? e.rang : ''}</span>
    <span class="assise-corps">
      <span class="assise-titre">${esc(e.libelle)}</span>
      <span class="assise-lieu">${esc(lieu(e))}</span>
      ${montrees.map((r, i) => `<span class="assise-raison${i ? ' seconde' : ''}">${esc(r.texte)}${i === montrees.length - 1 && autres > 0 ? ` <span class="plus">· et ${pl(autres, 'autre raison', 'autres raisons')}${raisons.some((x) => x.type === 'usure') && !montrees.some((x) => x.type === 'usure') ? ', dont l\'âge' : ''}</span>` : ''}</span>`).join('')}
    </span>
    <span class="assise-cote">
      ${niveau(e.niveau)}
      ${d ? `<span class="decision-etiquette">${esc(DECISIONS_PASSE[d.decision])}</span>` : `<span class="assise-score">indice <b>${e.score}</b></span>`}
    </span>
  </button></li>`;
}

function brancherRangs(racine) {
  $$('[data-eqp]', racine).forEach((b) => b.addEventListener('click', () => ouvrirEquipement(b.dataset.eqp)));
  $$('[data-lgt]', racine).forEach((b) => b.addEventListener('click', () => ouvrirLogement(b.dataset.lgt)));
}

function annoncer(texte) {
  const a = $('#annonce'); a.textContent = texte; a.classList.add('visible');
  clearTimeout(annoncer.t); annoncer.t = setTimeout(() => a.classList.remove('visible'), 2600);
}

// ── Vue 1 : À décider ──────────────────────────────────────────────────────
function vueDecider() {
  const filtre = (e) => (!vue.residence || e.residence === vue.residence) && (!vue.famille || e.famille === vue.famille);
  const prioritaires = E.equipements.filter((e) => e.niveau === 'prioritaire');
  const listes = {
    decider: prioritaires.filter((e) => !decisions[e.id]),
    surveiller: E.equipements.filter((e) => e.niveau === 'surveiller' && !decisions[e.id]),
    decides: E.equipements.filter((e) => decisions[e.id]),
  };
  const liste = listes[vue.onglet].filter(filtre);
  const nbDecidesPrio = prioritaires.length - listes.decider.length;
  const familles = [...new Map(E.equipements.filter((e) => e.niveau !== 'calme').map((e) => [e.famille, e.libelle])).entries()].sort((a, b) => a[1].localeCompare(b[1]));
  const m = E.meta;

  let chapeau;
  if (listes.decider.length === 0) chapeau = `Tous les équipements prioritaires ont reçu une décision. Les ${nb(listes.surveiller.length)} équipements à surveiller restent consultables.`;
  else if (nbDecidesPrio > 0) chapeau = `${nbDecidesPrio > 1 ? `${nb(nbDecidesPrio)} sont déjà tranchés` : 'Un est déjà tranché'}. ${listes.decider.length > 1 ? `Les ${nb(listes.decider.length)} autres attendent` : 'Le dernier attend'}, du plus urgent au moins urgent.`;
  else chapeau = `Du plus urgent au moins urgent, d'après tout l'historique jusqu'au ${m.dateDonneesTexte}. Ouvrez une ligne pour lire pourquoi, puis décidez.`;
  if (vue.residence && parId.res[vue.residence]) chapeau = `Liste limitée à la ${esc(parId.res[vue.residence].nom)} : ${nb(listes.decider.filter(filtre).length)} à décider, ${nb(listes.surveiller.filter(filtre).length)} à surveiller. « Toutes » rend la liste du parc entier.`;

  const onglet = (cle, libelle, n) => `<button type="button" role="tab" aria-selected="${vue.onglet === cle}" data-onglet="${cle}">${libelle} <span class="compte">${nb(n)}</span></button>`;

  let bilan = '';
  if (vue.onglet === 'decides') bilan = blocBilan(listes.decides);

  $('#contenu').innerHTML = `
    <p class="surtitre">À décider · métropole toulousaine · données au ${esc(m.dateDonneesTexte)}${aImporter() ? ` · <a class="lien" href="#/methode">${pl(aImporter(), 'trimestre à importer', 'trimestres à importer')}</a>` : ''}</p>
    <h1 class="phrase"><strong>${pl(prioritaires.length, 'équipement', 'équipements')}</strong> ${prioritaires.length > 1 ? 'risquent' : 'risque'} une panne bloquante ${esc(echeance())}.</h1>
    <p class="chapeau">${esc(chapeau)}</p>
    ${repartition(listes[vue.onglet])}
    <div class="barre">
      <div class="onglets" role="tablist" aria-label="Listes">
        ${onglet('decider', 'À décider', listes.decider.filter(filtre).length)}
        ${onglet('surveiller', 'À surveiller', listes.surveiller.filter(filtre).length)}
        ${onglet('decides', 'Décidés', listes.decides.filter(filtre).length)}
      </div>
      <div class="filtres">
        <label>Équipement
          <select id="f-famille"><option value="">Tous</option>${familles.map(([f, l]) => `<option value="${f}" ${vue.famille === f ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select>
        </label>
      </div>
    </div>
    ${bilan}
    ${liste.length ? `<ol class="assise-liste" aria-label="Équipements, du plus urgent au moins urgent">${liste.map((e) => rangEquipement(e)).join('')}</ol>`
      : `<p class="vide">${vue.onglet === 'decides' ? 'Aucune décision pour l\'instant. Ouvrez un équipement de la liste « À décider » pour trancher.' : (vue.residence || vue.famille) ? 'Rien dans cette liste pour ce filtre.' : 'Rien à décider ici.'}</p>`}
  `;
  $$('[data-onglet]').forEach((b) => b.addEventListener('click', () => { vue.onglet = b.dataset.onglet; vueDecider(); }));
  $$('[data-filtre-res]').forEach((b) => b.addEventListener('click', () => { vue.residence = b.dataset.filtreRes; vueDecider(); }));
  const choisie = $('.pastille-res[aria-pressed="true"]');
  if (choisie) { const rang = choisie.parentElement; rang.scrollLeft += choisie.getBoundingClientRect().left - rang.getBoundingClientRect().left - 70; }
  $('#f-famille').addEventListener('change', (ev) => { vue.famille = ev.target.value; vueDecider(); });
  brancherRangs($('#contenu'));
}

// Où se concentrent les équipements de la liste : de quoi grouper les passages par résidence.
function repartition(liste) {
  if (vue.onglet === 'decides' || liste.length < 2) return '';
  const compte = {};
  for (const e of liste) compte[e.residence] = (compte[e.residence] || 0) + 1;
  const tri = Object.entries(compte).sort((a, b) => b[1] - a[1]);
  return `<div class="repartition-res" role="group" aria-label="Filtrer par résidence"><span class="note">Par résidence :</span><button type="button" class="pastille-res" data-filtre-res="" aria-pressed="${!vue.residence}">Toutes <b>${liste.length}</b></button>${tri.map(([id, n]) => `<button type="button" class="pastille-res" data-filtre-res="${id}" aria-pressed="${vue.residence === id}">${esc(parId.res[id].nom)} <b>${n}</b></button>`).join('')}</div>`;
}

function blocBilan(decides) {
  if (!decides.length) return '';
  const compte = (k) => decides.filter((e) => decisions[e.id].decision === k);
  const rempl = compte('remplacer');
  const min = rempl.reduce((s, e) => s + (e.coutMin || 0), 0), max = rempl.reduce((s, e) => s + (e.coutMax || 0), 0);
  const morceaux = [];
  if (rempl.length) morceaux.push(`${pl(rempl.length, 'remplacement', 'remplacements')} (entre ${euros(min)} et ${euros(max)} TTC aux coûts de référence)`);
  if (compte('diagnostiquer').length) morceaux.push(pl(compte('diagnostiquer').length, 'diagnostic', 'diagnostics'));
  if (compte('surveiller').length) morceaux.push(`${nb(compte('surveiller').length)} à revoir au prochain trimestre`);
  if (compte('ecarter').length) morceaux.push(pl(compte('ecarter').length, 'écarté', 'écartés'));
  const parPresta = {};
  for (const e of decides) if (decisions[e.id].decision !== 'ecarter') parPresta[e.prestataire] = (parPresta[e.prestataire] || 0) + 1;
  return `<section class="bilan" aria-label="Bilan des décisions">
    <p>${esc(morceaux.join(', '))}.</p>
    <div class="actions">
      ${Object.entries(parPresta).map(([p, n]) => `<a class="bouton" href="/export/decisions.csv?prestataire=${encodeURIComponent(p)}" download>Liste pour ${esc(nomPrestataire(p))} · ${pl(n, 'équipement', 'équipements')} (CSV)</a>`).join('')}
      <a class="bouton secondaire" href="/export/decisions.csv" download>Toutes les décisions (CSV)</a>
    </div>
  </section>`;
}

// ── Fiche : panneau latéral / feuille du bas ───────────────────────────────
let ficheOuverte = false, dernierFocus = null, jetonFiche = 0;
function ouvrirFiche(html, niveauFiche) {
  const f = $('#fiche');
  if (!ficheOuverte) { dernierFocus = document.activeElement; history.pushState({ fiche: true }, ''); }
  f.dataset.niveau = niveauFiche || '';
  $('#zone-decision')?.remove();
  $('#fiche-corps').innerHTML = html;
  $('#fiche-corps').scrollTop = 0;
  f.hidden = false; $('#voile').hidden = false; ficheOuverte = true;
  document.body.style.overflow = 'hidden';
  setTimeout(() => $('#fiche-titre')?.focus(), 30);
}
function fermerFiche({ depuisHistorique = false } = {}) {
  if (!ficheOuverte) return;
  ficheOuverte = false;
  $('#zone-decision')?.remove();
  $('#fiche').hidden = true; $('#voile').hidden = true; document.body.style.overflow = '';
  dernierFocus?.focus?.();
  if (!depuisHistorique && history.state?.fiche) history.back();
}

async function ouvrirEquipement(id) {
  const e = parId.eqp[id];
  if (!e) return;
  ouvrirFiche(`<p class="chargement">…</p>`, e.niveau);
  const jeton = ++jetonFiche;
  const { interventions } = await (await fetch(`/api/equipement/${id}`)).json();
  if (jeton !== jetonFiche || !ficheOuverte) return;
  const raisons = e.raisons.filter((r) => r.points > 0);
  const precisions = e.raisons.filter((r) => r.points === 0);
  const maxPts = Math.max(...raisons.map((r) => r.points), 1);
  const d = decisions[id];
  const lgt = e.logement ? parId.lgt[e.logement] : null;
  const age = e.mesures.age;
  const hist = interventions.slice(0, 8);
  const suivant = prochainADecider(id);

  ouvrirFiche(`
    <p class="surtitre">Équipement · rang ${e.rang} sur ${nb(E.equipements.length)}</p>
    <h2 id="fiche-titre" tabindex="-1">${esc(e.libelle)}</h2>
    <p class="fiche-lieu">${esc(lieu(e))}${lgt ? ` · <button class="lien" type="button" data-lgt="${lgt.id}">ouvrir le logement</button>` : ''}</p>
    <div class="fiche-etat">${niveau(e.niveau)} <span class="score">indice de risque <b>${e.score}</b> sur 100 · panne bloquante ${esc(echeance())}</span></div>

    <h3>Pourquoi</h3>
    ${raisons.length ? `<ul class="raisons">${raisons.map((r) => `<li class="raison">
        <span class="raison-poids" aria-label="${r.points} points"><span class="raison-barre" style="width:${Math.max(4, (r.points / maxPts) * 34)}px"></span><span class="raison-points">${r.points} pts</span></span>
        <span class="raison-texte">${esc(r.texte)}${r.type === 'usure' && precisions.length ? precisions.map((p) => `<span class="raison-precision">${esc(p.texte)}</span>`).join('') : ''}</span>
      </li>`).join('')}</ul>
    <p class="note total-points">Total : ${raisons.reduce((s, r) => s + r.points, 0)} points${raisons.reduce((s, r) => s + r.points, 0) > 100 ? ', l\'indice s\'arrête à 100' : ''}. Chaque ingrédient est plafonné, <a class="lien" href="#/methode">voir la méthode</a>.</p>` : `<p class="note">Aucun signal particulier : équipement récent, sans dépannage ni remarque récente.</p>`}

    <h3>Repères</h3>
    <dl class="reperes">
      <div><dt>Posé le</dt><dd>${esc(dateLongue(e.mesures.pose))}</dd></div>
      <div><dt>Âge</dt><dd>${String(age).replace('.', ',')} ans · durée de vie ${e.mesures.vieRetenue < e.vieRef - 0.05 ? `retenue ${String(Math.round(e.mesures.vieRetenue)).replace('.', ',')} ans (${e.vieRef} prévus)` : `prévue ${e.vieRef} ans`}</dd></div>
      <div><dt>Entretien</dt><dd>${e.contrat ? 'Sous contrat' : 'Hors contrat'}</dd></div>
      <div><dt>Prestataire</dt><dd>${esc(nomPrestataire(e.prestataire))}</dd></div>
      ${e.coutMin ? `<div><dt>Remplacement (coût de référence)</dt><dd>${euros(e.coutMin)} à ${euros(e.coutMax)} TTC</dd></div>` : ''}
      <div><dt>Référence</dt><dd>${esc(e.id)}</dd></div>
    </dl>

    <h3>Historique · ${pl(interventions.length, 'intervention', 'interventions')}</h3>
    ${historique(hist)}
    ${interventions.length > hist.length ? `<p><button class="lien" type="button" id="tout-historique">Afficher les ${nb(interventions.length - hist.length)} plus anciennes</button></p>` : ''}
  `, e.niveau);
  // la zone de décision reste collée en bas de la fiche, à portée de pouce
  const zone = document.createElement('div');
  zone.className = 'decision'; zone.id = 'zone-decision';
  zone.innerHTML = blocDecision(e, d, suivant);
  $('#fiche').appendChild(zone);
  $('#tout-historique')?.addEventListener('click', (ev) => { ev.target.closest('p').outerHTML = historique(interventions.slice(8)); });
  brancherRangs($('#fiche-corps'));
  brancherDecision(e, zone);
}

function historique(liste) {
  if (!liste.length) return '<p class="note">Aucune intervention enregistrée.</p>';
  return `<ul class="historique">${liste.map((it) => {
    const grave = it.gravite === 'Arrêt total';
    const quoi = it.type === 'Dépannage' ? `Dépannage${it.gravite ? ` · ${it.gravite.toLowerCase()}` : ''}` : it.type === 'Entretien préventif' ? 'Visite d\'entretien' : it.type;
    const detail = [it.symptome, it.resultat].filter(Boolean).join(' — ');
    const cite = it.commentaire && !['Entretien annuel réalisé'].includes(it.commentaire) ? `<div class="h-cite">« ${esc(it.commentaire)} »</div>` : '';
    return `<li data-grave="${grave ? 1 : 0}"><span class="h-date">${esc(dateCourte(it.date))}</span><span><span class="h-quoi">${esc(quoi)}</span><div class="h-detail">${esc(detail)}</div>${cite}</span></li>`;
  }).join('')}</ul>`;
}

// Le suivant respecte les filtres en cours : une séance « Résidence D » reste dans la résidence D.
function prochainADecider(sauf) {
  // ouverte depuis la page d'une résidence, la séance reste dans cette résidence (sur place, on traite ce qu'on a devant soi)
  const surPlace = (location.hash.match(/^#\/residence\/([^/?#]+)/) || [])[1];
  const ok = (x) => (surPlace ? x.residence === surPlace : (!vue.residence || x.residence === vue.residence) && (!vue.famille || x.famille === vue.famille));
  const libre = (x, n) => x.niveau === n && !decisions[x.id] && x.id !== sauf && ok(x);
  return E.equipements.find((x) => libre(x, 'prioritaire')) || (surPlace && E.equipements.find((x) => libre(x, 'surveiller'))) || null;
}

function blocDecision(e, d, suivant) {
  const choix = d?.decision || '';
  return `
    <p class="decision-titre">Votre décision ${d ? `<span>${esc(DECISIONS_PASSE[d.decision])} le ${esc(dateLongue(d.date))}${d.auteur ? ` par ${esc(d.auteur)}` : ''}</span>` : '<span>rien n\'est déclenché sans vous</span>'}</p>
    <div class="choix" role="group" aria-label="Décision">
      ${Object.entries(DECISIONS).map(([k, l]) => `<button type="button" data-choix="${k}" aria-pressed="${choix === k}">${l}</button>`).join('')}
    </div>
    <div class="decision-suite" ${choix ? '' : 'data-replie'}>
      <textarea id="d-note" rows="1" placeholder="Note (facultatif) : pour qui, pour quand, pourquoi…" aria-label="Note de décision">${esc(d?.note || '')}</textarea>
      <input id="d-auteur" type="text" maxlength="12" placeholder="Vos initiales" aria-label="Vos initiales" value="${esc(lirePref('assise.auteur', ''))}">
      <button class="bouton" type="button" id="d-enregistrer" ${choix ? '' : 'disabled'}>Enregistrer</button>
    </div>
    <p class="decision-faite" id="d-suite">${d && d.decision !== 'ecarter' ? `<button class="lien" type="button" id="d-liste">Voir la liste pour ${esc(nomPrestataire(e.prestataire))}</button> · ` : ''}${d ? `<button class="lien" type="button" id="d-annuler">Annuler cette décision</button>` : ''}${suivant ? `${d ? ' · ' : ''}<button class="lien" type="button" id="d-suivant">Équipement suivant à décider →</button>` : ''}</p>
  `;
}

function brancherDecision(e, zone) {
  let choix = decisions[e.id]?.decision || '';
  const valider = $('#d-enregistrer', zone);
  $$('[data-choix]', zone).forEach((b) => b.addEventListener('click', () => {
    choix = b.dataset.choix;
    $$('[data-choix]', zone).forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    valider.disabled = false;
    $('.decision-suite', zone).removeAttribute('data-replie');
  }));
  valider.addEventListener('click', async () => {
    const auteur = $('#d-auteur', zone).value.trim();
    ecrirePref('assise.auteur', auteur);
    const r = await fetch('/api/decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ equipement: e.id, decision: choix, note: $('#d-note', zone).value, auteur }) });
    if (!r.ok) return annoncer('La décision n\'a pas pu être enregistrée.');
    decisions = (await r.json()).decisions;
    annoncer(`Décision enregistrée : ${DECISIONS[choix]}`);
    rafraichirVue();
    zone.innerHTML = blocDecision(e, decisions[e.id], prochainADecider(e.id));
    brancherDecision(e, zone);
  });
  $('#d-annuler', zone)?.addEventListener('click', async () => {
    const r = await fetch('/api/decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ equipement: e.id, decision: null }) });
    decisions = (await r.json()).decisions;
    annoncer('Décision annulée');
    rafraichirVue();
    zone.innerHTML = blocDecision(e, null, prochainADecider(e.id));
    brancherDecision(e, zone);
  });
  $('#d-suivant', zone)?.addEventListener('click', () => { const s = prochainADecider(e.id); if (s) ouvrirEquipement(s.id); });
  $('#d-liste', zone)?.addEventListener('click', () => { vue.onglet = 'decides'; fermerFiche(); if (location.hash === '#/' || location.hash === '') rafraichirVue(); else location.hash = '#/'; });
}

async function ouvrirLogement(id) {
  const l = parId.lgt[id];
  if (!l) return;
  ouvrirFiche('<p class="chargement">…</p>', l.niveau || 'calme');
  const jeton = ++jetonFiche;
  const { demandes, interventions, equipements } = await (await fetch(`/api/logement/${id}`)).json();
  if (jeton !== jetonFiche || !ficheOuverte) return;
  const res = parId.res[l.residence];
  const suivis = equipements.filter((e) => parId.eqp[e.id]).map((e) => parId.eqp[e.id]).sort((a, b) => b.score - a.score);
  const autres = equipements.filter((e) => !parId.eqp[e.id]);
  const fin = E.meta.dateDonnees;
  const unAn = `${Number(fin.slice(0, 4)) - 1}${fin.slice(4)}`;
  const d12 = demandes.filter((d) => d.date.slice(0, 10) > unAn);
  const annees = [];
  for (let a = 2019; a <= Number(fin.slice(0, 4)); a++) annees.push({ a, n: demandes.filter((d) => d.date.startsWith(String(a))).length });
  const maxA = Math.max(1, ...annees.map((x) => x.n));
  let phraseDemandes;
  if (!demandes.length) phraseDemandes = 'Aucune demande enregistrée depuis la mise en service de l\'outil de demandes (février 2019).';
  else phraseDemandes = `${pl(demandes.length, 'demande', 'demandes')} depuis février 2019, dont ${nb(d12.length)} ces douze derniers mois${d12.filter((d) => d.rouverte).length ? ` (${pl(d12.filter((d) => d.rouverte).length, 'rouverte', 'rouvertes')})` : ''}.`;

  ouvrirFiche(`
    <p class="surtitre">Logement · ${esc(res.nom)}</p>
    <h2 id="fiche-titre" tabindex="-1">Logement ${esc(numLogement(id))}</h2>
    <p class="fiche-lieu">${esc(res.nom)} · bâtiment ${esc(nomBat(l.batiment))} · ${esc(etageTexte(l.etage))} · ${esc(l.typologie)}, ${String(l.surface).replace('.', ',')} m² · ${esc(l.statut.toLowerCase())}</p>
    <div class="fiche-etat">${l.niveau ? niveau(l.niveau) : ''} <span class="score">DPE <span class="dpe dpe-${l.dpe}">${l.dpe}</span> · ${nb(l.conso)} kWh/m²/an</span></div>

    <h3>Ses équipements</h3>
    <ul class="mini-liste">
      ${suivis.map((e) => `<li><button type="button" data-eqp="${e.id}" data-niveau="${e.niveau}"><span><span class="m-titre">${esc(e.libelle)}</span><span class="m-sous">posé en ${e.mesures.pose.slice(0, 4)} · ${esc(e.raisons.find((r) => r.points > 0)?.texte || 'aucun signal')}</span></span>${niveau(e.niveau)}</button></li>`).join('')}
      ${autres.map((e) => `<li><span style="display:flex;justify-content:space-between;gap:12px;padding:8px 12px;color:var(--encre-2)"><span>${esc(e.libelle)}</span><span class="note">posé en ${esc(e.pose.slice(0, 4))}</span></span></li>`).join('')}
    </ul>

    <h3>Demandes du locataire</h3>
    <p style="font-family:var(--serif);font-size:17px;margin:0 0 6px">${esc(phraseDemandes)}</p>
    ${demandes.length ? `<div class="rythme" aria-label="Demandes par année">${annees.map((x) => `<div class="${x.a === Number(fin.slice(0, 4)) ? 'recent' : ''}"><em>${x.n || ''}</em><span class="b" style="height:${(x.n / maxA) * 46}px"></span><small>${x.a}</small></div>`).join('')}</div>` : ''}
    ${demandes.slice(0, 12).map((d) => `<div class="demande">
      <div class="demande-tete"><b>${esc(d.objet || d.motif)}</b><span class="note">${esc(dateCourte(d.date))} · ${esc(d.canal.replace(' service client', ''))}${d.rouverte ? ' · <span class="marque-rouverte">rouverte</span>' : ''}</span></div>
      <p class="demande-texte">« ${esc(d.texte)} »</p>
      <span class="note">${esc(d.motif)} · ${esc(d.priorite)} · résolue en ${d.delai < 48 ? `${String(Math.round(d.delai * 10) / 10).replace('.', ',')} h` : `${Math.round(d.delai / 24)} jours`}</span>
    </div>`).join('')}
    ${demandes.length > 12 ? `<details class="plus-anciennes"><summary>et ${pl(demandes.length - 12, 'demande plus ancienne', 'demandes plus anciennes')}</summary>${demandes.slice(12).map((d) => `<div class="demande"><div class="demande-tete"><b>${esc(d.objet || d.motif)}</b><span class="note">${esc(dateCourte(d.date))} · ${esc(d.canal.replace(' service client', ''))}</span></div><p class="demande-texte">« ${esc(d.texte)} »</p></div>`).join('')}</details>` : ''}

    <h3>Interventions dans le logement · ${nb(interventions.length)}</h3>
    ${historique(interventions.slice(0, 10))}
    ${interventions.length > 10 ? `<details class="plus-anciennes"><summary>et ${pl(interventions.length - 10, 'intervention plus ancienne', 'interventions plus anciennes')}</summary>${historique(interventions.slice(10))}</details>` : ''}
  `, l.niveau || 'calme');
  brancherRangs($('#fiche-corps'));
}

// ── Vue 2 : Le parc ────────────────────────────────────────────────────────
let carte = null;
function vueParc() {
  const total = E.residences.reduce((s, r) => s + r.logements, 0);
  const prio = E.residences.reduce((s, r) => s + r.prioritaire, 0);
  const dpts = [['31', 'Haute-Garonne'], ['33', 'Gironde'], ['34', 'Hérault'], ['40', 'Landes'], ['64', 'Pyrénées-Atlantiques']];
  const residences = E.residences.slice().sort((a, b) => b.prioritaire - a.prioritaire || b.surveiller - a.surveiller);
  $('#contenu').innerHTML = `
    <p class="surtitre">Le parc · territoire Sud-Ouest</p>
    <h1 class="phrase">Où se trouvent les <strong>${nb(prio)} équipements prioritaires</strong>.</h1>
    <p class="chapeau">La métropole toulousaine est le premier secteur raccordé : ${E.residences.length} résidences, ${nb(total)} logements. Choisissez une résidence pour voir ce qui la menace et retrouver chaque logement.</p>
    <div class="parc">
      <div class="carte-cadre">
        <div class="zooms" role="group" aria-label="Échelle de la carte">
          <button type="button" data-zoom="france">France</button>
          <button type="button" data-zoom="sudouest">Sud-Ouest</button>
          <button type="button" data-zoom="toulouse">Métropole toulousaine</button>
        </div>
        <div id="carte" class="carte" role="region" aria-label="Carte du territoire"></div>
        <p class="carte-note">Emplacements des résidences fictifs : secteurs indicatifs, sans adresse. Fond de carte © les contributeurs d'OpenStreetMap.</p>
      </div>
      <div>
        <section class="territoire" aria-labelledby="t-titre">
          <h2 id="t-titre">Sud-Ouest</h2>
          <p class="note" style="margin:0">Cinq départements, environ 6 300 logements. Un département se raccorde en déposant ses fichiers trimestriels.</p>
          <ul class="departements">
            ${dpts.map(([c, n]) => c === '31'
              ? `<li data-raccorde="1"><span class="pastille" aria-hidden="true"></span><span class="dpt-nom">${n} (${c})</span><span class="dpt-etat">${E.residences.length} résidences · ${nb(total)} logements</span></li>`
              : `<li><span class="pastille" aria-hidden="true"></span><span class="dpt-nom">${n} (${c})</span><span class="dpt-etat"><a class="lien" href="#/methode#import">raccorder</a></span></li>`).join('')}
          </ul>
        </section>
        <h2 class="titre-section" style="margin-top:22px">Les résidences</h2>
        <p class="sous-section">De la plus exposée à la plus calme.</p>
        <ol class="assise-liste">
          ${residences.map((r) => `<li><a class="assise residence-rang" href="#/residence/${r.id}" data-niveau="${r.prioritaire ? 'prioritaire' : r.surveiller ? 'surveiller' : 'calme'}" style="text-decoration:none">
            <span class="residence-lettre" aria-hidden="true">${r.lettre}</span>
            <span class="assise-corps"><span class="assise-titre">${esc(r.nom)}</span>
              <span class="assise-lieu">${r.annee} · ${nb(r.logements)} logements · ${esc(r.chauffage.split(' (')[0].toLowerCase())}</span>
              <span class="assise-raison">${r.prioritaire ? `<b>${pl(r.prioritaire, 'équipement prioritaire', 'équipements prioritaires')}</b>${r.logementsARisque ? ` dans ${pl(r.logementsARisque, 'logement', 'logements')}` : ''}, ` : ''}${nb(r.surveiller)} à surveiller · ${pl(r.demandes12m, 'demande', 'demandes')} de locataires en 12 mois</span></span>
          </a></li>`).join('')}
        </ol>
      </div>
    </div>`;
  monterCarte();
}

async function monterCarte() {
  if (carte) { carte.detruire(); carte = null; }
  const el = $('#carte');
  let creerCarte;
  try { ({ creerCarte } = await import('/vendor/carte/carte.mjs')); } catch { el.innerHTML = '<p class="vide">Carte indisponible.</p>'; return; }
  // Une brique par résidence : sa base se remplit des logements à visiter (prioritaires) et à surveiller.
  const residences = E.residences.map((r) => {
    const lg = E.logements.filter((l) => l.residence === r.id);
    return {
      id: r.id, nom: r.nom, lettre: r.lettre, position: r.position, logements: r.logements,
      aVisiter: lg.filter((l) => l.niveau === 'prioritaire').length, aSurveiller: lg.filter((l) => l.niveau === 'surveiller').length,
      communsAVisiter: E.equipements.filter((e) => e.residence === r.id && e.niveau === 'prioritaire' && !e.logement).length,
    };
  });
  const marquer = (cle) => $$('[data-zoom]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.zoom === cle)));
  // première visite : de la France au territoire, comme on s'oriente
  const premiere = !vue.carteVue;
  vue.carteVue = true;
  el.addEventListener('carte:residence', (e) => (location.hash = `#/residence/${e.detail.id}`));
  el.addEventListener('carte:echelle', (e) => { vue.zoom = e.detail.echelle; marquer(e.detail.echelle); });
  const c = await creerCarte(el, { residences, echelle: premiere ? 'sudouest' : vue.zoom || 'sudouest', depuis: premiere ? 'france' : null });
  if (!el.isConnected) { c.detruire(); return; }
  carte = c;
  $$('[data-zoom]').forEach((b) => b.addEventListener('click', () => { vue.zoom = b.dataset.zoom; marquer(b.dataset.zoom); carte.allerA(b.dataset.zoom); }));
  marquer(premiere ? 'france' : carte.echelle);
}

// ── Vue 2 bis : une résidence ──────────────────────────────────────────────
function vueResidence(id) {
  const r = parId.res[id];
  if (!r) return (location.hash = '#/parc');
  const eq = E.equipements.filter((e) => e.residence === id && e.niveau !== 'calme');
  const lg = E.logements.filter((l) => l.residence === id);
  const appellent = lg.filter((l) => l.demandes12m > 0).sort((a, b) => b.demandes12m - a.demandes12m || b.rouvertes12m - a.rouvertes12m || b.demandes - a.demandes).slice(0, 8);
  const bats = E.batiments.filter((b) => b.residence === id);
  const montres = eq.slice(0, Math.max(12, eq.filter((e) => e.niveau === 'prioritaire').length));
  $('#contenu').innerHTML = `
    <p class="surtitre"><a class="lien" href="#/parc">Le parc</a> · métropole toulousaine · <a class="lien" href="#/parc" id="voir-carte">voir sur la carte</a></p>
    <h1 class="phrase">${esc(r.nom)}</h1>
    <p class="chapeau">Construite en ${r.annee} · ${nb(r.logements)} logements en ${pl(r.batiments, 'bâtiment', 'bâtiments')} · ${esc(r.chauffage)} · eau chaude : ${esc(r.ecs)} · ${r.ascenseur ? 'avec ascenseur' : 'sans ascenseur'} · DPE majoritaire <span class="dpe dpe-${r.dpe}">${r.dpe}</span></p>

    <h2 class="titre-section">Ce qui menace ici</h2>
    <p class="sous-section">${r.prioritaire ? `<b>${pl(r.prioritaire, 'équipement prioritaire', 'équipements prioritaires')}</b> et ` : 'Aucun équipement prioritaire ; '}${pl(r.surveiller, 'équipement à surveiller', 'équipements à surveiller')}, du plus urgent au moins urgent.</p>
    ${montres.length ? `<ol class="assise-liste">${montres.map((e) => rangEquipement(e)).join('')}</ol>` : '<p class="vide">Rien à signaler dans cette résidence.</p>'}
    ${eq.length > montres.length ? `<p class="suite"><button class="bouton secondaire" type="button" id="voir-tout">Voir les ${nb(eq.length - montres.length)} autres à surveiller</button></p>` : ''}

    <h2 class="titre-section">Les logements qui appellent le plus</h2>
    <p class="sous-section">Demandes des douze derniers mois. Une demande qui revient peut annoncer une panne ; à vous d'en juger.</p>
    ${appellent.length ? `<ul class="mini-liste">${appellent.map((l) => `<li><button type="button" data-lgt="${l.id}" data-niveau="${l.niveau || 'calme'}"><span><span class="m-titre">Logement ${esc(numLogement(l.id))}</span><span class="m-sous">${esc(etageTexte(l.etage))} · ${esc(l.typologie)} · ${pl(l.demandes, 'demande', 'demandes')} depuis 2019</span></span><span>${pl(l.demandes12m, 'demande', 'demandes')} en 12 mois${l.rouvertes12m ? ` · <span class="marque-rouverte">${pl(l.rouvertes12m, 'rouverte', 'rouvertes')}</span>` : ''}</span></button></li>`).join('')}</ul>` : '<p class="note">Aucune demande ces douze derniers mois.</p>'}

    <h2 class="titre-section">Tous les logements, par bâtiment</h2>
    ${bats.map((b) => {
      const lb = lg.filter((l) => l.batiment === b.id).sort((x, y) => x.id.localeCompare(y.id));
      return `<details class="bloc"><summary style="cursor:pointer;font-weight:600">Bâtiment ${esc(nomBat(b.id))} · ${pl(lb.length, 'logement', 'logements')} · ${pl(b.niveaux, 'niveau', 'niveaux')}${b.prioritaire ? ` · <span style="color:var(--brique-cuite)">${pl(b.prioritaire, 'prioritaire', 'prioritaires')}</span>` : ''}</summary>
        <table class="tableau" style="margin-top:8px"><thead><tr><th>Logement</th><th>Étage</th><th class="masquable">Type</th><th>DPE</th><th class="nombre">Demandes</th><th>Risque</th></tr></thead><tbody>
        ${lb.map((l) => `<tr class="cliquable" data-lgt="${l.id}" tabindex="0"><td><b>${esc(l.id.slice(-3))}</b></td><td>${esc(etageTexte(l.etage))}</td><td class="masquable">${esc(l.typologie)}</td><td><span class="dpe dpe-${l.dpe}">${l.dpe}</span></td><td class="nombre">${l.demandes}${l.demandes12m ? ` <span class="note">(${l.demandes12m} en 12 mois)</span>` : ''}</td><td>${l.niveau && l.niveau !== 'calme' ? niveau(l.niveau) : '<span class="note">—</span>'}</td></tr>`).join('')}
        </tbody></table></details>`;
    }).join('')}
  `;
  // la carte s'ouvre directement à l'échelle de la métropole, là où la résidence se voit
  $('#voir-carte').addEventListener('click', () => { vue.carteVue = true; vue.zoom = 'toulouse'; });
  $('#voir-tout')?.addEventListener('click', (ev) => {
    ev.target.closest('p').remove();
    $('.assise-liste').insertAdjacentHTML('beforeend', eq.slice(12).map((e) => rangEquipement(e)).join(''));
    brancherRangs($('.assise-liste'));
  });
  brancherRangs($('#contenu'));
  $$('tr[data-lgt]').forEach((tr) => tr.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') ouvrirLogement(tr.dataset.lgt); }));
}

// ── Vue 3 : Énergie ────────────────────────────────────────────────────────
function vueEnergie() {
  const classes = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
  const seuil = vue.seuilDpe;
  const enAlerte = (l) => classes.indexOf(l.dpe) >= classes.indexOf(seuil);
  const alertes = E.logements.filter(enAlerte).sort((a, b) => b.conso - a.conso);
  const parRes = E.residences.map((r) => {
    const lg = E.logements.filter((l) => l.residence === r.id);
    return { r, lg, n: lg.filter(enAlerte).length, rep: classes.map((c) => [c, lg.filter((l) => l.dpe === c).length]) };
  }).sort((a, b) => b.n - a.n);
  const ops = E.plan.slice().sort((a, b) => a.rang - b.rang);
  $('#contenu').innerHTML = `
    <p class="surtitre">Énergie · diagnostics de performance énergétique</p>
    <h1 class="phrase"><strong>${pl(alertes.length, 'logement', 'logements')}</strong> ${alertes.length > 1 ? 'sont classés' : 'est classé'} ${seuil === 'G' ? 'G' : `${seuil} ou moins bien`}.</h1>
    <p class="chapeau">Choisissez à partir de quelle étiquette un logement doit apparaître ici ; votre choix est gardé sur cet appareil.</p>
    <div class="barre"><span class="note">Alerter à partir de</span>
      <div class="seuil" role="group" aria-label="Seuil d'alerte">${['D', 'E', 'F', 'G'].map((c) => `<button type="button" data-seuil="${c}" aria-pressed="${seuil === c}">${c}</button>`).join('')}</div>
    </div>

    <h2 class="titre-section">Par résidence</h2>
    <table class="tableau"><thead><tr><th>Résidence</th><th style="width:46%">Étiquettes des logements</th><th class="nombre">En alerte</th></tr></thead><tbody>
      ${parRes.map(({ r, lg, n, rep }) => `<tr class="cliquable" data-res="${r.id}"><td><b>${esc(r.nom)}</b><div class="note">${esc(r.energie)} · ${r.annee}</div></td>
        <td><div class="repartition" aria-label="${rep.filter(([, k]) => k).map(([c, k]) => `${k} ${c}`).join(', ')}">${rep.filter(([, k]) => k).map(([c, k]) => `<span class="dpe-${c}" style="flex:${k}" title="${k} logements ${c}">${k / lg.length > 0.07 ? c : ''}</span>`).join('')}</div></td>
        <td class="nombre"><b>${nb(n)}</b> <span class="note">/ ${nb(lg.length)}</span></td></tr>`).join('')}
    </tbody></table>

    <h2 class="titre-section">Les logements en alerte</h2>
    <p class="sous-section">Du plus consommateur au moins consommateur (énergie primaire).</p>
    ${alertes.length ? `<table class="tableau"><thead><tr><th>Logement</th><th class="masquable">Résidence</th><th>DPE</th><th class="nombre">kWh/m²/an</th><th class="nombre masquable">GES</th></tr></thead><tbody>
      ${alertes.slice(0, 40).map((l) => `<tr class="cliquable" data-lgt="${l.id}" tabindex="0"><td><b>Logement ${esc(numLogement(l.id))}</b><div class="note">${esc(l.typologie)} · ${esc(etageTexte(l.etage))}</div></td><td class="masquable">${esc(parId.res[l.residence].nom)}</td><td><span class="dpe dpe-${l.dpe}">${l.dpe}</span></td><td class="nombre">${nb(l.conso)}</td><td class="nombre masquable">${String(l.ges).replace('.', ',')}</td></tr>`).join('')}
    </tbody></table>${alertes.length > 40 ? `<details class="plus-anciennes"><summary>Afficher les ${nb(alertes.length - 40)} autres logements en alerte</summary><table class="tableau"><tbody>${alertes.slice(40).map((l) => `<tr class="cliquable" data-lgt="${l.id}" tabindex="0"><td><b>Logement ${esc(numLogement(l.id))}</b><div class="note">${esc(l.typologie)} · ${esc(etageTexte(l.etage))}</div></td><td class="masquable">${esc(parId.res[l.residence].nom)}</td><td><span class="dpe dpe-${l.dpe}">${l.dpe}</span></td><td class="nombre">${nb(l.conso)}</td><td class="nombre masquable">${String(l.ges).replace('.', ',')}</td></tr>`).join('')}</tbody></table></details>` : ''}` : '<p class="vide">Aucun logement à ce niveau.</p>'}

    <h2 class="titre-section">Opérations inscrites au plan</h2>
    <p class="sous-section">Plan d'investissement (opérations hypothétiques), dans l'ordre d'inscription actuel. Le nombre de logements en alerte de chaque résidence aide à juger de l'ordre.</p>
    <table class="tableau"><thead><tr><th class="nombre">Rang</th><th>Opération</th><th class="masquable">Année</th><th class="nombre">Coût TTC</th><th class="nombre masquable">Économie visée</th><th class="nombre">En alerte</th></tr></thead><tbody>
      ${ops.map((o) => { const pr = parRes.find((x) => x.r.id === o.residence); return `<tr><td class="nombre">${o.rang}</td><td><b>${esc(o.type)}</b><div class="note">${esc(parId.res[o.residence]?.nom || o.residence)} · ${esc(o.origine)}</div></td><td class="masquable">${o.annee}</td><td class="nombre">${euros(o.cout)}</td><td class="nombre masquable">${o.gain ? `${nb(Math.abs(o.gain))} kWh/m²/an` : '—'}</td><td class="nombre">${pr ? nb(pr.n) : '—'}</td></tr>`; }).join('')}
    </tbody></table>
  `;
  $$('[data-seuil]').forEach((b) => b.addEventListener('click', () => { vue.seuilDpe = b.dataset.seuil; ecrirePref('assise.seuilDpe', b.dataset.seuil); vueEnergie(); }));
  $$('tr[data-res]').forEach((tr) => tr.addEventListener('click', () => (location.hash = `#/residence/${tr.dataset.res}`)));
  brancherRangs($('#contenu'));
}

// ── Vue 4 : Méthode, mise à jour, exports ──────────────────────────────────
function vueMethode() {
  const m = E.methode, ep = m.epreuve, p = m.poids;
  const pct = (x) => `${Math.round((x / ep.pannes) * 100)} %`;
  const virg = (x) => x.toFixed(2).replace('.', ',');
  $('#contenu').innerHTML = `
    <p class="surtitre">Méthode · pourquoi croire ce classement</p>
    <h1 class="phrase">Une somme de raisons, <strong>mise à l'épreuve sur le passé</strong>.</h1>
    <div class="texte-long">
      <p>Chaque équipement reçoit des points, et chaque point a une raison qu'on peut lire et discuter. Le total, ramené entre 0 et 100, donne l'<b>indice de risque</b> qui classe les équipements : à partir de ${m.seuils.prioritaire}, l'équipement est <b>prioritaire</b> ; à partir de ${m.seuils.surveiller}, il est <b>à surveiller</b>. Chaque ingrédient est plafonné, pour qu'aucun ne suffise à lui seul ; le total s'arrête à 100.</p>
      <p>Une <b>panne bloquante</b>, c'est un dépannage noté « arrêt total » : l'équipement ne rend plus le service.</p>
    </div>
    <h2 class="titre-section">Les ingrédients</h2>
    <ul class="ingredients">
      <li><span><b>L'usure.</b> L'âge rapporté à la durée de vie prévue de la famille d'équipement. Le risque croît de plus en plus vite avec l'âge (loi de Weibull) ; la durée de vie retenue est raccourcie quand le locataire est souvent absent aux visites d'entretien (jusqu'à −30 %) et pour les grands logements.</span><span class="poids">jusqu'à ${p.usure} pts</span></li>
      <li><span><b>Les dépannages récents.</b> Chaque dépannage des douze derniers mois, davantage s'il s'agissait d'un arrêt total.</span><span class="poids">${p.depannage12m} pts chacun (3 au plus), +${p.arretTotal12m} par arrêt total (2 au plus)</span></li>
      <li><span><b>Ce que les techniciens ont écrit.</b> « Usure avancée », « réparation provisoire », « pièce difficile à obtenir »… sur les dix-huit derniers mois.</span><span class="poids">${p.signalTechnicien} pts chacun (3 au plus)</span></li>
      <li><span><b>Les anomalies en visite d'entretien</b> sur les dix-huit derniers mois.</span><span class="poids">${p.anomalieVisite} pts chacune (2 au plus)</span></li>
      <li><span><b>Un remplacement demandé et pas encore fait.</b></span><span class="poids">${p.remplacementDemande} pts</span></li>
      <li><span><b>Ce que le locataire a signalé.</b> Les demandes liées à cet équipement sur les douze derniers mois.</span><span class="poids">${p.demandeLocataire} pts chacune (3 au plus)</span></li>
    </ul>
    <p class="note">Les poids ont été fixés à partir des règles de fabrication des données (onglet HYPOTHESES), pas ajustés pour maximiser le résultat ci-dessous.</p>

    <h2 class="titre-section">La mise à l'épreuve</h2>
    <div class="texte-long">
      <p>On s'est placé au ${esc(dateLongue(ep.dateReference))}, sans rien regarder de la suite, et on a classé les ${nb(ep.equipements)} équipements. Puis on a compté ce qui a réellement cassé entre le ${esc(dateLongue(ep.debut))} et le ${esc(dateLongue(ep.fin))} : <b>${nb(ep.pannes)} pannes bloquantes</b>.</p>
      <p>En inspectant les ${nb(ep.methode.dixieme.inspectes)} premiers équipements de la liste (un sur dix), on en aurait trouvé :</p>
    </div>
    <div class="comparaison" role="img" aria-label="Pannes trouvées : ${ep.methode.dixieme.trouvees} avec la méthode, ${ep.ageSeul.dixieme.trouvees} avec l'âge seul, sur ${ep.pannes}">
      <div class="comparaison-ligne"><b>Avec cette méthode</b><div class="comparaison-piste"><span style="width:${(ep.methode.dixieme.trouvees / ep.pannes) * 100}%"></span></div><span><b>${ep.methode.dixieme.trouvees}</b> / ${ep.pannes}</span></div>
      <div class="comparaison-ligne age"><span>Avec l'âge seul</span><div class="comparaison-piste"><span style="width:${(ep.ageSeul.dixieme.trouvees / ep.pannes) * 100}%"></span></div><span><b>${ep.ageSeul.dixieme.trouvees}</b> / ${ep.pannes}</span></div>
    </div>
    <div class="texte-long">
      <p>Soit ${pct(ep.methode.dixieme.trouvees)} des pannes de la période repérées à l'avance, contre ${pct(ep.ageSeul.dixieme.trouvees)}. Sur l'ensemble du classement, la probabilité qu'un équipement tombé en panne soit placé au-dessus d'un équipement resté en service (AUC) est de <b>${virg(ep.methode.auc)}</b>, contre ${virg(ep.ageSeul.auc)} pour l'âge seul.</p>
      <p class="note">Calculé au démarrage de l'application, sur les données chargées. Les données chargées sont fictives : ce résultat dit que la méthode retrouve les mécanismes décrits, pas qu'elle fera de même sur le parc réel — c'est l'épreuve suivante.</p>
    </div>

    <h2 class="titre-section" id="import">Mettre à jour chaque trimestre</h2>
    <div class="bloc">
      <p style="margin-top:0">Déposez les fichiers CSV du trimestre (mêmes noms et colonnes que les fichiers actuels : <code>04_equipements.csv</code>, <code>06_interventions.csv</code>, <code>05_demandes_locataires.csv</code>…). Ils remplacent les précédents, le classement est recalculé sur cette machine, et rien n'est envoyé ailleurs. Un fichier aux colonnes incomplètes est refusé.</p>
      <label class="import-zone" style="display:block;cursor:pointer">
        <input id="fichiers" class="visuel-seul" type="file" accept=".csv,text/csv" multiple>
        <span class="bouton" style="margin-bottom:10px">Choisir les fichiers du trimestre</span><br>
        <span class="note">Données actuelles : ${esc(E.meta.trimestre)}, arrêtées au ${esc(E.meta.dateDonneesTexte)}${E.meta.importes.length ? ` · importés : ${esc(E.meta.importes.join(', '))}` : ' · fichiers d\'origine'}.</span>
      </label>
      <p id="import-etat" class="note" role="status"></p>
    </div>

    <h2 class="titre-section">Exporter</h2>
    <div class="bloc" style="display:flex;flex-wrap:wrap;gap:10px">
      <a class="bouton" href="/export/risques.csv" download>Classement complet avec raisons (CSV)</a>
      <a class="bouton secondaire" href="/export/decisions.csv" download>Décisions (CSV)</a>
      <a class="bouton secondaire" href="/export/scores.csv" download>Scores seuls (equipement_id, score_risque)</a>
    </div>

    <h2 class="titre-section">Ce que l'outil ne fait pas</h2>
    <div class="texte-long"><p>Il ne commande rien, ne prévient personne et ne décide pas : il classe, explique, et garde la trace de vos décisions. Il n'envoie aucune donnée à un service en ligne ; seul le fond de carte public est chargé depuis Internet. Les résidences n'ont pas d'adresse : leurs emplacements sur la carte sont fictifs.</p></div>
  `;
  $('#fichiers').addEventListener('change', async (ev) => {
    const etat = $('#import-etat');
    const fichiers = {};
    for (const f of ev.target.files) fichiers[f.name] = await f.text();
    etat.textContent = `Lecture de ${pl(Object.keys(fichiers).length, 'fichier', 'fichiers')}…`;
    const r = await fetch('/api/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ fichiers }) });
    const rep = await r.json();
    if (!r.ok) { etat.textContent = `${rep.erreur}${rep.refuses?.length ? ' — ' + rep.refuses.map((x) => `${x.nom} : ${x.raison}`).join(' ; ') : ''}`; return; }
    await charger();
    etat.textContent = `Import terminé : ${rep.retenus.map((x) => `${x.nom} (${nb(x.lignes)} lignes)`).join(', ')}.${rep.refuses.length ? ' Refusés : ' + rep.refuses.map((x) => `${x.nom} (${x.raison})`).join(' ; ') : ''} Classement recalculé.`;
    annoncer('Classement recalculé');
  });
  if (location.hash.endsWith('#import')) setTimeout(() => $('#import')?.scrollIntoView({ behavior: 'smooth' }), 50);
}

// ── Recherche ──────────────────────────────────────────────────────────────
function normaliser(s) { return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/^(lgt|eqp|res|bat)[-\s]?/, '').replace(/[^a-z0-9]/g, ''); }
function chercher(q) {
  const n = normaliser(q);
  if (!n) return [];
  const res = [];
  for (const r of E.residences) if (normaliser(r.nom).includes(n) || (n.length === 1 && r.lettre.toLowerCase() === n) || normaliser('residence ' + r.lettre) === n) res.push({ type: 'res', id: r.id, titre: r.nom, sous: `${nb(r.logements)} logements · ${r.prioritaire} prioritaires` });
  const lgtNum = n.match(/^([a-h])(\d)(\d{0,3})$/);
  for (const l of E.logements) {
    const id = normaliser(l.id);
    let ok = id.startsWith(n);
    if (!ok && lgtNum && lgtNum[3]) ok = id === `${lgtNum[1]}${lgtNum[2]}${lgtNum[3].padStart(3, '0')}`;
    if (ok) res.push({ type: 'lgt', id: l.id, titre: `Logement ${numLogement(l.id)}`, sous: `${parId.res[l.residence].nom} · ${etageTexte(l.etage)} · ${l.typologie} · ${pl(l.demandes, 'demande', 'demandes')}` });
    if (res.length > 12) break;
  }
  for (const e of E.equipements) if (normaliser(e.id).startsWith(n) && /^\d/.test(n)) { res.push({ type: 'eqp', id: e.id, titre: `${e.libelle} (${e.id})`, sous: lieu(e) }); if (res.length > 14) break; }
  return res.slice(0, 12);
}
function brancherRecherche() {
  const champ = $('#recherche'), boite = $('#recherche-resultats');
  let resultats = [], actif = -1;
  const fermer = () => { boite.hidden = true; champ.setAttribute('aria-expanded', 'false'); actif = -1; };
  const aller = (r) => { fermer(); champ.value = ''; champ.blur(); if (r.type === 'res') location.hash = `#/residence/${r.id}`; else if (r.type === 'lgt') ouvrirLogement(r.id); else ouvrirEquipement(r.id); };
  const dessiner = () => {
    boite.innerHTML = resultats.length ? resultats.map((r, i) => `<button type="button" role="option" aria-selected="${i === actif}" data-i="${i}"><span class="r-titre">${esc(r.titre)}</span><span class="r-sous">${esc(r.sous)}</span></button>`).join('')
      : `<div class="recherche-vide">Rien trouvé. Essayez un numéro de logement comme « F2-014 », une résidence comme « Résidence C », ou une référence « EQP-01633 ».</div>`;
    boite.hidden = false; champ.setAttribute('aria-expanded', 'true');
    $$('button', boite).forEach((b) => b.addEventListener('mousedown', (ev) => { ev.preventDefault(); aller(resultats[b.dataset.i]); }));
  };
  champ.addEventListener('input', () => { if (!champ.value.trim()) return fermer(); resultats = chercher(champ.value); actif = resultats.length ? 0 : -1; dessiner(); });
  champ.addEventListener('keydown', (ev) => {
    if (ev.key === 'ArrowDown') { actif = Math.min(resultats.length - 1, actif + 1); dessiner(); ev.preventDefault(); }
    else if (ev.key === 'ArrowUp') { actif = Math.max(0, actif - 1); dessiner(); ev.preventDefault(); }
    else if (ev.key === 'Enter' && resultats[actif]) aller(resultats[actif]);
    else if (ev.key === 'Escape') fermer();
  });
  champ.addEventListener('blur', () => setTimeout(fermer, 120));
}

// ── Routage ────────────────────────────────────────────────────────────────
function rafraichirVue() {
  const h = location.hash.replace(/^#/, '') || '/';
  if (h.startsWith('/parc')) vueParc();
  else if (h.startsWith('/residence/')) vueResidence(h.split('/')[2]);
  else if (h.startsWith('/energie')) vueEnergie();
  else if (h.startsWith('/methode')) vueMethode();
  else vueDecider();
  const cle = h.startsWith('/parc') || h.startsWith('/residence') ? 'parc' : h.startsWith('/energie') ? 'energie' : h.startsWith('/methode') ? 'methode' : 'decider';
  $$('[data-nav]').forEach((a) => (a.dataset.nav === cle ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
  document.title = { decider: 'À décider', parc: 'Le parc', energie: 'Énergie', methode: 'Méthode' }[cle] + ' — Assise';
}
function naviguer() {
  if (ficheOuverte) fermerFiche({ depuisHistorique: true });
  rafraichirVue();
  window.scrollTo(0, 0);
}

async function demarrer() {
  try { await charger(); } catch { $('#contenu').innerHTML = '<p class="vide">Le serveur ne répond pas. Relancez <code>npm start</code> dans le dossier de l\'application.</p>'; return; }
  brancherRecherche();
  $('.fiche-fermer').addEventListener('click', () => fermerFiche());
  $('#voile').addEventListener('click', () => fermerFiche());
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && ficheOuverte) fermerFiche(); });
  window.addEventListener('popstate', () => { if (ficheOuverte) fermerFiche({ depuisHistorique: true }); });
  window.addEventListener('hashchange', naviguer);
  rafraichirVue();
}
demarrer();
