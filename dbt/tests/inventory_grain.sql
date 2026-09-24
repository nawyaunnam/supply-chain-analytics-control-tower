select sku,warehouse_id,snapshot_date,count(*) as n from {{ ref('fct_inventory_daily') }} group by sku,warehouse_id,snapshot_date having count(*)<>1
