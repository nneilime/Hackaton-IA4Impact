"""Tests never call the real LLM (no network, no quota): the deterministic fallbacks are tested instead."""
import pytest


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    import dispatch.copilot.client as client
    import dispatch.copilot.explain as explain
    import dispatch.copilot.translate as translate
    for mod in (client, explain, translate):
        monkeypatch.setattr(mod, "llm_available", lambda: False)
