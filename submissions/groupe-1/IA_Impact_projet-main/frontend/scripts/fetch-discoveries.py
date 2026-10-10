"""Télécharge les photos des lieux à découvrir (src/data/discoveries.ts) depuis Wikipédia / Wikimedia Commons.

Chaque lieu prend l'image principale de son article Wikipédia (fr), réduite à 960 px, copiée dans
public/discoveries/<id>.jpg. Auteur et licence sont écrits dans src/data/discovery-credits.json :
les photos sont presque toutes en CC BY-SA, le crédit doit rester affiché sur la fiche.

    python3 scripts/fetch-discoveries.py      (depuis frontend/, relançable : saute les images déjà là)
"""
import json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "discoveries"
CREDITS = ROOT / "src" / "data" / "discovery-credits.json"
UA = {"User-Agent": "IAImpact-Occitanie/1.0 (student project; discoveries mock data)"}

# id du lieu -> titre de l'article Wikipédia (fr)
ARTICLES = {
    "canal-du-midi": "Canal du Midi",
    "saint-sernin": "Basilique Saint-Sernin de Toulouse",
    "capitole": "Capitole de Toulouse",
    "cite-carcassonne": "Cité de Carcassonne",
    "arenes-nimes": "Arènes de Nîmes",
    "maison-carree": "Maison carrée",
    "jardins-fontaine": "Jardins de la Fontaine",
    "place-comedie": "Place de la Comédie (Montpellier)",
    "peyrou": "Promenade du Peyrou",
    "musee-fabre": "Musée Fabre",
    "palais-majorque": "Palais des rois de Majorque",
    "castillet": "Castillet",
    "sainte-cecile": "Cathédrale Sainte-Cécile d'Albi",
    "musee-lautrec": "Musée Toulouse-Lautrec",
    "cimetiere-marin": "Cimetière marin de Sète",
    "mont-saint-clair": "Mont Saint-Clair",
    "chateau-lourdes": "Château fort de Lourdes",
    "sanctuaire-lourdes": "Sanctuaire Notre-Dame de Lourdes",
    "pont-valentre": "Pont Valentré",
    "cathedrale-cahors": "Cathédrale Saint-Étienne de Cahors",
    "horreum": "Horreum de Narbonne",
    "palais-archeveques": "Palais des archevêques de Narbonne",
    "fonseranes": "Écluses de Fonseranes",
    "saint-nazaire-beziers": "Cathédrale Saint-Nazaire de Béziers",
    "chateau-foix": "Château de Foix",
    "chateau-collioure": "Château royal de Collioure",
    "notre-dame-des-anges": "Église Notre-Dame-des-Anges de Collioure",
    "viaduc-millau": "Viaduc de Millau",
    "abbaye-moissac": "Abbaye Saint-Pierre de Moissac",
    "musee-champollion": "Musée Champollion",
    "musee-soulages": "Musée Soulages",
    "cathedrale-rodez": "Cathédrale Notre-Dame de Rodez",
    "halle-aux-grains": "Halle aux grains (Toulouse)",
    "corum": "Le Corum",
    "espace-brassens": "Espace Georges-Brassens",
    "stadium-toulouse": "Stadium de Toulouse",
    "cnea-font-romeu": "Centre national d'entraînement en altitude",
    "joutes-sete": "Joute nautique",
    "cite-espace": "Cité de l'espace",
    "four-solaire": "Four solaire d'Odeillo",
    "museum-toulouse": "Muséum de Toulouse",
    "musee-millau": "Musée de Millau et des Grands Causses",
    "hotel-assezat": "Hôtel d'Assézat",
}

# Quand l'image de l'article n'est pas sur Commons (photo locale, souvent non libre), on impose un fichier Commons
FILES = {
    "viaduc-millau": "Viaduc de Millau.jpg",
    "musee-champollion": "Facade musee champollion figeac.jpg",
    "halle-aux-grains": "Halle aux grains Toulouse.jpg",
    "cnea-font-romeu": "Stade d'athlétisme du CNEA de Font-Romeu.jpg",
    "joutes-sete": "Sète water jousting joute nautique (52222049980).jpg",
    "cite-espace": "France-Toulouse-Cite de l'espace-Ariane 5.jpg",
    "museum-toulouse": "Grand carré MHNT.jpg",
    "musee-millau": "Cup Drag 30 from Millau MDCL.jpg",
}


def get(url, binary=False):
    """GET avec reprise : Wikimedia répond 429 quand on enchaîne les requêtes."""
    for attempt in range(8):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                data = r.read()
                return data if binary else json.loads(data)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 7:
                raise
            time.sleep(15 * (attempt + 1))


def api(host, **params):
    return get(f"https://{host}/w/api.php?" + urllib.parse.urlencode({"action": "query", "format": "json", **params}))


def clean(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    credits_path = CREDITS
    credits = json.loads(credits_path.read_text()) if credits_path.exists() else {}
    for pid, title in ARTICLES.items():
        if pid in credits and (OUT / f"{pid}.jpg").exists():
            continue
        name = FILES.get(pid)
        if not name:
            pages = api("fr.wikipedia.org", redirects=1, prop="pageimages", piprop="name", titles=title)["query"]["pages"]
            name = next(iter(pages.values())).get("pageimage")
        if not name:
            print(f"!! {pid}: pas d'image pour « {title} »", file=sys.stderr)
            continue
        time.sleep(2)
        info = api("commons.wikimedia.org", prop="imageinfo", iiprop="url|extmetadata", iiurlwidth=960, titles=f"File:{name}")
        page = next(iter(info["query"]["pages"].values()))
        if "imageinfo" not in page:
            print(f"!! {pid}: « {name} » n'est pas sur Commons, ajouter un fichier dans FILES", file=sys.stderr)
            continue
        ii = page["imageinfo"][0]
        meta = ii.get("extmetadata", {})
        time.sleep(2)
        (OUT / f"{pid}.jpg").write_bytes(get(ii["thumburl"], binary=True))
        credits[pid] = {
            "author": clean(meta.get("Artist", {}).get("value")) or "Wikimedia Commons",
            "license": clean(meta.get("LicenseShortName", {}).get("value")),
            "source": ii["descriptionurl"],
        }
        credits_path.write_text(json.dumps(credits, ensure_ascii=False, indent=2) + "\n")
        print(f"ok {pid}: {name} — {credits[pid]['author']} ({credits[pid]['license']})")
        time.sleep(3)


if __name__ == "__main__":
    main()
