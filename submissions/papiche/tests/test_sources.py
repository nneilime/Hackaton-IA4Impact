# SPDX-License-Identifier: AGPL-3.0-or-later
"""Une nouvelle source se branche sans toucher au reste du code : découverte automatique et squelette valide.

Lancer : python -m unittest discover -s tests -v   (aucun service externe requis)
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from veille_reglementaire import source_scaffold
from veille_reglementaire.sources import discover_sources


class Sources(unittest.TestCase):
    def test_les_trois_sources_actuelles_sont_decouvertes(self):
        self.assertTrue({"ephy", "pmra", "epa"} <= set(discover_sources()))

    def test_le_modele_n_est_pas_une_source(self):
        self.assertNotIn("__ID__", discover_sources())

    def test_une_nouvelle_source_est_decouverte_et_valide(self):
        created = Path(source_scaffold.create_source("essai_test", "Essai", "ZZ", "Pays d'essai", "Région", "CSV", "fr"))
        try:
            sources = discover_sources()
            self.assertIn("essai_test", sources)
            module = sources["essai_test"]
            self.assertEqual(module.INFO["country_code"], "ZZ")
            self.assertEqual(module.passages({"products": []}), [])
            with self.assertRaises(FileExistsError):
                source_scaffold.create_source("essai_test", "Essai", "ZZ", "Pays", "Région")
        finally:
            (source_scaffold.config.ROOT / created).unlink(missing_ok=True)

    def test_identifiant_invalide_refuse(self):
        with self.assertRaises(ValueError):
            source_scaffold.create_source("Mauvais Nom", "x", "ZZ", "x", "x")


if __name__ == "__main__":
    unittest.main()
