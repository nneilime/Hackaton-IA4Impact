"""Produit src/data/network.json et src/data/photos.json pour le diapo (et copie les images dans public/assets) : contour de l'Occitanie, gares et tronçons des trains liO,
déjà projetés dans un repère SVG 1000 x 820. Relancer après une mise à jour des horaires :
    python3 presentation/scripts/build-data.py
"""
import csv, json, math, re, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "backend/data/train_lio"
OUT = ROOT / "presentation"
ASSETS = OUT / "public/assets"   # servi tel quel par Vite
JSON_OUT = OUT / "src/data"       # importé et typé par src/data/index.ts
W, H, PAD = 1000, 820, 30

outline = json.loads(re.search(r"OCCITANIE: LonLat\[\] = (\[\[.*?\]\]);", (ROOT / "frontend/src/occitanie.ts").read_text()).group(1))
k = math.cos(math.radians(43.6))  # projection équirectangulaire corrigée à la latitude de la région
xs = [p[0] * k for p in outline]; ys = [p[1] for p in outline]
s = min((W - 2 * PAD) / (max(xs) - min(xs)), (H - 2 * PAD) / (max(ys) - min(ys)))
ox = (W - (max(xs) - min(xs)) * s) / 2; oy = (H - (max(ys) - min(ys)) * s) / 2
def proj(lon, lat):
    return [round(ox + (lon * k - min(xs)) * s, 1), round(oy + (max(ys) - lat) * s, 1)]

stations = {}
for r in csv.DictReader(open(DATA / "stations_occitanie.csv")):
    stations[r["stop_id"]] = {"n": r["name"], "p": proj(float(r["lon"]), float(r["lat"]))}
edges = set()
for r in csv.DictReader(open(DATA / "connections_occitanie.csv")):
    a, b = r["stop_id_clean"], r["next_stop_id_clean"]
    if a in stations and b in stations and a != b:
        edges.add(tuple(sorted((a, b))))
ids = list(stations)

# Itinéraire d'exemple, calculé par le vrai moteur du backend (pas recopié à la main)
import sys
sys.path.insert(0, str(ROOT / "backend"))
from app.routing import Network
route = Network(DATA).route("Perpignan", "Albi")

idx = {sid: i for i, sid in enumerate(ids)}
net = {
    "outline": "M" + "L".join(f"{x},{y}" for x, y in (proj(*p) for p in outline)) + "Z",
    "stations": [[*stations[i]["p"], stations[i]["n"]] for i in ids],
    "edges": [[idx[a], idx[b]] for a, b in sorted(edges)],
    "ids": {sid: idx[sid] for sid in ("87611004", "87773002", "87613422", "87781005", "87784009", "87775007", "87615005")},
    # Monuments 3D posés sur la carte, à leurs vraies coordonnées
    "spots": {k: proj(lon, lat) for k, (lat, lon) in {"arenes-nimes": (43.8347, 4.3597), "maison-carree": (43.8384, 4.3561),
                                                       "viaduc-millau": (44.0797, 3.0225)}.items()},
    "route": {
        "from": route["from"], "to": route["to"], "minutes": round(route["minutes"]),
        "legs": [{"line": l["line"], "from": l["from"], "to": l["to"], "minutes": round(l["minutes"]),
                  "wait": round(l["wait_minutes"]), "perDay": l["trips_per_day"],
                  "stops": [idx[i] for i in l["stops"] if i in idx]} for l in route["legs"]],
    },
}
(JSON_OUT / "network.json").write_text(json.dumps(net, ensure_ascii=False, separators=(",", ":")))

# Photos des lieux à découvrir (Wikimedia Commons) + crédits
credits = json.load(open(ROOT / "frontend/src/data/discovery-credits.json"))
keep = ["cite-carcassonne", "pont-valentre", "viaduc-millau", "arenes-nimes", "canal-du-midi", "chateau-collioure"]
out = {}
for key in keep:
    src = next((ROOT / "frontend/public/discoveries").glob(key + ".*"))
    shutil.copy(src, ASSETS / "photos" / src.name)
    out[key] = {**credits[key], "file": "assets/photos/" + src.name}
print(len(stations), "gares,", len(edges), "tronçons")

# Paysages vus « par la fenêtre du train » sur Perpignan → Albi, dans l'ordre du trajet, + un modèle 3D
SCENERY = [("leucate", "Étang de Leucate, au bord des voies"), ("clape", "Massif de la Clape"), ("vignes", "Vignes du Minervois"),
           ("cite-carcassonne", "La Cité de Carcassonne"), ("montagne-noire", "Montagne Noire"), ("tournesols", "Champs de tournesols"),
           ("garonne", "La Garonne à Toulouse")]
sc_credits = json.load(open(ROOT / "frontend/src/data/scenery-credits.json"))
(ASSETS / "scenery").mkdir(exist_ok=True)
scenery = []
for key, title in SCENERY:
    src = next((ROOT / "frontend/public/scenery").glob(key + ".*"), None) or next((ROOT / "frontend/public/discoveries").glob(key + ".*"))
    shutil.copy(src, ASSETS / "scenery" / src.name)
    c = sc_credits.get(key) or credits[key]
    scenery.append({"id": key, "title": title, "file": "assets/scenery/" + src.name, "author": c["author"], "license": c["license"],
                    "place": key in credits})
model_credits = json.load(open(ROOT / "frontend/src/data/model-credits.json"))
(ASSETS / "models").mkdir(exist_ok=True)
for key in ("arenes-nimes", "maison-carree", "viaduc-millau"):
    shutil.copy(ROOT / f"frontend/public/models/{key}.glb", ASSETS / f"models/{key}.glb")
photos = {"PHOTOS": out, "SCENERY": scenery,
          "MODEL": {**model_credits["arenes-nimes"], "file": "assets/models/arenes-nimes.glb", "title": "Arènes de Nîmes"},
          "MODELS": {k: {**model_credits[k], "file": f"assets/models/{k}.glb"} for k in ("arenes-nimes", "maison-carree", "viaduc-millau")}}

# Idées de sorties scolaires au départ de Toulouse : vraies durées calculées par le moteur
IDEAS = [("Carcassonne", "cite-carcassonne", "La Cité de Carcassonne"), ("Cahors", "pont-valentre", "Pont Valentré"), ("Moissac", "abbaye-moissac", "Abbaye de Moissac")]
net_full = Network(DATA)
ideas = []
for city, key, title in IDEAS:
    r = net_full.route("Toulouse", city)
    src = next((ROOT / "frontend/public/discoveries").glob(key + ".*"))
    shutil.copy(src, ASSETS / "photos" / src.name)
    ideas.append({"title": title, "city": city, "minutes": round(r["minutes"]), "transfers": r["transfers"], "file": "assets/photos/" + src.name,
                  "author": credits[key]["author"], "license": credits[key]["license"]})
photos["IDEAS"] = ideas
(JSON_OUT / "photos.json").write_text(json.dumps(photos, ensure_ascii=False, indent=1))
