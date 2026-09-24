with shipments as (
 select sku,warehouse_id,shipped_date,sum(shipped_qty) as qty from {{ ref('fct_shipment') }} group by sku,warehouse_id,shipped_date
)
select coalesce(i.sku,s.sku) as sku,coalesce(i.warehouse_id,s.warehouse_id) as warehouse_id
from {{ ref('fct_inventory_daily') }} i full outer join shipments s
 on s.sku=i.sku and s.warehouse_id=i.warehouse_id and s.shipped_date=i.snapshot_date
where coalesce(i.shipped_qty,0)<>coalesce(s.qty,0)
