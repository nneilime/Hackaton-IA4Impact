"""Base fictive data/finance.db, outils de calcul de l'agent, réponses pré-rédigées et route /api/simulate.

Hors ligne : le modèle est SIMULÉ (aucun jeton), la base est la vraie base générée par finance/build_db.py.
"""
import json
import os
import threading
import unittest
import urllib.request
from unittest import mock

from assistant import agent as A
from assistant import scripted, server
from assistant.tests import fakes as F
from finance import engine as E


def call(name, cid="t1", **args):
    return F.calls(F.tool_call(name, cid, **args))


class Engine(unittest.TestCase):
    def test_loan_payment_matches_the_annuity_formula_and_taeg_includes_costs(self):
        r = E.simulate_loan("IMMO_FIXE", 200000, 240, age=32)
        i = r["taux_nominal"] / 100 / 12
        self.assertAlmostEqual(r["mensualite"], 200000 * i / (1 - (1 + i) ** -240), places=6)
        self.assertGreater(r["taeg"], r["taux_nominal"])         # frais, garantie et assurance obligatoire
        self.assertEqual(r["frais_dossier"], 1500)               # 1 %, plafonné à 1 500 €
        self.assertFalse(r["au_dessus_usure"])

    def test_future_start_gives_three_ordered_scenarios(self):
        r = E.simulate_loan("immo", 250000, 300, debut="2028-06")
        sc = r["scenarios"]
        self.assertEqual(set(sc), {"bas", "central", "haut"})
        self.assertLess(sc["bas"]["taux_nominal"], sc["central"]["taux_nominal"])
        self.assertLess(sc["central"]["taux_nominal"], sc["haut"]["taux_nominal"])
        self.assertIn("selon les scénarios", E.to_text(r))

    def test_consumer_credit_carries_the_legal_notice(self):
        r = E.simulate_loan("voiture", 15000, 48)
        self.assertEqual(r["produit"], "AUTO_NEUF")
        self.assertIn("Un crédit vous engage et doit être remboursé", E.to_text(r))

    def test_invalid_parameters_are_refused_with_a_readable_message(self):
        with self.assertRaisesRegex(E.FinanceError, "montant entre"):
            E.simulate_loan("PERSO", 500000, 48)
        with self.assertRaisesRegex(E.FinanceError, "Produit de crédit inconnu"):
            E.simulate_loan("bateau volant", 1000, 12)

    def test_debt_ratio_and_capacity_follow_the_35_percent_rule(self):
        cap = E.borrowing_capacity(3000, 0, 300)
        self.assertLessEqual(cap["mensualite_max"], 3000 * 0.35)
        check = E.simulate_loan("IMMO_FIXE", cap["capital_max"], 300, revenus_mensuels=3000)
        self.assertLessEqual(check["taux_endettement"], 35.0 + 0.5)

    def test_regulated_savings_respect_the_ceiling(self):
        r = E.project_savings("Livret A", 22000, 500, 3)
        self.assertLessEqual(r["scenarios"]["central"]["total_verse"], 22950)
        self.assertTrue(any("Plafond" in n for n in r["notes"]))

    def test_forecast_covers_history_and_quarters(self):
        r = E.forecast("livret a", 12)
        self.assertEqual(r["serie"], "livret_a")
        self.assertEqual(len(r["previsions"]), 4)
        self.assertEqual(r["historique"][-1]["mois"], E.ref_month())

    def test_catalogue_lists_every_topic(self):
        for topic in E.CATALOGUE_TOPICS:
            self.assertTrue(E.catalogue(topic)["elements"], topic)


