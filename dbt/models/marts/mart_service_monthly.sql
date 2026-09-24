select {{ month('promised_date') }} as month,warehouse_id,
 count(*) as due_orders,sum(otif) as otif_orders,sum(otif)*1.0/count(*) as otif_rate,
 sum(first_dispatch_qty)*1.0/nullif(sum(ordered_qty),0) as first_dispatch_fill_rate,
 sum(transport_cost) as transport_cost,
 sum(transport_cost)/nullif(sum(delivered_qty),0) as cost_per_delivered_unit
from {{ ref('fct_order') }} where due=1 group by {{ month('promised_date') }},warehouse_id
