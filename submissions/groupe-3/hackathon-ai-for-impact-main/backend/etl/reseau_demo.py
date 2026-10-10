"""Réseau liO de DÉMONSTRATION (tout est simulé : est_simule = 1).

- Gares : vraies gares d'Occitanie, coordonnées tirées de la carte du projet
  (visualisation/carte). Les codes UIC sont des codes de démonstration au format réel.
- Trains : numéros fictifs mais plausibles, horaires réalistes sans être ceux de la SNCF.
  Grille de « jour type » : lundi à vendredi identiques, samedi et dimanche réduits.
  Certains trains ne sont pas autorisés aux groupes (heures de pointe) : règle R1.
- Indicateurs mensuels : régularité 85 à 98 %, suppressions 0 à 4 %, respect de l'emport 80 à 100 %.
- Positionnements : options d'autres groupes, simulées (jamais d'identité).
"""
from __future__ import annotations

# clé -> (code UIC de démo, nom, lat, lon, commune)
GARES: dict[str, tuple[str, str, float, float, str]] = {
    "TOULOUSE": ("87611004", "Toulouse Matabiau", 43.61121, 1.45362, "Toulouse"),
    "FOIX": ("87611301", "Foix", 42.96975, 1.60715, "Foix"),
    "PAMIERS": ("87611202", "Pamiers", 43.11621, 1.61945, "Pamiers"),
    "TARASCON": ("87611400", "Tarascon-sur-Ariège", 42.84954, 1.59993, "Tarascon-sur-Ariège"),
    "AX": ("87611509", "Ax-les-Thermes", 42.72480, 1.83325, "Ax-les-Thermes"),
    "CARCASSONNE": ("87615005", "Carcassonne", 43.21803, 2.35182, "Carcassonne"),
    "CASTELNAUDARY": ("87615203", "Castelnaudary", 43.31229, 1.95039, "Castelnaudary"),
    "NARBONNE": ("87781104", "Narbonne", 43.19039, 3.00591, "Narbonne"),
    "BEZIERS": ("87781005", "Béziers", 43.33633, 3.21887, "Béziers"),
    "SETE": ("87781500", "Sète", 43.41248, 3.69656, "Sète"),
    "MONTPELLIER": ("87773002", "Montpellier Saint-Roch", 43.60474, 3.88067, "Montpellier"),
    "NIMES": ("87775007", "Nîmes", 43.83229, 4.36585, "Nîmes"),
    "PERPIGNAN": ("87784009", "Perpignan", 42.69629, 2.87978, "Perpignan"),
    "GAILLAC": ("87615500", "Gaillac", 43.90597, 1.89485, "Gaillac"),
    "ALBI": ("87615401", "Albi-Ville", 43.92238, 2.13796, "Albi"),
    "RODEZ": ("87613000", "Rodez", 44.36263, 2.58056, "Rodez"),
    "MONTAUBAN": ("87611806", "Montauban-Ville-Bourbon", 44.01439, 1.34150, "Montauban"),
    "CAHORS": ("87613109", "Cahors", 44.44928, 1.43332, "Cahors"),
    "MURET": ("87611905", "Muret", 43.46482, 1.32445, "Muret"),
    "SAINT_GAUDENS": ("87671206", "Saint-Gaudens", 43.10503, 0.72910, "Saint-Gaudens"),
    "TARBES": ("87671008", "Tarbes", 43.23996, 0.06942, "Tarbes"),
    "LOURDES": ("87671107", "Lourdes", 43.10037, -0.04217, "Lourdes"),
}

