"""Construit la base Occitanie à partir des horaires officiels SNCF et liO (GTFS).

    python scripts/build_from_gtfs.py            # télécharge si besoin, puis construit
    python scripts/build_from_gtfs.py --refresh  # force le re-téléchargement

Sources (dans backend/.cache/, non versionné) :
  - GTFS SNCF TGV + Intercités + TER : https://eu.ftp.opendatasoft.com/sncf/plandata/Export_OpenData_SNCF_GTFS_NewTripId.zip
  - GTFS liO (cars régionaux hors SNCF) : flux publié par la Région sur transport.data.gouv.fr,
    « Réseau interurbain liO Occitanie »
  - Liste des gares SNCF (département, commune par code UIC) : ressources.data.sncf.com, jeu « liste-des-gares »
  - Contours des départements (repli pour les arrêts absents de la liste des gares) : github.com/gregoiredavid/france-geojson

Produit dans backend/data/ :
  - stations_occitanie.csv    une ligne par gare (StopArea) : id UIC, nom, coordonnées, département, commune
  - missions_occitanie.csv    une ligne par « mission » : suite d'arrêts identique parcourue par un ou plusieurs trains,
                              avec les temps de passage médians. C'est ce qui permet de savoir qu'un trajet est direct.
                              `network` = réseau liO départemental (liO 09 … liO 82, liO TIL), vide pour la SNCF.
  - walk_links.csv            correspondances à pied entre un arrêt liO et une gare SNCF proches (< 400 m)
  - connections_occitanie.csv tronçons entre arrêts consécutifs, au format historique du projet (notebook, Neo4j)
  - build_info.json           dates de validité des horaires, jour de référence, volumes
"""
import argparse
import csv
import io
import json
import re
import statistics
import sys
import unicodedata
import urllib.request
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"
DATA = ROOT / "data"

GTFS_URL = "https://eu.ftp.opendatasoft.com/sncf/plandata/Export_OpenData_SNCF_GTFS_NewTripId.zip"
GARES_URL = "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/liste-des-gares/exports/csv?delimiter=%3B"
DEPTS_URL = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-version-simplifiee.geojson"
# Clé publique publiée par la Région avec le jeu de données sur transport.data.gouv.fr
LIO_URL = "https://app.mecatran.com/utw/ws/gtfsfeed/static/lio?apiKey=2b160d626f783808095373766f18714901325e45&type=gtfs_lio"
LIO_MODE = "Car liO"
# Réseaux liO : un par département (l'Hérault est publié sous le nom « Herault Transport »), plus les lignes
# régionales qui traversent plusieurs départements (« liO TIL »)
LIO_NETWORKS = {"109": "liO 09", "111": "liO 11", "112": "liO 12", "130": "liO 30", "131": "liO 31", "132": "liO 32",
                "134": "liO 34", "146": "liO 46", "148": "liO 48", "165": "liO 65", "166": "liO 66", "181": "liO 81",
                "182": "liO 82", "500": "liO TIL"}
WALK_MAX_M = 400        # distance maximale d'une correspondance à pied arrêt liO <-> gare SNCF
WALK_M_PER_MIN = 75     # 4,5 km/h

OCCITANIE = {"09": "Ariège", "11": "Aude", "12": "Aveyron", "30": "Gard", "31": "Haute-Garonne", "32": "Gers",
             "34": "Hérault", "46": "Lot", "48": "Lozère", "65": "Hautes-Pyrénées", "66": "Pyrénées-Orientales",
             "81": "Tarn", "82": "Tarn-et-Garonne"}
# Libellés de la liste des gares (majuscules sans accents) -> nom propre
GARES_DEPT = {normalized: name for name in OCCITANIE.values()
              for normalized in [unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().upper()]}


def fetch(url, path, refresh):
    if path.exists() and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"téléchargement {url}", file=sys.stderr)
    with urllib.request.urlopen(url) as r, open(path, "wb") as f:
        f.write(r.read())
    return path


def seconds(hms):
    h, m, s = (int(x) for x in hms.split(":"))
    return h * 3600 + m * 60 + s


def ascii_upper(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.upper()).strip()


SMALL_WORDS = {"de", "du", "des", "la", "le", "les", "et", "sur", "en", "aux", "au", "d", "l"}
ACRONYMS = {"SNCF", "ZA", "ZI", "ZAC", "RN", "RD", "CHU", "IUT", "EHPAD", "CFA", "LEP", "LP", "CES", "SDIS", "IME", "HLM"}


