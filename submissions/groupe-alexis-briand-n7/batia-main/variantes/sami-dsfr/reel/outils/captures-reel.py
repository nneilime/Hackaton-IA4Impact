# Captures du mode « Données réelles », ordinateur et téléphone : python3 reel/outils/captures-reel.py [url]
# Chromium sans écran, rendu logiciel SwiftShader (la carte est en WebGL). Toute requête hors localhost est bloquée et comptée.
# Un seul navigateur, fermé dès les captures prises.
import sys, asyncio, os
from playwright.async_api import async_playwright

URL = (sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:4811/').rstrip('/') + '/'
IMMEUBLE = sys.argv[2] if len(sys.argv) > 2 else 'bdnb-bg-ZFCY-1WR3-NKQ5'
DOSSIER = os.path.join(os.path.dirname(__file__), '..', '..', 'captures')
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
    return ctx, pg, stats

async def capture(pg, nom):
    chemin = os.path.join(DOSSIER, f'{nom}.png')
    await pg.screenshot(path=chemin)
    print('capture', os.path.normpath(chemin), flush=True)

async def attendre_reel(pg):
    await pg.wait_for_function('window.foraine && window.foraine.reel && window.foraine.reel.S.monde === "reel" && !window.foraine.reel.S.enCours', timeout=60000)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=ARGS)
        try:
            # ── Ordinateur ──
            ctx, pg, st = await page_pour(b, 1440, 900)
            await pg.goto(URL)
            await pg.wait_for_selector('body.bascule-prete', timeout=60000)
            await pg.wait_for_timeout(4200)
            await capture(pg, 'reel-ordi-1-kit')
            await pg.click('[data-monde="reel"]')
            await pg.wait_for_timeout(2600)
            await capture(pg, 'reel-ordi-2-bascule')
            await attendre_reel(pg)
            await pg.wait_for_timeout(1800)
            await capture(pg, 'reel-ordi-3-sud-ouest')
            await pg.click('[data-echelle="france"]')
            await pg.wait_for_timeout(2600)
            await capture(pg, 'reel-ordi-4-france')
            await pg.click('[data-echelle="toulouse"]')
            await pg.wait_for_timeout(2800)
            await capture(pg, 'reel-ordi-5-metropole')
            await pg.evaluate('(id) => window.foraine.reel.ouvrir(id)', IMMEUBLE)
            await pg.wait_for_timeout(3200)
            await capture(pg, 'reel-ordi-6-immeuble')
            await pg.click('.re-plus summary')
            await pg.wait_for_timeout(500)
            await capture(pg, 'reel-ordi-7-tout-voir')
            await pg.evaluate('() => window.foraine.reel.ouvrir("bdnb-bg-NCEF-432T-NKZ8")')
            await pg.wait_for_timeout(3600)
            await capture(pg, 'reel-ordi-9-urgent')
            await pg.evaluate('() => window.foraine.reel.ouvrir("commune-31555")')
            await pg.wait_for_timeout(3600)
            await capture(pg, 'reel-ordi-10-groupe')
            await pg.click('[data-monde="kit"]')
            await pg.wait_for_timeout(2800)
            await capture(pg, 'reel-ordi-8-retour-kit')
            print('ordinateur : requêtes hors machine', len(st['dehors']), st['dehors'][:3], '· erreurs', st['erreurs'][:5], flush=True)
            await ctx.close()

            # ── Téléphone : la bascule, puis les trois échelles et un immeuble ──
            ctx, pg, st = await page_pour(b, 390, 844, mobile=True)
            await pg.goto(URL)
            await pg.wait_for_selector('body.bascule-prete', timeout=60000)
            await pg.wait_for_timeout(3500)
            await capture(pg, 'reel-tel-1-kit')
            await pg.click('[data-monde="reel"]')
            await pg.wait_for_timeout(2600)
            await capture(pg, 'reel-tel-2-bascule')
            await attendre_reel(pg)
            await pg.wait_for_timeout(1800)
            await capture(pg, 'reel-tel-3-sud-ouest')
            await pg.evaluate('() => window.foraine.reel.cadrer("france", { duree: 10 })')
            await pg.wait_for_timeout(1800)
            await capture(pg, 'reel-tel-4-france')
            await pg.evaluate('() => window.foraine.reel.cadrer("toulouse", { duree: 10 })')
            await pg.wait_for_timeout(1800)
            await capture(pg, 'reel-tel-5-metropole')
            await pg.evaluate('(id) => window.foraine.reel.ouvrir(id)', IMMEUBLE)
            await pg.wait_for_timeout(3200)
            await capture(pg, 'reel-tel-6-immeuble')
            print('téléphone : requêtes hors machine', len(st['dehors']), st['dehors'][:3], '· erreurs', st['erreurs'][:5], flush=True)
            await ctx.close()
        finally:
            await b.close()

asyncio.run(main())
