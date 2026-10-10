# Vérifie que la carte ne demande rien à Internet : toute requête hors localhost est bloquée et comptée.
import sys, asyncio
from playwright.async_api import async_playwright
URL = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:4500/#/parc'
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        pg = await b.new_page(viewport={'width': 1280, 'height': 900})
        dehors, locales = [], 0
        async def filtre(route):
            nonlocal locales
            u = route.request.url
            if u.startswith('http://localhost') or u.startswith('http://127.0.0.1') or u.startswith('data:') or u.startswith('blob:'):
                locales += 1; await route.continue_()
            else:
                dehors.append(u); await route.abort()
        await pg.route('**/*', filtre)
        await pg.goto(URL)
        await pg.wait_for_timeout(6000)
        for cle in ['toulouse']:
            await pg.click(f'[data-zoom="{cle}"]'); await pg.wait_for_timeout(3500)
        await pg.screenshot(path='/tmp/sans-internet.png')
        print(f'requêtes locales : {locales} ; vers Internet : {len(dehors)}')
        for u in dehors[:10]: print('  ', u)
        await b.close()
asyncio.run(main())
