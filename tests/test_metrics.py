import os
import subprocess
from datetime import date
from pathlib import Path

import duckdb
import pytest

from control_tower.ingest import publish
from control_tower.warehouse import load_batch


def fixture_data():
    def d(day):
        return date(2025, 1, day)

    data = {
        "suppliers": [dict(supplier_id="S1", supplier_name="Fixture", region="AMER", target_lead_days=1)],
        "products": [
            dict(sku=p, supplier_id="S1", category="Parts", unit_cost_cents=1000) for p in ["P1", "P2"]
        ],
        "warehouses": [dict(warehouse_id="W1", region="AMER")],
        "order_lines": [],
        "shipments": [],
        "inventory": [],
        "purchase_orders": [
            dict(
                po_id="PO1",
                sku="P1",
                warehouse_id="W1",
                supplier_id="S1",
                placed_date=d(1),
                expected_date=d(2),
                received_date=d(2),
                ordered_qty=20,
                received_qty=20,
            )
        ],
    }
    for lid, oid, sku, qty, due, status in [
        ("L1", "O1", "P1", 10, 3, "open"),
        ("L2", "O1", "P2", 10, 3, "open"),
        ("L3", "O2", "P1", 20, 3, "open"),
        ("L4", "O3", "P1", 5, 15, "open"),
        ("L5", "O4", "P1", 99, 3, "cancelled"),
        ("L6", "O5", "P1", 10, 6, "open"),
    ]:
        data["order_lines"].append(
            dict(
                line_id=lid,
                order_id=oid,
                sku=sku,
                warehouse_id="W1",
                order_date=d(1),
                promised_date=d(due),
                ordered_qty=qty,
                status=status,
            )
        )
    for sid, line, ship, deliver, qty in [
        ("S1", "L1", 2, 3, 6),
        ("S2", "L1", 3, 4, 4),
        ("S3", "L2", 2, 3, 10),
        ("S4", "L3", 2, 3, 20),
    ]:
        data["shipments"].append(
            dict(
                shipment_id=sid,
                line_id=line,
                shipped_date=d(ship),
                delivered_date=d(deliver),
                shipped_qty=qty,
                transport_cost_cents=100,
                carrier="Fixture",
            )
        )
    for sku in ["P1", "P2"]:
        stock = 100
        for day in range(1, 11):
            received = 20 if sku == "P1" and day == 2 else 0
            shipped = (26 if day == 2 else 4 if day == 3 else 0) if sku == "P1" else (10 if day == 2 else 0)
            opening = stock
            stock += received - shipped
            data["inventory"].append(
                dict(
                    sku=sku,
                    warehouse_id="W1",
                    snapshot_date=d(day),
                    opening_qty=opening,
                    received_qty=received,
                    shipped_qty=shipped,
                    on_hand_qty=stock,
                    reserved_qty=0,
                    safety_stock=10,
                )
            )
    return data


def test_order_otif_and_weighted_fill_golden_case(tmp_path):
    root = Path(__file__).resolve().parents[1]
    batch = publish(fixture_data(), tmp_path / "data/landing")
    load_batch(tmp_path, batch)
    db = tmp_path / "data/warehouse.duckdb"
    run = subprocess.run(
        [
            "dbt",
            "build",
            "--project-dir",
            str(root / "dbt"),
            "--profiles-dir",
            str(root / "dbt"),
            "--target-path",
            str(tmp_path / "target"),
            "--log-path",
            str(tmp_path / "logs"),
        ],
        env={**os.environ, "DUCKDB_PATH": str(db)},
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    with duckdb.connect(str(db)) as con:
        due, otif, rate, fill = con.execute(
            "select due_orders,otif_orders,otif_rate,first_dispatch_fill_rate from analytics.mart_service_monthly"
        ).fetchone()
        assert (due, otif) == (3, 1)
        assert float(rate) == pytest.approx(1 / 3)
        assert float(fill) == pytest.approx(36 / 50)
        assert con.execute("select otif from analytics.fct_order where order_id='O1'").fetchone()[0] == 0
        assert con.execute("select due from analytics.fct_order where order_id='O3'").fetchone()[0] == 0
        assert con.execute("select count(*) from analytics.fct_order where order_id='O4'").fetchone()[0] == 0
        assert con.execute("select sum(transport_cost) from analytics.fct_order_line").fetchone()[0] == 4
