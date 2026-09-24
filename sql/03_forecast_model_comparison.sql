-- Lower WAPE is better. Ratios recomputed from underlying sums rather than averaged across SKUs.
select model,count(distinct origin_date) as folds,
 sum(abs(predicted_qty-actual_qty))/nullif(sum(actual_qty),0) as wape,
 avg(abs(predicted_qty-actual_qty)) as mae,
 sum(predicted_qty-actual_qty)/nullif(sum(actual_qty),0) as bias
from analytics.fct_backtests group by model order by wape;
