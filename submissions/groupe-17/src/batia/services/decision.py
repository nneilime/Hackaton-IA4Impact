"""Résumé automatique + recommandation de l'outil (l'IA recommande, l'humain décide)."""

from datetime import datetime
import pandas as pd
from batia import config as C

LOG = C.OUT / "decisions_log.csv"


def fmt_eur(x: float) -> str:
    return f"{x:,.0f} €".replace(",", " ")


def recommandation(
    equip: pd.DataFrame, bat: pd.DataFrame, ops_retenues: pd.DataFrame, budget: float
) -> dict:
    k = int(len(equip) * 0.10)
    top = equip.nlargest(k, "proba")
    rouges = bat[bat.statut == "rouge"].sort_values("risque_max", ascending=False)
    return {
        "n_rouge": len(rouges),
        "n_orange": int((bat.statut == "orange").sum()),
        "n_vert": int((bat.statut == "vert").sum()),
        "top_k": k,
        "top": top,
        "cout_top": top.cout_remplacement.sum(),
        "rouges": rouges,
        "ops": ops_retenues,
        "cout_ops": float(ops_retenues.cout_estime_ttc.sum()),
        "budget": budget,
        "n_rapport": int(equip.remonte_par_rapport.sum()),
    }


def resume_md(r: dict, equip: pd.DataFrame, metr: dict) -> str:
    total = r["n_rouge"] + r["n_orange"] + r["n_vert"]
    l = [
        f"- **{r['n_rouge']} bâtiment(s) en rouge**, {r['n_orange']} en orange et {r['n_vert']} en vert sur {total}.",
        f"- **{len(equip)} équipements scorés** ; risque moyen de panne bloquante sur la période : {equip.proba.mean() * 100:.1f} %.",
        f"- Le **top 10 % ({r['top_k']} équipements)** est à inspecter en priorité ; coût de remplacement exposé : {fmt_eur(r['cout_top'])}.",
        f"- **{r['n_rapport']} équipement(s)** ont été remontés au moins en orange grâce aux rapports du prestataire (T2-T4 2025).",
        f"- Dans l'enveloppe de {fmt_eur(r['budget'])}, **{len(r['ops'])} opération(s)** de rénovation sont retenues pour {fmt_eur(r['cout_ops'])}.",
    ]
    if metr:
        l.append(
            f"- Validation dans le passé (réf. 31/12/2024 → janv.-sept. 2025) : AUC {metr['auc_modele']:.2f} contre {metr['auc_age_seul']:.2f} pour l'âge seul ; "
            f"{metr['p_top10_modele'] * 100:.0f} % de vraies pannes dans le top 10 % (contre {metr['p_top10_age_seul'] * 100:.0f} %)."
        )
    return "\n".join(l)


def log_decision(choix: str, decideur: str, commentaire: str, r: dict) -> None:
    row = pd.DataFrame(
        [
            {
                "horodatage": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "decideur": decideur,
                "decision": choix,
                "commentaire": commentaire,
                "n_batiments_rouges": r["n_rouge"],
                "n_equipements_a_inspecter": r["top_k"],
                "budget": r["budget"],
                "n_operations": len(r["ops"]),
            }
        ]
    )
    row.to_csv(LOG, mode="a", header=not LOG.exists(), index=False)


def read_log() -> pd.DataFrame:
    return pd.read_csv(LOG) if LOG.exists() else pd.DataFrame()
