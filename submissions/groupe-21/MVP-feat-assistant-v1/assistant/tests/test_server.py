"""Serveur HTTP : interface, flux NDJSON, erreurs simples, aucun secret ni contenu exposé (modèle SIMULÉ)."""
import base64
import hashlib
import json
import os
import re
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from assistant import agent as A
from assistant import rag_tools, server
from assistant.llm import AgentError
from assistant.tests import fakes as F

FRONT = Path(server.__file__).resolve().parents[1] / "front"
FAKE_KEY = "gsk_SECRET_DE_TEST_0123456789abcdef"


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.llm = F.FakeLLM()
        self.httpd = server.create_server(A.Agent(self.llm), "127.0.0.1", 0)
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.env = mock.patch.dict(os.environ, {"GEMINI_API_KEY": FAKE_KEY})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.httpd.shutdown()
        self.httpd.server_close()

    def request(self, path, body=None, headers=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.base + path, data=data, method="POST" if data is not None else "GET",
                                     headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                return res.status, dict(res.headers), res.read().decode()
        except urllib.error.HTTPError as e:
            with e:
                return e.code, dict(e.headers), e.read().decode()

    def chat(self, message, bank="CE", conversation_id=None):
        status, headers, body = self.request("/api/chat", {"bank": bank, "message": message, "conversation_id": conversation_id})
        events = [json.loads(line) for line in body.splitlines() if line.strip()]
        return status, headers, events, body

    # ------------------------------------------------------------------ interface

    def test_interface_is_served_with_security_headers(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn("Assistant IA", body)
        # Seul le script intégré de la page est autorisé, par son empreinte : aucun script injecté ne s'exécute.
        [script] = re.findall(r"<script>(.*?)</script>", body, re.S)
        digest = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode()
        self.assertIn(f"script-src 'self' 'sha256-{digest}'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(headers["X-Frame-Options"], "SAMEORIGIN")   # cadre de la version mobile, même origine seulement
        self.assertEqual(self.request("/favicon.svg")[0], 200)

    def test_only_listed_files_are_served(self):
        for path in ("/server.py", "/../server.py", "/%2e%2e/server.py", "/.env", "/app.js", "/CLAUDE.md",
                     "/assets/logo.webp"):
            self.assertEqual(self.request(path)[0], 404, path)

    def test_health_reports_configuration_without_secret(self):
        status, _, body = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["llm_configured"], True)
        self.assertNotIn("gsk_", body)

    # ------------------------------------------------------------------ conversation

    def test_chat_streams_real_steps_then_a_sourced_result(self):
        reader = mock.Mock(return_value=F.read_ok(F.RETRAIT_CE, F.RETRAIT_CE_MD))
        self.llm.steps = [F.search("retrait sans carte"), F.read(F.RETRAIT_CE),
                          F.final("answer", "Code à 9 chiffres, utilisable 24 heures.", [F.RETRAIT_CE])]
        with mock.patch.object(rag_tools, "read", reader):
            status, headers, events, body = self.chat("Comment retirer sans carte ?")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("application/x-ndjson"))
        types = [e["type"] for e in events]
        self.assertEqual((types[0], types[-1]), ("start", "result"))
        self.assertIn("status", types)
        result = events[-1]
        self.assertEqual(result["conversation_id"], events[0]["conversation_id"])
        sources = [b for b in result["response"]["blocks"] if b["type"] == "sources"][0]["items"]
        self.assertTrue(sources[0]["url"].startswith("https://www.caisse-epargne.fr/faq-particuliers/"))
        self.assertNotIn(FAKE_KEY, body)

    def test_errors_are_simple_and_never_expose_internal_details(self):
        self.llm.steps = [AgentError("llm_unavailable", "Le service d'IA est momentanément indisponible.")]
        _, _, events, _ = self.chat("Question ?")
        self.assertEqual(events[-1], {"type": "error", "code": "llm_unavailable",
                                      "message": "Le service d'IA est momentanément indisponible."})
        self.llm.steps = [RuntimeError(f"détail interne {FAKE_KEY}")]
        with self.assertLogs("assistant", "ERROR") as logs:
            _, _, events, body = self.chat("Autre question ?")
        self.assertEqual(events[-1]["code"], "internal")
        self.assertNotIn("détail interne", body)
        self.assertNotIn(FAKE_KEY, body)
        self.assertNotIn(FAKE_KEY, "\n".join(logs.output))

    def test_invalid_requests_are_rejected_with_a_clear_message(self):
        status, _, body = self.request("/api/chat", {"message": "   "})
        self.assertEqual(status, 400)
        self.assertIn("Votre message est vide", json.loads(body)["error"]["message"])
        self.assertEqual(self.request("/api/chat", {"bank": "CE", "message": "x" * 2001})[0], 413)
        self.assertEqual(self.request("/api/chat", raw=b"{}", headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("/api/chat", {"bank": "CE", "message": "Bonjour"},
                                      headers={"Origin": "https://autre-site.example"})[0], 403)
        self.assertEqual(self.request("/api/chat", raw=b"{pas du json")[0], 400)

    def test_reset_forgets_the_conversation(self):
        self.llm.steps = [F.final("chat", "Bonjour ! Posez votre question.")]
        _, _, events, _ = self.chat("Bonjour")
        cid = events[0]["conversation_id"]
        self.assertEqual(self.request("/api/reset", {"conversation_id": cid})[0], 200)
        self.llm.steps = [F.final("chat", "Bonjour.")]
        _, _, events, _ = self.chat("Re-bonjour", conversation_id=cid)
        self.assertEqual(events[0]["context_reset"], "expired")
        self.assertNotEqual(events[0]["conversation_id"], cid)

    def test_logs_contain_no_conversation_content(self):
        self.llm.steps = [F.final("chat", "Bonjour, que puis-je pour vous ?")]
        with self.assertLogs("assistant", "INFO") as logs:
            self.chat("Message très personnel : ma sœur vit à Lyon")      # → modèle
            self.chat("Je déménage à Lyon, comment changer d'adresse ?")  # → réponse pré-rédigée
        joined = "\n".join(logs.output)
        self.assertIn("réponse kind=chat", joined)
        self.assertIn("réponse pré-rédigée id=adresse (0 jeton)", joined)
        self.assertNotIn("Lyon", joined)
        self.assertNotIn("que puis-je", joined)


class FrontendFiles(unittest.TestCase):
    def test_no_secret_no_inline_handler_and_a_single_inline_script(self):
        text = (FRONT / "index.html").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"gsk_|AQ\.|GEMINI_API_KEY|GROQ_API_KEY|api[_-]?key")
        self.assertIsNone(re.search(r'\son[a-z]+="', text))            # gestionnaires en attribut : bloqués par la CSP
        self.assertEqual(len(re.findall(r"<script[\s>]", text)), 1)
        self.assertIn('id="viewMobile"', text)                         # sélecteur Web | Mobile
        # The RAG now explicitly supports both banks through server-side mock profiles.


if __name__ == "__main__":
    unittest.main()
