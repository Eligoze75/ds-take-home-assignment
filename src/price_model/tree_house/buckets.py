"""Absolute price buckets for the router.

Three ordered buckets — low, mid, high — cut at the 1/3 and 2/3 quantiles of
`unit_price_paid` on the dev pool only. The cuts are then applied unchanged
to the holdout.

These are dollar levels, not "cheap for this item". A global tertile is
mostly item identity (a load center is high, a wall plate is low), which is
what a description can actually predict. A bucket defined as the residual
versus the item's own history would be a discount/premium label, and the
description does not know whether this particular purchase was discounted.

The cutpoints do use every dev-pool price, including later dev months. That
nudges early labels by two numbers. It does not put a future price into a
feature, and the out-of-time rows are not in the quantiles at all.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BUCKET_LABELS: dict[int, str] = {0: "low", 1: "mid", 2: "high"}
N_BUCKETS = 3


def fit_tertile_cuts(y: pd.Series) -> tuple[float, float]:
    """Return (q33, q66). Rows at a cut go to the higher bucket (`>=`)."""
    clean = pd.Series(y).dropna().astype(float)
    if clean.empty:
        raise ValueError("cannot cut tertiles on an empty price series")
    # Absolute dollar cuts, shared by every item. Not a within-item residual.
    q33, q66 = np.quantile(clean.to_numpy(), [1.0 / 3.0, 2.0 / 3.0])
    if not np.isfinite(q33) or not np.isfinite(q66) or q33 > q66:
        raise ValueError(f"degenerate tertile cuts: {(q33, q66)}")
    return float(q33), float(q66)


def assign_buckets(y: pd.Series, cuts: tuple[float, float]) -> pd.Series:
    """0 = low, 1 = mid, 2 = high. Null prices stay null."""
    q33, q66 = cuts
    values = pd.Series(y).astype(float)
    buckets = pd.Series(np.nan, index=values.index, dtype="float")
    known = values.notna()
    price = values[known]
    # Ties at a cut go up: price == q33 is mid, price == q66 is high.
    buckets.loc[known] = np.where(price < q33, 0, np.where(price < q66, 1, 2))
    return buckets.astype("Int64")
