with receipts as (
 select sku,warehouse_id,received_date,sum(received_qty) as qty from {{ ref('fct_supplier_receipt') }}
 where received_date is not null group by sku,warehouse_id,received_date
)
select coalesce(i.sku,r.sku) as sku,coalesce(i.warehouse_id,r.warehouse_id) as warehouse_id
from {{ ref('fct_inventory_daily') }} i full outer join receipts r
 on r.sku=i.sku and r.warehouse_id=i.warehouse_id and r.received_date=i.snapshot_date
where coalesce(i.received_qty,0)<>coalesce(r.qty,0)
