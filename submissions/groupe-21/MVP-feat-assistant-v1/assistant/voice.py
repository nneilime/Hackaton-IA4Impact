"""Voix de l'assistant, côté serveur (utilisée par tous les navigateurs pour une voix identique et naturelle).

- transcribe : audio du micro (WAV découpé par le navigateur) → texte, par l'API Gemini (GEMINI_API_KEY,
  modèle gemini-3.5-transcribe, gemini-3.8-flash s'il est saturé) ;
- synthesize : texte → audio. Par défaut, voix neuronale Microsoft (edge-tts, « Denise » en français) : le texte des
  réponses de l'assistant est envoyé au service de synthèse de Microsoft. En secours, ou avec ASSISTANT_TTS=piper,
  voix locale Piper (aucun service tiers ; voix téléchargée au premier usage dans data/voices/, ignoré par git).

Rien n'est écrit au journal ni conservé sur disque : ni l'audio, ni le texte (cache en mémoire des phrases lues).
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import urllib.error
import urllib.request
import logging
import os
import re
import threading
import wave
from collections import OrderedDict
from pathlib import Path

log = logging.getLogger("assistant")

VOICES_DIR = Path(__file__).resolve().parents[1] / "data" / "voices"
PIPER_VOICES = {"fr": "fr_FR-siwis-medium", "en": "en_GB-alba-medium", "es": "es_ES-davefx-medium"}
EDGE_VOICES = {"fr": "fr-FR-DeniseNeural", "en": "en-GB-SoniaNeural", "es": "es-ES-ElviraNeural"}
TTS_ENGINE = os.environ.get("ASSISTANT_TTS", "piper")  # piper (locale) ou edge (voix Microsoft : refusée en 403 en oct. 2026)
STT_MODEL = os.environ.get("ASSISTANT_STT_MODEL", "gemini-3.5-transcribe")      # modèle Gemini dédié
STT_FALLBACK_MODEL = os.environ.get("ASSISTANT_STT_FALLBACK_MODEL", "gemini-3.8-flash")   # si le premier est saturé
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
MAX_TTS_CHARS = 1000
# Vocabulaire bancaire attendu, transmis au modèle de transcription : « RIB » n'est plus compris « rythme »,
# ni « crédit auto » « crédit au taux ».
STT_PROMPTS = {
    "fr": "Caisse d'Épargne, RIB, IBAN, Sécur'Pass, Wero, prêt étudiant, prêt personnel, crédit auto, crédit immobilier, "
          "prêt à la consommation, TAEG, mensualité, Livret A, LEP, PEL, assurance emprunteur, carte bancaire, opposition, "
          "virement, bénéficiaire, plafond, chéquier.",
}
# Phrases qu'un modèle de transcription produit parfois sur un bruit ou un souffle : ignorées
_HALLUCINATIONS = re.compile(r"sous-titr|amara\.org|merci d'avoir regard|abonnez-vous|thanks for watching|^\W*$", re.I)


class VoiceError(Exception):
    """Erreur présentable à l'utilisateur."""


LANG_NAMES = {"fr": "français", "en": "anglais", "es": "espagnol"}


