select supplier_id,count(*) as due_purchase_orders,sum(supplier_otif)*1.0/count(*) as otif_rate,
 avg(actual_lead_days*1.0) as average_lead_days,avg(lead_variance_days*1.0) as mean_lead_variance_days,
 stddev_samp(actual_lead_days*1.0) as lead_time_stddev,
 sum(case when received_date is null then 1 else 0 end) as overdue_unreceived
from {{ ref('fct_supplier_receipt') }} where due=1 group by supplier_id
