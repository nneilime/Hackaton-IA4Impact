"""Photos réelles prises le long des voies TER d'Occitanie, pour la fenêtre du train simulé.

Pour chaque case (~6 km) traversée par une ligne du réseau, recherche géographique sur Wikimedia Commons, puis tri :
JPEG au format paysage seulement, sans cartes, blasons, vues de l'ISS ni photos d'intérieur, une seule photo par
série (« Église X 001 », « Église X 002 »…), en privilégiant celles dont le titre parle de paysage. Résultat dans
public/trackside.json (positions, titres, crédits ; les images restent chez Wikimedia et sont chargées depuis
upload.wikimedia.org). Fait une fois ici plutôt qu'en direct dans le navigateur : l'API Commons répond 429 aux
rafales de requêtes.

    python3 scripts/fetch-trackside.py      (depuis frontend/, API locale lancée sur :8000 ; relançable, reprend
                                             où il s'est arrêté grâce à scripts/.trackside-cache.json)
"""
import json, math, re, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "trackside.json"
CACHE = Path(__file__).resolve().parent / ".trackside-cache.json"
KNOWN = [ROOT / "src" / "data" / "discovery-credits.json", ROOT / "src" / "data" / "scenery-credits.json"]
API_LOCAL = "http://127.0.0.1:8000"
UA = {"User-Agent": "IAImpact-Occitanie/1.0 (student project; trackside photos)"}

CELL = 0.06  # degrés, ~6 km
RADIUS_M = 7000
PAGES = 1  # une page (50 fichiers détaillés) par case : au-delà, Commons répond 429 et tout ralentit
PER_CELL = 8

BAD = re.compile(r"\b(map|maps|carte|cartes|plan|logo|blason|armoiries|bo[iî]te à livres|panneau|plaque|int[ée]rieur|interior|vitrail|vitraux|stained|statue|tombe|tombeau|grave|retable|orgue|autel|chapiteau|inscription|affiche|poster|monument aux morts|cadastre|sign|signage|fossil|insect|herbier|specimen|mairie|école|ecole|rue|street|maison|house|hôtel|hotel|porte|door|fenêtre|window|cloche|bell|croix|cross)\b", re.I)
NOT_LANDSCAPE = re.compile(r"^(ISS\d|STS\d|IMG|DSC|DSCF|DSCN|DJI|PICT|CIMG|P\d{6,}|\d{6,})", re.I)
LANDSCAPE = re.compile(r"\b(paysage|vue|panorama|vall[ée]e|vigne|vignes|vignoble|[ée]tang|lac|rivi[èe]re|canal|pont|viaduc|gorges?|causse|montagne|pic|mont|plage|champs?|for[êe]t|colline|village|ch[âa]teau|garonne|tarn|aude|lot|h[ée]rault|orb|ari[èe]ge|landscape|view|river|hills?|lake|bridge|coast|mer|sea|campagne|pyr[ée]n[ée]es|cirque|falaise|cascade)\b", re.I)


def km(a, b):
    r = math.pi / 180
    h = math.sin((b[1] - a[1]) * r / 2) ** 2 + math.cos(a[1] * r) * math.cos(b[1] * r) * math.sin((b[0] - a[0]) * r / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def get(url):
    for attempt in range(8):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 7:
                raise
            wait = 60 * (attempt + 1)
            print(f"   429, pause {wait} s", file=sys.stderr)
            time.sleep(wait)


def clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def series(file):
    f = re.sub(r"\.[a-z]+$", "", file, flags=re.I)
    f = re.sub(r"[\s_\-–(]*\d+[)]?$", "", f)
    return re.sub(r"[\s_\-–]+$", "", f).replace("_", " ").strip()


def cells_on_track():
    places = {p["id"]: p for p in get(f"{API_LOCAL}/places")["places"]}
    cells = set()
    for e in get(f"{API_LOCAL}/network")["edges"]:
        if not e["mode"].startswith("Train"):
            continue
        a, b = places.get(e["from_id"]), places.get(e["to_id"])
        if not a or not b:
            continue
        A, B = (a["lon"], a["lat"]), (b["lon"], b["lat"])
        n = max(1, int(km(A, B) / 4))
        for i in range(n + 1):
            cells.add((round((A[1] + (B[1] - A[1]) * i / n) / CELL), round((A[0] + (B[0] - A[0]) * i / n) / CELL)))
    return sorted(cells)


def fetch_cell(lat, lon):
    base = {
        "action": "query", "format": "json", "generator": "geosearch", "ggsnamespace": 6,
        "ggscoord": f"{lat}|{lon}", "ggsradius": RADIUS_M, "ggslimit": 150,
        "prop": "imageinfo|coordinates", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 640,
        "iiextmetadatafilter": "Artist|LicenseShortName",
    }
    found, cont = [], {}
    for _ in range(PAGES):
        d = get("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({**base, **cont}))
        for p in d.get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [None])[0]
            at = (p.get("coordinates") or [None])[0]
            if not ii or not at or ii["mime"] != "image/jpeg" or ii["width"] < 1000 or ii["width"] < ii["height"] * 1.2:
                continue
            file = p["title"][5:]
            if BAD.search(file) or NOT_LANDSCAPE.match(file):
                continue
            title = series(file)
            if not re.search(r"[^\W\d_]{3}", title):
                continue
            meta = ii.get("extmetadata", {})
            found.append({
                "id": f"wc-{p['pageid']}", "src": ii["thumburl"], "lat": round(at["lat"], 5), "lon": round(at["lon"], 5),
                "title": title, "author": clean(meta.get("Artist", {}).get("value")) or "Wikimedia Commons",
                "license": clean(meta.get("LicenseShortName", {}).get("value")), "source": ii["descriptionurl"],
                "landscape": bool(LANDSCAPE.search(title)),
            })
        if "continue" not in d:
            break
        cont = d["continue"]
        time.sleep(2)
    return found


def main():
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    cells = cells_on_track()
    print(f"{len(cells)} cases le long des voies, {len(cache)} déjà faites")
    for i, (cy, cx) in enumerate(cells):
        key = f"{cy}:{cx}"
        if key in cache:
            continue
        cache[key] = fetch_cell(round(cy * CELL, 4), round(cx * CELL, 4))
        CACHE.write_text(json.dumps(cache, ensure_ascii=False))
        print(f"{i + 1}/{len(cells)} {key}: {len(cache[key])} photos")
        time.sleep(2)

    # Tri final : une seule photo par série sur toute la région, pas celles déjà utilisées pour les lieux et les
    # paysages choisis, et par case les plus « paysage » d'abord
    known = set()
    for f in KNOWN:
        if f.exists():
            known |= {c["source"] for c in json.loads(f.read_text()).values()}
    seen, out = set(), []
    for key in sorted(cache):
        keep = 0
        for p in sorted(cache[key], key=lambda p: not p["landscape"]):
            if keep >= PER_CELL or p["title"] in seen or p["source"] in known:
                continue
            seen.add(p["title"])
            out.append({k: v for k, v in p.items() if k != "landscape"})
            keep += 1
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"{len(out)} photos -> {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} Ko)")


if __name__ == "__main__":
    main()
