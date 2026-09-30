"""TreeHouse: ordinal price-bucket router, then a specialist regressor per bucket.

Stage 1 is two binary classifiers, not a 3-class softmax. Softmax treats
"low vs high" as the same kind of mistake as "low vs mid". The cumulative
pair asks P(bucket >= mid) and P(bucket == high), which is the Frank and Hall
reduction: predicting low when the truth is high means both classifiers are
wrong, and the reconstructed middle probability is the overlap of the two.

Stage 2 fits one `XGBRegressor` per true bucket, on `log1p(unit_price_paid)`.
At prediction time the router picks the expert. `predict_given_bucket` skips
the router so a bad route can be separated from a bad expert.

Category is not a stage. It is already on the line.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRegressor

from src.price_model.tree_house.buckets import BUCKET_LABELS, N_BUCKETS

_DEFAULT_CLASSIFIER = {
    "n_estimators": 300,
    "max_depth": 4,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "eval_metric": "logloss",
    "random_state": 42,
    "n_jobs": -1,
}
_DEFAULT_REGRESSOR = {
    "n_estimators": 500,
    "max_depth": 6,
    "learning_rate": 0.03,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "n_jobs": -1,
}


class TreeHouse:
    def __init__(
        self,
        classifier_params: dict | None = None,
        regressor_params: dict | None = None,
        min_bucket_rows: int = 30,
    ):
        self.classifier_params = {**_DEFAULT_CLASSIFIER, **(classifier_params or {})}
        self.regressor_params = {**_DEFAULT_REGRESSOR, **(regressor_params or {})}
        self.min_bucket_rows = min_bucket_rows
        self.router_cols_: dict[str, list[str]] | None = None
        self.expert_cols_: list[str] | None = None
        self.cuts_: tuple[float, float] | None = None  # frozen tertile edges, not used at score time
        self.clf_ge1_: XGBClassifier | None = None  # P(bucket >= mid)
        self.clf_ge2_: XGBClassifier | None = None  # P(bucket == high)
        self.experts_: dict[int, XGBRegressor] = {}  # one price model per tertile
        self.fallback_: XGBRegressor | None = None  # all-rows model for a thin bucket

    def fit(
        self,
        df: pd.DataFrame,
        y: pd.Series,
        router_cols: dict[str, list[str]],
        expert_cols: list[str],
        bucket: pd.Series | None = None,
        cuts: tuple[float, float] | None = None,
    ) -> TreeHouse:
        """Fit the router on `bucket` and one expert per bucket that has enough rows.

        `bucket` is the true tertile (0/1/2), already assigned with cuts that
        were frozen before this fit. Rows with a null bucket or a null price
        are skipped. Experts see the true bucket, never the router's guess.
        """
        self.router_cols_ = router_cols
        self.expert_cols_ = expert_cols
        self.cuts_ = cuts

        y = pd.Series(y).astype(float)
        if bucket is None:
            if "price_bucket" not in df.columns:
                raise KeyError("pass `bucket`, or a frame that already has price_bucket")
            bucket = df["price_bucket"]
        bucket = pd.Series(bucket)

        usable = y.notna() & bucket.notna()
        frame = df.loc[usable]
        y = y.loc[usable]
        bucket_int = bucket.loc[usable].astype(int)

        # Stage 1: two binary cuts. ge1 is "at least mid", ge2 is "high".
        self.clf_ge1_ = XGBClassifier(**dict(self.classifier_params))
        self.clf_ge2_ = XGBClassifier(**dict(self.classifier_params))
        self.clf_ge1_.fit(frame[router_cols["ge1"]], (bucket_int >= 1).astype(int))
        self.clf_ge2_.fit(frame[router_cols["ge2"]], (bucket_int >= 2).astype(int))

        # Stage 2 trains on log price so a few expensive lines do not dominate.
        log_y = np.log1p(y.to_numpy())
        self.fallback_ = self._new_regressor()
        self.fallback_.fit(frame[expert_cols], log_y)

        # Each expert sees only its true bucket, never the router's guess.
        self.experts_ = {}
        for level in range(N_BUCKETS):
            mask = bucket_int.to_numpy() == level
            if int(mask.sum()) < self.min_bucket_rows:
                continue  # too few rows: predict() will use fallback_
            expert = self._new_regressor()
            expert.fit(frame.loc[mask, expert_cols], log_y[mask])
            self.experts_[level] = expert
        return self

    def route(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """Predicted bucket and a (n, 3) probability matrix, columns low/mid/high.

        If the two cumulative models disagree (`P(high) > P(mid or high)`),
        the high probability is clipped down so the three class probabilities
        stay non-negative and sum to 1.
        """
        self._check_fitted()
        p_ge1 = self.clf_ge1_.predict_proba(df[self.router_cols_["ge1"]])[:, 1]
        p_ge2 = self.clf_ge2_.predict_proba(df[self.router_cols_["ge2"]])[:, 1]
        # The two models can disagree; clip so P(high) cannot exceed P(mid or high).
        p_ge2 = np.minimum(p_ge2, p_ge1)
        # Recover the three classes: low, mid = overlap, high.
        probabilities = np.column_stack([1.0 - p_ge1, p_ge1 - p_ge2, p_ge2])
        return probabilities.argmax(axis=1).astype(int), probabilities

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Dollar unit price. The router chooses the expert."""
        buckets, _ = self.route(df)
        return self.predict_given_bucket(df, buckets)

    def predict_given_bucket(self, df: pd.DataFrame, bucket: pd.Series | np.ndarray) -> np.ndarray:
        """Dollar unit price using a supplied bucket instead of the router.

        Pass the true tertile to measure the experts with a perfect route.
        """
        self._check_fitted()
        chosen = np.asarray(bucket).astype(int)
        log_price = np.empty(len(df), dtype=float)
        expert_x = df[self.expert_cols_]
        for level in range(N_BUCKETS):
            positions = np.flatnonzero(chosen == level)
            if len(positions) == 0:
                continue
            expert = self.experts_.get(level, self.fallback_)  # thin bucket has no specialist
            log_price[positions] = expert.predict(expert_x.iloc[positions])
        return np.expm1(log_price)  # undo log1p, back to dollars

    def predict_detail(self, df: pd.DataFrame) -> pd.DataFrame:
        """Price, routed bucket, and class probabilities, aligned to `df.index`."""
        buckets, probabilities = self.route(df)
        return pd.DataFrame(
            {
                "predicted_price": self.predict_given_bucket(df, buckets),
                "predicted_bucket": buckets,
                "predicted_bucket_label": [BUCKET_LABELS[int(b)] for b in buckets],
                "p_low": probabilities[:, 0],
                "p_mid": probabilities[:, 1],
                "p_high": probabilities[:, 2],
            },
            index=df.index,
        )

    def _new_regressor(self) -> XGBRegressor:
        return XGBRegressor(**dict(self.regressor_params))

    def _check_fitted(self) -> None:
        if self.clf_ge1_ is None or self.fallback_ is None:
            raise RuntimeError("call fit before predict")
