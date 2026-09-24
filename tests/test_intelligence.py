import numpy as np
import pandas as pd
import pytest

from control_tower import intelligence


def test_seasonal_baseline():
    y = np.tile(np.arange(1, 8), 12)
    assert list(intelligence.predict(y, 14, "seasonal_naive")) == list(np.tile(np.arange(1, 8), 2))


def test_backtest_has_no_future_leakage(monkeypatch):
    calls = []

    def predictor(history, horizon, model):
        calls.append((len(history), float(history[-1])))
        return np.repeat(float(history[-1]), horizon)

    monkeypatch.setattr(intelligence, "predict", predictor)
    frame = pd.DataFrame({"date_day": pd.date_range("2025-01-01", periods=100), "demand_qty": np.arange(100)})
    future, backtests = intelligence.evaluate_series(frame)
    assert calls[:3] == [(58, 57.0), (72, 71.0), (86, 85.0)]
    assert all(r["origin_date"] < r["target_date"] for r in backtests)
    assert all(r["forecast_date"] > r["training_cutoff"] for r in future)
    assert all(0 <= r["lower_qty"] <= r["predicted_qty"] <= r["upper_qty"] for r in future)


def test_anomaly_threshold_excludes_current_and_future_values():
    frame = pd.DataFrame(
        {"date_day": pd.date_range("2025-01-01", periods=60), "warehouse_id": "W01", "qty": [10.0] * 60}
    )
    frame.loc[40, "qty"] = 100
    a = intelligence.trailing_anomalies(frame, "qty", "demand", 3, "P001")
    frame.loc[41:, "qty"] = 9999
    b = intelligence.trailing_anomalies(frame, "qty", "demand", 3, "P001")
    assert a[0]["date_day"] == pd.Timestamp("2025-02-10").date()
    assert a[0]["robust_score"] == 30
    assert a[0] == b[0]


def test_ets_produces_finite_nonnegative_forecast():
    y = np.tile([8, 9, 12, 14, 9, 3, 2], 16) + np.linspace(0, 5, 112)
    pred = intelligence.predict(y, 14, "ets")
    assert len(pred) == 14 and np.isfinite(pred).all() and (pred >= 0).all()


def test_reject_incomplete_calendar():
    frame = pd.DataFrame({"date_day": pd.date_range("2025-01-01", periods=100), "demand_qty": 10}).drop(50)
    with pytest.raises(ValueError, match="calendar"):
        intelligence.evaluate_series(frame)
