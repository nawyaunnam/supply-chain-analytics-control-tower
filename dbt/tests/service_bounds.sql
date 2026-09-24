select * from {{ ref('mart_service_monthly') }} where otif_rate<0 or otif_rate>1 or first_dispatch_fill_rate<0 or first_dispatch_fill_rate>1
