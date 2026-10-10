"""Construit les cartes de traits de référence des 3 mises en page à partir d'un bordereau
de chaque famille du corpus (seuls les traits du formulaire sont conservés, aucune donnée)."""
import sys
from pathlib import Path
import cv2
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from sentinel.ocr.layout import line_mask_small, REF_DIR  # noqa
from sentinel.config import CORPUS_DIR, JPG_SUBDIR  # noqa

REFS = {"F1": "Facture1_02.jpg", "F2": "Facture2_02.jpg", "F3": "Facture3_02.jpg"}
if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else CORPUS_DIR / "General-main" / JPG_SUBDIR
    REF_DIR.mkdir(exist_ok=True)
    for fam, name in REFS.items():
        g = cv2.imread(str(src / name), cv2.IMREAD_GRAYSCALE)
        cv2.imwrite(str(REF_DIR / f"{fam}.png"), line_mask_small(g).astype("uint8"))
        print(fam, "<-", name)
