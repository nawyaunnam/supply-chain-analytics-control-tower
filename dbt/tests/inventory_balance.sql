select * from {{ ref('fct_inventory_daily') }} where opening_qty+received_qty-shipped_qty<>on_hand_qty or reserved_qty>on_hand_qty
