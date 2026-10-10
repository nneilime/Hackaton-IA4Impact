// Rejeu de 2025 : la preuve, en vingt secondes, que le barème voit venir les pannes.
// Module autonome, branché sur BâtIA par une ligne dans app/index.html. Il attend la carte
// (window.foraine.carte), ajoute un bouton discret et la touche L, et pose son calque par-dessus la carte.
// Tous les chiffres viennent de rejeu/donnees/rejeu-2025.json, écrit par rejeu/preparer.py.
// Ouverture directe : /?rejeu (lance la lecture) ou /?rejeu=pause (attend au 1er janvier).

const ICI = new URL('.', import.meta.url).href;
const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
const MOIS_COURTS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
const nb = (n) => new Intl.NumberFormat('fr-FR').format(n);
const borne = (x) => Math.max(0, Math.min(1, x));
const doux = (x) => { x = borne(x); return x * x * (3 - 2 * x); };

// Le rythme, en secondes à la vitesse 1 : vingt secondes de bout en bout.
// Les briques se posent, les 128 s'allument, puis janvier à septembre défilent en treize secondes.
const R = { allumage: 1.0, allumageFin: 3.0, mois: 3.8, moisFin: 16.8, regroupe: 17.3, fin: 20 };
const VITESSES = [1, 2, 0.5];
const C = { vue: '#0072B2', allumee: '#7FB0D8', eteinte: 'rgba(58, 58, 58, .24)', manquee: '#D7261E', /* le rouge d'« Urgent » (app/palette.css) : le canevas ne lit pas les variables CSS */ encre: '#161616', encre3: '#666666', blanc: 'rgba(255, 255, 255, .96)' };
const GESTES = ['dragPan', 'scrollZoom', 'boxZoom', 'doubleClickZoom', 'touchZoomRotate', 'keyboard'];
// Les secteurs de BâtIA (cercles de 400 m) se cachent sous les briques : on les retire le temps du rejeu.
const COUCHES_CACHEES = ['secteurs', 'secteurs-trait', 'secteurs-choisi'];

let D = null, carte = null, el = null, ctx = null, bouton = null;
let ouvert = false, lecture = false, fige = false, t = 0, vitesse = 1, dernier = 0, raf = 0, avant = null;
let briques = [], pannes = [], jours = 273, pas = 11;
const vu = {};

const jourDe = (iso) => (Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) - Date.UTC(+D.debut.slice(0, 4), +D.debut.slice(5, 7) - 1, +D.debut.slice(8, 10))) / 864e5;
const dateLongue = (iso) => { const [a, m, j] = iso.split('-').map(Number); return `${j === 1 ? '1er' : j} ${MOIS[m - 1]} ${a}`; };

function feuille() {
  if (document.querySelector('link[data-rejeu]')) return;
  const l = Object.assign(document.createElement('link'), { rel: 'stylesheet', href: ICI + 'rejeu.css' });
  l.dataset.rejeu = '';
  document.head.append(l);
}

async function attendreCarte() {
  for (let i = 0; i < 900; i++) {
    if (window.foraine?.carte?.map) return window.foraine.carte;
    await new Promise((ok) => setTimeout(ok, 100));
  }
  throw new Error('la carte de BâtIA ne s’est pas montée');
}

// ── Les données : une brique par résidence, une cellule par équipement ─────────
function preparer() {
  jours = jourDe(D.fin) + 1;
  const parRes = new Map(D.residences.map((r, i) => [r.id, { ...r, ordre: i, cellules: [] }]));
  // les 128 s'allument du plus haut score au moins haut
  const visites = D.liste.filter((e) => e.visite).sort((a, b) => b.points - a.points || a.id.localeCompare(b.id));
  const rang = new Map(visites.map((e, i) => [e.id, i]));
  const duree = R.allumageFin - R.allumage - 0.4;
  // la liste est rangée par résidence puis par score : les visités forment la base de chaque brique
  for (const e of D.liste) {
    const b = parRes.get(e.r);
    b.cellules.push({ eq: e, i: b.cellules.length, allume: e.visite ? R.allumage + (rang.get(e.id) / visites.length) * duree : null });
  }
  briques = [...parRes.values()];
  for (const b of briques) { b.colonnes = Math.ceil(Math.sqrt(b.cellules.length)); b.rangees = Math.ceil(b.cellules.length / b.colonnes); }
  pannes = [];
  for (const b of briques) for (const c of b.cellules) if (c.eq.panne) {
    pannes.push({ b, c, te: R.mois + ((jourDe(c.eq.panne) + 0.5) / jours) * (R.moisFin - R.mois), vue: c.eq.visite, vueAge: c.eq.plusVieux, id: c.eq.id });
  }
  pannes.sort((a, b) => a.te - b.te || a.id.localeCompare(b.id));
  // à la fin, chaque gaufre se range : les pannes vues venir d'abord
  const ranger = (cle) => { const o = [...pannes.filter((p) => p[cle]), ...pannes.filter((p) => !p[cle])]; return new Map(o.map((p, i) => [p, i])); };
  pannes.forEach((p, i) => { p.k = i; });
  const fe = ranger('vue'), fa = ranger('vueAge');
  pannes.forEach((p) => { p.finEquipe = fe.get(p); p.finAge = fa.get(p); });
}

