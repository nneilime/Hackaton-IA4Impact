# Captures du déroulé complet de la démonstration : kit, rejeu, bascule, réel, Sous le capot (une adresse, son verdict), retour.
#   python3 outils/captures-demo.py [projecteur|telephone|tout] [url]   → captures/demo/
# Chromium sans écran, rendu logiciel SwiftShader (la carte est en WebGL). Toute requête hors de la machine est bloquée
# et comptée. Un seul navigateur, fermé dès la dernière capture.
import sys, asyncio, os
from playwright.async_api import async_playwright

QUOI = sys.argv[1] if len(sys.argv) > 1 else 'tout'
URL = sys.argv[2] if len(sys.argv) > 2 else 'http://localhost:4860/'
DOSSIER = os.path.join(os.path.dirname(__file__), '..', 'captures', 'demo')
os.makedirs(DOSSIER, exist_ok=True)
ARGS = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']


async def page_pour(b, largeur, hauteur, mobile=False):
    ctx = await b.new_context(viewport={'width': largeur, 'height': hauteur}, device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile)
    pg = await ctx.new_page()
    stats = {'dehors': [], 'erreurs': []}

    async def filtre(route):
        u = route.request.url
        if u.startswith(('http://localhost', 'http://127.0.0.1', 'data:', 'blob:')):
            await route.continue_()
        else:
            stats['dehors'].append(u)
            await route.abort()
    await pg.route('**/*', filtre)
    pg.on('pageerror', lambda e: stats['erreurs'].append(str(e)))
    pg.on('console', lambda m: stats['erreurs'].append(m.text) if m.type == 'error' and 'favicon' not in m.text else None)
    return ctx, pg, stats


async def capture(pg, nom):
    chemin = os.path.join(DOSSIER, f'{nom}.png')
    await pg.screenshot(path=chemin, timeout=120000)
    print('capture', os.path.relpath(chemin))


async def cliquer(pg, selecteur, attente):
    loc = pg.locator(selecteur)
    if await loc.count() == 0 or not await loc.first.is_visible():
        print('ABSENT OU INVISIBLE :', selecteur)
        return False
    await loc.first.click()
    await pg.wait_for_timeout(attente)
    return True


async def deroule(pg, p, tel=False):
    await pg.goto(URL)
    await pg.wait_for_selector('.carte-prete', timeout=40000)
    await pg.wait_for_timeout(5500)
    await capture(pg, f'{p}-01-kit-pannes')
    if await cliquer(pg, '#file .ligne', 3000):
        await capture(pg, f'{p}-02-kit-fiche')
    await pg.keyboard.press('Escape')
    await pg.wait_for_timeout(800)
    if await cliquer(pg, '[data-lentille="energie"]', 2500):
        await capture(pg, f'{p}-03-kit-energie')
    if await cliquer(pg, '[data-lentille="renovations"]', 2500):
        await capture(pg, f'{p}-04-kit-renovations')
    await cliquer(pg, '[data-lentille="pannes"]', 1500)
    # le rejeu : par le bouton de l'en-tête (au téléphone, au pied de la liste)
    entree = '#file [data-rejeu]' if tel else '#rejeu-entree'
    if tel:
        await pg.evaluate("document.querySelector('#file [data-rejeu]')?.scrollIntoView()")
        await pg.wait_for_timeout(400)
    if await cliquer(pg, entree, 9000):
        await capture(pg, f'{p}-05-rejeu-milieu')
        await pg.wait_for_function('window.rejeu && window.rejeu.t >= window.rejeu.rythme.fin - 0.05', timeout=60000)
        await pg.wait_for_timeout(1500)
        await capture(pg, f'{p}-06-rejeu-fin')
        await pg.keyboard.press('Escape')
        await pg.wait_for_timeout(2000)
        await capture(pg, f'{p}-07-retour-kit')
    # la bascule
    if await cliquer(pg, '[data-monde="reel"]', 2600):
        await capture(pg, f'{p}-08-bascule-onde')
        await pg.wait_for_timeout(5000)
        await capture(pg, f'{p}-09-reel')
        if await cliquer(pg, '#reel-panneau .ligne', 4500):
            await capture(pg, f'{p}-10-reel-fiche')
        # Sous le capot : la première adresse prête (34 boulevard de l'Embouchure), son verdict, puis le retour à la carte
        if await cliquer(pg, '.capot-entree', 2500):
            await pg.wait_for_selector('#pretes li', timeout=20000)
            await capture(pg, f'{p}-11-capot')
            if tel:
                await pg.locator('#pretes li').first.click()
            else:
                await pg.keyboard.press('ArrowDown')
                await pg.wait_for_timeout(400)
                await pg.keyboard.press('Enter')
            await pg.wait_for_timeout(7000)
            await capture(pg, f'{p}-12-capot-course')
            await pg.wait_for_selector('#verdict:not([hidden])', timeout=90000)
            await pg.wait_for_timeout(2200)
            await capture(pg, f'{p}-13-capot-verdict')
            print(p, 'verdict :', (await pg.locator('#verdict').inner_text()).replace('\n', ' | ')[:160])
            # au téléphone, le bouton « ← BâtIA » ; au clavier, Échap
            if tel:
                await pg.evaluate('scrollTo(0, 0)')
                await cliquer(pg, '#marque', 0)
            else:
                await pg.keyboard.press('Escape')
            await pg.wait_for_function("document.body.classList.contains('monde-reel')", timeout=30000)
            await pg.wait_for_timeout(4000)
            await capture(pg, f'{p}-14-retour-reel')
        if await cliquer(pg, '[data-monde="kit"]', 4000):
            await capture(pg, f'{p}-15-retour-kit')


async def main():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(args=ARGS)
        try:
            ecrans = []
            if QUOI in ('tout', 'projecteur'):
                ecrans.append(('projecteur', 1920, 1080, False))
            if QUOI in ('tout', 'telephone'):
                ecrans.append(('telephone', 390, 844, True))
            for nom, l, h, mobile in ecrans:
                ctx, pg, stats = await page_pour(b, l, h, mobile)
                await deroule(pg, nom, tel=mobile)
                print(nom, 'requêtes hors de la machine :', len(stats['dehors']), stats['dehors'][:3])
                print(nom, 'erreurs :', stats['erreurs'][:6])
                await ctx.close()
        finally:
            await b.close()

asyncio.run(main())
