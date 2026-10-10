"""Générateur de données simulées pour le copilote du voyage scolaire.

Produit les fichiers sites.csv, avis.csv et options.csv dans donnees_simulees/.
Toutes les données sont déterministes (graine fixe) et contiennent la colonne source = 'simulé'.
"""

import os
import random
import pandas as pd
import numpy as np

# ==========================================
# Constantes configurables
# ==========================================
GRAINE = 42
DOSSIER_SORTIE = "donnees_simulees"
FICHIER_HACKATHON = "Data_Hackathon.csv"
SOURCE_LABEL = "simulé"

# Dates réalistes de circulation pour la démo (période scolaire mai-juin 2026)
DATES_OPTIONS = [
    "2026-05-12",
    "2026-05-19",
    "2026-05-26",
    "2026-06-02",
    "2026-06-09",
    "2026-06-16",
]


def obtenir_sites_culturels():
    """Renvoie la liste des 15 sites culturels d'Occitanie avec les pièges pour la démo."""
    return [
        {
            "site_id": "SITE_01",
            "nom_site": "Cité Médiévale de Carcassonne",
            "gare_proche": "Carcassonne",
            "distance_m": 2100,
            "bus_unique": True,
            "trottoir_ok": True,
            "pique_nique_couvert": True,
            "consignes": True,
            "theme": "Histoire",
        },
        {
            "site_id": "SITE_02",
            "nom_site": "Musée Toulouse-Lautrec",
            "gare_proche": "Albi Ville",
            "distance_m": 950,
            "bus_unique": False,
            "trottoir_ok": True,
            "pique_nique_couvert": False,
            "consignes": True,
            "theme": "Art",
        },
        {
            "site_id": "SITE_03",
            "nom_site": "Château de Foix",
            "gare_proche": "Foix",
            "distance_m": 800,
            "bus_unique": False,
            "trottoir_ok": True,
            "pique_nique_couvert": True,
            "consignes": True,
            "theme": "Histoire",
        },
        {
            "site_id": "SITE_04",
            "nom_site": "Cité de l'Espace",
            "gare_proche": "Toulouse Matabiau",
            "distance_m": 4800,
            "bus_unique": True,
            "trottoir_ok": True,
            "pique_nique_couvert": True,
            "consignes": True,
            "theme": "Sciences",
        },
        {
            "site_id": "SITE_05",
            "nom_site": "Arènes de Nîmes",
            "gare_proche": "Nîmes Centre",
            "distance_m": 450,
            "bus_unique": False,
            "trottoir_ok": True,
            "pique_nique_couvert": False,
            "consignes": True,
            "theme": "Histoire",
        },
        {
            "site_id": "SITE_06",
            "nom_site": "Musée Fabre",
            "gare_proche": "Montpellier Saint-Roch",
            "distance_m": 850,
            "bus_unique": False,
            "trottoir_ok": True,
            "pique_nique_couvert": False,
            "consignes": True,
            "theme": "Art",
        },
        {
            "site_id": "SITE_07",
            "nom_site": "Château Royal de Collioure",
            "gare_proche": "Collioure",
            "distance_m": 600,
            "bus_unique": False,
            "trottoir_ok": True,
            "pique_nique_couvert": False,
            "consignes": False,
            "theme": "Histoire",
        },
        {
            "site_id": "SITE_08",
            "nom_site": "Tours et Remparts d'Aigues-Mortes",
            "gare_proche": "Aigues-Mortes",
            "distance_m": 700,
            "bus_unique": False,
            "trottoir_ok": True,
            "pique_nique_couvert": True,
            "consignes": True,
            "theme": "Histoire",
        },
        {
            "site_id": "SITE_09",
            "nom_site": "Musée Soulages",
            "gare_proche": "Rodez",
            "distance_m": 1300,
            "bus_unique": True,
            "trottoir_ok": True,
            "pique_nique_couvert": False,
            "consignes": True,
            "theme": "Art",
        },
        {
            "site_id": "SITE_10",
            "nom_site": "Pont Valentré et Ville Médiévale",
            "gare_proche": "Cahors",
            "distance_m": 1100,
            "bus_unique": False,
            "trottoir_ok": True,
            "pique_nique_couvert": True,
            "consignes": False,
            "theme": "Histoire",
        },
        {
            "site_id": "SITE_11",
            "nom_site": "Musée Jean Jaurès",
            "gare_proche": "Castres",
            "distance_m": 900,
            "bus_unique": False,
            "trottoir_ok": True,
            "pique_nique_couvert": False,
            "consignes": False,
            "theme": "Histoire",
        },
        {
            "site_id": "SITE_12",
            "nom_site": "Espace Georges Brassens",
            "gare_proche": "Sète",
            "distance_m": 3200,
            "bus_unique": True,
            "trottoir_ok": True,
            "pique_nique_couvert": False,
            "consignes": True,
            "theme": "Culture",
        },
        # --- CAS PIÈGE 1 : 35 min de marche sans bus (1750 m à 3 km/h = 35 min) ---
        {
            "site_id": "SITE_13",
            "nom_site": "Grotte Préhistorique de Bédeilhac",
            "gare_proche": "Foix",
            "distance_m": 1750,
            "bus_unique": False,
            "trottoir_ok": True,
            "pique_nique_couvert": True,
            "consignes": False,
            "theme": "Préhistoire",
        },
        # --- CAS PIÈGE 2 : Cheminement piéton sans trottoir (danger sécurité) ---
        {
            "site_id": "SITE_14",
            "nom_site": "Fort Saint-Elme (accès crête)",
            "gare_proche": "Collioure",
            "distance_m": 1100,
            "bus_unique": False,
            "trottoir_ok": False,
            "pique_nique_couvert": False,
            "consignes": False,
            "theme": "Histoire",
        },
        # --- CAS PIÈGE 3 : Site sans avis d'enseignants (test valeur manquante) ---
        {
            "site_id": "SITE_15",
            "nom_site": "Musée Ingres Bourdelle",
            "gare_proche": "Montauban Ville Bourbon",
            "distance_m": 800,
            "bus_unique": False,
            "trottoir_ok": True,
            "pique_nique_couvert": True,
            "consignes": True,
            "theme": "Art",
        },
    ]


