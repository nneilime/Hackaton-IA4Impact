"""Télécharge les paysages vus depuis la fenêtre du train simulé (src/data/scenery.ts) depuis Wikimedia Commons.

Même mécanique que fetch-discoveries.py (image principale de l'article Wikipédia fr, 960 px) : photos dans
public/scenery/<id>.jpg, auteur et licence dans src/data/scenery-credits.json.

    python3 scripts/fetch-scenery.py      (depuis frontend/, relançable : saute les images déjà là)
"""
import importlib.util, json, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("fetch_discoveries", HERE / "fetch-discoveries.py")
fd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fd)

ROOT = HERE.parent
OUT = ROOT / "public" / "scenery"
CREDITS = ROOT / "src" / "data" / "scenery-credits.json"

# id du paysage -> titre de l'article Wikipédia (fr)
ARTICLES = {
    "vignes": "Vignoble du Languedoc-Roussillon",
    "etang-thau": "Étang de Thau",
    "canigou": "Pic du Canigou",
    "montagne-noire": "Montagne Noire",
    "larzac": "Causse du Larzac",
    "gorges-tarn": "Gorges du Tarn",
    "garrigue": "Garrigue",
    "leucate": "Étang de Salses-Leucate",
    "cote-vermeille": "Côte Vermeille",
    "pic-saint-loup": "Pic Saint-Loup",
    "garonne": "Garonne",
    "cevennes": "Cévennes",
    "clape": "Massif de la Clape",
    "aubrac": "Aubrac",
    "pyrenees-ariegeoises": "Parc naturel régional des Pyrénées ariégeoises",
    "gavarnie": "Cirque de Gavarnie",
    "tournesols": "Tournesol",
    "flamants": "Flamant rose",
    "oliviers": "Olivier",
    "pont-du-gard": "Pont du Gard",
    "tarn": "Tarn (rivière)",
    "quercy": "Causses du Quercy",
    "maguelone": "Cathédrale de Maguelone",
}

# Quand l'image de l'article est une carte, un blason ou une planche botanique : une vraie photo de paysage
FILES = {
    "vignes": "Vignes sur plateau in the Languedoc wine region of Minervois.jpg",
    "montagne-noire": "Montagne Noire from Lagardiolle.jpg",
    "leucate": "Étang de Leucate depuis voie ferrée.JPG",
    "cote-vermeille": "Baie de Collioure A.jpg",
    "clape": "Massif de la Clape en fin de journée d'été (juillet 2007) 1.JPG",
    "aubrac": "Paysage de l'Aubrac.jpg",
    "oliviers": "Oliviers près Rochefort du Gard.jpg",
    "tournesols": "Champ Tournesols Route Rossignolières Sulignat 1.jpg",
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    credits = json.loads(CREDITS.read_text()) if CREDITS.exists() else {}
    for pid, title in ARTICLES.items():
        if pid in credits and (OUT / f"{pid}.jpg").exists():
            continue
        name = FILES.get(pid)
        if not name:
            pages = fd.api("fr.wikipedia.org", redirects=1, prop="pageimages", piprop="name", titles=title)["query"]["pages"]
            name = next(iter(pages.values())).get("pageimage")
        if not name:
            print(f"!! {pid}: pas d'image pour « {title} »", file=sys.stderr)
            continue
        time.sleep(2)
        info = fd.api("commons.wikimedia.org", prop="imageinfo", iiprop="url|extmetadata", iiurlwidth=960, titles=f"File:{name}")
        page = next(iter(info["query"]["pages"].values()))
        if "imageinfo" not in page:
            print(f"!! {pid}: « {name} » n'est pas sur Commons, ajouter un fichier dans FILES", file=sys.stderr)
            continue
        ii = page["imageinfo"][0]
        meta = ii.get("extmetadata", {})
        time.sleep(2)
        (OUT / f"{pid}.jpg").write_bytes(fd.get(ii["thumburl"], binary=True))
        credits[pid] = {
            "author": fd.clean(meta.get("Artist", {}).get("value")) or "Wikimedia Commons",
            "license": fd.clean(meta.get("LicenseShortName", {}).get("value")),
            "source": ii["descriptionurl"],
            "file": name,
        }
        CREDITS.write_text(json.dumps(credits, ensure_ascii=False, indent=2) + "\n")
        print(f"ok {pid}: {name} — {credits[pid]['author']} ({credits[pid]['license']})")
        time.sleep(3)


if __name__ == "__main__":
    main()
