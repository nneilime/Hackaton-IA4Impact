"""Garde-fou du connecteur Power Platform : le Swagger 2.0 doit rester importable et fidèle au contrat."""
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SWAGGER_YAML = ROOT / "connector" / "power-platform.swagger.yaml"
SWAGGER_JSON = ROOT / "connector" / "power-platform.swagger.json"
CONTRACT = ROOT / "openapi.proposed.yaml"

# Constructions OpenAPI 3.x que Power Platform refuse dans un Swagger 2.0
FORBIDDEN_KEYS = {"const", "oneOf", "anyOf", "nullable", "openapi"}


def load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def walk(node, path="$"):
    """Parcourt tout le document et rend (chemin, clé, valeur)."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield path, key, value
            yield from walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk(value, f"{path}[{i}]")


def operations(doc):
    """{operationId: (chemin, méthode, noms de paramètres)}"""
    result = {}
    for route, methods in doc["paths"].items():
        for method, op in methods.items():
            names = {p["name"] for p in op.get("parameters", []) if "name" in p}
            result[op["operationId"]] = (route, method, names)
    return result


def test_is_swagger_2():
    doc = load(SWAGGER_YAML)
    assert doc["swagger"] == "2.0"
    assert "openapi" not in doc


def test_no_openapi_3_constructs():
    doc = load(SWAGGER_YAML)
    for where, key, value in walk(doc):
        assert key not in FORBIDDEN_KEYS, f"{key} interdit dans un Swagger 2.0 ({where})"
        if key == "type":
            assert isinstance(value, str), f"type en liste interdit ({where}) : utiliser x-nullable"


def test_refs_resolve():
    doc = load(SWAGGER_YAML)
    for where, key, value in walk(doc):
        if key == "$ref":
            assert value.startswith("#/definitions/"), where
            assert value.split("/")[-1] in doc["definitions"], f"$ref cassé : {value}"


def test_https_host_and_size():
    doc = load(SWAGGER_YAML)
    assert doc["schemes"] == ["https"]
    assert "://" not in doc["host"] and "/" not in doc["host"], "host = domaine seul"
    assert SWAGGER_JSON.stat().st_size < 1_000_000


def test_operations_match_contract():
    swagger_ops = operations(load(SWAGGER_YAML))
    contract_ops = operations(load(CONTRACT))
    assert set(swagger_ops) == {"askRegulatoryQuestion", "searchProducts",
                                "getProductRegistrations", "compareProductUses"}
    for op_id, (route, method, params) in swagger_ops.items():
        c_route, c_method, c_params = contract_ops[op_id]
        assert (route, method) == (c_route, c_method), op_id
        # body de /ask : nommé « body » dans Swagger 2.0, absent des parameters de la 3.1
        assert params - {"body"} <= c_params, f"{op_id} : paramètres inconnus du contrat {params - c_params}"


def test_json_is_up_to_date():
    """Si ce test échoue : python scripts/build_connector.py"""
    assert json.loads(SWAGGER_JSON.read_text(encoding="utf-8")) == load(SWAGGER_YAML)