# Lignes : suite (gare, minutes de trajet depuis l'arrêt précédent). 1 min d'arrêt intermédiaire.
LIGNES: dict[str, tuple[str, list[tuple[str, int]]]] = {
    "ARIEGE_N": ("TOULOUSE - AX-LES-THERMES",
                 [("AX", 0), ("TARASCON", 23), ("FOIX", 12), ("PAMIERS", 15), ("TOULOUSE", 55)]),
    "ARIEGE_S": ("TOULOUSE - AX-LES-THERMES",
                 [("TOULOUSE", 0), ("PAMIERS", 55), ("FOIX", 15), ("TARASCON", 12), ("AX", 23)]),
    "AUDE_E": ("TOULOUSE - NARBONNE",
               [("TOULOUSE", 0), ("CASTELNAUDARY", 35), ("CARCASSONNE", 21), ("NARBONNE", 33)]),
    "AUDE_O": ("TOULOUSE - NARBONNE",
               [("NARBONNE", 0), ("CARCASSONNE", 33), ("CASTELNAUDARY", 21), ("TOULOUSE", 35)]),
    "TARN_E": ("TOULOUSE - RODEZ",
               [("TOULOUSE", 0), ("GAILLAC", 42), ("ALBI", 16), ("RODEZ", 78)]),
    "TARN_O": ("TOULOUSE - RODEZ",
               [("RODEZ", 0), ("ALBI", 78), ("GAILLAC", 16), ("TOULOUSE", 42)]),
    "QUERCY_N": ("TOULOUSE - CAHORS",
                 [("TOULOUSE", 0), ("MONTAUBAN", 30), ("CAHORS", 45)]),
    "QUERCY_S": ("TOULOUSE - CAHORS",
                 [("CAHORS", 0), ("MONTAUBAN", 45), ("TOULOUSE", 30)]),
    "LITTORAL_E": ("NARBONNE - NIMES",
                   [("NARBONNE", 0), ("BEZIERS", 14), ("SETE", 30), ("MONTPELLIER", 17),
                    ("NIMES", 28)]),
    "LITTORAL_O": ("NARBONNE - NIMES",
                   [("NIMES", 0), ("MONTPELLIER", 28), ("SETE", 17), ("BEZIERS", 30),
                    ("NARBONNE", 14)]),
    "ROUSSILLON_S": ("NARBONNE - PERPIGNAN", [("NARBONNE", 0), ("PERPIGNAN", 38)]),
    "ROUSSILLON_N": ("NARBONNE - PERPIGNAN", [("PERPIGNAN", 0), ("NARBONNE", 38)]),
    "BIGORRE_O": ("TOULOUSE - LOURDES",
                  [("TOULOUSE", 0), ("MURET", 18), ("SAINT_GAUDENS", 45), ("TARBES", 48),
                   ("LOURDES", 18)]),
    "BIGORRE_E": ("TOULOUSE - LOURDES",
                  [("LOURDES", 0), ("TARBES", 18), ("SAINT_GAUDENS", 48), ("MURET", 45),
                   ("TOULOUSE", 18)]),
}

S = "semaine"      # lundi à vendredi
T = "tous"         # tous les jours
WE = "week-end"    # samedi et dimanche seulement