function placerCellules() {
  for (const b of briques) {
    b.l = b.colonnes * pas; b.h = b.rangees * pas;
    // la zone regardée : les cellules des visités, en bas de la brique (colonnes, rangées pleines, reste)
    const v = b.cellules.filter((c) => c.eq.visite).length, pleines = Math.floor(v / b.colonnes), reste = v % b.colonnes;
    b.zone = !v ? null : pleines && reste ? [[0, 0], [b.colonnes, 0], [b.colonnes, pleines], [reste, pleines], [reste, pleines + 1], [0, pleines + 1]]
      : pleines ? [[0, 0], [b.colonnes, 0], [b.colonnes, pleines], [0, pleines]] : [[0, 0], [reste, 0], [reste, 1], [0, 1]];
    b.zoneFin = Math.max(...b.cellules.filter((c) => c.eq.visite).map((c) => c.allume)) + 0.45;
    for (const c of b.cellules) {
      const col = c.i % b.colonnes, rangee = Math.floor(c.i / b.colonnes);
      c.dx = (col - (b.colonnes - 1) / 2) * pas;
      c.dy = ((b.rangees - 1) / 2 - rangee) * pas;
    }
  }
}

// ── Le calque ──────────────────────────────────────────────────────────────────
const SVG = {
  tous: `<svg viewBox="0 0 22 22" width="22" height="22" aria-hidden="true"><rect x="4" y="4" width="14" height="14" rx="1.5" fill="${C.eteinte}"/></svg>`,
  visite: `<svg viewBox="0 0 22 22" width="22" height="22" aria-hidden="true"><rect x="4" y="4" width="14" height="14" rx="1.5" fill="${C.allumee}" stroke="${C.vue}" stroke-width="1.6"/></svg>`,
  vue: `<svg viewBox="0 0 22 22" width="22" height="22" aria-hidden="true"><circle cx="11" cy="11" r="8" fill="${C.vue}" stroke="#fff" stroke-width="2"/></svg>`,
  manquee: `<svg viewBox="0 0 22 22" width="22" height="22" aria-hidden="true"><path d="M5 5l12 12M17 5L5 17" stroke="#fff" stroke-width="6.5" stroke-linecap="round"/><path d="M5 5l12 12M17 5L5 17" stroke="${C.manquee}" stroke-width="3.6" stroke-linecap="round"/></svg>`,
  lecture: '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M4 2.5v11l9-5.5z" fill="currentColor"/></svg>',
  pause: '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M4 2.5h3v11H4zM9 2.5h3v11H9z" fill="currentColor"/></svg>',
  revoir: '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M8 2.5a5.5 5.5 0 1 1-5.2 3.7" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M1.6 2.4l1.4 4.1 4-1.3z" fill="currentColor"/></svg>',
};

function compteur(cle, nom) {
  return `<div class="compteur ${cle}">
      <span class="c-nom">${nom}</span>
      <span class="c-val"><b>0</b><span></span></span>
      <span class="gaufre" aria-hidden="true">${pannes.map(() => '<i></i>').join('')}</span>
    </div>`;
}

