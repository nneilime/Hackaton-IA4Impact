# Captures du rejeu de 2025 : python3 rejeu/captures.py [url] [--video] [--sans-photos]
# Début, milieu et fin de la séquence, au format projecteur (1920 × 1080) et au téléphone ;
# avec --video, la séquence complète, image par image, dans captures/rejeu.webm (ffmpeg).
# Chromium sans écran, rendu logiciel SwiftShader (la carte est en WebGL). Un seul navigateur à la fois,
# fermé dès la fin. Toute requête hors localhost est bloquée et comptée.
import asyncio
import os
import shutil
import subprocess
import sys

from playwright.async_api import async_playwright

ARGS_POS = [a for a in sys.argv[1:] if not a.startswith('--')]
URL = ARGS_POS[0] if ARGS_POS else 'http://localhost:4850/'
DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'captures')
os.makedirs(DOSSIER, exist_ok=True)
ARGS = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
# Instants de la séquence (secondes à la vitesse 1, voir R dans rejeu.mjs)
MOMENTS = [('1-debut', 2.9), ('2-milieu', 10.3), ('3-fin', 20)]


async def page(b, largeur, hauteur, mobile=False, **opts):
    opts.setdefault('device_scale_factor', 2 if mobile else 1)
    ctx = await b.new_context(viewport={'width': largeur, 'height': hauteur}, is_mobile=mobile, has_touch=mobile, **opts)
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
    pg.on('console', lambda m: stats['erreurs'].append(m.text) if m.type == 'error' else None)
    return ctx, pg, stats


async def attendre_carte(pg):
    await pg.wait_for_selector('.carte-prete', timeout=60000)
    await pg.wait_for_function('window.foraine && window.foraine.carte && window.foraine.carte.map.loaded()', timeout=60000)


async def photos(b):
    for appareil, (l, h), mobile in (('projecteur', (1920, 1080), False), ('telephone', (390, 844), True)):
        ctx, pg, st = await page(b, l, h, mobile)
        await pg.goto(URL + '?rejeu=pause')
        await attendre_carte(pg)
        await pg.wait_for_function('window.rejeu && window.rejeu.ouvert', timeout=60000)
        await pg.wait_for_timeout(2600)
        await pg.wait_for_function('window.foraine.carte.map.areTilesLoaded()', timeout=30000)
        for nom, t in MOMENTS:
            await pg.evaluate(f'window.rejeu.aller({t})')
            await pg.wait_for_timeout(1300)
            chemin = os.path.join(DOSSIER, f'rejeu-{appareil}-{nom}.png')
            await pg.screenshot(path=chemin)
            print('capture', os.path.relpath(chemin))
        print(appareil, ': requêtes vers Internet', len(st['dehors']), '· erreurs', st['erreurs'][:5])
        await ctx.close()


async def video(b, largeur=1920, hauteur=1080, echelle=2 / 3, ips=6):
    """La séquence complète, image par image : chaque instant est rendu par window.rejeu.image(t),
    photographié, puis ffmpeg assemble les images à la vitesse ×1. Le magnétoscope de Playwright
    perd des images quand la machine est chargée ; ce chemin-là n'en perd aucune.
    La mise en page est celle du projecteur (1920 × 1080), réduite d'un tiers : vidéo en 1280 × 720."""
    dossier = os.path.join(DOSSIER, 'video-images')
    shutil.rmtree(dossier, ignore_errors=True)
    os.makedirs(dossier)
    ctx, pg, st = await page(b, largeur, hauteur, device_scale_factor=echelle)
    await pg.goto(URL + '?rejeu=pause')
    await attendre_carte(pg)
    await pg.wait_for_function('window.rejeu && window.rejeu.ouvert', timeout=60000)
    await pg.wait_for_timeout(2600)
    await pg.wait_for_function('window.foraine.carte.map.areTilesLoaded()', timeout=30000)
    fin = await pg.evaluate('window.rejeu.rythme.fin')
    n = int(round(fin * ips))
    for i in range(n + 1):
        await pg.evaluate(f'window.rejeu.image({i / ips})')
        await pg.screenshot(path=os.path.join(dossier, f'{i:04d}.jpg'), type='jpeg', quality=90)
    await ctx.close()
    sortie = os.path.join(DOSSIER, 'rejeu.webm')
    # une seconde sur le 1er janvier avant de partir, trois secondes sur l'image finale
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(ips), '-i', os.path.join(dossier, '%04d.jpg'),
                    '-vf', 'tpad=start_mode=clone:start_duration=1:stop_mode=clone:stop_duration=3',
                    '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '33', '-row-mt', '1', '-pix_fmt', 'yuv420p', sortie], check=True)
    shutil.rmtree(dossier, ignore_errors=True)
    print('vidéo', os.path.relpath(sortie), f'· {n + 1} images à {ips} par seconde')
    print('vidéo : requêtes vers Internet', len(st['dehors']), '· erreurs', st['erreurs'][:5])


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=ARGS)
        try:
            if '--sans-photos' not in sys.argv:
                await photos(b)
            if '--video' in sys.argv:
                await video(b)
        finally:
            await b.close()


asyncio.run(main())
