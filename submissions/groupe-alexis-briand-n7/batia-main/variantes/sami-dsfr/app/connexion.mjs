const form = document.querySelector('form');
const champId = form.elements.identifiant;
const champMdp = form.elements.motdepasse;
const erreur = document.querySelector('.erreur');

function nomDepuis(identifiant) {
  const local = identifiant.split('@')[0].replace(/[._-]+/g, ' ').trim();
  const mots = local.split(/\s+/).filter(Boolean).map((m) => m[0].toUpperCase() + m.slice(1).toLowerCase());
  return mots.join(' ') || 'Compte de démonstration';
}

function initiales(nom) {
  const mots = nom.split(/\s+/).filter(Boolean);
  return ((mots[0]?.[0] || '') + (mots[mots.length - 1]?.[0] || '')).toUpperCase() || 'BA';
}

form.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const identifiant = champId.value.trim();
  const mdp = champMdp.value;
  if (!identifiant || !mdp) {
    erreur.textContent = 'Renseignez un identifiant et un mot de passe.';
    erreur.hidden = false;
    (identifiant ? champMdp : champId).focus();
    return;
  }
  erreur.hidden = true;
  form.classList.add('envoi');
  let reponse;
  try { reponse = await fetch('/api/connexion', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ motdepasse: mdp }) }); } catch { reponse = null; }
  if (reponse && reponse.status === 401) {
    form.classList.remove('envoi');
    erreur.textContent = 'Mot de passe incorrect.';
    erreur.hidden = false;
    champMdp.focus(); champMdp.select();
    return;
  }
  const nom = nomDepuis(identifiant);
  const role = form.elements.role.value;
  localStorage.setItem('foraine.compte', JSON.stringify({ identifiant, nom, initiales: initiales(nom), le: new Date().toISOString() }));
  localStorage.setItem('foraine.role', role);
  const suite = new URLSearchParams(location.search).get('suite');
  const cible = suite && suite.startsWith('/') && !suite.startsWith('//') && !suite.startsWith('/connexion') ? suite : '/';
  setTimeout(() => location.replace(cible), 250);
});

document.querySelector('[data-voir]').addEventListener('click', (ev) => {
  const voir = champMdp.type === 'password';
  champMdp.type = voir ? 'text' : 'password';
  ev.currentTarget.setAttribute('aria-pressed', String(voir));
  ev.currentTarget.textContent = voir ? 'Masquer' : 'Afficher';
});

if (localStorage.getItem('foraine.compte')) {
  try { champId.value = JSON.parse(localStorage.getItem('foraine.compte')).identifiant || champId.value; } catch {}
}
const roleActuel = localStorage.getItem('foraine.role');
if (roleActuel && form.elements.role) [...form.elements.role].forEach((r) => { r.checked = r.value === roleActuel; });
champMdp.focus();
