"""indice_confiance.py - Calculateur de l'Indicateur de Confiance (score 0 à 100)
Hackathon "IA for Impact" — Défi SNCF TER liO : Copilote du voyage scolaire.

Style simple : fonctions et dictionnaires, pas de classes ni métaprogrammation.
4 piliers, 8 sous-critères :
  1. Fiabilité ferroviaire (30 %) : régularité, suppressions, stabilité de l'offre, fréquentation
  2. Faisabilité terrain   (20 %) : accès dernier km, sécurité du cheminement, marge horaire
  3. Capacité / jauge      (40 %) : plafond de 50 voyageurs, options déjà posées
  4. Pairs & confort       (10 %) : avis (coup de cœur), logistique de survie, adéquation pédagogique
"""

import json
import re
import sys
import unicodedata

import pandas as pd

# =====================================================================
# 1. PARAMÈTRES (constantes réglables en haut du fichier)
# =====================================================================

# Poids des 4 piliers (somme = 1.0)
POIDS = {
    "fiabilite": 0.30,
    "faisabilite": 0.20,
    "capacite": 0.40,
    "pairs": 0.10,
}

# Poids des sous-critères par pilier (somme = 1.0 chacun)
POIDS_FIABILITE = {
    "regularite": 0.40,
    "suppressions": 0.25,
    "stabilite": 0.15,
    "frequentation": 0.20,
}
POIDS_FAISABILITE = {
    "accessibilite": 0.50,
    "securite": 0.20,
    "marge": 0.30,
}
POIDS_PAIRS = {
    "avis": 0.50,
    "logistique": 0.25,
    "adequation": 0.25,
}

# --- Règles validées par l'équipe ---
CAPACITE_MAX = 50            # Règle d'or : 50 voyageurs maximum
VITESSE_MARCHE_KMH = 2.75    # 2.5 - 3.0 km/h (rythme groupe)
SEUIL_MARCHE_MIN = 20        # <= 20 min à pied = note max
SEUIL_VERT = 85              # 85-100 : vert
SEUIL_ORANGE = 65            # 65-84 : orange ; < 65 : rouge
PLAFOND_SI_VETO = 64         # Veto force le rouge (< 65)

# --- Seuils et pénalités de gestion ---
SEUIL_SUPPRESSION_CHRONIQUE = 10.0   # % suppressions => veto
FACTEUR_PENALITE_SUPPRESSION = 5.0   # 5 pts par % de suppression
SEUIL_REGULARITE_ALERTE = 85         # Alerte si en dessous
SEUIL_STABILITE_ALERTE = 90          # Alerte si en dessous
SEUIL_POINTE = 0.75                  # Percentile fréquentation => heure de pointe
DECOTE_BUS = 15                      # Décote si bus nécessaire
BUS_TRAJET_MIN = 15                  # Durée estimée en bus urbain
MARGE_CONFORT_MIN = 20               # Marge >= 20 min : note max
MARGE_MINIMALE_MIN = 15              # Marge < 15 min : veto
TAUX_OCCUPATION_CONFORT = 0.60       # Remplissage <= 60 % : note max
NOTE_MARGE_PLEINE = 40               # Note marge de places quand plein
NOTE_PAIRS_NEUTRE = 70               # Note neutre si aucun avis
SEUIL_COUP_DE_COEUR = 4.5            # Note moyenne /5 pour coup de coeur
MIN_AVIS_COUP_DE_COEUR = 3           # Nombre minimum d'avis pour le badge
POINTS_PIQUE_NIQUE = 60              # Logistique pique-nique couvert
POINTS_CONSIGNES = 40                # Logistique consignes sacs
NOTE_HORS_THEME = 30                 # Site sans rapport avec le thème
DEFAUT_REGULARITE = 80.0             # Valeur prudente si donnée manquante


# =====================================================================
# 2. OUTILS
# =====================================================================

def borner(valeur, bas=0.0, haut=100.0):
    """Force une valeur numérique à rester entre bas et haut."""
    return max(bas, min(haut, valeur))


def moyenne_ponderee(elements):
    """Calcule la moyenne pondérée en ignorant les valeurs None et en re-normalisant."""
    total = 0.0
    total_poids = 0.0
    for note, poids in elements:
        if note is None:
            continue
        total += note * poids
        total_poids += poids
    if total_poids == 0:
        return None
    return total / total_poids


def minutes_de_marche(distance_m, vitesse_kmh=VITESSE_MARCHE_KMH):
    """Convertit une distance en mètres en minutes de marche pour un groupe."""
    metres_par_minute = vitesse_kmh * 1000 / 60
    return distance_m / metres_par_minute


