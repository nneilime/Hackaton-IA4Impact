# SPDX-License-Identifier: AGPL-3.0-or-later
"""Storyboard vidéo de la présentation, au format de `generate_scene.sh` (Astroport.ONE/IA/generators).

Une prise par diapositive Pecha Kucha : la page `index.html` est filmée vivante (animations p5.js) pendant 20 s, avec la voix-off
du texte de `config/narration_fr.json` (voix Orpheus « amelie »). Même texte que la présentation : image et voix ne peuvent pas diverger.
Rendu : generate_scene.sh video/storyboard.json   (voir `./veille storyboard`).
"""
from __future__ import annotations

import json

from . import config, narration

SLIDE_SECONDS = 20
TRANSITION_SECONDS = 0.4
VIDEO_FOLDER = config.ROOT / "video"


def build(height: int = 720, voice: str = "amelie") -> dict:
    texts = narration.render_script()
    page = (config.ROOT / "index.html").resolve().as_uri()
    shots = []
    for index, text in enumerate(texts):
        shot = {"screen": page,
                "record": {"wait": 2500, "actions": [{"js": f"window.PechaKucha.present({index})"}, {"mark": True}]},
                "duration": SLIDE_SECONDS, "voiceover": text}
        if index < len(texts) - 1:
            shot["transition"] = {"type": "fade", "duration": TRANSITION_SECONDS}
        shots.append(shot)
    return {"ratio": "16:9", "height": height, "style": "clean", "voice": voice, "shots": shots}


def srt_time(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    return f"{milliseconds // 3600000:02d}:{milliseconds // 60000 % 60:02d}:{milliseconds // 1000 % 60:02d},{milliseconds % 1000:03d}"


def build_subtitles(texts: list[str]) -> str:
    """Sous-titres : chaque phrase de la voix-off, calée sur sa diapositive (les fondus raccourcissent la durée totale)."""
    blocks = []
    for index, text in enumerate(texts):
        start = index * (SLIDE_SECONDS - TRANSITION_SECONDS) + 0.6
        end = start + min(SLIDE_SECONDS - 2, max(4.0, len(text.split()) / 2.6))      # ≈ 2,6 mots par seconde
        blocks.append(f"{index + 1}\n{srt_time(start)} --> {srt_time(end)}\n{text}\n")
    return "\n".join(blocks)


def write(height: int = 720) -> dict:
    VIDEO_FOLDER.mkdir(exist_ok=True)
    storyboard = build(height)
    (VIDEO_FOLDER / "storyboard.json").write_text(json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8")
    (VIDEO_FOLDER / "sous-titres.srt").write_text(build_subtitles(narration.render_script()), encoding="utf-8")
    return {"storyboard": "video/storyboard.json", "subtitles": "video/sous-titres.srt", "shots": len(storyboard["shots"])}
