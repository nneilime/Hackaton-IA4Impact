"""Réglages lus dans l'environnement, avec un fichier .env facultatif à la racine du dépôt (ignoré par git)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EFFORTS = ("minimal", "low", "medium", "high")


@dataclass(frozen=True)
class Settings:
    model: str
    reasoning_effort: str
    host: str
    port: int


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Charge les lignes KEY=VALUE de .env sans écraser les variables déjà définies."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.removeprefix("export ").strip()
        os.environ.setdefault(key, value.strip().strip("'\""))


def from_env(host: str | None = None, port: int | None = None) -> Settings:
    load_dotenv()
    effort = os.environ.get("ASSISTANT_REASONING_EFFORT", "minimal")
    if effort not in EFFORTS:
        raise SystemExit(f"ASSISTANT_REASONING_EFFORT doit valoir {', '.join(EFFORTS)} (reçu : {effort!r}).")
    return Settings(
        model=os.environ.get("ASSISTANT_MODEL", "gemini-3.5-flash-lite"),
        reasoning_effort=effort,
        host=host or os.environ.get("ASSISTANT_HOST", "127.0.0.1"),
        port=port or int(os.environ.get("ASSISTANT_PORT", "8000")),
    )
