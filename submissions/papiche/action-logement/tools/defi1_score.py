#!/usr/bin/env python3
"""Défi 1 BâtIA : score de risque de panne bloquante (« Arrêt total »), 01/01 → 30/09/2026.

Modèle : régression logistique L2 (numpy/scipy), donc explicable : contribution = coef × variable standardisée.
Toutes les variables d'une date de référence n'utilisent que l'historique <= cette date (pas de fuite).

Usage : python3 tools/defi1_score.py [dossier_donnees]
Sorties (dossier livrables/) :
  defi1_soumission.csv    equipement_id,score_risque   <- fichier à déposer
  defi1_explications.csv  3 raisons principales par équipement
  defi1_validation.txt    AUC / précision top 10 % vs baseline « âge seul »
"""
import re, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parent.parent
D = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "donnees"
OUT = ROOT / "livrables"
OUT.mkdir(exist_ok=True)

eq = pd.read_csv(D / "04_equipements.csv", parse_dates=["date_pose"])
iv = pd.read_csv(D / "06_interventions.csv", parse_dates=["date_intervention"])
dm = pd.read_csv(D / "05_demandes_locataires.csv", parse_dates=["date_creation"])
lg = pd.read_csv(D / "03_logements.csv")
P = eq[eq.dans_perimetre_prediction == "Oui"].reset_index(drop=True)
assert len(P) == 1285, len(P)

SIGNAUX = ["Nombreux redémarrages enregistrés", "Traces de corrosion visibles sur l'appareil",
           "Usure avancée constatée, pièce à surveiller", "Pièce de rechange difficile à obtenir",
           "Appareil vieillissant, remplacement à prévoir", "Réparation provisoire, fiabilité incertaine"]
FAMILLES = sorted(P.famille.unique())
dep_all = iv[iv.type_intervention == "Dépannage"]
txt = (dm.objet.fillna("") + " " + dm.texte_demande.fillna("")).str.lower()
dm = dm.assign(
    panne=dm.motif.fillna("").str.lower().str.startswith("panne équipement"),
    sympt=txt.str.contains(r"tiède|pas de chauffage|froid|chaudière|chauffe-eau|revient|toujours"),
    reouv=dm.demande_reouverte.astype(str).str.lower().isin(["oui", "true", "1"]))
rot = lg.set_index("logement_id").nb_changements_locataire_2018_2025
LOG = P.set_index("equipement_id").logement_id


def variables(ref):
    ref = pd.Timestamp(ref)
    h = iv[iv.date_intervention <= ref]
    dep = h[h.type_intervention == "Dépannage"]
    X = P[["equipement_id", "famille", "duree_vie_reference_ans", "sous_contrat_entretien"]].copy()
    ix = X.equipement_id
    # âge connu à la date de référence (pose précédente si remplacé depuis)
    pose = P.set_index("equipement_id").date_pose
    prec = pd.to_datetime(P.set_index("equipement_id").date_pose_precedente)
    pr = pd.Series(pd.to_datetime(np.where(pose <= ref, pose, prec)), index=pose.index).fillna(pose)
    remp = h[h.type_intervention == "Remplacement"].groupby("equipement_id").date_intervention.max()
    pr = pd.concat([pr, remp], axis=1).max(axis=1)
    X["age_ans"] = ((ref - ix.map(pr)).dt.days / 365.25).values
    X["age_relatif"] = X.age_ans / X.duree_vie_reference_ans
    X["age_rel_sq"] = X.age_relatif ** 2

    def cnt(df, mois, col=None):
        d = df[df.date_intervention > ref - pd.Timedelta(days=30.4 * mois)]
        return ix.map(d.groupby("equipement_id").size()).fillna(0).values
    X["dep_12m"] = cnt(dep, 12)
    X["dep_24m"] = cnt(dep, 24)
    X["dep_total"] = cnt(dep, 120)
    X["arret_24m"] = cnt(dep[dep.gravite == "Arrêt total"], 24)
    X["degrade_12m"] = cnt(dep[dep.gravite == "Fonctionnement dégradé"], 12)
    X["second_passage_12m"] = cnt(h[h.resultat == "Pièce commandée - second passage"], 12)
    X["anomalie_12m"] = cnt(h[h.resultat.isin(["Anomalie constatée", "Remplacement nécessaire"])], 12)
    X["signaux_texte_18m"] = cnt(h[h.commentaire_technicien.isin(SIGNAUX)], 18)
    # intensité auto-excitée : chaque dépannage laisse une trace en loi de puissance (Hawkes)
    dd = dep.assign(w=(1 + (ref - dep.date_intervention).dt.days / 30.0) ** -1.5)
    X["hawkes"] = ix.map(dd.groupby("equipement_id").w.sum()).fillna(0).values
    vis = h[h.type_intervention == "Entretien préventif"]
    vis24 = vis[vis.date_intervention > ref - pd.Timedelta(days=730)]
    n = ix.map(vis24.groupby("equipement_id").size()).fillna(0).values
    m = ix.map(vis24[vis24.resultat.str.startswith("Logement absent")].groupby("equipement_id").size()).fillna(0).values
    X["visites_manquees_24m"] = m
    X["ratio_manquees"] = m / np.maximum(n, 1)
    X["nb_rempl_passes"] = ix.map(h[h.type_intervention == "Remplacement"].groupby("equipement_id").size()).fillna(0).values
    X["sous_contrat"] = (X.sous_contrat_entretien == "Oui").astype(float)
    # voix du locataire (niveau logement)
    d12 = dm[(dm.date_creation <= ref) & (dm.date_creation > ref - pd.Timedelta(days=365))].dropna(subset=["logement_id"])
    lgid = ix.map(LOG)
    for nom, masque in [("dem_panne_12m", d12.panne), ("dem_symptome_12m", d12.sympt), ("dem_reouv_12m", d12.reouv)]:
        X[nom] = lgid.map(d12[masque].groupby("logement_id").size()).fillna(0).values
    X["rotation_locataires"] = lgid.map(rot).fillna(0).values
    for f in FAMILLES:
        X["fam_" + f] = (X.famille == f).astype(float)
    return X.drop(columns=["famille", "sous_contrat_entretien", "duree_vie_reference_ans"])


