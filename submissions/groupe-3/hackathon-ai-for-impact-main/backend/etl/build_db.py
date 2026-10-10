"""Construit lio.db à partir des VRAIS fichiers SNCF du hackathon, s'ils sont présents.

Fichiers attendus dans data/ (racine du repo) ou backend/data/ (jamais commités) :
- desserte.csv        export de « Détail desserte » (colonnes date, train, ordre, code, stop, arr, dep),
                      produit par visualisation/scripts/xlsx_to_csv.py ;
- Data_Hackathon.csv  indicateurs mensuels par train, séparateur « ; » ;
- gares.json          référentiel open data SNCF (codes_uic, position_geographique, nom) ;
- optionnel : un fichier dont le nom contient « groupe » (.csv, ou .xlsx si openpyxl est installé)
  listant les trains autorisés aux groupes. À défaut, on considère autorisés les trains présents
  dans Data_Hackathon.csv (hypothèse : ce fichier ne couvre que les trains groupes) et on le signale.

Le catalogue de sites (etl/catalogue.py) est rattaché aux gares par leur nom.
Une option simulée (10 places, est_simule = 1) est posée sur le premier train groupe du matin
Foix -> Toulouse le jeudi type, pour rejouer le scénario de démonstration.

Usage : python -m etl.build_db
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from app import config, db
from . import commun, import_datatourisme, import_sncf

MOIS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout",
        "septembre", "octobre", "novembre", "decembre"]
FICHIERS = ("desserte.csv", "Data_Hackathon.csv", "gares.json")


def trouver_dossier() -> Path | None:
    for d in config.dossiers_donnees():
        if all((d / f).exists() for f in FICHIERS):
            return d
    return None


def fichiers_sncf_disponibles() -> bool:
    return import_sncf.fichiers_disponibles() or trouver_dossier() is not None


def _num_train(v: str) -> str:
    v = (v or "").strip()
    if re.fullmatch(r"\d+\.0+", v):
        v = v.split(".")[0]
    return v.replace(" ", "")


def _heure(v: str) -> str | None:
    v = (v or "").strip()
    if not v:
        return None
    m = re.match(r"(\d{1,2}):(\d{2})", v)
    if not m:
        return None
    h = int(m.group(1)) % 24
    return f"{h:02d}:{m.group(2)}"


def _taux(v: str) -> float | None:
    """'63,20%' -> 63.2 ; '0,632' -> 63.2 ; '' -> None. Tous les taux sont ramenés sur 0-100."""
    v = (v or "").strip().replace("%", "").replace(" ", "").replace(" ", "").replace(",", ".")
    if not v:
        return None
    try:
        x = float(v)
    except ValueError:
        return None
    return x * 100 if 0 <= x <= 1.0 else x


def _nombre(v: str) -> float | None:
    v = (v or "").strip().replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        return float(v) if v else None
    except ValueError:
        return None


def _colonne(entetes: list[str], *mots: str, exclure: tuple[str, ...] = ()) -> str | None:
    for e in entetes:
        n = commun.normaliser(e)
        if all(m in n for m in mots) and not any(x in n for x in exclure):
            return e
    return None


def _trains_groupes(dossier: Path) -> set[str] | None:
    for f in sorted(dossier.iterdir()):
        if "groupe" not in commun.normaliser(f.stem):
            continue
        lignes: list[list[str]] = []
        if f.suffix.lower() == ".csv":
            texte = f.read_text(encoding="utf-8-sig", errors="replace")
            delim = ";" if texte.count(";") > texte.count(",") else ","
            lignes = list(csv.reader(texte.splitlines(), delimiter=delim))
        elif f.suffix.lower() in (".xlsx", ".xlsm"):
            try:
                import openpyxl  # type: ignore
            except ImportError:
                print(f"{f.name} ignoré : installez openpyxl ou convertissez-le en CSV.", file=sys.stderr)
                continue
            ws = openpyxl.load_workbook(f, read_only=True, data_only=True).active
            lignes = [["" if c is None else str(c) for c in r] for r in ws.iter_rows(values_only=True)]
        if not lignes:
            continue
        entetes = lignes[0]
        idx = next((i for i, e in enumerate(entetes) if "train" in commun.normaliser(str(e))), 0)
        trains = {_num_train(str(r[idx])) for r in lignes[1:] if len(r) > idx}
        trains = {t for t in trains if t.isdigit()}
        if trains:
            print(f"Liste des trains groupes : {f.name} ({len(trains)} trains)", file=sys.stderr)
            return trains
    return None


def construire(path: Path | None = None) -> None:
    """Base « sncf » : fichiers bruts (xlsx, import_sncf) en priorité, sinon export CSV historique."""
    dossier = trouver_dossier()
    if dossier is None and import_sncf.fichiers_disponibles():
        return import_sncf.construire(path)
    if dossier is None:
        raise FileNotFoundError("Fichiers SNCF introuvables dans data/ : " + ", ".join(FICHIERS))
    path = path or config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    # --- gares.json ---------------------------------------------------------------------------
    ref_gares: dict[str, tuple[float, float, str]] = {}
    for g in json.load(open(dossier / "gares.json", encoding="utf-8")):
        p = g.get("position_geographique")
        if p and g.get("codes_uic"):
            for c in str(g["codes_uic"]).split(";"):
                ref_gares[c.strip()[:8]] = (p["lat"], p["lon"], g.get("nom") or "")

    def resoudre_gare(code: str, nom: str) -> tuple[str, float | None, float | None]:
        m = re.search(r"(\d{7,8})$", code or "")
        uic7 = m.group(1)[:7] if m else None
        if uic7:
            for k, (lat, lon, _) in ref_gares.items():
                if k.startswith(uic7):
                    return k, lat, lon
            return m.group(1), None, None
        return "X" + commun.normaliser(nom).replace(" ", "")[:20], None, None

    # --- desserte.csv ----------------------------------------------------------------------------
    gares: dict[str, tuple[str, float | None, float | None]] = {}
    lignes_desserte = []
    trains_desserte: set[str] = set()
    circulations_par_mois: dict[tuple[str, str], set[str]] = defaultdict(set)
    with open(dossier / "desserte.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            train = _num_train(r.get("train", ""))
            jour = (r.get("date") or "").strip()[:10]
            if not train or not jour:
                continue
            uic, lat, lon = resoudre_gare(r.get("code", ""), r.get("stop", ""))
            gares.setdefault(uic, (r.get("stop", "").strip(), lat, lon))
            d = date.fromisoformat(jour)
            lignes_desserte.append((train, jour, d.isoweekday(), int(float(r.get("ordre") or 0)), uic,
                                    _heure(r.get("arr", "")), _heure(r.get("dep", ""))))
            trains_desserte.add(train)
            circulations_par_mois[(train, jour[:7])].add(jour)

    # --- Data_Hackathon.csv -----------------------------------------------------------------------
    indicateurs = []
    infos_train: dict[str, tuple[str, str]] = {}
    with open(dossier / "Data_Hackathon.csv", encoding="utf-8-sig") as f:
        lecteur = csv.DictReader(f, delimiter=";")
        e = lecteur.fieldnames or []
        c_train = _colonne(e, "train") or "N° Train"
        c_mois, c_annee = _colonne(e, "mois"), _colonne(e, "annee")
        c_axe, c_od = _colonne(e, "axe"), _colonne(e, "origine")
        c_freq = _colonne(e, "frequentation")
        c_reg = _colonne(e, "regularite")
        c_tsup = _colonne(e, "taux", "suppression")
        c_nsup = _colonne(e, "suppression", exclure=("taux",))
        c_emport = _colonne(e, "emport")
        c_min = _colonne(e, "minutes")
        c_circ = _colonne(e, "circulation", exclure=("realis",))
        c_real = _colonne(e, "realis")
        for r in lecteur:
            train = _num_train(r.get(c_train, ""))
            if not train:
                continue
            try:
                m = MOIS.index(commun.normaliser(r.get(c_mois, ""))) + 1
                mois = f"{int(float(r.get(c_annee) or 0))}-{m:02d}"
            except (ValueError, TypeError):
                continue
            infos_train[train] = ((r.get(c_axe) or "").strip(), (r.get(c_od) or "").strip())
            nsup = _nombre(r.get(c_nsup, "")) if c_nsup else None
            circ = _nombre(r.get(c_circ, "")) if c_circ else None
            if circ is None:
                circ = float(len(circulations_par_mois.get((train, mois), ()))) or None
            tsup = _taux(r.get(c_tsup, "")) if c_tsup else None
            if tsup is None and nsup is not None and circ:
                tsup = 100.0 * nsup / circ
            indicateurs.append((
                train, mois, int(circ) if circ else None,
                int(_nombre(r.get(c_real, "")) or 0) if c_real else None,
                _nombre(r.get(c_freq, "")) if c_freq else None,
                _taux(r.get(c_reg, "")) if c_reg else None,
                int(nsup) if nsup is not None else None, tsup,
                _taux(r.get(c_emport, "")) if c_emport else None,
                _nombre(r.get(c_min, "")) if c_min else None,
            ))

    liste_groupes = _trains_groupes(dossier)
    if liste_groupes is None:
        print("Pas de liste des trains groupes : hypothèse, les trains de Data_Hackathon.csv "
              "sont autorisés aux groupes.", file=sys.stderr)
        liste_groupes = set(infos_train)

    with db.connexion(path) as conn:
        db.creer_schema(conn)
        conn.executemany(
            "INSERT INTO gare (code_uic, nom, lat, lon, commune, est_simule) VALUES (?,?,?,?,NULL,0)",
            [(k, nom, lat, lon) for k, (nom, lat, lon) in gares.items()],
        )
        for t in sorted(trains_desserte | set(infos_train)):
            axe, od = infos_train.get(t, ("", ""))
            orig, _, dest = od.partition("/")
            conn.execute(
                """INSERT INTO train (numero, axe, origine, destination, autorise_groupe,
                     capacite_groupe, est_simule) VALUES (?,?,?,?,?,?,0)""",
                (t, axe, orig.strip(), dest.strip(), 1 if t in liste_groupes else 0,
                 config.CAPACITE_GROUPE),
            )
        conn.executemany(
            """INSERT INTO desserte (train_numero, date_circulation, jour_semaine, ordre, gare_uic,
                 heure_arrivee, heure_depart, est_simule) VALUES (?,?,?,?,?,?,?,0)""",
            lignes_desserte,
        )
        conn.executemany(
            """INSERT OR REPLACE INTO indicateur_mensuel (train_numero, mois,
                 circulations_theoriques, circulations_realisees, frequentation, taux_regularite,
                 nb_suppressions, taux_suppression, taux_respect_emport, minutes_perdues, est_simule)
               VALUES (?,?,?,?,?,?,?,?,?,?,0)""",
            indicateurs,
        )
        commun.calculer_fiabilite(conn)
        ignores = commun.inserer_sites(conn, est_simule=0)
        if ignores:
            print("Sites du catalogue sans gare correspondante :", ignores, file=sys.stderr)
        _option_scenario(conn)
        # Lieux DATAtourisme en complément du catalogue fait main (voir etl/import_datatourisme.py).
        import_datatourisme.importer_si_disponible(conn)
        db.meta_set(conn, "donnees", "sncf")
        db.meta_set(conn, "construite_le", db.maintenant_iso())
        db.meta_set(conn, "sequence_dossier", "0")
        db.meta_set(conn, "source", f"fichiers SNCF ({dossier})")
    print(f"Base SNCF créée : {path} ({len(lignes_desserte)} arrêts, {len(gares)} gares, "
          f"{len(indicateurs)} indicateurs mensuels)", file=sys.stderr)


def _option_scenario(conn) -> None:
    """Option simulée d'un autre groupe sur le premier train groupe du matin Foix -> Toulouse."""
    gares = {commun.normaliser(r["nom"]): r["code_uic"] for r in conn.execute("SELECT * FROM gare")}
    foix, toulouse = gares.get("foix"), gares.get("toulouse matabiau")
    if not foix or not toulouse:
        return
    row = conn.execute(
        """SELECT a.train_numero, a.heure_depart FROM desserte a
           JOIN desserte b ON b.train_numero = a.train_numero
                AND b.date_circulation = a.date_circulation AND b.ordre > a.ordre
           JOIN train t ON t.numero = a.train_numero AND t.autorise_groupe = 1
           WHERE a.gare_uic = ? AND b.gare_uic = ? AND a.jour_semaine = 4
             AND a.heure_depart >= '08:00'
           ORDER BY a.date_circulation DESC, a.heure_depart LIMIT 1""",
        (foix, toulouse),
    ).fetchone()
    if row:
        conn.execute(
            """INSERT INTO positionnement (train_numero, date_sortie, nb_places, dossier_reference,
                 est_simule) VALUES (?, '2026-11-12', 10, NULL, 1)""",
            (row["train_numero"],),
        )
    commun.inserer_retours_simules(conn)


if __name__ == "__main__":
    construire()
