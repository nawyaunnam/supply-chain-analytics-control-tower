with latest as (
 select * from {{ ref('fct_inventory_daily') }} where snapshot_date=(select max(snapshot_date) from {{ ref('fct_inventory_daily') }})
), demand as (
 select sku,warehouse_id,sum(predicted_qty) as next_14_day_demand
 from {{ ref('fct_forecasts') }} group by sku,warehouse_id
)
select l.sku,l.warehouse_id,l.snapshot_date,l.available_qty,l.safety_stock,d.next_14_day_demand,
 case when l.available_qty<d.next_14_day_demand then 'review_replenishment' else 'covered' end as risk,
 d.next_14_day_demand-l.available_qty as projected_shortfall
from latest l join demand d on l.sku=d.sku and l.warehouse_id=d.warehouse_id
