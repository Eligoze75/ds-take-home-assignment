import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from utils import tokenize


def build_description_index(dim_item_df, model_name: str = "all-MiniLM-L6-v2"):

    texts = dim_item_df["search_text"].tolist()

    bm25 = BM25Okapi([tokenize(t) for t in texts])

    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, normalize_embeddings=True)

    return {
        "item_ids": dim_item_df["item_id"].tolist(),
        "texts": texts,
        "bm25": bm25,
        "model": model,
        "embeddings": embeddings,
    }


def peach_fuzz(
    query: str,
    desc_index: dict,
    alpha: float = 0.5,
    semantic_floor: float = 0.3,
    top_k: int = 10,
):
    query_vec = desc_index["model"].encode([query], normalize_embeddings=True)[0]
    # Note: cosine similarity is defined as (a · b) / (‖a‖ ‖b‖), but here ‖a‖ = ‖b‖ = 1
    sem_scores = np.clip(desc_index["embeddings"] @ query_vec, 0, 1)

    # gate:
    candidates = np.where(sem_scores >= semantic_floor)[0]
    if len(candidates) == 0:
        return []

    bm25_scores = np.array(desc_index["bm25"].get_scores(tokenize(query)))
    cand_bm25 = bm25_scores[candidates]
    bm25_norm = cand_bm25 / cand_bm25.max() if cand_bm25.max() > 0 else cand_bm25

    fused = alpha * sem_scores[candidates] + (1 - alpha) * bm25_norm

    order = np.argsort(-fused)[:top_k]
    ranked = candidates[order]
    return [
        {
            "item_id": desc_index["item_ids"][i],
            "text": desc_index["texts"][i],
            "score": float(fused[j]),
            "semantic_score": float(sem_scores[i]),
            "bm25_score": float(bm25_norm[j]),
        }
        for j, i in zip(order, ranked)
    ]