def stt_configured() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def transcribe(audio: bytes, filename: str, lang: str = "fr") -> str:
    """Audio → texte par Gemini (modèle de transcription, puis modèle de secours s'il est saturé)."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise VoiceError("La reconnaissance vocale n'est pas configurée sur ce serveur (clé Gemini absente).")
    lang = lang if lang in PIPER_VOICES else "fr"
    mime = {"wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/mp4", "ogg": "audio/ogg"}.get(
        filename.rsplit(".", 1)[-1], "audio/webm")
    instruction = (f"Transcris mot pour mot cet enregistrement en {LANG_NAMES[lang]}. Réponds uniquement par la "
                   "transcription, sans commentaire ; rien si l'enregistrement ne contient pas de parole.")
    if lang in STT_PROMPTS:
        instruction += " Vocabulaire possible : " + STT_PROMPTS[lang]
    body = json.dumps({"contents": [{"parts": [{"text": instruction},
                                               {"inline_data": {"mime_type": mime, "data": base64.b64encode(audio).decode()}}]}],
                       "generationConfig": {"temperature": 0}}).encode()
    models = [m for m in dict.fromkeys((STT_MODEL, STT_FALLBACK_MODEL)) if m]
    for n, model in enumerate(models):
        req = urllib.request.Request(GEMINI_API.format(model), data=body, method="POST",
                                     headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = _transcript(json.load(resp))
            return "" if _HALLUCINATIONS.search(text) else text
        except urllib.error.HTTPError as e:
            log.warning("transcription Gemini en échec (%s) : statut %s", model, e.code)
            if e.code in (429, 500, 503, 504) and n < len(models) - 1:
                continue
            if e.code == 429:
                raise VoiceError("Le service de reconnaissance vocale est très sollicité : réessayez dans un instant.") from None
            if e.code in (401, 403):
                raise VoiceError("La reconnaissance vocale est mal configurée sur ce serveur (clé Gemini refusée).") from None
            raise VoiceError("Je n'ai pas pu comprendre l'enregistrement. Réessayez, ou écrivez votre message.") from None
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError, TypeError) as e:
            log.warning("transcription Gemini en échec (%s) : %s", model, type(e).__name__)
            if n < len(models) - 1:
                continue
            raise VoiceError("Le service de reconnaissance vocale ne répond pas. Réessayez, ou écrivez votre message.") from None
    raise VoiceError("Le service de reconnaissance vocale ne répond pas. Réessayez, ou écrivez votre message.")


def _transcript(data: dict) -> str:
    """Texte d'une réponse Gemini : champ audioTranscription (modèle de transcription) ou texte simple."""
    parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    return " ".join((p.get("audioTranscription") or {}).get("text") or p.get("text") or "" for p in parts).strip()


class Speaker:
    """Voix Microsoft (edge-tts) avec Piper en secours ; cache en mémoire des phrases déjà lues."""

    def __init__(self, directory: Path = VOICES_DIR, engine: str = TTS_ENGINE):
        self.directory, self.engine, self._voices, self._lock = directory, engine, {}, threading.Lock()
        self._cache: OrderedDict = OrderedDict()
        self._cache_lock = threading.Lock()

    @property
    def available(self) -> bool:
        try:
            import piper  # noqa: F401
            return True
        except ImportError:
            return False

    def _voice(self, lang: str):
        name = PIPER_VOICES.get(lang, PIPER_VOICES["fr"])
        if name not in self._voices:
            from piper import PiperVoice
            from piper.download_voices import download_voice
            model = self.directory / f"{name}.onnx"
            if not model.exists():
                self.directory.mkdir(parents=True, exist_ok=True)
                log.info("téléchargement de la voix %s (première utilisation)", name)
                download_voice(name, self.directory)
            self._voices[name] = PiperVoice.load(str(model))
        return self._voices[name]

    def synthesize(self, text: str, lang: str = "fr", rate: float = 1.0) -> tuple[bytes, str]:
        """Audio et type MIME. Voix neuronale si possible, sinon voix locale."""
        text = " ".join(str(text).split())[:MAX_TTS_CHARS]
        if not text:
            raise VoiceError("Rien à lire.")
        rate = min(max(float(rate or 1.0), 0.5), 2.0)
        key = (self.engine, lang, rate, text)
        with self._cache_lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        result = None
        if self.engine == "edge":
            try:
                result = (self._edge(text, lang, rate), "audio/mpeg")
            except Exception as e:  # service injoignable, réseau…
                log.warning("voix neuronale indisponible (%s) : voix locale utilisée", type(e).__name__)
        if result is None:
            result = (self._piper(text, lang, rate), "audio/wav")
        with self._cache_lock:
            self._cache[key] = result
            while len(self._cache) > 300:
                self._cache.popitem(last=False)
        return result

    def _edge(self, text: str, lang: str, rate: float) -> bytes:
        import edge_tts

        async def run() -> bytes:
            pct = round((rate - 1.0) * 100)
            com = edge_tts.Communicate(text, EDGE_VOICES.get(lang, EDGE_VOICES["fr"]), rate=f"{pct:+d}%")
            return b"".join([c["data"] async for c in com.stream() if c["type"] == "audio"])

        audio = asyncio.run(asyncio.wait_for(run(), timeout=8))
        if not audio:
            raise VoiceError("Audio vide.")
        return audio

    def _piper(self, text: str, lang: str, rate: float) -> bytes:
        if not self.available:
            raise VoiceError("La synthèse vocale n'est pas installée sur ce serveur (paquet piper-tts).")
        from piper import SynthesisConfig
        buf = io.BytesIO()
        with self._lock:
            voice = self._voice(lang)
            with wave.open(buf, "wb") as wav:
                voice.synthesize_wav(text, wav, syn_config=SynthesisConfig(length_scale=1.0 / rate))
        return buf.getvalue()
