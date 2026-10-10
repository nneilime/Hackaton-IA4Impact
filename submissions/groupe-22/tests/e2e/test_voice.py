"""Voice, for real: French speech made with OpenAI's text-to-speech is played into
Chromium's fake microphone, and the page calls the Realtime API over WebRTC, as on a
phone. Checks the call connects, the question is heard (transcript), and the tools the
server ran are those of the session: a visitor is offered the login, a customer hears
the balance. uv run pytest tests/e2e/test_voice.py -m live"""

import os
import re
import tempfile
import wave
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv
from helpers import chromium_path, login, shot
from playwright.sync_api import expect

pytestmark = pytest.mark.live
SLOW = 60_000


def speech(text):
    """A WAV: 4 s of silence (the call connects), the sentence, then 30 s of silence."""
    path = Path(tempfile.gettempdir()) / f"compass-voice-{abs(hash(text))}.wav"
    if path.exists():
        return path
    load_dotenv(Path(__file__).parents[2] / ".env", override=True)
    r = httpx.post(
        "https://api.openai.com/v1/audio/speech",
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        # pcm: raw 24 kHz, 16-bit, mono (the wav format's header has no length)
        json={"model": "gpt-4o-mini-tts", "voice": "alloy", "input": text, "response_format": "pcm"},
        timeout=60,
    )
    r.raise_for_status()
    rate = 24000
    silence = lambda seconds: b"\0\0" * int(rate * seconds)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(silence(4) + r.content + silence(30))
    return path


class VoiceBrowser:
    """Its own Chromium (the fake mic's file is set when a browser starts), launched by
    the session's Playwright."""

    def __init__(self, browser, base_url, text):
        self.browser_type, self.wav, self.base_url = browser.browser_type, speech(text), base_url

    def __enter__(self):
        self.browser = self.browser_type.launch(
            executable_path=chromium_path(),
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                f"--use-file-for-fake-audio-capture={self.wav}%noloop",
                "--autoplay-policy=no-user-gesture-required",
            ],
        )
        context = self.browser.new_context(base_url=self.base_url, viewport={"width": 390, "height": 844}, permissions=["microphone"])
        return context.new_page()

    def __exit__(self, *exc):
        self.browser.close()


def test_visitor_voice_balance_is_refused(browser, base_url):
    with VoiceBrowser(browser, base_url, "Bonjour. Quel est le solde de mon compte ?") as page:
        page.goto("/")
        page.get_by_role("button", name="Parler à Compass (conversation vocale)").click()
        call = page.get_by_label("Conversation vocale avec Compass")
        expect(call).to_be_visible()
        expect(call.get_by_role("button", name="Raccrocher").first).to_be_visible()
        expect(call.get_by_text("Connexion proposée")).to_be_visible(timeout=SLOW)
        expect(call.get_by_role("log", name="Transcription")).to_contain_text(re.compile("solde", re.IGNORECASE))
        expect(call).not_to_contain_text("1 245")
        shot(page, "voice-visitor")
        call.get_by_role("button", name="Raccrocher").first.click()
        expect(page.get_by_label("Conversation vocale avec Compass")).to_have_count(0)
        assert page.evaluate("navigator.mediaDevices !== undefined")


def test_customer_voice_hears_the_balance(browser, base_url):
    with VoiceBrowser(browser, base_url, "Bonjour. Quel est mon solde ?") as page:
        page.goto("/")
        login(page)
        expect(page.get_by_role("heading", name="Bonjour Camille")).to_be_visible()
        page.get_by_role("button", name="Parler à Compass (conversation vocale)").click()
        call = page.get_by_label("Conversation vocale avec Compass")
        expect(call.get_by_text("Soldes consultés")).to_be_visible(timeout=SLOW)
        expect(call.get_by_role("article", name="Vos soldes")).to_contain_text("1 245,80")
        page.wait_for_timeout(4000)  # the spoken answer's transcript
        shot(page, "voice-customer")
        print("\n[voice transcript]", call.get_by_role("log", name="Transcription").inner_text())
        # Voice to text: the written chat picks up where the call stopped.
        call.get_by_role("button", name="Raccrocher et revenir à l'écrit").click()
        sheet = page.get_by_role("dialog", name="Compass, assistant bancaire")
        expect(sheet.get_by_text("En ligne", exact=True)).to_be_visible(timeout=SLOW)
        expect(sheet.get_by_role("button", name="Envoyer")).to_be_visible(timeout=SLOW)  # resumed
        log = sheet.get_by_role("log", name="Conversation avec Compass")
        expect(log.get_by_role("alert")).to_have_count(0)  # the Realtime API took the context
        page.wait_for_timeout(500)
        print("[text after voice]", log.inner_text()[-400:])
        shot(page, "voice-to-text")
