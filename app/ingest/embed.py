"""텍스트 → dense 벡터. 교체 가능한 Embedder 인터페이스(ADR-005).

모델 교체(BGE-M3 ↔ OpenAI)가 색인/검색 코드 변경 없이 가능하도록,
소비 측(색인·검색)은 구체 클래스가 아니라 `Embedder` 프로토콜에만 의존한다.
"""
from __future__ import annotations

from typing import Protocol


class Embedder(Protocol):
    dim: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class BGEM3Embedder:
    """FlagEmbedding BGE-M3 dense 임베딩. dim=1024.

    dense_vecs는 BGE-M3가 내부에서 L2 정규화해 반환한다(cosine=inner product).
    ponytail: 이미 단위벡터라 재정규화하지 않음. 모델이 정규화를 멈추면 여기서 추가.
    """

    dim = 1024

    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        # 무거운 torch/FlagEmbedding 스택은 지연 로드 — 계약 테스트와 오프라인 import가
        # 모델 다운로드 없이 가능해야 한다(parse/chunk 선례).
        from FlagEmbedding import BGEM3FlagModel

        self._model = BGEM3FlagModel(model_name, use_fp16=True)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        dense = self._model.encode(texts, return_dense=True)["dense_vecs"]
        return [v.tolist() for v in dense]


def get_embedder() -> Embedder:
    """config.embedding_model 기반 팩토리. 소비 측은 반환값(Embedder)에만 의존한다."""
    from app.config import get_settings

    return BGEM3Embedder(model_name=get_settings().embedding_model)
