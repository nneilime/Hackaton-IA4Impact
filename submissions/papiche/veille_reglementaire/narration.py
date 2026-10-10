# SPDX-License-Identifier: AGPL-3.0-or-later
"""Voix de la présentation Pecha Kucha : le texte dit (avec les vrais chiffres) et la génération audio locale.

Le texte vit dans config/narration_fr.json. Les {chiffres} sont recalculés à partir des vraies exécutions, donc la voix
ne peut pas annoncer un chiffre différent de celui de la page. L'audio est facultatif : sans fichier, la page utilise
la synthèse vocale locale du navigateur (jamais une voix cloud).
"""
from __future__ import annotations

import json
import subprocess

import requests

from . import config, pipeline

AUDIO_FOLDER = config.WEB / "audio"
MAX_SECONDS_PER_SLIDE = 19.5          # une diapositive Pecha Kucha dure 20 s
DEFAULT_TTS_URL = "http://localhost:5005/v1/audio/speech"    # service Orpheus de l'essaim, voir ollama.me.sh / orpheus.me.sh


def french(number: float, decimals: int = 0) -> str:
    """Nombre au format français, lisible à voix haute : 117,7 ; 16,26 ; 400 000."""
    text = f"{number:,.{decimals}f}".replace(",", " ").replace(".", ",")
    return text


def collect_figures() -> dict:
    """Tous les chiffres que la voix peut citer, relus dans les résultats réels."""
    from . import web_data                       # import tardif : web_data utilise ce module
    traces = pipeline.load("traces.jsonl")
    performance = web_data.measure_performance(traces)
    history = web_data.read_prompt_history()
    network = web_data.read_network_runs()
    evaluation = json.loads((config.PROCESSED / "eval.json").read_text())
    bench = json.loads((config.PROCESSED / "bench" / "report.json").read_text())
    cost = json.loads((config.PROCESSED / "cost" / "report.json").read_text())

    holdout_path = config.PROCESSED / "holdout.json"
    holdout = json.loads(holdout_path.read_text()) if holdout_path.exists() else None
    attempts = sum(int(k) * v for k, v in evaluation["essais_par_passage"].items())
    big = cost["scenarios"][2]
    api_options = [o for o in cost["options"] if o["kind"] != "local"]
    flagship = next(o for o in cost["options"] if o["kind"] == "api" and o.get("tier") == "haut" and "Opus" in o["label"])
    recommended = bench["recommendation"]
    return {
        "passages": performance["passages"], "attempts": attempts, "refused": attempts - performance["published"],
        "first_pct": round(100 * performance["first_try"] / performance["passages"]),
        "published_pct": round(100 * performance["published_rate"]), "rescued": performance["rescued_by_retry"],
        "pydantic_refused": performance["refused_by_pydantic"], "proof_refused": performance["refused_by_proof_check"],
        "dose_pct": round(100 * evaluation["exactitude_par_champ"]["dose_value"]),
        "v1_expert": history[0]["sent_to_expert"], "v3_expert": history[-1]["sent_to_expert"],
        "holdout_passages": holdout["passages"] if holdout else 0,
        "holdout_dose_pct": round(100 * holdout["exactitude_par_champ"]["dose_value"]) if holdout else 0,
        "requests": network["cold"]["total_requests"], "cold_mb": french(network["cold"]["total_megabytes"], 1),
        "warm_mb": french(network["warm"]["total_megabytes"], 1) if network["warm"] else "0",
        "vram": french(recommended["vram_1_request_gb"], 1), "passages_big": french(big["passages"]),
        "local_cost": french(cost["options"][0]["totals"][big["name"]], 0),
        "cheapest_cost": french(min(o["totals"][big["name"]] for o in api_options), 0),
        "flagship_cost": french(flagship["totals"][big["name"]], 0),
    }


def render_script() -> list[str]:
    """Le texte de chaque diapositive, chiffres remplacés."""
    templates = json.loads((config.CONFIG / "narration_fr.json").read_text(encoding="utf-8"))["slides"]
    figures = collect_figures()
    return [template.format(**figures) for template in templates]


# ── Génération audio (facultative) ───────────────────────────────────────────

def synthesize(text: str, engine: str, voice: str, wav_path) -> None:
    if engine == "orpheus":
        response = requests.post(config.TTS_URL or DEFAULT_TTS_URL, timeout=600,
                                 json={"model": "orpheus", "input": text, "voice": voice, "response_format": "wav"})
        response.raise_for_status()
        wav_path.write_bytes(response.content)
    elif engine == "espeak":                      # voix de secours, hors ligne, mais robotique
        subprocess.run(["espeak", "-v", "fr", "-s", "150", "-w", str(wav_path), text], check=True)
    else:
        raise SystemExit(f"Moteur inconnu : {engine} (orpheus ou espeak)")


def audio_duration_seconds(path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def convert_to_mp3(wav_path, mp3_path) -> float:
    """Convertit en mp3 léger et accélère légèrement si la phrase dépasse 20 s. Retourne la durée finale."""
    duration = audio_duration_seconds(wav_path)
    tempo = min(1.5, max(1.0, duration / MAX_SECONDS_PER_SLIDE))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), "-filter:a", f"atempo={tempo:.3f}",
                    "-ac", "1", "-ar", "24000", "-b:a", "64k", str(mp3_path)], check=True)
    return audio_duration_seconds(mp3_path)


def render_audio(engine: str = "orpheus", voice: str = "amelie", only: list[int] | None = None) -> list[dict]:
    """Génère les fichiers audio ; `only` = numéros de diapositives à refaire (toutes par défaut)."""
    AUDIO_FOLDER.mkdir(parents=True, exist_ok=True)
    report = []
    for number, text in enumerate(render_script(), 1):
        if only and number not in only:
            continue
        wav_path, mp3_path = AUDIO_FOLDER / f"pk-{number:02d}.wav", AUDIO_FOLDER / f"pk-{number:02d}.mp3"
        synthesize(text, engine, voice, wav_path)
        seconds = convert_to_mp3(wav_path, mp3_path)
        wav_path.unlink()
        report.append({"slide": number, "seconds": round(seconds, 1), "fits_20s": seconds <= 20.0})
        print(f"  diapositive {number:02d} : {seconds:.1f} s", flush=True)
    return report
