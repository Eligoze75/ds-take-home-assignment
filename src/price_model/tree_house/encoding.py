"""Expanding, time-respecting weight-of-evidence encoding.

WOE is the right encoding for the router because the router's target is a
class, not a dollar amount. It is not the right encoding for the expert
regressors — those keep using `ExpandingTargetEncoder` on the price.

Same two bugs the target encoder already had to fix, so the same two rules:

- A null label is not an observation. It must not enter the counts.
- Same-day rows must not see each other. Counts are collapsed to one
  observation per (category, calendar day) before the expansion, then
  broadcast back. About 99% of rows share their date with another row, so
  skipping this step makes the encoding depend on arbitrary row order.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _woe(event: float, nonevent: float, event_total: float, nonevent_total: float, smoothing: float) -> float:
    return float(
        np.log(event + smoothing)
        - np.log(event_total + smoothing)
        - np.log(nonevent + smoothing)
        + np.log(nonevent_total + smoothing)
    )


class ExpandingWoeEncoder:
    """WOE of one categorical column against a binary target, strictly prior.

        WOE = log((n_event + a) / (N_event + a)) - log((n_nonevent + a) / (N_nonevent + a))

    `a` (smoothing) is a pseudo-count on both the category and the global
    total, so a category that has only ever been one class cannot produce
    an infinite weight. A category with no history at all encodes to 0,
    the "no evidence" value, rather than NaN.
    """

    def __init__(self, smoothing: float = 0.5):
        if smoothing <= 0:
            raise ValueError("smoothing must be > 0 (WOE divides by it in the empty case)")
        self.smoothing = smoothing
        self.group_event_: dict[str, float] = {}
        self.group_nonevent_: dict[str, float] = {}
        self.global_event_: float = 0.0
        self.global_nonevent_: float = 0.0
        self.is_fitted_: bool = False

    def fit_transform(
        self,
        df: pd.DataFrame,
        group_col: str,
        target_col: str,
        date_col: str,
    ) -> pd.Series:
        """Expanding WOE for historical rows. See `ExpandingTargetEncoder.fit_transform`.

        Call once on the full chronological history, after the class labels
        are already assigned, and before the dev / out-of-time split. A row's
        value depends only on earlier calendar days.
        """
        d = df[[group_col, target_col, date_col]].copy()
        d[group_col] = d[group_col].astype(str)
        # Binary target in {0, 1}. Null labels are not observations.
        d["_valid"] = (~d[target_col].isna()).astype(float)
        label = d[target_col].fillna(0.0).astype(float)
        d["_event"] = label * d["_valid"]
        d["_nonevent"] = (1.0 - label) * d["_valid"]

        # Collapse to one row per (category, day) so same-day lines cannot see each other.
        daily_group = (
            d.groupby([group_col, date_col], sort=False)
            .agg(day_event=("_event", "sum"), day_nonevent=("_nonevent", "sum"))
            .reset_index()
            .sort_values(date_col, kind="mergesort")
        )
        grp = daily_group.groupby(group_col, sort=False)
        # cumsum includes today; subtract it to keep only strictly earlier days.
        daily_group["prior_event"] = grp["day_event"].cumsum() - daily_group["day_event"]
        daily_group["prior_nonevent"] = grp["day_nonevent"].cumsum() - daily_group["day_nonevent"]

        daily_global = (
            d.groupby(date_col, sort=False)
            .agg(day_event=("_event", "sum"), day_nonevent=("_nonevent", "sum"))
            .reset_index()
            .sort_values(date_col, kind="mergesort")
        )
        # Global base rate as of the previous calendar day.
        daily_global["prior_event"] = daily_global["day_event"].cumsum().shift(1, fill_value=0.0)
        daily_global["prior_nonevent"] = daily_global["day_nonevent"].cumsum().shift(1, fill_value=0.0)

        daily_group = daily_group.merge(
            daily_global[[date_col, "prior_event", "prior_nonevent"]],
            on=date_col,
            how="left",
            suffixes=("", "_global"),
        )
        # log(category rate) - log(global rate), with a pseudo-count so a one-class history stays finite.
        a = self.smoothing
        daily_group["encoded"] = (
            np.log(daily_group["prior_event"] + a)
            - np.log(daily_group["prior_event_global"] + a)
            - np.log(daily_group["prior_nonevent"] + a)
            + np.log(daily_group["prior_nonevent_global"] + a)
        )

        encoded = d.merge(
            daily_group[[group_col, date_col, "encoded"]],
            on=[group_col, date_col],
            how="left",
        )["encoded"]
        encoded.index = df.index

        # Final counts, used later by transform() on rows that were not in this history.
        self.group_event_ = d.groupby(group_col)["_event"].sum().to_dict()
        self.group_nonevent_ = d.groupby(group_col)["_nonevent"].sum().to_dict()
        self.global_event_ = float(d["_event"].sum())
        self.global_nonevent_ = float(d["_nonevent"].sum())
        self.is_fitted_ = True
        return encoded

    def transform(self, df: pd.DataFrame, group_col: str) -> pd.Series:
        """Frozen WOE for a not-yet-priced row, using the final historical counts."""
        if not self.is_fitted_:
            raise RuntimeError("call fit_transform on historical data first")

        def _encode(group_value: str) -> float:
            return _woe(
                self.group_event_.get(group_value, 0.0),
                self.group_nonevent_.get(group_value, 0.0),
                self.global_event_,
                self.global_nonevent_,
                self.smoothing,
            )

        return df[group_col].astype(str).map(_encode)
