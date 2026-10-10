"""Copilote LLM local (Ollama) : reformule le JSON d'explication et vérifie les nombres.

Tâche(s) : T5.2 — propriétaire : P5.
Spécification : docs/PLAN_EQUIPE_DEFI_ENEDIS.md §4.3 et §5.8.

Garde-fous :
- Le LLM ne calcule rien et ne décide rien.
- Vérification regex : tout nombre généré doit provenir du JSON d'explication.
- En cas d'hallucination ou d'échec du LLM, bascule automatique sur le texte modèle de secours.
- Mise en cache sur disque pour une restitution instantanée et déterministe.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

PROMPT_SYSTEME_COPILOTE = (
    "Tu es l'adjoint du responsable de crise Enedis. Tu es strictement factuel et concis "
    "(3 phrases maximum). Tu reformules l'arbitrage d'affectation d'une équipe à partir des données "
    "fournies. Tu ne dois inventer aucun chiffre ni aucune information absente du JSON. "
    "N'utilise que les chiffres exacts figurant dans les données."
)


def extraire_nombres(texte: str) -> set[float | int]:
    """Extrait tous les nombres (entiers et flottants) d'une chaîne de caractères."""
    resultats: set[float | int] = set()
    # Capture entiers et décimaux avec point ou virgule
    motifs = re.findall(r"-?\d+(?:[.,]\d+)?", texte)
    for m in motifs:
        val_str = m.replace(",", ".")
        try:
            if "." in val_str:
                f_val = float(val_str)
                resultats.add(f_val)
                if f_val.is_integer():
                    resultats.add(int(f_val))
            else:
                i_val = int(val_str)
                resultats.add(i_val)
                resultats.add(float(i_val))
        except ValueError:
            continue
    return resultats


def extraire_nombres_json(donnees: Any) -> set[float | int]:
    """Extrait récursivement tous les nombres présents dans une structure JSON ou ses libellés."""
    nombres: set[float | int] = set()

    def _parcourir(elem: Any):
        if isinstance(elem, (int, float)) and not isinstance(elem, bool):
            nombres.add(elem)
            if isinstance(elem, float) and elem.is_integer():
                nombres.add(int(elem))
            elif isinstance(elem, int):
                nombres.add(float(elem))
        elif isinstance(elem, str):
            # Extraire les nombres potentiels dans les chaînes (ex: "INC_000123" -> 123, "4h" -> 4)
            nombres.update(extraire_nombres(elem))
        elif isinstance(elem, dict):
            for k, v in elem.items():
                _parcourir(k)
                _parcourir(v)
                # Autoriser les conversions minutes <-> heures explicites si pertinentes
                if k.endswith("_min") and isinstance(v, (int, float)):
                    h_val = v / 60.0
                    nombres.add(h_val)
                    if h_val.is_integer():
                        nombres.add(int(h_val))
                elif k.endswith("_heures") and isinstance(v, (int, float)):
                    m_val = v * 60.0
                    nombres.add(m_val)
                    if m_val.is_integer():
                        nombres.add(int(m_val))
        elif isinstance(elem, (list, tuple, set)):
            for v in elem:
                _parcourir(v)

    _parcourir(donnees)
    return nombres


def verifier_conformite_nombres(texte: str, explication_json: dict) -> bool:
    """Garde-fou anti-hallucination : vérifie que tous les nombres du texte figurent dans le JSON.

    Renvoie True si tous les nombres du texte sont licites, False si une hallucination est détectée.
    """
    nombres_texte = extraire_nombres(texte)
    if not nombres_texte:
        return True

    nombres_autorises = extraire_nombres_json(explication_json)
    for n in nombres_texte:
        # Vérification exacte ou tolérance flottante minime
        est_autorise = any(
            n == aut or (isinstance(n, float) and isinstance(aut, float) and abs(n - aut) < 1e-4)
            for aut in nombres_autorises
        )
        if not est_autorise:
            return False
    return True