def minutes_de_trajet_gare_site(distance_m, bus_unique):
    """Calcule la durée de trajet gare-site à pied ou en bus urbain."""
    marche = minutes_de_marche(distance_m)
    if marche <= SEUIL_MARCHE_MIN:
        return marche
    if bus_unique:
        return float(BUS_TRAJET_MIN)
    return marche


def heure_en_minutes(valeur):
    """Convertit 'HH:MM:SS', 'HH:MM' ou un entier en minutes depuis minuit."""
    if valeur is None:
        return None
    if isinstance(valeur, (int, float)):
        return None if pd.isna(valeur) else int(valeur)
    morceaux = str(valeur).strip().split(":")
    if len(morceaux) < 2:
        return None
    try:
        return int(morceaux[0]) * 60 + int(morceaux[1])
    except ValueError:
        return None


def liste_themes(valeur):
    """Normalise une chaîne ou une liste de thèmes en liste de minuscules."""
    if valeur is None:
        return []
    if isinstance(valeur, str):
        valeur = re.split(r"[;,|]", valeur)
    return [normaliser_texte(t) for t in valeur if str(t).strip()]


# =====================================================================
# 3. LES 4 PILIERS
# =====================================================================

def score_fiabilite(train):
    """Calcule la note du pilier fiabilité ferroviaire et détecte les alertes/vetos."""
    regularite = train["regularite_pct"]
    suppression = train["suppression_pct"]
    stabilite = train.get("stabilite_pct", 100.0)
    pointe = train["frequentation_percentile"]

    details = {
        "regularite": borner(regularite),
        "suppressions": borner(100 - FACTEUR_PENALITE_SUPPRESSION * suppression),
        "stabilite": borner(stabilite),
        "frequentation": 100 * (1 - borner(pointe, 0, 1)),
    }
    alertes = []
    vetos = []

    if suppression >= SEUIL_SUPPRESSION_CHRONIQUE:
        vetos.append(f"Train à fort risque d'annulation ({suppression:.0f} % de suppressions)")
        details["suppressions"] = 0.0
    if regularite < SEUIL_REGULARITE_ALERTE:
        alertes.append(f"Régularité du train moyenne ({regularite:.0f} %)")
    if stabilite < SEUIL_STABILITE_ALERTE:
        alertes.append(f"Offre instable ({stabilite:.0f} % des circulations prévues réalisées)")
    if pointe >= SEUIL_POINTE:
        alertes.append("Train habituellement très fréquenté (heure de pointe)")

    note = moyenne_ponderee([(details[k], POIDS_FIABILITE[k]) for k in POIDS_FIABILITE])
    return note, details, alertes, vetos


def score_faisabilite(site, heure_arrivee_gare=None, heure_debut_activite=None):
    """Calcule la note de faisabilité terrain (accès, trottoir, marge horaire)."""
    distance_m = site["distance_m"]
    bus_unique = bool(site.get("bus_unique", False))
    trottoir_ok = site.get("trottoir_ok")
    marche = minutes_de_marche(distance_m)

    details = {}
    alertes = []
    vetos = []

    # Accès dernier kilomètre
    if marche <= SEUIL_MARCHE_MIN:
        details["accessibilite"] = 100.0
        if marche > 15:
            alertes.append(f"Marche proche de la limite ({marche:.0f} min)")
    elif bus_unique:
        details["accessibilite"] = 100.0 - DECOTE_BUS
        alertes.append(f"Correspondance bus nécessaire (marche de {marche:.0f} min sinon)")
    else:
        details["accessibilite"] = 0.0
        vetos.append(f"Marche de {marche:.0f} min sans bus (> {SEUIL_MARCHE_MIN} min avec un groupe)")

    # Sécurité du cheminement piéton
    if trottoir_ok is True:
        details["securite"] = 100.0
    elif trottoir_ok is False:
        details["securite"] = 0.0
        vetos.append("Cheminement piéton dangereux (pas de trottoir)")
    else:
        details["securite"] = None
        alertes.append("Securite du cheminement non verifiee")

    # Marge horaire avant le début de l'activité
    arrivee = heure_en_minutes(heure_arrivee_gare)
    debut = heure_en_minutes(heure_debut_activite)
    if arrivee is None or debut is None:
        details["marge"] = None
    else:
        trajet = minutes_de_trajet_gare_site(distance_m, bus_unique)
        marge = debut - (arrivee + trajet)
        if marge >= MARGE_CONFORT_MIN:
            details["marge"] = 100.0
        elif marge >= MARGE_MINIMALE_MIN:
            ecart = (marge - MARGE_MINIMALE_MIN) / (MARGE_CONFORT_MIN - MARGE_MINIMALE_MIN)
            details["marge"] = 60.0 + 40.0 * ecart
            alertes.append(f"Marge horaire serrée ({marge:.0f} min avant l'activité)")
        else:
            details["marge"] = 0.0
            vetos.append(f"Marge horaire insuffisante ({marge:.0f} min avant l'activité, "
                         f"{MARGE_MINIMALE_MIN} min nécessaires)")

    note = moyenne_ponderee([(details[k], POIDS_FAISABILITE[k]) for k in POIDS_FAISABILITE])
    return note, details, alertes, vetos


