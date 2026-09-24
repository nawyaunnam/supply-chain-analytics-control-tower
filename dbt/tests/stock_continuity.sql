select * from (
 select *,lag(on_hand_qty) over(partition by sku,warehouse_id order by snapshot_date) as prior_close
 from {{ ref('fct_inventory_daily') }}
) x where prior_close is not null and opening_qty<>prior_close
