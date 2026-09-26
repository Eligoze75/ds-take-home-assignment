import os
import duckdb
from index import build_index
from router import classify_query
from handlers import DISPATCH

DATA_DIR = os.environ.get("DATA_DIR", "../data")
ROUTER_THRESHOLDS = {
    "category": 87.5,
    "manufacturer": 87.5,
}


conn = duckdb.connect()
conn.sql(
    f"""
    CREATE VIEW dim_item AS
    SELECT * FROM read_csv_auto('{DATA_DIR}/gold/dim_item.csv')
"""
)

index = build_index(conn)  # built exactly once

all_results = []
for query in queries_to_run:
    intent, matched_value, score = classify_query(
        query,
        index,
        category_threshold=ROUTER_THRESHOLDS["category"],
        manufacturer_threshold=ROUTER_THRESHOLDS["manufacturer"],
    )

    handler = DISPATCH[intent]
    if intent == "description":
        results = handler(
            query, matched_value, index, score, desc_index, CONFIDENCE_THRESHOLD
        )
    else:
        results = handler(query, matched_value, index, score)

    all_results.extend(results)