def cible(debut, fin):
    p = dep_all[(dep_all.gravite == "Arrêt total") & (dep_all.date_intervention >= debut) & (dep_all.date_intervention <= fin)]
    return P.equipement_id.isin(p.equipement_id).astype(int).values


def auc(y, s):
    r = pd.Series(s).rank().values
    n1, n0 = y.sum(), len(y) - y.sum()
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def prec_top(y, s, q=.10):
    k = int(round(len(y) * q))
    return y[np.argsort(-s)[:k]].sum() / k


def fit(X, y, lam):
    mu, sd = X.mean(axis=0), X.std(axis=0).replace(0, 1)
    Z = ((X - mu) / sd).values
    w0 = np.zeros(Z.shape[1] + 1)
    pos = y.mean()

    def f(w):
        z = Z @ w[1:] + w[0]
        p = 1 / (1 + np.exp(-z))
        ll = -(y * np.log(p + 1e-12) + (1 - y) * np.log(1 - p + 1e-12)).mean() + lam * (w[1:] ** 2).sum()
        g = Z.T @ (p - y) / len(y) + 2 * lam * w[1:]
        return ll, np.r_[(p - y).mean(), g]
    w = minimize(f, w0, jac=True, method="L-BFGS-B").x
    return dict(w=w, mu=mu, sd=sd, cols=list(X.columns))


def proba(m, X):
    Z = ((X[m["cols"]] - m["mu"]) / m["sd"]).values
    return 1 / (1 + np.exp(-(Z @ m["w"][1:] + m["w"][0])))


def jeu(refs):
    Xs, ys = [], []
    for r in refs:
        y = r + 1
        Xs.append(variables(f"{r}-12-31").drop(columns="equipement_id"))
        ys.append(cible(f"{y}-01-01", f"{y}-09-30"))
    return pd.concat(Xs, ignore_index=True), np.concatenate(ys)


# 1) choix du lambda sans toucher au test : entraînement 2020-2022, validation sur 2023 -> pannes 2024
Xa, ya = jeu([2020, 2021, 2022]); Xv, yv = jeu([2023])
cands = [.0003, .001, .003, .01, .03]
sc = {l: auc(yv, proba(fit(Xa, ya, l), Xv)) for l in cands}
lam = max(sc, key=sc.get)