def score_capacite(effectif, options_actives):
    """Calcule le respect de la jauge stricte de 50 voyageurs max par train."""
    alertes = []
    vetos = []
    total = effectif + options_actives

    if total > CAPACITE_MAX:
        vetos.append(f"Capacite actuellement insuffisante : {total} voyageurs "
                     f"pour {CAPACITE_MAX} places groupe")
        return 0.0, {"places": 0.0}, alertes, vetos

    occupation = total / CAPACITE_MAX
    if occupation <= TAUX_OCCUPATION_CONFORT:
        note = 100.0
    else:
        pente = (100 - NOTE_MARGE_PLEINE) / (1 - TAUX_OCCUPATION_CONFORT)
        note = 100 - (occupation - TAUX_OCCUPATION_CONFORT) * pente

    if occupation > 0.9:
        alertes.append(f"Train presque plein ({total}/{CAPACITE_MAX} places groupe)")
    return note, {"places": note}, alertes, vetos


def score_pairs(site, theme_projet=None):
    """Calcule la note des retours pairs, logistique de confort et thème pédagogique."""
    alertes = []
    details = {}

    # Avis enseignants
    note_moyenne = site.get("note_moyenne")
    nb_avis = site.get("nb_avis") or 0
    badge = False
    if note_moyenne is None or nb_avis == 0 or pd.isna(note_moyenne):
        details["avis"] = float(NOTE_PAIRS_NEUTRE)
        alertes.append("Pas encore d'avis d'enseignants")
    else:
        details["avis"] = borner(note_moyenne / 5 * 100)
        badge = note_moyenne >= SEUIL_COUP_DE_COEUR and nb_avis >= MIN_AVIS_COUP_DE_COEUR

    # Logistique pratique
    pique_nique = site.get("pique_nique_couvert")
    consignes = site.get("consignes")
    if pique_nique is None and consignes is None:
        details["logistique"] = None
    else:
        details["logistique"] = (POINTS_PIQUE_NIQUE * (pique_nique is True)
                                 + POINTS_CONSIGNES * (consignes is True))
        if pique_nique is False:
            alertes.append("Pas d'espace pique-nique couvert sur le site")
        if consignes is False:
            alertes.append("Pas de consignes pour les sacs sur le site")

    # Adéquation au thème pédagogique
    themes_site = liste_themes(site.get("themes"))
    if not theme_projet or not themes_site:
        details["adequation"] = None
    elif normaliser_texte(theme_projet) in themes_site:
        details["adequation"] = 100.0
    else:
        details["adequation"] = float(NOTE_HORS_THEME)
        alertes.append("Site peu en rapport avec le thème du projet")

    note = moyenne_ponderee([(details[k], POIDS_PAIRS[k]) for k in POIDS_PAIRS])
    return note, details, alertes, [], badge


# =====================================================================
# 4. CALCUL DE L'INDICE GLOBAL
# =====================================================================

def couleur_depuis_score(score, veto_actif):
    """Détermine la pastille couleur (vert, orange, rouge) selon le score et veto."""
    if veto_actif or score < SEUIL_ORANGE:
        return "rouge"
    if score < SEUIL_VERT:
        return "orange"
    return "vert"


