select s.supplier_name,p.warehouse_id,count(*) as received_orders,
 avg(p.actual_lead_days*1.0) as mean_lead_days,stddev_samp(p.actual_lead_days*1.0) as lead_stddev,
 sum(case when p.lead_variance_days>0 then 1 else 0 end)*1.0/count(*) as late_receipt_rate
from analytics.fct_supplier_receipt p join analytics.dim_supplier s on s.supplier_id=p.supplier_id
where p.received_date is not null group by s.supplier_name,p.warehouse_id order by lead_stddev desc;
