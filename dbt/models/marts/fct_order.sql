-- One row per order: ALL non-cancelled lines must pass. Do not average line OTIF.
select order_id,warehouse_id,min(order_date) as order_date,max(promised_date) as promised_date,
 count(*) as lines,sum(ordered_qty) as ordered_qty,sum(first_dispatch_qty) as first_dispatch_qty,
 sum(delivered_qty) as delivered_qty,min(due) as due,min(line_otif) as otif,
 sum(transport_cost) as transport_cost
from {{ ref('fct_order_line') }} group by order_id,warehouse_id
