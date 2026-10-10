"""Tests unitaires pour le copilote LLM et le garde-fou anti-hallucination (T5.2).

Contrat : docs/PLAN_EQUIPE_DEFI_ENEDIS.md §4.3 et §5.8.
Critère de fin : 10 JSON factices reformulés, 0 nombre inventé laissé passer.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from crise.copilote.llm import (
    PROMPT_SYSTEME_COPILOTE,
    extraire_nombres,
    extraire_nombres_json,
    reformuler_explication,
    verifier_conformite_nombres,
)

EXEMPLE_JSON_4_3 = {
    "id_equipe": "SITE_08_E1",
    "id_incident": "INC_000123",
    "t": 95,
    "score": 41.7,
    "facteurs": {
        "nb_clients": 142,
        "sensible": True,
        "attente_min": 35,
        "trajet_min": 22,
        "duree_min": 240,
        "poids_sensible": 6.0,
        "poids_attente": 1.06,
    },
    "contributions_pct": {
        "clients": 38,
        "sensible": 41,
        "attente": 3,
        "trajet": -6,
        "duree": -12,
    },
    "alternative": {
        "id_incident": "INC_000140",
        "score": 30.2,
        "delta_clients_heures": 312,
    },
    "meilleure_autre_equipe": {"id_equipe": "SITE_10_E2", "retard_min": 48},
    "confiance": 0.72,
    "limites": [
        "trajet estimé à vol d'oiseau × 1,3",
        "durée nominale 4h, réelle incertaine",
    ],
}


def test_extraire_nombres():
    """Vérifie l'extraction précise des entiers, décimaux et pourcentages dans un texte."""
    texte = "L'équipe SITE_08_E1 intervient pour 142 clients (trajet 22 min, score 41.7, impact 38%)."
    nombres = extraire_nombres(texte)
    assert 142 in nombres
    assert 22 in nombres
    assert 41.7 in nombres
    assert 38 in nombres


def test_extraire_nombres_json():
    """Vérifie la collecte récursive de tous les nombres d'un JSON §4.3."""
    nombres = extraire_nombres_json(EXEMPLE_JSON_4_3)
    assert 142 in nombres
    assert 95 in nombres
    assert 41.7 in nombres
    assert 312 in nombres
    assert 0.72 in nombres
    # Vérifie aussi les nombres contenus dans les libellés (ex: 8, 1, 123, 4h...)
    assert 8 in nombres
    assert 123 in nombres


def test_verifier_conformite_nombres_succes():
    """Un texte contenant uniquement des nombres issus du JSON est validé."""
    texte_valide = (
        "L'équipe SITE_08_E1 prend en charge l'incident INC_000123 pour 142 clients. "
        "Le trajet est évalué à 22 minutes avec un score de 41.7. "
        "L'alternative aurait engendré un surcoût de 312 clients-heures."
    )
    assert verifier_conformite_nombres(texte_valide, EXEMPLE_JSON_4_3) is True


def test_verifier_conformite_nombres_rejet_hallucination():
    """Un texte qui invente un chiffre non présent dans le JSON doit être rejeté."""
    # 999 clients n'est nulle part dans le JSON
    texte_hallucine = (
        "L'équipe SITE_08_E1 prend en charge l'incident pour 999 clients. "
        "Le délai est de 22 minutes."
    )
    assert verifier_conformite_nombres(texte_hallucine, EXEMPLE_JSON_4_3) is False


def test_prompt_systeme_exigences():
    """Le prompt système doit définir le rôle d'adjoint, la factualité et l'interdiction d'inventer."""
    assert "adjoint" in PROMPT_SYSTEME_COPILOTE.lower()
    assert "3 phrases" in PROMPT_SYSTEME_COPILOTE.lower()
    assert "chiffre" in PROMPT_SYSTEME_COPILOTE.lower() or "nombre" in PROMPT_SYSTEME_COPILOTE.lower()


def test_mise_en_cache_disque():
    """Vérifie que la mise en cache sur disque évite les recalculs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Premier appel (avec fallback ou mock)
        t1 = reformuler_explication(EXEMPLE_JSON_4_3, cache_dir=tmpdir, forcer_template=True)
        assert len(t1) > 0

        # Vérifie qu'un fichier de cache a été écrit
        cache_files = list(Path(tmpdir).glob("*.json"))
        assert len(cache_files) == 1

        # Deuxième appel lit directement le cache
        t2 = reformuler_explication(EXEMPLE_JSON_4_3, cache_dir=tmpdir)
        assert t1 == t2


def test_10_json_factices_reformules():
    """Critère d'acceptation T5.2 : 10 JSON factices reformulés, 0 nombre inventé laissé passer."""
    with tempfile.TemporaryDirectory() as tmpdir:
        for idx in range(10):
            json_factice = json.loads(json.dumps(EXEMPLE_JSON_4_3))
            # Variations de données
            json_factice["id_incident"] = f"INC_000{200 + idx}"
            json_factice["id_equipe"] = f"SITE_0{1 + (idx % 8)}_E1"
            json_factice["facteurs"]["nb_clients"] = 50 + idx * 10
            json_factice["facteurs"]["trajet_min"] = 15 + idx * 3
            json_factice["facteurs"]["duree_min"] = 120 if idx % 2 == 0 else 240
            json_factice["score"] = round(30.0 + idx * 1.5, 1)
            json_factice["alternative"]["delta_clients_heures"] = 100 + idx * 25

            texte = reformuler_explication(
                json_factice,
                cache_dir=tmpdir,
                forcer_template=True,
            )

            assert len(texte.strip()) > 0
            # Garantie absolue : aucun nombre dans le texte ne doit violer la conformité
            assert verifier_conformite_nombres(texte, json_factice) is True, (
                f"Nombre inventé détecté dans le texte pour l'échantillon {idx}: {texte}"
            )


def test_reformuler_avec_ollama_live():
    """Vérifie la reformulation end-to-end avec le LLM Ollama local si disponible."""
    ollama = pytest.importorskip("ollama", reason="Bibliothèque ollama non installée")
    try:
        ollama.list()
    except Exception as exc:
        pytest.skip(f"Démon Ollama non joignable: {exc}")

    with tempfile.TemporaryDirectory() as tmpdir:
        texte = reformuler_explication(
            EXEMPLE_JSON_4_3,
            model="qwen2.5:1.5b",
            fallback_model="qwen2.5:1.5b",
            cache_dir=tmpdir,
            forcer_template=False,
        )
        assert len(texte.strip()) > 0
        assert verifier_conformite_nombres(texte, EXEMPLE_JSON_4_3) is True

