"""Accès PostgreSQL de l'API : LECTURE SEULE.

- La connexion vient uniquement de DATABASE_URL (fichier .env, jamais dans le code).
- Trois protections contre toute écriture :
  1. la session PostgreSQL est ouverte en `default_transaction_read_only=on` ;
  2. `query()` refuse toute requête qui ne commence pas par SELECT ou WITH ;
  3. aucun INSERT / UPDATE / DELETE n'existe dans ce dossier.
"""
import os
import re
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# .env est à la racine du dépôt (en conteneur, les variables viennent de docker compose)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_READ_ONLY = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


@lru_cache(maxsize=1)
def get_engine():
    """Crée (une seule fois) le moteur SQLAlchemy."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL absent : copiez .env.example en .env et renseignez-le.")
    return create_engine(
        url,
        pool_size=8,
        max_overflow=8,
        pool_recycle=240,   # pas de "ping" avant chaque requête (coûteux sur un serveur distant) : voir query()
        # Session en lecture seule + limite de 20 s par requête
        connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=20000"},
    )


def _run(sql, params):
    with get_engine().connect() as conn:
        result = conn.execute(text(sql), params or {})
        return [{k: (float(v) if isinstance(v, Decimal) else v) for k, v in row._mapping.items()} for row in result]


def query(sql, params=None):
    """Exécute un SELECT et renvoie une liste de dictionnaires (Decimal -> float)."""
    if not _READ_ONLY.match(sql):
        raise ValueError("Seules les requêtes SELECT / WITH sont autorisées dans l'API.")
    try:
        return _run(sql, params)
    except OperationalError:
        # Connexion coupée par le serveur ou le réseau : on vide le pool et on réessaie une fois
        get_engine().dispose()
        return _run(sql, params)


def query_many(requests):
    """Exécute plusieurs SELECT indépendants EN PARALLÈLE (le serveur est loin : chaque aller-retour compte).

    `requests` = liste de (sql, params). Renvoie les résultats dans le même ordre.
    """
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(requests)))) as pool:
        futures = [pool.submit(query, sql, params) for sql, params in requests]
        return [f.result() for f in futures]