# 2) validation dans le passé : variables au 31/12/2024, test janv.-sept. 2025
Xt, yt = jeu([2020, 2021, 2022, 2023])
m = fit(Xt, yt, lam)
X24 = variables("2024-12-31").drop(columns="equipement_id"); y25 = cible("2025-01-01", "2025-09-30")
s_mod, s_age = proba(m, X24), X24.age_relatif.values
rapport = [
    f"Pannes bloquantes janv.-sept. 2025 : {y25.sum()} / {len(y25)} ({y25.mean():.1%})",
    f"lambda (L2) retenu sur 2024 : {lam}  (AUC par lambda : { {k: round(v, 3) for k, v in sc.items()} })",
    f"AUC  baseline âge relatif : {auc(y25, s_age):.3f}   | modèle BâtIA : {auc(y25, s_mod):.3f}",
    f"Précision top 10 % baseline : {prec_top(y25, s_age):.1%}   | modèle BâtIA : {prec_top(y25, s_mod):.1%}   (taux de base {y25.mean():.1%})",
]
k = int(round(len(y25) * .10))
hit_m, hit_a = int(y25[np.argsort(-s_mod)[:k]].sum()), int(y25[np.argsort(-s_age)[:k]].sum())
rapport.append(f"En inspectant les {k} équipements en tête (10 %) : {hit_m} vraies pannes repérées sur {y25.sum()} "
               f"({hit_m / y25.sum():.0%}) avec BâtIA, contre {hit_a} ({hit_a / y25.sum():.0%}) avec l'âge seul ; hasard attendu : {k * y25.mean():.0f}")
imp = pd.Series(m["w"][1:], index=m["cols"]).sort_values(key=abs, ascending=False)
rapport.append("Variables les plus influentes (coef. standardisé) : " + ", ".join(f"{k} {v:+.2f}" for k, v in imp.head(8).items()))

# 3) soumission : variables au 31/12/2025, entraînement 2020-2024 (pannes observées jusqu'au 30/09/2025)
Xf, yf = jeu([2020, 2021, 2022, 2023, 2024])
mf = fit(Xf, yf, lam)
X25 = variables("2025-12-31")
score = proba(mf, X25.drop(columns="equipement_id"))
sub = pd.DataFrame({"equipement_id": X25.equipement_id, "score_risque": np.round(score, 6)})
sub.to_csv(OUT / "defi1_soumission.csv", index=False, encoding="utf-8")

# explications : 3 plus fortes contributions positives par équipement
Z = ((X25.drop(columns="equipement_id")[mf["cols"]] - mf["mu"]) / mf["sd"]).values * mf["w"][1:]
lib = {"age_relatif": "âge élevé par rapport à la durée de vie", "age_rel_sq": "équipement en fin de vie", "age_ans": "âge",
       "dep_12m": "dépannages sur 12 mois", "dep_24m": "dépannages sur 24 mois", "dep_total": "historique de dépannages",
       "arret_24m": "arrêt total récent", "degrade_12m": "fonctionnement dégradé récent", "hawkes": "récidive de pannes (Hawkes)",
       "second_passage_12m": "pièces commandées / second passage", "anomalie_12m": "anomalies constatées en visite",
       "signaux_texte_18m": "signaux faibles dans les commentaires du technicien", "visites_manquees_24m": "visites d'entretien manquées",
       "ratio_manquees": "part de visites manquées", "nb_rempl_passes": "remplacements passés", "sous_contrat": "contrat d'entretien",
       "dem_panne_12m": "demandes de panne du locataire", "dem_symptome_12m": "plaintes (eau tiède, froid…)",
       "dem_reouv_12m": "demandes réouvertes", "rotation_locataires": "rotation des locataires"}
ex = []
for i, eid in enumerate(X25.equipement_id):
    o = np.argsort(-Z[i])[:3]
    ex.append([eid, round(float(score[i]), 4)] + [lib.get(mf["cols"][j], mf["cols"][j].replace("fam_", "famille ")) for j in o])
pd.DataFrame(ex, columns=["equipement_id", "score_risque", "raison_1", "raison_2", "raison_3"]).sort_values(
    "score_risque", ascending=False).to_csv(OUT / "defi1_explications.csv", index=False, encoding="utf-8")

# 4) contrôles de conformité du fichier à déposer
chk = pd.read_csv(OUT / "defi1_soumission.csv")
assert list(chk.columns) == ["equipement_id", "score_risque"]
assert len(chk) == 1285 and chk.equipement_id.is_unique and set(chk.equipement_id) == set(P.equipement_id)
assert chk.score_risque.notna().all() and chk.score_risque.between(0, 1).all()
(OUT / "defi1_validation.txt").write_text("\n".join(rapport) + "\n", encoding="utf-8")
print("\n".join(rapport))
print(f"\nOK : {OUT/'defi1_soumission.csv'}  ({len(chk)} lignes, 0 NaN, UTF-8, séparateur virgule)")
