"""Entraîne les quatre horizons à partir d'un instantané cohérent de Supabase."""

import argparse, json, subprocess, sys
from pathlib import Path
from scripts.database import export_snapshot
from scripts.schema import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--snapshot-dir", type=Path, default=ROOT / "training_snapshots" / "current"
    )
    parser.add_argument(
        "--types-only",
        action="store_true",
        help="Entraîne les symptômes en conservant les modèles de risque déjà présents.",
    )
    args = parser.parse_args()
    revision = export_snapshot(args.snapshot_dir)
    for horizon in (90, 180, 365, 730):
        output = args.snapshot_dir / f"training_{horizon}.csv"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.build_monthly_training_table",
                "--data-dir",
                str(args.snapshot_dir),
                "--horizon-days",
                str(horizon),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            check=True,
        )
        metadata_path = output.with_suffix(".metadata.json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["source_revision"] = revision
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if not args.types_only:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.train_failure_model",
                    "--input",
                    str(output),
                    "--horizon-days",
                    str(horizon),
                ],
                cwd=ROOT,
                check=True,
            )
            metrics_path = ROOT / "artifacts" / f"{horizon}d" / "metrics.json"
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            metrics["source_revision"] = revision
            metrics["calibrated"] = False
            metrics_path.write_text(
                json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.train_failure_types",
                "--input",
                str(output),
                "--horizon-days",
                str(horizon),
            ],
            cwd=ROOT,
            check=True,
        )
        types_path = (
            ROOT / "artifacts" / f"{horizon}d" / "failure_types" / "manifest.json"
        )
        types_manifest = json.loads(types_path.read_text(encoding="utf-8"))
        types_manifest["source_revision"] = revision
        types_manifest["calibrated"] = False
        types_path.write_text(
            json.dumps(types_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    from scripts.scoring import model_version

    manifest = {
        "source_revision": revision,
        "training_scope": "failure_types" if args.types_only else "all",
        "risk_source_revisions": {
            str(h): json.loads(
                (ROOT / "artifacts" / f"{h}d" / "metrics.json").read_text(
                    encoding="utf-8"
                )
            ).get("source_revision")
            for h in (90, 180, 365, 730)
        },
        "version_modele": model_version(),
        "horizons": [90, 180, 365, 730],
        "calibrated": False,
    }
    (ROOT / "artifacts" / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest), flush=True)


if __name__ == "__main__":
    main()
