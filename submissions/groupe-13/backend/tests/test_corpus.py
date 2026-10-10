import zipfile
from pathlib import Path
from sentinel.corpus import safe_extract, build_manifest, pair_documents


def test_zip_malveillant(tmp_path):
    z = tmp_path / "evil.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("../evil.txt", "x")
        f.writestr("/abs.txt", "x")
        f.writestr("ok/fine.txt", "x")
    rep = safe_extract(z, tmp_path / "out")
    assert rep["extracted"] == 1 and len(rep["refused"]) == 2
    assert not (tmp_path / "evil.txt").exists()


def test_manifeste_et_paires():
    m = build_manifest()
    assert m["counts"]["bordereau_jpg"] == 55 and m["counts"]["facture_txt"] == 55
    assert all(len(f["sha256"]) == 64 for f in m["files"])
    p = pair_documents()
    assert len(p) == 55 and all(x["status"] == "paire" for x in p)
    assert {x["family"] for x in p} == {"Facture1", "Facture2", "Facture3"}
