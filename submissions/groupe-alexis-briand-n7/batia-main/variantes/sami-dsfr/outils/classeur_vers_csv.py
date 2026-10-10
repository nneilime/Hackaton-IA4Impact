import csv
import datetime as dt
import os
import re
import sys

import openpyxl


def cellule(v):
    if v is None:
        return ""
    if isinstance(v, dt.datetime):
        return v.strftime("%Y-%m-%d %H:%M") if (v.hour or v.minute) else v.strftime("%Y-%m-%d")
    if isinstance(v, dt.date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, bool):
        return "Oui" if v else "Non"
    return str(v).strip()


def main(chemin, sortie):
    os.makedirs(sortie, exist_ok=True)
    wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
    for ws in wb.worksheets:
        lignes = ws.iter_rows(values_only=True)
        entete = None
        for l in lignes:
            if l and any(c not in (None, "") for c in l):
                entete = [cellule(c) for c in l]
                break
        if not entete:
            continue
        while entete and entete[-1] == "":
            entete.pop()
        nom = re.sub(r"[^\w.-]+", "_", ws.title).strip("_") or "feuille"
        with open(os.path.join(sortie, nom + ".csv"), "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(entete)
            for l in lignes:
                vals = [cellule(c) for c in l[: len(entete)]]
                if any(vals):
                    vals += [""] * (len(entete) - len(vals))
                    w.writerow(vals)
        print(nom)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
