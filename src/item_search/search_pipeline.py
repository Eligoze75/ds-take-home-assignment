import os
from pathlib import Path

import duckdb
from src.item_search.config import EMBEDDING_MODEL
from src.item_search.index import build_index
from src.item_search.router import classify_query
from src.item_search.peach_fuzz import build_description_index
from src.item_search.handlers import DISPATCH

_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = os.environ.get("DATA_DIR", str(_ROOT / "data"))

conn = duckdb.connect(f"{DATA_DIR}/warehouse.duckdb", read_only=True)
conn.execute("SET search_path = 'gold'")
idx = build_index(conn)
desc_index = build_description_index(
    conn.sql("SELECT * FROM gold.dim_item").df(),
    model_name=EMBEDDING_MODEL,
)


def search_item(query: str) -> list[dict]:
    """Run a single query through the router and the matching handler.
    Returns a list of result dicts, same shape regardless of intent."""
    intent, matched_value, score = classify_query(query, idx)

    handler = DISPATCH[intent]
    if intent == "description":
        return handler(query, matched_value, idx, score, desc_index)
    return handler(query, matched_value, idx, score)
