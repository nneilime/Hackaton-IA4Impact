"""Tests de validation de l'environnement Copilote IA et du suivi de projet (T5.1).

Vérifie :
- L'accessibilité du serveur local Ollama
- La présence des modèles requis (Qwen2.5)
- La présence et la structure du tableau de suivi des tâches
"""
from __future__ import annotations

from pathlib import Path

import pytest


def test_tableau_de_suivi_existe():
    """Vérifie que docs/TABLEAU_DE_SUIVI.md existe et liste bien les 5 lots."""
    tracking_path = Path(__file__).resolve().parent.parent / "docs" / "TABLEAU_DE_SUIVI.md"
    assert tracking_path.exists(), "Le fichier docs/TABLEAU_DE_SUIVI.md doit exister."
    content = tracking_path.read_text(encoding="utf-8")
    for lot_idx in range(1, 6):
        lot_found = f"LOT {lot_idx}" in content or f"Lot {lot_idx}" in content
        assert lot_found, f"Lot {lot_idx} manquant dans le tableau"
    assert "T5.1" in content, "T5.1 doit être présente dans le tableau"


def test_ollama_serveur_disponible():
    """Vérifie que le serveur Ollama local répond aux requêtes si ollama est installé."""
    ollama = pytest.importorskip("ollama", reason="Bibliothèque ollama non installée dans cet environnement")
    try:
        models_info = ollama.list()
    except Exception as exc:
        pytest.skip(f"Ollama daemon non joignable: {exc}")

    # Support à la fois des objets pydantic et des dicts
    if hasattr(models_info, "models"):
        model_names = [m.model for m in models_info.models]
    else:
        model_names = [m.get("name") or m.get("model") for m in models_info.get("models", [])]

    assert len(model_names) > 0, "Au moins un modèle doit être disponible dans Ollama"
    has_qwen = any("qwen2.5" in name for name in model_names)
    assert has_qwen, f"Un modèle qwen2.5 doit être présent, modèles trouvés: {model_names}"


def test_ollama_inference_minimale():
    """Vérifie qu'une inférence rapide s'exécute correctement sur le modèle disponible."""
    ollama = pytest.importorskip("ollama", reason="Bibliothèque ollama non installée dans cet environnement")
    model_to_use = "qwen2.5:1.5b"
    try:
        response = ollama.chat(
            model=model_to_use,
            messages=[{"role": "user", "content": "Ping"}],
            options={"temperature": 0.1},
        )
    except Exception as exc:
        pytest.skip(f"Ollama daemon non joignable ou modèle indisponible: {exc}")

    content = response.get("message", {}).get("content", "")
    assert len(content.strip()) > 0, "La réponse d'inférence ne doit pas être vide"