def calculer_indice(train, site, effectif, options_actives, theme_projet=None,
                    heure_arrivee_gare=None, heure_debut_activite=None):
    """Calcule l'Indicateur de Confiance (0-100) complet pour un triplet de voyage."""
    n_fiab, d_fiab, a_fiab, v_fiab = score_fiabilite(train)
    n_fais, d_fais, a_fais, v_fais = score_faisabilite(site, heure_arrivee_gare,
                                                       heure_debut_activite)
    n_cap, d_cap, a_cap, v_cap = score_capacite(effectif, options_actives)
    n_pairs, d_pairs, a_pairs, v_pairs, badge = score_pairs(site, theme_projet)

    piliers = {
        "fiabilite": (n_fiab, d_fiab),
        "faisabilite": (n_fais, d_fais),
        "capacite": (n_cap, d_cap),
        "pairs": (n_pairs, d_pairs),
    }

    composantes = {}
    score_brut = 0.0
    for nom, (note, details) in piliers.items():
        points = note * POIDS[nom]
        score_brut += points
        composantes[nom] = {
            "note": round(note, 1),
            "poids": POIDS[nom],
            "points": round(points, 1),
            "details": {k: (None if v is None else round(v, 1)) for k, v in details.items()},
        }

    vetos = v_fiab + v_fais + v_cap + v_pairs
    alertes = a_fiab + a_fais + a_cap + a_pairs

    score = min(score_brut, PLAFOND_SI_VETO) if vetos else score_brut
    score = int(round(borner(score)))
    couleur = couleur_depuis_score(score, bool(vetos))

    if vetos:
        message = "Trajet bloque : " + " ; ".join(vetos)
    elif alertes:
        message = "Trajet réalisable, à surveiller : " + " ; ".join(alertes)
    else:
        message = "Trajet fluide et sécurisé. Pré-réservation recommandée."

    manque = {nom: POIDS[nom] * (100 - c["note"]) for nom, c in composantes.items()}
    point_faible = max(manque, key=manque.get)

    return {
        "score": score,
        "couleur": couleur,
        "bloque": bool(vetos),
        "vetos": vetos,
        "alertes": alertes,
        "message": message,
        "composantes": composantes,
        "point_faible": point_faible,
        "badge_coup_de_coeur": badge,
    }


# =====================================================================
# 5. CHARGEMENT ET AGREGATION DES DONNEES
# =====================================================================

def normaliser_texte(texte):
    """Normalise un texte en minuscules sans accents ni ponctuation."""
    texte = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", texte.lower()).strip("_")


def trouver_colonne(df, *mots):
    """Trouve la colonne dont le nom normalisé contient tous les mots clés demandés."""
    for col in df.columns:
        if all(mot in col for mot in mots):
            return col
    raise KeyError(f"Aucune colonne ne contient {mots}. Colonnes dispo : {list(df.columns)}")


def trouver_colonne_train(df):
    """Identifie la colonne désignant le numéro de train dans le DataFrame."""
    for nom in ("n_train", "no_train", "numero_train", "num_train"):
        if nom in df.columns:
            return nom
    for col in df.columns:
        if "train" in col and "taux" not in col and "nombre" not in col:
            return col
    raise KeyError(f"Colonne du numéro de train introuvable. Colonnes dispo : {list(df.columns)}")


def cle_train(valeur):
    """Convertit un numéro de train en chaîne propre sans décimale."""
    return str(int(float(valeur)))


def lire_csv_souple(chemin_csv):
    """Lit un CSV avec détection automatique de l'encodage et du délimiteur."""
    for encodage in ("utf-8-sig", "latin-1"):
        try:
            with open(chemin_csv, encoding=encodage) as fichier:
                premiere_ligne = fichier.readline()
            separateur = ";" if premiere_ligne.count(";") > premiere_ligne.count(",") else ","
            df = pd.read_csv(chemin_csv, sep=separateur, encoding=encodage)
            df.columns = [normaliser_texte(c) for c in df.columns]
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Impossible de lire {chemin_csv} (encodage inconnu)")


def en_nombre(serie):
    """Convertit une série textuelle avec % et virgules en valeurs numériques float."""
    texte = serie.astype(str).str.replace(",", ".", regex=False)
    texte = texte.str.replace("%", "", regex=False).str.strip()
    return pd.to_numeric(texte, errors="coerce")


def profil_d_un_train(groupe):
    """Agrège l'historique mensuel d'un train en un profil synthétique unique."""
    realisees = groupe["_real"].sum()
    theoriques = groupe["_theo"].sum()
    suppressions = groupe["_supp"].sum()

    valides = groupe.dropna(subset=["_regul"])
    poids = valides["_real"]
    if len(valides) == 0:
        regularite = DEFAUT_REGULARITE
    elif poids.sum() > 0:
        regularite = float((valides["_regul"] * poids).sum() / poids.sum())
    else:
        regularite = float(valides["_regul"].mean())

    if realisees > 0:
        suppression = 100 * suppressions / realisees
    else:
        suppression = 100.0 if suppressions > 0 else 0.0
    suppression = borner(float(suppression))

    stabilite = borner(100 * realisees / theoriques) if theoriques > 0 else 100.0

    frequentation = groupe["_freq"].mean()
    return {
        "regularite_pct": borner(regularite),
        "suppression_pct": suppression,
        "stabilite_pct": float(stabilite),
        "frequentation_moyenne": None if pd.isna(frequentation) else float(frequentation),
        "axe": str(groupe["axe"].iloc[0]) if "axe" in groupe.columns else "",
        "nb_mois": int(len(groupe)),
    }


