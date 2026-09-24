"""Leakage-safe rolling-origin evaluation plus explainable trailing-window alerts."""

import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from .warehouse import read_table, save_intelligence


def predict(history, horizon, model):
    y = np.asarray(history, dtype=float)
    if len(y) < 28 or not np.isfinite(y).all() or (y < 0).any():
        raise ValueError("Forecast requires at least 28 finite, nonnegative daily observations")
    if model == "seasonal_naive":
        result = np.resize(y[-7:], horizon)
    elif model == "ets":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            fit = ExponentialSmoothing(
                y,
                trend="add",
                damped_trend=True,
                seasonal="add",
                seasonal_periods=7,
                initialization_method="estimated",
            ).fit(optimized=True)
            if not fit.mle_retvals.get("success", True):
                raise ValueError("ETS optimizer did not converge")
            result = fit.forecast(horizon)
    else:
        raise ValueError("Unknown forecast model")
    if not np.isfinite(result).all():
        raise ValueError("Non-finite forecast")
    return np.maximum(result, 0)


def evaluate_series(frame, horizon=14, folds=3):
    frame = frame.sort_values("date_day")
    dates = pd.to_datetime(frame["date_day"])
    if not dates.diff().dropna().eq(pd.Timedelta(days=1)).all():
        raise ValueError("Series must contain one row per calendar day")
    y = frame["demand_qty"].to_numpy(dtype=float)
    if len(y) < 42 + horizon * folds:
        raise ValueError("Not enough history for three non-overlapping backtests")
    backtests = []
    errors = {}
    for model in ["seasonal_naive", "ets"]:
        candidate = []
        try:
            for cutoff in range(len(y) - horizon * folds, len(y), horizon):
                predicted = predict(y[:cutoff], horizon, model)
                for i, value in enumerate(predicted):
                    candidate.append(
                        dict(
                            origin_date=dates.iloc[cutoff - 1].date(),
                            target_date=dates.iloc[cutoff + i].date(),
                            model=model,
                            predicted_qty=float(value),
                            actual_qty=float(y[cutoff + i]),
                        )
                    )
        except (ValueError, FloatingPointError):
            # A failed candidate is excluded rather than mislabeled as an ETS prediction.
            continue
        backtests.extend(candidate)
        errors[model] = sum(abs(r["predicted_qty"] - r["actual_qty"]) for r in candidate)
    winner = min(errors, key=errors.get)
    try:
        future = predict(y, horizon, winner)
    except (ValueError, FloatingPointError):
        winner = "seasonal_naive"
        future = predict(y, horizon, winner)
    # Empirical error bands, not calibrated probabilistic confidence intervals.
    residuals = [abs(r["predicted_qty"] - r["actual_qty"]) for r in backtests if r["model"] == winner]
    band = float(np.quantile(residuals, 0.9))
    forecasts = [
        dict(
            forecast_date=(dates.iloc[-1] + pd.Timedelta(days=i + 1)).date(),
            training_cutoff=dates.iloc[-1].date(),
            model=winner,
            predicted_qty=float(value),
            lower_qty=float(max(0, value - band)),
            upper_qty=float(value + band),
        )
        for i, value in enumerate(future)
    ]
    return forecasts, backtests


def trailing_anomalies(frame, value_col, metric, floor, sku):
    frame = frame.sort_values("date_day")
    values = frame[value_col].to_numpy(dtype=float)
    dates = pd.to_datetime(frame["date_day"])
    alerts = []
    for i in range(14, len(values)):
        if not np.isfinite(values[i]):
            continue
        history = values[max(0, i - 28) : i]
        history = history[np.isfinite(history)]
        if len(history) < 14:
            continue
        median = float(np.median(history))
        scale = max(float(np.median(np.abs(history - median))) * 1.4826, floor)
        score = (values[i] - median) / scale
        if abs(score) >= 4:
            alerts.append(
                dict(
                    sku=sku,
                    warehouse_id=str(frame["warehouse_id"].iloc[i]),
                    date_day=dates.iloc[i].date(),
                    metric=metric,
                    observed=float(values[i]),
                    expected=median,
                    robust_score=float(score),
                    severity="high" if abs(score) >= 7 else "medium",
                )
            )
    return alerts


def score(root, target="local"):
    demand = read_table(root, target, "fct_demand_daily")
    inventory = read_table(root, target, "fct_inventory_daily")
    delivery = read_table(root, target, "fct_delivery_daily")
    result = {"forecasts": [], "backtests": [], "anomalies": []}
    for (sku, wid), group in demand.groupby(["sku", "warehouse_id"], sort=True):
        future, backtests = evaluate_series(group)
        for key, rows in [("forecasts", future), ("backtests", backtests)]:
            result[key].extend(dict(sku=sku, warehouse_id=wid, **r) for r in rows)
        result["anomalies"].extend(trailing_anomalies(group, "demand_qty", "demand_spike", 3.0, sku))
    for (sku, _wid), group in inventory.groupby(["sku", "warehouse_id"], sort=True):
        group = group.sort_values("snapshot_date").rename(columns={"snapshot_date": "date_day"})
        group["inventory_change"] = group["on_hand_qty"].astype(float).diff()
        result["anomalies"].extend(
            trailing_anomalies(group, "inventory_change", "inventory_change", 5.0, sku)
        )
    for _wid, group in delivery.groupby("warehouse_id", sort=True):
        result["anomalies"].extend(
            trailing_anomalies(group, "average_transit_days", "delivery_delay", 0.5, "ALL")
        )
    save_intelligence(root, target, result)
    return {k: len(v) for k, v in result.items()}
