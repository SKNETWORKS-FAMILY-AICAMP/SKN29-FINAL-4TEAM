"""BAAI/bge-m3 문서·질의 임베딩 어댑터."""

from typing import Iterable, List, Protocol


class EmbeddingProvider(Protocol):
    dimension: int

    def embed_documents(self, texts: Iterable[str]) -> List[List[float]]: ...
    def embed_query(self, text: str) -> List[float]: ...


class BgeM3EmbeddingClient:
    """sentence-transformers를 지연 로딩하는 bge-m3 구현."""

    model_name = "BAAI/bge-m3"
    dimension = 1024

    def __init__(self, *, device: str = "cpu", model_revision: str | None = None) -> None:
        self.device = device
        self.model_revision = model_revision
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
                revision=self.model_revision,
            )
        return self._model

    def embed_documents(self, texts: Iterable[str]) -> List[List[float]]:
        vectors = self._load_model().encode(
            list(texts), normalize_embeddings=True, show_progress_bar=False
        )
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]
