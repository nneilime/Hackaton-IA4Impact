"""Review difficulty per invoice, 0 (trivial) to 100 (hardest). Plain deterministic Python.

Signals (all already available, no extra OCR pass):
  - KO / A_VERIFIER counts from run_checks()
  - C0 KO: the B2 file is malformed, every other check is unevaluable -> fully manual review
  - unreadable zones ("illisible") involved in an anomaly
  - low per-zone OCR confidence ("scores") on an anomaly zone

  uv run python difficulte.py              # self-test on synthetic checks
  uv run python difficulte.py Facture1_01  # score one invoice (needs its OCR cache)
"""

POIDS_KO = 8
PLAFOND_KO = 40
POIDS_A_VERIFIER = 4
PLAFOND_A_VERIFIER = 20
BONUS_C0_KO = 20
PAR_ZONE_ILLISIBLE = 4
PLAFOND_ILLISIBLE = 12
# A KO read with shaky OCR means its "lu" value cannot be trusted: the agent must
# verify from the pixels, so the invoice is harder. Confident KO = clear-cut mismatch.
# Per KO check: round((1 - confiance) * 10) points, capped overall.
ECHELLE_CONFIANCE_KO = 10
PLAFOND_CONFIANCE_KO = 20
# Long mismatched values (code lists, ...) take longer to compare character by character.
# Per KO check (C0 excluded: its "lu" is a diagnostic message, not a compared value):
# max(len(attendu), len(lu)) // 15 points, capped overall.
PAS_LONGUEUR_KO = 15
PLAFOND_LONGUEUR_KO = 10

# Display bands: (upper bound inclusive, French label)
NIVEAUX = [
    (20, "Facile"),
    (40, "Modérée"),
    (60, "Moyenne"),
    (80, "Difficile"),
    (100, "Très difficile"),
]


def niveau(score):
    """0-100 score -> French band label."""
    for borne, label in NIVEAUX:
        if score <= borne:
            return label
    return NIVEAUX[-1][1]


def zones_anomalie(checks):
    """Union of the scan zones involved in non-OK checks."""
    return {z for c in checks if c["statut"] != "OK" for z in c.get("zones", [])}


def confiance_check(check, scan=None):
    """OCR confidence of a check's read value: its own `confiance` field when present,
    else the min per-zone score from the scan dict. None when unknown
    (no zones, unprocessed scan, or unscored zones like the signatures 11/14)."""
    if check.get("confiance") is not None:
        return float(check["confiance"])
    scores = (scan or {}).get("scores", {}) or {}
    valeurs = [float(scores[str(z)]) for z in check.get("zones", []) if str(z) in scores]
    return min(valeurs) if valeurs else None


