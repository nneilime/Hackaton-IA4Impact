# Captures de BâtIA, ordinateur et téléphone : python3 outils/captures.py [url]
# Chromium sans écran, rendu logiciel SwiftShader (la carte est en WebGL). Toute requête hors localhost est bloquée et comptée.
import sys, asyncio, os
from playwright.async_api import async_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:4720/'
DOSSIER = os.path.join(os.path.dirname(__file__), '..', 'captures')
os.makedirs(DOSSIER, exist_ok=True)
ARGS = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']

async def page_pour(b, largeur, hauteur, mobile=False):
    ctx = await b.new_context(viewport={'width': largeur, 'height': hauteur}, device_scale_factor=1 if not mobile else 2, is_mobile=mobile, has_touch=mobile)
    pg = await ctx.new_page()
    stats = {'dehors': [], 'erreurs': []}
    async def filtre(route):
        u = route.request.url
        if u.startswith(('http://localhost', 'http://127.0.0.1', 'data:', 'blob:')): await route.continue_()
        else: stats['dehors'].append(u); await route.abort()
    await pg.route('**/*', filtre)
    pg.on('pageerror', lambda e: stats['erreurs'].append(str(e)))
    pg.on('console', lambda m: stats['erreurs'].append(m.text) if m.type == 'error' else None)
    return pg, stats

async def capture(pg, nom):
    chemin = os.path.join(DOSSIER, f'{nom}.png')
    await pg.screenshot(path=chemin)
    print('capture', chemin)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=ARGS)
        # ── Ordinateur ──
        pg, st = await page_pour(b, 1440, 900)
        await pg.goto(URL)
        await pg.wait_for_selector('.carte-prete', timeout=30000)
        await pg.wait_for_timeout(1200)
        await capture(pg, 'ordi-1-ouverture')
        await pg.wait_for_timeout(3500)
        await capture(pg, 'ordi-2-parc-et-file')
        await pg.click('.ligne >> nth=0')
        await pg.wait_for_timeout(2600)
        await capture(pg, 'ordi-3-fiche-equipement')
        await pg.click('[data-aller^="logement/"]')
        await pg.wait_for_timeout(1800)
        await capture(pg, 'ordi-4-fiche-logement')
        await pg.goto(URL + '#/residence/RES-F')
        await pg.wait_for_timeout(3000)
        await capture(pg, 'ordi-5-residence')
        await pg.click('[data-lentille="energie"]')
        await pg.wait_for_timeout(2000)
        await capture(pg, 'ordi-6-energie')
        await pg.goto(URL + '#/')
        await pg.wait_for_timeout(1500)
        await pg.click('[data-echelle="toulouse"]')
        await pg.wait_for_timeout(2600)
        await capture(pg, 'ordi-7-metropole')
        await pg.goto(URL + '#/methode')
        await pg.wait_for_timeout(3500)
        await capture(pg, 'ordi-8-methode')
        print('ordinateur : requêtes vers Internet', len(st['dehors']), '· erreurs', st['erreurs'][:5])
        # ── Téléphone ──
        pg, st = await page_pour(b, 390, 844, mobile=True)
        await pg.goto(URL)
        await pg.wait_for_selector('.carte-prete', timeout=30000)
        await pg.wait_for_timeout(5000)
        await capture(pg, 'tel-1-parc')
        await pg.click('.ligne >> nth=0')
        await pg.wait_for_timeout(2500)
        await capture(pg, 'tel-2-fiche')
        print('téléphone : requêtes vers Internet', len(st['dehors']), '· erreurs', st['erreurs'][:5])
        await b.close()

asyncio.run(main())