# (numéro, ligne, gare de départ, heure de départ, gare terminus, autorisé groupes, jours)
TRAINS: list[tuple[str, str, str, str, str, int, str]] = [
    # Ariège -> Toulouse
    ("871601", "ARIEGE_N", "AX", "05:30", "TOULOUSE", 0, S),
    ("871603", "ARIEGE_N", "TARASCON", "06:40", "TOULOUSE", 0, S),
    ("871605", "ARIEGE_N", "AX", "07:28", "TOULOUSE", 1, S),
    ("871607", "ARIEGE_N", "TARASCON", "08:47", "TOULOUSE", 1, S),
    ("871609", "ARIEGE_N", "AX", "09:38", "TOULOUSE", 1, T),
    ("871611", "ARIEGE_N", "TARASCON", "11:57", "TOULOUSE", 1, S),
    ("871613", "ARIEGE_N", "AX", "16:28", "TOULOUSE", 0, S),
    ("871651", "ARIEGE_N", "AX", "08:28", "TOULOUSE", 1, WE),
    # Toulouse -> Ariège
    ("871620", "ARIEGE_S", "TOULOUSE", "12:40", "AX", 1, S),
    ("871622", "ARIEGE_S", "TOULOUSE", "14:35", "TARASCON", 1, S),
    ("871624", "ARIEGE_S", "TOULOUSE", "16:10", "AX", 1, T),
    ("871626", "ARIEGE_S", "TOULOUSE", "17:05", "TARASCON", 0, S),
    ("871628", "ARIEGE_S", "TOULOUSE", "17:45", "AX", 0, S),
    ("871630", "ARIEGE_S", "TOULOUSE", "18:40", "AX", 1, S),
    ("871652", "ARIEGE_S", "TOULOUSE", "15:10", "AX", 1, WE),
    # Toulouse -> Carcassonne -> Narbonne
    ("871701", "AUDE_E", "TOULOUSE", "07:05", "NARBONNE", 0, S),
    ("871703", "AUDE_E", "TOULOUSE", "09:33", "NARBONNE", 1, T),
    ("871705", "AUDE_E", "TOULOUSE", "10:33", "NARBONNE", 1, S),
    ("871707", "AUDE_E", "TOULOUSE", "12:33", "NARBONNE", 1, S),
    ("871709", "AUDE_E", "TOULOUSE", "17:03", "NARBONNE", 0, S),
    # Narbonne -> Carcassonne -> Toulouse
    ("871710", "AUDE_O", "NARBONNE", "06:50", "TOULOUSE", 0, S),
    ("871712", "AUDE_O", "NARBONNE", "12:24", "TOULOUSE", 1, S),
    ("871714", "AUDE_O", "NARBONNE", "14:24", "TOULOUSE", 1, T),
    ("871716", "AUDE_O", "NARBONNE", "15:24", "TOULOUSE", 1, S),
    ("871718", "AUDE_O", "NARBONNE", "16:24", "TOULOUSE", 0, S),
    # Toulouse -> Albi -> Rodez
    ("871801", "TARN_E", "TOULOUSE", "07:08", "RODEZ", 0, S),
    ("871803", "TARN_E", "TOULOUSE", "09:38", "RODEZ", 1, T),
    ("871805", "TARN_E", "TOULOUSE", "10:38", "ALBI", 1, S),
    ("871807", "TARN_E", "TOULOUSE", "12:38", "RODEZ", 1, S),
    ("871809", "TARN_E", "TOULOUSE", "17:08", "RODEZ", 0, S),
    # Rodez -> Albi -> Toulouse
    ("871810", "TARN_O", "ALBI", "06:55", "TOULOUSE", 0, S),
    ("871812", "TARN_O", "RODEZ", "11:00", "TOULOUSE", 1, S),
    ("871814", "TARN_O", "RODEZ", "13:33", "TOULOUSE", 1, T),
    ("871816", "TARN_O", "ALBI", "15:50", "TOULOUSE", 1, S),
    ("871818", "TARN_O", "RODEZ", "15:30", "TOULOUSE", 0, S),
    # Toulouse -> Montauban -> Cahors
    ("871901", "QUERCY_N", "TOULOUSE", "07:15", "CAHORS", 0, S),
    ("871903", "QUERCY_N", "TOULOUSE", "09:40", "CAHORS", 1, T),
    ("871905", "QUERCY_N", "TOULOUSE", "10:45", "MONTAUBAN", 1, S),
    ("871907", "QUERCY_N", "TOULOUSE", "13:40", "CAHORS", 1, S),
    # Cahors -> Montauban -> Toulouse
    ("871910", "QUERCY_S", "CAHORS", "06:50", "TOULOUSE", 0, S),
    ("871912", "QUERCY_S", "CAHORS", "12:10", "TOULOUSE", 1, S),
    ("871914", "QUERCY_S", "CAHORS", "14:15", "TOULOUSE", 1, T),
    ("871916", "QUERCY_S", "MONTAUBAN", "16:00", "TOULOUSE", 1, S),
    ("871918", "QUERCY_S", "CAHORS", "16:30", "TOULOUSE", 0, S),
    # Narbonne -> Montpellier -> Nîmes
    ("872001", "LITTORAL_E", "NARBONNE", "06:45", "NIMES", 0, S),
    ("872003", "LITTORAL_E", "NARBONNE", "09:10", "NIMES", 1, T),
    ("872005", "LITTORAL_E", "NARBONNE", "11:10", "NIMES", 1, S),
    ("872007", "LITTORAL_E", "NARBONNE", "13:10", "NIMES", 1, S),
    ("872009", "LITTORAL_E", "NARBONNE", "17:10", "NIMES", 0, S),
    # Nîmes -> Montpellier -> Narbonne
    ("872010", "LITTORAL_O", "NIMES", "07:00", "NARBONNE", 0, S),
    ("872012", "LITTORAL_O", "NIMES", "12:15", "NARBONNE", 1, S),
    ("872014", "LITTORAL_O", "NIMES", "14:15", "NARBONNE", 1, T),
    ("872016", "LITTORAL_O", "NIMES", "15:30", "NARBONNE", 1, S),
    ("872018", "LITTORAL_O", "NIMES", "16:45", "NARBONNE", 0, S),
    # Narbonne <-> Perpignan
    ("872105", "ROUSSILLON_S", "NARBONNE", "07:10", "PERPIGNAN", 0, S),
    ("872101", "ROUSSILLON_S", "NARBONNE", "09:20", "PERPIGNAN", 1, T),
    ("872103", "ROUSSILLON_S", "NARBONNE", "11:20", "PERPIGNAN", 1, S),
    ("872110", "ROUSSILLON_N", "PERPIGNAN", "13:30", "NARBONNE", 1, S),
    ("872112", "ROUSSILLON_N", "PERPIGNAN", "15:00", "NARBONNE", 1, T),
    ("872114", "ROUSSILLON_N", "PERPIGNAN", "17:00", "NARBONNE", 0, S),
    # Toulouse <-> Tarbes <-> Lourdes
    ("872201", "BIGORRE_O", "TOULOUSE", "06:50", "LOURDES", 0, S),
    ("872203", "BIGORRE_O", "TOULOUSE", "09:25", "LOURDES", 1, T),
    ("872205", "BIGORRE_O", "TOULOUSE", "11:25", "LOURDES", 1, S),
    ("872210", "BIGORRE_E", "LOURDES", "13:00", "TOULOUSE", 1, S),
    ("872212", "BIGORRE_E", "LOURDES", "14:20", "TOULOUSE", 1, T),
    ("872214", "BIGORRE_E", "LOURDES", "16:30", "TOULOUSE", 0, S),
]

