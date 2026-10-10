import csv
import io
import unittest
from copy import deepcopy

from scripts.import_csv import convert, initial_lot, parse_files, preview
from scripts.schema import SOURCES


def payload(table, rows, delimiter=",", bom=False):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=SOURCES[table][2].split(), delimiter=delimiter
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig" if bom else "utf-8")


class ImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.initial = initial_lot()["lot"]

    def test_source_counts_and_document_cells(self):
        self.assertEqual(len(initial_lot()["files"]), 17)
        self.assertEqual(len(self.initial["prix_interventions"]), 87)
        self.assertEqual(sum(len(self.initial[t]) for t in SOURCES), 46581)
        self.assertEqual(len(self.initial["equipements"]), 4217)
        self.assertEqual(
            sum(r["dans_perimetre_prediction"] for r in self.initial["equipements"]),
            1285,
        )
        self.assertEqual(
            [
                len(self.initial[t])
                for t in ("dictionnaire", "hypotheses", "documentation")
            ],
            [99, 22, 32],
        )
        self.assertEqual(self.initial["documentation"][0]["colonne_1"], "")

    def test_bom_semicolon_and_reimport(self):
        row = {
            "prestataire_id": "QA",
            "nom": "Équipe; spécialiste",
            "domaine": "Chauffage",
            "type_contrat": "P2",
        }
        parsed = parse_files(
            [("nouveau.csv", payload("prestataires", [row], ";", True))]
        )
        first = preview(parsed, {})
        self.assertEqual(first["tables"]["prestataires"]["added"], 1)
        self.assertEqual(first["files"][0]["added"], 1)
        second = preview(parsed, {"prestataires": [row]})
        self.assertEqual(second["tables"]["prestataires"]["unchanged"], 1)

    def test_unknown_columns_are_reported(self):
        parsed = parse_files(
            [
                (
                    "bad.csv",
                    b"prestataire_id,nom,domaine,type_contrat,secret\nP,x,x,x,123",
                )
            ]
        )
        self.assertIn("secret", parsed["errors"][0]["message"])
        self.assertFalse(parsed["lot"])

    def test_duplicates_across_files_block_the_lot(self):
        row = {
            "prestataire_id": "QA",
            "nom": "Équipe",
            "domaine": "Test",
            "type_contrat": "Test",
        }
        parsed = parse_files(
            [(name, payload("prestataires", [row])) for name in ("a.csv", "b.csv")]
        )
        self.assertEqual(parsed["errors"][0]["file"], "b.csv")
        self.assertEqual(parsed["errors"][0]["line"], 2)

    def test_empty_lot_and_wrong_encoding(self):
        self.assertTrue(parse_files([])["errors"])
        self.assertTrue(parse_files([("bad.csv", b"\xff")])["errors"])

    def test_references_have_original_file_and_line(self):
        row = {
            "batiment_id": "QA",
            "residence_id": "ABSENT",
            "nb_niveaux": "2",
            "nb_logements": "3",
            "ascenseur": "Non",
        }
        result = preview(
            parse_files([("batiments.csv", payload("batiments", [row]))]), self.initial
        )
        self.assertEqual(result["errors"][0]["file"], "batiments.csv")
        self.assertEqual(result["errors"][0]["line"], 2)

    def test_parent_change_validates_existing_children(self):
        changed = deepcopy(self.initial["batiments"][0])
        changed["residence_id"] = self.initial["residences"][1]["residence_id"]
        result = preview(
            {"lot": {"batiments": [changed]}, "files": [], "errors": []}, self.initial
        )
        self.assertTrue(result["errors"])

    def test_types_and_special_texts(self):
        for col, value in [
            ("ascenseur", "peut-être"),
            ("montant_ttc", "NaN"),
            ("nb_logements", "1.5"),
            ("date_pose", "2025-02-30"),
        ]:
            with self.assertRaises(ValueError):
                convert(col, value)
        self.assertEqual(
            convert("date_entree_locataire_actuel", "Avant 2018"), "Avant 2018"
        )
        self.assertEqual(convert("energie_primaire_kwh_m2_an", "≤70"), "≤70")


if __name__ == "__main__":
    unittest.main()
