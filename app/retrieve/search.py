"""온라인 dense 검색 — query 임베딩 → pgvector cosine ANN.

ADR-002: 0-rag-core는 dense-only(하이브리드+RRF·리랭킹은 다음 페이즈).
이 step은 검색된 청크만 반환한다 — LLM 생성/인용 문장 합성은 다음 페이즈.

온라인 호출이므로 @observe로 계측한다(CLAUDE.md CRITICAL). 계측은 검색 span으로,
내부의 query 임베딩(step 3에서 여기로 미룬 계측)도 이 span에 포함된다.

conn을 인자로 받으면 그 연결을, 없으면 DATABASE_URL로 직접 연결한다. 후자일 때만
psycopg를 지연 import해 소비 측이 드라이버 없이 이 모듈을 import할 수 있게 한다(index.py 선례).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.ingest.embed import Embedder, get_embedder
from observability.langfuse_setup import observe


@dataclass
class Retrieved:
    text: str
    source: str          # citation provenance (CLAUDE.md CRITICAL)
    page: int | None
    score: float         # cosine 유사도 (1 - distance), 높을수록 관련


@observe(name="search")
def search(
    query: str, *, top_k: int = 5, conn=None, embedder=None
) -> list[Retrieved]:
    embedder = embedder or get_embedder()
    vec = embedder.embed_texts([query])[0]
    literal = "[" + ",".join(map(str, vec)) + "]"

    own_conn = conn is None
    if own_conn:
        import psycopg

        from app.config import get_settings

        conn = psycopg.connect(get_settings().database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT text, source, page, 1 - (embedding <=> %s::vector) AS score
                FROM chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (literal, literal, top_k),
            )
            rows = cur.fetchall()
    finally:
        if own_conn:
            conn.close()
    return [Retrieved(text=t, source=s, page=p, score=sc) for t, s, p, sc in rows]
