import os
import duckdb
from index import build_index
from router import classify_query
from peach_fuzz import build_description_index
from handlers import DISPATCH

DATA_DIR = os.environ.get("DATA_DIR", "../data")
ROUTER_THRESHOLDS = {
    "category": 87.5,
    "manufacturer": 87.5,
}
CONFIDENCE_THRESHOLD = 0.5

conn = duckdb.connect(f"{DATA_DIR}/warehouse.duckdb", read_only=True)
idx = build_index(conn)
desc_index = build_description_index(conn.sql("SELECT * FROM gold.dim_item").df())


def search_item(query: str) -> list[dict]:
    """Run a single query through the router and the matching handler.
    Returns a list of result dicts, same shape regardless of intent."""
    intent, matched_value, score = classify_query(
        query,
        idx,
        category_threshold=ROUTER_THRESHOLDS["category"],
        manufacturer_threshold=ROUTER_THRESHOLDS["manufacturer"],
    )

    handler = DISPATCH[intent]
    if intent == "description":
        return handler(
            query, matched_value, idx, score, desc_index, CONFIDENCE_THRESHOLD
        )
    return handler(query, matched_value, idx, score)
