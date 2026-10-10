"""Helpers for the browser tests."""

import os
import tempfile
from pathlib import Path

SHOTS = Path(os.environ.get("SHOTS_DIR", tempfile.gettempdir())) / "compass-shots"


def chromium_path():
    """CHROMIUM, or the system's Chromium when Playwright's own isn't installed."""
    if path := os.environ.get("CHROMIUM"):
        return path
    return "/usr/bin/chromium" if Path("/usr/bin/chromium").exists() else None


def shot(page, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=False)


def login(page, code="compass", profile="Camille Martin"):
    page.get_by_role("button", name="Connexion démo").first.click()
    dialog = page.get_by_role("dialog", name="Connexion démo")
    dialog.get_by_label(profile).check()
    dialog.get_by_label("Code de démonstration").fill(code)
    dialog.get_by_role("button", name="Se connecter (démo)").click()
    return dialog
