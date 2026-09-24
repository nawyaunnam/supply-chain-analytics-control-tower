import json
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "powerbi"


def test_official_report_schemas():
    folder = ROOT / "tests/schemas"
    index = json.loads((folder / "index.json").read_text())
    registry = Registry().with_resources(
        (uri, Resource.from_contents(json.loads((folder / path).read_text()))) for uri, path in index.items()
    )
    for p in list(PBI.rglob("*.json")) + list(PBI.rglob("*.pbir")):
        obj = json.loads(p.read_text())
        if "$schema" in obj:
            schema = registry.contents(obj["$schema"])
            errors = list(
                jsonschema.validators.validator_for(schema)(schema, registry=registry).iter_errors(obj)
            )
            assert not errors, f"{p}: {[e.message for e in errors]}"


def test_model_bindings_and_warehouse_security():
    model = json.loads((PBI / "ControlTower.SemanticModel/model.bim").read_text())["model"]
    tables = {t["name"]: t for t in model["tables"]}
    for r in model["relationships"]:
        for side in ["from", "to"]:
            assert r[side + "Column"] in [c["name"] for c in tables[r[side + "Table"]]["columns"]]
        assert r["crossFilteringBehavior"] == "oneDirection"
    facts = [
        "Orders",
        "Inventory",
        "Demand",
        "Shipments",
        "Supplier receipts",
        "Forecasts",
        "Backtests",
        "Anomalies",
    ]
    for fact in facts:
        assert any(r["fromTable"] == fact and r["toTable"] == "Warehouse" for r in model["relationships"])
    assert "USERPRINCIPALNAME" in model["roles"][0]["tablePermissions"][0]["filterExpression"]

    def walk(obj):
        if isinstance(obj, dict):
            for kind, collection in [("Column", "columns"), ("Measure", "measures")]:
                if kind in obj and "Property" in obj[kind]:
                    e = obj[kind]
                    t = e["Expression"]["SourceRef"]["Entity"]
                    assert e["Property"] in [c["name"] for c in tables[t][collection]]
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    for p in (PBI / "ControlTower.Report").rglob("*.json"):
        walk(json.loads(p.read_text()))
    dax = (PBI / "measures.dax").read_text()
    assert all(m["expression"] in dax for m in tables["Metrics"]["measures"])
