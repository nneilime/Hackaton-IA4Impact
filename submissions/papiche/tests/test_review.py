# SPDX-License-Identifier: AGPL-3.0-or-later
"""La relecture humaine suit les mêmes règles que l'IA : une valeur sans preuve dans la source est refusée.

Lancer : python -m unittest discover -s tests -v   (aucun service externe requis : Qdrant et fichiers sont simulés)
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from veille_reglementaire import review
from veille_reglementaire.sources import Passage

TEXT = ("Produit: LALSTOP G46 WG (AMM 2230771) | Usage: Vigne*Trt Part.Aer.*Pourriture grise | "
        "Dose retenue: 0.5 kg/ha | Nombre max d'applications: 4")
PASSAGE = Passage(passage_id="t:1", source_id="ephy", country="FR", region="Europe", product="LALSTOP G46 WG", reg_number="1",
                  holder="X", status_original="AUTORISE", status="autorise", text=TEXT, source_url="https://exemple.invalide/fictif",
                  dataset_url="", collected_at="2026-10-10")
TRACE = {"passage": {"passage_id": "t:1"}, "attempts": [{"n": 1, "model": "fake", "raw": "{}", "error": "preuve non retrouvée"}],
         "outcome": "hitl", "record": None, "critic": None}
GOOD = {"crop_original": "Vigne", "target_original": "Pourriture grise", "dose_original": "0.5 kg/ha", "dose_value": 0.5,
        "dose_unit": "kg/ha", "max_applications": 4, "quote": "Dose retenue: 0.5 kg/ha"}


class Relecture(unittest.TestCase):
    def setUp(self):
        self.get_passage, review.qdrant_store.get_passage = review.qdrant_store.get_passage, lambda _id: PASSAGE

    def tearDown(self):
        review.qdrant_store.get_passage = self.get_passage

    def test_correction_valide_donne_le_statut_humain(self):
        record = review.build_human_record(TRACE, GOOD, "Camille")
        self.assertEqual(record["validation_status"], "valide_humain")
        self.assertEqual(record["dose_value"], 0.5)
        self.assertIn("Camille", record["model"])

    def test_une_dose_inventee_est_refusee_meme_par_un_humain(self):
        fabricated = dict(GOOD, dose_original="1.2 kg/ha", dose_value=1.2, quote="Dose retenue: 1.2 kg/ha")
        with self.assertRaisesRegex(ValueError, "preuve non retrouvée"):
            review.build_human_record(TRACE, fabricated, "Camille")

    def test_champ_inconnu_refuse(self):
        with self.assertRaises(ValueError):
            review.build_human_record(TRACE, dict(GOOD, invente=True), "Camille")

    def test_ecarter_exige_une_raison(self):
        with self.assertRaisesRegex(ValueError, "raison"):
            review.decide("t:1", "dismissed", "Camille", reason="  ")

    def test_decision_enregistree_puis_relue(self):
        with tempfile.TemporaryDirectory() as folder:
            old = (review.CORRECTIONS_FILE, review.apply_decision, review.config.PROCESSED)
            review.CORRECTIONS_FILE = Path(folder) / "corrections.jsonl"
            review.apply_decision = lambda entry: None            # l'écriture des enregistrements est testée ailleurs
            try:
                review.decide("t:1", "dismissed", "Camille", reason="étiquette sans dose")
                self.assertEqual(review.load_decisions()["t:1"]["action"], "dismissed")
                review.decide("t:1", "dismissed", "Léo", reason="doublon")      # la dernière décision l'emporte
                self.assertEqual(review.load_decisions()["t:1"]["author"], "Léo")
            finally:
                review.CORRECTIONS_FILE, review.apply_decision, _ = old


if __name__ == "__main__":
    unittest.main()
