"""Nettoyage des données brutes → data/clean/*.parquet (voir docs/PLAN_EQUIPE_DEFI_ENEDIS.md §1.4).

Tâche : T1.2 — propriétaire : P1.

Lancement :
    python -m crise.data.nettoyage                 # chemins de config/default.yaml
    python -m crise.data.nettoyage --raw data/raw --clean data/clean

Entrées (data/raw/, CSV « ; » + BOM UTF-8) :
    agents_v2.csv, poste_v2.csv, insee_v2.csv, coupures_v2_100_crises.csv

Sorties (data/clean/) :
    sites.parquet      18 sites (id_site, commune, departement, lat, lon, nb_equipes)
    postes.parquet     33 288 postes (id_poste, code_insee, commune, departement, lat, lon, x_l93, y_l93,
                       nb_clients, sensible)
    communes.parquet   1 365 communes (code_insee, commune, departement, lat, lon, nb_postes)
    incidents.parquet  incidents valides, enrichis avec les infos du poste + temps relatifs à la crise
    rapport_nettoyage.json   ce qui a été corrigé / exclu (utile pour le README et le pitch)

Corrections appliquées :
    - lecture « ; » + BOM UTF-8, tout en texte puis typage explicite (pas de devinette de pandas)
    - coordonnées : virgule décimale tolérée, contrôle de la zone géographique
    - code_insee : remis sur 5 caractères (9001 → 09001)
    - dateHeureIncident : format JJ/MM/AAAA HH:MM
    - dureeDepannage : "4h" → 240 (minutes)
    - incidents dont le poste n'existe pas (5 attendus) : EXCLUS et journalisés
    - même poste touché plusieurs fois dans une crise (43 attendus) : conservés, signalés
      (colonnes rang_sur_poste, nb_incidents_poste_crise)
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from crise.config import charger_config, chemin_projet

log = logging.getLogger("crise.nettoyage")

# Emprise géographique attendue (Ariège, Haute-Garonne, Gers) — sert de garde-fou
LAT_MIN, LAT_MAX = 42.4, 44.3
LON_MIN, LON_MAX = -0.5, 2.4
DUREES_AUTORISEES_MIN = {120, 240, 480}

FICHIERS_DEFAUT = {
    "agents": "agents_v2.csv",
    "postes": "poste_v2.csv",
    "insee": "insee_v2.csv",
    "coupures": "coupures_v2_100_crises.csv",
}


class DonneesInvalides(ValueError):
    """Levée quand un contrôle de cohérence échoue (message explicite pour l'équipe)."""


# --------------------------------------------------------------------------- utilitaires
def _lire_csv(chemin: Path) -> pd.DataFrame:
    if not chemin.exists():
        raise FileNotFoundError(f"Fichier introuvable : {chemin} — déposer les fichiers fournis dans data/raw/")
    df = pd.read_csv(chemin, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    return df.apply(lambda s: s.str.strip())


def _verifier_colonnes(df: pd.DataFrame, attendues: list[str], nom: str) -> None:
    manquantes = [c for c in attendues if c not in df.columns]
    if manquantes:
        raise DonneesInvalides(f"{nom} : colonnes manquantes {manquantes} (colonnes lues : {list(df.columns)})")


def _en_float(s: pd.Series, nom: str) -> pd.Series:
    out = pd.to_numeric(s.str.replace(",", ".", regex=False), errors="coerce")
    if out.isna().any():
        exemples = s[out.isna()].head(3).tolist()
        raise DonneesInvalides(f"{nom} : {int(out.isna().sum())} valeurs non numériques, ex. {exemples}")
    return out


def _en_int(s: pd.Series, nom: str) -> pd.Series:
    return _en_float(s, nom).round().astype("int64")


def _verifier_coordonnees(df: pd.DataFrame, nom: str) -> None:
    hors = ~(df["lat"].between(LAT_MIN, LAT_MAX) & df["lon"].between(LON_MIN, LON_MAX))
    if hors.any():
        raise DonneesInvalides(
            f"{nom} : {int(hors.sum())} lignes hors zone (lat {LAT_MIN}–{LAT_MAX}, lon {LON_MIN}–{LON_MAX}) :\n"
            f"{df.loc[hors].head(5).to_string()}"
        )


def _verifier_unicite(df: pd.DataFrame, cle: str, nom: str) -> None:
    doublons = df[cle].duplicated()
    if doublons.any():
        raise DonneesInvalides(f"{nom} : clé {cle} en double, ex. {df.loc[doublons, cle].head(3).tolist()}")


def _duree_en_minutes(s: pd.Series) -> pd.Series:
    heures = pd.to_numeric(s.str.lower().str.replace("h", "", regex=False).str.replace(",", "."), errors="coerce")
    minutes = (heures * 60).round()
    invalides = minutes.isna() | ~minutes.isin(DUREES_AUTORISEES_MIN)
    if invalides.any():
        raise DonneesInvalides(f"dureeDepannage : valeurs inattendues {s[invalides].unique()[:5].tolist()}")
    return minutes.astype("int64")


# --------------------------------------------------------------------------- lecture par fichier
def lire_sites(chemin: Path) -> pd.DataFrame:
    df = _lire_csv(chemin)
    _verifier_colonnes(df, ["id_site", "commune", "departement", "longitude", "latitude", "nb_equipes"], "agents")
    out = pd.DataFrame({
        "id_site": df["id_site"],
        "commune": df["commune"],
        "departement": df["departement"],
        "lat": _en_float(df["latitude"], "agents.latitude"),
        "lon": _en_float(df["longitude"], "agents.longitude"),
        "nb_equipes": _en_int(df["nb_equipes"], "agents.nb_equipes"),
    })
    _verifier_unicite(out, "id_site", "agents")
    _verifier_coordonnees(out, "agents")
    if (out["nb_equipes"] < 1).any():
        raise DonneesInvalides("agents : un site a moins d'une équipe")
    return out.sort_values("id_site").reset_index(drop=True)


def lire_postes(chemin: Path) -> pd.DataFrame:
    df = _lire_csv(chemin)
    _verifier_colonnes(
        df,
        ["id_poste", "code_insee", "commune", "departement", "longitude", "latitude", "x_l93", "y_l93",
         "nb_clients", "poste_avec_client_sensible"],
        "postes",
    )
    out = pd.DataFrame({
        "id_poste": df["id_poste"],
        "code_insee": df["code_insee"].str.zfill(5),
        "commune": df["commune"],
        "departement": df["departement"],
        "lat": _en_float(df["latitude"], "postes.latitude"),
        "lon": _en_float(df["longitude"], "postes.longitude"),
        "x_l93": _en_float(df["x_l93"], "postes.x_l93"),
        "y_l93": _en_float(df["y_l93"], "postes.y_l93"),
        "nb_clients": _en_int(df["nb_clients"], "postes.nb_clients"),
        "sensible": _en_int(df["poste_avec_client_sensible"], "postes.sensible").astype(bool),
    })
    _verifier_unicite(out, "id_poste", "postes")
    _verifier_coordonnees(out, "postes")
    if (out["nb_clients"] <= 0).any():
        raise DonneesInvalides("postes : nb_clients doit être > 0")
    return out


def lire_communes(chemin: Path) -> pd.DataFrame:
    df = _lire_csv(chemin)
    _verifier_colonnes(df, ["code_insee", "commune", "departement", "latitude", "longitude", "nb_postes"], "insee")
    out = pd.DataFrame({
        "code_insee": df["code_insee"].str.zfill(5),
        "commune": df["commune"],
        "departement": df["departement"],
        "lat": _en_float(df["latitude"], "insee.latitude"),
        "lon": _en_float(df["longitude"], "insee.longitude"),
        "nb_postes": _en_int(df["nb_postes"], "insee.nb_postes"),
    })
    _verifier_unicite(out, "code_insee", "insee")
    _verifier_coordonnees(out, "insee")
    return out


def lire_coupures(chemin: Path) -> pd.DataFrame:
    df = _lire_csv(chemin)
    _verifier_colonnes(
        df, ["numero_crise", "id_incident", "id_poste", "causeInterruption", "dateHeureIncident", "dureeDepannage"],
        "coupures",
    )
    date = pd.to_datetime(df["dateHeureIncident"], format="%d/%m/%Y %H:%M", errors="coerce")
    if date.isna().any():
        exemples = df.loc[date.isna(), "dateHeureIncident"].head(3).tolist()
        raise DonneesInvalides(f"coupures : dates illisibles, ex. {exemples}")
    out = pd.DataFrame({
        "numero_crise": df["numero_crise"],
        "id_incident": df["id_incident"],
        "id_poste": df["id_poste"],
        "cause": df["causeInterruption"],
        "date_incident": date,
        "duree_min": _duree_en_minutes(df["dureeDepannage"]),
    })
    _verifier_unicite(out, "id_incident", "coupures")
    return out


# --------------------------------------------------------------------------- assemblage
def construire_incidents(coupures: pd.DataFrame, postes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Jointure coupures ↔ postes. Renvoie (incidents valides, incidents exclus)."""
    connus = coupures["id_poste"].isin(postes["id_poste"])
    exclus = coupures.loc[~connus].copy()
    inc = coupures.loc[connus].merge(
        postes[["id_poste", "code_insee", "commune", "departement", "lat", "lon", "nb_clients", "sensible"]],
        on="id_poste", how="left", validate="many_to_one",
    )

    # Temps relatifs à la crise (minutes depuis le premier incident de la crise)
    debut = inc.groupby("numero_crise")["date_incident"].transform("min")
    inc["debut_crise"] = debut
    inc["t_apparition"] = ((inc["date_incident"] - debut).dt.total_seconds() // 60).astype("int64")

    # Même poste touché plusieurs fois dans une crise : on garde, on signale
    inc = inc.sort_values(["numero_crise", "date_incident", "id_incident"]).reset_index(drop=True)
    inc["rang_sur_poste"] = inc.groupby(["numero_crise", "id_poste"]).cumcount() + 1
    inc["nb_incidents_poste_crise"] = inc.groupby(["numero_crise", "id_poste"])["id_incident"].transform("size")

    colonnes = ["numero_crise", "id_incident", "id_poste", "code_insee", "commune", "departement", "lat", "lon",
                "nb_clients", "sensible", "cause", "date_incident", "debut_crise", "t_apparition", "duree_min",
                "rang_sur_poste", "nb_incidents_poste_crise"]
    return inc[colonnes], exclus


def controles_globaux(sites, postes, communes, incidents) -> None:
    """Garde-fous de cohérence entre fichiers."""
    inconnues = ~postes["code_insee"].isin(communes["code_insee"])
    if inconnues.any():
        raise DonneesInvalides(f"postes : {int(inconnues.sum())} code_insee absents du référentiel des communes")
    if incidents["t_apparition"].lt(0).any():
        raise DonneesInvalides("incidents : t_apparition négatif")
    if incidents[["lat", "lon", "nb_clients"]].isna().any().any():
        raise DonneesInvalides("incidents : valeurs manquantes après jointure avec les postes")


def nettoyer(raw: Path, clean: Path, fichiers: dict | None = None) -> dict:
    """Pipeline complet. Écrit les parquet dans `clean` et renvoie le rapport (dict)."""
    f = {**FICHIERS_DEFAUT, **(fichiers or {})}
    raw, clean = Path(raw), Path(clean)
    clean.mkdir(parents=True, exist_ok=True)

    sites = lire_sites(raw / f["agents"])
    postes = lire_postes(raw / f["postes"])
    communes = lire_communes(raw / f["insee"])
    coupures = lire_coupures(raw / f["coupures"])
    incidents, exclus = construire_incidents(coupures, postes)
    controles_globaux(sites, postes, communes, incidents)

    sites.to_parquet(clean / "sites.parquet", index=False)
    postes.to_parquet(clean / "postes.parquet", index=False)
    communes.to_parquet(clean / "communes.parquet", index=False)
    incidents.to_parquet(clean / "incidents.parquet", index=False)

    multi = incidents[incidents["nb_incidents_poste_crise"] > 1]
    par_crise = incidents.groupby("numero_crise").agg(
        n=("id_incident", "size"), fenetre_min=("t_apparition", "max"))
    rapport = {
        "sites": len(sites),
        "equipes": int(sites["nb_equipes"].sum()),
        "equipes_par_departement": sites.groupby("departement")["nb_equipes"].sum().astype(int).to_dict(),
        "postes": len(postes),
        "clients_total": int(postes["nb_clients"].sum()),
        "postes_sensibles": int(postes["sensible"].sum()),
        "communes": len(communes),
        "crises": int(incidents["numero_crise"].nunique()),
        "incidents_lus": len(coupures),
        "incidents_valides": len(incidents),
        "incidents_exclus_poste_inconnu": exclus[["numero_crise", "id_incident", "id_poste"]].to_dict("records"),
        "incidents_meme_poste_meme_crise": int((incidents["rang_sur_poste"] > 1).sum()),
        "postes_touches_plusieurs_fois": int(multi.groupby(["numero_crise", "id_poste"]).ngroups),
        "incidents_par_crise": {"min": int(par_crise["n"].min()), "moyenne": round(float(par_crise["n"].mean()), 1),
                                "max": int(par_crise["n"].max())},
        "fenetre_apparition_h": {"min": round(par_crise["fenetre_min"].min() / 60, 2),
                                 "moyenne": round(par_crise["fenetre_min"].mean() / 60, 2),
                                 "max": round(par_crise["fenetre_min"].max() / 60, 2)},
        "durees_min": incidents["duree_min"].value_counts().sort_index().astype(int).to_dict(),
    }
    rapport["durees_min"] = {str(k): v for k, v in rapport["durees_min"].items()}
    with open(clean / "rapport_nettoyage.json", "w", encoding="utf-8") as fh:
        json.dump(rapport, fh, ensure_ascii=False, indent=2)

    log.info("Sites : %s (%s équipes)", rapport["sites"], rapport["equipes"])
    log.info("Postes : %s (%s sensibles) — communes : %s", rapport["postes"], rapport["postes_sensibles"],
             rapport["communes"])
    log.info("Incidents : %s lus, %s valides, %s exclus (poste inconnu)", rapport["incidents_lus"],
             rapport["incidents_valides"], len(rapport["incidents_exclus_poste_inconnu"]))
    for e in rapport["incidents_exclus_poste_inconnu"]:
        log.info("   exclu : %s %s → %s", e["numero_crise"], e["id_incident"], e["id_poste"])
    log.info("Postes touchés plusieurs fois dans une même crise : %s (conservés, signalés)",
             rapport["postes_touches_plusieurs_fois"])
    log.info("Fichiers écrits dans %s", clean)
    return rapport


def main(argv: list[str] | None = None) -> None:
    cfg = charger_config()
    p = argparse.ArgumentParser(description="Nettoyage des données du défi Enedis")
    p.add_argument("--raw", default=str(chemin_projet(cfg["chemins"]["raw"])))
    p.add_argument("--clean", default=str(chemin_projet(cfg["chemins"]["clean"])))
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    nettoyer(Path(args.raw), Path(args.clean), cfg.get("fichiers_bruts"))


if __name__ == "__main__":
    main()
