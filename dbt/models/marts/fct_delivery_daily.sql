select warehouse_id,delivered_date as date_day,
 avg(transit_days*1.0) as average_transit_days,count(*) as delivered_shipments
from {{ ref('fct_shipment') }} where delivered_date is not null group by warehouse_id,delivered_date
