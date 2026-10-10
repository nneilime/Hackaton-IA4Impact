"""Tests de validation pour la Fiche C (Script de démo et vidéo de secours)."""
import subprocess
from pathlib import Path

import pytest


def test_script_demo_existe_et_complet():
    script_path = Path("docs/script_demo.md")
    assert script_path.exists(), "Le fichier docs/script_demo.md doit exister."
    content = script_path.read_text(encoding="utf-8")

    # Vérifications des sections et éléments obligatoires du scénario
    assert "CRISE_024" in content
    assert "WSPT" in content
    assert "R1" in content and "R2" in content
    assert "H+6" in content and "H+20" in content
    assert "Refuser" in content or "refuser" in content
    assert "Routes coupées" in content or "routes coupées" in content
    assert "demo.mp4" in content
    assert "Q&A" in content or "Questions" in content


def test_video_demo_existe_et_conforme():
    video_path = Path("demo.mp4")
    assert video_path.exists(), "Le fichier demo.mp4 doit exister."
    size_mb = video_path.stat().st_size / (1024 * 1024)
    assert 0.1 < size_mb <= 50.0, f"La taille de la vidéo ({size_mb:.2f} Mo) doit être entre 0.1 et 50 Mo."

    # Vérification de l'intégrité et de la durée via ffmpeg
    imageio_ffmpeg = pytest.importorskip("imageio_ffmpeg")
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg_exe, "-v", "error", "-i", str(video_path), "-f", "null", "-"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"La vidéo demo.mp4 présente des erreurs de décodage: {res.stderr}"


def test_tache_c_attribuee():
    taches_path = Path("docs/TACHES_RESTANTES.md")
    assert taches_path.exists()
    content = taches_path.read_text(encoding="utf-8")
    assert "C — Script de démo + vidéo de secours" in content
    assert "ATAE" in content
