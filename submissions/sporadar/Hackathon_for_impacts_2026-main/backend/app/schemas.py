"""Enveloppes de réponse pour les schémas "inline" du contrat.

Les modèles du contrat sont dans models.py (générés par datamodel-code-generator, NE PAS éditer).
Le contrat décrit certaines réponses directement dans les routes (sans nom) ; le générateur ne
leur donne donc pas de classe. Ce fichier les reprend à l'identique, en réutilisant les classes
générées.
"""
from typing import Literal

from pydantic import BaseModel

from .models import (Answer, AnswerGenerator, ComparisonCell, ComparisonResponse, ComparisonRow, CountryCoverage, Evidence, Intent,
                     MatchedVia, Product, Registration, SourceInfo)


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ProductOut(Product):
    """Product du contrat + `matchedVia` (AJOUT optionnel demandé pour la recherche : par quel nom,
    alias ou substance active le produit a été trouvé). Propose d'ajouter ce champ au contrat."""
    matchedVia: MatchedVia | None = None


class CropDose(BaseModel):
    unitOriginal: str | None = None   # unité telle que publiée par la source, jamais convertie
    min: float
    max: float


class CropCellSummary(BaseModel):
    useCount: int
    targetsOriginal: list[str]
    doses: list[CropDose]


class ComparisonCellOut(ComparisonCell):
    """ComparisonCell du contrat + `summary` (AJOUT optionnel, seulement avec granularity=crop)."""
    summary: CropCellSummary | None = None


class ComparisonRowOut(ComparisonRow):
    """ComparisonRow du contrat + `cropGroup` / `targetGroup` (AJOUT optionnel : catégorie large suggérée par l'IA,
    ex. "Powdery mildews", "Cereals", à vérifier) + `alignedBy` (clé d'alignement). Propose d'ajouter ces champs au contrat."""
    cropGroup: str | None = None
    targetGroup: str | None = None
    alignedBy: Literal["eppo", "normalized_name", "original"] | None = None   # clé d'alignement de la ligne (hors contrat)
    cells: list[ComparisonCellOut]


class ComparisonResponseOut(ComparisonResponse):
    """ComparisonResponse du contrat, avec des lignes enrichies de cropGroup / targetGroup."""
    rows: list[ComparisonRowOut] | None = None
    granularity: Literal["use", "crop"] | None = None   # niveau de comparaison (hors contrat)


class ProductsResponse(BaseModel):
    items: list[ProductOut]


class RegistrationsResponse(BaseModel):
    items: list[Registration]
    coverage: list[CountryCoverage] | None = None
    warnings: list[str] | None = None
    disclaimer: str


class SourcesResponse(BaseModel):
    items: list[SourceInfo]


class AnswerGeneratorOut(AnswerGenerator):
    """AnswerGenerator du contrat + `mode` (AJOUT optionnel : « llm » si l'IA a servi, « keyword » en mode sans clé).
    Propose d'ajouter ce champ au contrat."""
    mode: Literal["llm", "keyword"] | None = None


# ---------------------------------------------------------------------------
# /opportunities : HORS CONTRAT (à reporter par Damien, voir docs/openapi-changes.md)
# ---------------------------------------------------------------------------
class OpportunityProduct(BaseModel):
    """Produit LPC, sœur ou de même substance autorisé sur le couple. Sœurs et même substance = hypothèses."""
    productId: str
    commercialName: str | None = None
    relation: Literal["lpc_product", "sister_candidate", "same_active_substance"]
    reviewStatus: Literal["validated", "to_verify", "confirmed", "rejected"] | str
    productCategory: Literal["biological", "chemical", "unknown"]
    categoryMethod: Literal["rule_based"] = "rule_based"
    evidenceIds: list[str]


class WithdrawnSameSubstance(BaseModel):
    """Produits RETIRÉS de même substance, SANS lien culture × cible. Jamais un usage retiré."""
    countryCode: str
    withdrawnProducts: int
    substancesCompared: int
    note: str
    evidenceIds: list[str]


class Opportunity(BaseModel):
    countryCode: str
    cropNormalized: str
    targetNormalized: str
    chemicalUses: int
    biologicalUses: int
    unknownCategoryUses: int
    chemicalProducts: int
    biologicalProducts: int
    unknownCategoryProducts: int
    chemicalToBiologicalRatio: float | None = None   # produits chimiques / produits biologiques ; null quand aucun produit biologique (division par zéro)
    biocontrolSpaceScore: float
    usesWithUnknownRegistrationStatus: int
    lpcProducts: list[OpportunityProduct]
    withdrawnSameSubstance: WithdrawnSameSubstance | None = None
    # Usages retirés RÉELS (Canada seulement ; null ailleurs). Usages/produits chimiques d'homologations « withdrawn ».
    withdrawnChemicalUses: int | None = None
    withdrawnChemicalProducts: int | None = None
    lastWithdrawalDate: str | None = None   # plus grande date de fin officielle (expiration_date), ISO 8601
    withdrawnEvidenceIds: list[str] = []
    evidenceIds: list[str]
    chemicalEvidenceIds: list[str]
    biologicalEvidenceIds: list[str]
    productCategoryMethod: Literal["rule_based"] = "rule_based"
    disclaimer: str


class OpportunitiesResponse(BaseModel):
    items: list[Opportunity]
    evidence: list[Evidence]
    warnings: list[str]
    categoryMethod: Literal["rule_based"] = "rule_based"
    scoreFormula: str
    minChemicalUses: int
    disclaimer: str


class SuggestedQuestionOut(BaseModel):
    label: str
    question: str
    intent: Intent | Literal["market_opportunity"] | None = None


class AnswerOut(Answer):
    """Answer du contrat, avec le `generator` enrichi du champ `mode`, l'intention `market_opportunity` (hors contrat)
    et les `opportunities` (couples culture × cible, uniquement pour cette intention)."""
    intent: Intent | Literal["market_opportunity"] | None = None
    generator: AnswerGeneratorOut | None = None
    opportunities: list[Opportunity] | None = None
    suggestedQuestions: list[SuggestedQuestionOut] | None = None
