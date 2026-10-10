"""Browser tests: the built page (web/dist) served by server.py on a free port, with its
own database, in Chromium (Playwright). Run: uv run pytest tests/e2e (after
cd web && npm run build). CHROMIUM=/path/to/chrome to pick the browser; by default the
system's /usr/bin/chromium if Playwright's own isn't installed.

The deterministic tests don't need OpenAI. The ones marked live talk to the real model
(OPENAI_API_KEY in .env): uv run pytest tests/e2e -m live."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest
from helpers import chromium_path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parents[2]
# Text only a logged-in customer may ever see: if it shows for a visitor, even for a
# frame before a redirect, it's a leak (recorded by LEAK_WATCH below).
PRIVATE_TEXT = ["1 245,80", "8 650,00", "Camille Martin", "4821", "Paiement inconnu"]

LEAK_WATCH = """
window.__leaks = [];
const PRIVATE = __PRIVATE__;
new MutationObserver(() => {
  const text = document.body ? document.body.innerText : "";
  for (const p of PRIVATE) if (text.includes(p)) window.__leaks.push(p);
}).observe(document, { subtree: true, childList: true, characterData: true });
""".replace("__PRIVATE__", json.dumps(PRIVATE_TEXT))


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def base_url():
    if url := os.environ.get("BASE_URL"):
        yield url
        return
    assert (ROOT / "web" / "dist" / "index.html").exists(), "cd web && npm run build"
    port = _free_port()
    tmp = Path(tempfile.mkdtemp(prefix="compass-e2e-"))
    env = {**os.environ, "DB_PATH": str(tmp / "e2e.db"), "RECAPS_DIR": str(tmp / "recaps")}
    if env.get("OPENAI_API_KEY") == "sk-test-not-used":  # tests/conftest.py's: the
        del env["OPENAI_API_KEY"]  # server reads the real one from .env
    with open(tmp / "server.log", "w") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server:app", "--port", str(port)],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        url = f"http://127.0.0.1:{port}"
        for _ in range(60):
            try:
                if httpx.get(f"{url}/api/health").status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        else:
            server.kill()
            raise RuntimeError((tmp / "server.log").read_text())
        print(f"\n[e2e] server log: {tmp / 'server.log'}")
        yield url
        server.terminate()
        server.wait(10)


@pytest.fixture(scope="session")
def browser():
    args = [
        # Voice tests: a fake mic, fed with a WAV when FAKE_MIC_WAV is set.
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        "--autoplay-policy=no-user-gesture-required",
    ]
    if wav := os.environ.get("FAKE_MIC_WAV"):
        args.append(f"--use-file-for-fake-audio-capture={wav}")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=chromium_path(), args=args)
        yield b
        b.close()


@pytest.fixture
def page(browser, base_url):
    """A fresh browser profile (no cookie), phone-sized, watching for private text."""
    context = browser.new_context(base_url=base_url, viewport={"width": 390, "height": 844}, locale="fr-FR")
    context.add_init_script(LEAK_WATCH)
    p = context.new_page()
    p.errors = []
    p.on("pageerror", lambda e: p.errors.append(str(e)))
    # A refused request (wrong demo code, a visitor asking for a private API) is
    # logged by the browser itself: expected, not a page error.
    expected = "the server responded with a status of 401"
    p.on("console", lambda m: m.type == "error" and expected not in m.text and p.errors.append(m.text))
    yield p
    context.close()
