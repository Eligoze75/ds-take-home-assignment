"""Description embeddings for item identity, in place of `item_id`.

`all-MiniLM-L6-v2` is the encoder Task 2 already settled on. A purchase line
does not get its own vector: every row with the same description shares one,
then PCA compresses the 384 dimensions down to something a tree can split on
without the embedding drowning the customer / vendor / time features.

PCA is fit on descriptions that appear before the out-of-time cut only. It
sees text, never price. A description that shows up for the first time in the
holdout is projected into that same space.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from src.item_search.config import EMBEDDING_MODEL


class DescriptionEmbedder:
    def __init__(self, n_components: int = 16, model_name: str = EMBEDDING_MODEL):
        if n_components < 1:
            raise ValueError("n_components must be >= 1")
        self.n_components = n_components
        self.model_name = model_name
        self.pca_: PCA | None = None
        self._encoder = None
        self._cache: dict[str, np.ndarray] = {}

    @property
    def component_columns(self) -> list[str]:
        if self.pca_ is None:
            raise RuntimeError("call fit before reading component names")
        return [f"emb_{i:02d}" for i in range(self.pca_.n_components_)]

    def fit(self, texts: pd.Series) -> DescriptionEmbedder:
        unique = _unique_texts(texts)
        if len(unique) < 2:
            raise ValueError("need at least two distinct descriptions to fit PCA")
        matrix = self._encode(unique)  # one 384-d vector per distinct description
        k = min(self.n_components, len(unique), matrix.shape[1])
        self.pca_ = PCA(n_components=k, svd_solver="full", random_state=42)
        self.pca_.fit(matrix)
        for text, row in zip(unique, self.pca_.transform(matrix)):
            self._cache[text] = row  # reuse the projection; descriptions repeat
        return self

    def transform(self, texts: pd.Series) -> pd.DataFrame:
        if self.pca_ is None:
            raise RuntimeError("call fit before transform")
        as_str = texts.map(_as_text)
        unseen = [text for text in pd.unique(as_str) if text not in self._cache]
        if unseen:
            # New holdout text is projected into the PCA fit on earlier descriptions.
            projected = self.pca_.transform(self._encode(unseen))
            for text, row in zip(unseen, projected):
                self._cache[text] = row
        matrix = np.vstack([self._cache[text] for text in as_str])
        return pd.DataFrame(matrix, index=texts.index, columns=self.component_columns)

    def _encode(self, texts: list[str]) -> np.ndarray:
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer

            self._encoder = SentenceTransformer(self.model_name)
        return np.asarray(
            self._encoder.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        )


def _as_text(value: object) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return str(value).strip()


def _unique_texts(texts: pd.Series) -> list[str]:
    return [text for text in pd.unique(texts.map(_as_text)) if text]
