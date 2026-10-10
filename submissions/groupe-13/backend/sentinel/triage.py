"""Regroupement explicable des alertes (version 2.0).

Objectif : aider l'agent à traiter d'abord la cause probable lorsque plusieurs alertes pourraient provenir
d'une même incohérence. Les regroupements :
- ne suppriment ni ne fusionnent jamais les résultats des règles R01 à R22, qui restent indépendants ;
- sont formulés au conditionnel (« pourraient provenir de… ») et citent les éléments qui les fondent ;
- n'utilisent aucun score de fraude.
"""
from __future__ import annotations

from collections import defaultdict

from .normalize import amount_str
from .zones import zones_of_rule


def _by(results):
    return {r["rule_id"]: r for r in results}


def _ano(r):
    return r and r["status"] == "ANOMALIE"


def triage_case(payload: dict) -> list:
    results = payload.get("results") or []
    R = _by(results)
    groups = []

    def add(gid, title, hypothesis, rules, evidence, first, kind):
        rules = [r for r in rules if r in R]
        if len(rules) < 1:
            return
        zs = sorted({z for r in rules for z in zones_of_rule(r)}, key=lambda z: int(z[1:]))
        groups.append({"id": gid, "type": kind, "title": title, "hypothesis": hypothesis, "rules": rules, "zones": zs,
                       "evidence": evidence, "first_check": first,
                       "avertissement": "Hypothèse d'aide au tri : chaque règle reste vérifiée et décidée individuellement."})

    txt = payload.get("txt") or {}
    # 1. décalage de positions du fichier : la plupart des écarts peuvent en découler
    if txt.get("alignment_shift"):
        an = [r["rule_id"] for r in results if r["status"] in ("ANOMALIE", "NON_VERIFIABLE")]
        if an:
            add("decalage", "Fichier TXT décalé", f"Ces {len(an)} alertes pourraient découler du décalage de "
                f"{txt['alignment_shift']} caractère(s) détecté dans le fichier (observation DECALAGE_POSITIONS).",
                an, ["Observation DECALAGE_POSITIONS du parseur"], "Vérifiez d'abord la structure du fichier (onglet Observations).",
                "structure")
    ra = txt.get("realignment")
    if ra:
        rel = [r["rule_id"] for r in results if (r.get("details") or {}).get("lecture_realignee")]
        add("realignement", "Fichier B2 mal formé (lecture réalignée)",
            f"Un caractère blanc a été inséré en position {ra['position']} sur {ra['lignes_realignees']} ligne(s). "
            f"Les {len(rel)} contrôle(s) listés reposent sur la lecture réalignée, démontrée par "
            f"{len(ra['preuves'])} vérifications internes au fichier : à confirmer, et le défaut du fichier est à "
            "signaler à l'établissement.", rel or ["R02"], [x["libelle"] for x in ra["preuves"]],
            "Confirmez la lecture réalignée (onglet Observations) avant de décider sur les autres écarts.", "structure")
    # 2. identification / rapprochement
    ids = [k for k in ("R02", "R03", "R04", "R05") if _ano(R.get(k))]
    pairing = (payload.get("pairing") or {}).get("status")
    if len(ids) >= 2 or (ids and pairing not in ("confirmé", None)):
        add("identification", "Identifiants du dossier", "Ces alertes pourraient indiquer que le bordereau et le fichier "
            "ne concernent pas le même dossier (ou qu'un numéro a été mal reporté).", ids,
            [f"{k} : bordereau {R[k].get('jpg_value')} / fichier {R[k].get('txt_value')}" for k in ids] +
            ([f"Rapprochement des documents : {pairing}"] if pairing and pairing != "confirmé" else []),
            "Vérifiez d'abord l'appariement des deux documents (n° de facture et d'assuré).", "identification")
    # 3. numéro GHS
    gh = [k for k in ("R07", "R09", "R10", "R16") if _ano(R.get(k))]
    if len(gh) >= 2:
        add("ghs", "Numéro GHS", f"Ces {len(gh)} alertes pourraient provenir d'une même incohérence de numéro GHS.", gh,
            [f"{k} : {R[k].get('explanation')}" for k in gh], "Vérifiez d'abord le GHS de référence (ligne GHS de la zone 6).",
            "ghs")
    # 4. substitution de code (même famille : un code du bordereau absent du fichier ET un code du fichier absent du bordereau)
    shifted = bool(txt.get("alignment_shift"))
    for img_r, txt_r, fam in ((("R08", "R11"), ("R13",), "prestations (zones 6/7)"), (("R14", "R15"), ("R19",), "actes (zone 10)")):
        if shifted:
            break                      # fichier décalé : les codes lus aux positions officielles ne sont pas fiables
        a = [k for k in img_r if _ano(R.get(k))]
        b = [k for k in txt_r if _ano(R.get(k))]
        if a and b:
            img_codes = sum(((R[k].get("details") or {}).get("non_retrouves") or [] for k in a), [])
            txt_codes = sum(((R[k].get("details") or {}).get("non_retrouves") or [] for k in b), [])
            short = lambda xs: ", ".join(map(str, xs[:6])) + (f" (+{len(xs) - 6})" if len(xs) > 6 else "")
            add(f"substitution-{fam[:5]}", f"Code différent entre les deux documents — {fam}",
                f"Le bordereau porte {short(img_codes)} et le fichier {short(txt_codes)} : "
                "ces alertes pourraient décrire une même ligne codée différemment.", a + b,
                [f"{k} : {R[k].get('explanation')}" for k in a + b],
                "Comparez la ligne concernée sur le bordereau et dans le fichier avant de décider.", "code")
    # 5. écart de total expliqué par des lignes (montants identiques)
    for tot, lines, lab in (("R12", ("R13", "R08", "R11"), "prestations"), ("R17", ("R19", "R14", "R15"), "honoraires")):
        t = R.get(tot)
        if shifted:
            break
        if not _ano(t) or not (t.get("gap") or {}).get("amount_cents"):
            continue
        g = abs(t["gap"]["amount_cents"])
        for lk in lines:
            l = R.get(lk)
            lg = abs(((l or {}).get("gap") or {}).get("amount_cents") or 0)
            if _ano(l) and lg and lg == g:
                add(f"montant-{tot}-{lk}", f"Écart sur le total des {lab}",
                    f"L'écart de {tot} ({amount_str(g)}) est égal au montant des lignes signalées par {lk} : les deux alertes "
                    "pourraient décrire la même différence (elle n'est comptée qu'une fois dans le volet financier).",
                    [tot, lk], [f"{tot} : écart {amount_str(g)}", f"{lk} : lignes {amount_str(lg)}"],
                    f"Examinez d'abord {lk} : la ligne en cause explique peut-être l'écart de total.", "montant")
    # 6. difficultés de lecture OCR
    nv = [r["rule_id"] for r in results if r["status"] == "NON_VERIFIABLE"]
    if len(nv) >= 2:
        add("ocr", "Lectures OCR incertaines", f"Ces {len(nv)} contrôles non vérifiables pourraient tous provenir de la "
            "qualité de lecture du bordereau.", nv, [f"{k} : {(R[k].get('uncertainty') or {}).get('reason', '')}" for k in nv],
            "Ouvrez l'onglet Lectures du bordereau et validez ou corrigez les valeurs incertaines.", "ocr")
    return groups


def triage_portfolio(payloads: dict) -> dict:
    """Synthèse transversale : nombre de dossiers par type de regroupement."""
    by = defaultdict(list)
    for cid, p in payloads.items():
        for g in triage_case(p):
            by[g["type"]].append({"case_id": cid, "title": g["title"], "rules": g["rules"], "hypothesis": g["hypothesis"]})
    return dict(by)
