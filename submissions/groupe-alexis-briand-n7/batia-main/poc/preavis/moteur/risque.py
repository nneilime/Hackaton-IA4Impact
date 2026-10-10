"""Moteur de risque de panne — méthode explicable par points additifs.

Module isolé et remplaçable : une seule fonction publique, `scorer`.

Entrée : les lignes des CSV du kit (listes de dicts, colonnes d'origine)
et une date de référence. Sortie : pour chaque équipement du périmètre,
un score de 0 à 100 et la liste des raisons qui le composent.

    scorer(equipements, interventions, demandes, logements, date_ref)
      -> {equipement_id: {"score": float, "raisons": [{"texte": str, "points": float}]}}

Règle anti-fuite : seules les lignes datées au plus tard à `date_ref`
sont lues. L'historique d'un emplacement antérieur à la dernière pose
(appareil précédent) est ignoré.
"""

import re
from datetime import date, timedelta

# --- Poids (réglés sur la fenêtre 31/12/2023 -> janv.-sept. 2024) -----------
POIDS = {
    "usure_max": 40.0,        # points d'usure quand l'âge atteint la durée de vie
    "usure_forme": 3.0,       # forme de la courbe (Weibull : usure croissante)
    "usure_plafond": 55.0,    # au-delà de la durée de vie, l'usure continue de monter
    "arret_total": 9.0,       # par dépannage « Arrêt total » sur 12 mois
    "degrade": 6.0,           # par dépannage « Fonctionnement dégradé » sur 12 mois
    "gene": 2.5,              # par dépannage « Gêne mineure » sur 12 mois
    "depannage_plafond": 30.0,
    "commentaire_usure": 9.0,  # par commentaire d'usure sur 18 mois
    "commentaire_grave": 14.0, # par commentaire de fin de vie sur 18 mois
    "commentaire_plafond": 32.0,
    "anomalie": 5.0,          # « Anomalie constatée » / « Remplacement nécessaire » sur 18 mois
    "anomalie_plafond": 15.0,
    "absences_max": 10.0,     # part des visites manquées sur 3 ans
    "demande_liee": 6.0,      # par demande locataire liée à l'équipement sur 12 mois
    "demande_plafond": 14.0,
    "demande_repetee": 6.0,   # bonus si la demande revient ou est rouverte
    "grand_logement": 2.0,
}

COMMENTAIRES_USURE = (
    "Usure avancée constatée",
    "Appareil vieillissant",
    "Réparation provisoire",
    "Pièce de rechange difficile",
    "Traces de corrosion",
    "Nombreux redémarrages",
)
COMMENTAIRES_GRAVES = (
    "Défaillance majeure",
    "Panne irréparable",
    "hors service",
)

# Mots qui relient une demande locataire à une famille d'équipement.
MOTS_CHAUFFAGE = r"chauff|radiateur|convecteur|froid|température basse|panneau"
MOTS_ECS = r"eau chaude|eau tiède|cumulus|ballon|chauffe[- ]eau"
MOTS_FAMILLE = {
    "chaudiere_gaz_individuelle": MOTS_CHAUFFAGE + r"|chaudi|" + MOTS_ECS + r"|pression|gaz",
    "convecteurs_electriques": MOTS_CHAUFFAGE,
    "panneaux_rayonnants": MOTS_CHAUFFAGE,
    "ballon_ecs_electrique": MOTS_ECS,
    "ballon_thermodynamique": MOTS_ECS,
    "pompe_a_chaleur": MOTS_CHAUFFAGE + r"|pompe à chaleur|\bpac\b|unité extérieure",
    "ascenseur": r"ascenseur",
    "caisson_vmc": r"vmc|ventilation",
    "chaufferie_collective": r"chauffage collectif|chauffage dans l'immeuble|radiateurs froids|eau chaude dans la résidence",
    "production_ecs_solaire": r"eau chaude dans la résidence|eau chaude",
}


def _d(texte):
    """'2024-05-29' ou '2024-05-29 10:12' -> date ; vide -> None."""
    if not texte:
        return None
    return date(int(texte[0:4]), int(texte[5:7]), int(texte[8:10]))


def _f(x, n=1):
    """Nombre au format français : 14.2 -> '14,2'."""
    return f"{x:.{n}f}".replace(".", ",")


