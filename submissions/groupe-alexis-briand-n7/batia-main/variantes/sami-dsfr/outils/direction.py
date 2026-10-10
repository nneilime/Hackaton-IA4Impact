import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DONNEES = Path(sys.argv[1]) if len(sys.argv) > 1 else RACINE.parents[1] / "donnees" / "kit-batia" / "donnees"
APP = RACINE / "app"
DETAIL = RACINE / "livrables" / "defi1" / "detail_2026.csv"
PLAN = RACINE / "livrables" / "defi2" / "plan_recommande.csv"

ANNEE_REF = 2026
ANNEES_OBS = list(range(2018, 2026))
HORIZON_COURT = 2030
HORIZON_LONG = 2035
HORIZON_GRAPHE = 2032
PLAFOND = 1_500_000

H = {
    "cout_depannage": 250.0,
    "remise_groupe": 0.20,
    "age_mini_groupe": 5,
    "plafond_taux_panne": 0.35,
    "plafond_taux_depannage": 1.0,
    "part_remplacement_defaut": 0.65,
    "mois_engine": 9,
    "premiere_annee_possible": 2027,
    "famille_principale": {
        "RES-A": "chaudiere_gaz_individuelle", "RES-B": "convecteurs_electriques",
        "RES-C": "chaufferie_collective", "RES-D": "pompe_a_chaleur",
        "RES-E": "panneaux_rayonnants", "RES-F": "chaudiere_gaz_individuelle",
        "RES-G": "convecteurs_electriques", "RES-H": "chaudiere_gaz_individuelle",
    },
}


