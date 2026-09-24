select * from {{ source('raw', 'purchase_orders') }}
