"""Garde-fou des secrets, mise en forme des sources et adaptateur Gemini (hors ligne, sans jeton)."""
import json
import unittest
from unittest import mock

import openai
import httpx

from assistant import guard, llm, rag_tools
from assistant.tests import fakes as F


class Guard(unittest.TestCase):
    def test_secrets_are_detected(self):
        for text in ["Mon code Sécur'Pass est 4821", "voici le code reçu par SMS : 12345678",
                     "4970 1234 5678 9012", "FR76 3000 6000 0112 3456 7890 189",
                     "mon mot de passe est Soleil2024!", "1234 c'est mon code", "mon identifiant 0123456789"]:
            self.assertTrue(guard.contains_secret(text), text)

    def test_ordinary_questions_pass(self):
        for text in ["J'ai perdu mon code", "Mon code à 4 chiffres ne marche plus", "mon code postal est 31000",
                     "Quel est le plafond de 3000 € de ma carte ?", "Appeler le 09 69 36 45 45 ?",
                     "Mon mot de passe est bloqué", "virement de 1500 euros le 10/10/2026"]:
            self.assertFalse(guard.contains_secret(text), text)


class RagFormatting(unittest.TestCase):
    def test_read_fiche_is_wrapped_as_evidence_with_its_metadata(self):
        text, failed = rag_tools.format_read(F.RETRAIT_CE, "CE", F.read_ok(F.RETRAIT_CE, F.RETRAIT_CE_MD, videos=[{"title": "x"}]))
        self.assertFalse(failed)
        self.assertIn("Mise à jour de la page : 11/09/2026", text)
        self.assertIn("1 vidéo(s) non lue(s)", text)
        self.assertTrue(text.rstrip().endswith("</source_officielle>"))

    def test_failed_read_exposes_no_content_and_reader_link_stays_official(self):
        text, failed = rag_tools.format_read(F.RETRAIT_CE, "CE", F.read_error(F.RETRAIT_CE))
        self.assertTrue(failed)
        self.assertIn("ÉCHEC de lecture", text)
        candidate = {"question": "Comment retirer ?", "source_url": F.record(F.RETRAIT_CE)["url"]}
        shown = rag_tools.source_display(F.RETRAIT_CE, "CE", F.read_error(F.RETRAIT_CE), candidate)
        self.assertEqual((shown["verified"], shown["url"]), (False, F.record(F.RETRAIT_CE)["url"]))

    def test_link_outside_the_official_faq_is_never_displayed(self):
        result = F.read_ok(F.RETRAIT_CE, F.RETRAIT_CE_MD, url="https://evil.example/faq-particuliers/x/")
        self.assertIsNone(rag_tools.source_display(F.RETRAIT_CE, "CE", result, None))

    def test_empty_or_failed_read_is_not_considered_verified(self):
        self.assertFalse(rag_tools.is_verified(F.read_empty(F.RETRAIT_CE)))
        self.assertFalse(rag_tools.is_verified(F.read_error(F.RETRAIT_CE)))


def _status_error(cls, status, body=None, headers=None):
    response = httpx.Response(status, headers=headers or {}, request=httpx.Request("POST", "https://generativelanguage.googleapis.com/x"))
    return cls("erreur simulée", response=response, body=body)


class GeminiAdapter(unittest.TestCase):
    def make(self, *outcomes):
        client = mock.Mock(api_key="gemini_test")
        client.chat.completions.create.side_effect = list(outcomes)
        return llm.ChatLLM(client, "gemini-3.8-flash"), client

    def ok(self):
        message = F.calls(F.tool_call("search_faq", query="x"))
        return mock.Mock(choices=[mock.Mock(message=message, finish_reason="tool_calls")], usage=mock.Mock(prompt_tokens=300, completion_tokens=21))

    def test_rate_limit_wait_is_announced_then_retried(self):
        adapter, client = self.make(_status_error(openai.RateLimitError, 429, headers={"retry-after": "2"}), self.ok())
        waits = []
        with mock.patch.object(llm.time, "sleep") as sleep:
            message, finish, tokens = adapter.chat([], [], on_wait=waits.append)
        self.assertEqual((waits, tokens), ([2], (300, 21)))
        sleep.assert_called_once_with(2)
        params = client.chat.completions.create.call_args.kwargs
        self.assertEqual((params["tool_choice"], params["reasoning_effort"]), ("required", "medium"))

    def test_long_rate_limit_is_reported_simply(self):
        adapter, _ = self.make(_status_error(openai.RateLimitError, 429, headers={"retry-after": "3600"}))
        with self.assertRaises(llm.AgentError) as ctx, self.assertLogs("assistant", "WARNING"):
            adapter.chat([], [])
        self.assertEqual(ctx.exception.code, "llm_busy")

    def test_exhausted_daily_quota_switches_to_the_fallback_model(self):
        client = mock.Mock(api_key="gemini_test")
        client.chat.completions.create.side_effect = [
            _status_error(openai.RateLimitError, 429, headers={"retry-after": "3600"}), self.ok(), self.ok()]
        adapter = llm.ChatLLM(client, "gemini-3.8-flash", fallback_model="gemini-3.7-flash")
        with self.assertLogs("assistant", "WARNING"):
            adapter.chat([], [])
        adapter.chat([], [])   # tant que le quota principal est épuisé, le secours est utilisé d'emblée
        models = [c.kwargs["model"] for c in client.chat.completions.create.call_args_list]
        self.assertEqual(models, ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.7-flash"])
        self.assertEqual(adapter.last_model, "gemini-3.7-flash")

    def test_overloaded_primary_model_hands_over_to_the_fallback_model(self):
        client = mock.Mock(api_key="gemini_test")
        client.chat.completions.create.side_effect = [
            _status_error(openai.InternalServerError, 503), _status_error(openai.InternalServerError, 503), self.ok(), self.ok()]
        adapter = llm.ChatLLM(client, "gemini-3.8-flash", fallback_model="gemini-3.7-flash")
        with mock.patch.object(llm.time, "sleep"), self.assertLogs("assistant", "WARNING"):
            adapter.chat([], [])
        adapter.chat([], [])   # le principal saturé est laissé de côté quelques minutes
        models = [c.kwargs["model"] for c in client.chat.completions.create.call_args_list]
        self.assertEqual(models, ["gemini-3.8-flash", "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.7-flash"])

    def test_text_generation_instead_of_tool_call_is_returned_for_checking(self):
        generation = json.dumps({"kind": "answer", "text": "…", "options": [], "source_ids": []})
        error = _status_error(openai.BadRequestError, 400, body={"error": {"code": "tool_use_failed", "failed_generation": generation}})
        adapter, _ = self.make(error)
        message, finish, _ = adapter.chat([], [])
        self.assertEqual((message.content, message.tool_calls, finish), (generation, None, "stop"))

    def test_missing_key_starts_unconfigured_instead_of_crashing(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            adapter = llm.ChatLLM.from_env("gemini-3.8-flash", "medium")
        self.assertFalse(adapter.configured)
        from assistant.agent import Agent, ConversationStore
        with self.assertRaises(llm.AgentError) as ctx:
            Agent(adapter).answer(ConversationStore().open(None, "CE")[0], "Bonjour")
        self.assertEqual(ctx.exception.code, "llm_not_configured")

    def test_authentication_error_becomes_a_configuration_message(self):
        adapter, _ = self.make(_status_error(openai.AuthenticationError, 401))
        with self.assertRaises(llm.AgentError) as ctx, self.assertLogs("assistant", "WARNING"):
            adapter.chat([], [])
        self.assertEqual(ctx.exception.code, "llm_config")
        self.assertNotIn("gsk_", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
