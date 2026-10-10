# SPDX-License-Identifier: AGPL-3.0-or-later
"""Configuration : tout se règle par variables d'environnement, aucune clé personnelle requise."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("VEILLE_DATA_DIR", ROOT / "data"))
RAW = DATA / "raw"            # téléchargements bruts (non versionnés)
PROCESSED = DATA / "processed"
CACHE = DATA / "cache"
WEB = ROOT / "web"
PROMPTS = ROOT / "prompts"
CONFIG = ROOT / "config"

# Fournisseur de modèle interchangeable par configuration (exigence LPC)
MODEL = os.environ.get("VEILLE_MODEL", "qwen2.5:latest")
EMBED_MODEL = os.environ.get("VEILLE_EMBED_MODEL", "nomic-embed-text")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
# Nom de la carte qui exécute le modèle (information pour le dimensionnement : l'API Ollama ne le donne pas).
SERVICE_GPU = os.environ.get("VEILLE_GPU", "")
# Service de synthèse vocale locale (Orpheus de l'essaim, voir orpheus.me.sh) ; vide = adresse par défaut.
TTS_URL = os.environ.get("VEILLE_TTS_URL", "")
# Jeton d'administration : s'il est défini, toute action qui modifie des données exige l'en-tête X-Admin-Token.
ADMIN_TOKEN = os.environ.get("VEILLE_ADMIN_TOKEN", "")

# Qdrant : serveur local si joignable (QDRANT_URL, sinon http://localhost:6333), sinon mode embarqué
# (aucun serveur, aucune clé : c'est le cas d'un lancement à partir du seul README).
QDRANT_URL = os.environ.get("QDRANT_URL") or "http://localhost:6333"
QDRANT_PATH = Path(os.environ.get("VEILLE_QDRANT_PATH", DATA / "qdrant"))
QDRANT_FORCE_EMBEDDED = os.environ.get("VEILLE_QDRANT_EMBEDDED", "0") == "1"


def _qdrant_key() -> str | None:
    """Clé lue dans l'environnement, sinon dans le .env local de la machine (jamais copiée dans le dépôt)."""
    if os.environ.get("QDRANT_API_KEY"):
        return os.environ["QDRANT_API_KEY"]
    env = Path.home() / ".zen/ai-company/.env"
    try:
        for line in env.read_text().splitlines():
            if line.startswith("QDRANT_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'")
    except OSError:
        pass
    return None


QDRANT_API_KEY = _qdrant_key()

# Si présent, on délègue l'appel LLM à question.py (Astroport.ONE/IA) ; sinon client Ollama intégré.
QUESTION_PY_DIR = os.environ.get("VEILLE_QUESTION_PY", str(Path.home() / ".zen/Astroport.ONE/IA"))

MAX_ATTEMPTS = int(os.environ.get("VEILLE_MAX_ATTEMPTS", "3"))
LLM_CRITIC = os.environ.get("VEILLE_LLM_CRITIC", "1") == "1"

for d in (RAW, PROCESSED, CACHE):
    d.mkdir(parents=True, exist_ok=True)
