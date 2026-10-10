"""Modèle de risque de panne bloquante (dépannage « Arrêt total ») + export jury.

On se place à des dates de référence passées (31/12 de chaque année), on calcule les
variables avec l'historique antérieur uniquement, puis on regarde si un « Arrêt total »
survient entre le 1er janvier et le 30 septembre suivants.
Validation : référence 31/12/2024 -> test janv.-sept. 2025.
Prédiction : référence 31/12/2025 -> janv.-sept. 2026.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from batia.config import RAW, OUT, REF_DATE, FAMILLE_POIDS
from batia.io import save_table

SIGNAUX = [
    "Nombreux redémarrages enregistrés",
    "Traces de corrosion visibles sur l'appareil",
    "Usure avancée constatée, pièce à surveiller",
    "Appareil vieillissant, remplacement à prévoir",
    "Réparation provisoire, fiabilité incertaine",
    "Pièce de rechange difficile à obtenir",
]
FEATS = [
    "ratio_vie",
    "dep_12m",
    "arret_24m",
    "signaux_12m",
    "anomalies_12m",
    "absences_12m",
    "sans_contrat",
]


def load():
    eq = pd.read_csv(
        RAW / "04_equipements.csv", parse_dates=["date_pose", "date_pose_precedente"]
    )
    iv = pd.read_csv(RAW / "06_interventions.csv", parse_dates=["date_intervention"])
    ref = pd.read_csv(RAW / "10_ref_familles_equipements.csv")
    eq = eq[eq.dans_perimetre_prediction == "Oui"].copy()
    eq = eq.merge(
        ref[["famille", "cout_remplacement_min_ttc", "cout_remplacement_max_ttc"]],
        on="famille",
        how="left",
    )
    eq["cout_remplacement"] = (
        eq.cout_remplacement_min_ttc + eq.cout_remplacement_max_ttc
    ) / 2
    iv = iv[iv.equipement_id.isin(eq.equipement_id)]
    return eq, iv


def features(eq, iv, ref_date):
    ref_date = pd.Timestamp(ref_date)
    d = eq[
        [
            "equipement_id",
            "date_pose",
            "date_pose_precedente",
            "duree_vie_reference_ans",
            "sous_contrat_entretien",
        ]
    ].copy()
    # date de pose valable à la date de référence (évite les fuites si remplacé après)
    pose = d.date_pose.where(d.date_pose <= ref_date, d.date_pose_precedente)
    d["age_ans"] = (ref_date - pose).dt.days / 365.25
    d["ratio_vie"] = (d.age_ans / d.duree_vie_reference_ans).clip(upper=2.0)
    d["ratio_vie"] = d.ratio_vie.fillna(d.ratio_vie.median())
    d["sans_contrat"] = (d.sous_contrat_entretien != "Oui").astype(int)
    h = iv[iv.date_intervention <= ref_date]
    y1 = h[h.date_intervention > ref_date - pd.Timedelta(days=365)]
    y2 = h[h.date_intervention > ref_date - pd.Timedelta(days=730)]
    dep1 = y1[y1.type_intervention == "Dépannage"].groupby("equipement_id").size()
    arr2 = (
        y2[(y2.type_intervention == "Dépannage") & (y2.gravite == "Arrêt total")]
        .groupby("equipement_id")
        .size()
    )
    sig = y1[y1.commentaire_technicien.isin(SIGNAUX)].groupby("equipement_id").size()
    ano = y1[y1.resultat == "Anomalie constatée"].groupby("equipement_id").size()
    abs_ = (
        y1[y1.resultat.str.startswith("Logement absent")]
        .groupby("equipement_id")
        .size()
    )
    for name, s in [
        ("dep_12m", dep1),
        ("arret_24m", arr2),
        ("signaux_12m", sig),
        ("anomalies_12m", ano),
        ("absences_12m", abs_),
    ]:
        d[name] = d.equipement_id.map(s).fillna(0)
    return d.set_index("equipement_id")


def target(iv, ref_date):
    start = pd.Timestamp(ref_date) + pd.Timedelta(days=1)
    end = pd.Timestamp(ref_date) + pd.Timedelta(days=273)  # ~ 9 mois
    w = iv[
        (iv.date_intervention >= start)
        & (iv.date_intervention <= end)
        & (iv.type_intervention == "Dépannage")
        & (iv.gravite == "Arrêt total")
    ]
    return w.groupby("equipement_id").size()


def panel(eq, iv, refs):
    rows = []
    for r in refs:
        X = features(eq, iv, r)
        X["y"] = (X.index.map(target(iv, r)).fillna(0) > 0).astype(int)
        X["ref"] = r
        rows.append(X)
    return pd.concat(rows)


def fit(df):
    mu, sd = df[FEATS].mean(), df[FEATS].std().replace(0, 1)
    m = LogisticRegression(C=0.5, max_iter=1000)
    m.fit((df[FEATS] - mu) / sd, df.y)
    return m, mu, sd


def p_at_k(y, s, k=0.10):
    n = max(1, int(len(y) * k))
    idx = np.argsort(-s)[:n]
    return y[idx].mean()


def phrase(f, row):
    return {
        "ratio_vie": f"Âge à {row.ratio_vie * 100:.0f} % de la durée de vie",
        "dep_12m": f"{int(row.dep_12m)} dépannage(s) sur 12 mois",
        "arret_24m": f"{int(row.arret_24m)} arrêt(s) total(aux) sur 24 mois",
        "signaux_12m": f"{int(row.signaux_12m)} signal(aux) du technicien (usure, corrosion, redémarrages…)",
        "anomalies_12m": f"{int(row.anomalies_12m)} anomalie(s) constatée(s) en visite",
        "absences_12m": f"{int(row.absences_12m)} visite(s) manquée(s) (locataire absent)",
        "sans_contrat": "Équipement hors contrat d'entretien",
    }[f]


def main():
    eq, iv = load()
    # --- validation dans le passé ---
    train = panel(
        eq, iv, ["2019-12-31", "2020-12-31", "2021-12-31", "2022-12-31", "2023-12-31"]
    )
    valid = panel(eq, iv, ["2024-12-31"])
    m, mu, sd = fit(train)
    s = m.predict_proba((valid[FEATS] - mu) / sd)[:, 1]
    base = valid.ratio_vie.values
    metrics = {
        "auc_modele": roc_auc_score(valid.y, s),
        "auc_age_seul": roc_auc_score(valid.y, base),
        "p_top10_modele": p_at_k(valid.y.values, s),
        "p_top10_age_seul": p_at_k(valid.y.values, base),
        "taux_base": valid.y.mean(),
        "n_pannes_test": int(valid.y.sum()),
        "n_equipements": len(valid),
    }
    print({k: round(float(v), 3) for k, v in metrics.items()})
    save_table(pd.DataFrame([metrics]), "metriques_modele")
    # --- modèle final + prédiction 2026 ---
    full = panel(
        eq,
        iv,
        [
            "2019-12-31",
            "2020-12-31",
            "2021-12-31",
            "2022-12-31",
            "2023-12-31",
            "2024-12-31",
        ],
    )
    m, mu, sd = fit(full)
    X = features(eq, iv, REF_DATE)
    Z = (X[FEATS] - mu) / sd
    X["proba"] = m.predict_proba(Z)[:, 1]
    contrib = Z * pd.Series(m.coef_[0], index=FEATS)
    reasons = []
    for eid, row in X.iterrows():
        top = contrib.loc[eid].sort_values(ascending=False)
        top = [f for f in top.index[:3] if contrib.loc[eid, f] > 0.05]
        reasons.append(
            " · ".join(phrase(f, row) for f in top)
            or "Aucun facteur de risque marquant"
        )
    X["raisons"] = reasons
    out = eq[
        [
            "equipement_id",
            "residence_id",
            "batiment_id",
            "logement_id",
            "famille",
            "libelle_famille",
            "duree_vie_reference_ans",
            "cout_remplacement",
        ]
    ].merge(
        X.reset_index()[
            [
                "equipement_id",
                "proba",
                "raisons",
                "age_ans",
                "ratio_vie",
                "dep_12m",
                "arret_24m",
                "signaux_12m",
                "absences_12m",
            ]
        ],
        on="equipement_id",
    )
    out["poids_nature"] = out.famille.map(FAMILLE_POIDS).fillna(0.6)
    out["risque_pondere"] = out.proba * out.poids_nature
    out["score_risque"] = out.proba
    out["source"] = "modèle interne (régression logistique)"
    save_table(out, "alerts_equipements")
    save_table(out, "alerts_equipements_interne")
    out[["equipement_id", "score_risque"]].round(4).to_csv(
        OUT / "soumission_defi1.csv", index=False
    )
    print(
        "OK", len(out), "équipements scorés ; proba moyenne", round(out.proba.mean(), 3)
    )


if __name__ == "__main__":
    main()
