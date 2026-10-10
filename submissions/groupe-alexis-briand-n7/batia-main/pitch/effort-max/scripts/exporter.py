"""Exporte les diapositives : une capture PNG 1920x1080 par diapositive dans apercus/,
puis diapositives.pdf (une page 1920x1080 par diapositive).
Usage : python3 scripts/exporter.py [url]   (par défaut http://127.0.0.1:4980/index.html)"""
import sys, pathlib
from playwright.sync_api import sync_playwright
from PIL import Image

racine = pathlib.Path(__file__).resolve().parent.parent
url = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:4980/index.html'
sortie = racine / 'apercus'
sortie.mkdir(exist_ok=True)

with sync_playwright() as p:
    nav = p.chromium.launch()
    page = nav.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
    page.goto(url + '?export#1', wait_until='networkidle')
    page.evaluate('document.fonts.ready')
    n = page.evaluate("document.querySelectorAll('.slide').length")
    fichiers = []
    for i in range(1, n + 1):
        page.evaluate(f"location.hash = '#{i}'")
        page.wait_for_timeout(250)
        f = sortie / f'diapositive-{i:02d}.png'
        page.screenshot(path=str(f))
        fichiers.append(f)
    nav.close()

images = [Image.open(f).convert('RGB') for f in fichiers]
images[0].save(racine / 'diapositives.pdf', save_all=True, append_images=images[1:], resolution=72.0, quality=90)
print(f'{n} diapositives exportées')
