# SPDX-License-Identifier: AGPL-3.0-or-later
"""Source __NAME__ (__COUNTRY__, __REGION__) — modèle généré par `./veille new-source`.

Trois choses à remplir : DATASET_URL, collect() si le téléchargement n'est pas un simple fichier, et passages().
Règles qui protègent la fiabilité :
  - le texte d'un passage recopie les valeurs de la source TELLES QUELLES (le contrôle de preuve les cherchera mot à mot) ;
  - passage_id est stable d'une collecte à l'autre (même ligne source = même identifiant) ;
  - si la source a des colonnes structurées (dose, nombre d'applications…), les mettre dans `gold` : elles servent
    d'étalon à `./veille eval` ; sinon laisser gold vide (contrôle par échantillon).
"""
from __future__ import annotations

import hashlib
from datetime import date

from .. import config, polite_http
from . import Passage

INFO = {"id": "__ID__", "name": "__NAME__", "country_code": "__COUNTRY_CODE__", "country": "__COUNTRY__",
        "region": "__REGION__", "format": "__FORMAT__", "lang": "__LANG__"}

DATASET_URL = "https://exemple.invalide/jeu-de-donnees.csv"     # TODO : jeu de données ouvert, pris EN BLOC
RAW_FILE = config.RAW / INFO["id"] / "dataset.csv"


def collect(scope: dict | None = None) -> dict:
    """Télécharge seulement si la source a changé (requêtes conditionnelles, pause, journal : polite_http)."""
    result = polite_http.download(DATASET_URL, RAW_FILE)
    return {"source": INFO["id"], "url": DATASET_URL, "changed": result["changed"]}


def wanted_names(scope: dict) -> set[str]:
    """Noms de produits à garder : config/scope.json, clé « __ID__ » de chaque produit."""
    return {name.casefold() for product in scope["products"] for name in product.get(INFO["id"], [])}


def passages(scope: dict) -> list[Passage]:
    """Un passage par usage autorisé. À compléter : lire RAW_FILE, filtrer sur wanted_names(scope)."""
    wanted = wanted_names(scope)
    found: list[Passage] = []
    # TODO : pour chaque ligne source retenue, ajouter :
    #   text = " | ".join(f"{libellé}: {valeur}" ...)           # valeurs copiées telles quelles
    #   found.append(Passage(
    #       passage_id=f"{INFO['id']}:{numero}:{hashlib.sha1(text.encode()).hexdigest()[:8]}",
    #       source_id=INFO["id"], country=INFO["country_code"], region=INFO["region"], product=nom, reg_number=numero,
    #       holder=titulaire, status_original=statut_source, status="autorise",   # autorise | retire | autre
    #       text=text, source_url="https://…/page-du-produit", dataset_url=DATASET_URL,
    #       collected_at=date.today().isoformat(), ai=substances_actives, gold={}))
    return found
