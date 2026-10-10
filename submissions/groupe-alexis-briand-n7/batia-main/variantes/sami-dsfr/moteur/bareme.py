"""Barème en points du défi 1 : score de risque de panne bloquante à neuf mois.

Mêmes entrées et même sortie que `moteur.risque.scorer` : les lignes des CSV du
kit (listes de dicts) et une date de référence ; pour chaque équipement du
périmètre, un score et la liste des raisons avec leurs points.

    scorer(equipements, interventions, demandes, logements, date_ref)
      -> {equipement_id: {"score": float, "points": int, "raisons": [...], "age": float, "pose": str}}

Le score est la probabilité, en pour cent, d'un dépannage « Arrêt total » dans
les neuf mois qui suivent la date de référence. Les points de chaque situation
viennent d'une régression logistique ajustée sur les situations observées au
1er janvier de 2019 à 2024 et les pannes des neuf mois suivants ; 14 points
doublent la cote. Seules les lignes antérieures à la date de référence sont
lues, et seule la vie de l'appareil en place compte.
"""

import math
import re
from datetime import datetime, timedelta

ORDONNEE = -4.672
POINTS = {
    "age_1": 11, "age_2": 28, "age_3": 35, "age_4": 40,
    "usure_1": 15, "usure_2": 39, "usure_dep": 28,
    "demande_1": 20, "demande_2": 31, "demande_nomme": 28,
    "depannage_6m": 11, "panne_reparee_24m": 9,
    "absences_1": 2, "absences_2": -1,
    "remplacement_prevu": -20,
}
BORNES_AGE = (0.25, 0.5, 0.75, 1.0)
RAISONS_MAX = 4
BANDES = (
    (0, "Rien à signaler", "0 panne sur 241 l'an dernier", "aucune"),
    (20, "Calme", "7 pannes sur 434 l'an dernier, 2 %", "3 sur 434 dans les 3 mois"),
    (40, "À surveiller", "18 pannes sur 439 l'an dernier, 4 %", "4 sur 439 dans les 3 mois"),
    (60, "Vigilance", "14 pannes sur 109 l'an dernier, 13 %", "3 sur 109 dans les 3 mois"),
    (80, "Alerte", "9 pannes sur 16 l'an dernier", "2 sur 16 dans les 3 mois"),
    (10**9, "Urgence", "28 pannes sur 46 l'an dernier, 61 %", "18 sur 46 dans les 3 mois, 40 %"),
)
COMMENTAIRES_USURE = (
    "Nombreux redémarrages enregistrés",
    "Traces de corrosion visibles sur l'appareil",
    "Usure avancée constatée, pièce à surveiller",
    "Pièce de rechange difficile à obtenir",
    "Appareil vieillissant, remplacement à prévoir",
    "Réparation provisoire, fiabilité incertaine",
)
MOTIFS_CHAUFFAGE = (
    "Panne équipement individuel électrique (chauffe eau, radiateur)",
    "panne équipement individuel gaz (chauffe eau/chaudière, radiateur)",
    "Température basse dans le logement",
    "Absence de chauffage collectif",
    "Signalement d'une panne Ascenseur",
    "VMC bruyante / Dysfonctionnement",
)
MOTS_FAMILLE = {
    "chaudiere_gaz_individuelle": r"chaudi",
    "ballon_ecs_electrique": r"cumulus|ballon|chauffe.eau",
    "ballon_thermodynamique": r"ballon|chauffe.eau|thermodynamique",
    "pompe_a_chaleur": r"pompe|pac\b|unit[ée] ext",
    "convecteurs_electriques": r"radiateur|convecteur",
    "panneaux_rayonnants": r"radiateur|panneau",
    "caisson_vmc": r"vmc|ventilation",
    "ascenseur": r"ascenseur",
    "chaufferie_collective": r"chauffage|eau chaude",
}


def _dt(texte):
    if not texte:
        return None
    texte = texte.strip()
    if len(texte) >= 16:
        return datetime(int(texte[0:4]), int(texte[5:7]), int(texte[8:10]), int(texte[11:13]), int(texte[14:16]))
    return datetime(int(texte[0:4]), int(texte[5:7]), int(texte[8:10]))


