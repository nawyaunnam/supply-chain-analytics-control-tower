-- Inventory spine preserves zero-demand days for each observed SKU/warehouse series.
select i.sku,i.warehouse_id,i.snapshot_date as date_day,
 coalesce(sum(o.ordered_qty),0) as demand_qty
from {{ ref('stg_inventory') }} i
left join {{ ref('stg_order_lines') }} o on o.sku=i.sku and o.warehouse_id=i.warehouse_id
 and o.order_date=i.snapshot_date and o.status<>'cancelled'
group by i.sku,i.warehouse_id,i.snapshot_date
