"""Accès SQLite : schéma (repris de livrables/05-mcd-mld.md), connexion, métadonnées.

Écarts assumés avec le MLD, tous additifs :
- colonne `est_simule` sur les tables de référence (gare, train, desserte, indicateurs, site)
  pour ne jamais présenter une donnée de démonstration comme réelle ;
- `proposition.id` est un texte (proposition_id du contrat) et la proposition complète est
  stockée en JSON pour pouvoir être pré-réservée telle qu'elle a été montrée ;
- `dossier.statut` accepte CONTRE_PROPOSITION (présent dans le contrat d'API) ;
- table `dossier_historique` pour les étapes du dossier, table `meta` pour l'état de la base.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
  cle    TEXT PRIMARY KEY,
  valeur TEXT
);

CREATE TABLE IF NOT EXISTS gare (
  code_uic   TEXT PRIMARY KEY,
  nom        TEXT NOT NULL,
  lat        REAL,
  lon        REAL,
  commune    TEXT,
  est_simule INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS train (
  numero          TEXT PRIMARY KEY,
  axe             TEXT,
  origine         TEXT,
  destination     TEXT,
  autorise_groupe INTEGER NOT NULL DEFAULT 0,
  capacite_groupe INTEGER NOT NULL DEFAULT 50,
  est_simule      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS desserte (
  id               INTEGER PRIMARY KEY,
  train_numero     TEXT    NOT NULL REFERENCES train(numero),
  date_circulation TEXT    NOT NULL,
  jour_semaine     INTEGER NOT NULL,
  ordre            INTEGER NOT NULL,
  gare_uic         TEXT    NOT NULL REFERENCES gare(code_uic),
  heure_arrivee    TEXT,
  heure_depart     TEXT,
  est_simule       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_desserte_gare ON desserte (gare_uic, jour_semaine);
CREATE INDEX IF NOT EXISTS idx_desserte_train ON desserte (train_numero, date_circulation);
CREATE INDEX IF NOT EXISTS idx_desserte_date ON desserte (date_circulation);

CREATE TABLE IF NOT EXISTS indicateur_mensuel (
  train_numero            TEXT NOT NULL REFERENCES train(numero),
  mois                    TEXT NOT NULL,
  circulations_theoriques INTEGER,
  circulations_realisees  INTEGER,
  frequentation           REAL,
  nb_retards              INTEGER,
  taux_regularite         REAL,
  nb_suppressions         INTEGER,
  taux_suppression        REAL,
  taux_respect_emport     REAL,
  nb_incidents            INTEGER,
  nb_trains_impactes      INTEGER,
  nb_ventes               INTEGER,
  minutes_perdues         REAL,
  est_simule              INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (train_numero, mois)
);

CREATE TABLE IF NOT EXISTS fiabilite_train (
  train_numero        TEXT PRIMARY KEY REFERENCES train(numero),
  taux_regularite     REAL,
  taux_suppression    REAL,
  taux_respect_emport REAL,
  frequentation_moy   REAL,
  minutes_perdues_moy REAL,
  nb_mois             INTEGER,
  est_simule          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS site_culturel (
  id                    TEXT PRIMARY KEY,
  nom                   TEXT NOT NULL,
  commune               TEXT,
  lat                   REAL,
  lon                   REAL,
  gare_uic              TEXT NOT NULL REFERENCES gare(code_uic),
  minutes_pied          INTEGER,
  minutes_pied_groupe   INTEGER,
  acces_urbain          TEXT,
  minutes_urbain        INTEGER,
  correspondances_urbain INTEGER,
  themes                TEXT,
  niveaux               TEXT,
  activites             TEXT,
  interet_pedagogique   TEXT,
  richesse              INTEGER NOT NULL DEFAULT 2,
  heure_ouverture       TEXT,
  heure_fermeture       TEXT,
  duree_visite_min      INTEGER,
  horaires              TEXT,
  capacite_accueil      INTEGER,
  source_url            TEXT NOT NULL,
  est_simule            INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS demande (
  id                 INTEGER PRIMARY KEY,
  texte_brut         TEXT,
  niveau             TEXT,
  theme              TEXT,
  nb_eleves          INTEGER,
  nb_accompagnateurs INTEGER,
  date_sortie        TEXT,
  heure_depart_min   TEXT,
  heure_retour_max   TEXT,
  lieu_depart        TEXT,
  lieu_lat           REAL,
  lieu_lon           REAL,
  gare_depart_uic    TEXT REFERENCES gare(code_uic),
  email              TEXT,
  demande_json       TEXT,
  cree_le            TEXT
);

CREATE TABLE IF NOT EXISTS proposition (
  id               TEXT PRIMARY KEY,
  demande_id       INTEGER REFERENCES demande(id),
  site_id          TEXT NOT NULL REFERENCES site_culturel(id),
  date_sortie      TEXT NOT NULL,
  train_aller      TEXT NOT NULL,
  train_retour     TEXT NOT NULL,
  score            INTEGER,
  niveau           TEXT,
  details_json     TEXT,
  explication_ia   TEXT,
  est_alternative  INTEGER NOT NULL DEFAULT 0,
  remplace         TEXT,
  proposition_json TEXT NOT NULL,
  site_json        TEXT,
  demande_json     TEXT,
  cree_le          TEXT
);

CREATE TABLE IF NOT EXISTS dossier (
  reference      TEXT PRIMARY KEY,
  proposition_id TEXT NOT NULL UNIQUE REFERENCES proposition(id),
  statut         TEXT NOT NULL
                 CHECK (statut IN ('OPTION', 'PRE_RESERVATION', 'CONFIRMATION',
                                   'CONTRE_PROPOSITION', 'ANNULE')),
  message        TEXT,
  nb_voyageurs   INTEGER NOT NULL,
  email          TEXT NOT NULL,
  site_id        TEXT,
  demande_json   TEXT,
  cree_le        TEXT,
  maj_le         TEXT
);

CREATE TABLE IF NOT EXISTS dossier_historique (
  id        INTEGER PRIMARY KEY,
  reference TEXT NOT NULL REFERENCES dossier(reference),
  statut    TEXT NOT NULL,
  date      TEXT NOT NULL,
  message   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positionnement (
  id                INTEGER PRIMARY KEY,
  train_numero      TEXT    NOT NULL REFERENCES train(numero),
  date_sortie       TEXT    NOT NULL,
  nb_places         INTEGER NOT NULL,
  dossier_reference TEXT REFERENCES dossier(reference),
  est_simule        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_positionnement ON positionnement (train_numero, date_sortie);

CREATE TABLE IF NOT EXISTS retour_experience (
  id                INTEGER PRIMARY KEY,
  dossier_reference TEXT UNIQUE REFERENCES dossier(reference),
  site_id           TEXT NOT NULL REFERENCES site_culturel(id),
  satisfaction      INTEGER,
  adaptation_train  INTEGER,
  acces_gare_site   INTEGER,
  confiance         INTEGER,
  recommande        INTEGER,
  commentaire       TEXT,
  est_simule        INTEGER NOT NULL DEFAULT 0,
  cree_le           TEXT
);
"""

