{{ config(tags=['intelligence']) }}
select * from {{ ref('fct_forecasts') }} where forecast_date<=training_cutoff or lower_qty<0 or predicted_qty<lower_qty or predicted_qty>upper_qty
