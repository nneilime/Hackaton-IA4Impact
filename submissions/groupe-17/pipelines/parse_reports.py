"""Extrait les rapports trimestriels PDF du prestataire (texte natif) en tables exploitables."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pandas as pd
import pdfplumber
from batia.config import REPORTS
from batia.io import save_table

RECO = (
    "Pièces d.usure à prévoir|Remplacement à étudier|À surveiller lors de la prochaine visite|"
    "Devis de remplacement disponible sur demande|Nous recommandons un diagnostic approfondi"
)
RE_OBS = re.compile(
    r"^(?P<famille>.+?) — (?P<lieu>LGT-[A-H]\d-\d{3}|Parties communes) \((?P<eqp>EQP-\d{5})\) : "
    r"(?P<nb>\d+) interventions correctives ou anomalies sur les (?P<mois>\d+) derniers mois"
    r"(?:, dont (?P<arrets>\d+) arrêt\(s\) total\(aux\))?\. "
    r"(?:Constat du technicien : « (?P<constat>.+?) »\. )?(?P<reco>" + RECO + r")"
)
RE_VISITE = re.compile(r"^(CH\w+|MUPPR) - (.+?) (\d+) (\d+) (\d+) (\d+) (\d+ %|—)$")
RE_DEP = re.compile(r"^(CH\w+|MUPPR) - (.+?) (\d+) (\d+) (\d+) (\d+) %$")
RE_ABS = re.compile(r"^Résidence ([A-H]) (\d+) (\d+) (\d+) %$")
RE_DEPRES = re.compile(r"^Résidence ([A-H]) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)$")


def pct(s):
    return None if s == "—" else float(s.replace(" %", ""))


def parse_pdf(path):
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    q = re.search(r"Trimestre (T\d) (\d{4})", text)
    tri = f"{q.group(1)} {q.group(2)}"
    visites, deps, absences, depres, obs = [], [], [], [], []
    for line in text.splitlines():
        line = line.strip()
        if m := RE_VISITE.match(line):
            visites.append(
                dict(
                    trimestre=tri,
                    code=m[1],
                    libelle=m[2],
                    programmees=int(m[3]),
                    realisees=int(m[4]),
                    absents=int(m[5]),
                    anomalies=int(m[6]),
                    taux_realisation=pct(m[7]),
                )
            )
        elif m := RE_DEP.match(line):
            deps.append(
                dict(
                    trimestre=tri,
                    code=m[1],
                    libelle=m[2],
                    uo=int(m[3]),
                    depannages=int(m[4]),
                    arrets_totaux=int(m[5]),
                    taux_depannage=float(m[6]),
                )
            )
        elif m := RE_ABS.match(line):
            absences.append(
                dict(
                    trimestre=tri,
                    residence_id=f"RES-{m[1]}",
                    programmees=int(m[2]),
                    absents=int(m[3]),
                    taux_absence=float(m[4]),
                )
            )
        elif m := RE_DEPRES.match(line):
            vals = [int(x) for x in m.groups()[1:]]
            depres.append(
                dict(
                    trimestre=tri,
                    residence_id=f"RES-{m[1]}",
                    CHGAZ=vals[0],
                    CHPAC=vals[1],
                    CHFRC=vals[2],
                    CHVBO=vals[3],
                    CHVCC=vals[4],
                    MUPPR=vals[5],
                    total=vals[6],
                )
            )
    if "Observations du technicien référent" in text:
        blob = text.split("Observations du technicien référent", 1)[1].replace(
            "\n", " "
        )
        for chunk in blob.split("•")[1:]:
            chunk = re.sub(r"\s+", " ", chunk).strip().replace("’", "'")
            m = RE_OBS.match(chunk)
            if m:
                obs.append(
                    dict(
                        trimestre=tri,
                        famille_libelle=m["famille"],
                        lieu=m["lieu"],
                        equipement_id=m["eqp"],
                        nb_interventions=int(m["nb"]),
                        nb_arrets_totaux=int(m["arrets"] or 0),
                        constat=m["constat"] or "",
                        recommandation=m["reco"],
                    )
                )
    return visites, deps, absences, depres, obs


def main():
    acc = [[], [], [], [], []]
    for pdf in sorted(REPORTS.glob("Rapport_activite_*.pdf")):
        for lst, part in zip(acc, parse_pdf(pdf)):
            lst.extend(part)
        print("lu :", pdf.name)
    names = [
        "rapports_visites",
        "rapports_depannages_metier",
        "rapports_absences",
        "rapports_depannages_res",
        "rapports_observations",
    ]
    for n, lst in zip(names, acc):
        df = pd.DataFrame(lst)
        save_table(df, n)
        print(f"{n}: {len(df)} lignes")


if __name__ == "__main__":
    main()
