"""Splitting and diagnostic helpers shared across price_model approaches
(single regressor, TreeHouse, and the baseline)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def dev_oot_split(
    df: pd.DataFrame, date_col: str, oot_start: str | pd.Timestamp
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Everything before `oot_start` is the dev pool: used for TimeSeriesSplit
    cross-validation / hyperparameter tuning, and for the final training fit.
    Everything from `oot_start` onward is the out-of-time holdout — touched
    exactly once, after the model configuration is already locked in.
    """
    oot_start = pd.Timestamp(oot_start)
    dev = df[df[date_col] < oot_start].copy()
    oot = df[df[date_col] >= oot_start].copy()
    return dev, oot


def prediction_bias(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    """Ratio-based bias diagnostic: predicted / actual.

    1.0 = unbiased. Below 1.0 = systematic underprediction — the failure mode
    expected from a tree ensemble facing a target with a secular upward trend
    it has not fully seen in training (it cannot extrapolate past the range
    of values in its training leaves).
    """
    ratio = np.asarray(y_pred) / np.asarray(y_true)
    return {
        "mean_ratio": float(np.mean(ratio)),
        "median_ratio": float(np.median(ratio)),
        "pct_underpredicted": float(np.mean(ratio < 1.0) * 100),
    }
