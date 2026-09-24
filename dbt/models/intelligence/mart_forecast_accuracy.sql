select sku,warehouse_id,model,count(distinct origin_date) as folds,count(*) as predictions,
 sum(abs(predicted_qty-actual_qty))/nullif(sum(actual_qty),0) as wape,
 avg(abs(predicted_qty-actual_qty)) as mae,
 sum(predicted_qty-actual_qty)/nullif(sum(actual_qty),0) as bias
from {{ ref('fct_backtests') }} group by sku,warehouse_id,model
