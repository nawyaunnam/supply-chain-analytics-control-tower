select s.*,o.sku,o.warehouse_id,o.order_id,
 s.transport_cost_cents/100.0 as transport_cost,
 {{ days_between('s.shipped_date','s.delivered_date') }} as transit_days
from {{ ref('stg_shipments') }} s join {{ ref('stg_order_lines') }} o on o.line_id=s.line_id