# Fiabilité moyenne fixée pour les trains du scénario (régularité %, suppression %, emport %).
# Les autres trains reçoivent des valeurs pseudo-aléatoires reproductibles dans les fourchettes.
FIABILITE_FIXEE: dict[str, tuple[float, float, float]] = {
    "871605": (94.5, 1.2, 95.0),
    "871607": (96.2, 0.8, 97.0),
    "871609": (93.0, 1.5, 92.0),
    "871620": (95.0, 1.0, 96.0),
    "871622": (95.8, 0.9, 96.0),
    "871624": (91.0, 2.0, 90.0),
    "871703": (92.5, 1.8, 93.0),
    "871714": (90.5, 2.4, 91.0),
    "871803": (93.5, 1.4, 94.0),
    "871814": (92.0, 1.9, 92.0),
    "872203": (86.0, 3.6, 82.0),
}

# Options déjà posées par d'autres groupes (SIMULÉES, sans identité) : (train, date, places).
# La première est celle du scénario : premier train du matin Foix -> Toulouse le 12/11/2026.
POSITIONNEMENTS_SIMULES: list[tuple[str, str, int]] = [
    ("871605", "2026-11-12", 10),
    ("872003", "2026-11-12", 20),
    ("871703", "2026-11-19", 25),
    ("871622", "2026-11-26", 30),
    ("871803", "2026-12-03", 44),
]

DEBUT_GRILLE = "2026-02-01"
FIN_GRILLE = "2026-06-30"
MOIS_INDICATEURS = [f"2026-{m:02d}" for m in range(1, 10)]


def _hm(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def _fmt(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def arrets_du_train(ligne: str, depart: str, heure: str, terminus: str) -> list[tuple[str, str | None, str | None]]:
    """Calcule (gare, arrivée, départ) pour un train d'une ligne, avec 1 min d'arrêt."""
    _, chemin = LIGNES[ligne]
    cles = [g for g, _ in chemin]
    i0, i1 = cles.index(depart), cles.index(terminus)
    t = _hm(heure)
    arrets = [(depart, None, _fmt(t))]
    for k in range(i0 + 1, i1 + 1):
        t += chemin[k][1]
        if k == i1:
            arrets.append((cles[k], _fmt(t), None))
        else:
            arrets.append((cles[k], _fmt(t), _fmt(t + 1)))
            t += 1
    return arrets
