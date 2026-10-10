"""Itinéraire le plus court (Dijkstra) sur les horaires officiels SNCF et liO en Occitanie.

Le graphe est construit à partir des **missions** (data/missions_occitanie.csv, voir
scripts/build_from_gtfs.py) : une mission est une suite d'arrêts parcourue par un ou plusieurs
trains ou cars. Chaque arête relie deux gares desservies **par le même véhicule, sans changer** ;
un itinéraire est donc une suite de trajets directs, et le nombre de correspondances est connu.

Coût d'un itinéraire = temps passé à bord + pour chaque correspondance :
  - `transfer_min` minutes de changement (descendre, changer de quai),
  - l'attente moyenne du véhicule suivant, estimée par sa fréquence : la moitié de l'intervalle entre
    deux passages sur une journée de service de 16 h (19 trains/jour -> ~25 min).
Le premier départ n'est pas pénalisé : le voyageur choisit son heure — sauf s'il ne circule pas le jour de
référence (car du week-end, des vacances…) : il compte alors l'attente maximale, comme une correspondance rare. Les heures précises ne sont pas
modélisées ; la durée annoncée est une estimation moyenne.

Un arrêt de car liO et une gare SNCF à moins de 400 m sont reliés à pied (data/walk_links.csv) :
la marche n'est pas un trajet, elle ne compte pas comme une montée.

Le départ et la destination sont des noms de ville ou de gare, tels que les sort le NER (FROM / TO).

    python -m app.routing Toulouse Perpignan                  # trains liO (data/train_lio)
    python -m app.routing Toulouse Tarbes --dataset full --exclude INTERCITES --transfer 5

    from app.routing import Network
    route = Network().route("Toulouse", "Perpignan")
"""
import argparse
import csv
import heapq
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_TRANSFER_MIN = 5
SERVICE_DAY_MIN = 16 * 60   # amplitude d'une journée de service, pour estimer l'attente
MAX_WAIT_MIN = 120          # plafond : un car à 1 passage/jour ne coûte pas 8 h d'attente moyenne


def expected_wait(per_day):
    """Attente moyenne avant le prochain passage, en minutes, pour une fréquence donnée (trains/jour)."""
    return min(SERVICE_DAY_MIN / (2 * max(per_day, 0.5)), MAX_WAIT_MIN)

# Ordre d'affichage des types de transport ; ceux qui n'y sont pas viennent après
MODES = ("Train TER", "Car TER", "Car liO", "Car à réservation", "INTERCITES", "INTERCITES de nuit", "TGV INOUI", "OUIGO")
WALK = "Marche"
# Temps pour rejoindre (ou quitter) un arrêt quand on demande une ville : la gare qui porte le nom de la
# ville est le point de départ naturel, un arrêt de car en périphérie demande de traverser la ville.
LIO_DEPARTMENTS = {"09": "Ariège", "11": "Aude", "12": "Aveyron", "30": "Gard", "31": "Haute-Garonne", "32": "Gers",
                   "34": "Hérault", "46": "Lot", "48": "Lozère", "65": "Hautes-Pyrénées", "66": "Pyrénées-Orientales",
                   "81": "Tarn", "82": "Tarn-et-Garonne", "TIL": "Lignes régionales"}
ACCESS_MIN = {"main": 0, "station": 10, "hub": 10, "stop": 20}


