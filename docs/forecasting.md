# Forecasting and behavior monitoring

The scoring job reads tested warehouse facts, not raw files. Each SKU/warehouse is an independent, complete daily series with zero-demand days preserved. Forecast horizon: 14 days. Candidates: seasonal-naive (repeat last week) and additive, damped-trend ETS with weekly seasonality. Values are clipped to zero.

Three non-overlapping rolling-origin windows each hold out 14 days. At each origin, only prior data is passed to the model; a unit test records training lengths to prove this boundary. The winning candidate minimizes absolute error over those windows (equivalent to WAPE ranking because denominators match). The winner is refit through the observation cutoff for the future forecast. Failed ETS fits are excluded and explicitly fall back to the named seasonal-naive model; results are never mislabeled.

Backtest tables retain origin, target, model, prediction and actual, allowing WAPE/MAE/bias analysis. These same windows select the model, so reported selection performance is not an unbiased final test-set estimate. Before operational adoption, add a separate untouched test period, service-level cost loss, intermittent-demand models such as Croston, and promotion/calendar covariates.

The shaded band is prediction ± the 90th percentile of absolute held-out errors, truncated at zero. It is an empirical error band, **not a guaranteed or calibrated 90% confidence interval**. Inspect one SKU/warehouse at a time; summing bands does not produce calibrated portfolio uncertainty.

Anomalies use only the preceding 28 observations, minimum 14, with `(current − median) / max(1.4826 × MAD, floor)`. Absolute score ≥4 is medium; ≥7 is high. Floors prevent a zero-MAD baseline from exploding: 3 demand units, 5 inventory-change units and 0.5 transit days. Inputs are daily demand, daily inventory movement and warehouse daily average delivered-shipment transit time. Delivery windows count observed delivery days, not missing days as zero. SKU `ALL` identifies warehouse-wide delivery alerts.

The sample intentionally creates stock pressure, a demand shock and a delayed-delivery interval. Alerts are statistical review candidates, not proof of an operational incident. Ordinary replenishments can also trigger inventory alerts; tune thresholds with labeled incidents before claiming precision/recall. Current shipment/inventory tables describe the latest snapshot; this example does not implement historical event-time replay of source revisions.
