"""BAAI/bge-m3 문서·질의 임베딩 어댑터."""

from threading import Lock
from typing import Iterable, List, Protocol


class EmbeddingProvider(Protocol):
    dimension: int

    def embed_documents(self, texts: Iterable[str]) -> List[List[float]]: ...
    def embed_query(self, text: str) -> List[float]: ...


class BgeM3EmbeddingClient:
    """sentence-transformers를 지연 로딩하는 bge-m3 구현."""

    model_name = "BAAI/bge-m3"
    dimension = 1024
    _warmup_text = "정수기 검색 준비"

    def __init__(self, *, device: str = "cpu", model_revision: str | None = None) -> None:
        self.device = device
        self.model_revision = model_revision
        self._model = None
        self._warmed_up = False
        self._model_lock = Lock()
        self._encode_lock = Lock()

    def _load_model(self):
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer
                    self._model = SentenceTransformer(
                        self.model_name,
                        device=self.device,
                        revision=self.model_revision,
                    )
        return self._model

    def warmup(self) -> None:
        """요청 Timeout 밖에서 모델 로드와 첫 Encode 초기화를 완료한다."""

        model = self._load_model()
        with self._encode_lock:
            if self._warmed_up:
                return
            model.encode(
                [self._warmup_text],
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            self._warmed_up = True

    def embed_documents(self, texts: Iterable[str]) -> List[List[float]]:
        model = self._load_model()
        with self._encode_lock:
            vectors = model.encode(
                list(texts), normalize_embeddings=True, show_progress_bar=False
            )
            self._warmed_up = True
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]