def lire(nom):
    with open(DONNEES / nom, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def lire_chemin(chemin):
    with open(chemin, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def pente(xs, ys):
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return 0.0, my
    a = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return a, my - a * mx


def fr_nombre(x, dec=0):
    s = f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")
    return s


def fr_euro(x):
    return fr_nombre(round(x)) + " €"


def fr_keuro(x):
    return fr_nombre(x / 1000, 0) + " k€"


def fr_pct(x, dec=1):
    return fr_nombre(100 * x, dec) + " %"


def analyser(res, fam, equipements, interventions, scores, ref, residences):
    eq = [e for e in equipements if e["residence_id"] == res and e["famille"] == fam]
    n = len(eq)
    ids = {e["equipement_id"] for e in eq}
    inter = [i for i in interventions if i["equipement_id"] in ids]
    duree_vie = int(ref[fam]["duree_vie_reference_ans"])
    cout_min = float(ref[fam]["cout_remplacement_min_ttc"])
    cout_max = float(ref[fam]["cout_remplacement_max_ttc"])
    poses = [int(e["date_pose"][:4]) for e in eq]
    ages = [ANNEE_REF - p for p in poses]
    age_moyen = sum(ages) / n
    remplaces = sum(1 for e in eq if e["date_pose_precedente"] or int(e["nb_remplacements_2018_2025"] or 0) > 0)
    dep_par_eq = Counter(i["equipement_id"] for i in inter if i["type_intervention"] == "Dépannage")
    deux_plus = sum(1 for v in dep_par_eq.values() if v >= 2)
    dep_an = {a: 0 for a in ANNEES_OBS}
    bloq_an = {a: 0 for a in ANNEES_OBS}
    remp_an = {a: 0 for a in ANNEES_OBS}
    for i in inter:
        a = int(i["date_intervention"][:4])
        if a not in dep_an:
            continue
        if i["type_intervention"] == "Dépannage":
            dep_an[a] += 1
            if i["gravite"] == "Arrêt total":
                bloq_an[a] += 1
        elif i["type_intervention"] == "Remplacement":
            remp_an[a] += 1
    taux_dep = [dep_an[a] / n for a in ANNEES_OBS]
    a_dep, b_dep = pente(ANNEES_OBS, taux_dep)
    taux_dep_2025_fit = max(a_dep * 2025 + b_dep, 1e-6)
    croissance = max(a_dep / taux_dep_2025_fit, 0.0) if taux_dep_2025_fit > 0 else 0.0
    taux_bloq = [bloq_an[a] / n for a in ANNEES_OBS]
    a_bloq, _ = pente(ANNEES_OBS, taux_bloq)
    total_bloq = sum(bloq_an.values())
    total_remp = sum(remp_an.values())
    part_remp = min(total_remp / total_bloq, 1.0) if total_bloq else H["part_remplacement_defaut"]
    somme_score = sum(scores.get(e["equipement_id"], 0.0) for e in eq)
    pannes_2026 = somme_score * 12 / H["mois_engine"]
    taux_neuf = min(taux_dep) if taux_dep else 0.0
    moitie_1 = sum(dep_an[a] for a in ANNEES_OBS[:4])
    moitie_2 = sum(dep_an[a] for a in ANNEES_OBS[4:])

    annees = list(range(ANNEE_REF, HORIZON_LONG + 1))

    def projection(k=1.0):
        lignes = []
        for t in annees:
            r = min(max(a_dep * t + b_dep, 0.0) * k, H["plafond_taux_depannage"])
            p = min(pannes_2026 / n * (1 + croissance) ** (t - ANNEE_REF) * k, H["plafond_taux_panne"])
            pannes = p * n
            remps = pannes * part_remp
            deps = r * n
            cout = deps * H["cout_depannage"] + remps * cout_max
            lignes.append({"annee": t, "taux_depannage": r, "depannages": deps, "taux_panne": p, "pannes": pannes, "remplacements": remps, "cout": cout})
        return lignes

    fil = projection()

    def groupe(y, fil_lignes):
        k_y = sum(1 for p in poses if y - p >= H["age_mini_groupe"])
        cout_groupe = k_y * cout_min * (1 - H["remise_groupe"])
        lignes = []
        for l in fil_lignes:
            t = l["annee"]
            if t < y:
                lignes.append({"annee": t, "cout": l["cout"], "depannages": l["depannages"], "remplacements": l["remplacements"], "investissement": 0.0})
            elif t == y:
                deps = taux_neuf * n
                lignes.append({"annee": t, "cout": cout_groupe + deps * H["cout_depannage"], "depannages": deps, "remplacements": 0.0, "investissement": cout_groupe})
            else:
                deps = taux_neuf * n
                lignes.append({"annee": t, "cout": deps * H["cout_depannage"], "depannages": deps, "remplacements": 0.0, "investissement": 0.0})
        return k_y, cout_groupe, lignes

    def cumul(lignes):
        c, out = 0.0, []
        for l in lignes:
            c += l["cout"]
            out.append(c)
        return out

    cum_fil = cumul(fil)
    scenarios = {}
    for y in range(ANNEE_REF, HORIZON_COURT + 1):
        k_y, cout_groupe, lignes = groupe(y, fil)
        cg = cumul(lignes)
        croisement = next((t for t, a, b in zip(annees, cg, cum_fil) if a <= b and t >= y), None)
        scenarios[y] = {
            "annee": y, "equipements_remplaces": k_y, "investissement": cout_groupe, "lignes": lignes, "cumul": cg,
            "cumul_2030": cg[HORIZON_COURT - ANNEE_REF], "cumul_2035": cg[-1], "croisement": croisement,
        }
    cumul_fil_2030 = cum_fil[HORIZON_COURT - ANNEE_REF]
    cumul_fil_2035 = cum_fil[-1]
    y_eco = min(scenarios, key=lambda y: scenarios[y]["cumul_2035"])
    gagnant_2030 = min(scenarios, key=lambda y: scenarios[y]["cumul_2030"])

    def ecart_2030(k):
        f = projection(k)
        cf = cumul(f)[HORIZON_COURT - ANNEE_REF]
        _, _, g = groupe(ANNEE_REF, f)
        return cf - cumul(g)[HORIZON_COURT - ANNEE_REF]

    bas, haut = 0.0, 20.0
    k_seuil = None
    if ecart_2030(haut) > 0:
        for _ in range(60):
            mid = (bas + haut) / 2
            if ecart_2030(mid) > 0:
                haut = mid
            else:
                bas = mid
        k_seuil = (bas + haut) / 2
    taux_panne_actuel = pannes_2026 / n
    part_deux_plus = deux_plus / n
    seuil = None
    if k_seuil is not None:
        seuil = {
            "facteur": k_seuil,
            "taux_panne_annuel": taux_panne_actuel * k_seuil,
            "part_deux_depannages": min(part_deux_plus * k_seuil, 1.0),
            "depannages_par_an_pour_100": min(taux_dep_2025_fit * k_seuil, H["plafond_taux_depannage"]) * 100,
        }

    return {
        "residence_id": res, "nom": residences[res]["nom"], "famille": fam, "libelle_famille": ref[fam]["libelle"],
        "n": n, "duree_vie": duree_vie, "age_moyen": age_moyen, "part_duree_vie": age_moyen / duree_vie,
        "poses": dict(sorted(Counter(poses).items())), "remplaces_depuis_2018": remplaces,
        "deux_depannages_ou_plus": deux_plus, "part_deux_depannages": part_deux_plus,
        "depannages_par_an": dep_an, "bloquantes_par_an": bloq_an, "remplacements_par_an": remp_an,
        "depannages_2018_2021": moitie_1, "depannages_2022_2025": moitie_2,
        "pente_depannage_par_eq_par_an": a_dep, "croissance_annuelle": croissance, "pente_bloquantes": a_bloq,
        "part_remplacement_sur_panne": part_remp, "taux_neuf": taux_neuf,
        "cout_min": cout_min, "cout_max": cout_max,
        "somme_score_9_mois": somme_score, "pannes_attendues_2026": pannes_2026, "taux_panne_2026": taux_panne_actuel,
        "fil_de_l_eau": fil, "cumul_fil": cum_fil, "cumul_fil_2030": cumul_fil_2030, "cumul_fil_2035": cumul_fil_2035,
        "scenarios": scenarios, "annee_economique": y_eco, "gagnant_2030": gagnant_2030, "seuil": seuil,
    }


def budget(plan):
    reserve = defaultdict(float)
    par_an = defaultdict(list)
    for r in plan:
        y = int(r["annee_debut_recommandee"])
        n = int(r["annees_de_travaux"])
        for k in range(n):
            reserve[y + k] += float(r["cout_par_an"])
            par_an[y + k].append({"operation_id": r["operation_id"], "residence_id": r["residence_id"], "type": r["type_operation"], "cout": float(r["cout_par_an"]), "score": float(r["score_base"])})
    return reserve, par_an


def recommander(a, plan):
    reserve, par_an = budget(plan)
    ope_a = next((r for r in plan if r["residence_id"] == "RES-A" and "chaudi" in r["type_operation"].lower()), None)
    score_ref = float(ope_a["score_base"]) if ope_a else 0.0
    options = []
    for y in range(ANNEE_REF, HORIZON_COURT + 1):
        cout = a["scenarios"][y]["investissement"]
        reste = PLAFOND - reserve.get(y, 0.0)
        deplacer = []
        if cout > reste:
            manque = cout - reste
            for op in sorted(par_an.get(y, []), key=lambda o: o["score"]):
                if manque <= 0:
                    break
                if op["operation_id"] == (ope_a or {}).get("operation_id"):
                    continue
                deplacer.append(op)
                manque -= op["cout"]
            faisable = manque <= 0 and all(op["score"] < score_ref for op in deplacer)
        else:
            faisable = True
        options.append({"annee": y, "investissement": cout, "reste_enveloppe": reste, "a_deplacer": deplacer, "faisable": faisable, "cumul_2035": a["scenarios"][y]["cumul_2035"], "cumul_2030": a["scenarios"][y]["cumul_2030"]})
    y_eco = a["annee_economique"]
    recommandee = next((o["annee"] for o in options if o["annee"] >= max(y_eco, H["premiere_annee_possible"]) and o["faisable"]), None)
    if recommandee is None:
        recommandee = y_eco
    return {"options": options, "annee_recommandee": recommandee, "operation_plan": ope_a, "score_reference": score_ref, "reserve": {str(k): v for k, v in sorted(reserve.items())}}


def svg_courbes(a, y_rec):
    annees = list(range(ANNEE_REF - 1, HORIZON_GRAPHE + 1))
    fil = [0.0] + a["cumul_fil"][: HORIZON_GRAPHE - ANNEE_REF + 1]
    g26 = [0.0] + a["scenarios"][ANNEE_REF]["cumul"][: HORIZON_GRAPHE - ANNEE_REF + 1]
    grec = [0.0] + a["scenarios"][y_rec]["cumul"][: HORIZON_GRAPHE - ANNEE_REF + 1] if y_rec != ANNEE_REF else None
    W, Hh, ml, mr, mt, mb = 760, 300, 64, 150, 16, 36
    maxv = max(fil + g26 + (grec or [])) * 1.08
    pas = 100_000 if maxv < 900_000 else 250_000
    maxv = (int(maxv // pas) + 1) * pas

    def X(i):
        return ml + i * (W - ml - mr) / (len(annees) - 1)

    def Y(v):
        return mt + (Hh - mt - mb) * (1 - v / maxv)

    def chemin(vals):
        return " ".join(f"{'M' if i == 0 else 'L'}{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))

    out = [f'<svg viewBox="0 0 {W} {Hh}" width="100%" role="img" aria-label="Coût cumulé 2026 à 2032 des deux scénarios" font-family="Inter, sans-serif" font-size="12">']
    v = 0
    while v <= maxv:
        out.append(f'<line x1="{ml}" x2="{W - mr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#E5E5E5" stroke-width="1"/>')
        out.append(f'<text x="{ml - 8}" y="{Y(v) + 4:.1f}" text-anchor="end" fill="#666">{fr_keuro(v)}</text>')
        v += pas
    for i, an in enumerate(annees):
        out.append(f'<text x="{X(i):.1f}" y="{Hh - 12}" text-anchor="middle" fill="#666">{an}</text>')
    out.append(f'<path d="{chemin(fil)}" fill="none" stroke="#000091" stroke-width="2.5" stroke-linejoin="round"/>')
    out.append(f'<path d="{chemin(g26)}" fill="none" stroke="#18753C" stroke-width="2.5" stroke-linejoin="round"/>')
    if grec:
        out.append(f'<path d="{chemin(grec)}" fill="none" stroke="#18753C" stroke-width="2" stroke-dasharray="5 4" stroke-linejoin="round"/>')
    for vals, coul in ((fil, "#000091"), (g26, "#18753C")) + (((grec, "#18753C"),) if grec else ()):
        for i, vv in enumerate(vals):
            if i:
                out.append(f'<circle cx="{X(i):.1f}" cy="{Y(vv):.1f}" r="3" fill="{coul}"/>')
    fin = len(annees) - 1
    etiquettes = [(fil[-1], "#000091", f"Au fil de l'eau {fr_keuro(fil[-1])}"), (g26[-1], "#18753C", f"Groupé 2026 {fr_keuro(g26[-1])}")]
    if grec:
        etiquettes.append((grec[-1], "#18753C", f"Groupé {y_rec} {fr_keuro(grec[-1])}"))
    etiquettes.sort(key=lambda e: Y(e[0]))
    derniere = -100
    for val, coul, texte in etiquettes:
        yy = max(Y(val) + 4, derniere + 16)
        derniere = yy
        out.append(f'<text x="{X(fin) + 8:.1f}" y="{yy:.1f}" fill="{coul}" font-weight="600">{texte}</text>')
    cr = a["scenarios"][ANNEE_REF]["croisement"]
    if cr and cr <= HORIZON_GRAPHE:
        i = annees.index(cr)
        out.append(f'<line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{mt}" y2="{Hh - mb}" stroke="#18753C" stroke-dasharray="3 3"/>')
        out.append(f'<text x="{X(i) - 6:.1f}" y="{mt + 12}" text-anchor="end" fill="#18753C">croisement {cr}</text>')
    out.append("</svg>")
    return "\n".join(out)


def svg_barres(a):
    dep = [a["depannages_par_an"][y] for y in ANNEES_OBS]
    blo = [a["bloquantes_par_an"][y] for y in ANNEES_OBS]
    W, Hh, ml, mt, mb = 520, 170, 28, 14, 26
    maxv = max(dep + [1]) * 1.15
    larg = (W - ml - 10) / len(ANNEES_OBS)
    out = [f'<svg viewBox="0 0 {W} {Hh}" width="100%" role="img" aria-label="Dépannages et pannes bloquantes par an de 2018 à 2025" font-family="Inter, sans-serif" font-size="11">']
    for i, y in enumerate(ANNEES_OBS):
        x0 = ml + i * larg
        hd = (Hh - mt - mb) * dep[i] / maxv
        hb = (Hh - mt - mb) * blo[i] / maxv
        out.append(f'<rect x="{x0 + 6:.1f}" y="{Hh - mb - hd:.1f}" width="{larg * 0.5:.1f}" height="{hd:.1f}" rx="2" fill="#000091"/>')
        out.append(f'<rect x="{x0 + 6 + larg * 0.5 + 2:.1f}" y="{Hh - mb - hb:.1f}" width="{larg * 0.28:.1f}" height="{hb:.1f}" rx="2" fill="#CE0500"/>')
        out.append(f'<text x="{x0 + 6 + larg * 0.25:.1f}" y="{Hh - mb - hd - 4:.1f}" text-anchor="middle" fill="#161616" font-weight="600">{dep[i]}</text>')
        if blo[i]:
            out.append(f'<text x="{x0 + 6 + larg * 0.5 + 2 + larg * 0.14:.1f}" y="{Hh - mb - hb - 4:.1f}" text-anchor="middle" fill="#CE0500">{blo[i]}</text>')
        out.append(f'<text x="{x0 + 6 + larg * 0.4:.1f}" y="{Hh - 8}" text-anchor="middle" fill="#666">{y}</text>')
    out.append("</svg>")
    return "\n".join(out)


def page(a, reco, autres, plan_total):
    y_rec = reco["annee_recommandee"]
    s26 = a["scenarios"][ANNEE_REF]
    srec = a["scenarios"][y_rec]
    seuil = a["seuil"]
    cr = s26["croisement"]
    opt = next(o for o in reco["options"] if o["annee"] == y_rec)
    ope = reco["operation_plan"]
    n = a["n"]
    hausse = a["depannages_2022_2025"] / max(a["depannages_2018_2021"], 1) - 1
    ecart_2030 = a["cumul_fil_2030"] - srec["cumul_2030"]
    ecart_2035 = a["cumul_fil_2035"] - srec["cumul_2035"]
    pose_principale = max(a["poses"], key=lambda p: a["poses"][p])

    def ligne_proj(l, g):
        return (f"<tr><td>{l['annee']}</td><td class=n>{fr_nombre(l['depannages'], 0)}</td><td class=n>{fr_nombre(l['pannes'], 1)}</td>"
                f"<td class=n>{fr_nombre(l['remplacements'], 1)}</td><td class=n>{fr_euro(l['cout'])}</td><td class=n>{fr_euro(g['cout'])}</td></tr>")

    lignes_proj = "\n".join(ligne_proj(l, g) for l, g in zip(a["fil_de_l_eau"][: HORIZON_COURT - ANNEE_REF + 1], srec["lignes"]))

    lignes_scen = "\n".join(
        f"<tr{' class=reco' if y == y_rec else ''}><td>Remplacement groupé en {y}</td><td class=n>{s['equipements_remplaces']}</td><td class=n>{fr_euro(s['investissement'])}</td>"
        f"<td class=n>{fr_euro(s['cumul_2030'])}</td><td class=n>{fr_euro(s['cumul_2035'])}</td><td>{s['croisement'] if s['croisement'] else 'après ' + str(HORIZON_LONG)}</td></tr>"
        for y, s in a["scenarios"].items()
    )

    def ligne_budget(o):
        if o["a_deplacer"]:
            dep = ", ".join(f"{d['operation_id']} {d['residence_id'][-1]} {fr_keuro(d['cout'])} note {fr_nombre(d['score'], 1)}" for d in o["a_deplacer"])
        else:
            dep = "rien"
        etat = "oui" if o["faisable"] else "non"
        return (f"<tr{' class=reco' if o['annee'] == y_rec else ''}><td>{o['annee']}</td><td class=n>{fr_euro(PLAFOND - o['reste_enveloppe'])}</td><td class=n>{fr_euro(o['reste_enveloppe'])}</td>"
                f"<td class=n>{fr_euro(o['investissement'])}</td><td>{dep}</td><td>{etat}</td></tr>")

    lignes_budget = "\n".join(ligne_budget(o) for o in reco["options"])

    def ligne_autre(b):
        s = b["scenarios"][ANNEE_REF]
        se = b["seuil"]
        verdict = "Grouper, rentable en moins de 5 ans" if s["croisement"] and s["croisement"] <= HORIZON_COURT else (f"Grouper, rentable en {s['croisement']}" if s["croisement"] else "Au fil de l'eau, pas de bascule avant 2035")
        tendance = b["depannages_2022_2025"] / max(b["depannages_2018_2021"], 1) - 1
        return (f"<tr{' class=reco' if b['residence_id'] == 'RES-A' else ''}><td>{b['nom']}</td><td>{b['libelle_famille']}</td><td class=n>{b['n']}</td>"
                f"<td class=n>{fr_nombre(b['age_moyen'], 1)} / {b['duree_vie']}</td><td class=n>{fr_pct(b['part_deux_depannages'], 0)}</td>"
                f"<td class=n>{'+' if tendance >= 0 else ''}{fr_pct(tendance, 0)}</td><td class=n>{fr_nombre(b['pannes_attendues_2026'] * H['mois_engine'] / 12, 1)}</td>"
                f"<td class=n>{fr_pct(se['taux_panne_annuel'], 1) if se else 'hors portée'}</td><td class=n>{fr_pct(b['taux_panne_2026'], 1)}</td>"
                f"<td class=n>{s['croisement'] if s['croisement'] else 'après ' + str(HORIZON_LONG)}</td><td>{verdict}</td></tr>")

    lignes_autres = "\n".join(ligne_autre(b) for b in autres)

    autres_annees = [o for o in reco["options"] if o["annee"] != y_rec]
    cout_attente = ""
    if y_rec + 1 in a["scenarios"]:
        d = a["scenarios"][y_rec + 1]["cumul_2035"] - srec["cumul_2035"]
        cout_attente = f" Attendre un an de plus coûte environ {fr_euro(d)} de dépannages et de remplacements d'urgence supplémentaires sur l'horizon 2035."

    sens = "au-dessus" if seuil and a["taux_panne_2026"] >= seuil["taux_panne_annuel"] else "juste au-dessous"
    annee_franchissement = None
    if seuil and a["croissance_annuelle"] > 0:
        t = ANNEE_REF
        while t <= HORIZON_LONG and a["taux_panne_2026"] * (1 + a["croissance_annuelle"]) ** (t - ANNEE_REF) < seuil["taux_panne_annuel"]:
            t += 1
        annee_franchissement = t if t <= HORIZON_LONG else None
    phrase_seuil = ("Le modèle ne trouve pas de niveau de panne où le groupé devient moins cher en cinq ans." if not seuil else
                    f"Dès que plus de {fr_nombre(seuil['part_deux_depannages'] * 100, 0)} chaudières sur 100 ont eu deux dépannages ou plus, ou qu'un taux de panne bloquante dépasse "
                    f"{fr_pct(seuil['taux_panne_annuel'], 1)} par an, soit environ {fr_nombre(seuil['taux_panne_annuel'] * n, 0)} chaudières sur {n} qui tombent en panne bloquante dans l'année, "
                    f"le remplacement groupé revient moins cher que le cas par cas sur les cinq années 2026 à 2030. Cela correspond aussi à environ {fr_nombre(seuil['depannages_par_an_pour_100'], 0)} dépannages par an pour 100 chaudières.")
    phrase_annee = (f"La résidence A se situe aujourd'hui {sens} de ce seuil : {fr_nombre(a['part_deux_depannages'] * 100, 0)} chaudières sur 100 ont eu deux dépannages ou plus et le moteur du défi 1 attend "
                    f"un taux de panne bloquante de {fr_pct(a['taux_panne_2026'], 1)} en 2026.")
    if annee_franchissement and sens != "au-dessus":
        phrase_annee += f" Au rythme de hausse observé, {fr_pct(a['croissance_annuelle'], 1)} par an, elle franchit le seuil en {annee_franchissement}."
    if ecart_2030 >= 0:
        phrase_verdict = (f"Sur 2026 à 2030, le groupé lancé en {y_rec} coûte {fr_euro(srec['cumul_2030'])} contre {fr_euro(a['cumul_fil_2030'])} au fil de l'eau, soit {fr_euro(ecart_2030)} de moins.")
    else:
        phrase_verdict = (f"Sur les cinq années 2026 à 2030, le groupé lancé en {y_rec} coûte {fr_euro(srec['cumul_2030'])} contre {fr_euro(a['cumul_fil_2030'])} au fil de l'eau, soit {fr_euro(-ecart_2030)} de plus, "
                          f"parce que l'investissement est payé d'avance alors que les pannes évitées s'étalent dans le temps.")
    phrase_verdict += (f" Sur 2026 à 2035, le groupé lancé en {y_rec} économise {fr_euro(ecart_2035)}." if ecart_2035 >= 0 else f" Sur 2026 à 2035, il coûte encore {fr_euro(-ecart_2035)} de plus.")
    phrase_verdict += f" Lancé dès 2026, le groupé devient moins cher que le cas par cas à partir de {cr if cr else 'après ' + str(HORIZON_LONG)}."
    if y_rec != a["annee_economique"]:
        phrase_verdict += (f" L'année la moins chère est {a['annee_economique']}, mais une opération décidée en octobre ne peut pas être consultée et réalisée avant {H['premiere_annee_possible']}.")
    phrase_verdict += cout_attente

    if opt["a_deplacer"]:
        texte_budget = ("Cette année-là, l'enveloppe est déjà réservée à hauteur de " + fr_euro(PLAFOND - opt["reste_enveloppe"]) + f" par le plan du défi 2, il reste {fr_euro(opt['reste_enveloppe'])}. "
                        f"Pour loger les {fr_euro(opt['investissement'])} du groupé, il faut décaler d'un an " + " et ".join(f"l'opération {d['operation_id']} de la résidence {d['residence_id'][-1]}, {d['type'].lower()}, {fr_euro(d['cout'])}, notée {fr_nombre(d['score'], 1)} sur 100" for d in opt["a_deplacer"]) +
                        f". Ces opérations sont toutes notées en dessous des {fr_nombre(reco['score_reference'], 1)} points de la ligne chaudières de la résidence A dans le classement du défi 2, le décalage ne fait donc pas passer une priorité plus forte derrière une plus faible.")
    else:
        texte_budget = f"Cette année-là, le plan du défi 2 laisse {fr_euro(opt['reste_enveloppe'])} libres sous le plafond, ce qui suffit aux {fr_euro(opt['investissement'])} du groupé sans rien décaler."

    texte_ope = ""
    if ope:
        texte_ope = (f" Le plan d'investissement du kit contient déjà cette opération sous le numéro {ope['operation_id']}, le renouvellement anticipé des chaudières individuelles, estimée {fr_euro(float(ope['cout_estime_ttc']))} et souhaitée en {ope['annee_souhaitee']}, "
                     f"que le calendrier du défi 2 place en {ope['annee_debut_recommandee']}. L'avancer en {y_rec} libère ces {fr_euro(float(ope['cout_estime_ttc']))} en {ope['annee_debut_recommandee']}. "
                     f"L'écart entre les {fr_euro(float(ope['cout_estime_ttc']))} du plan et les {fr_euro(srec['investissement'])} calculés ici tient à l'hypothèse de remise et au prix de référence bas de la table 10 ; le chiffre du plan vise des chaudières à condensation avec un gain énergétique, le nôtre un renouvellement à l'identique.")

    html = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Direction · Remplacement groupé ou au fil de l'eau</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect x='2' y='9' width='28' height='14' rx='2' fill='%23000091'/%3E%3Crect x='2' y='18' width='28' height='5' rx='1' fill='%23CACAFB'/%3E%3C/svg%3E">
<link rel="stylesheet" href="/carte/vendor/polices/polices.css">
<link rel="stylesheet" href="/palette.css">
<style>
:root {{ --bleu: #000091; --vert: #18753C; --encre: #161616; --encre-2: #3A3A3A; --encre-3: #666666; --gris: #F6F6F6; --trait: #DDDDDD; --vert-fond: #DFFEE6; --jaune-fond: #FEECC2; --rayon: 10px; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; }}
body {{ font-family: 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; line-height: 1.5; color: var(--encre); background: #fff; font-feature-settings: "tnum" 1, "lnum" 1; -webkit-font-smoothing: antialiased; }}
a {{ color: var(--bleu); }}
.page {{ max-width: 1080px; margin: 0 auto; padding: 24px 24px 64px; }}
.retour {{ display: inline-block; text-decoration: none; font-weight: 600; margin-bottom: 20px; }}
.retour:hover {{ text-decoration: underline; }}
h1 {{ font-size: 26px; line-height: 1.2; margin: 0 0 8px; color: var(--bleu); }}
h2 {{ font-size: 18px; margin: 40px 0 10px; padding-left: 12px; border-left: 4px solid var(--bleu); line-height: 1.3; }}
h3 {{ font-size: 15px; margin: 20px 0 6px; }}
p {{ margin: 0 0 10px; max-width: 78ch; }}
.chapeau {{ font-size: 16px; color: var(--encre-2); max-width: 82ch; }}
.tuiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 20px 0 8px; }}
.tuile {{ background: var(--gris); border-left: 4px solid #B5B5B5; border-radius: 8px; padding: 12px 14px; }}
.tuile .val {{ font-size: 24px; font-weight: 700; line-height: 1.1; margin-bottom: 4px; }}
.tuile .lib {{ color: var(--encre-3); font-size: 12.5px; }}
.tuile.vert {{ border-left-color: var(--vert); }}
.tuile.vert .val {{ color: var(--vert); }}
.tuile.bleu {{ border-left-color: var(--bleu); }}
.verdict {{ background: var(--vert-fond); border-left: 5px solid var(--vert); border-radius: var(--rayon); padding: 16px 20px; margin: 20px 0; }}
.verdict strong {{ color: var(--vert); }}
.verdict p:last-child {{ margin-bottom: 0; }}
.hypotheses {{ background: var(--jaune-fond); border-left: 5px solid #C8AA39; border-radius: var(--rayon); padding: 16px 20px; margin: 20px 0; }}
.hypotheses h2 {{ margin: 0 0 8px; border-left: 0; padding-left: 0; font-size: 16px; color: var(--encre); }}
.hypotheses ul {{ margin: 0; padding-left: 20px; }}
.hypotheses li {{ margin-bottom: 4px; }}
.grille {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; align-items: start; }}
.carte {{ background: var(--gris); border-radius: var(--rayon); padding: 16px 18px; }}
.carte h3 {{ margin-top: 0; }}
table {{ width: 100%; border-collapse: collapse; margin: 10px 0 14px; font-size: 13.5px; }}
th, td {{ padding: 7px 10px; border-bottom: 1px solid var(--trait); text-align: left; vertical-align: top; }}
th {{ background: var(--gris); font-weight: 600; color: var(--encre-2); }}
td.n, th.n {{ text-align: right; white-space: nowrap; }}
tr.reco td {{ background: var(--vert-fond); font-weight: 600; }}
.legende {{ display: flex; gap: 18px; flex-wrap: wrap; font-size: 12.5px; color: var(--encre-2); margin: 6px 0 4px; }}
.legende span::before {{ content: ""; display: inline-block; width: 14px; height: 3px; border-radius: 2px; margin-right: 6px; vertical-align: middle; background: var(--c); }}
.legende .pt::before {{ border-top: 3px dashed var(--c); background: none; height: 0; }}
.legende .barre::before {{ height: 10px; width: 10px; }}
.graphe {{ background: #fff; border: 1px solid var(--trait); border-radius: var(--rayon); padding: 12px 12px 4px; }}
.note {{ color: var(--encre-3); font-size: 12.5px; }}
table.compact {{ font-size: 12.5px; }}
table.compact th, table.compact td {{ padding: 6px 7px; }}
table.compact th {{ white-space: normal; font-size: 12px; vertical-align: bottom; }}
table.compact td:nth-child(2) {{ min-width: 120px; }}
table.compact td:last-child {{ min-width: 110px; }}
.defile {{ overflow-x: auto; }}
footer {{ margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--trait); color: var(--encre-3); font-size: 12.5px; }}
@media (max-width: 760px) {{ .grille {{ grid-template-columns: 1fr; }} .page {{ padding: 16px 16px 48px; }} h1 {{ font-size: 22px; }} }}
</style>
</head>
<body>
<div class="page">
<a class="retour" href="/">← BâtIA</a>
<h1>Résidence A : remplacer les {n} chaudières d'un coup, ou continuer au cas par cas ?</h1>
<p class="chapeau">Les {n} chaudières gaz individuelles de la résidence A ont été posées pour l'essentiel en {pose_principale}. Elles ont {fr_nombre(a['age_moyen'], 1)} ans en moyenne pour une durée de vie de référence de {a['duree_vie']} ans et entrent dans la phase d'usure. Cette page compare, en euros et sur 2026 à 2030, le remplacement groupé planifié et la poursuite des dépannages et remplacements unitaires en urgence, puis cherche le seuil de bascule et l'année où l'opération tient dans l'enveloppe de {fr_euro(PLAFOND)} par an.</p>

<div class="tuiles">
<div class="tuile"><div class="val">{n}</div><div class="lib">chaudières, {fr_nombre(a['age_moyen'], 1)} ans en moyenne, {fr_pct(a['part_duree_vie'], 0)} de la durée de vie</div></div>
<div class="tuile"><div class="val">{a['remplaces_depuis_2018']}</div><div class="lib">déjà remplacées depuis 2018, dont {a['remplacements_par_an'][2024] + a['remplacements_par_an'][2025]} sur 2024 et 2025</div></div>
<div class="tuile"><div class="val">{a['deux_depannages_ou_plus']}</div><div class="lib">dépannées au moins deux fois depuis 2018, soit {fr_pct(a['part_deux_depannages'], 0)}</div></div>
<div class="tuile bleu"><div class="val">{fr_nombre(a['somme_score_9_mois'], 1)}</div><div class="lib">pannes bloquantes attendues sur 9 mois selon le moteur du défi 1</div></div>
<div class="tuile vert"><div class="val">{y_rec}</div><div class="lib">année recommandée pour le remplacement groupé</div></div>
</div>

<div class="verdict">
<p><strong>Recommandation : lancer le remplacement groupé en {y_rec}.</strong> {phrase_verdict}</p>
<p>{phrase_seuil}</p>
</div>

<h2>1. L'ensemble : où en sont les {n} chaudières</h2>
<div class="grille">
<div>
<p>Les dates de pose se répartissent ainsi : {", ".join(f"{v} en {k}" for k, v in a['poses'].items())}. Les {a['remplaces_depuis_2018']} chaudières posées après 2016 sont des remplacements d'urgence faits après une panne bloquante, l'essentiel sur 2024 et 2025. Sur les pannes bloquantes observées depuis 2018, {fr_pct(a['part_remplacement_sur_panne'], 0)} ont fini par un remplacement plutôt qu'une réparation.</p>
<p>Le rythme s'accélère : {a['depannages_2018_2021']} dépannages sur 2018 à 2021 contre {a['depannages_2022_2025']} sur 2022 à 2025, soit {fr_pct(hausse, 0)} de plus. La tendance linéaire sur les huit années donne {fr_nombre(a['pente_depannage_par_eq_par_an'] * 100, 1)} dépannage de plus par an pour 100 chaudières, ce qui revient à une hausse de {fr_pct(a['croissance_annuelle'], 1)} par an du taux de dépannage. Les pannes bloquantes, un arrêt total de l'appareil, passent de {a['bloquantes_par_an'][2018]} en 2018 à {a['bloquantes_par_an'][2024]} en 2024 et {a['bloquantes_par_an'][2025]} en 2025.</p>
</div>
<div class="carte">
<h3>Dépannages et pannes bloquantes par an</h3>
<div class="legende"><span class="barre" style="--c:#000091">Dépannages</span><span class="barre" style="--c:#CE0500">dont arrêts totaux</span></div>
{svg_barres(a)}
</div>
</div>

<h2>2. Ce qui attend la résidence : pannes attendues 2026 à 2030</h2>
<p>Le moteur du défi 1 donne à chaque chaudière une probabilité de panne bloquante dans les 9 prochains mois. La somme sur les {n} chaudières vaut {fr_nombre(a['somme_score_9_mois'], 1)} pannes bloquantes attendues, soit {fr_nombre(a['pannes_attendues_2026'], 1)} ramenées à une année pleine et un taux de {fr_pct(a['taux_panne_2026'], 1)} par an. Pour les années suivantes, le taux de panne suit la hausse observée de 2018 à 2025, {fr_pct(a['croissance_annuelle'], 1)} par an, plafonnée à {fr_pct(H['plafond_taux_panne'], 0)} du parc. Le nombre de dépannages suit la droite de tendance 2018 à 2025, plafonnée à un dépannage par chaudière et par an. Chaque panne bloquante finit en remplacement unitaire dans {fr_pct(a['part_remplacement_sur_panne'], 0)} des cas, la part observée depuis 2018.</p>
<div class="defile">
<table>
<thead><tr><th>Année</th><th class="n">Dépannages</th><th class="n">Pannes bloquantes</th><th class="n">Remplacements d'urgence</th><th class="n">Coût au fil de l'eau</th><th class="n">Coût si groupé en {y_rec}</th></tr></thead>
<tbody>
{lignes_proj}
<tr><th>Cumul 2026 à 2030</th><th class="n">{fr_nombre(sum(l['depannages'] for l in a['fil_de_l_eau'][:5]), 0)}</th><th class="n">{fr_nombre(sum(l['pannes'] for l in a['fil_de_l_eau'][:5]), 1)}</th><th class="n">{fr_nombre(sum(l['remplacements'] for l in a['fil_de_l_eau'][:5]), 1)}</th><th class="n">{fr_euro(a['cumul_fil_2030'])}</th><th class="n">{fr_euro(srec['cumul_2030'])}</th></tr>
</tbody>
</table>
</div>

<h2>3. Les deux scénarios en euros</h2>
<p>Au fil de l'eau, chaque dépannage coûte {fr_euro(H['cout_depannage'])} et chaque remplacement d'urgence le prix haut de la table 10, {fr_euro(a['cout_max'])}, parce qu'il se fait seul, vite et hors contrat cadre. Le remplacement groupé en année Y remplace les chaudières qui ont au moins {H['age_mini_groupe']} ans cette année-là au prix bas de la table 10, {fr_euro(a['cout_min'])}, moins une remise de {fr_pct(H['remise_groupe'], 0)} obtenue par un contrat groupé, soit {fr_euro(a['cout_min'] * (1 - H['remise_groupe']))} par chaudière. Avant Y, la résidence coûte comme au fil de l'eau. Après Y, les chaudières neuves gardent un taux de dépannage de {fr_pct(a['taux_neuf'], 0)} par an, le plus bas observé sur 2018 à 2025, et aucun remplacement d'urgence.</p>
<div class="graphe">
<div class="legende"><span style="--c:#000091">Au fil de l'eau</span><span style="--c:#18753C">Remplacement groupé en 2026</span>{f'<span class="pt" style="--c:#18753C">Remplacement groupé en {y_rec}</span>' if y_rec != ANNEE_REF else ''}</div>
{svg_courbes(a, y_rec)}
<p class="note">Coût cumulé depuis le 1er janvier 2026 jusqu'en 2032, en euros TTC, sans actualisation ; le trait vertical marque l'année où le groupé lancé en 2026 passe sous le fil de l'eau.</p>
</div>
<div class="defile">
<table>
<thead><tr><th>Scénario</th><th class="n">Chaudières remplacées</th><th class="n">Investissement groupé</th><th class="n">Cumul 2026 à 2030</th><th class="n">Cumul 2026 à 2035</th><th>Devient moins cher que le fil de l'eau en</th></tr></thead>
<tbody>
<tr><td>Au fil de l'eau</td><td class="n">{fr_nombre(sum(l['remplacements'] for l in a['fil_de_l_eau'][:5]), 0)} en urgence d'ici 2030</td><td class="n">0 €</td><td class="n">{fr_euro(a['cumul_fil_2030'])}</td><td class="n">{fr_euro(a['cumul_fil_2035'])}</td><td>référence</td></tr>
{lignes_scen}
</tbody>
</table>
</div>
<p>L'année la moins chère sur l'horizon 2035 est {a['annee_economique']}. Sur cinq ans seulement, aucun scénario groupé ne repasse sous le fil de l'eau quand le croisement tombe après 2030, parce que l'achat des chaudières est payé en une fois. Plus on attend, plus on paie de remplacements d'urgence à {fr_euro(a['cout_max'])} pour des chaudières qu'on remplacera de toute façon.</p>

<h2>4. Le seuil de bascule</h2>
<p>Pour trouver le seuil, le modèle multiplie le taux de panne et le taux de dépannage de 2026 par un même facteur et cherche le niveau où le fil de l'eau et le groupé lancé en 2026 coûtent la même chose sur 2026 à 2030. {'Ce niveau vaut ' + fr_nombre(seuil['facteur'], 2) + ' fois la situation actuelle de la résidence A.' if seuil else ''}</p>
<p><strong>{phrase_seuil}</strong></p>
<p>{phrase_annee} La règle de suivi pour les autres résidences est la même : compter chaque année la part des équipements dépannés au moins deux fois et le taux de panne bloquante attendu par le moteur, et comparer ces deux chiffres au seuil de la famille.</p>

<h2>5. Quelle année, compte tenu de l'enveloppe de {fr_euro(PLAFOND)} par an</h2>
<p>Le calendrier recommandé du défi 2 réserve déjà l'enveloppe presque entièrement chaque année. Le tableau donne, pour chaque année possible, ce qui est déjà engagé, ce qui reste, ce que coûte le groupé et ce qu'il faudrait décaler d'un an pour le loger, en commençant par les opérations les moins bien notées de l'année.</p>
<div class="defile">
<table>
<thead><tr><th>Année</th><th class="n">Déjà engagé</th><th class="n">Reste sous le plafond</th><th class="n">Groupé résidence A</th><th>À décaler d'un an</th><th>Tient sans dégrader une priorité</th></tr></thead>
<tbody>
{lignes_budget}
</tbody>
</table>
</div>
<div class="verdict">
<p><strong>Année recommandée : {y_rec}.</strong> {texte_budget}{texte_ope}</p>
</div>

<div class="hypotheses">
<h2>Hypothèses</h2>
<ul>
<li><strong>Coût d'un dépannage : {fr_euro(H['cout_depannage'])} TTC.</strong> La table des commandes ne contient aucun montant pour les dépannages, qui relèvent du contrat d'entretien ; c'est une hypothèse à faire régler par la direction.</li>
<li><strong>Remplacement d'urgence : {fr_euro(a['cout_max'])} TTC</strong>, le prix haut de la table 10 pour la famille. Les {fr_nombre(plan_total['nb_commandes_chaudiere'])} commandes « remplacement chaudière gaz mixte » du kit coûtent en moyenne {fr_euro(plan_total['moyenne_commande_chaudiere'])}, dans la fourchette de la table.</li>
<li><strong>Remplacement groupé : {fr_euro(a['cout_min'])} TTC moins {fr_pct(H['remise_groupe'], 0)}</strong>, soit {fr_euro(a['cout_min'] * (1 - H['remise_groupe']))} par chaudière. Le prix d'un marché groupé n'est pas dans les données ; la remise de {fr_pct(H['remise_groupe'], 0)} est une hypothèse à confirmer par un devis.</li>
<li><strong>Périmètre du groupé :</strong> seules les chaudières ayant au moins {H['age_mini_groupe']} ans l'année des travaux sont remplacées ; les remplacements récents sont conservés.</li>
<li><strong>Après le groupé :</strong> taux de dépannage de {fr_pct(a['taux_neuf'], 0)} par an, le plus bas observé sur 2018 à 2025, et aucun remplacement d'urgence jusqu'en 2035.</li>
<li><strong>Projection des pannes :</strong> point de départ 2026 égal à la somme des probabilités du moteur du défi 1 ramenée à 12 mois ; hausse annuelle égale à la tendance des dépannages 2018 à 2025, plafonnée à {fr_pct(H['plafond_taux_panne'], 0)} du parc par an ; {fr_pct(a['part_remplacement_sur_panne'], 0)} des pannes bloquantes finissent en remplacement, comme observé.</li>
<li><strong>Au fil de l'eau :</strong> les chaudières remplacées en urgence sont comptées comme le reste du parc, ce qui surestime légèrement le coût de ce scénario dans les dernières années.</li>
<li><strong>Calendrier :</strong> une opération groupée décidée en octobre 2026 ne peut pas être consultée, commandée et réalisée avant {H['premiere_annee_possible']} ; 2026 n'est donc plus une année possible, même si c'est la moins chère.</li>
<li><strong>Enveloppe :</strong> {fr_euro(PLAFOND)} par an, déjà occupée par le calendrier recommandé du défi 2 ; euros TTC courants, sans actualisation ni inflation.</li>
</ul>
</div>

<h2>Les sept autres résidences, même calcul sur leur équipement de chauffage principal</h2>
<div class="defile">
<table class="compact">
<thead><tr><th>Résidence</th><th>Famille</th><th class="n">Nombre</th><th class="n">Âge moyen sur référence</th><th class="n">Dépannées 2 fois ou plus</th><th class="n">Dépannages 2022 à 2025 contre 2018 à 2021</th><th class="n">Pannes attendues sur 9 mois</th><th class="n">Seuil de taux de panne</th><th class="n">Taux de panne 2026</th><th class="n">Groupé 2026 moins cher dès</th><th>Lecture</th></tr></thead>
<tbody>
{lignes_autres}
</tbody>
</table>
</div>
<p class="note">Le prix haut et le prix bas viennent de la table 10 pour chaque famille ; les mêmes hypothèses de dépannage, de remise et de périmètre s'appliquent. Pour la chaufferie collective de la résidence C, cinq appareils seulement, le résultat est fragile.</p>

<footer>Sources : tables 01, 04, 06, 07, 08 et 10 du kit BâtIA, scores du défi 1 dans livrables/defi1/detail_2026.csv, calendrier du défi 2 dans livrables/defi2/plan_recommande.csv. Calcul : outils/direction.py, données dans app/direction.json. Prototype non officiel réalisé pendant le hackathon IA for Impact 2026.</footer>
</div>
</body>
</html>
"""
    return html


def main():
    residences = {r["residence_id"]: r for r in lire("01_residences.csv")}
    equipements = lire("04_equipements.csv")
    interventions = lire("06_interventions.csv")
    commandes = lire("07_commandes.csv")
    ref = {r["famille"]: r for r in lire("10_ref_familles_equipements.csv")}
    scores = {r["equipement_id"]: float(r["score_risque"]) for r in lire_chemin(DETAIL)}
    plan = lire_chemin(PLAN)
    chaud = [float(c["montant_ttc"]) for c in commandes if c["libelle"] == "REMPLACEMENT CHAUDIERE GAZ MIXTE" and c["montant_ttc"]]
    plan_total = {"nb_commandes_chaudiere": len(chaud), "moyenne_commande_chaudiere": sum(chaud) / len(chaud) if chaud else 0.0}

    analyses = [analyser(res, fam, equipements, interventions, scores, ref, residences) for res, fam in H["famille_principale"].items()]
    a = next(x for x in analyses if x["residence_id"] == "RES-A")
    reco = recommander(a, plan)

    html = page(a, reco, analyses, plan_total)
    (APP / "direction.html").write_text(html, encoding="utf-8")

    def allege(x):
        y = {k: v for k, v in x.items() if k not in ("fil_de_l_eau", "scenarios", "cumul_fil")}
        y["fil_de_l_eau"] = x["fil_de_l_eau"]
        y["cumul_fil"] = x["cumul_fil"]
        y["scenarios"] = {str(k): {kk: vv for kk, vv in v.items()} for k, v in x["scenarios"].items()}
        for k in ("depannages_par_an", "bloquantes_par_an", "remplacements_par_an", "poses"):
            y[k] = {str(kk): vv for kk, vv in x[k].items()}
        return y

    sortie = {
        "genere_le": "2026-10-10",
        "hypotheses": {k: v for k, v in H.items() if k != "famille_principale"},
        "familles_principales": H["famille_principale"],
        "plafond_annuel": PLAFOND,
        "commandes_chaudiere": plan_total,
        "residence_a": allege(a),
        "recommandation": reco,
        "residences": [allege(x) for x in analyses],
    }
    (APP / "direction.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")

    s26 = a["scenarios"][ANNEE_REF]
    print(f"RES-A : {a['n']} chaudières, âge moyen {a['age_moyen']:.1f}, remplacées {a['remplaces_depuis_2018']}, deux dépannages ou plus {a['deux_depannages_ou_plus']}")
    print(f"pannes 9 mois {a['somme_score_9_mois']:.1f}, taux 2026 {a['taux_panne_2026']:.3f}, croissance {a['croissance_annuelle']:.3f}")
    print(f"fil 2030 {a['cumul_fil_2030']:.0f} fil 2035 {a['cumul_fil_2035']:.0f}")
    for y, s in a["scenarios"].items():
        print(f"groupé {y}: inv {s['investissement']:.0f} cum2030 {s['cumul_2030']:.0f} cum2035 {s['cumul_2035']:.0f} croisement {s['croisement']}")
    print("seuil", a["seuil"])
    print("recommandée", reco["annee_recommandee"], [(o["annee"], o["faisable"], [d["operation_id"] for d in o["a_deplacer"]]) for o in reco["options"]])


if __name__ == "__main__":
    main()
