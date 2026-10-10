"""Indicateurs financiers fiables (version 2.0).

Principes :
- un écart financier est rattaché à un dossier, à une règle, à ses lignes (occurrences) lorsque c'est possible,
  à sa preuve (résultat de la règle) et à la DERNIÈRE décision humaine applicable à cette règle ;
- un montant n'est « confirmé » que si la règle concernée est actuellement en anomalie ET que sa dernière
  décision non annulée est une confirmation par un agent. Confirmer une anomalie d'un dossier ne confirme
  jamais les autres anomalies du même dossier ; un faux positif, une revue demandée ou une décision annulée
  n'est pas compté ;
- pas de double comptage : plusieurs règles peuvent décrire la même différence économique (ex. R12 sur le total
  des prestations et R13 sur la ligne manquante). Par famille économique (prestations / honoraires) et par
  dossier, on retient le MAXIMUM entre l'écart sur le total et la somme des lignes en écart, jamais leur somme ;
- R20 (cohérence arithmétique interne au bordereau) n'est pas un montant facturé : exclu des montants ;
- montant facturé, montant en anomalie, montant confirmé, indu établi et montant récupéré ne sont jamais
  assimilés. Sans données de notification ni de recouvrement, les deux derniers restent « non calculables ».
"""
from __future__ import annotations

FAMILIES = {
    "prestations": {"total": "R12", "lines": ("R08", "R11", "R13")},
    "honoraires": {"total": "R17", "lines": ("R14", "R15", "R19")},
}
DECIDING = ("confirmation", "faux_positif", "revue_complementaire")
DECISION_LABEL = {"confirmation": "écart confirmé", "faux_positif": "faux positif", "revue_complementaire": "revue demandée"}


def effective_decisions(decisions: list) -> dict:
    """Dernière décision non annulée par règle (confirmation, faux positif ou revue complémentaire).
    Une décision d'annulation porte dans `value` l'identifiant de la décision annulée."""
    cancelled = {str(d.get("value")) for d in decisions if d.get("kind") == "annulation" and d.get("value")}
    eff = {}
    for d in sorted(decisions, key=lambda x: x.get("id") or 0):
        if d.get("kind") in DECIDING and d.get("rule_id") and str(d.get("id")) not in cancelled:
            eff[d["rule_id"]] = d
    return eff


def _gap(r) -> int:
    g = (r or {}).get("gap") or {}
    v = g.get("amount_cents")
    return abs(int(v)) if isinstance(v, (int, float)) else 0


def deduplicated_amount(results_by_rule: dict, rule_ids: set) -> tuple[int, list]:
    """Montant sans double comptage pour un ensemble de règles en anomalie. Retourne (centimes, détail)."""
    total, detail = 0, []
    for fam, spec in FAMILIES.items():
        t = _gap(results_by_rule.get(spec["total"])) if spec["total"] in rule_ids else 0
        lines = {rid: _gap(results_by_rule.get(rid)) for rid in spec["lines"] if rid in rule_ids}
        ls = sum(lines.values())
        kept = max(t, ls)
        if kept:
            detail.append({"famille": fam, "ecart_total_cents": t if spec["total"] in rule_ids else None,
                           "lignes_cents": ls if lines else None, "retenu_cents": kept,
                           "regles": [r for r in [spec["total"], *spec["lines"]] if r in rule_ids],
                           "methode": "maximum (total, somme des lignes) : pas de double comptage"})
        total += kept
    return total, detail


def case_finance(results: list, decisions: list, billed_cents) -> dict:
    by_rule = {r["rule_id"]: r for r in results}
    anomalies = {r["rule_id"] for r in results if r["status"] == "ANOMALIE"}
    eff = effective_decisions(decisions)
    confirmed = {rid for rid in anomalies if eff.get(rid, {}).get("kind") == "confirmation"}
    stale = [rid for rid, d in eff.items() if d["kind"] == "confirmation" and rid not in anomalies]
    ano_amount, ano_detail = deduplicated_amount(by_rule, anomalies)
    conf_amount, conf_detail = deduplicated_amount(by_rule, confirmed)
    return {
        "billed_cents": billed_cents,
        "anomaly_cents": ano_amount, "anomaly_detail": ano_detail,
        "totals_gap_cents": sum(_gap(by_rule.get(r)) for r in ("R12", "R17") if r in anomalies),
        "lines_gap_cents": sum(_gap(by_rule.get(r)) for f in FAMILIES.values() for r in f["lines"] if r in anomalies),
        "confirmed_cents": conf_amount, "confirmed_detail": conf_detail,
        "confirmed_rules": sorted(confirmed),
        "false_positive_rules": sorted(rid for rid, d in eff.items() if d["kind"] == "faux_positif"),
        "review_rules": sorted(rid for rid, d in eff.items() if d["kind"] == "revue_complementaire"),
        "decisions_a_revoir": stale,   # confirmation d'une règle qui n'est plus en anomalie après réanalyse
        "decisions_effectives": {rid: {"kind": d["kind"], "label": DECISION_LABEL[d["kind"]], "id": d.get("id"),
                                       "by": d.get("display_name") or d.get("username"), "at": d.get("created_at")}
                                 for rid, d in eff.items()},
    }


def portfolio(cases: list) -> dict:
    """Agrégat sur un ensemble de dossiers : liste de (case_row, case_finance)."""
    billed = sum((f["billed_cents"] or 0) for _, f in cases)
    with_alert = sum((f["billed_cents"] or 0) for _, f in cases if f["anomaly_cents"] or _has_ano(_))
    return {
        "facture_total_cents": billed,
        "montant_en_anomalie_cents": sum(f["anomaly_cents"] for _, f in cases),
        "ecart_net_mesurable_cents": sum(f["totals_gap_cents"] for _, f in cases),
        "montants_lignes_en_ecart_cents": sum(f["lines_gap_cents"] for _, f in cases),
        "facture_dossiers_alerte_cents": with_alert,
        "ecart_confirme_cents": sum(f["confirmed_cents"] for _, f in cases),
        "regles_confirmees": sum(len(f["confirmed_rules"]) for _, f in cases),
        "faux_positifs": sum(len(f["false_positive_rules"]) for _, f in cases),
        "decisions_a_revoir": sum(len(f["decisions_a_revoir"]) for _, f in cases),
        "indu_etabli_cents": None,
        "recupere_cents": None,
    }


def _has_ano(case_row) -> bool:
    return bool((case_row or {}).get("n_anomalies"))
