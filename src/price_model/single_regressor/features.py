"""Feature assembly for the single-regressor model.

The encoders themselves (leakage-safe expanding target encoding) live in
`encoding.py`; this module just wires them together into one feature frame,
for two distinct situations that must not be confused:

- `build_training_features`: retrospective, on historical rows that have a
  known `unit_price_paid` — used once, up front, on the full chronological
  history (dev pool + out-of-time holdout combined) before any splitting.
- `build_inference_features`: real inference on brand-new rows with no known
  price yet — uses the frozen final state from already-fitted encoders.
"""

from __future__ import annotations

import pandas as pd

from .encoding import ExpandingTargetEncoder

TARGET_ENCODE_COLUMNS: tuple[str, ...] = ("item_id", "customer_id", "vendor_id")


def add_time_trend(df: pd.DataFrame, date_col: str, origin: pd.Timestamp) -> pd.Series:
    """Days since a fixed origin date.

    Use the *same* origin for every historical fit and every later inference
    call (e.g. the earliest order_date in the full history you have) — never
    recompute it as `df[date_col].min()` per call, or the trend feature's
    scale silently shifts between training and inference.
    """
    return (df[date_col] - origin).dt.days.astype(float)


def build_training_features(
    df: pd.DataFrame,
    target_col: str,
    date_col: str,
    origin: pd.Timestamp,
    smoothing: float = 10.0,
    group_cols: tuple[str, ...] = TARGET_ENCODE_COLUMNS,
) -> tuple[pd.DataFrame, dict[str, ExpandingTargetEncoder]]:
    """Fit one ExpandingTargetEncoder per column in `group_cols` on the full
    historical `df`, and return the resulting feature frame plus the fitted
    encoders (needed later by `build_inference_features`).

    Call this ONCE on the entire chronological history you have, before doing
    any train / TimeSeriesSplit / out-of-time split — every row's encoding
    only depends on its own past, so splitting the *output* afterwards cannot
    leak, and there is no need to refit per CV fold.
    """
    out = df.copy()
    encoders: dict[str, ExpandingTargetEncoder] = {}
    for col in group_cols:
        enc = ExpandingTargetEncoder(smoothing=smoothing)
        out[f"{col}_te"] = enc.fit_transform(
            df, group_col=col, target_col=target_col, date_col=date_col
        )
        encoders[col] = enc
    out["days_since_start"] = add_time_trend(df, date_col, origin)
    return out, encoders


def build_inference_features(
    df: pd.DataFrame,
    encoders: dict[str, ExpandingTargetEncoder],
    date_col: str,
    origin: pd.Timestamp,
) -> pd.DataFrame:
    """Score brand-new (not-yet-priced) rows with already-fitted encoders.

    Not equivalent to `build_training_features` on the same rows: this uses
    each encoder's frozen final state (as of the most recent history it was
    fit on), it does not keep expanding through `df`.
    """
    out = df.copy()
    for col, enc in encoders.items():
        out[f"{col}_te"] = enc.transform(df, group_col=col)
    out["days_since_start"] = add_time_trend(df, date_col, origin)
    return out
