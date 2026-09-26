import re
from rapidfuzz import fuzz, process
from src.item_search.index import ItemSearchIndex


SKU_PATTERN = re.compile(r"^itm-\d{4}$")
MANUFACTURER_PATTERN = re.compile(r"^mfg-\d{2}$")


def classify_query(
    query: str, index: ItemSearchIndex, category_threshold=90, manufacturer_threshold=90
):
    q = query.strip().lower()

    # 1. structural check — no ambiguity possible, so it goes first and short-circuits
    if SKU_PATTERN.fullmatch(q):
        if q in index.sku_lookup:
            return "sku", q.upper(), 100
        return "sku_not_found", q.upper(), 0

    if MANUFACTURER_PATTERN.fullmatch(q):
        return "manufacturer_id", q.upper(), 100

    # 2. closed vocab — whole-string fuzz.ratio, not partial_ratio, so a description
    #    query that merely *contains* a category word doesn't misfire
    cat_match, cat_score, _ = process.extractOne(q, index.categories, scorer=fuzz.ratio)
    if cat_score >= category_threshold:
        return "category", cat_match, cat_score

    mfg_match, mfg_score, _ = process.extractOne(
        q, index.manufacturers, scorer=fuzz.ratio
    )
    if mfg_score >= manufacturer_threshold:
        return "manufacturer", mfg_match, mfg_score

    # 3. catch-all — everything else, including malformed SKU-like queries
    return "description", q, (cat_score, mfg_score)