def _pluriel(n, mot, mot_pluriel=None):
    return f"{n} {mot if n <= 1 else (mot_pluriel or mot + 's')}"


def _pose_a_date(eq, remplacements, date_ref, origine):
    """Date de pose de l'appareil en place à date_ref (sans regarder après)."""
    candidats = [d for d in remplacements if d <= date_ref]
    pose = _d(eq["date_pose"])
    if pose and pose <= date_ref:
        candidats.append(pose)
    else:
        prec = _d(eq.get("date_pose_precedente"))
        if prec and prec <= date_ref:
            candidats.append(prec)
    if candidats:
        return max(candidats)
    return origine


def scorer(equipements, interventions, demandes, logements, date_ref, residences=None):
    if isinstance(date_ref, str):
        date_ref = _d(date_ref)
    il_y_a_12m = date_ref - timedelta(days=365)
    il_y_a_18m = date_ref - timedelta(days=548)
    il_y_a_36m = date_ref - timedelta(days=3 * 365)

    construction = {}
    for r in residences or []:
        construction[r["residence_id"]] = date(int(r["annee_construction"]), 6, 1)

    surfaces = {l["logement_id"]: float(l["surface_habitable_m2"] or 0) for l in logements}

    # Index des interventions par équipement (passé seulement).
    par_eq = {}
    for it in interventions:
        d = _d(it["date_intervention"])
        if d is None or d > date_ref:
            continue
        par_eq.setdefault(it["equipement_id"], []).append((d, it))

    # Index des demandes par logement et par bâtiment (passé seulement).
    dem_lgt, dem_bat = {}, {}
    for dm in demandes:
        d = _d(dm["date_creation"])
        if d is None or d > date_ref:
            continue
        texte = " ".join((dm["objet"], dm["motif"], dm["texte_demande"])).lower()
        ligne = (d, texte, dm["demande_reouverte"] == "Oui", dm["objet"])
        if dm["logement_id"]:
            dem_lgt.setdefault(dm["logement_id"], []).append(ligne)
        if dm["batiment_id"] and (dm["parties"] == "Communes" or not dm["logement_id"]):
            dem_bat.setdefault(dm["batiment_id"], []).append(ligne)

    resultats = {}
    for eq in equipements:
        if eq.get("dans_perimetre_prediction") != "Oui":
            continue
        eid = eq["equipement_id"]
        histo = sorted(par_eq.get(eid, []), key=lambda x: x[0])
        remplacements = [d for d, it in histo if it["type_intervention"] == "Remplacement"]
        origine = construction.get(eq["residence_id"]) or _d(eq["date_pose"])
        pose = _pose_a_date(eq, remplacements, date_ref, origine)
        # On ne garde que la vie de l'appareil actuellement en place.
        histo = [(d, it) for d, it in histo if d >= pose]

        raisons = []

        # 1. Usure : âge rapporté à la durée de vie de référence.
        duree = float(eq["duree_vie_reference_ans"])
        age = (date_ref - pose).days / 365.25
        ratio = age / duree if duree else 0
        pts = min(POIDS["usure_plafond"], POIDS["usure_max"] * ratio ** POIDS["usure_forme"])
        if pts >= 0.5:
            raisons.append({
                "texte": f"{_f(age)} ans sur {int(duree)} ans de durée de vie ({round(ratio * 100)} %)",
                "points": pts,
            })

        # 2. Dépannages des 12 derniers mois.
        dep = [it for d, it in histo if d > il_y_a_12m and it["type_intervention"] == "Dépannage"]
        if dep:
            n_arret = sum(1 for it in dep if it["gravite"] == "Arrêt total")
            n_degr = sum(1 for it in dep if it["gravite"] == "Fonctionnement dégradé")
            n_gene = len(dep) - n_arret - n_degr
            pts = min(POIDS["depannage_plafond"],
                      n_arret * POIDS["arret_total"] + n_degr * POIDS["degrade"] + n_gene * POIDS["gene"])
            details = []
            if n_arret:
                details.append(_pluriel(n_arret, "arrêt total", "arrêts totaux"))
            if n_degr:
                details.append(_pluriel(n_degr, "fonctionnement dégradé", "fonctionnements dégradés"))
            texte = f"{_pluriel(len(dep), 'dépannage')} en 12 mois"
            if details:
                texte += " (dont " + ", ".join(details) + ")"
            raisons.append({"texte": texte, "points": pts})

        # 3. Commentaires des techniciens sur 18 mois.
        com = [it["commentaire_technicien"] for d, it in histo if d > il_y_a_18m]
        n_usure = sum(1 for c in com if any(m in c for m in COMMENTAIRES_USURE))
        n_grave = sum(1 for c in com if any(m in c for m in COMMENTAIRES_GRAVES))
        if n_usure or n_grave:
            pts = min(POIDS["commentaire_plafond"],
                      n_usure * POIDS["commentaire_usure"] + n_grave * POIDS["commentaire_grave"])
            exemples = [c for c in com if any(m in c for m in COMMENTAIRES_GRAVES + COMMENTAIRES_USURE)]
            dernier = exemples[-1] if exemples else ""
            n = n_usure + n_grave
            raisons.append({
                "texte": f"{_pluriel(n, 'note', 'notes')} de technicien sur l'usure en 18 mois, dont « {dernier} »",
                "points": pts,
            })

        # 4. Anomalies constatées en visite / remplacement jugé nécessaire.
        ano = [it for d, it in histo if d > il_y_a_18m
               and it["resultat"] in ("Anomalie constatée", "Remplacement nécessaire")]
        if ano:
            n_ano = sum(1 for it in ano if it["resultat"] == "Anomalie constatée")
            n_rn = len(ano) - n_ano
            morceaux = []
            if n_ano:
                morceaux.append(_pluriel(n_ano, "anomalie constatée", "anomalies constatées"))
            if n_rn:
                morceaux.append(f"{n_rn} × « remplacement nécessaire »")
            raisons.append({
                "texte": " et ".join(morceaux) + " en 18 mois",
                "points": min(POIDS["anomalie_plafond"], len(ano) * POIDS["anomalie"]),
            })

        # 5. Visites d'entretien manquées (logement absent) sur 3 ans.
        visites = [it for d, it in histo if d > il_y_a_36m and it["type_intervention"] == "Entretien préventif"]
        absents = [it for it in visites if it["resultat"].startswith("Logement absent")]
        if len(visites) >= 2 and absents:
            part = len(absents) / len(visites)
            if part >= 0.34:
                raisons.append({
                    "texte": f"Entretien manqué : {len(absents)} visite{'s' if len(absents) > 1 else ''} sur {len(visites)} sans accès au logement (3 ans)",
                    "points": POIDS["absences_max"] * part,
                })

        # 6. Demandes des locataires liées à cet équipement (12 mois).
        motif = MOTS_FAMILLE.get(eq["famille"])
        if motif:
            if eq["logement_id"]:
                source = dem_lgt.get(eq["logement_id"], [])
            else:
                source = dem_bat.get(eq["batiment_id"], [])
            liees = [x for x in source if x[0] > il_y_a_12m and x[0] >= pose and re.search(motif, x[1])]
            if liees:
                pts = min(POIDS["demande_plafond"], len(liees) * POIDS["demande_liee"])
                texte = f"{_pluriel(len(liees), 'demande')} du locataire sur ce sujet en 12 mois"
                if eq["logement_id"] == "":
                    texte = f"{_pluriel(len(liees), 'demande')} des locataires de l'immeuble sur ce sujet en 12 mois"
                rouvertes = sum(1 for x in liees if x[2])
                if len(liees) >= 2 or rouvertes:
                    pts += POIDS["demande_repetee"]
                    if rouvertes:
                        texte += f", {_pluriel(rouvertes, 'rouverte')}"
                    else:
                        texte += " : la demande revient"
                raisons.append({"texte": texte, "points": pts})

        # 7. Grand logement : usage plus intense.
        surf = surfaces.get(eq["logement_id"], 0)
        if surf >= 85:
            raisons.append({
                "texte": f"Grand logement ({_f(surf, 0)} m²) : appareil plus sollicité",
                "points": POIDS["grand_logement"],
            })

        score = min(100.0, sum(r["points"] for r in raisons))
        for r in raisons:
            r["points"] = round(r["points"], 1)
        raisons.sort(key=lambda r: -r["points"])
        resultats[eid] = {
            "score": round(score, 1),
            "raisons": raisons,
            "age": round(age, 1),
            "pose": pose.isoformat(),
        }
    return resultats