class AgentWithFinanceTools(unittest.TestCase):
    def run_agent(self, *steps, text="Mensualité pour 15 000 € sur 48 mois pour une voiture ?"):
        llm = F.FakeLLM(*steps)
        conv = A.ConversationStore().open(None, "CE")[0]
        return A.Agent(llm).answer(conv, text), llm

    def test_answer_based_on_a_simulation_shows_a_result_card_and_a_fictive_source(self):
        r = E.simulate_loan("AUTO_NEUF", 15000, 48)
        text = (f"Pour 15 000 € sur 48 mois : environ **{E.eur(r['mensualite_avec_assurance'])}** par mois, "
                f"TAEG **{E.pct(r['taeg'])}**. Un crédit vous engage et doit être remboursé.")
        reply, llm = self.run_agent(call("simuler_credit", produit="AUTO_NEUF", montant=15000, duree_mois=48),
                                    F.final("answer", text))
        self.assertEqual(reply["meta"]["kind"], "answer")
        types = [b["type"] for b in reply["blocks"]]
        self.assertEqual(types[:2], ["text", "result"])
        [src] = [b for b in reply["blocks"] if b["type"] == "sources"][0]["items"]
        self.assertEqual(src["status"], "hypothese")
        self.assertIn("données fictives", src["title"])
        self.assertIn("<base_prototype", llm.tool_messages()[-1]["content"])

    def test_a_number_computed_by_the_model_is_refused(self):
        reply, llm = self.run_agent(call("simuler_credit", produit="AUTO_NEUF", montant=15000, duree_mois=48),
                                    F.final("answer", "Environ 412 € par mois."),
                                    F.final("answer", "Environ 413 € par mois."),
                                    F.final("answer", "Environ 414 € par mois."))
        self.assertEqual(reply["meta"]["kind"], "unverified")
        self.assertIn("412", llm.tool_messages(2)[-1]["content"])   # refus renvoyé au modèle

    def test_tool_call_written_as_text_is_recognised_and_executed(self):
        r = E.simulate_loan("PERSO", 8000, 36)
        written = F.text_reply(json.dumps({"produit": "PERSO", "montant": 8000, "duree_mois": 36}))
        reply, llm = self.run_agent(written, F.final("answer", f"Environ **{E.eur(r['mensualite'])}** par mois."))
        self.assertEqual(reply["meta"]["kind"], "answer")
        self.assertIn("simuler_credit", llm.tool_messages()[-1]["content"])

    def test_bad_parameters_go_back_to_the_model(self):
        reply, llm = self.run_agent(call("simuler_credit", produit="PERSO", montant=900000, duree_mois=48),
                                    F.final("clarification", "Quel montant souhaitez-vous emprunter ?",
                                            options=["10 000 €", "20 000 €"]))
        self.assertIn("Paramètres refusés par la base", llm.tool_messages()[-1]["content"])
        self.assertEqual(reply["blocks"][1]["key"], "llm")         # choix renvoyés tels quels au serveur


class Scripted(unittest.TestCase):
    def test_simple_questions_match_and_complex_ones_go_to_the_model(self):
        self.assertEqual(scripted.match("Quel est le taux du Livret A ?")["id"], "taux_livret_a")
        self.assertEqual(scripted.match("c'est quoi le TAEG")["id"], "taeg")
        for q in ("Quel sera le taux du Livret A en 2027 ?", "Je veux emprunter 200 000 € sur 20 ans",
                  "Comment vont évoluer les taux immobiliers ?", "Bonjour"):
            self.assertIsNone(scripted.match(q), q)

    def test_every_answer_fills_its_variables_from_the_database(self):
        for entry in scripted.entries():
            text = scripted.reply(entry)["blocks"][0]["text"]
            self.assertNotIn("indisponible", text, entry["id"])
            self.assertNotRegex(text, r"\{\w+:", entry["id"])
        rate = E.pct(E.value_at("livret_a", E.ref_month()))
        self.assertIn(rate, scripted.reply(scripted.match("taux livret A"))["blocks"][0]["text"])


