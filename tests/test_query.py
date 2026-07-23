import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.generate.llm import Generated, get_generator
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


class FakeGenerator:
    """고정 답변 반환 — 실제 LLM 호출 금지(handoff AC). test_answer.py 선례."""

    def generate(self, system: str, prompt: str) -> Generated:
        return Generated(
            text="보증기간은 24개월입니다. [1]",
            model="fake-model",
            input_tokens=10,
            output_tokens=5,
        )


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
    results = search("보증기간이 얼마인가요", top_k=1, conn=indexed, embedder=FakeEmbedder())

    assert results, "검색 결과가 비어있으면 안 된다"
    # top_k=1 — 존재가 아니라 순위를 검증: cosine 정렬이 관련 청크를 1등으로 올려야.
    top = results[0]
    assert "보증기간" in top.text
    # provenance(citation) 포함 — CLAUDE.md CRITICAL.
    assert top.source == "doc.docx"
    assert top.page == 1
    assert isinstance(top.score, float)


@pytest.mark.integration
def test_query_endpoint_returns_answer_with_citations(indexed):
    # 실제 BGE-M3 로드·Claude 클라이언트 생성을 피하려 의존성을 오버라이드.
    app.dependency_overrides[get_embedder] = lambda: FakeEmbedder()
    app.dependency_overrides[get_generator] = lambda: FakeGenerator()
    try:
        client = TestClient(app)
        # "보증기간이"가 아니라 "보증기간은": FakeEmbedder 결정적 점수가
        # 0.46으로 no_context_threshold(0.4)를 넘어야 거절 게이트를 통과한다.
        resp = client.post("/query", json={"question": "보증기간은 얼마인가요"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"], "answer가 비어있으면 안 된다"
    assert body["citations"], "citations가 비어있으면 안 된다"
    # 모든 citation의 source가 이 테스트에서 색인한 소스 집합의 부분집합 — 지어낸 출처 차단.
    assert {c["source"] for c in body["citations"]} <= {c.source for c in CHUNKS}
    # 인용 provenance(CLAUDE.md CRITICAL) — page 키 포함.
    assert all("page" in c for c in body["citations"])
    assert body["trace_id"]
    assert "results" not in body, "청크 뭉치(results)는 응답에서 제거됐다"
