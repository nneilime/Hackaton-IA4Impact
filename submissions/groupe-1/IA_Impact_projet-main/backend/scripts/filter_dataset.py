"""Crée une copie de la base limitée à certains types de transport.

    python scripts/filter_dataset.py                       # data/ -> data/train_lio/ (trains TER liO seulement)
    python scripts/filter_dataset.py --out data/ter_lio --modes "Train TER" "Car TER" "Car liO"

La base complète (data/*.csv, produite par build_from_gtfs.py) n'est pas modifiée. La copie contient les mêmes
fichiers, réduits aux missions des modes gardés et aux arrêts qu'elles desservent ; l'API la charge via
la variable d'environnement IA_DATASET (voir app/main.py).
"""
import argparse
import csv
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
TRAIN_LIO = ["Train TER"]  # les trains régionaux d'Occitanie, exploités sous la marque liO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=DATA)
    ap.add_argument("--out", type=Path, default=DATA / "train_lio")
    ap.add_argument("--modes", nargs="+", default=TRAIN_LIO, help="types de transport à garder")
    args = ap.parse_args()
    keep = set(args.modes)
    args.out.mkdir(parents=True, exist_ok=True)

    def copy(name, pred):
        with open(args.src / name, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [r for r in reader if pred(r)]
        with open(args.out / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=reader.fieldnames)
            w.writeheader()
            w.writerows(rows)
        return rows

    missions = copy("missions_occitanie.csv", lambda r: r["mode"] in keep)
    served = {s for m in missions for s in m["stops"].split("|")}
    stations = copy("stations_occitanie.csv", lambda r: r["stop_id"] in served)
    walks = copy("walk_links.csv", lambda r: r["from_id"] in served and r["to_id"] in served)
    segments = copy("connections_occitanie.csv",
                    lambda r: r["stop_id"].split(":", 1)[1].rsplit("-", 1)[0].removeprefix("OCE") in keep)

    info = json.loads((args.src / "build_info.json").read_text(encoding="utf-8"))
    info.update({"dataset": args.out.name, "modes_kept": sorted(keep), "stations": len(stations),
                 "missions": len(missions), "segments": len(segments), "walk_links": len(walks) // 2,
                 "modes": {k: v for k, v in info["modes"].items() if k in keep}})
    (args.out / "build_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
