import pytest

from app.ingest.embed import Embedder


class FakeEmbedder:
    """고정 dim의 계약 검증용 — 무거운 모델 로드 없이 인터페이스만 확인."""

    dim = 8

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dim for _ in texts]


def test_embedder_contract():
    emb: Embedder = FakeEmbedder()
    texts = ["안녕하세요", "hello world", "제품코드 A-100"]

    vecs = emb.embed_texts(texts)

    assert len(vecs) == len(texts)              # 개수 == 입력 수
    assert all(len(v) == emb.dim for v in vecs)  # 각 벡터 길이 == dim


@pytest.mark.integration
def test_bge_m3_real_embedding():
    # 실제 BGE-M3 로드(최초 다운로드 큼) → 팩토리 + dense 차원 검증.
    from app.ingest.embed import BGEM3Embedder, get_embedder

    emb = get_embedder()
    assert isinstance(emb, BGEM3Embedder)
    assert emb.dim == 1024

    vecs = emb.embed_texts(["보증기간은 24개월입니다.", "hello"])

    assert len(vecs) == 2
    assert len(vecs[0]) == 1024
    assert all(isinstance(x, float) for x in vecs[0])