def normalize(s):
    """'Saint-Gaudens' / 'SAINT GAUDENS' / 'saint-gaudéns' -> 'SAINT GAUDENS'."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", " ", s.upper()).strip()


def is_lio(stop_id):
    """Les arrêts liO ont un identifiant préfixé par L ; les gares SNCF, leur code UIC."""
    return stop_id.startswith("L")


def boarding_cost(boarded, per_day, transfer_min):
    """Minutes ajoutées à une montée : correspondance (changement + attente) ou premier départ."""
    if boarded:
        return transfer_min + expected_wait(per_day)
    return 0 if per_day > 0 else MAX_WAIT_MIN


class UnknownPlace(KeyError):
    pass


class SamePlace(ValueError):
    pass


class Network:
    def __init__(self, data_dir=DATA_DIR):
        data_dir = Path(data_dir)
        self.place = {}                 # id UIC -> {"id", "name", "lat", "lon", "department", "commune"}
        self.by_key = defaultdict(set)  # nom normalisé (gare ou commune) -> ids
        with open(data_dir / "stations_occitanie.csv", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                self.place[r["stop_id"]] = {"id": r["stop_id"], "name": r["name"], "lat": float(r["lat"]),
                                            "lon": float(r["lon"]), "department": r["department"], "commune": r["commune"],
                                            "network": "lio" if is_lio(r["stop_id"]) else "sncf"}
                self.by_key[normalize(r["name"])].add(r["stop_id"])
                if r["commune"]:
                    self.by_key[normalize(r["commune"])].add(r["stop_id"])
        self.name = {i: p["name"] for i, p in self.place.items()}

        self.missions = []
        # Un « service » = (mode, réseau) : ("Train TER", "") pour la SNCF, ("Car liO", "liO 34") pour les cars liO.
        # Trajets directs : (a, b, mode, réseau) -> [minutes, mission, i, j, trains/jour]. On garde la mission la plus
        # rapide, et on additionne les fréquences de toutes les missions qui font a -> b sans changement.
        self.rides = {}
        self.segments = {}              # (a, b, mode, réseau) -> minutes : arrêts consécutifs, pour dessiner le réseau
        self.served = defaultdict(int)  # arrêt -> passages par jour (jour de référence)
        self.lines = defaultdict(Counter)  # arrêt -> {ligne: passages par jour}
        with open(data_dir / "missions_occitanie.csv", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                m = {"mode": r["mode"], "network": r.get("network", ""), "line": r["line"], "trips": int(r["trips"]), "per_day": int(r["trips_ref_day"]),
                     "stops": r["stops"].split("|"),
                     "arr": [float(x) for x in r["arrival_min"].split("|")],
                     "dep": [float(x) for x in r["departure_min"].split("|")],
                     "pickup": [c == "1" for c in r["pickup"]], "dropoff": [c == "1" for c in r["dropoff"]]}
                k = len(self.missions)
                self.missions.append(m)
                stops = m["stops"]
                for i, stop in enumerate(stops):  # fréquentation et lignes de chaque arrêt, pour la carte
                    if m["pickup"][i] or m["dropoff"][i]:
                        self.served[stop] += m["per_day"]
                        if m["line"]:
                            self.lines[stop][m["line"]] += m["per_day"]
                for i in range(len(stops) - 1):
                    seg = (stops[i], stops[i + 1], m["mode"], m["network"])
                    t = m["arr"][i + 1] - m["dep"][i]
                    self.segments[seg] = min(t, self.segments.get(seg, t))
                    if not m["pickup"][i]:
                        continue
                    for j in range(i + 1, len(stops)):
                        if not m["dropoff"][j] or stops[j] == stops[i]:
                            continue
                        key = (stops[i], stops[j], m["mode"], m["network"])
                        t = m["arr"][j] - m["dep"][i]
                        best = self.rides.get(key)
                        if best is None:
                            self.rides[key] = [t, k, i, j, m["per_day"]]
                        else:
                            best[4] += m["per_day"]
                            if t < best[0]:
                                best[:4] = [t, k, i, j]
        self.adj = defaultdict(list)    # a -> [(b, mode, réseau)]
        for a, b, mode, network in self.rides:
            self.adj[a].append((b, mode, network))
        self.walk = defaultdict(list)   # a -> [(b, minutes, mètres)]
        walk_path = data_dir / "walk_links.csv"
        if walk_path.exists():
            with open(walk_path, encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    self.walk[r["from_id"]].append((r["to_id"], float(r["minutes"]), int(r["meters"])))

    # ── Recherche de lieux ───────────────────────────────────────────────────
    def resolve(self, query):
        """Gares et arrêts correspondant à une ville ou une gare -> minutes d'accès estimées depuis la ville.

        Une gare précise (« Nîmes Pont du Gard ») : elle seule, sans accès.
        Une ville (« Toulouse ») : toutes ses gares et ses arrêts de car, la gare qui porte son nom à 0 min
        (Matabiau, pas Montaudran), les autres gares et les gares routières à 10, les autres arrêts à 20.
        Repli : gares dont le nom commence par la requête.
        """
        key = normalize(query)
        stops = self.by_key.get(key)
        if not stops:
            stops = {s for k, ids in self.by_key.items() if k.startswith(key + " ") for s in ids}
        if not stops:
            raise UnknownPlace(query)
        exact = {s for s in stops if normalize(self.name[s]) == key}
        if exact:
            return {s: 0 for s in exact}
        out = {}
        for s in stops:
            named = (normalize(self.name[s]) + " ").startswith(key + " ")
            if not is_lio(s):
                kind = "main" if named else "station"
            else:
                kind = "hub" if re.search(r"\b(GARE|PEM)\b", normalize(self.name[s])) else "stop"
            out[s] = ACCESS_MIN[kind]
        return out

    def stations(self, query="", limit=20):
        """Gares dont le nom normalisé contient la requête, triées par nom."""
        key = normalize(query)
        return sorted({n for n in self.name.values() if key in normalize(n)})[:limit]

    def places(self):
        """Arrêts avec leurs passages par jour et leurs lignes (les plus fréquentes d'abord)."""
        return [{**p, "trips_per_day": self.served[p["id"]],
                 "lines": [line for line, _ in self.lines[p["id"]].most_common(6)]}
                for p in sorted(self.place.values(), key=lambda p: normalize(p["name"]))]

    def edges(self):
        """Tronçons entre arrêts consécutifs (pour tracer le réseau)."""
        return [{"from_id": a, "to_id": b, "mode": m, "network": n, "minutes": round(t, 1)}
                for (a, b, m, n), t in self.segments.items()]

    def modes(self):
        """Types de transport présents, avec leur nombre de tronçons et de missions."""
        links, missions = defaultdict(int), defaultdict(int)
        for _, _, m, _ in self.segments:
            links[m] += 1
        for m in self.missions:
            missions[m["mode"]] += 1
        order = {m: i for i, m in enumerate(MODES)}
        return [{"id": m, "links": links[m], "missions": missions[m]}
                for m in sorted(links, key=lambda m: (order.get(m, len(MODES)), m))]

    def networks(self):
        """Réseaux liO (un par département + lignes régionales), avec leur département et leur nombre de missions."""
        missions = defaultdict(int)
        for m in self.missions:
            if m["network"]:
                missions[m["network"]] += 1
        return [{"id": n, "department": LIO_DEPARTMENTS.get(n.removeprefix("liO "), ""), "missions": c}
                for n, c in sorted(missions.items())]

    # ── Dijkstra ─────────────────────────────────────────────────────────────
    def route(self, departure, destination, exclude=(), exclude_networks=(), transfer_min=DEFAULT_TRANSFER_MIN):
        """Itinéraire le plus court entre une gare (ou ville) de départ et une gare (ou ville) d'arrivée.

        exclude          : types de transport à ignorer, ex. {"Car TER", "INTERCITES de nuit"}
        exclude_networks : réseaux liO à ignorer, ex. {"liO 34", "liO TIL"} (voir networks())
        transfer_min : minutes de changement par correspondance (en plus de l'attente estimée)

        Renvoie None s'il n'existe aucun chemin, sinon
        {"from", "to", "minutes", "ride_minutes", "access_minutes", "egress_minutes", "transfers", "transfer_min",
         "legs": [{"mode", "line", "from", "to", "from_id", "to_id", "minutes", "wait_minutes",
                   "stops", "times", "trips_per_day"}, ...]}
        où chaque leg est un trajet direct (même train ou même car du début à la fin) et wait_minutes
        le changement + l'attente estimée avant ce leg (0 pour le premier).
        """
        sources, targets = self.resolve(departure), self.resolve(destination)
        if sources.keys() & targets.keys():
            raise SamePlace(departure)
        # État = (gare, déjà monté ?) : la première montée est gratuite, les suivantes sont des correspondances.
        # La marche ne change pas l'état : partir à pied vers un arrêt de car n'est pas une correspondance.
        dist = {(s, False): float(a) for s, a in sources.items()}
        prev = {}
        heap = [(float(a), s, False) for s, a in sources.items()]
        heapq.heapify(heap)
        best = None  # (coût total avec l'accès à l'arrivée, état)
        while heap:
            d, u, boarded = heapq.heappop(heap)
            if best and d >= best[0]:
                break
            if d > dist[(u, boarded)]:
                continue
            if u in targets and boarded and (best is None or d + targets[u] < best[0]):
                best = (d + targets[u], (u, boarded))
            moves = []
            for v, mode, network in self.adj[u]:
                if mode in exclude or network in exclude_networks:
                    continue
                ride, _, _, _, per_day = self.rides[(u, v, mode, network)]
                moves.append((v, True, ride + boarding_cost(boarded, per_day, transfer_min), (mode, network)))
            for v, minutes, _ in self.walk[u]:
                moves.append((v, boarded, minutes, (WALK, "")))
            for v, b, cost, mode in moves:
                nd = d + cost
                if nd < dist.get((v, b), float("inf")):
                    dist[(v, b)] = nd
                    prev[(v, b)] = ((u, boarded), mode)
                    heapq.heappush(heap, (nd, v, b))
        if best is None:
            return None
        return self._itinerary(best[1], prev, transfer_min, best[0], sources, targets)

    def _itinerary(self, state, prev, transfer_min, total, sources, targets):
        legs = []
        while state in prev:
            (p, was_boarded), (mode, network) = prev[state]
            u = state[0]
            if mode == WALK:
                minutes, meters = next((m, mt) for v, m, mt in self.walk[p] if v == u)
                legs.append({"mode": WALK, "network": "", "line": f"{meters} m", "from": self.name[p], "to": self.name[u],
                             "from_id": p, "to_id": u, "minutes": minutes, "wait_minutes": 0,
                             "stops": [p, u], "trips_per_day": None, "times": [0, minutes]})
            else:
                minutes, k, i, j, per_day = self.rides[(p, u, mode, network)]
                m = self.missions[k]
                legs.append({"mode": mode, "network": network, "line": m["line"], "from": self.name[p], "to": self.name[u],
                             "from_id": p, "to_id": u, "minutes": round(minutes, 1),
                             "wait_minutes": round(boarding_cost(was_boarded, per_day, transfer_min), 1),
                             "stops": m["stops"][i:j + 1], "trips_per_day": per_day,
                             # minutes depuis le départ du leg, à chaque arrêt (arrivée), extrémités comprises
                             "times": [0] + [round(m["arr"][x] - m["dep"][i], 1) for x in range(i + 1, j + 1)]})
            state = (p, was_boarded)
        legs.reverse()
        rides = [leg for leg in legs if leg["mode"] != WALK]
        return {"from": legs[0]["from"], "to": legs[-1]["to"], "minutes": round(total, 1),
                "ride_minutes": round(sum(leg["minutes"] for leg in legs), 1),
                "access_minutes": sources[legs[0]["from_id"]], "egress_minutes": targets[legs[-1]["to_id"]],
                "transfers": max(len(rides) - 1, 0), "transfer_min": transfer_min, "legs": legs}


def fmt(minutes):
    m = round(minutes)
    return f"{m // 60} h {m % 60:02d}" if m >= 60 else f"{m} min"


def main():
    p = argparse.ArgumentParser(description="Plus court chemin entre deux villes/gares d'Occitanie.")
    p.add_argument("departure")
    p.add_argument("destination")
    p.add_argument("--exclude", action="append", default=[], metavar="MODE",
                   help="type de transport à ignorer (répétable) : " + ", ".join(MODES))
    p.add_argument("--exclude-network", action="append", default=[], metavar="RÉSEAU",
                   help="réseau liO à ignorer (répétable), ex. « liO 34 »")
    p.add_argument("--dataset", default="train_lio",
                   help="sous-dossier de data/ (défaut train_lio : trains TER liO) ; « full » pour la base complète")
    p.add_argument("--transfer", type=float, default=DEFAULT_TRANSFER_MIN,
                   help="minutes de changement par correspondance, en plus de l'attente estimée")
    args = p.parse_args()

    net = Network(DATA_DIR if args.dataset == "full" else DATA_DIR / args.dataset)
    unknown = set(args.exclude) - {m["id"] for m in net.modes()}
    if unknown:
        sys.exit(f"Type de transport inconnu : {', '.join(sorted(unknown))}")
    try:
        r = net.route(args.departure, args.destination, exclude=set(args.exclude),
                      exclude_networks=set(args.exclude_network), transfer_min=args.transfer)
    except UnknownPlace as e:
        sys.exit(f"Ville ou gare inconnue : {e.args[0]!r}")
    except SamePlace:
        sys.exit("Le départ et la destination désignent la même gare ou la même ville.")
    if r is None:
        sys.exit(f"Aucun itinéraire entre {args.departure} et {args.destination}.")
    n = r["transfers"]
    if r["access_minutes"] or r["egress_minutes"]:
        print(f"  (dont ~{fmt(r['access_minutes'])} pour rejoindre {r['from']}, ~{fmt(r['egress_minutes'])} depuis {r['to']})")
    print(f"{r['from']} -> {r['to']} : {fmt(r['minutes'])} "
          f"({'direct' if n == 0 else f'{n} correspondance' + ('s' if n > 1 else '')})")
    for leg in r["legs"]:
        if leg["wait_minutes"]:
            print(f"  ~{fmt(leg['wait_minutes'])} de correspondance à {leg['from']}")
        if leg["mode"] == WALK:
            print(f"  {leg['from']} -> {leg['to']}  {fmt(leg['minutes'])} à pied ({leg['line']})")
            continue
        print(f"  {leg['from']} -> {leg['to']}  {fmt(leg['minutes'])}  [{leg['network'] or leg['mode']} · {leg['line']}]"
              f"  {len(leg['stops']) - 2} arrêt(s) intermédiaire(s), {leg['trips_per_day']}/jour")


if __name__ == "__main__":
    main()
