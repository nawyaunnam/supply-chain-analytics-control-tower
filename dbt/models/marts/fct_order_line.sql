with dispatch as (
 select *, min(shipped_date) over(partition by line_id) as first_date from {{ ref('stg_shipments') }}
), rollup as (
 select o.line_id, sum(s.shipped_qty) as shipped_qty,
   sum(case when s.shipped_date=s.first_date then s.shipped_qty else 0 end) as first_dispatch_qty,
   sum(case when s.delivered_date is not null then s.shipped_qty else 0 end) as delivered_qty,
   sum(case when s.delivered_date<=o.promised_date then s.shipped_qty else 0 end) as on_time_qty,
   sum(s.transport_cost_cents)/100.0 as transport_cost,
   max(s.delivered_date) as final_delivery_date
 from {{ ref('stg_order_lines') }} o left join dispatch s on o.line_id=s.line_id group by o.line_id
)
select o.*, coalesce(r.shipped_qty,0) as shipped_qty,coalesce(r.first_dispatch_qty,0) as first_dispatch_qty,
 coalesce(r.delivered_qty,0) as delivered_qty,coalesce(r.on_time_qty,0) as on_time_qty,
 coalesce(r.transport_cost,0) as transport_cost,r.final_delivery_date,
 case when o.promised_date<=(select max(date_day) from {{ ref('dim_date') }}) then 1 else 0 end as due,
 case when coalesce(r.on_time_qty,0)>=o.ordered_qty then 1 else 0 end as line_otif,
 coalesce(r.shipped_qty,0)*p.unit_cost_cents/100.0 as shipped_cogs
from {{ ref('stg_order_lines') }} o join rollup r on o.line_id=r.line_id
join {{ ref('dim_product') }} p on p.sku=o.sku where o.status<>'cancelled'