def generer_avis(liste_sites):
    """Génère les notes et nombres d'avis pour chaque site (avec un cas piège à 0 avis)."""
    lignes_avis = []
    # Notes et avis prédéfinis de manière déterministe
    donnees_notes = [
        (4.8, 11),  # SITE_01 Coup de coeur
        (4.6, 9),   # SITE_02
        (4.7, 12),  # SITE_03 Coup de coeur
        (4.9, 12),  # SITE_04 Coup de coeur
        (4.5, 8),   # SITE_05
        (4.4, 7),   # SITE_06
        (4.2, 5),   # SITE_07
        (4.6, 10),  # SITE_08
        (4.3, 6),   # SITE_09
        (3.9, 4),   # SITE_10
        (3.8, 3),   # SITE_11
        (4.1, 5),   # SITE_12
        (3.5, 2),   # SITE_13
        (2.8, 4),   # SITE_14
        (None, 0),  # SITE_15 -> CAS PIÈGE : 0 avis (inconnu)
    ]

    for site_info, (note, nb) in zip(liste_sites, donnees_notes):
        lignes_avis.append({
            "site_id": site_info["site_id"],
            "nom_site": site_info["nom_site"],
            "note_moyenne": note if note is not None else "",
            "nb_avis": nb,
            "source": SOURCE_LABEL,
        })
    return pd.DataFrame(lignes_avis)


def charger_trains_reels(chemin_csv, nb_trains=30):
    """Extrait nb_trains numéros de trains réels et uniques de Data_Hackathon.csv."""
    df = pd.read_csv(chemin_csv, sep=";", encoding="utf-8-sig")
    trains = sorted(df["N° Train"].dropna().unique().tolist())
    # Sélectionner 30 trains de façon déterministe
    rng = random.Random(GRAINE)
    selection = rng.sample(trains, min(nb_trains, len(trains)))
    return sorted(selection)


def generer_options(trains_reels):
    """Génère des options sans nom d'école, avec des trains presque pleins pour la démo."""
    rng = random.Random(GRAINE)
    lignes_options = []

    # Distribution réaliste de places prises : 0 à 45
    for i, train in enumerate(trains_reels):
        # Associer 1 à 3 dates par train
        nb_dates = rng.choice([1, 2, 3])
        dates_choisies = rng.sample(DATES_OPTIONS, nb_dates)
        
        for j, date in enumerate(dates_choisies):
            # CAS PIÈGE 4 : Train presque plein (45 places prises sur 50) pour le premier train
            if i == 0 and j == 0:
                places = 45
            # Train bien rempli (35-40 places)
            elif i == 1 and j == 0:
                places = 38
            # Train vide (0 place prise)
            elif i == 2:
                places = 0
            else:
                places = rng.randint(0, 30)

            lignes_options.append({
                "n_train": train,
                "date": date,
                "places_prises": places,
                "source": SOURCE_LABEL,
            })

    return pd.DataFrame(lignes_options)


def generer_toutes_les_donnees():
    """Point d'entrée principal pour générer les 3 fichiers CSV simulés."""
    random.seed(GRAINE)
    np.random.seed(GRAINE)

    os.makedirs(DOSSIER_SORTIE, exist_ok=True)

    # 1. Génération de sites.csv
    sites_liste = obtenir_sites_culturels()
    df_sites = pd.DataFrame(sites_liste)
    df_sites["source"] = SOURCE_LABEL
    chemin_sites = os.path.join(DOSSIER_SORTIE, "sites.csv")
    df_sites.to_csv(chemin_sites, sep=";", index=False, encoding="utf-8-sig")
    print(f"[OK] {len(df_sites)} sites écrits dans {chemin_sites}")

    # 2. Génération de avis.csv
    df_avis = generer_avis(sites_liste)
    chemin_avis = os.path.join(DOSSIER_SORTIE, "avis.csv")
    df_avis.to_csv(chemin_avis, sep=";", index=False, encoding="utf-8-sig")
    print(f"[OK] {len(df_avis)} avis écrits dans {chemin_avis}")

    # 3. Génération de options.csv (30 trains réels)
    trains_reels = charger_trains_reels(FICHIER_HACKATHON, nb_trains=30)
    df_options = generer_options(trains_reels)
    chemin_options = os.path.join(DOSSIER_SORTIE, "options.csv")
    df_options.to_csv(chemin_options, sep=";", index=False, encoding="utf-8-sig")
    print(f"[OK] {len(df_options)} options posées ({len(trains_reels)} trains réels) écrites dans {chemin_options}")


if __name__ == "__main__":
    generer_toutes_les_donnees()
