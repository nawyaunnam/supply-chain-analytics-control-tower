import hashlib
import json
import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import get_args

import pyarrow as pa
import pyarrow.parquet as pq

from .contracts import CONTRACTS, KEYS


def arrow_schema(name):
    fields = []
    for field, info in CONTRACTS[name].model_fields.items():
        annotation = info.annotation
        if date in get_args(annotation):
            annotation = date
        dtype = pa.date32() if annotation is date else pa.int64() if annotation is int else pa.string()
        fields.append(pa.field(field, dtype))
    return pa.schema(fields)


def validate(data):
    if set(data) != set(CONTRACTS):
        raise ValueError("Supply all seven contracted datasets")
    clean = {}
    for name, cls in CONTRACTS.items():
        rows = [cls.model_validate(row).model_dump() for row in data[name]]
        if not rows:
            raise ValueError(f"Empty required dataset: {name}")
        seen = set()
        for r in rows:
            key = tuple(r[k] for k in KEYS[name])
            if key in seen:
                raise ValueError(f"Duplicate {name} key")
            seen.add(key)
        clean[name] = rows
    suppliers = {s["supplier_id"] for s in clean["suppliers"]}
    products = {p["sku"] for p in clean["products"]}
    warehouses = {r["warehouse_id"] for r in clean["warehouses"]}
    lines = {r["line_id"]: r for r in clean["order_lines"]}
    for p in clean["products"]:
        if p["supplier_id"] not in suppliers:
            raise ValueError("Orphan product supplier")
    for name in ["order_lines", "inventory", "purchase_orders"]:
        for r in clean[name]:
            if r["sku"] not in products or r["warehouse_id"] not in warehouses:
                raise ValueError(f"Orphan {name} dimension")
    orders = {}
    for r in clean["order_lines"]:
        header = (r["warehouse_id"], r["order_date"])
        if r["order_id"] in orders and orders[r["order_id"]] != header:
            raise ValueError("An order must have one warehouse and order date")
        orders[r["order_id"]] = header
        if r["promised_date"] < r["order_date"]:
            raise ValueError("Promise precedes order")
    shipped = {}
    for r in clean["shipments"]:
        line = lines.get(r["line_id"])
        if not line or line["status"] == "cancelled":
            raise ValueError("Shipment has invalid order line")
        if r["shipped_date"] < line["order_date"] or (
            r["delivered_date"] and r["delivered_date"] < r["shipped_date"]
        ):
            raise ValueError("Invalid shipment chronology")
        shipped[r["line_id"]] = shipped.get(r["line_id"], 0) + r["shipped_qty"]
    if any(q > lines[k]["ordered_qty"] for k, q in shipped.items()):
        raise ValueError("Over-shipment exceeds ordered quantity")
    for r in clean["inventory"]:
        if (
            r["opening_qty"] + r["received_qty"] - r["shipped_qty"] != r["on_hand_qty"]
            or r["reserved_qty"] > r["on_hand_qty"]
        ):
            raise ValueError("Inventory flow does not balance")
    for r in clean["purchase_orders"]:
        if r["supplier_id"] not in suppliers or r["expected_date"] < r["placed_date"]:
            raise ValueError("Invalid purchase order")
        if r["received_date"] and r["received_date"] < r["placed_date"]:
            raise ValueError("Receipt precedes placement")
        if r["received_qty"] > r["ordered_qty"] or (r["received_qty"] > 0 and not r["received_date"]):
            raise ValueError("Invalid received quantity")
    as_of = max(r["snapshot_date"] for r in clean["inventory"])
    for name, fields in {
        "order_lines": ["order_date"],
        "shipments": ["shipped_date", "delivered_date"],
        "purchase_orders": ["placed_date", "received_date"],
    }.items():
        if any(r[f] and r[f] > as_of for r in clean[name] for f in fields):
            raise ValueError("Observed fact is later than snapshot cutoff")
    return clean


def publish(data, landing):
    data = validate(data)
    landing = Path(landing)
    landing.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".batch-", dir=landing))
    try:
        manifest = {"contract_version": 1, "files": {}}
        for name, rows in data.items():
            rows = sorted(rows, key=lambda r: tuple(r[k] for k in KEYS[name]))
            file = temp / f"{name}.parquet"
            pq.write_table(pa.Table.from_pylist(rows, schema=arrow_schema(name)), file, compression="snappy")
            manifest["files"][name] = {
                "rows": len(rows),
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            }
        batch_id = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[:24]
        manifest["batch_id"] = batch_id
        (temp / "manifest.json").write_text(json.dumps(manifest, indent=2))
        dest = landing / batch_id
        if dest.exists():
            verify(dest)
        else:
            temp.rename(dest)
        return dest
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def verify(batch):
    batch = Path(batch)
    m = json.loads((batch / "manifest.json").read_text())
    if set(m["files"]) != set(CONTRACTS):
        raise ValueError("Invalid manifest")
    for name, info in m["files"].items():
        if hashlib.sha256((batch / f"{name}.parquet").read_bytes()).hexdigest() != info["sha256"]:
            raise ValueError(f"Checksum failed: {name}")
    return m
