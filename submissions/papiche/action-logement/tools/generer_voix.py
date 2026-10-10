#!/usr/bin/env python3
"""Génère la voix off (Orpheus-FastAPI, voix « pierre ») des 20 diapositives.

Usage : python3 tools/generer_voix.py [numéro ...]   (sans argument : les 20)
Prérequis : serveur Orpheus-FastAPI sur http://127.0.0.1:5005 et ffmpeg.
Entrée : tools/voix_textes.json  ·  Sortie : assets/voix/NN.mp3 + durees.json
Chaque piste doit durer moins de 20 s (format Pecha Kucha).
"""
import json, subprocess, sys, tempfile, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "http://127.0.0.1:5005/v1/audio/speech"
MAX_S = 19.0
textes = json.loads((ROOT / "tools/voix_textes.json").read_text(encoding="utf-8"))
out = ROOT / "assets/voix"
out.mkdir(parents=True, exist_ok=True)
dfile = out / "durees.json"
durees = json.loads(dfile.read_text()) if dfile.exists() else {}

def duree(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True, check=True)
    return float(r.stdout)

def synth(texte, wav):
    req = urllib.request.Request(URL, method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"model": "orpheus", "input": texte, "voice": "pierre",
                         "response_format": "wav", "speed": 1.0}).encode())
    with urllib.request.urlopen(req, timeout=300) as r:
        wav.write_bytes(r.read())

todo = [int(a) for a in sys.argv[1:]] or range(1, len(textes) + 1)
for n in todo:
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "v.wav"
        synth(textes[n - 1], wav)
        mp3 = out / f"{n:02d}.mp3"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
            "-af", "silenceremove=start_periods=1:start_threshold=-50dB,loudnorm=I=-18:TP=-2",
            "-ac", "1", "-ar", "24000", "-b:a", "64k", str(mp3)], check=True)
    durees[f"{n:02d}"] = round(duree(mp3), 2)
    flag = "  <-- TROP LONG" if durees[f"{n:02d}"] > MAX_S else ""
    print(f"{n:02d}  {durees[f'{n:02d}']:5.1f} s  {len(textes[n-1].split())} mots{flag}", flush=True)
    dfile.write_text(json.dumps(durees, indent=1))
