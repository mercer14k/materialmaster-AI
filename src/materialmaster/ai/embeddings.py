"""Embedding backends never own business rules or review state."""

from typing import Protocol

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer


class Embedder(Protocol):
    name: str
    kind: str

    def encode(self, texts: list[str]) -> np.ndarray: ...


class LexicalEmbedder:
    name = "sklearn-hashing-char-3-5/512-v1"
    kind = "lexical_embedding"

    def __init__(self):
        self.vectorizer = HashingVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            n_features=512,
            alternate_sign=False,
            norm="l2",
            dtype=np.float32,
        )

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.vectorizer.transform(texts).toarray()


class SentenceEmbedder:
    kind = "semantic_embedding"

    def __init__(self, model_path: str):
        from sentence_transformers import SentenceTransformer

        self.name = model_path
        self.model = SentenceTransformer(model_path, local_files_only=True, trust_remote_code=False)

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
        )
