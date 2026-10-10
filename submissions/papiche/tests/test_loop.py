# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests de la boucle de contrôle avec un FAUX modèle : on prouve que le code rejette les erreurs du LLM.

Lancer : python -m unittest discover -s tests -v   (aucun Ollama ni Qdrant requis)
"""
import json, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from veille_reglementaire import extraction_loop, llm, sister_products
from veille_reglementaire.models import Extraction, normalize_dose
from veille_reglementaire.sources import Passage

TEXT = ("Produit: LALSTOP G46 WG (AMM 2230771) | Usage: Vigne*Trt Part.Aer.*Pourriture grise | "
        "Dose retenue: 0.5 kg/ha | Nombre max d'applications: 4")
P = Passage(passage_id="t:1", source_id="ephy", country="FR", region="Europe", product="LALSTOP G46 WG", reg_number="1",
            holder="X", status_original="AUTORISE", status="autorise", text=TEXT, source_url="https://exemple.invalide/fictif",
            dataset_url="", collected_at="2026-10-10")

GOOD = {"crop_original": "Vigne", "target_original": "Pourriture grise", "dose_original": "0.5 kg/ha", "dose_value": 0.5,
        "dose_unit": "kg/ha", "max_applications": 4, "restrictions": [], "quote": "Dose retenue: 0.5 kg/ha"}


def fake(*answers):
    """Remplace chat_json par une suite de réponses scriptées ; l'état est vérifiable via .calls."""
    it = iter(answers)
    calls = []

    def chat_json(system, user, **kw):
        calls.append(user)
        return {"text": next(it), "cached": False, "backend": "fake", "model": "fake"}
    chat_json.calls = calls
    return chat_json


class Loop(unittest.TestCase):
    def run_loop(self, *answers):
        llm_fake = fake(*answers)
        old = llm.chat_json
        llm.chat_json = llm_fake
        try:
            return extraction_loop.extract_passage(P, use_llm_critic=False), llm_fake
        finally:
            llm.chat_json = old

    def test_accepte_du_premier_coup(self):
        tr, _ = self.run_loop(json.dumps(GOOD))
        self.assertEqual(tr["outcome"], "accepted")
        self.assertEqual(tr["record"]["dose_norm_value"], 0.5)
        self.assertEqual(tr["record"]["crop_eppo"], "VITVI")

    def test_pydantic_rejette_puis_corrige(self):
        bad = dict(GOOD, dose_value="0,5 kg/ha")            # texte au lieu d'un nombre
        tr, f = self.run_loop(json.dumps(bad), json.dumps(GOOD))
        self.assertEqual(len(tr["attempts"]), 2)
        self.assertIn("dose_value", tr["attempts"][0]["error"])
        self.assertIn("REFUSÉE", f.calls[1])                  # l'erreur exacte est renvoyée au modèle
        self.assertEqual(tr["outcome"], "accepted")

    def test_citation_inventee_est_rejetee(self):
        fab = dict(GOOD, dose_original="1.2 kg/ha", dose_value=1.2, quote="Dose retenue: 1.2 kg/ha")
        tr, _ = self.run_loop(json.dumps(fab), json.dumps(GOOD))
        self.assertFalse(tr["attempts"][0]["accepted"])
        self.assertIn("preuve non retrouvée", tr["attempts"][0]["error"])
        self.assertEqual(tr["record"]["dose_value"], 0.5)

    def test_trois_echecs_arbitrage_humain(self):
        fab = json.dumps(dict(GOOD, dose_original="9 kg/ha", dose_value=9, quote="Dose retenue: 9 kg/ha"))
        tr, _ = self.run_loop(fab, fab, fab)
        self.assertEqual(tr["outcome"], "hitl")
        self.assertIsNone(tr["record"])                       # rien n'est publié

    def test_json_invalide(self):
        tr, _ = self.run_loop("pas du json", json.dumps(GOOD))
        self.assertIn("JSON invalide", tr["attempts"][0]["error"])


class Contrat(unittest.TestCase):
    def test_dose_absente_de_loriginal(self):
        with self.assertRaises(Exception):
            Extraction(dose_original="0.5 kg/ha", dose_value=0.8, dose_unit="kg/ha", quote="Dose retenue: 0.5 kg/ha")

    def test_champ_inconnu_interdit(self):
        with self.assertRaises(Exception):
            Extraction(quote="Dose retenue: 0.5", invente=True)

    def test_unites_us(self):
        self.assertEqual(normalize_dose(8, "fl oz/acre"), (0.5846, "L/ha"))
        self.assertEqual(normalize_dose(500, "g/m3"), (None, None))   # non convertible : jamais deviné


class Soeurs(unittest.TestCase):
    def test_g46_prestop(self):
        meta = [{"product": "LALSTOP G46 WG", "country": "FR", "holder": "DANSTAR FERMENT AG",
                 "ai": "Clonostachys rosea souche J1446 (Clonostachys rosea, souche J1446) 1000000000 UFC/g"},
                {"product": "PRESTOP WG", "country": "CA", "holder": "DANSTAR FERMENT AG",
                 "ai": "CLONOSTACHYS ROSEA STRAIN J1446"}]
        r = sister_products.detect(meta)
        self.assertEqual(len(r), 1)
        self.assertGreaterEqual(r[0]["confidence"], 0.8)
        self.assertEqual(r[0]["status"], "a_confirmer")


if __name__ == "__main__":
    unittest.main()