def pretty(name):
    """'AGDE - GARE SNCF' -> 'Agde - Gare SNCF' (les noms liO sont souvent en majuscules, parfois en partie)."""

    def word(w, first):
        if w.upper() in ACRONYMS:
            return w.upper()
        if "'" in w:  # D'ARTAGNAN -> d'Artagnan
            head, tail = w.split("'", 1)
            return word(head, first) + "'" + word(tail, True)
        if w.lower() in SMALL_WORDS and not first:
            return w.lower()
        return "-".join(p[:1].upper() + p[1:].lower() for p in w.split("-"))

    return " - ".join(part if part != part.upper() else " ".join(word(w, i == 0) for i, w in enumerate(part.split()))
                      for part in name.split(" - "))


def meters(lat1, lon1, lat2, lon2):
    """Distance approximative (projection équirectangulaire, suffisante sous 1 km)."""
    import math
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6371000 * math.hypot(x, y)


def point_in_polygon(lon, lat, rings):
    inside = False
    for ring in rings:
        j = len(ring) - 1
        for i in range(len(ring)):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
    return inside


def load_departments(path):
    polys = []
    for f in json.load(open(path))["features"]:
        code = f["properties"]["code"]
        if code not in OCCITANIE:
            continue
        g = f["geometry"]
        parts = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        polys += [(OCCITANIE[code], p) for p in parts]
    return polys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-télécharger les sources")
    args = ap.parse_args()

    gtfs = zipfile.ZipFile(fetch(GTFS_URL, CACHE / "gtfs" / "sncf.zip", args.refresh))
    gares_path = fetch(GARES_URL, CACHE / "liste-des-gares.csv", args.refresh)
    depts = load_departments(fetch(DEPTS_URL, CACHE / "departements.geojson", args.refresh))

    def table(name):
        return csv.DictReader(io.TextIOWrapper(gtfs.open(name), encoding="utf-8-sig"))

    # ── Gares d'Occitanie ────────────────────────────────────────────────────
    gares = {r["code_uic"][:8]: r for r in csv.DictReader(open(gares_path, encoding="utf-8-sig"), delimiter=";")}
    stations, point_area, point_mode = {}, {}, {}
    for r in table("stops.txt"):
        if r["location_type"] == "1":  # StopArea = la gare
            uic = r["stop_id"].removeprefix("StopArea:OCE")
            lat, lon = float(r["stop_lat"]), float(r["stop_lon"])
            g = gares.get(uic)
            if g:
                dept = GARES_DEPT.get(g["departemen"])
                commune = g["commune"].title()
            else:
                dept = next((d for d, rings in depts if point_in_polygon(lon, lat, rings)), None)
                commune = ""
            if dept:
                stations[r["stop_id"]] = {"id": uic, "name": r["stop_name"], "lat": round(lat, 6), "lon": round(lon, 6),
                                          "department": dept, "commune": commune}
        else:  # StopPoint = un quai pour un mode : "StopPoint:OCETrain TER-87611004"
            point_area[r["stop_id"]] = r["parent_station"]
            point_mode[r["stop_id"]] = r["stop_id"].split(":", 1)[1].rsplit("-", 1)[0].removeprefix("OCE")
    print(f"{len(stations)} gares en Occitanie", file=sys.stderr)

    # ── Jour de référence : le mardi, mercredi ou jeudi où roulent le plus de services ──
    active = defaultdict(set)
    for r in table("calendar_dates.txt"):
        if r["exception_type"] == "1":
            active[r["date"]].add(r["service_id"])
    weekdays = {d: s for d, s in active.items() if date(int(d[:4]), int(d[4:6]), int(d[6:])).weekday() in (1, 2, 3)}
    ref_day = max(weekdays, key=lambda d: len(weekdays[d]))
    ref_services = weekdays[ref_day]

    trips = {r["trip_id"]: (r["route_id"], r["service_id"]) for r in table("trips.txt")}
    routes = {r["route_id"]: r["route_long_name"] or r["route_short_name"] for r in table("routes.txt")}

    # ── Horaires : on ne garde que les morceaux de trajets à l'intérieur de l'Occitanie ──
    missions = defaultdict(lambda: {"trips": 0, "ref": 0, "arr": defaultdict(list), "dep": defaultdict(list), "routes": Counter()})

    def runs(rows, point_area):
        """Découpe un trajet en suites contiguës d'arrêts en Occitanie (un train peut sortir de la région)."""
        rows.sort(key=lambda r: int(r["stop_sequence"]))
        run = []
        for r in rows:
            area = point_area.get(r["stop_id"])
            if area in stations:
                run.append(r)
            else:
                if len(run) > 1:
                    yield run
                run = []
        if len(run) > 1:
            yield run

    def collect(stop_times, trips, routes, ref_services, point_area, mode_of, network_of=lambda route_id: ""):
        """Regroupe les trajets d'un GTFS en missions. stop_times doit être groupé par trajet."""
        n_rows, current, rows = 0, None, []
        for r in stop_times:
            n_rows += 1
            if r["trip_id"] != current:
                if rows:
                    flush(current, rows, trips, routes, ref_services, point_area, mode_of, network_of)
                current, rows = r["trip_id"], []
            rows.append(r)
        if rows:
            flush(current, rows, trips, routes, ref_services, point_area, mode_of, network_of)
        return n_rows

    def flush(trip_id, rows, trips, routes, ref_services, point_area, mode_of, network_of):
        route_id, service = trips[trip_id]
        for run in runs(rows, point_area):
            mode = mode_of(run[0]["stop_id"])
            areas = tuple(point_area[r["stop_id"]] for r in run)
            pickup = tuple(r["pickup_type"] != "1" for r in run)
            dropoff = tuple(r["drop_off_type"] != "1" for r in run)
            m = missions[(mode, network_of(route_id), areas, pickup, dropoff)]
            t0 = seconds(run[0]["departure_time"])
            for k, r in enumerate(run):
                m["arr"][k].append((seconds(r["arrival_time"]) - t0) / 60)
                m["dep"][k].append((seconds(r["departure_time"]) - t0) / 60)
            m["trips"] += 1
            m["ref"] += service in ref_services
            m["routes"][routes.get(route_id, "")] += 1

    n_rows = collect(table("stop_times.txt"), trips, routes, ref_services, point_area, point_mode.get)
    n_sncf = len(missions)
    print(f"SNCF : {n_rows} horaires lus, {n_sncf} missions en Occitanie", file=sys.stderr)

    # ── liO : cars régionaux ─────────────────────────────────────────────────
    lio = zipfile.ZipFile(fetch(LIO_URL, CACHE / "gtfs" / "lio.zip", args.refresh))

    def lio_table(name):
        return csv.DictReader(io.TextIOWrapper(lio.open(name), encoding="utf-8-sig"))

    lio_area = {}
    lio_stops = list(lio_table("stops.txt"))
    for r in lio_stops:
        if r["location_type"] == "1" or not r["parent_station"]:  # zone d'arrêt (ou arrêt isolé)
            lat, lon = float(r["stop_lat"]), float(r["stop_lon"])
            dept = next((d for d, rings in depts if point_in_polygon(lon, lat, rings)), None)
            if dept:
                name = pretty(r["stop_name"])
                stations["lio:" + r["stop_id"]] = {"id": "L" + r["stop_id"], "name": name, "lat": round(lat, 6),
                                                   "lon": round(lon, 6), "department": dept,
                                                   "commune": name.split(" - ")[0] if " - " in name else ""}
    for r in lio_stops:
        area = "lio:" + (r["parent_station"] or r["stop_id"])
        if area in stations:
            lio_area[r["stop_id"]] = area

    # Services actifs le jour de référence : calendar (jours de semaine + période) corrigé par calendar_dates
    ref = date(int(ref_day[:4]), int(ref_day[4:6]), int(ref_day[6:]))
    weekday = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")[ref.weekday()]
    lio_ref = {r["service_id"] for r in lio_table("calendar.txt")
               if r[weekday] == "1" and r["start_date"] <= ref_day <= r["end_date"]}
    for r in lio_table("calendar_dates.txt"):
        if r["date"] == ref_day:
            (lio_ref.add if r["exception_type"] == "1" else lio_ref.discard)(r["service_id"])

    lio_trips = {r["trip_id"]: (r["route_id"], r["service_id"]) for r in lio_table("trips.txt")}
    lio_route_rows = list(lio_table("routes.txt"))
    lio_routes = {r["route_id"]: f'{r["route_short_name"]} · {pretty(r["route_long_name"])}'.strip(" ·")
                  for r in lio_route_rows}
    lio_network = {r["route_id"]: LIO_NETWORKS.get(r["agency_id"], "liO") for r in lio_route_rows}
    n_rows = collect(lio_table("stop_times.txt"), lio_trips, lio_routes, lio_ref, lio_area, lambda _: LIO_MODE,
                     lio_network.get)
    print(f"liO : {n_rows} horaires lus, {len(missions) - n_sncf} missions", file=sys.stderr)

    # ── Écriture ─────────────────────────────────────────────────────────────
    DATA.mkdir(exist_ok=True)
    used = set()
    mission_rows = []
    for i, ((mode, network, areas, pickup, dropoff), m) in enumerate(
            sorted(missions.items(), key=lambda kv: (kv[0][0], kv[0][1], -kv[1]["trips"]))):
        used.update(areas)
        arr = [round(statistics.median(m["arr"][k]), 1) for k in range(len(areas))]
        dep = [round(statistics.median(m["dep"][k]), 1) for k in range(len(areas))]
        mission_rows.append({
            "mission_id": f"M{i:05d}", "mode": mode, "network": network, "line": m["routes"].most_common(1)[0][0],
            "trips": m["trips"], "trips_ref_day": m["ref"],
            "stops": "|".join(stations[a]["id"] for a in areas),
            "arrival_min": "|".join(f"{x:g}" for x in arr), "departure_min": "|".join(f"{x:g}" for x in dep),
            "pickup": "".join("1" if p else "0" for p in pickup), "dropoff": "".join("1" if d else "0" for d in dropoff),
        })
    with open(DATA / "missions_occitanie.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(mission_rows[0]))
        w.writeheader()
        w.writerows(mission_rows)

    by_id = {s["id"]: s for a, s in stations.items() if a in used}

    # Correspondances à pied : arrêt liO <-> gare SNCF à moins de WALK_MAX_M mètres
    sncf_ids = [s for i, s in by_id.items() if not i.startswith("L")]
    walks = []
    for i, s in by_id.items():
        if not i.startswith("L"):
            continue
        for g in sncf_ids:
            if abs(g["lat"] - s["lat"]) > 0.005 or abs(g["lon"] - s["lon"]) > 0.007:
                continue
            d = meters(s["lat"], s["lon"], g["lat"], g["lon"])
            if d <= WALK_MAX_M:
                minutes = max(2, round(d / WALK_M_PER_MIN, 1))
                walks += [(i, g["id"], minutes, round(d)), (g["id"], i, minutes, round(d))]
    with open(DATA / "walk_links.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["from_id", "to_id", "minutes", "meters"])
        w.writerows(sorted(walks))
    with open(DATA / "stations_occitanie.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["stop_id", "name", "lat", "lon", "department", "commune"])
        w.writeheader()
        for s in sorted(by_id.values(), key=lambda s: ascii_upper(s["name"])):
            w.writerow({"stop_id": s["id"], **{k: s[k] for k in ("name", "lat", "lon", "department", "commune")}})

    # Format historique : un tronçon entre deux arrêts consécutifs, durée moyenne pondérée par le nombre de trains
    seg = defaultdict(lambda: [0.0, 0])
    for m in mission_rows:
        ids = m["stops"].split("|")
        arr = [float(x) for x in m["arrival_min"].split("|")]
        dep = [float(x) for x in m["departure_min"].split("|")]
        for k in range(len(ids) - 1):
            s = seg[(m["mode"], ids[k], ids[k + 1])]
            s[0] += (arr[k + 1] - dep[k]) * m["trips"]
            s[1] += m["trips"]

    def city(s):
        return ascii_upper(s["commune"] or s["name"])

    def td(minutes):
        total = round(minutes * 60)
        return f"0 days {total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"

    with open(DATA / "connections_occitanie.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["stop_id", "stop_name", "next_stop_id", "next_stop_name", "duration_min_mean",
                    "stop_id_clean", "next_stop_id_clean", "departure_city", "destination_city"])
        for (mode, a, b), (total, n) in sorted(seg.items(), key=lambda kv: (by_id[kv[0][1]]["name"], kv[0][0], by_id[kv[0][2]]["name"])):
            sa, sb = by_id[a], by_id[b]
            w.writerow([f"StopPoint:OCE{mode}-{a}", sa["name"], f"StopPoint:OCE{mode}-{b}", sb["name"], td(total / n),
                        a, b, city(sa), city(sb)])

    feed = next(table("feed_info.txt"))
    info = {"source": GTFS_URL, "feed_version": feed["feed_version"], "valid_from": feed["feed_start_date"],
            "valid_until": feed["feed_end_date"], "reference_day": ref_day, "stations": len(by_id),
            "lio_source": "transport.data.gouv.fr — Réseau interurbain liO Occitanie",
            "lio_feed_version": next(lio_table("feed_info.txt"))["feed_version"],
            "missions": len(mission_rows), "segments": len(seg), "walk_links": len(walks) // 2,
            "modes": dict(Counter(m["mode"] for m in mission_rows)),
            "lio_networks": dict(sorted(Counter(m["network"] for m in mission_rows if m["network"]).items()))}
    json.dump(info, open(DATA / "build_info.json", "w"), ensure_ascii=False, indent=2)
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
