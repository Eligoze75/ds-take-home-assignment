"""Feature assembly for TreeHouse.

Two matrices, because the two stages do not want the same encoding:

- Router (ordinal bucket): expanding WOE of customer, vendor, category, and
  unit of measure. One WOE per cumulative cut, since WOE is target-specific.
- Expert (dollar price): expanding target encoding of those same columns,
  against `unit_price_paid`, same encoder the single regressor uses.

Shared, and not encoded further: MiniLM principal components, the numeric
specs parsed from the description, and `days_since_start`.
`item_id` is not a feature. The description is standing in for it.
Order quantity is left out: it may not be known when a price is quoted,
and the single regressor does not use it either.

Call `build_training_features` once on the full chronological history
(dev pool and out-of-time holdout together) before splitting. Encodings use
strictly earlier days only, so the split afterwards does not leak.
"""

from __future__ import annotations

import pandas as pd

from src.price_model.single_regressor.encoding import ExpandingTargetEncoder
from src.price_model.single_regressor.features import add_time_trend
from src.price_model.tree_house.attributes import SPEC_COLUMNS, parse_descriptions
from src.price_model.tree_house.buckets import assign_buckets, fit_tertile_cuts
from src.price_model.tree_house.embeddings import DescriptionEmbedder
from src.price_model.tree_house.encoding import ExpandingWoeEncoder

CATEGORICAL_COLUMNS: tuple[str, ...] = (
    "customer_id",
    "vendor_id",
    "category",
    "unit_of_measure",
)
# Cumulative cuts of an ordinal bucket in {0, 1, 2}: P(Y >= 1), P(Y >= 2).
WOE_CUTS: tuple[str, ...] = ("ge1", "ge2")
SHARED_NUMERIC: tuple[str, ...] = ("days_since_start",)


def text_for_embedding(
    df: pd.DataFrame,
    text_col: str = "description",
    fallback_text_col: str = "search_text",
) -> pd.Series:
    """Description, or the search text when the description is blank.

    Two catalog items (`ITM-0120`, `ITM-0901`) have an empty description.
    `search_text` still carries category and manufacturer.
    """
    description = df[text_col].fillna("").astype(str).str.strip()
    if fallback_text_col not in df.columns:
        return description
    fallback = df[fallback_text_col].fillna("").astype(str).str.strip()
    return description.where(description.ne(""), fallback)


def build_training_features(
    df: pd.DataFrame,
    *,
    target_col: str = "unit_price_paid",
    date_col: str = "order_date",
    origin: pd.Timestamp,
    oot_start: str | pd.Timestamp,
    smoothing: float = 10.0,
    woe_smoothing: float = 0.5,
    n_components: int = 16,
    categorical_cols: tuple[str, ...] = CATEGORICAL_COLUMNS,
) -> tuple[pd.DataFrame, dict]:
    """Full historical feature frame, plus everything `build_inference_features` needs.

    Tertile cuts are fit on rows dated strictly before `oot_start`.
    """
    out = df.copy()
    # A tuple is one column label, not a list of them.
    cols = list(categorical_cols)
    out[cols] = out[cols].fillna("__missing__")
    texts = text_for_embedding(out)

    # Item identity as 16 PCA components. Fit on pre-holdout text only.
    embedder = DescriptionEmbedder(n_components=n_components)
    dev_mask = out[date_col] < pd.Timestamp(oot_start)
    embedder.fit(texts[dev_mask])
    components = embedder.transform(texts)
    out = pd.concat([out, components], axis=1)

    # Numeric specs (AWG, amps, inches, ...) parsed from the same text.
    specs = parse_descriptions(out["description"] if "description" in out.columns else texts)
    out = pd.concat([out, specs], axis=1)

    out["days_since_start"] = add_time_trend(out, date_col, origin)

    # Freeze low/mid/high cuts on the dev pool, then label every priced row.
    priced = out[target_col].notna()
    cuts = fit_tertile_cuts(out.loc[priced & dev_mask, target_col])
    out["price_bucket"] = assign_buckets(out[target_col], cuts)

    # Router features: one WOE per category column and per cumulative cut.
    woe_encoders: dict[tuple[str, str], ExpandingWoeEncoder] = {}
    bucket = out["price_bucket"].astype("float")
    out["_ge1"] = (bucket >= 1).where(bucket.notna(), other=pd.NA)
    out["_ge2"] = (bucket >= 2).where(bucket.notna(), other=pd.NA)
    for cut, label_col in zip(WOE_CUTS, ("_ge1", "_ge2")):
        for col in categorical_cols:
            enc = ExpandingWoeEncoder(smoothing=woe_smoothing)
            out[f"{col}_woe_{cut}"] = enc.fit_transform(
                out, group_col=col, target_col=label_col, date_col=date_col
            )
            woe_encoders[(col, cut)] = enc
    out = out.drop(columns=["_ge1", "_ge2"])

    # Expert features: mean price of the same columns, still strictly prior.
    target_encoders: dict[str, ExpandingTargetEncoder] = {}
    for col in categorical_cols:
        enc = ExpandingTargetEncoder(smoothing=smoothing)
        out[f"{col}_te"] = enc.fit_transform(
            out, group_col=col, target_col=target_col, date_col=date_col
        )
        target_encoders[col] = enc

    # Embeddings, specs, and time go to both stages unchanged.
    shared = list(embedder.component_columns) + list(SPEC_COLUMNS) + list(SHARED_NUMERIC)
    router_cols = {
        cut: [f"{col}_woe_{cut}" for col in categorical_cols] + shared for cut in WOE_CUTS
    }
    expert_cols = [f"{col}_te" for col in categorical_cols] + shared

    artifacts = {
        "embedder": embedder,
        "woe_encoders": woe_encoders,
        "target_encoders": target_encoders,
        "cuts": cuts,
        "origin": origin,
        "categorical_cols": categorical_cols,
        "router_cols": router_cols,
        "expert_cols": expert_cols,
        "date_col": date_col,
    }
    return out, artifacts


def build_inference_features(
    df: pd.DataFrame,
    artifacts: dict,
    *,
    date_col: str | None = None,
    origin: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Score a not-yet-priced line from the frozen encoders and the fitted PCA.

    Unlike `build_training_features`, this does not look at `unit_price_paid`
    and does not assign a bucket. The router predicts the bucket.
    """
    date_col = date_col or artifacts["date_col"]
    origin = artifacts["origin"] if origin is None else origin
    categorical_cols = artifacts["categorical_cols"]

    out = df.copy()
    out[list(categorical_cols)] = out[list(categorical_cols)].fillna("__missing__")
    texts = text_for_embedding(out)
    out = pd.concat([out, artifacts["embedder"].transform(texts)], axis=1)
    description = out["description"] if "description" in out.columns else texts
    out = pd.concat([out, parse_descriptions(description)], axis=1)
    out["days_since_start"] = add_time_trend(out, date_col, origin)

    # Apply the frozen historical counts. No price, no bucket, on this path.
    for (col, cut), enc in artifacts["woe_encoders"].items():
        out[f"{col}_woe_{cut}"] = enc.transform(out, group_col=col)
    for col, enc in artifacts["target_encoders"].items():
        out[f"{col}_te"] = enc.transform(out, group_col=col)
    return out
