# Supply chain metric contracts

The sample is a single-currency, single-unit-per-SKU model. Each order belongs to one warehouse. Cancelled lines are excluded from service metrics and demand. The observation cutoff is the latest inventory snapshot; future promised dates are allowed, future observed deliveries are rejected. Partial receipts/shipments must be supplied explicitly.

| Metric | Definition |
|---|---|
| Order OTIF | Due orders for which **every non-cancelled line** has cumulative delivered quantity by its own promise date ≥ ordered quantity, divided by due orders. Not an average of line OTIF. An overdue undelivered order fails; a not-yet-due order is excluded. |
| First-dispatch fill rate | Quantity shipped on each line's first dispatch date / ordered units, aggregated with unit weights across due orders. Multiple dispatches on that first date are summed. This is not eventual fulfillment or on-time delivery fill rate. |
| Inventory turnover | Shipped COGS during the selected period / average daily end-of-day inventory value at standard unit cost. Not annualized; compare equal-length periods. At company scope, average the **daily total** inventory value, not SKU-level ratios. |
| Stockouts | SKU/warehouse observation days with physical on-hand quantity = 0. Rate denominator is observed SKU-days, not calendar days or units. Available-to-promise = on-hand − reserved is separate. |
| Supplier OTIF | POs due by cutoff received in full by expected date / due POs. Overdue unreceived POs remain in the denominator. |
| Lead-time variance | Actual receipt date − expected receipt date, in days. Mean signed lateness and lead-time standard deviation are distinct measures. Receipt-based averages exclude unreceived POs; the scorecard also displays overdue unreceived counts. |
| Transportation cost | Sum of each shipment's cost exactly once. Shipment-date reporting in Power BI; service mart attributes cumulative shipment cost to the order's promise month. Cost per shipped unit is separate from cost per delivered unit. |
| Demand | Non-cancelled ordered units per SKU/warehouse/day; includes zero-order days. Does not estimate unobserved lost demand. |
| WAPE | Sum absolute forecast errors / sum actual demand. NULL for zero demand, not an invented zero accuracy. Report per model; do not mix candidates. |
| Bias | Sum(prediction − actual) / sum(actual); positive = overforecasting. |
| MAE | Mean absolute forecast error in SKU units. |
| Replenishment review | Next 14-day predicted demand minus current available stock. Ignores open inbound supply, allocation policy, order quantities and service targets; **not an automatic purchasing recommendation**. |

## Grains and joins

Dimensions: product (SKU), warehouse, supplier and date. Facts: order line, order, shipment, SKU/warehouse/day inventory and demand, purchase order, forecast target date, backtest origin/target/model and anomaly observation. Aggregate shipments to lines before combining with order measures; otherwise split shipments multiply order quantities. Orders use one warehouse and one order date; the ingestion contract rejects inconsistent headers. Products do not filter the order-grain OTIF measure: SKU slicing would change the definition. The warehouse slicer filters every operational fact.

## Golden case

O1 has two ten-unit lines; one arrives as six on time plus four late, and the other ten arrives on time. O1 fails OTIF. O2's twenty units arrive on time, so it passes. O5's ten units are overdue/unshipped. O3 is not yet due and O4 is cancelled: both excluded. OTIF = 1/3, first-dispatch fill rate = (6+10+20+0)/(10+10+20+10) = 72%. Tests run these inputs through the actual dbt models.

Inventory tests assert opening + receipts − shipments = closing, prior closing = next opening, and shipped inventory equals shipment records. This detects quantity leakage that a dashboard alone would miss.
