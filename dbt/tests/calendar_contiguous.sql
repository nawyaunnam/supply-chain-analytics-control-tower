select 1 as failure from {{ ref('dim_date') }} having count(*) <> {{ days_between('min(date_day)','max(date_day)') }} + 1
