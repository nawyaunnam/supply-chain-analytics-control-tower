import csv
import json
from pathlib import Path

from .warehouse import connect, execute

TABLES = [
    "dim_supplier",
    "dim_product",
    "dim_warehouse",
    "dim_date",
    "fct_order_line",
    "fct_order",
    "fct_inventory_daily",
    "fct_demand_daily",
    "fct_shipment",
    "fct_supplier_receipt",
    "mart_service_monthly",
    "mart_inventory_monthly",
    "mart_supplier_performance",
    "fct_forecasts",
    "fct_backtests",
    "fct_anomalies",
    "mart_forecast_accuracy",
    "mart_risk_queue",
]


def export(root, target="local"):
    output = Path(root) / "artifacts"
    output.mkdir(exist_ok=True)
    data = {}
    with connect(root, target) as con:
        for name in TABLES:
            cur = execute(con, f"select * from analytics.{name}")
            fields = [d[0] for d in cur.description]
            rows = cur.fetchall()
            data[name] = [dict(zip(fields, row, strict=True)) for row in rows]
            with (output / f"{name}.csv").open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(fields)
                writer.writerows(rows)
    orders = [r for r in data["fct_order"] if r["due"] == 1]
    otif = sum(r["otif"] for r in orders) / len(orders)
    fill = sum(r["first_dispatch_qty"] for r in orders) / sum(r["ordered_qty"] for r in orders)
    inv = data["fct_inventory_daily"]
    stockout = sum(r["stockout"] for r in inv) / len(inv)
    risk = sorted(data["mart_risk_queue"], key=lambda r: float(r["projected_shortfall"]), reverse=True)[:8]
    alerts = sorted(data["fct_anomalies"], key=lambda r: abs(float(r["robust_score"])), reverse=True)[:8]
    summary = {
        "dataset": "synthetic",
        "as_of": str(max(r["snapshot_date"] for r in inv)),
        "due_orders": len(orders),
        "otif": otif,
        "first_dispatch_fill_rate": fill,
        "stockout_sku_day_rate": stockout,
        "order_lines": len(data["fct_order_line"]),
        "shipments": len(data["fct_shipment"]),
        "forecast_rows": len(data["fct_forecasts"]),
        "backtest_rows": len(data["fct_backtests"]),
        "anomalies": len(data["fct_anomalies"]),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2))

    def fmt(v):
        return f"{float(v):,.1f}"

    cards = "".join(
        f"<article><span>{label}</span><strong>{value}</strong></article>"
        for label, value in [
            ("On time, in full", f"{otif:.1%}"),
            ("First-dispatch fill rate", f"{fill:.1%}"),
            ("Stockout SKU-days", f"{stockout:.1%}"),
            ("Forecast horizon", "14 days"),
        ]
    )
    riskrows = "".join(
        f"<tr><td>{r['sku']}</td><td>{r['warehouse_id']}</td><td>{r['available_qty']}</td><td>{fmt(r['next_14_day_demand'])}</td><td>{fmt(r['projected_shortfall'])}</td></tr>"
        for r in risk
    )
    alertrows = "".join(
        f"<tr><td>{r['date_day']}</td><td>{r['warehouse_id']} / {r['sku']}</td><td>{r['metric'].replace('_', ' ')}</td><td>{fmt(r['robust_score'])}</td></tr>"
        for r in alerts
    )
    supplierrows = "".join(
        f"<tr><td>{r['supplier_id']}</td><td>{float(r['otif_rate']):.1%}</td><td>{fmt(r['average_lead_days'])}</td><td>{r['overdue_unreceived']}</td></tr>"
        for r in sorted(data["mart_supplier_performance"], key=lambda r: r["supplier_id"])
    )
    # One explicit series so forecast bands and historical demand are not mixed across SKUs.
    series = sorted(
        [r for r in data["fct_demand_daily"] if r["sku"] == "P001" and r["warehouse_id"] == "W01"],
        key=lambda r: r["date_day"],
    )[-42:]
    future = sorted(
        [r for r in data["fct_forecasts"] if r["sku"] == "P001" and r["warehouse_id"] == "W01"],
        key=lambda r: r["forecast_date"],
    )
    maxy = max([float(r["demand_qty"]) for r in series] + [float(r["upper_qty"]) for r in future] + [1])

    def points(values, start):
        return " ".join(
            f"{20 + (start + i) * 15:.1f},{210 - float(v) * 180 / maxy:.1f}" for i, v in enumerate(values)
        )

    history = points([r["demand_qty"] for r in series], 0)
    predicted = points([r["predicted_qty"] for r in future], len(series))
    upper = points([r["upper_qty"] for r in future], len(series))
    lower = " ".join(reversed(points([r["lower_qty"] for r in future], len(series)).split()))
    doc = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Supply Chain Control Tower</title>
