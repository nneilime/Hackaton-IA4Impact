for (const motif of CE.motifs) document.querySelector('#motif').add(new Option(motif, motif));
const steps = [...document.querySelectorAll('.step')];
let current = 0, changes = 0;
function render() {
  steps.forEach((step, i) => step.classList.toggle('active', i === current));
  document.querySelector('#back').disabled = current === 0;
  document.querySelector('#next').textContent = current === steps.length - 1 ? 'Terminer la démo' : 'Étape suivante';
}
document.querySelector('#next').onclick = () => {
  if (current < steps.length - 1) { current++; render(); }
  else document.querySelector('#end').textContent = 'Démo terminée. Aucun formulaire envoyé, aucune donnée transmise.';
};
document.querySelector('#back').onclick = () => { current = Math.max(0, current - 1); render(); };
document.querySelector('#demo-form').onsubmit = event => event.preventDefault();
document.querySelector('#demo-form').addEventListener('change', () => {
  document.querySelector('#events').textContent = `${++changes} changement(s) reçu(s) par le formulaire fictif.`;
});
// Le lanceur peut réafficher un panneau fermé dans cet onglet.
chrome.tabs.getCurrent().then(tab => {
  chrome.runtime.onMessage.addListener((request, sender, respond) => {
    if (sender.id !== chrome.runtime.id || request.type !== 'ce-show' || request.demoTabId !== tab.id) return;
    CEPanel.show(); respond({ok: true});
  });
});
render();
