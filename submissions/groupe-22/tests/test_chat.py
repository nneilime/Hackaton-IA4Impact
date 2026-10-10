"""The written chat's relay (WebSocket /api/chat), with a scripted fake of the Realtime
API instead of OpenAI: deterministic, no network. It checks what the server does around
the model, not the model (see live_smoke.py for that)."""

import asyncio
import json
import threading
from contextlib import contextmanager
from typing import ClassVar

import pytest
from api_helpers import ORIGIN, login
from starlette.websockets import WebSocketDisconnect

import server


class FakeRealtime:
    """Answers each user message by calling the tool named in it ("call get_accounts"),
    then with a text answer once the tool's output is back."""

    instances: ClassVar[list] = []

    def __init__(self):
        self.sent = []
        self.events = asyncio.Queue()
        FakeRealtime.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def send(self, message):
        event = json.loads(message)
        self.sent.append(event)
        if event["type"] == "conversation.item.create":
            item = {**event["item"], "id": f"item_{len(self.sent)}"}
            await self.events.put({"type": "conversation.item.added", "item": item})
            if item["type"] == "function_call_output":
                await self.events.put({"type": "conversation.item.done", "item": item})
        elif event["type"] == "response.create":
            last = next((e["item"] for e in reversed(self.sent) if e["type"] == "conversation.item.create"), None)
            if last and last["type"] == "message" and last["role"] == "user":
                tool = last["content"][0]["text"].removeprefix("call ")
                output = [{"type": "function_call", "call_id": f"c{len(self.sent)}", "name": tool, "arguments": "{}"}]
            else:
                output = [{"type": "message", "role": "assistant", "content": []}]
            await self.events.put({"type": "response.done", "response": {"status": "completed", "output": output}})

    def __aiter__(self):
        return self

    async def __anext__(self):
        return json.dumps(await self.events.get())

    def tool_output(self):
        outputs = [e["item"]["output"] for e in self.sent if e["type"] == "conversation.item.create" and e["item"]["type"] == "function_call_output"]
        return json.loads(outputs[-1]) if outputs else None


ENDED = threading.Event()  # the server's chat handler has returned


@pytest.fixture(autouse=True)
def fake_openai(monkeypatch):
    FakeRealtime.instances.clear()
    monkeypatch.setattr(server.websockets, "connect", lambda *a, **k: FakeRealtime())
    ENDED.clear()

    def watch(*args, **kwargs):
        if args and args[0] == "[chat] ended":
            ENDED.set()

    monkeypatch.setattr(server, "print", watch, raising=False)


@contextmanager
def chat_page(client):
    """The page's chat socket. Closed by the page, then waits for the server to finish:
    the test client cancels whatever still runs when it leaves."""
    with client.websocket_connect("/api/chat", headers=ORIGIN) as page:
        yield page
        page.close()
        assert ENDED.wait(5), "the chat handler didn't end"


def finish_turn(page):
    """Reads the page's events until the answer after the tool: the server is idle when
    the test closes the socket. Returns the tool's output."""
    output = None
    for _ in range(30):
        event = json.loads(page.receive_text())
        if event["type"] == "conversation.item.done":
            output = json.loads(event["item"]["output"])
        elif (
            event["type"] == "response.done"
            and output is not None
            and not any(o["type"] == "function_call" for o in event["response"]["output"])
        ):
            return output
    raise AssertionError("no tool output")


def ask(client, text):
    with chat_page(client) as page:
        page.send_text(json.dumps({"type": "message", "text": text}))
        return finish_turn(page)


def test_visitor_chat_gets_only_public_tools(client):
    output = ask(client, "call get_accounts")
    assert "Réservé aux clients connectés" in output["error"]
    session_update = FakeRealtime.instances[-1].sent[0]["session"]
    names = {t["name"] for t in session_update["tools"]}
    assert "get_accounts" not in names and "offer_login" in names
    assert "n'est pas connecté" in session_update["instructions"]


def test_customer_chat_reads_the_customers_balance(client):
    login(client)
    output = ask(client, "call get_accounts")
    assert output["accounts"][0]["balance"] == "1 245,80 euros"
    assert "Camille Martin" in FakeRealtime.instances[-1].sent[0]["session"]["instructions"]


def test_chat_after_logout_is_a_visitors(client):
    login(client)
    client.post("/api/auth/logout", json={}, headers=ORIGIN)
    assert "Réservé aux clients connectés" in ask(client, "call get_accounts")["error"]


def test_chat_from_another_site_is_refused(client):
    evil = {"origin": "https://evil.example"}
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/api/chat", headers=evil) as page:
        page.receive_text()


def test_page_cannot_change_the_session(client):
    with chat_page(client) as page:
        page.send_text(json.dumps({"type": "session.update", "session": {"tools": [{"name": "get_accounts"}]}}))
        page.send_text(json.dumps({"type": "message", "text": "call offer_login"}))
        finish_turn(page)
    sent = FakeRealtime.instances[-1].sent
    assert [e["type"] for e in sent].count("session.update") == 1  # only the server's


def test_card_numbers_typed_by_mistake_never_reach_openai(client):
    with chat_page(client) as page:
        page.send_text(json.dumps({"type": "message", "text": "call get_procedure 4970 1234 5678 9012"}))
        finish_turn(page)
    texts = [e["item"]["content"][0]["text"] for e in FakeRealtime.instances[-1].sent if e["type"] == "conversation.item.create" and e["item"]["type"] == "message"]
    assert all("4970" not in t for t in texts)


def test_simple_mode_switch_updates_the_instructions(client):
    with chat_page(client) as page:
        page.send_text(json.dumps({"type": "settings", "simple": True}))
        page.send_text(json.dumps({"type": "message", "text": "call offer_login"}))
        finish_turn(page)
    updates = [e for e in FakeRealtime.instances[-1].sent if e["type"] == "session.update"]
    assert updates[-1]["session"]["instructions"].startswith("EXPLICATIONS SIMPLES")


def test_voice_transcript_carries_over_to_the_chat(client):
    session = server.bank_store.get_session(client.cookies[server.COOKIE])
    server.remember(session, "Client", "Je voudrais récupérer l'accès à mon compte")
    with chat_page(client) as page:
        page.send_text(json.dumps({"type": "message", "text": "call offer_login"}))
        finish_turn(page)
    system = [e for e in FakeRealtime.instances[-1].sent if e["type"] == "conversation.item.create" and e["item"].get("role") == "system"]
    assert "récupérer l'accès" in system[0]["item"]["content"][0]["text"]


def test_openai_unreachable_is_said_to_the_page(client, monkeypatch):
    def refused(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr(server.websockets, "connect", refused)
    with chat_page(client) as page:
        event = json.loads(page.receive_text())
    assert event["type"] == "error" and event["error"]["code"] == "unavailable"
    assert "indisponible" in event["error"]["message"]
