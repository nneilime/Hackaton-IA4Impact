"""Détoure les icônes de lieux générées par NanoBanana (scripts/landmark-raw/<id>.png, fond blanc uni)
et les écrit en PNG transparent, recadrées et réduites, dans public/landmarks/<id>.png.

Le fond est retiré par remplissage depuis les bords (pas par seuil global) : le blanc *dans* l'icône
(un mur clair, un nuage) est conservé tant qu'il ne touche pas le bord de l'image.

    python3 scripts/cutout-landmarks.py        (depuis frontend/)
"""
from collections import deque
from pathlib import Path
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "scripts" / "landmark-raw", ROOT / "public" / "landmarks"
SIZE = 160  # côté max en px : affichée à ~56 px sur la carte, nette sur écran Retina
TOL = 28  # écart max au blanc pour être considéré comme fond


def cutout(src: Path) -> Image.Image:
    im = Image.open(src).convert("RGB")
    w, h = im.size
    px = im.load()
    bg = bytearray(w * h)
    near_white = lambda p: 255 * 3 - sum(p) <= TOL * 3
    q = deque((x, y) for x in range(w) for y in (0, h - 1))
    q.extend((x, y) for y in range(h) for x in (0, w - 1))
    while q:
        x, y = q.popleft()
        i = y * w + x
        if bg[i] or not near_white(px[x, y]):
            continue
        bg[i] = 1
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not bg[ny * w + nx]:
                q.append((nx, ny))
    # Masque adouci d'un pixel pour éviter le liseré blanc en escalier
    mask = Image.frombytes("L", (w, h), bytes(0 if b else 255 for b in bg)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1))
    out = im.convert("RGBA")
    out.putalpha(mask)
    out = out.crop(mask.point(lambda a: 255 if a > 8 else 0).getbbox())
    out.thumbnail((SIZE, SIZE), Image.LANCZOS)
    return out


OUT.mkdir(parents=True, exist_ok=True)
for src in sorted(RAW.glob("*.*")):
    cutout(src).save(OUT / f"{src.stem}.png", optimize=True)
    print("ok", src.stem)