def generer_template_secours(explication: dict) -> str:
    """Génère un texte modèle de secours 100% factuel et conforme en cas d'absence de LLM."""
    eq_id = explication.get("id_equipe", "Équipe")
    inc_id = explication.get("id_incident", "Incident")
    score = explication.get("score", 0.0)
    facteurs = explication.get("facteurs", {})

    nb_clients = facteurs.get("nb_clients", 0)
    sensible = facteurs.get("sensible", False)
    trajet_min = facteurs.get("trajet_min", 0)
    duree_min = facteurs.get("duree_min", 0)

    alt = explication.get("alternative", {})
    alt_inc = alt.get("id_incident", "N/A")
    delta_ch = alt.get("delta_clients_heures", 0)

    part_sensible = " (poste sensible prioritaire)" if sensible else ""
    phrase1 = (
        f"L'équipe {eq_id} est affectée à l'incident {inc_id} avec un score d'arbitrage de {score:.1f}."
    )
    phrase2 = (
        f"L'intervention rétablit {nb_clients} clients{part_sensible} après {trajet_min} min de trajet "
        f"et une durée de dépannage estimée à {duree_min} min."
    )
    phrase3 = (
        f"Choisir l'alternative sur {alt_inc} aurait occasionné un surcoût évalué "
        f"à {delta_ch} clients·heures."
    )
    return f"{phrase1} {phrase2} {phrase3}"


def _calculer_cle_cache(explication: dict) -> str:
    """Calcule une empreinte SHA256 stable pour l'explication."""
    payload = json.dumps(explication, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def reformuler_explication(
    explication: dict,
    model: str = "qwen2.5:3b",
    fallback_model: str = "qwen2.5:1.5b",
    timeout_s: float = 30.0,
    cache_dir: Path | str = ".cache/copilote",
    forcer_template: bool = False,
) -> str:
    """Reformule l'arbitrage d'affectation via Ollama local ou renvoie le modèle de secours.

    Paramètres :
    - explication : dictionnaire conforme au contrat §4.3
    - model : modèle Ollama principal (défaut Qwen2.5-3B)
    - fallback_model : modèle de repli plus rapide (Qwen2.5-1.5B)
    - timeout_s : délai maximal accordé au LLM
    - cache_dir : répertoire de cache sur disque
    - forcer_template : si True, utilise directement le template de secours sans appeler Ollama
    """
    c_dir = Path(cache_dir)
    c_dir.mkdir(parents=True, exist_ok=True)
    cle = _calculer_cle_cache(explication)
    fichier_cache = c_dir / f"{cle}.json"

    # 1. Vérification du cache sur disque
    if fichier_cache.exists():
        try:
            with open(fichier_cache, encoding="utf-8") as f:
                data = json.load(f)
                texte_cache = data.get("texte")
                if texte_cache and verifier_conformite_nombres(texte_cache, explication):
                    return texte_cache
        except Exception:
            pass

    # 2. Mode template forcé ou secours immédiat
    if forcer_template:
        texte_secours = generer_template_secours(explication)
        try:
            with open(fichier_cache, "w", encoding="utf-8") as f:
                json.dump({"texte": texte_secours, "source": "template"}, f, ensure_ascii=False)
        except Exception:
            pass
        return texte_secours

    # 3. Appel du LLM local (Ollama)
    texte_genere: str | None = None
    try:
        import ollama

        prompt_user = (
            f"Reformule de façon claire et factuelle en 3 phrases maximum l'affectation suivante :\n"
            f"{json.dumps(explication, ensure_ascii=False, indent=2)}\n"
            f"Règles strictes : N'invente aucun chiffre. Utilise uniquement les données ci-dessus."
        )

        modeles_a_tenter = [model, fallback_model]
        for m in modeles_a_tenter:
            try:
                response = ollama.chat(
                    model=m,
                    messages=[
                        {"role": "system", "content": PROMPT_SYSTEME_COPILOTE},
                        {"role": "user", "content": prompt_user},
                    ],
                    options={"temperature": 0.2},
                )
                candidat = response.get("message", {}).get("content", "").strip()
                if candidat and verifier_conformite_nombres(candidat, explication):
                    texte_genere = candidat
                    break
            except Exception:
                continue
    except ImportError:
        pass

    # 4. Garde-fou : si aucune réponse valide du LLM (ou hallucination détectée), bascule template
    if not texte_genere:
        texte_final = generer_template_secours(explication)
        source = "fallback_template"
    else:
        texte_final = texte_genere
        source = "llm"

    # 5. Enregistrement en cache
    try:
        with open(fichier_cache, "w", encoding="utf-8") as f:
            json.dump({"texte": texte_final, "source": source}, f, ensure_ascii=False)
    except Exception:
        pass

    return texte_final
