select sku,warehouse_id from {{ ref('fct_inventory_daily') }} group by sku,warehouse_id having count(*) <> {{ days_between('min(snapshot_date)','max(snapshot_date)') }} + 1
