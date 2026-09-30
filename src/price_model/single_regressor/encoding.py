"""Leakage-safe expanding (time-respecting) target encoding.

Each row's encoded value is a smoothed average of the target over *strictly
prior* observations of the same category: never the row's own value, and
never anything that happens later in time. That property is what lets the
same encoded columns be reused across every TimeSeriesSplit fold and the
final out-of-time holdout without refitting per fold — a row's encoding
never depends on which split it lands in, only on what happened before it.

Cold-start / thin-history categories shrink toward a global prior that is
itself expanding and one-row-shifted, not a flat whole-dataset mean. Using
`df[target_col].mean()` as that fallback would leak future price levels
(there is a real upward price drift in this data) into early rows.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class ExpandingTargetEncoder:
    """Expanding, shrinkage-smoothed target encoding for one categorical column.

        encoded = (prior_sum_for_category + smoothing * global_prior)
                  / (prior_count_for_category + smoothing)

    `smoothing` is the number of "prior pseudo-observations" assigned to the
    global prior: a category with `smoothing` prior observations of its own
    is weighted 50/50 against the global prior; a category with many more
    observations is dominated by its own history; a brand-new category
    (0 prior observations) falls back entirely to the global prior.
    """

    def __init__(self, smoothing: float = 10.0):
        if smoothing < 0:
            raise ValueError("smoothing must be >= 0")
        self.smoothing = smoothing
        self.group_sum_: dict[str, float] = {}
        self.group_count_: dict[str, int] = {}
        self.global_sum_: float = 0.0
        self.global_count_: int = 0
        self.is_fitted_: bool = False

    def fit_transform(
        self,
        df: pd.DataFrame,
        group_col: str,
        target_col: str,
        date_col: str,
    ) -> pd.Series:
        """Compute leakage-safe expanding encodings for historical data.

        Collapses to one observation per (group, calendar day) before
        expanding — same-day purchases must not see each other, whether they
        share the same category or not. This mirrors the day-level grain
        already used in `gold.t1_baseline_pricing_model`, and it matters here:
        in this dataset ~99% of rows share their date with at least one other
        row, and ~12% share both date and category, so without this step the
        result would depend on arbitrary row order among same-day ties.

        Returns one encoded value per row of `df`, aligned to its original
        index. Also stores the final accumulated totals (grand totals, order
        does not matter for those) so `transform` can later score brand-new,
        not-yet-happened rows.

        Call this ONCE on the full chronological history you have (i.e. dev
        pool + out-of-time holdout combined) before splitting into folds or
        a held-out set — every row's value only depends on strictly-prior
        calendar days, so splitting afterwards cannot introduce leakage.
        """
        d = df.copy()
        # A handful of lines have a genuinely null unit_price_paid (known data
        # issue). They must not count as an observation, and a plain cumsum()
        # does not skip NaN the way an aggregate like SQL's median() does —
        # so we zero-fill for summation and track validity as its own column.
        d["_valid"] = (~d[target_col].isna()).astype(float)
        d["_target_filled"] = d[target_col].fillna(0.0)

        daily_group = (
            d.groupby([group_col, date_col])
            .agg(day_sum=("_target_filled", "sum"), day_count=("_valid", "sum"))
            .reset_index()
            .sort_values(date_col, kind="mergesort")
        )
        grp = daily_group.groupby(group_col)
        daily_group["prior_group_sum"] = grp["day_sum"].cumsum() - daily_group["day_sum"]
        daily_group["prior_group_count"] = grp["day_count"].cumsum() - daily_group["day_count"]

        # Global prior at the same day-level grain, across every group, shifted
        # by one *day* (not one row) so it never includes the current day at all.
        daily_global = (
            d.groupby(date_col)
            .agg(day_sum=("_target_filled", "sum"), day_count=("_valid", "sum"))
            .reset_index()
            .sort_values(date_col, kind="mergesort")
        )
        daily_global["prior_global_sum"] = daily_global["day_sum"].cumsum().shift(1, fill_value=0.0)
        daily_global["prior_global_count"] = daily_global["day_count"].cumsum().shift(1, fill_value=0.0)
        with np.errstate(invalid="ignore", divide="ignore"):
            daily_global["global_prior"] = (
                daily_global["prior_global_sum"] / daily_global["prior_global_count"]
            )
        daily_global.loc[daily_global["prior_global_count"] == 0, "global_prior"] = np.nan

        daily_group = daily_group.merge(
            daily_global[[date_col, "global_prior"]], on=date_col, how="left"
        )
        daily_group["encoded"] = (
            daily_group["prior_group_sum"] + self.smoothing * daily_group["global_prior"]
        ) / (daily_group["prior_group_count"] + self.smoothing)

        # Broadcast the per-(group, day) encoded value back to every original
        # row that shares that (group, day) — left join preserves row order.
        encoded = d.merge(
            daily_group[[group_col, date_col, "encoded"]], on=[group_col, date_col], how="left"
        )["encoded"]
        encoded.index = df.index

        # Persist final grand totals (order-independent) for transform().
        self.group_sum_ = d.groupby(group_col)["_target_filled"].sum().to_dict()
        self.group_count_ = d.groupby(group_col)["_valid"].sum().to_dict()
        self.global_sum_ = float(d["_target_filled"].sum())
        self.global_count_ = float(d["_valid"].sum())
        self.is_fitted_ = True

        return encoded

    def transform(self, df: pd.DataFrame, group_col: str) -> pd.Series:
        """Score brand-new rows (no known target yet) using the frozen final
        state from `fit_transform` — i.e. "as of the most recent history we
        have, what would we expect this category's price to be".

        Use this for real inference on a not-yet-issued PO. For retrospective
        backtesting / model training, use `fit_transform` instead — it is not
        equivalent (it keeps expanding through the historical rows, this does
        not).
        """
        if not self.is_fitted_:
            raise RuntimeError("call fit_transform on historical data first")

        global_prior = (
            self.global_sum_ / self.global_count_ if self.global_count_ else np.nan
        )

        def _encode(group_value: str) -> float:
            g_sum = self.group_sum_.get(group_value, 0.0)
            g_count = self.group_count_.get(group_value, 0)
            return (g_sum + self.smoothing * global_prior) / (g_count + self.smoothing)

        return df[group_col].astype(str).map(_encode)
