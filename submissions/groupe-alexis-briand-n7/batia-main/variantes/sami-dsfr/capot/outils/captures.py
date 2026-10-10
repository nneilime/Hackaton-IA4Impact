# Captures de « Sous le capot » à chaque étape de la cascade, et vidéo de la séquence.
# python3 capot/outils/captures.py [base] [reseau|coupe] [largeur] [hauteur] [nombre de ↓] [prefixe] [video]
# Chromium sans écran, rendu logiciel SwiftShader (la carte est en WebGL). Un seul navigateur, fermé à la fin.
import sys, asyncio, os, time
from playwright.async_api import async_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:4861'
RESEAU = (sys.argv[2] if len(sys.argv) > 2 else 'reseau') == 'reseau'
L = int(sys.argv[3]) if len(sys.argv) > 3 else 1920
H = int(sys.argv[4]) if len(sys.argv) > 4 else 1080
TOUCHE = sys.argv[5] if len(sys.argv) > 5 else '1'
PREFIXE = sys.argv[6] if len(sys.argv) > 6 else 'projecteur'
VIDEO = len(sys.argv) > 7 and sys.argv[7] == 'video'
DOSSIER = os.path.join(os.path.dirname(__file__), '..', '..', 'captures')
os.makedirs(DOSSIER, exist_ok=True)
ARGS = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=ARGS)
        opts = dict(viewport={'width': L, 'height': H})
        if VIDEO: opts['record_video_dir'] = os.path.join(DOSSIER, 'video-brute'); opts['record_video_size'] = {'width': L, 'height': H}
        ctx = await b.new_context(**opts)
        pg = await ctx.new_page()
        dehors, erreurs = [], []
        async def filtre(route):
            u = route.request.url
            if u.startswith(('http://localhost', 'http://127.0.0.1', 'data:', 'blob:')) or RESEAU: await route.continue_()
            else: dehors.append(u); await route.abort()
        await pg.route('**/*', filtre)
        pg.on('pageerror', lambda e: erreurs.append(str(e)))
        pg.on('console', lambda m: erreurs.append(m.text) if m.type == 'error' else None)
        await pg.goto(BASE + '/capot/')
        await pg.wait_for_timeout(2500)
        await pg.screenshot(path=os.path.join(DOSSIER, f'{PREFIXE}-00-vide.png'))
        if VIDEO:
            # Dans la vidéo, l'adresse est tapée comme le fera le présentateur.
            pretes = await pg.evaluate("fetch('/capot/enregistrements/index.json').then((r) => r.json())")
            await pg.keyboard.type(pretes[int(TOUCHE) - 1]['saisie'], delay=55)
        else:
            for _ in range(int(TOUCHE)): await pg.keyboard.press('ArrowDown'); await pg.wait_for_timeout(150)
        await pg.wait_for_timeout(500)
        await pg.screenshot(path=os.path.join(DOSSIER, f'{PREFIXE}-01-adresse-tapee.png'))
        await pg.keyboard.press('Enter')
        # Une capture à chaque changement visible (une ligne de plus, la photo, le verdict), nommée au temps réel.
        t0, vu, k = time.time(), None, 2
        while time.time() - t0 < 30:
            etat = await pg.evaluate("[document.querySelectorAll('.ligne:not(.attente)').length, !document.querySelector('#photo').hidden, !document.querySelector('#verdict').hidden]")
            if etat != vu:
                vu = etat
                if not VIDEO:
                    n, photo, verdict = etat
                    nom = f"{PREFIXE}-{k:02d}-{time.time() - t0:04.1f}s-{n}lignes{'-photo' if photo else ''}{'-verdict' if verdict else ''}.png"
                    await pg.screenshot(path=os.path.join(DOSSIER, nom)); k += 1
                if etat[2]: break
            await pg.wait_for_timeout(100)
        # La vidéo prend du retard sous rendu logiciel : on la laisse finir sur le verdict.
        await pg.wait_for_timeout(8000 if VIDEO else 2500)
        if not VIDEO: await pg.screenshot(path=os.path.join(DOSSIER, f'{PREFIXE}-{k:02d}-fin.png'))
        print(f'verdict après {time.time() - t0:.1f} s')
        signe = await pg.evaluate("[...document.querySelectorAll('#signe i')].map(i => i.title).join(' | ')")
        bilan = await pg.evaluate("document.querySelector('#bilan').innerText")
        verdict = await pg.evaluate("document.querySelector('#verdict').innerText")
        print('signe :', signe); print('bilan :', bilan); print('verdict :', verdict.replace('\n', ' / '))
        print('requêtes bloquées :', len(dehors)); print('erreurs :', erreurs[:8])
        chemin_video = await pg.video.path() if VIDEO else None
        await ctx.close()
        await b.close()
        if chemin_video:
            os.replace(chemin_video, os.path.join(DOSSIER, 'sequence.webm'))
            print('vidéo :', os.path.join(DOSSIER, 'sequence.webm'))
asyncio.run(main())
