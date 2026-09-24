select i.*,i.on_hand_qty-i.reserved_qty as available_qty,
 i.on_hand_qty*p.unit_cost_cents/100.0 as inventory_value,
 i.shipped_qty*p.unit_cost_cents/100.0 as shipped_cogs,
 case when i.on_hand_qty=0 then 1 else 0 end as stockout,
 case when i.on_hand_qty-i.reserved_qty<i.safety_stock then 1 else 0 end as below_safety
from {{ ref('stg_inventory') }} i join {{ ref('dim_product') }} p on p.sku=i.sku
