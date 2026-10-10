# python3 outils/captures.py [dossier] — captures réelles de l'application (ordinateur et téléphone).
# À lancer de préférence contre un serveur à l'état séparé : ETAT_LOCAL=/tmp/assise PORT=4398 node serveur.mjs, puis BASE=http://localhost:4398.
import sys, os
from playwright.sync_api import sync_playwright
BASE = os.environ.get('BASE', 'http://localhost:4321')
OUT = sys.argv[1] if len(sys.argv) > 1 else 'captures'
os.makedirs(OUT, exist_ok=True)
erreurs = []
with sync_playwright() as p:
    nav = p.chromium.launch()
    for nom, vp, mobile in [('ordi', {'width': 1440, 'height': 900}, False), ('tel', {'width': 390, 'height': 844}, True)]:
        ctx = nav.new_context(viewport=vp, device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile, locale='fr-FR')
        page = ctx.new_page()
        page.on('pageerror', lambda e, nom=nom: erreurs.append(f'{nom}: {e}'))
        page.on('console', lambda m, nom=nom: m.type == 'error' and erreurs.append(f'{nom} console: {m.text}'))
        page.goto(BASE + '/#/'); page.wait_for_selector('.assise'); page.wait_for_timeout(400)
        page.screenshot(path=f'{OUT}/{nom}-1-decider.png')
        page.click('.assise >> nth=0'); page.wait_for_selector('#zone-decision'); page.wait_for_timeout(500)
        page.screenshot(path=f'{OUT}/{nom}-2-fiche-equipement.png')
        page.click('#fiche [data-lgt]'); page.wait_for_selector('.demande, .mini-liste'); page.wait_for_timeout(500)
        page.screenshot(path=f'{OUT}/{nom}-3-fiche-logement.png')
        page.keyboard.press('Escape'); page.wait_for_timeout(300)
        # quatre décisions de démonstration le temps d'une capture, puis retirées
        ids = page.evaluate("""async () => {
          const e = await (await fetch('/api/etat')).json();
          const ids = e.equipements.filter((x) => x.niveau === 'prioritaire').sort((a, b) => a.rang - b.rang).slice(0, 4).map((x) => x.id);
          const choix = ['remplacer', 'remplacer', 'diagnostiquer', 'surveiller'];
          for (const [i, id] of ids.entries()) await fetch('/api/decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ equipement: id, decision: choix[i], note: '', auteur: 'AB' }) });
          return ids;
        }""")
        page.reload(); page.wait_for_selector('.assise'); page.wait_for_timeout(300)
        page.click('[data-onglet="decides"]'); page.wait_for_timeout(400)
        page.screenshot(path=f'{OUT}/{nom}-1b-decides.png')
        page.evaluate("""async (ids) => { for (const id of ids) await fetch('/api/decision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ equipement: id, decision: null }) }); }""", ids)
        page.goto(BASE + '/#/parc'); page.wait_for_selector('.leaflet-container, .carte-prete'); page.wait_for_timeout(2800)
        page.screenshot(path=f'{OUT}/{nom}-4-parc.png')
        page.click('[data-zoom="toulouse"]'); page.wait_for_timeout(2200)
        page.screenshot(path=f'{OUT}/{nom}-5-parc-toulouse.png')
        page.goto(BASE + '/#/residence/RES-F'); page.wait_for_timeout(600)
        page.screenshot(path=f'{OUT}/{nom}-6-residence.png')
        page.goto(BASE + '/#/energie'); page.wait_for_timeout(600)
        page.screenshot(path=f'{OUT}/{nom}-7-energie.png')
        page.goto(BASE + '/#/methode'); page.wait_for_timeout(600)
        page.screenshot(path=f'{OUT}/{nom}-8-methode.png', full_page=True)
        ctx.close()
    nav.close()
print('erreurs:', erreurs or 'aucune')
