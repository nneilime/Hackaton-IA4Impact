#!/usr/bin/env python3
"""Mesures citées dans la présentation (diapositives 6, 7 et 9) sur 06_interventions.csv.

 - dispersion mensuelle (indice de Fano = variance / moyenne ; 1 pour un processus de Poisson)
 - récidive : part des dépannages suivis d'un nouveau dépannage du même équipement sous 90 jours,
   comparée à des dates tirées uniformément (aucune dépendance), graine fixée
 - exposant de Hurst par analyse R/S sur la série mensuelle (indice, pas une preuve : 96 points seulement)

Usage : python3 tools/analyse_signaux.py [dossier_donnees]   ->  livrables/analyse_signaux.txt
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
D = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "donnees"
iv = pd.read_csv(D / "06_interventions.csv", parse_dates=["date_intervention"])
d = iv[iv.type_intervention == "Dépannage"].sort_values("date_intervention")
m = d.set_index("date_intervention").resample("ME").size()
fano = m.var() / m.mean()


def hurst_rs(s, ns=(4, 6, 8, 12, 16, 24)):
    s = np.asarray(s, float); rs = []
    for n in ns:
        v = []
        for k in range(0, len(s) - n + 1, n):
            c = s[k:k + n]; z = np.cumsum(c - c.mean()); sd = c.std()
            if sd > 0: v.append((z.max() - z.min()) / sd)
        rs.append(np.mean(v))
    return np.polyfit(np.log(ns), np.log(rs), 1)[0]


t0, span = pd.Timestamp("2018-01-01"), (pd.Timestamp("2025-12-31") - pd.Timestamp("2018-01-01")).days
obs = [(g.date_intervention - t0).dt.days.values for _, g in d.groupby("equipement_id")]
rng = np.random.default_rng(0)
nul = [rng.integers(0, span, len(x)) for x in obs]


def recidive(groupes, jours=90):
    r = []
    for x in groupes:
        x = np.sort(x)
        if len(x) > 1: r += list(np.diff(x) <= jours)
    return np.mean(r), len(r)


(ro, n), (rn, _) = recidive(obs), recidive(nul)
txt = (f"Dépannages analysés : {len(d)}\n"
       f"Dispersion mensuelle (Fano) : {fano:.2f}  (Poisson = 1 ; une part vient de la saisonnalité du chauffage)\n"
       f"Récidive <= 90 j : observée {ro:.1%} contre {rn:.1%} si indépendantes, sur {n} intervalles\n"
       f"Hurst R/S mensuel : {hurst_rs(m.values):.2f} sur {len(m)} mois (indice seulement, pas une preuve de fractalité)\n")
out = ROOT / "livrables"; out.mkdir(exist_ok=True)
(out / "analyse_signaux.txt").write_text(txt, encoding="utf-8")
print(txt)
