"""Protection des données personnelles dans les vues transversales (version 3.0).

Le numéro d'immatriculation de l'assuré (NIR, 13 chiffres, 15 avec la clé) n'est utile qu'au contrôle détaillé
d'un dossier, par une personne habilitée à ouvrir ce dossier. Toutes les réponses destinées à une vue globale
(liste des anomalies, revue, exports, regroupements, journal d'audit) le masquent CÔTÉ SERVEUR : le navigateur ne
reçoit jamais la valeur complète.
"""
from __future__ import annotations

import re

# 13 à 15 chiffres consécutifs, éventuellement séparés par des espaces simples (« 2520299007005 01 »)
_NIR = re.compile(r"(?<![\d])(?:\d[  ]?){12,16}\d(?![\d])")


def mask_id(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 13:
        return value
    return digits[0] + "•" * (len(digits) - 3) + digits[-2:]


def mask_text(value):
    """Masque tout numéro de 13 chiffres ou plus dans une valeur (texte, nombre, liste ou dictionnaire)."""
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return _NIR.sub(lambda m: mask_id(m.group(0)), value)
    if isinstance(value, list):
        return [mask_text(v) for v in value]
    if isinstance(value, dict):
        return {k: mask_text(v) for k, v in value.items()}
    return value


def mask_result_values(item: dict, keys=("jpg_value", "txt_value", "explanation", "hypothesis", "evidence",
                                          "message")) -> dict:
    return {k: (mask_text(v) if k in keys else v) for k, v in item.items()}
