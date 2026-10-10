# SPDX-License-Identifier: AGPL-3.0-or-later
"""Contrat de données canonique (Pydantic). Le LLM propose, ce contrat dispose."""
from __future__ import annotations
import re
from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

ValidationStatus = Literal["extrait", "verifie_auto", "a_confirmer", "valide_humain", "rejete"]

_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def numbers_in(text: str) -> set[float]:
    """Tous les nombres d'un texte ('1,25' et '1.25' valent 1.25)."""
    return {float(n.replace(",", ".")) for n in _NUM.findall(text or "")}


class Extraction(BaseModel):
    """Ce que le modèle de langage doit remplir, et RIEN d'autre (champs absents = null)."""
    model_config = ConfigDict(extra="forbid")

    crop_original: Optional[str] = None          # culture telle qu'écrite dans la source
    target_original: Optional[str] = None        # cible (ravageur / maladie) telle qu'écrite
    dose_original: Optional[str] = None          # dose telle qu'écrite : "0.5 kg/ha"
    dose_value: Optional[float] = Field(default=None, gt=0)
    dose_unit: Optional[str] = None              # unité telle qu'écrite : "kg/ha", "g/m3"...
    max_applications: Optional[int] = Field(default=None, ge=1)
    min_interval_days: Optional[int] = Field(default=None, ge=0)
    pre_harvest_interval_days: Optional[int] = Field(default=None, ge=0)
    restrictions: list[str] = Field(default_factory=list)   # extraits littéraux
    quote: str = Field(min_length=6)             # preuve : phrase copiée mot à mot

    @model_validator(mode="after")
    def dose_coherente(self):
        if self.dose_value is not None:
            if not self.dose_original or not self.dose_unit:
                raise ValueError("dose_value exige dose_original et dose_unit")
            if self.dose_value not in numbers_in(self.dose_original):
                raise ValueError(f"dose_value={self.dose_value} absente de dose_original={self.dose_original!r}")
            if len(self.dose_unit) > 30 or re.search(r"[\[\]()]", self.dose_unit):
                raise ValueError(f"dose_unit={self.dose_unit!r} n'est pas une unité (court, sans crochets ni parenthèses)")
            if self.dose_unit.replace(" ", "").casefold() not in self.dose_original.replace(" ", "").casefold():
                raise ValueError(f"dose_unit={self.dose_unit!r} absente de dose_original={self.dose_original!r}")
        elif self.dose_original or self.dose_unit:
            raise ValueError("dose_original/dose_unit renseignés sans dose_value")
        return self


class Citation(BaseModel):
    source_id: str                    # ephy | pmra | epa
    source_url: str                   # lien direct vers la source officielle
    dataset_url: Optional[str] = None
    collected_at: date
    quote: str
    passage_id: str
    passage_sha256: str
    is_fictional: bool = False


class Record(BaseModel):
    """Enregistrement canonique mondial : valeur originale ET valeur normalisée."""
    record_id: str
    product: str
    country: str                      # FR | CA | US ...
    region: str
    reg_number: str
    holder: Optional[str] = None
    authorization_status_original: Optional[str] = None
    authorization_status: Optional[Literal["autorise", "retire", "autre"]] = None
    crop_original: Optional[str] = None
    crop_eppo: Optional[str] = None
    target_original: Optional[str] = None
    target_eppo: Optional[str] = None
    dose_original: Optional[str] = None
    dose_value: Optional[float] = None
    dose_unit: Optional[str] = None
    dose_norm_value: Optional[float] = None      # dose normalisée par code (kg/ha ou L/ha), sinon null
    dose_norm_unit: Optional[Literal["kg/ha", "L/ha"]] = None
    max_applications: Optional[int] = None
    min_interval_days: Optional[int] = None
    pre_harvest_interval_days: Optional[int] = None
    restrictions: list[str] = Field(default_factory=list)
    citation: Citation
    validation_status: ValidationStatus = "extrait"
    attempts: int = 1
    model: str = ""
    critic_notes: list[str] = Field(default_factory=list)


class CriticVerdict(BaseModel):
    """Sortie du critique LLM (second avis, jamais décisionnaire seul)."""
    model_config = ConfigDict(extra="forbid")
    verdict: Literal["ok", "rejet"]
    motifs: list[str] = Field(default_factory=list)


class EppoChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eppo: Optional[str] = None        # un code parmi les candidats, ou null


class QueryPlan(BaseModel):
    """Question en langage naturel -> filtres (le LLM ne répond pas, il planifie)."""
    model_config = ConfigDict(extra="forbid")
    product: Optional[str] = None
    countries: list[str] = Field(default_factory=list)
    crop: Optional[str] = None
    target: Optional[str] = None


class SisterHypothesis(BaseModel):
    product_a: str
    country_a: str
    product_b: str
    country_b: str
    confidence: float = Field(ge=0, le=1)
    features: dict[str, bool]
    justification: str
    status: Literal["a_confirmer"] = "a_confirmer"   # une hypothèse n'est jamais « validée »


_UNITS = {   # unité (sans espaces ni points, minuscule) -> (facteur, unité normalisée)
    "kg/ha": (1, "kg/ha"), "g/ha": (1e-3, "kg/ha"), "l/ha": (1, "L/ha"), "ml/ha": (1e-3, "L/ha"),
    # unités américaines (EPA) : 1 acre = 0,404686 ha
    "lb/acre": (0.453592 / 0.404686, "kg/ha"), "lbs/acre": (0.453592 / 0.404686, "kg/ha"),
    "oz/acre": (0.0283495 / 0.404686, "kg/ha"),
    "floz/acre": (0.0295735 / 0.404686, "L/ha"), "pt/acre": (0.473176 / 0.404686, "L/ha"),
    "pint/acre": (0.473176 / 0.404686, "L/ha"), "qt/acre": (0.946353 / 0.404686, "L/ha"),
    "quart/acre": (0.946353 / 0.404686, "L/ha"), "gal/acre": (3.78541 / 0.404686, "L/ha"),
}


def normalize_dose(value: Optional[float], unit: Optional[str]):
    """Conversion déterministe vers kg/ha ou L/ha ; toute autre unité reste non normalisée (null).
    La valeur originale est toujours conservée à côté (dose_original, dose_value, dose_unit)."""
    if value is None or not unit:
        return None, None
    u = re.sub(r"[\s.]", "", unit).casefold()
    if u in _UNITS:
        f, nu = _UNITS[u]
        return round(value * f, 4), nu
    return None, None
