-- Gaps-and-islands: find persistent stockouts rather than counting isolated zero balances.
with changes as (
 select *,case when stockout=lag(stockout) over(partition by sku,warehouse_id order by snapshot_date)
 then 0 else 1 end as new_group from analytics.fct_inventory_daily
), islands as (
 select *,sum(new_group) over(partition by sku,warehouse_id order by snapshot_date rows unbounded preceding) as island
 from changes
)
select sku,warehouse_id,min(snapshot_date) as first_day,max(snapshot_date) as last_day,count(*) as stockout_days
from islands where stockout=1 group by sku,warehouse_id,island order by stockout_days desc;