<style>*{{box-sizing:border-box}}body{{background:#0d1721;color:#e4edf6;font:14px system-ui;margin:0}}main{{max-width:1280px;margin:auto;padding:32px 24px}}header{{border-bottom:1px solid #344b5a;padding-bottom:24px}}small{{color:#66dcc1;letter-spacing:3px}}h1{{font-size:34px;margin:12px 0}}span,.muted{{color:#b3c2cf}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:24px 0}}article,.panel{{background:#172735;border:1px solid #344b5a;border-radius:9px;padding:20px}}strong{{display:block;font-size:34px;margin-top:12px}}h2{{font-size:18px;margin-top:0}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:12px 7px;border-bottom:1px solid #344b5a;text-align:left}}th{{color:#b3c2cf;font-size:12px}}svg{{width:100%;height:auto}}footer{{line-height:1.8;color:#b3c2cf;margin:24px 0}}@media(max-width:800px){{.cards{{grid-template-columns:1fr 1fr}}.grid{{grid-template-columns:1fr}}.panel{{overflow-x:auto}}}}</style>
<main><header><small>SUPPLY CHAIN / CONTROL TOWER</small><h1>See the delay. Anticipate the shortage.</h1><div class="muted">Orders · inventory · suppliers · transportation | Synthetic data as of {summary["as_of"]}</div></header>
<section class="cards">{cards}</section><section class="panel"><h2>Demand outlook · P001 / W01</h2><div class="muted">Last 42 days + 14-day forecast · green: observed · blue: forecast · shaded: empirical error band</div><svg viewBox="0 0 880 235" role="img" aria-label="Historical demand and forecast"><polygon points="{upper} {lower}" fill="#588dcd" opacity=".2"/><polyline points="{history}" stroke="#66dcc1" stroke-width="2" fill="none"/><polyline points="{predicted}" stroke="#72aaff" stroke-width="3" fill="none"/></svg></section>
<section class="grid"><div class="panel"><h2>Replenishment review queue</h2><div class="muted">Forecast demand minus available stock; inbound supply is not netted.</div><table><tr><th>SKU</th><th>Warehouse</th><th>Available</th><th>14d demand</th><th>Shortfall</th></tr>{riskrows}</table></div><div class="panel"><h2>Supplier reliability</h2><table><tr><th>Supplier</th><th>OTIF</th><th>Lead days</th><th>Overdue POs</th></tr>{supplierrows}</table></div></section>
<section class="panel" style="margin-top:20px"><h2>Largest behavior anomalies</h2><div class="muted">Trailing-window robust scores, not future-informed thresholds. Alerts require analyst review.</div><table><tr><th>Date</th><th>Scope</th><th>Metric</th><th>Robust score</th></tr>{alertrows}</table></section>
<footer>Order OTIF includes only due, non-cancelled orders and requires every line to meet its promise. Fill rate is unit-weighted on the first dispatch date.<br>Forecasts compare seasonal-naive and ETS models on three held-out windows. Error bands are empirical, not calibrated guarantees. HTML is a portable preview; Power BI source is in powerbi/.</footer></main></html>"""
    (output / "dashboard.html").write_text(doc)
    print(json.dumps(summary))
