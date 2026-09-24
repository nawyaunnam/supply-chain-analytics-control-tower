with shipments as (
 select sku,warehouse_id,shipped_date,sum(shipped_qty) as qty from {{ ref('fct_shipment') }} group by sku,warehouse_id,shipped_date
)
select i.* from {{ ref('fct_inventory_daily') }} i left join shipments s
 on s.sku=i.sku and s.warehouse_id=i.warehouse_id and s.shipped_date=i.snapshot_date
where i.shipped_qty<>coalesce(s.qty,0)
