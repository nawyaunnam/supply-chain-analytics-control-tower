from datetime import date

import duckdb
import pytest

from control_tower.generate import generate
from control_tower.ingest import publish, validate
from control_tower.warehouse import load_batch


@pytest.fixture
def records():
    return generate(days=84, skus=1)


def test_idempotent_load_and_stock_balance(records, tmp_path):
    batch = publish(records, tmp_path / "data/landing")
    assert publish(records, tmp_path / "data/landing") == batch
    load_batch(tmp_path, batch)
    load_batch(tmp_path, batch)
    with duckdb.connect(str(tmp_path / "data/warehouse.duckdb")) as con:
        assert con.execute("select count(*) from raw.order_lines").fetchone()[0] == len(
            records["order_lines"]
        )
        assert (
            con.execute(
                "select count(*) from raw.inventory where opening_qty+received_qty-shipped_qty<>on_hand_qty"
            ).fetchone()[0]
            == 0
        )


@pytest.mark.parametrize("fault", ["negative", "duplicate", "orphan", "stock", "over_shipment", "future"])
def test_bad_batch_never_lands(records, tmp_path, fault):
    if fault == "negative":
        records["shipments"][0]["shipped_qty"] = -1
    elif fault == "duplicate":
        records["suppliers"].append(records["suppliers"][0])
    elif fault == "orphan":
        records["shipments"][0]["line_id"] = "absent"
    elif fault == "stock":
        records["inventory"][0]["on_hand_qty"] += 1
    elif fault == "over_shipment":
        records["shipments"][0]["shipped_qty"] = 9999
    else:
        records["shipments"][0]["delivered_date"] = date(2099, 1, 1)
    with pytest.raises(ValueError):
        publish(records, tmp_path / "landing")
    assert not (tmp_path / "landing").exists()


def test_corrupt_manifest_does_not_replace_warehouse(records, tmp_path):
    batch = publish(records, tmp_path / "data/landing")
    load_batch(tmp_path, batch)
    (batch / "products.parquet").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="Checksum"):
        load_batch(tmp_path, batch)
    with duckdb.connect(str(tmp_path / "data/warehouse.duckdb")) as con:
        assert con.execute("select count(*) from raw.products").fetchone()[0] == 1


def test_no_future_delivery_observations(records):
    assert validate(records)
    as_of = max(r["snapshot_date"] for r in records["inventory"])
    assert all(r["delivered_date"] is None or r["delivered_date"] <= as_of for r in records["shipments"])