function monter() {
  el = document.createElement('div');
  el.className = 'rejeu';
  el.setAttribute('role', 'region');
  el.setAttribute('aria-label', 'Rejeu de 2025, données fictives du kit');
  const moisPeriode = MOIS_COURTS.slice(+D.debut.slice(5, 7) - 1, +D.fin.slice(5, 7));
  el.innerHTML = `
    <div class="rejeu-voile"></div>
    <canvas class="rejeu-toile" aria-hidden="true"></canvas>
    <div class="rejeu-panneau">
      <div class="rejeu-haut">
        <div class="rejeu-quand"><small>Rejeu de 2025</small><span class="q">${dateLongue(D.debut)}</span></div>
        <div class="rejeu-mois"><span class="barre"></span><ol>${moisPeriode.map((m) => `<li>${m}</li>`).join('')}</ol></div>
      </div>
      <div class="rejeu-bas-tel">
        <div class="rejeu-compteurs">
          ${compteur('equipe', 'La méthode de l’équipe')}
          ${compteur('age', `Les ${nb(D.visites)} plus vieux`)}
        </div>
        <ul class="rejeu-legende">
          <li class="tous">${SVG.tous}<span>${nb(D.equipements)} équipements</span></li>
          <li class="visite">${SVG.visite}<span>${nb(D.visites)} à visiter<span class="long">, choisis le ${dateLongue(D.debut)}</span></span></li>
          <li class="vue">${SVG.vue}<span>panne vue venir</span></li>
          <li class="manquee">${SVG.manquee}<span>panne manquée</span></li>
        </ul>
        <div class="rejeu-bas">
          <div class="rejeu-commandes">
            <button type="button" data-rj="lecture"></button>
            <button type="button" data-rj="vitesse" title="Vitesse (touche V)"></button>
            <button type="button" data-rj="recommencer" title="Recommencer (touche L)" aria-label="Recommencer">${SVG.revoir}<span class="mot">Recommencer</span> <kbd>L</kbd></button>
            <button type="button" data-rj="quitter" class="quitter" title="Revenir à BâtIA (Échap)">Quitter <kbd>Échap</kbd></button>
          </div>
          <p class="rejeu-pied"><b>Prototype non officiel</b> · données fictives du kit BâtIA · barème réglé sur 2019 à 2024, sans voir 2025</p>
        </div>
      </div>
    </div>
    <p class="cache" role="status" aria-live="polite"></p>`;
  document.body.append(el);
  ctx = el.querySelector('canvas').getContext('2d');
  el.addEventListener('click', (ev) => {
    const b = ev.target.closest('[data-rj]');
    if (!b) return;
    const a = b.dataset.rj;
    if (a === 'lecture') basculer();
    else if (a === 'vitesse') changerVitesse();
    else if (a === 'recommencer') recommencer();
    else if (a === 'quitter') fermer();
    b.blur();
  });
  for (const k of Object.keys(vu)) delete vu[k];
  majCommandes();
}