def evaluer(checks, scan=None):
    """Score one invoice. `checks` are run_checks() dicts, `scan` the extract() scan dict or None.

    Returns {"score": int 0-100, "niveau": str, "details": {...}} for the API.
    """
    nb_ko = sum(1 for c in checks if c["statut"] == "KO")
    nb_av = sum(1 for c in checks if c["statut"] == "A_VERIFIER")
    c0_ko = any(c["code"] == "C0" and c["statut"] == "KO" for c in checks)

    pts_ko = min(nb_ko * POIDS_KO, PLAFOND_KO)
    pts_av = min(nb_av * POIDS_A_VERIFIER, PLAFOND_A_VERIFIER)
    pts_c0 = BONUS_C0_KO if c0_ko else 0

    zones = zones_anomalie(checks)
    illisibles = set((scan or {}).get("illisible", []) or [])
    nb_illisible = len([z for z in zones if z in illisibles])
    pts_illisible = min(nb_illisible * PAR_ZONE_ILLISIBLE, PLAFOND_ILLISIBLE)

    # Confidence of the wrong lines: one entry per KO check that has a score.
    confiance_ko = {}
    for c in checks:
        if c["statut"] != "KO":
            continue
        conf = confiance_check(c, scan)
        if conf is not None:
            confiance_ko[c["code"]] = conf
    pts_confiance = min(
        sum(round((1.0 - conf) * ECHELLE_CONFIANCE_KO) for conf in confiance_ko.values()),
        PLAFOND_CONFIANCE_KO)

    # Length of the KO-ing lines: the longer the mismatched values, the longer
    # the character-by-character comparison for the agent.
    longueurs_ko = {}
    for c in checks:
        if c["statut"] != "KO" or c["code"] == "C0":
            continue
        longueurs_ko[c["code"]] = max(len(c.get("attendu") or ""), len(c.get("lu") or ""))
    pts_longueur = min(sum(l // PAS_LONGUEUR_KO for l in longueurs_ko.values()),
                       PLAFOND_LONGUEUR_KO)

    score = max(0, min(100, pts_ko + pts_av + pts_c0 + pts_illisible + pts_confiance + pts_longueur))
    return {
        "score": score,
        "niveau": niveau(score),
        "details": {
            "nb_ko": nb_ko, "nb_a_verifier": nb_av, "c0_ko": c0_ko,
            "zones_illisible": nb_illisible, "confiance_ko": confiance_ko,
            "longueurs_ko": longueurs_ko,
        },
    }


def test():
    def check(code, statut, zones=None):
        return {"code": code, "statut": statut, "zones": zones or []}

    # No anomaly at all -> 0, Facile
    assert evaluer([check("C0", "OK")])["score"] == 0
    assert evaluer([check("C0", "OK")])["niveau"] == "Facile"
    # One KO -> 8 ; one A_VERIFIER -> 4
    assert evaluer([check("C0", "OK"), check("C14", "KO", [9, 11])])["score"] == 8
    assert evaluer([check("C0", "OK"), check("C6", "A_VERIFIER", [6])])["score"] == 4
    # KO contribution capped at 40
    many_ko = [check("C0", "OK")] + [check(f"C{i}", "KO", [i]) for i in range(1, 10)]
    assert evaluer(many_ko)["score"] == 40
    # C0 KO (malformed B2, everything else unevaluable): C0 itself counts as a KO (8),
    # plus the C0 bonus (20), plus capped A_VERIFIER points (20)
    c0_ko = [check("C0", "KO")] + [check(f"C{i}", "A_VERIFIER", [i]) for i in range(1, 18)]
    assert evaluer(c0_ko)["score"] == 8 + 20 + 20
    # Unreadable + low-confidence anomaly zones add up
    scan = {"illisible": [6, 9, 11], "scores": {"6": 0.4, "9": 0.5, "11": 0.9}}
    checks = [check("C0", "KO"), check("C6", "KO", [6]), check("C14", "KO", [9, 11])]
    # 3 KO (24) + C0 bonus (20) + 3 zones illisibles (12) + confiance KO : 6 (zone 6 à 0.4)
    # et 5 (zones 9/11, min 0.5) ; C0 sans zones n'apporte rien
    assert evaluer(checks, scan)["score"] == 24 + 20 + 12 + 6 + 5
    # A KO read with shaky OCR adds round((1 - confiance) * 10) points each (cap 20) ;
    # a confident KO adds nothing on top of the KO points.
    ko_sur = [check("C0", "OK"), {"code": "C6", "statut": "KO", "zones": [6], "confiance": 0.42}]
    assert evaluer(ko_sur)["score"] == 8 + 6
    assert evaluer(ko_sur)["details"]["confiance_ko"] == {"C6": 0.42}
    ko_franc = [check("C0", "OK"), {"code": "C6", "statut": "KO", "zones": [6], "confiance": 0.99}]
    assert evaluer(ko_franc)["score"] == 8
    # Length of the KO-ing line: max(len(attendu), len(lu)) // 15 points each (cap 10) ;
    # C0 excluded (its "lu" is a diagnostic message, not a compared value).
    ko_long = [check("C0", "OK"),
               {"code": "C11", "statut": "KO", "zones": [10], "confiance": 1.0,
                "attendu": "B, APC, JCPD001, YYYY405, JCLE002, CS",
                "lu": "B, APC, JCPD001, YYYY405, JCLE002, CS"}]
    assert evaluer(ko_long)["score"] == 8 + 0 + 2
    assert evaluer(ko_long)["details"]["longueurs_ko"] == {"C11": 37}
    ko_c0_long = [ {"code": "C0", "statut": "KO", "zones": [],
                    "attendu": "fichier conforme", "lu": "Fichier B2 mal formé (ligne 1 : décalage de colonnes)"}]
    assert evaluer(ko_c0_long)["score"] == 8 + 20
    assert evaluer(ko_c0_long)["details"]["longueurs_ko"] == {}
    # Fallback on the scan dict when the check carries no `confiance` field
    ko_legacy = [check("C0", "OK"), check("C6", "KO", [6])]
    assert evaluer(ko_legacy, {"scores": {"6": 0.5}})["score"] == 8 + 5
    # Unscored KO zones (signatures 11/14, C0 with no zones) add nothing
    ko_sans_score = [check("C0", "OK"), check("C14", "KO", [9, 11])]
    assert evaluer(ko_sans_score, {"scores": {"9": 1.0}})["score"] == 8
    # Worst case reaches every cap: total clamped at 100, "Très difficile"
    pire = ([{"code": "C0", "statut": "KO", "zones": []}]
            + [{"code": f"K{i}", "statut": "KO", "zones": [i], "confiance": 0.1} for i in range(1, 8)]
            + [check(f"A{i}", "A_VERIFIER", [i]) for i in range(1, 18)])
    scan_pire = {"illisible": [1, 2, 3]}
    assert evaluer(pire, scan_pire)["score"] == 100
    assert evaluer(pire, scan_pire)["niveau"] == "Très difficile"
    print("ok")


if __name__ == "__main__":
    import json
    import sys

    if sys.argv[1:]:
        from checks import run_checks
        from extract import extract

        name = sys.argv[1]
        ocr = extract(name)
        print(json.dumps(evaluer(run_checks(name), ocr["scan"] if ocr else None),
                         ensure_ascii=False))
    else:
        test()