def charger_profils_trains(chemin_csv):
    """Charge et agrège Data_Hackathon.csv en un dictionnaire de profils par train."""
    df = lire_csv_souple(chemin_csv)

    col_train = trouver_colonne_train(df)
    col_regul = trouver_colonne(df, "regularite")
    col_supp = trouver_colonne(df, "nombre", "suppression")
    col_theo = trouver_colonne(df, "theorique")
    col_real = trouver_colonne(df, "realise")
    col_freq = trouver_colonne(df, "frequentation")

    df["_train"] = en_nombre(df[col_train])
    df["_regul"] = en_nombre(df[col_regul])
    df["_supp"] = en_nombre(df[col_supp]).fillna(0)
    df["_theo"] = en_nombre(df[col_theo]).fillna(0)
    df["_real"] = en_nombre(df[col_real]).fillna(0)
    df["_freq"] = en_nombre(df[col_freq])
    df = df.dropna(subset=["_train"])

    if df["_regul"].max() <= 1.0:
        df["_regul"] = df["_regul"] * 100

    profils = {}
    for numero, groupe in df.groupby("_train"):
        profils[cle_train(numero)] = profil_d_un_train(groupe)

    frequentations = pd.Series({k: p["frequentation_moyenne"] for k, p in profils.items()},
                                dtype="float64")
    percentiles = frequentations.rank(pct=True)
    for numero, profil in profils.items():
        valeur = percentiles[numero]
        profil["frequentation_percentile"] = 0.5 if pd.isna(valeur) else float(valeur)

    return profils


def colonne_en_minutes(serie):
    """Convertit une série d'heures HH:MM:SS en minutes depuis minuit."""
    morceaux = serie.astype(str).str.split(":", expand=True)
    if morceaux.shape[1] < 2:
        return pd.Series(float("nan"), index=serie.index)
    heures = pd.to_numeric(morceaux[0], errors="coerce")
    minutes = pd.to_numeric(morceaux[1], errors="coerce")
    return heures * 60 + minutes


def charger_desserte(chemin_csv, trains_utiles=None):
    """Charge les arrêts du fichier de desserte avec filtres et normalisation."""
    df = lire_csv_souple(chemin_csv)

    col_num = trouver_colonne(df, "numero", "circulation")
    col_date = trouver_colonne(df, "date")
    col_arrivee = trouver_colonne(df, "arrivee")
    col_depart = trouver_colonne(df, "depart")
    col_gare = trouver_colonne(df, "libelle")
    col_ordre = trouver_colonne(df, "ordre")

    df["_train"] = pd.to_numeric(df[col_num], errors="coerce")
    df = df.dropna(subset=["_train"])
    if trains_utiles is not None:
        trains_utiles_set = {int(t) for t in trains_utiles}
        df = df[df["_train"].isin(trains_utiles_set)]

    dates = pd.to_datetime(df[col_date], format="%d/%m/%Y", errors="coerce")
    if dates.isna().any():
        dates = dates.fillna(pd.to_datetime(df[col_date], dayfirst=True, errors="coerce"))

    gares_normalisees = {g: normaliser_texte(g) for g in df[col_gare].unique()}

    return pd.DataFrame({
        "train": df["_train"].astype("int64"),
        "date": dates,
        "gare": df[col_gare].map(gares_normalisees),
        "arrivee_min": colonne_en_minutes(df[col_arrivee]),
        "depart_min": colonne_en_minutes(df[col_depart]),
        "ordre": pd.to_numeric(df[col_ordre], errors="coerce"),
    })


def trains_eligibles(desserte):
    """Renvoie l'ensemble des numéros de trains uniques présents dans la desserte."""
    return {cle_train(t) for t in desserte["train"].unique()}


def heure_arrivee_en_gare(desserte, n_train, date, gare):
    """Renvoie l'heure d'arrivée en minutes à une gare donnée pour un train et une date."""
    selection = desserte[(desserte["train"] == int(n_train))
                         & (desserte["gare"] == normaliser_texte(gare))]
    if date is not None:
        selection = selection[selection["date"] == pd.Timestamp(date)]
    if selection.empty:
        return None
    valeur = selection.iloc[0]["arrivee_min"]
    return None if pd.isna(valeur) else int(valeur)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        profils = charger_profils_trains(sys.argv[1])
        print(f"{len(profils)} profils de trains charges avec succes.")
    else:
        print("Indicateur de confiance prêt.")
