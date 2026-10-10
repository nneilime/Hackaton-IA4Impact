"""Reproductibilité de l'extraction : ré-extrait un bordereau et compare au cache livré.
Ignoré si aucun moteur OCR n'est installé."""
import pytest
from sentinel.corpus import corpus_root, sha256_file
from sentinel.config import JPG_SUBDIR
from sentinel import ocrcache

try:
    from sentinel.ocr.engine import get_engine
    get_engine("tesseract"); get_engine("rapidocr")
    HAVE = True
except Exception:
    HAVE = False


@pytest.mark.skipif(not HAVE, reason="moteurs OCR non installés")
def test_extraction_reproductible():
    from sentinel.ocr.extract import extract_bordereau
    p = corpus_root() / JPG_SUBDIR / "Facture3_01.jpg"
    new = extract_bordereau(p)
    old, statut, _ = ocrcache.read(sha256_file(p))
    if old is None:
        pytest.skip(f"cache OCR non disponible pour la comparaison ({statut})")
    for k in ("Z1", "Z2", "Z3", "Z4", "Z5", "Z8", "Z12", "Z13", "Z15"):
        assert new["fields"][k]["value"] == old["fields"][k]["value"], k
    assert new["fields"]["Z4"]["value"] == "491901"
    assert new["fields"]["Z13"]["value"] == 44878
    assert [s["status"] for s in new["signatures"]["Z14"]] == ["PRESENT"]
    assert new["layout"]["family"] == "F3"
