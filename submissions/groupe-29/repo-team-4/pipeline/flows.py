"""Registered flows. Add a new one by subclassing Flow, listing its steps and decorating it with @register_flow."""

from __future__ import annotations

from .core import Flow, register_flow
from .steps import (CheckB2Layout, CheckBordereauSums, CheckFacture, CheckOcrComplete, CheckSignatureBoxes,
                    CleanupOcrBlocks, CompareDocuments, ExtractBordereauFields, ExtractBordereauTables,
                    FilterB2Records, FilterOcrBlocks, IdentifyClinic, NormalizeB2Lines, ParseB2)

DEFAULT_FLOW = "facture_bordereau"


@register_flow
class FactureBordereauFlow(Flow):
    name = "facture_bordereau"
    description = "B2 invoice file + LightOnOCR output of its bordereau -> one normalised, compared invoice pair."
    steps = [
        NormalizeB2Lines(),
        FilterB2Records(),
        ParseB2(),
        CheckB2Layout(),
        CheckFacture(),
        CleanupOcrBlocks(),
        FilterOcrBlocks(),
        ExtractBordereauFields(),
        ExtractBordereauTables(),
        CheckSignatureBoxes(),
        CheckOcrComplete(),
        CheckBordereauSums(),
        CompareDocuments(),
        IdentifyClinic(),
    ]
