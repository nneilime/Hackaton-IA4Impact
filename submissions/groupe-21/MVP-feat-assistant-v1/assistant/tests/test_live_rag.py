"""Fiches RÉELLES de la base de connaissances (data/faq_corpus.jsonl), avec modèle scripté : aucun jeton consommé.

    .venv/bin/python -m unittest assistant.tests.test_live_rag -v
"""
import unittest

from assistant import agent as A
from assistant import rag_tools
from assistant.tests import fakes as F


class CorpusRead(unittest.TestCase):
    def read(self, source_id, bank):
        result = rag_tools.read(source_id, bank)
        self.assertTrue(rag_tools.is_verified(result), result.get("error"))
        return rag_tools.format_read(source_id, bank, result)[0]

    def test_withdrawal_without_card_keeps_bank_specific_conditions(self):
        ce, bp = self.read(F.RETRAIT_CE, "CE"), self.read(F.RETRAIT_BP, "BP")
        self.assertIn("24 heures", ce)
        self.assertIn("9 chiffres", ce)
        self.assertIn("5 jours", bp)
        self.assertIn("9 chiffres", bp)
        self.assertNotIn("24 heures", bp)

    def test_new_beneficiary_delay_keeps_its_condition(self):
        text = self.read(F.BENEFICIAIRE_CE, "CE")
        for fragment in ("72 heures", "Sécur’Pass", "8 chiffres", "4 chiffres"):
            self.assertIn(fragment, text)

    def test_search_finds_the_expected_fiche(self):
        self.assertIn(F.RETRAIT_CE, [r["source_id"] for r in rag_tools.search("retirer de l'argent sans carte", "CE")])
        self.assertIn(F.BENEFICIAIRE_CE, [r["source_id"] for r in rag_tools.search("ajouter un bénéficiaire", "CE")])

    def test_full_turn_with_the_real_fiche_links_to_the_official_page(self):
        llm = F.FakeLLM(F.search("retrait sans carte"), F.read(F.RETRAIT_BP),
                        F.final("answer", "Avec SM@RT’retrait, la date peut être différée jusqu’à 5 jours ; le jeton "
                                          "compte 9 chiffres.", [F.RETRAIT_BP]))
        conv = A.ConversationStore().open(None, "BP")[0]
        reply = A.Agent(llm).answer(conv, "retirer sans carte")
        self.assertEqual(reply["meta"]["kind"], "answer")
        [src] = [b for b in reply["blocks"] if b["type"] == "sources"][0]["items"]
        self.assertEqual(src["status"], "constat")
        self.assertTrue(src["url"].startswith("https://www.banquepopulaire.fr/faq-particuliers/"))


if __name__ == "__main__":
    unittest.main()