# Vote en classe (v2). Votes anonymes : aucune donnée personnelle (les votants sont des mineurs),
# seulement une empreinte de l'identifiant aléatoire du navigateur pour éviter les doubles votes.
SCHEMA_SONDAGES = """
CREATE TABLE IF NOT EXISTS sondage (
  code     TEXT PRIMARY KEY,
  titre    TEXT NOT NULL,
  statut   TEXT NOT NULL DEFAULT 'ouvert' CHECK (statut IN ('ouvert', 'ferme')),
  gagnant  TEXT,
  cree_le  TEXT NOT NULL,
  ferme_le TEXT
);

CREATE TABLE IF NOT EXISTS sondage_option (
  sondage_code        TEXT    NOT NULL REFERENCES sondage(code),
  ordre               INTEGER NOT NULL,
  site_id             TEXT    NOT NULL,
  nom                 TEXT    NOT NULL,
  commune             TEXT    NOT NULL DEFAULT '',
  interet_pedagogique TEXT    NOT NULL DEFAULT '',
  indice_confiance    INTEGER NOT NULL DEFAULT 0,
  niveau              TEXT    NOT NULL,
  PRIMARY KEY (sondage_code, site_id)
);

CREATE TABLE IF NOT EXISTS sondage_vote (
  sondage_code     TEXT NOT NULL REFERENCES sondage(code),
  votant_empreinte TEXT NOT NULL,
  site_id          TEXT NOT NULL,
  vote_le          TEXT NOT NULL,
  PRIMARY KEY (sondage_code, votant_empreinte)
);

CREATE TABLE IF NOT EXISTS sondage_manuel (
  sondage_code TEXT    NOT NULL REFERENCES sondage(code),
  site_id      TEXT    NOT NULL,
  nb           INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (sondage_code, site_id)
);

CREATE TABLE IF NOT EXISTS sondage_effectif (
  sondage_code TEXT PRIMARY KEY REFERENCES sondage(code),
  effectif     INTEGER NOT NULL
);
"""
SCHEMA += SCHEMA_SONDAGES


def maintenant_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def connecter(path=None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or config.db_path()), timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def connexion(path=None) -> Iterator[sqlite3.Connection]:
    conn = connecter(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def creer_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def meta_get(conn: sqlite3.Connection, cle: str, defaut: str | None = None) -> str | None:
    row = conn.execute("SELECT valeur FROM meta WHERE cle = ?", (cle,)).fetchone()
    return row["valeur"] if row else defaut


def meta_set(conn: sqlite3.Connection, cle: str, valeur: str) -> None:
    conn.execute(
        "INSERT INTO meta (cle, valeur) VALUES (?, ?) "
        "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur",
        (cle, valeur),
    )


def base_prete(path=None) -> bool:
    p = path or config.db_path()
    if not p.exists():
        return False
    try:
        with connexion(p) as conn:
            return meta_get(conn, "donnees") is not None and (
                conn.execute("SELECT COUNT(*) FROM desserte").fetchone()[0] > 0
            )
    except sqlite3.DatabaseError:
        return False


def initialiser() -> str:
    """Construit la base si elle n'existe pas : vrais fichiers SNCF s'ils sont là, sinon démo.

    Retourne la nature des données ("sncf" ou "demo").
    """
    from etl import build_db, seed_demo  # import local : l'ETL dépend de ce module

    path = config.db_path()
    if not base_prete(path):
        if path.exists():
            path.unlink()
        if build_db.fichiers_sncf_disponibles():
            build_db.construire(path)
        else:
            seed_demo.semer(path)
    with connexion(path) as conn:
        return meta_get(conn, "donnees", "demo") or "demo"


def nature_donnees() -> str:
    try:
        with connexion() as conn:
            return meta_get(conn, "donnees", "demo") or "demo"
    except sqlite3.DatabaseError:
        return "demo"


def version_base(conn: sqlite3.Connection) -> str:
    return meta_get(conn, "construite_le", "") or ""