class ServerRoutes(unittest.TestCase):
    def setUp(self):
        self.llm = F.FakeLLM()
        self.httpd = server.create_server(A.Agent(self.llm), "127.0.0.1", 0)
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.env = mock.patch.dict(os.environ, {"GEMINI_API_KEY": "gemini_test"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.httpd.shutdown()
        self.httpd.server_close()

    def post(self, path, body):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                return res.status, res.read().decode()
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read().decode()

    def test_simple_question_is_answered_without_calling_the_model(self):
        status, body = self.post("/api/chat", {"message": "C'est quoi le TAEG ?"})
        self.assertEqual(status, 200)
        result = [json.loads(l) for l in body.splitlines()][-1]
        self.assertEqual(result["response"]["meta"]["model"], "script")
        self.assertEqual(result["response"]["meta"]["usage"], {"input_tokens": 0, "output_tokens": 0})
        self.assertEqual(self.llm.calls, [])

    def test_simulate_route_returns_a_result_card(self):
        status, body = self.post("/api/simulate", {"produit": "IMMO_FIXE", "montant": 200000, "duree_mois": 240})
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["result"]["type"], "result")
        self.assertTrue(data["result"]["big"].startswith("≈"))
        status, body = self.post("/api/simulate", {"produit": "IMMO_FIXE", "montant": 10, "duree_mois": 240})
        self.assertEqual(status, 400)
        self.assertIn("montant entre", json.loads(body)["error"]["message"])


if __name__ == "__main__":
    unittest.main()


class VoiceRoutes(ServerRoutes):
    """Voix côté serveur : synthèse Piper locale réelle, transcription simulée (aucun appel à Gemini)."""

    def raw(self, path, data, ctype):
        req = urllib.request.Request(self.base + path, data=data, method="POST", headers={"Content-Type": ctype})
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                return res.status, res.headers.get("Content-Type"), res.read()
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.headers.get("Content-Type"), e.read()

    @unittest.skipUnless(server.voice.Speaker().available and (server.voice.VOICES_DIR / "fr_FR-siwis-medium.onnx").exists(),
                         "voix Piper française absente")
    def test_local_voice_takes_over_when_the_neural_voice_is_unreachable(self):
        with mock.patch.object(server.voice.Speaker, "_edge", side_effect=OSError("hors ligne")):
            status, ctype, body = self.raw("/api/tts", json.dumps({"text": "Bonjour, je suis l'assistant.", "lang": "fr"}).encode(),
                                           "application/json")
        self.assertEqual((status, ctype), (200, "audio/wav"))
        self.assertEqual(body[:4], b"RIFF")

    def test_local_voice_is_used_by_default_and_punctuation_alone_is_refused(self):
        with mock.patch.object(server.voice.Speaker, "_piper", return_value=b"RIFF-wav") as piper, \
                mock.patch.object(server.voice.Speaker, "_edge") as edge:
            status, ctype, body = self.raw("/api/tts", json.dumps({"text": "Bonjour.", "lang": "fr", "rate": 1.25}).encode(),
                                           "application/json")
        self.assertEqual((status, ctype, body), (200, "audio/wav", b"RIFF-wav"))
        self.assertEqual(piper.call_args.args, ("Bonjour.", "fr", 1.25))
        edge.assert_not_called()   # voix Microsoft refusée (403) : plus appelée par défaut
        self.assertEqual(self.raw("/api/tts", json.dumps({"text": " ; … "}).encode(), "application/json")[0], 400)

    def test_transcription_goes_through_the_model_client_and_rejects_non_audio(self):
        with mock.patch.object(server.voice, "transcribe", return_value="quel est le taux du livret A") as t:
            status, _, body = self.raw("/api/transcribe?lang=fr", b"\x1aE\xdf\xa3fake", "audio/webm")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["text"], "quel est le taux du livret A")
        self.assertEqual(t.call_args.args[1:], ("micro.webm", "fr"))
        self.assertEqual(self.raw("/api/transcribe", b"x", "text/plain")[0], 415)

    def test_page_allows_audio_from_blob_urls(self):
        with urllib.request.urlopen(self.base + "/", timeout=10) as res:
            self.assertIn("media-src 'self' blob:", res.headers["Content-Security-Policy"])


class FrontDefaults(unittest.TestCase):
    def test_french_is_the_default_language_and_voice_has_a_server_fallback(self):
        html = (server.FRONT / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("navigator.language", html)
        self.assertIn("this.prefs.langChosen && LOCALES[this.prefs.lang] ? this.prefs.lang : 'fr'", html)
        self.assertIn("get canListen()", html)
        self.assertIn("/api/transcribe", html)
