# Captures des trois onglets et des fiches, ordinateur et téléphone : python3 outils/captures-onglets.py <dossier> [url]
# Chromium sans écran, rendu logiciel SwiftShader (la carte est en WebGL). Toute requête hors localhost est bloquée et comptée.
# Un seul navigateur, fermé dès la dernière capture.
import sys, asyncio, os
from playwright.async_api import async_playwright

NOM = sys.argv[1] if len(sys.argv) > 1 else 'apres'
URL = sys.argv[2] if len(sys.argv) > 2 else 'http://localhost:4800/'
DOSSIER = os.path.join(os.path.dirname(__file__), '..', 'captures', NOM)
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

async def essayer(pg, selecteur, attente=2200):
    if await pg.locator(selecteur).count() == 0:
        print('absent :', selecteur)
        return False
    await pg.locator(selecteur).first.click()
    await pg.wait_for_timeout(attente)
    return True

async def parcours(pg, prefixe):
    await pg.goto(URL)
    await pg.wait_for_selector('.carte-prete', timeout=30000)
    await pg.wait_for_timeout(5200)
    await capture(pg, f'{prefixe}-1-pannes')
    if await essayer(pg, '.ligne', 2800):
        await capture(pg, f'{prefixe}-2-fiche-equipement')
    await pg.goto(URL + '#/residence/RES-D')
    await pg.wait_for_timeout(3200)
    await capture(pg, f'{prefixe}-3-fiche-residence')
    await pg.goto(URL + '#/')
    await pg.wait_for_timeout(1500)
    if await essayer(pg, '[data-lentille="energie"]', 2600):
        await capture(pg, f'{prefixe}-4-energie')
    if await essayer(pg, '[data-lentille="renovations"]', 2600):
        await capture(pg, f'{prefixe}-5-renovations')
        if await essayer(pg, '.op-ligne', 2800):
            await capture(pg, f'{prefixe}-6-fiche-operation')

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=ARGS)
        try:
            pg, st = await page_pour(b, 1440, 900)
            await parcours(pg, 'ordi')
            print('ordinateur : requêtes vers Internet', len(st['dehors']), '· erreurs', st['erreurs'][:5])
            await pg.context.close()
            pg, st = await page_pour(b, 390, 844, mobile=True)
            await parcours(pg, 'tel')
            print('téléphone : requêtes vers Internet', len(st['dehors']), '· erreurs', st['erreurs'][:5])
            await pg.context.close()
            # projecteur : 1280 × 720, la file et les rénovations, puis la page Méthode
            pg, st = await page_pour(b, 1280, 720)
            await pg.goto(URL)
            await pg.wait_for_selector('.carte-prete', timeout=30000)
            await pg.wait_for_timeout(5200)
            await capture(pg, 'projecteur-1-pannes')
            if await essayer(pg, '[data-onglet="surveiller"]', 900):
                await capture(pg, 'projecteur-2-a-surveiller')
            if await essayer(pg, '[data-lentille="renovations"]', 2600):
                await capture(pg, 'projecteur-3-renovations')
            await pg.goto(URL + '#/methode')
            await pg.wait_for_timeout(2500)
            await capture(pg, 'projecteur-4-methode')
            print('projecteur : requêtes vers Internet', len(st['dehors']), '· erreurs', st['erreurs'][:5])
        finally:
            await b.close()

asyncio.run(main())