function mesurer() {
  const W = innerWidth, H = innerHeight, dpr = devicePixelRatio || 1;
  const toile = el.querySelector('canvas');
  toile.width = Math.round(W * dpr); toile.height = Math.round(H * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  pas = W <= 760 ? 5 : W <= 1500 ? 10 : 14;
  placerCellules();
  // une case par panne, en rangées de dix (treize au téléphone), à la largeur du compteur
  const g = el.querySelector('.gaufre');
  vu.colonnes = W <= 760 ? 13 : 10;
  vu.jeu = parseFloat(getComputedStyle(g).getPropertyValue('--jeu')) || 2;
  vu.case = Math.max(5, Math.min(24, Math.floor((g.clientWidth - (vu.colonnes - 1) * vu.jeu) / vu.colonnes)));
  const rangees = Math.ceil(pannes.length / vu.colonnes);
  el.querySelectorAll('.gaufre').forEach((x) => { x.style.setProperty('--case', `${vu.case}px`); x.style.height = `${rangees * vu.case + (rangees - 1) * vu.jeu}px`; });
  delete vu.ordre; delete vu.quand;
  dessine = -1;
}

// Le cadre : les huit résidences dans l'espace que le panneau laisse libre, chaque brique entière.
function cadrer({ anime = true } = {}) {
  const map = carte.map, W = innerWidth, H = innerHeight, etroit = W <= 760;
  const demi = Math.max(...briques.map((b) => Math.max(b.l, b.h))) / 2 + (etroit ? 10 : 22);
  const zone = { top: 0, right: 0, bottom: 0, left: 0 };
  if (etroit) {
    const haut = el.querySelector('.rejeu-haut'), bas = el.querySelector('.rejeu-bas-tel');
    zone.top = haut.offsetTop + haut.offsetHeight;
    zone.bottom = H - bas.offsetTop;
  } else zone.right = W - el.querySelector('.rejeu-panneau').offsetLeft;
  const m = etroit ? 6 : 36;
  const lngs = briques.map((b) => b.position[1]), lats = briques.map((b) => b.position[0]);
  const bornes = [[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]];
  const padding = { top: zone.top + m + demi, bottom: zone.bottom + m + demi, left: m + demi, right: zone.right + m + demi };
  const cam = map.cameraForBounds(bornes, { padding }) || map.cameraForBounds(bornes, { padding: 20 });
  if (!cam) return Promise.resolve();
  const reduit = matchMedia('(prefers-reduced-motion: reduce)').matches || localStorage.getItem('foraine.animations') === 'reduites';
  return new Promise((ok) => {
    if (!anime || reduit) { map.jumpTo(cam); ok(); return; }
    map.once('moveend', ok);
    map.flyTo({ ...cam, duration: 1500, curve: 1.3, essential: true });
  });
}

// ── Dessin de la carte ─────────────────────────────────────────────────────────
function disque(x, y, r) {
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fillStyle = C.vue; ctx.fill();
  ctx.lineWidth = Math.max(1.5, r * 0.28); ctx.strokeStyle = C.blanc; ctx.stroke();
}
function croix(x, y, a, lw) {
  ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(x - a, y - a); ctx.lineTo(x + a, y + a); ctx.moveTo(x + a, y - a); ctx.lineTo(x - a, y + a);
  ctx.strokeStyle = C.blanc; ctx.lineWidth = lw + Math.max(2.4, lw * 0.9); ctx.stroke();
  ctx.strokeStyle = C.manquee; ctx.lineWidth = lw; ctx.stroke();
}

function dessiner() {
  const W = innerWidth, H = innerHeight, map = carte.map;
  ctx.clearRect(0, 0, W, H);
  const s = pas >= 9 ? pas - 3 : pas - 1;
  // à la fin, les équipements sans histoire s'effacent à moitié : restent la zone regardée et les pannes
  const eteinte = `rgba(58, 58, 58, ${(0.24 - 0.11 * doux((t - R.moisFin) / 0.8)).toFixed(3)})`;
  const etiquette = pas >= 9 ? 17 : 11;
  for (const b of briques) {
    const p = map.project([b.position[1], b.position[0]]);
    b.x = p.x; b.y = p.y;
    const a = doux((t - b.ordre * 0.08) / 0.45);
    if (a <= 0) continue;
    ctx.globalAlpha = a;
    ctx.font = `700 ${etiquette}px 'Inter', 'Source Sans 3', sans-serif`;
    ctx.fillStyle = C.encre3; ctx.textBaseline = 'bottom';
    ctx.fillText(b.lettre, p.x - b.l / 2, p.y - b.h / 2 - 3);
    for (const c of b.cellules) {
      const x = p.x + c.dx - s / 2, y = p.y + c.dy - s / 2;
      if (c.allume != null && t >= c.allume) {
        const k = borne((t - c.allume) / 0.45);
        if (k < 1) { const e = (1 - k) * pas * 0.9; ctx.fillStyle = `rgba(0, 114, 178, ${0.45 * (1 - k)})`; ctx.fillRect(x - e, y - e, s + 2 * e, s + 2 * e); }
        ctx.fillStyle = C.allumee; ctx.fillRect(x, y, s, s);
        ctx.lineWidth = pas >= 9 ? 1.3 : 0.9; ctx.strokeStyle = C.vue; ctx.strokeRect(x + 0.5, y + 0.5, s - 1, s - 1);
      } else { ctx.fillStyle = eteinte; ctx.fillRect(x, y, s, s); }
    }
    // la zone où la méthode a regardé : un trait bleu autour des visités de la résidence
    if (b.zone && t >= b.zoneFin) {
      const g = p.x - b.l / 2, bas = p.y + b.h / 2, e = pas >= 9 ? 2.5 : 1.5;
      ctx.globalAlpha = a * doux((t - b.zoneFin) / 0.4);
      ctx.beginPath();
      b.zone.forEach(([X, Y], i) => { const px = g + X * pas + (X ? e - 1.5 : -e), py = bas - Y * pas + (Y ? -e : e - 1.5); if (i) ctx.lineTo(px, py); else ctx.moveTo(px, py); });
      ctx.closePath();
      ctx.lineJoin = 'round'; ctx.lineWidth = pas >= 9 ? 2.5 : 1.5; ctx.strokeStyle = C.vue; ctx.stroke();
    }
  }
  ctx.globalAlpha = 1;
  // Les pannes tombées : une onde, puis la marque qui reste.
  const r = Math.max(3, pas * 0.56), bras = Math.max(2.6, pas * 0.4), lw = Math.max(1.8, pas * 0.22);
  for (const pn of pannes) {
    if (t < pn.te) break;
    const age = t - pn.te, x = pn.b.x + pn.c.dx, y = pn.b.y + pn.c.dy;
    if (age < 1.2) {
      const k = age / 1.2;
      ctx.beginPath(); ctx.arc(x, y, r + (pas >= 9 ? 60 : 26) * Math.sqrt(k), 0, Math.PI * 2);
      ctx.strokeStyle = pn.vue ? `rgba(0, 114, 178, ${0.85 * (1 - k)})` : `rgba(213, 94, 0, ${0.85 * (1 - k)})`;
      ctx.lineWidth = (pas >= 9 ? 4 : 2.5) * (1 - k) + 1; ctx.stroke();
    }
    const pop = 1 + 1.1 * Math.max(0, 1 - age / 0.35);
    if (pn.vue) disque(x, y, r * pop); else croix(x, y, bras * pop, lw * Math.min(pop, 1.3));
  }
}

// ── Le panneau ─────────────────────────────────────────────────────────────────
function changer(cle, valeur, fn) { if (vu[cle] !== valeur) { vu[cle] = valeur; fn(valeur); } }

function majPanneau() {
  const phase = t < R.allumage ? 'briques' : t < R.mois ? 'allumage' : t < R.moisFin ? 'mois' : 'fin';
  changer('phase', phase, (v) => { el.dataset.phase = v; });
  const avance = borne((t - R.mois) / (R.moisFin - R.mois));
  const jour = Math.min(jours - 1, Math.floor(avance * jours));
  const d = new Date(Date.UTC(+D.debut.slice(0, 4), +D.debut.slice(5, 7) - 1, +D.debut.slice(8, 10) + jour));
  const quand = phase === 'briques' || phase === 'allumage' ? dateLongue(D.debut) : phase === 'fin' ? dateLongue(D.fin) : `${MOIS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
  changer('quand', quand, (v) => {
    const q = el.querySelector('.rejeu-quand .q'), boite = q.parentElement;
    q.textContent = v; q.style.fontSize = '';
    if (q.scrollWidth > boite.clientWidth) q.style.fontSize = `${Math.floor(parseFloat(getComputedStyle(q).fontSize) * boite.clientWidth / q.scrollWidth)}px`;
  });
  el.querySelector('.rejeu-mois').style.setProperty('--avance', avance.toFixed(4));
  const moisCourant = phase === 'mois' || phase === 'fin' ? d.getUTCMonth() - (+D.debut.slice(5, 7) - 1) : -1;
  changer('moisCourant', moisCourant, (v) => el.querySelectorAll('.rejeu-mois li').forEach((li, i) => li.classList.toggle('passe', i <= v)));

  let total = 0, vues = 0, vuesAge = 0;
  for (const p of pannes) { if (p.te > t) break; total++; if (p.vue) vues++; if (p.vueAge) vuesAge++; }
  const sur = total ? `sur ${nb(total)} panne${total > 1 ? 's' : ''}` : '';
  changer('vues', vues, (v) => { const b = el.querySelector('.equipe .c-val b'); b.textContent = nb(v); b.classList.remove('saute'); void b.offsetWidth; b.classList.add('saute'); });
  changer('vuesAge', vuesAge, (v) => { const b = el.querySelector('.age .c-val b'); b.textContent = nb(v); b.classList.remove('saute'); void b.offsetWidth; b.classList.add('saute'); });
  changer('sur', sur, (v) => el.querySelectorAll('.c-val span').forEach((s) => { s.textContent = v; }));
  changer('total', total, () => {
    const [ge, ga] = el.querySelectorAll('.gaufre');
    pannes.forEach((p, i) => {
      const tombe = i < total;
      ge.children[i].className = tombe ? (p.vue ? 'vue' : 'manquee') : '';
      ga.children[i].className = tombe ? (p.vueAge ? 'vue' : 'manquee') : '';
    });
  });
  const range = t >= R.regroupe;
  changer('ordre', range, (v) => {
    const [ge, ga] = el.querySelectorAll('.gaufre');
    const pos = (i) => `translate(${(i % vu.colonnes) * (vu.case + vu.jeu)}px, ${Math.floor(i / vu.colonnes) * (vu.case + vu.jeu)}px)`;
    pannes.forEach((p, i) => { ge.children[i].style.transform = pos(v ? p.finEquipe : p.k); ga.children[i].style.transform = pos(v ? p.finAge : p.k); });
  });
  changer('annonce', phase === 'fin', (v) => {
    el.querySelector('.cache').textContent = v ? `La méthode de l’équipe a vu venir ${vues} pannes sur ${total} ; les ${D.visites} plus vieux, ${vuesAge} sur ${total}.` : '';
  });
}

function majCommandes() {
  if (!el) return;
  const fini = t >= R.fin;
  el.querySelector('[data-rj="lecture"]').innerHTML = lecture ? `${SVG.pause}<span>Pause</span> <kbd>Espace</kbd>` : `${SVG.lecture}<span>${fini ? 'Revoir' : 'Lecture'}</span> <kbd>Espace</kbd>`;
  // à la fin, « Revoir » suffit : un seul bouton pour repartir du début
  el.querySelector('[data-rj="recommencer"]').style.display = fini && !lecture ? 'none' : '';
  el.querySelector('[data-rj="vitesse"]').innerHTML = `<span class="mot">Vitesse </span>×${String(vitesse).replace('.', ',')} <kbd>V</kbd>`;
}

// On ne redessine que si l'instant ou la caméra ont changé : à l'arrêt, le rejeu ne coûte rien à la machine.
let dessine = -1;
function rendre() { dessine = t; dessiner(); majPanneau(); }

function boucle(maintenant) {
  if (!ouvert) return;
  raf = requestAnimationFrame(boucle);
  // l'horloge suit le temps réel, même si la machine peine ; après un onglet caché, on ne saute pas plus d'une seconde et demie
  const dt = dernier ? Math.min(1.5, (maintenant - dernier) / 1000) : 0;
  dernier = maintenant;
  if (lecture && !fige) {
    t = Math.min(R.fin, t + dt * vitesse);
    if (t >= R.fin) { lecture = false; majCommandes(); }
  }
  if (t !== dessine) rendre();
}

// ── Commandes ──────────────────────────────────────────────────────────────────
function lire() { if (t >= R.fin) t = 0; fige = false; lecture = true; dernier = 0; majCommandes(); }
function pause() { lecture = false; majCommandes(); }
function basculer() { if (lecture) pause(); else if (t >= R.fin) recommencer(true); else lire(); }
function recommencer(lancer = true) { t = 0; dessine = -1; for (const k of ['total', 'ordre', 'vues', 'vuesAge']) delete vu[k]; if (lancer) lire(); else pause(); }
function changerVitesse() { vitesse = VITESSES[(VITESSES.indexOf(vitesse) + 1) % VITESSES.length]; majCommandes(); }
function aller(x) { fige = false; t = Math.max(0, Math.min(R.fin, x)); lecture = false; majCommandes(); if (el) rendre(); }
// Pour fabriquer la vidéo image par image (rejeu/captures.py) : l'instant x, tel qu'il s'affiche pendant la lecture.
function image(x) { fige = true; t = Math.max(0, Math.min(R.fin, x)); lecture = t < R.fin; majCommandes(); if (el) rendre(); }

// BâtIA glisse de la France au Sud-Ouest à l'ouverture : on attend qu'elle soit posée avant de cadrer.
async function attendrePose() {
  const map = carte.map;
  for (let i = 0; i < 80 && (!document.body.classList.contains('pret') || map.isMoving()); i++) await new Promise((ok) => setTimeout(ok, 100));
}

// La séquence part sur un fond entièrement dessiné : on attend la fin du chargement des tuiles (4 s au plus).
function fondPret() {
  const map = carte.map;
  if (map.loaded() && map.areTilesLoaded()) return Promise.resolve();
  return new Promise((ok) => { map.once('idle', ok); setTimeout(ok, 4000); });
}

// Le rejeu montre les données du kit : jamais par-dessus les données réelles.
const enDonneesReelles = () => document.body.classList.contains('monde-reel');

async function ouvrir({ lancer = true } = {}) {
  if (ouvert) { recommencer(lancer); return; }
  if (enDonneesReelles()) return;
  ouvert = true;
  const map = carte.map;
  avant = { centre: map.getCenter(), zoom: map.getZoom(), gestes: GESTES.map((g) => map[g]?.isEnabled?.() ?? false) };
  GESTES.forEach((g) => map[g]?.disable?.());
  avant.couches = COUCHES_CACHEES.filter((id) => map.getLayer(id)).map((id) => [id, map.getLayoutProperty(id, 'visibility') || 'visible']);
  avant.couches.forEach(([id]) => map.setLayoutProperty(id, 'visibility', 'none'));
  document.body.classList.add('rejeu-actif');
  monter();
  mesurer();
  t = 0; lecture = false; dernier = 0;
  raf = requestAnimationFrame(boucle);
  requestAnimationFrame(() => el.classList.add('ouvert'));
  await attendrePose();
  if (!ouvert) return;
  await cadrer();
  await fondPret();
  if (lancer && ouvert) lire();
}

function fermer() {
  if (!ouvert) return;
  ouvert = false; lecture = false;
  cancelAnimationFrame(raf);
  const map = carte.map, x = el;
  x.classList.remove('ouvert');
  setTimeout(() => x.remove(), 600);
  el = null;
  document.body.classList.remove('rejeu-actif');
  GESTES.forEach((g, i) => { if (avant.gestes[i]) map[g]?.enable?.(); });
  avant.couches.forEach(([id, v]) => map.setLayoutProperty(id, 'visibility', v));
  map.flyTo({ center: avant.centre, zoom: avant.zoom, duration: 1100, essential: true });
  bouton?.focus({ preventScroll: true });
}

// Pendant le rejeu, le clavier est à lui : BâtIA ne reçoit rien (pas de décision par mégarde).
function clavier(ev) {
  if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
  if (!ouvert) {
    if ((ev.key === 'l' || ev.key === 'L') && !ev.target.matches?.('input, select, textarea, [contenteditable]')) {
      ev.preventDefault(); ev.stopImmediatePropagation(); ouvrir({ lancer: true });
    }
    return;
  }
  const k = ev.key.length === 1 ? ev.key.toLowerCase() : ev.key;
  const actions = {
    ' ': basculer, k: basculer, l: () => recommencer(true), Home: () => recommencer(false), v: changerVitesse, Escape: fermer,
    ArrowRight: () => { t = Math.min(R.fin, t + 1.5); }, ArrowLeft: () => { t = Math.max(0, t - 1.5); for (const x of ['total', 'ordre']) delete vu[x]; },
  };
  ev.stopImmediatePropagation();
  if (actions[k]) { ev.preventDefault(); actions[k](); }
}

// L'entrée est écrite dans l'en-tête de BâtIA (#rejeu-entree, à gauche de la bascule des mondes) ;
// au téléphone, au pied de la liste ([data-rejeu]). À défaut, un bouton en bas au centre.
function ajouterBouton() {
  bouton = document.getElementById('rejeu-entree');
  if (!bouton) {
    bouton = document.createElement('button');
    bouton.type = 'button';
    bouton.className = 'rejeu-entree rejeu-entree-seule';
    bouton.innerHTML = `${SVG.lecture}<span>Rejeu de 2025</span>`;
    document.body.append(bouton);
  }
  bouton.addEventListener('click', () => ouvrir({ lancer: true }));
  document.addEventListener('click', (ev) => {
    const e = ev.target.closest?.('[data-rejeu]');
    if (!e) return;
    ev.preventDefault();
    ouvrir({ lancer: true });
  });
}

async function demarrer() {
  feuille();
  D = await (await fetch(ICI + 'donnees/rejeu-2025.json', { cache: 'no-store' })).json();
  preparer();
  carte = await attendreCarte();
  ajouterBouton();
  addEventListener('keydown', clavier, true);
  carte.map.on('move', () => { dessine = -1; });
  addEventListener('resize', () => { if (!ouvert) return; mesurer(); cadrer({ anime: false }); });
  window.rejeu = { ouvrir, fermer, lire, pause, recommencer, aller, image, rythme: R, get t() { return t; }, get ouvert() { return ouvert; } };
  const p = new URLSearchParams(location.search).get('rejeu');
  if (p !== null && new URLSearchParams(location.search).get('monde') !== 'reel') ouvrir({ lancer: p !== 'pause' });
}

demarrer().catch((err) => console.warn('[rejeu]', err));
