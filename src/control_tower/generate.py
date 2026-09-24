"""Daily stock-flow simulation; shipments cannot consume stock that does not exist."""

import random
from datetime import date, timedelta


def generate(days=240, skus=8, seed=17):
    if not 84 <= days <= 730 or not 1 <= skus <= 100:
        raise ValueError("Use 84–730 days and 1–100 SKUs")
    rng = random.Random(seed)
    start = date(2025, 1, 1)
    as_of = start + timedelta(days=days - 1)
    data = {
        n: []
        for n in [
            "suppliers",
            "products",
            "warehouses",
            "order_lines",
            "shipments",
            "inventory",
            "purchase_orders",
        ]
    }
    for i in range(4):
        data["suppliers"].append(
            dict(
                supplier_id=f"S{i + 1:02}",
                supplier_name=f"Synthetic Supplier {i + 1}",
                region=["AMER", "EMEA", "APAC", "AMER"][i],
                target_lead_days=4 + i,
            )
        )
    for i in range(skus):
        data["products"].append(
            dict(
                sku=f"P{i + 1:03}",
                supplier_id=f"S{i % 4 + 1:02}",
                category=["Components", "Finished goods"][i % 2],
                unit_cost_cents=900 + i * 175,
            )
        )
    data["warehouses"] = [
        dict(warehouse_id=f"W{i + 1:02}", region=r) for i, r in enumerate(["AMER", "EMEA", "APAC"])
    ]
    lid = sid = pid = 0
    for product in data["products"]:
        sku = product["sku"]
        supplier = next(s for s in data["suppliers"] if s["supplier_id"] == product["supplier_id"])
        for wh in data["warehouses"]:
            wid = wh["warehouse_id"]
            receipts = {}
            for k in range(0, days, 7):
                placed = start + timedelta(days=k)
                expected = placed + timedelta(days=supplier["target_lead_days"])
                delay = rng.choice([0, 0, 0, 1, 2, 4])
                if wid == "W02" and sku == "P003" and 98 <= k <= 126:
                    delay += 28
                received = expected + timedelta(days=delay)
                qty = rng.randrange(45, 80)
                pid += 1
                data["purchase_orders"].append(
                    dict(
                        po_id=f"PO{pid:06}",
                        sku=sku,
                        warehouse_id=wid,
                        supplier_id=supplier["supplier_id"],
                        placed_date=placed,
                        expected_date=expected,
                        received_date=received if received <= as_of else None,
                        ordered_qty=qty,
                        received_qty=qty if received <= as_of else 0,
                    )
                )
                if received <= as_of:
                    receipts[received] = receipts.get(received, 0) + qty
            stock = 65
            backlog = []
            for day in range(days):
                d = start + timedelta(days=day)
                opening = stock
                received_qty = receipts.get(d, 0)
                stock += received_qty
                # Weekly demand, gradual growth and one deliberate, labeled demand shock.
                if rng.random() < (0.78 if d.weekday() < 5 else 0.35):
                    qty = rng.randrange(6, 20) + day // 90
                    if sku == "P003" and wid == "W01" and day == 190:
                        qty *= 8
                    lid += 1
                    status = "cancelled" if rng.random() < 0.025 else "open"
                    line = dict(
                        line_id=f"L{lid:07}",
                        order_id=f"O{day:03}{wid}",
                        sku=sku,
                        warehouse_id=wid,
                        order_date=d,
                        promised_date=d + timedelta(days=5),
                        ordered_qty=qty,
                        status=status,
                    )
                    data["order_lines"].append(line)
                    if status != "cancelled":
                        backlog.append({"line": line, "remaining": qty})
                shipped = 0
                for item in backlog:
                    line = item["line"]
                    if line["order_date"] >= d or not item["remaining"] or stock == 0:
                        continue
                    qty = min(item["remaining"], stock)
                    if qty > 1 and rng.random() < 0.13:
                        qty = max(1, qty // 2)
                    transit = rng.choice([1, 2, 2, 3, 6])
                    if wid == "W03" and 150 <= day < 175:
                        transit += 7
                    delivered = d + timedelta(days=transit)
                    sid += 1
                    data["shipments"].append(
                        dict(
                            shipment_id=f"SH{sid:07}",
                            line_id=line["line_id"],
                            shipped_date=d,
                            delivered_date=delivered if delivered <= as_of else None,
                            shipped_qty=qty,
                            transport_cost_cents=250 + qty * rng.randrange(30, 80),
                            carrier=["North Freight", "Blue Route", "Summit Logistics"][day % 3],
                        )
                    )
                    stock -= qty
                    shipped += qty
                    item["remaining"] -= qty
                data["inventory"].append(
                    dict(
                        sku=sku,
                        warehouse_id=wid,
                        snapshot_date=d,
                        opening_qty=opening,
                        received_qty=received_qty,
                        shipped_qty=shipped,
                        on_hand_qty=stock,
                        reserved_qty=min(stock, sum(b["remaining"] for b in backlog)),
                        safety_stock=25,
                    )
                )
    return data
