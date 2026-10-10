"""Intègre un CSV de scores produit hors de l'application (ex. Colab) dans le dashboard.

Usage :
  python pipelines/import_scores.py data/external/scores_equipe.csv
  python pipelines/import_scores.py data/external/scores_equipe.csv --auc 0.84 --auc-age 0.78 --p10 0.30 --p10-age 0.15
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
import pandas as pd
from batia.config import OUT
from batia.io import read_table, save_table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument(
        "--mode",
        choices=["rang", "proba"],
        default="rang",
        help="rang : seul l'ordre compte (recommandé) ; proba : le score est déjà une probabilité entre 0 et 1",
    )
    ap.add_argument("--auc", type=float)
    ap.add_argument("--auc-age", type=float)
    ap.add_argument(
        "--p10", type=float, help="part de vraies pannes dans le top 10 %% (ex. 0.30)"
    )
    ap.add_argument("--p10-age", type=float)
    args = ap.parse_args()

    base = read_table("alerts_equipements_interne")
    ext = pd.read_csv(args.csv)
    if not {"equipement_id", "score_risque"} <= set(ext.columns):
        sys.exit(
            f"Colonnes attendues : equipement_id, score_risque. Trouvées : {list(ext.columns)}"
        )
    ext["equipement_id"] = ext.equipement_id.astype(str).str.strip()
    ext["score_risque"] = pd.to_numeric(ext.score_risque, errors="coerce")

    erreurs = []
    if ext.equipement_id.duplicated().any():
        erreurs.append(
            f"{int(ext.equipement_id.duplicated().sum())} doublon(s) d'equipement_id"
        )
    if ext.score_risque.isna().any():
        erreurs.append(
            f"{int(ext.score_risque.isna().sum())} score(s) vide(s) ou non numérique(s)"
        )
    manquants = set(base.equipement_id) - set(ext.equipement_id)
    inconnus = set(ext.equipement_id) - set(base.equipement_id)
    if manquants:
        erreurs.append(
            f"{len(manquants)} équipement(s) du périmètre absent(s), ex. {sorted(manquants)[:3]}"
        )
    if inconnus:
        erreurs.append(
            f"{len(inconnus)} identifiant(s) inconnu(s), ex. {sorted(inconnus)[:3]}"
        )
    if erreurs:
        sys.exit("ERREURS dans le fichier :\n- " + "\n- ".join(erreurs))

    ext = ext.rename(columns={"score_risque": "score_ext"})
    keep = ["equipement_id", "score_ext"] + (
        ["raisons"] if "raisons" in ext.columns else []
    )
    out = base.merge(
        ext[keep].rename(columns={"raisons": "raisons_ext"}),
        on="equipement_id",
        how="left",
    )
    interne = out.proba.copy()

    if args.mode == "proba":
        if not out.score_ext.between(0, 1).all():
            sys.exit("--mode proba exige des scores entre 0 et 1")
        out["proba"] = out.score_ext
    else:
        # on garde l'ORDRE de leurs scores, mais on les replace sur l'échelle de probabilité du modèle interne
        # (taux de base réaliste) pour que les seuils rouge / orange gardent un sens
        pct = (out.score_ext.rank(method="average") - 0.5) / len(out)
        out["proba"] = np.quantile(np.sort(base.proba.values), pct.clip(0, 1))

    if "raisons_ext" in out.columns and out.raisons_ext.notna().any():
        out["raisons"] = out.raisons_ext.fillna(out.raisons)
    out["risque_pondere"] = out.proba * out.poids_nature
    out["score_risque"] = out.score_ext
    out["source"] = f"scores importés ({Path(args.csv).name})"

    rho = out.score_ext.corr(interne, method="spearman")
    k = int(len(out) * 0.10)
    commun = len(
        set(out.nlargest(k, "score_ext").equipement_id)
        & set(base.nlargest(k, "proba").equipement_id)
    )
    out = out.drop(
        columns=["score_ext"]
        + (["raisons_ext"] if "raisons_ext" in out.columns else [])
    )

    save_table(out, "alerts_equipements")
    out[["equipement_id", "score_risque"]].round(4).to_csv(
        OUT / "soumission_defi1.csv", index=False
    )

    for suffixe in (".parquet", ".csv"):
        (OUT / f"metriques_modele{suffixe}").unlink(missing_ok=True)
    vals = [args.auc, args.auc_age, args.p10, args.p10_age]
    if all(v is not None for v in vals):
        save_table(
            pd.DataFrame(
                [
                    {
                        "auc_modele": vals[0],
                        "auc_age_seul": vals[1],
                        "p_top10_modele": vals[2],
                        "p_top10_age_seul": vals[3],
                    }
                ]
            ),
            "metriques_modele",
        )
    else:
        print(
            "Métriques de validation retirées (non fournies) : la ligne de validation disparaît du résumé."
        )

    print(f"OK : {len(out)} équipements importés.")
    print(f"Corrélation de rang avec le modèle interne : {rho:.2f}")
    print(f"Top 10 % en commun avec le modèle interne : {commun} sur {k}")


if __name__ == "__main__":
    main()
