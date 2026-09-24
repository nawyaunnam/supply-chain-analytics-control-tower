-- Due orders with incomplete delivery, largest missing quantity first.
select order_id,warehouse_id,promised_date,ordered_qty-delivered_qty as outstanding_units,transport_cost
from analytics.fct_order where due=1 and delivered_qty<ordered_qty
order by outstanding_units desc,promised_date;