def _moins_mois(t, n):
    mois = t.month - n
    annee = t.year
    while mois <= 0:
        mois += 12
        annee -= 1
    jour = min(t.day, [31, 29 if annee % 4 == 0 and (annee % 100 != 0 or annee % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mois - 1])
    return t.replace(year=annee, month=mois, day=jour)


def _f(x, n=1):
    return f"{x:.{n}f}".replace(".", ",")


def _jour(d):
    return f"{d.day} {['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'][d.month - 1]} {d.year}"


def _pose(eq, remplacements_tous, t):
    avant = [d for d in remplacements_tous if d < t]
    if avant:
        return avant[-1]
    if not remplacements_tous:
        return _dt(eq["date_pose"])
    if len(remplacements_tous) == 1:
        return _dt(eq.get("date_pose_precedente")) or _dt(eq["date_pose"])
    return remplacements_tous[0] - timedelta(days=int(365.25 * float(eq["duree_vie_reference_ans"])))


def bande(points):
    for borne, nom, neuf_mois, trois_mois in BANDES:
        if points <= borne:
            return {"nom": nom, "neuf_mois": neuf_mois, "trois_mois": trois_mois}


def probabilite(points):
    return 1.0 / (1.0 + math.exp(-(ORDONNEE + points / 20.0)))


def scorer(equipements, interventions, demandes, logements, date_ref, residences=None):
    if isinstance(date_ref, str):
        date_ref = _dt(date_ref)
    t = datetime(date_ref.year, date_ref.month, date_ref.day) + timedelta(days=1)
    t_6m, t_12m, t_24m = _moins_mois(t, 6), _moins_mois(t, 12), _moins_mois(t, 24)

    par_eq = {}
    remplacements = {}
    for it in interventions:
        d = _dt(it["date_intervention"])
        if d is None:
            continue
        if it["type_intervention"] == "Remplacement":
            remplacements.setdefault(it["equipement_id"], []).append(d)
        if d < t:
            par_eq.setdefault(it["equipement_id"], []).append((d, it))
    for v in remplacements.values():
        v.sort()

    dem_lgt = {}
    for dm in demandes:
        d = _dt(dm["date_creation"])
        if d is None or d >= t or d < t_12m or not dm["logement_id"]:
            continue
        dem_lgt.setdefault(dm["logement_id"], []).append((d, dm["motif"] in MOTIFS_CHAUFFAGE, dm["texte_demande"].lower()))

    resultats = {}
    for eq in equipements:
        if eq.get("dans_perimetre_prediction") != "Oui":
            continue
        eid = eq["equipement_id"]
        pose = _pose(eq, remplacements.get(eid, []), t)
        duree = float(eq["duree_vie_reference_ans"])
        age = (t - pose).days / 365.25
        ratio = age / duree if duree else 0.0
        histo = sorted(par_eq.get(eid, []), key=lambda x: x[0])
        vie = [(d, it) for d, it in histo if d >= pose]

        raisons = []
        tranche = sum(1 for b in BORNES_AGE if ratio > b)
        pts_age = POINTS[f"age_{tranche}"] if tranche else 0
        raisons.append({"texte": f"{_f(age)} ans sur {int(duree)} ans de durée de vie, {round(ratio * 100)} %", "points": pts_age})

        usure = [(d, it) for d, it in vie if d >= t_12m and it["commentaire_technicien"] in COMMENTAIRES_USURE]
        if usure:
            n = len(usure)
            dernier = usure[-1][1]["commentaire_technicien"]
            if n == 1:
                raisons.append({"texte": f"1 commentaire d'usure du technicien en 12 mois : « {dernier} »", "points": POINTS["usure_1"]})
            else:
                raisons.append({"texte": f"{n} commentaires d'usure du technicien en 12 mois, le dernier : « {dernier} »", "points": POINTS["usure_2"]})
            if any(it["type_intervention"] == "Dépannage" for d, it in usure):
                raisons.append({"texte": "Commentaire d'usure écrit pendant un dépannage", "points": POINTS["usure_dep"]})

        source = dem_lgt.get(eq["logement_id"], []) if eq.get("logement_id") else []
        source = [x for x in source if x[0] >= pose]
        chauffage = [x for x in source if x[1]]
        if chauffage:
            n = len(chauffage)
            if n == 1:
                raisons.append({"texte": f"1 demande chauffage ou eau chaude du locataire en 12 mois, le {_jour(chauffage[0][0])}", "points": POINTS["demande_1"]})
            else:
                raisons.append({"texte": f"{n} demandes chauffage ou eau chaude du locataire en 12 mois", "points": POINTS["demande_2"]})
        motif = MOTS_FAMILLE.get(eq["famille"])
        if motif:
            nommees = [x for x in source if x[0] >= t_6m and re.search(motif, x[2])]
            if nommees:
                raisons.append({"texte": "La demande du locataire nomme l'appareil, dans les 6 mois", "points": POINTS["demande_nomme"]})

        depannages = [(d, it) for d, it in vie if it["type_intervention"] == "Dépannage"]
        if depannages and (t - depannages[-1][0]).days <= 180:
            raisons.append({"texte": f"Dépannage dans les 6 derniers mois, le {_jour(depannages[-1][0])}", "points": POINTS["depannage_6m"]})
        if any(d >= t_24m and it["gravite"] == "Arrêt total" for d, it in depannages):
            raisons.append({"texte": "Panne bloquante réparée sans remplacement dans les 24 mois", "points": POINTS["panne_reparee_24m"]})

        visites = [(d, it) for d, it in vie if it["type_intervention"] == "Entretien préventif"]
        absentes = [1 for d, it in visites if it["resultat"].startswith("Logement absent")]
        if visites and absentes:
            part = len(absentes) / len(visites)
            if part > 0.3:
                raisons.append({"texte": f"Visites d'entretien manquées : {len(absentes)} sur {len(visites)} depuis la pose", "points": POINTS["absences_2"]})
            elif part > 0.1:
                raisons.append({"texte": f"Visites d'entretien manquées : {len(absentes)} sur {len(visites)} depuis la pose", "points": POINTS["absences_1"]})

        rn = [d for d, it in histo if it["resultat"] == "Remplacement nécessaire" and d > pose]
        if rn:
            raisons.append({"texte": f"Remplacement déjà jugé nécessaire le {_jour(rn[-1])}", "points": POINTS["remplacement_prevu"]})

        total = sum(r["points"] for r in raisons)
        gardees = [r for r in raisons if r["texte"].startswith("Remplacement déjà jugé nécessaire")]
        autres = sorted((r for r in raisons if r not in gardees), key=lambda r: -abs(r["points"]))
        repliees = autres[RAISONS_MAX:]
        reste = sum(r["points"] for r in repliees)
        raisons = autres[:RAISONS_MAX] + gardees
        if reste:
            raisons.append({"texte": "Autres situations", "points": reste})
        resultats[eid] = {
            "score": round(100.0 * probabilite(total), 1),
            "points": total,
            "bande": bande(total),
            "raisons": raisons,
            "autres": repliees,
            "age": round(age, 1),
            "pose": pose.date().isoformat(),
        }
    return resultats
