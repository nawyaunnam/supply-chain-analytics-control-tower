select {{ month('snapshot_date') }} as month,sku,warehouse_id,
 avg(inventory_value) as average_inventory_value,sum(shipped_cogs) as shipped_cogs,
 sum(shipped_cogs)/nullif(avg(inventory_value),0) as period_inventory_turnover,
 sum(stockout) as stockout_days,count(*) as observed_days,
 sum(stockout)*1.0/count(*) as stockout_rate,
 sum(below_safety) as below_safety_days
from {{ ref('fct_inventory_daily') }} group by {{ month('snapshot_date') }},sku,warehouse_id
