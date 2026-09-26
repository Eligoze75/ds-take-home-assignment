from rapidfuzz import fuzz, process
from src.item_search.peach_fuzz import peach_fuzz


def handle_sku(query, matched_value, index, score):
    return [
        {
            "query": query,
            "intent": "sku",
            "matched_value": matched_value,
            "item_id": matched_value,
            "item_score": 1.0,
            "route_score": score,
        }
    ]


def handle_sku_not_found(query, matched_value, index, score, top_k=5):
    # near-SKU fallback: edit distance against the 358 real item_ids
    candidates = process.extract(
        matched_value, list(index.sku_lookup.keys()), scorer=fuzz.ratio, limit=top_k
    )
    return [
        {
            "query": query,
            "intent": "sku_not_found",
            "matched_value": matched_value,
            "item_id": item_id.upper(),
            "item_score": sim / 100,
            "route_score": score,
        }
        for item_id, sim, _ in candidates
    ]


def handle_category(query, matched_value, index, score):
    items = index.items_by_category.get(
        matched_value, []
    )  # sorted by popularity — see note below
    return [
        {
            "query": query,
            "intent": "category",
            "matched_value": matched_value,
            "item_id": item_id,
            "item_score": None,
            "route_score": score,
        }
        for item_id in items
    ]


def handle_manufacturer(query, matched_value, index, score):
    items = index.items_by_manufacturer.get(matched_value, [])
    return [
        {
            "query": query,
            "intent": "manufacturer",
            "matched_value": matched_value,
            "item_id": item_id,
            "item_score": None,
            "route_score": score,
        }
        for item_id in items
    ]


def handle_manufacturer_id(query, matched_value, index, score):
    items = index.items_by_manufacturer_id.get(matched_value, [])
    return [
        {
            "query": query,
            "intent": "manufacturer_id",
            "matched_value": matched_value,
            "item_id": item_id,
            "item_score": None,
            "route_score": score,
        }
        for item_id in items
    ]


def handle_description(query, matched_value, index, score, desc_index, threshold):
    results = peach_fuzz(matched_value, desc_index)
    return [
        {
            "query": query,
            "intent": "description",
            "matched_value": matched_value,
            "item_id": r["item_id"],
            "item_score": r["score"],
            "route_score": None,
        }
        for r in results
        if r["score"] >= threshold
    ]


DISPATCH = {
    "sku": handle_sku,
    "sku_not_found": handle_sku_not_found,
    "category": handle_category,
    "manufacturer": handle_manufacturer,
    "manufacturer_id": handle_manufacturer_id,
    "description": handle_description,
}
