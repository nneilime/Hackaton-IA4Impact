"""db/schema.sql doit pouvoir être relancé sans danger : aucune suppression, uniquement des créations « si absent »."""
import re
from pathlib import Path

SQL = (Path(__file__).resolve().parents[1] / "db" / "schema.sql").read_text(encoding="utf-8")
CODE = "\n".join(line for line in SQL.splitlines() if not line.strip().startswith("--"))


def test_schema_has_no_destructive_statement():
    # « ON DELETE CASCADE » (clé étrangère) est permis ; ce sont les instructions de suppression qui sont interdites
    assert not re.search(r"\b(DROP|TRUNCATE)\b|\bDELETE\s+FROM\b", CODE, re.I)


def test_schema_creates_only_if_missing():
    assert not re.search(r"CREATE\s+TABLE\s+(?!IF NOT EXISTS)", CODE, re.I)
    assert not re.search(r"CREATE\s+INDEX\s+(?!IF NOT EXISTS)", CODE, re.I)
    assert not re.search(r"CREATE\s+VIEW", CODE, re.I)   # CREATE OR REPLACE VIEW uniquement
    assert "Safe to re-run: creates only what is missing, never deletes data." in SQL


def test_schema_keeps_related_product_id_and_its_index():
    assert "related_product_id" in SQL and "idx_aliases_related" in SQL
