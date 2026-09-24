select distinct snapshot_date as date_day, {{ month('snapshot_date') }} as month from {{ ref('stg_inventory') }}
