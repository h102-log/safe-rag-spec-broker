import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.ingest.chunk import Chunk
from app.ingest.embed import get_embedder
from app.ingest.index import EMBED_DIM, ensure_schema, index_chunks
from app.retrieve.search import search


class FakeEmbedder:
    """결정적 bag-of-chars 임베딩(dim=1024). 겹치는 문자가 많을수록 cosine 유사 →
    실제 모델 다운로드 없이 검색 순위가 의미를 갖는다. 값이 non-zero라 cosine 유효."""

    dim = EMBED_DIM

    def embed_texts(self, texts):
        out = []
        for t in texts:
            v = [0.0] * self.dim
            for ch in t:
                v[ord(ch) % self.dim] += 1.0
            out.append(v)
        return out


CHUNKS = [
    Chunk(text="제품 보증기간은 24개월입니다.", source="doc.docx", page=1, chunk_index=0),
    Chunk(text="환불은 구매 후 30일 이내 가능합니다.", source="doc.docx", page=1, chunk_index=1),
    Chunk(text="배송은 영업일 기준 3일 소요됩니다.", source="doc.docx", page=2, chunk_index=2),
]


@pytest.fixture
def indexed(conn):
    # step 4 색인 경로 재사용: ensure_schema → index_chunks.
    ensure_schema(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE chunks RESTART IDENTITY")
    conn.commit()
    index_chunks(CHUNKS, FakeEmbedder(), conn)
    return conn


@pytest.mark.integration
def test_search_returns_relevant_chunk_with_provenance(indexed):
    results = search("보증기간이 얼마인가요", top_k=5, conn=indexed, embedder=FakeEmbedder())

    assert results, "검색 결과가 비어있으면 안 된다"
    # 관련 청크(보증기간)가 top_k 안에 있어야 한다.
    assert any("보증기간" in r.text for r in results)
    # provenance(citation) 포함 — CLAUDE.md CRITICAL.
    top = results[0]
    assert top.source == "doc.docx"
    assert top.page is not None
    assert isinstance(top.score, float)


@pytest.mark.integration
def test_query_endpoint_returns_results_and_trace_id(indexed):
    # 실제 BGE-M3 로드를 피하려 embedder 의존성을 FakeEmbedder로 오버라이드.
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    try:
        client = TestClient(app)
        resp = client.post("/query", json={"question": "보증기간이 얼마인가요"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["results"], "results가 비어있으면 안 된다"
    assert body["trace_id"]
    assert body["results"][0]["source"] == "doc.docx"
