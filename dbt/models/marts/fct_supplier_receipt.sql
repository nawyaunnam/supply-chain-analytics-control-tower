select p.*,
 {{ days_between('placed_date','received_date') }} as actual_lead_days,
 {{ days_between('expected_date','received_date') }} as lead_variance_days,
 case when expected_date<=(select max(date_day) from {{ ref('dim_date') }}) then 1 else 0 end as due,
 case when received_date<=expected_date and received_qty>=ordered_qty then 1 else 0 end as supplier_otif
from {{ ref('stg_purchase_orders') }} p
