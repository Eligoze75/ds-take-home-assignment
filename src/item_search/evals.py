"""Score search_item on the shipped queries and on query_tests.csv.

Each query is weighted equally (macro average). Recall is the share of
expected items that came back. Precision is the share of returned items
that were expected. An empty expected set is a no-match query: returning
anything drops precision, and returning nothing scores as a perfect result.
MRR and MAP skip those queries, because there is no relevant item to rank.
"""

import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = Path(os.environ.get("DATA_DIR", _ROOT / "data"))
DATASETS = {
    "search_queries": _DATA_DIR / "search_queries.csv",
    "query_tests": _DATA_DIR / "query_tests.csv",
}


def evaluate_search() -> pd.DataFrame:
    """Run search_item on both query files and return one metrics row each."""
    from src.item_search.search_pipeline import search_item

    search_item("thhn wire")  # warm the description encoder; not scored

    rows = [_evaluate_file(name, path, search_item) for name, path in DATASETS.items()]
    table = pd.DataFrame(rows).set_index("dataset")
    table[["recall", "precision", "f1", "mrr", "map"]] = table[
        ["recall", "precision", "f1", "mrr", "map"]
    ].round(4)
    table[["latency_ms", "latency_p95_ms"]] = table[
        ["latency_ms", "latency_p95_ms"]
    ].round(2)
    return table


def _evaluate_file(name: str, path: Path, search_item) -> dict:
    queries = pd.read_csv(path)
    per_query = [_score_query(row, search_item) for _, row in queries.iterrows()]
    scored = pd.DataFrame(per_query)
    ranked = scored.dropna(subset=["reciprocal_rank"])

    return {
        "dataset": name,
        "n_queries": len(scored),
        "recall": scored["recall"].mean(),
        "precision": scored["precision"].mean(),
        "f1": scored["f1"].mean(),
        "mrr": ranked["reciprocal_rank"].mean(),
        "map": ranked["average_precision"].mean(),
        "latency_ms": scored["latency_ms"].mean(),
        "latency_p95_ms": float(np.percentile(scored["latency_ms"], 95)),
    }


def _score_query(row: pd.Series, search_item) -> dict:
    expected = _parse_ids(row["expected_item_ids"])
    started = time.perf_counter()
    retrieved = _retrieved_ids(search_item(row["query"]))
    latency_ms = (time.perf_counter() - started) * 1000

    expected_set = set(expected)
    hit_count = sum(item_id in expected_set for item_id in retrieved)

    if not retrieved and not expected:
        precision, recall = 1.0, 1.0
    elif not retrieved:
        precision, recall = 0.0, 0.0
    else:
        precision = hit_count / len(retrieved)
        recall = hit_count / len(expected) if expected else 1.0

    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return {
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "reciprocal_rank": _reciprocal_rank(retrieved, expected_set),
        "average_precision": _average_precision(retrieved, expected_set),
        "latency_ms": latency_ms,
    }


def _parse_ids(value) -> list[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


def _retrieved_ids(results: list[dict]) -> list[str]:
    seen = set()
    ordered = []
    for result in results:
        item_id = result["item_id"]
        if item_id not in seen:
            seen.add(item_id)
            ordered.append(item_id)
    return ordered


def _reciprocal_rank(retrieved: list[str], expected: set[str]) -> float | None:
    if not expected:
        return None
    for rank, item_id in enumerate(retrieved, start=1):
        if item_id in expected:
            return 1.0 / rank
    return 0.0


def _average_precision(retrieved: list[str], expected: set[str]) -> float | None:
    if not expected:
        return None
    hits = 0
    precision_sum = 0.0
    for rank, item_id in enumerate(retrieved, start=1):
        if item_id in expected:
            hits += 1
            precision_sum += hits / rank
    return precision_sum / len(expected)
